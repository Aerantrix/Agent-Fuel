"""Agent Fuel: execution-level spend control for LLM agents.

The controller sits between the agent and everything it calls. Every model call
and every tool call passes through it. It holds the state the agent does not:
how much this run has cost, what has already been tried, and which dependency
has stopped answering.

Six components, each answering a different question:

    RunBudget        how much has this run spent
    TimeBudget       how long has this run taken
    LoopDetector     has anything changed since the last few steps
    CircuitBreaker   is this dependency answering at all
    ErrorClassifier  is retrying this error ever going to help
    PolicyEngine     given all of the above, allow, warn or stop

Nothing here is fitted or trained. Every decision rests on a fact the run has
already produced, which is the point: a statistical monitor needs recalibration
for each deployment, a counter does not.
"""

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    STOP = "stop"


@dataclass
class Verdict:
    decision: Decision
    mechanism: str | None = None
    reason: str = ""

    @property
    def stops(self):
        return self.decision is Decision.STOP


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------

@dataclass
class RunBudget:
    """A ceiling on one run, not on an account over a billing period.

    This is the backstop. It is the only thing that stops scenarios 9, 10 and
    11, where nothing is visibly broken and every step is reasoned.
    """

    max_tokens: int = 50_000
    max_cost_usd: float = 2.00
    tokens_used: int = 0
    cost_used: float = 0.0

    def record(self, tokens, cost):
        self.tokens_used += tokens
        self.cost_used += cost

    def check(self, projected_tokens=0):
        if self.tokens_used + projected_tokens >= self.max_tokens:
            return Verdict(
                Decision.STOP, "run_budget",
                f"token ceiling reached: {self.tokens_used}/{self.max_tokens}",
            )
        if self.cost_used >= self.max_cost_usd:
            return Verdict(
                Decision.STOP, "run_budget",
                f"cost ceiling reached: ${self.cost_used:.2f}/${self.max_cost_usd:.2f}",
            )
        if self.tokens_used >= 0.8 * self.max_tokens:
            return Verdict(
                Decision.WARN, "run_budget",
                f"{self.tokens_used} of {self.max_tokens} tokens used",
            )
        return Verdict(Decision.ALLOW)


@dataclass
class TimeBudget:
    """A wall-clock ceiling. Catches scenario 7, where tokens stay fine and
    the run still never ends in useful time."""

    max_seconds: float = 600.0
    started_at: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self):
        return time.monotonic() - self.started_at

    def check(self):
        if self.elapsed >= self.max_seconds:
            return Verdict(
                Decision.STOP, "time_budget",
                f"time ceiling reached: {self.elapsed:.0f}s/{self.max_seconds:.0f}s",
            )
        return Verdict(Decision.ALLOW)


