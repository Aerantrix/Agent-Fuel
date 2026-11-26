"""The controller against the stub, scenario by scenario.

Each test plays a scripted agent against sandbox/fake_tools.py under the full
controller (configuration G) and checks the decision the scenario expects in
evaluation/scenarios.json: which mechanism stops a broken run and at which
call, and that the healthy tasks run to the end. No model is called; the
agent's moves are written out, so every test is deterministic.

    python -m pytest tests
"""

import json
from pathlib import Path

import pytest

from control.agent_fuel import AgentFuel, Decision, LoopDetector, build_controller
from sandbox.fake_tools import FakeAnalytics, ToolError

SCENARIOS = {s["id"]: s for s in json.loads(
    (Path(__file__).resolve().parents[1] / "evaluation" / "scenarios.json").read_text())["scenarios"]}

TOKENS_PER_STEP = 500   # small enough that the run budget never interferes unless a test wants it


def play(controller, tool, calls, tokens=TOKENS_PER_STEP):
    """Run a scripted agent: one model call and one tool call per step, as
    agent/runner.py does, until the calls run out or the controller stops it.

    Returns (steps taken, the verdicts of the run, the warnings handed to the agent)."""
    verdicts, warnings = [], []
    for args in calls:
        v = controller.before_step()
        verdicts.append(v)
        if v.stops:
            break
        controller.record_model_call(tokens - 50, 50, 0.0)
        v = controller.before_tool("analytics", args)
        verdicts.append(v)
        if v.stops:
            break
        try:
            result = tool.get_metrics(**args)
            v = controller.after_tool("analytics", args, result=result)
        except ToolError as exc:
            v = controller.after_tool("analytics", args, error=exc)
        verdicts.append(v)
        warnings += controller.drain_warnings()
        if v.stops:
            break
    return controller.step, verdicts, warnings


def same(n, **args):
    return [dict({"domain": "example.com", "period": "30d"}, **args) for _ in range(n)]


def stub(scenario_id):
    return FakeAnalytics(failure_mode=SCENARIOS[scenario_id]["failure_mode"])


# -- group A: broken services, each stopped by the mechanism the scenario names --

def test_s1_service_unavailable_identical_retries_stopped_by_loop_detector():
    g = build_controller("G")
    steps, verdicts, warnings = play(g, stub(1), same(20))
    assert g.halted.mechanism == "loop_detector_call_fingerprint"
    assert steps == 3                                        # warned after the second call, stopped at the third
    assert any("Controller notice" in w for w in warnings)
    assert SCENARIOS[1]["expected_mechanism"] == "loop_detector"


def test_s1_service_unavailable_varied_retries_stopped_by_circuit_breaker():
    """An agent that changes its call every time escapes the loop detector;
    the breaker sees four failures in five calls and refuses the fifth."""
    g = build_controller("G")
    calls = [{"domain": "example.com", "period": f"{d}d"} for d in range(1, 21)]
    steps, verdicts, _ = play(g, stub(1), calls)
    assert g.halted.mechanism == "circuit_breaker_sliding_window"
    assert steps == 5
    assert verdicts[-1].stops and verdicts[-1] is g.halted   # refused before the call reached the stub


def test_s2_empty_response_reworded_queries_stopped_by_result_fingerprint():
    """The agent rewords its query, so every call is new; the answer is the
    same empty set, and the result fingerprint ignores the echoed request."""
    g = build_controller("G")
    calls = [{"domain": d, "period": "30d"} for d in ("example.com", "www.example.com", "example.com/", "example.org")]
    steps, _, _ = play(g, stub(2), calls)
    assert g.halted.mechanism == "loop_detector_result_fingerprint"
    assert steps == 3


def test_s3_auth_error_stopped_at_the_first_call_by_error_classifier():
    g = build_controller("G")
    steps, _, warnings = play(g, stub(3), same(20))
    assert g.halted.mechanism == "error_classifier"
    assert steps == 1                                        # "should stop on the first occurrence"
    assert warnings == []                                    # nothing for a warning to achieve


def test_s4_timeout_is_transient_and_left_to_the_loop_detector():
    g = build_controller("G")
    steps, _, _ = play(g, stub(4), same(20))
    assert g.halted.mechanism == "loop_detector_call_fingerprint"   # 504 is transient: no classifier stop
    assert steps == 3


def test_s5_broken_pagination_stopped_by_result_fingerprint():
    """The agent follows next_cursor; the stub returns the first page again."""
    g = build_controller("G")
    calls = [{"domain": "example.com", "period": "30d"}] + same(20, cursor="page_2")
    steps, _, _ = play(g, stub(5), calls)
    assert g.halted.mechanism == "loop_detector_result_fingerprint"
    assert steps == 3


def test_s8_malformed_body_stopped_by_loop_detector():
    g = build_controller("G")
    steps, _, _ = play(g, stub(8), same(20))
    assert g.halted.mechanism.startswith("loop_detector")
    assert steps == 3


# -- group C and R: healthy work the controller must not stop --