@dataclass
class LoopDetector:
    """Structural evidence that the run is not progressing.

    Two fingerprints per call:

        call fingerprint    tool name + normalised arguments
        result fingerprint  tool name + a hash of what came back

    The result fingerprint is what catches scenario 2: the agent keeps changing
    its query, so the call fingerprint differs every time, but the answer is the
    same empty set. Scenario 13 is the control in the other direction: forty
    calls with genuinely different arguments must not collapse into one print.

    Errors are counted by the call fingerprint only. A failing dependency is
    the circuit breaker's evidence; printing the error text as a result would
    stop scenario 6, where a retry after each failure succeeds.
    """

    threshold: int = 3
    call_counts: dict = field(default_factory=dict)
    result_counts: dict = field(default_factory=dict)

    @staticmethod
    def _normalise(args):
        """Canonical form of the arguments.

        Deliberately conservative. Sorting keys and lowercasing strings is
        enough to make {"domain": "A", "period": "30d"} and
        {"period": "30d", "domain": "a"} the same call. Anything more
        aggressive risks collapsing scenario 13 into a false positive.
        """
        def norm(value):
            if isinstance(value, str):
                return value.strip().lower()
            if isinstance(value, dict):
                return {k: norm(v) for k, v in sorted(value.items())}
            if isinstance(value, (list, tuple)):
                return [norm(v) for v in value]
            return value

        return json.dumps(norm(args), sort_keys=True, default=str)

    @staticmethod
    def _digest(text):
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]

    def fingerprint_call(self, tool, args):
        return self._digest(f"{tool}|{self._normalise(args)}")

    def fingerprint_result(self, tool, args, result):
        # The request stays out of the print, and so do the fields of the
        # answer that only echo it back. An earlier version hashed the
        # arguments in, so a changed query always looked like a new result and
        # this print could never fire on its own.
        if isinstance(result, dict):
            result = {k: v for k, v in result.items() if k not in args}
        payload = json.dumps(result, sort_keys=True, default=str)[:4000]
        return self._digest(f"{tool}|{self._digest(payload)}")

    def observe(self, tool, args, result=None, failed=False):
        """Called after a tool returns or raises. Returns a verdict on the run so far."""
        call_fp = self.fingerprint_call(tool, args)
        self.call_counts[call_fp] = self.call_counts.get(call_fp, 0) + 1
        calls = self.call_counts[call_fp]

        results = 0
        if not failed:
            result_fp = self.fingerprint_result(tool, args, result)
            self.result_counts[result_fp] = self.result_counts.get(result_fp, 0) + 1
            results = self.result_counts[result_fp]

        if calls >= self.threshold:
            return Verdict(
                Decision.STOP, "loop_detector_call_fingerprint",
                f"identical call repeated {calls} times ({call_fp})",
            )
        if results >= self.threshold:
            return Verdict(
                Decision.STOP, "loop_detector_result_fingerprint",
                f"identical result returned {results} times ({result_fp})",
            )
        if calls == self.threshold - 1:
            return Verdict(
                Decision.WARN, "loop_detector_call_fingerprint",
                f"call repeated {self.threshold - 1} times",
            )
        if results == self.threshold - 1:
            return Verdict(
                Decision.WARN, "loop_detector_result_fingerprint",
                f"identical result returned {self.threshold - 1} times",
            )
        return Verdict(Decision.ALLOW)


@dataclass
class CircuitBreaker:
    """Per-dependency failure tracking over a sliding window.

    A consecutive-error counter is the obvious implementation and it fails on
    scenario 6: every other call succeeds, so the counter resets before it
    trips. The window counts failures among the last N calls instead, so an
    intermittent service still trips it.

    Latency is not failure. Scenario 14 is a slow but correct service, and it
    must not open the circuit.
    """

    window: int = 5
    max_failures: int = 4
    cooldown_seconds: float = 60.0
    history: dict = field(default_factory=dict)   # tool -> deque of bools
    opened_at: dict = field(default_factory=dict)  # tool -> timestamp

    def _window_for(self, tool):
        if tool not in self.history:
            self.history[tool] = deque(maxlen=self.window)
        return self.history[tool]

    def record(self, tool, failed):
        self._window_for(tool).append(bool(failed))

    def is_open(self, tool):
        opened = self.opened_at.get(tool)
        if opened is None:
            return False
        if time.monotonic() - opened >= self.cooldown_seconds:
            # half-open: allow one probe
            del self.opened_at[tool]
            self._window_for(tool).clear()
            return False
        return True

    def check(self, tool):
        if self.is_open(tool):
            return Verdict(
                Decision.STOP, "circuit_breaker",
                f"circuit open for {tool}; call refused without reaching the model",
            )

        window = self._window_for(tool)
        failures = sum(window)
        if failures >= self.max_failures:
            self.opened_at[tool] = time.monotonic()
            return Verdict(
                Decision.STOP, "circuit_breaker_sliding_window",
                f"{failures} failures in the last {len(window)} calls to {tool}",
            )
        if failures == self.max_failures - 1:
            return Verdict(
                Decision.WARN, "circuit_breaker_sliding_window",
                f"{failures} of the last {len(window)} calls to {tool} failed",
            )
        return Verdict(Decision.ALLOW)