def test_s6_flapping_service_retry_after_each_failure_is_not_stopped():
    """Every other call fails and a retry succeeds. The agent retries a failed
    domain once and moves on: ten domains in nineteen calls. At most two of
    any five calls fail, so the breaker never opens; the identical retry earns
    a warning from the loop detector, never a stop."""
    g = build_controller("G")
    tool = stub(6)
    calls = 0
    for i in range(1, 11):
        args = {"domain": f"site{i}.com", "period": "30d"}
        for _attempt in range(2):
            assert not g.before_step().stops
            g.record_model_call(450, 50, 0.0)
            assert not g.before_tool("analytics", args).stops
            calls += 1
            try:
                v = g.after_tool("analytics", args, result=tool.get_metrics(**args))
                assert not v.stops
                break
            except ToolError as exc:
                assert not g.after_tool("analytics", args, error=exc).stops
    assert g.halted is None
    assert calls == 19
    assert SCENARIOS[6]["expected_decision"] == "allow"


def test_s13_forty_different_domains_are_not_a_loop():
    g = build_controller("G", {"max_tokens": 10_000_000})
    calls = [{"domain": f"site{i}.com", "period": "30d"} for i in range(1, 41)]
    steps, verdicts, warnings = play(g, stub(13), calls)
    assert g.halted is None and steps == 40
    assert warnings == []


def test_s13_the_50k_run_budget_cuts_the_honest_task():
    """The weakness the paper reports: the forty-domain task costs more than
    the 50,000-token default, so the run budget stops honest work."""
    g = build_controller("G")
    calls = [{"domain": f"site{i}.com", "period": "30d"} for i in range(1, 41)]
    steps, verdicts, warnings = play(g, stub(13), calls, tokens=2_500)
    assert g.halted.mechanism == "run_budget"
    assert steps == 21                                        # 20 steps x 2,500 tokens reach the ceiling


def test_s15_healthy_task_runs_to_the_end():
    g = build_controller("G")
    calls = [{"domain": "example.com", "period": p} for p in ("7d", "30d", "90d")] + \
            [{"domain": "example.org", "period": p} for p in ("7d", "30d", "90d")]
    steps, _, warnings = play(g, stub(15), calls)
    assert g.halted is None and steps == 6 and warnings == []


# -- the ablation ladder: each configuration adds one mechanism --

@pytest.mark.parametrize("arm,mechanism,steps", [
    ("A", None, 20),                                         # no control: the agent runs out its calls
    ("D", None, 20),                                         # run budget only: 20 x 500 tokens stay under 50k
    ("E", "loop_detector_call_fingerprint", 3),              # + loop detector
    ("F", "loop_detector_call_fingerprint", 3),              # + circuit breaker: the loop still fires first
    ("G", "error_classifier", 1),                            # + error classifier: the first 401
])
def test_auth_error_down_the_ladder(arm, mechanism, steps):
    c = build_controller(arm)
    taken, _, _ = play(c, stub(3), same(20))
    assert (c.halted.mechanism if c.halted else None) == mechanism
    assert taken == steps


def test_unknown_configuration_is_refused():
    with pytest.raises(ValueError):
        build_controller("Z")


# -- the components on their own --

def test_call_fingerprint_ignores_case_spacing_and_key_order():
    fp = LoopDetector().fingerprint_call
    assert fp("analytics", {"domain": " Example.COM", "period": "30d"}) == \
           fp("analytics", {"period": "30d", "domain": "example.com"})
    assert fp("analytics", {"domain": "site1.com"}) != fp("analytics", {"domain": "site2.com"})


def test_errors_never_count_as_identical_results():
    """Failed calls with different arguments must not trip the result
    fingerprint: that would stop the flapping service."""
    loops = LoopDetector()
    for d in range(5):
        v = loops.observe("analytics", {"domain": f"s{d}.com"}, failed=True)
    assert v.decision is Decision.ALLOW


def test_breaker_half_opens_after_the_cooldown(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("control.agent_fuel.time.monotonic", lambda: clock[0])
    g = AgentFuel(enabled={"circuit_breaker"})
    for _ in range(4):
        g.breaker.record("analytics", failed=True)
    assert g.before_tool("analytics", {}).mechanism == "circuit_breaker_sliding_window"
    assert g.before_tool("analytics", {}).mechanism == "circuit_breaker"        # open: refused at once
    clock[0] += 61
    assert g.before_tool("analytics", {}).decision is Decision.ALLOW            # one probe let through


def test_stop_outranks_warn():
    g = build_controller("G")
    from control.agent_fuel import Verdict
    v = g._resolve([Verdict(Decision.WARN, "a"), Verdict(Decision.STOP, "b"), Verdict(Decision.ALLOW)])
    assert v.mechanism == "b"


def test_every_decision_is_journaled():
    g = build_controller("G")
    play(g, stub(3), same(3))
    events = [r["event"] for r in g.journal.rows]
    assert events == ["before_step", "before_tool", "after_tool"]
    assert g.journal.rows[-1]["mechanism"] == "error_classifier"