@dataclass
class ErrorClassifier:
    """Is retrying this error ever going to help.

    This is the one component that makes a judgement rather than counting a
    fact, and the paper should say so. The rule below is a heuristic keyed on
    HTTP status and exception type; it is deliberately small and explicit so a
    reader can disagree with it.
    """

    TERMINAL_STATUSES = {400, 401, 403, 404, 405, 410, 422}
    TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}

    def classify(self, error):
        status = getattr(error, "status", None)
        if status in self.TERMINAL_STATUSES:
            return "terminal"
        if status in self.TRANSIENT_STATUSES:
            return "transient"
        if isinstance(error, AuthFailedLike):
            return "terminal"
        return "unknown"

    def check(self, error):
        kind = self.classify(error)
        if kind == "terminal":
            return Verdict(
                Decision.STOP, "error_classifier",
                f"{type(error).__name__} is terminal; retrying cannot succeed",
            )
        return Verdict(Decision.ALLOW)


class AuthFailedLike(Exception):
    """Duck type so control/ does not import sandbox/."""


# --------------------------------------------------------------------------
# Policy and controller
# --------------------------------------------------------------------------

WARNING_TEMPLATE = (
    "Controller notice: {reason}. Stop retrying this tool and either proceed "
    "with partial results or report what you could not retrieve."
)


@dataclass
class Journal:
    """One row per decision. This is the evidence base for the Results section
    and the only way to build the mechanism-attribution table."""

    rows: list = field(default_factory=list)

    def write(self, **row):
        self.rows.append(row)

    def to_csv_rows(self):
        return self.rows


@dataclass
class AgentFuel:
    """The controller. Wrap the agent loop with this."""

    max_tokens: int = 50_000
    max_cost_usd: float = 2.00
    max_seconds: float = 600.0
    loop_threshold: int = 3
    breaker_window: int = 5
    breaker_failures: int = 4
    enabled: set = field(default_factory=lambda: {
        "run_budget", "time_budget", "loop_detector",
        "circuit_breaker", "error_classifier",
    })

    def __post_init__(self):
        self.budget = RunBudget(self.max_tokens, self.max_cost_usd)
        self.clock = TimeBudget(self.max_seconds)
        self.loops = LoopDetector(self.loop_threshold)
        self.breaker = CircuitBreaker(self.breaker_window, self.breaker_failures)
        self.errors = ErrorClassifier()
        self.journal = Journal()
        self.step = 0
        self.pending_warnings = []
        self.halted = None  # the Verdict that ended the run

    # -- internal ---------------------------------------------------------

    def _resolve(self, verdicts):
        """Strongest verdict wins: stop over warn over allow."""
        for v in verdicts:
            if v.decision is Decision.STOP:
                return v
        for v in verdicts:
            if v.decision is Decision.WARN:
                return v
        return Verdict(Decision.ALLOW)

    def _active(self, name):
        return name in self.enabled

    def _log(self, event, verdict, **extra):
        self.journal.write(
            step=self.step,
            event=event,
            decision=verdict.decision.value,
            mechanism=verdict.mechanism,
            reason=verdict.reason,
            tokens_used=self.budget.tokens_used,
            cost_used=round(self.budget.cost_used, 4),
            elapsed=round(self.clock.elapsed, 2),
            **extra,
        )

    # -- public API -------------------------------------------------------

    def before_step(self):
        """Call at the top of each agent turn. Returns a Verdict."""
        self.step += 1
        checks = []
        if self._active("run_budget"):
            checks.append(self.budget.check())
        if self._active("time_budget"):
            checks.append(self.clock.check())

        verdict = self._resolve(checks)
        self._log("before_step", verdict)
        if verdict.stops:
            self.halted = verdict
        return verdict

    def before_tool(self, tool, args):
        """Call before invoking a tool. A STOP here costs zero tokens, which
        is the whole value of the circuit breaker."""
        checks = []
        if self._active("circuit_breaker"):
            checks.append(self.breaker.check(tool))

        verdict = self._resolve(checks)
        self._log("before_tool", verdict, tool=tool)
        if verdict.decision is Decision.WARN:
            self.pending_warnings.append(WARNING_TEMPLATE.format(reason=verdict.reason))
        if verdict.stops:
            self.halted = verdict
        return verdict

    def after_tool(self, tool, args, result=None, error=None):
        """Call after a tool returns or raises."""
        checks = []
        failed = error is not None

        if self._active("circuit_breaker"):
            self.breaker.record(tool, failed)

        if failed and self._active("error_classifier"):
            checks.append(self.errors.check(error))

        if self._active("loop_detector"):
            checks.append(self.loops.observe(tool, args, result, failed=failed))

        verdict = self._resolve(checks)
        self._log("after_tool", verdict, tool=tool, failed=failed)

        if verdict.decision is Decision.WARN:
            self.pending_warnings.append(WARNING_TEMPLATE.format(reason=verdict.reason))
        if verdict.stops:
            self.halted = verdict
        return verdict

    def record_model_call(self, input_tokens, output_tokens, cost):
        """Call after every model call so the budget sees real numbers."""
        self.budget.record(input_tokens + output_tokens, cost)

    def drain_warnings(self):
        """Messages to inject into the agent's context before its next turn.

        This is the middle rung between allow and stop: the run continues, but
        the agent is told what the controller can see and it cannot.
        """
        out, self.pending_warnings = self.pending_warnings, []
        return out

    def summary(self):
        return {
            "steps": self.step,
            "tokens": self.budget.tokens_used,
            "cost": round(self.budget.cost_used, 4),
            "seconds": round(self.clock.elapsed, 2),
            "halted": self.halted is not None,
            "halt_mechanism": self.halted.mechanism if self.halted else None,
            "halt_reason": self.halted.reason if self.halted else None,
        }


ARMS = {
    # A, B and C carry no in-run components. Their enforcement lives in
    # run_experiment.py: a shared account allowance for B, a step ceiling for C.
    "A": set(),
    "B": set(),
    "C": set(),
    # D through G add exactly one halting mechanism at a time. time_budget is
    # present throughout and is not part of the ladder: it is a wall-clock
    # guard, not one of the three mechanisms under study.
    "D": {"run_budget", "time_budget"},
    "E": {"run_budget", "time_budget", "loop_detector"},
    "F": {"run_budget", "time_budget", "loop_detector", "circuit_breaker"},
    "G": {"run_budget", "time_budget", "loop_detector",
          "circuit_breaker", "error_classifier"},
}

# A, B and C have no spend control of their own, so they run under a ceiling
# high enough not to interfere with the measurement and low enough that a
# single run cannot run away.
UNCONTROLLED = dict(max_tokens=200_000, max_cost_usd=20.0, max_seconds=3600)


def build_controller(config_code, scenario_overrides=None):
    """Return a controller configured for one of the seven experiment arms.

    A  no control            the baseline; only the harness ceiling applies
    B  account-level limit   a shared allowance; enforced in run_experiment.py
    C  iteration cap         a step ceiling; enforced in run_experiment.py
    D  run budget only       the first execution-level control
    E  D + loop detector     adds repetition detection
    F  E + circuit breaker   adds failure-rate detection
    G  Agent Fuel            adds error classification and the warn rung

    A, B and C are the approaches being compared against. D through G are an
    ablation ladder: the difference between two adjacent arms is the
    contribution of the one mechanism that separates them, which is what
    objective 2 promises to measure.
    """
    overrides = scenario_overrides or {}

    if config_code not in ARMS:
        raise ValueError(f"unknown configuration: {config_code}")

    enabled = set(ARMS[config_code])

    if config_code in ("A", "B", "C"):
        return AgentFuel(enabled=enabled, **{**UNCONTROLLED, **overrides})

    return AgentFuel(enabled=enabled, **overrides)
