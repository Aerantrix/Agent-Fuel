"""Run one batch of Agent Fuel runs for one model configuration.

Started by server.py, one process per configuration, because agent/runner.py
reads its backend, model and thinking mode from the environment at import.
Every finished run is appended to data/runs.jsonl in the shape the dashboard
reads; data/now.json says what is running right now.
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Qwen has neither a thinking mode nor an effort setting. Haiku 5.5 runs four
# ways: thinking on or off, effort low or high.
CONFIGS = {
    "qwen": {"label": "qwen2.5:7b", "backend": "ollama",
             "model": "qwen2.5:7b", "thinking": "on", "effort": ""},
}
for _think, _effort in (("on", "low"), ("on", "high"), ("off", "low"), ("off", "high")):
    _mode = "thinking" if _think == "on" else "no-thinking"
    CONFIGS[f"haiku-{'think' if _think == 'on' else 'nothink'}-{_effort}"] = {
        "label": f"claude-haiku-5-5+{_mode}+{_effort}", "backend": "anthropic",
        "model": "claude-haiku-5-5", "thinking": _think, "effort": _effort}

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True)
ap.add_argument("--data", required=True)
ap.add_argument("--config", required=True, choices=sorted(CONFIGS))
ap.add_argument("--scenarios", required=True, help="comma-separated ids")
ap.add_argument("--arms", required=True, help="comma-separated codes")
ap.add_argument("--repeats", type=int, default=1)
ap.add_argument("--repeat-ids", default="",
                help="comma-separated repeat numbers to run instead of 1..repeats, e.g. 2,3 to fill gaps")
ap.add_argument("--max-cost", type=float, default=1.0, help="stop this batch past this many dollars")
ap.add_argument("--condition", default="base", choices=["lenient", "base", "strict"])
ap.add_argument("--real-prompt", default="",
                help="a file from docs/real-prompts/: run under that framework's default prompt "
                     "instead of --condition; the run is recorded with the file's name as its condition")
ap.add_argument("--error-hint", action="store_true",
                help="the fourth condition: the service's transient errors add 'Please try again later.'; "
                     "the run is recorded with '+hint' after the condition")
ap.add_argument("--temperature", type=float, default=0.0)
ap.add_argument("--id-suffix", default="",
                help="appended to every run id, so console runs never replace a record of the frozen database")
args = ap.parse_args()

cfg = CONFIGS[args.config]
# Must be set before agent.runner is imported: it reads them at import time.
os.environ["AGENT_FUEL_BACKEND"] = cfg["backend"]
os.environ["AGENT_FUEL_MODEL"] = cfg["model"]
os.environ["AGENT_FUEL_THINKING"] = cfg["thinking"]
os.environ["AGENT_FUEL_EFFORT"] = cfg["effort"]
os.environ["AGENT_FUEL_PROMPT"] = args.condition
os.environ["AGENT_FUEL_TEMPERATURE"] = str(args.temperature)
if args.real_prompt:
    os.environ["AGENT_FUEL_REAL_PROMPT"] = str(Path(args.real_prompt).resolve())
    args.condition = Path(args.real_prompt).stem  # e.g. P03_llamaindex_react
if args.error_hint:
    os.environ["AGENT_FUEL_ERROR_HINT"] = "on"
    args.condition += "+hint"  # e.g. base+hint

sys.path.insert(0, args.repo)
import agent.runner as runner  # noqa: E402
from evaluation import run_experiment as rx  # noqa: E402

# The condition is the prompt level (lenient, base, strict) and lives in
# agent/runner.py. It changes the first message and nothing else: the tool's
# replies are passed to the agent as they are at every level.

# The temperature a run actually sampled at: models in NO_TEMPERATURE ignore
# the setting and run at the provider default, recorded as "default".
TEMP = "default" if cfg["model"] in runner.NO_TEMPERATURE else args.temperature

DATA = Path(args.data)
DATA.mkdir(parents=True, exist_ok=True)
RUNS = DATA / "runs.jsonl"
NOW = DATA / "now.json"
LIVE = DATA / "live.json"  # the run in progress, step by step, for the console's Run view

wanted = {int(x) for x in args.scenarios.split(",") if x}
arms = [a.strip().upper() for a in args.arms.split(",") if a.strip()]
scenarios = [s for s in rx.SCENARIOS["scenarios"] if s["id"] in wanted]
repeat_ids = [int(x) for x in args.repeat_ids.split(",") if x.strip()] or list(range(1, args.repeats + 1))
plan = [(s, a, r) for s in scenarios for a in arms for r in repeat_ids]

spent = {"usd": 0.0, "tokens": 0}
current = {"label": "", "trace": [], "seen": 0, "index": 0, "controller": None, "meta": {}}

# The controller of the run in progress, so its decisions can be shown live.
_real_build = rx.build_controller


def _capture_controller(code, *a, **kw):
    c = _real_build(code, *a, **kw)
    current["controller"] = c
    # The tool's reply for the current step, as soon as the controller sees it,
    # so the live view does not wait for the next model call to learn it.
    real_after = c.after_tool

    def after_tool(tool, args, result=None, error=None):
        if current["trace"]:
            current["trace"][-1]["tool_result"] = (f"Tool error: {error}" if error is not None else f"Tool result: {result}")[:2000]
        verdict = real_after(tool, args, result=result, error=error)
        write_live()
        return verdict

    c.after_tool = after_tool
    return c


rx.build_controller = _capture_controller


def stamp():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_now(active, doing):
    NOW.write_text(json.dumps({
        "active": active, "doing": doing, "updated": stamp(),
        "config": cfg["label"] + " · " + args.condition
        + ("" if TEMP in (0, "default") else f" · t={TEMP:g}"), "done": current["index"], "total": len(plan),
        "spent_usd": round(spent["usd"], 4), "tokens": spent["tokens"],
    }, ensure_ascii=False), encoding="utf-8")


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def write_live(done=False, outcome=None):
    """The run in progress: every step so far and every controller decision so far."""
    c = current["controller"]
    trace = current["trace"]
    tokens = sum(s["in"] + s["out"] for s in trace)
    doc = dict(current["meta"], active=not done, done=done, updated=stamp(), steps=trace,
               decisions=decision_rows(c.journal.rows) if c is not None else [],
               tokens=tokens, step=len(trace), total=len(plan), index=current["index"] + 1)
    if outcome:
        doc["outcome"] = outcome
    LIVE.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def stop(signum, frame):
    write_now(False, f"Stopped by hand after {current['index']} of {len(plan)}")
    log("stopped")
    sys.exit(0)


signal.signal(signal.SIGTERM, stop)

real_call = runner.call_model


def traced_call(messages, model=runner.DEFAULT_MODEL):
    """Record each step: what the agent said and what came back from the tool."""
    trace = current["trace"]
    if trace:
        new = [m["content"] for m in messages[current["seen"]:] if m["role"] in ("user", "tool")]
        trace[-1]["tool_result"] = "\n".join(new)[:2000]
    text, tin, tout, cost = real_call(messages, model)
    spent["usd"] += cost
    spent["tokens"] += tin + tout
    trace.append({"step": len(trace) + 1, "in": tin, "out": tout, "reply": text[:4000]})
    current["seen"] = len(messages) + 1  # the runner appends this reply next
    write_now(True, f"{current['label']} · step {len(trace)}")
    write_live()
    return text, tin, tout, cost


runner.call_model = traced_call


def decision_rows(journal):
    keep = ("step", "event", "decision", "mechanism", "reason", "tokens_used", "tool", "failed")
    out = []
    for row in journal:
        d = {k: row.get(k) for k in keep if row.get(k) not in (None, "")}
        out.append(d)
    return out


log(f"{cfg['label']}, {args.condition}, temperature {TEMP}: {len(plan)} runs, spend cap ${args.max_cost:.2f}")
errors_in_a_row = 0

for i, (scenario, arm, repeat) in enumerate(plan, start=1):
    if spent["usd"] >= args.max_cost:
        log(f"spend cap ${args.max_cost:.2f} reached, stopping")
        write_now(False, f"Stopped: spend cap ${args.max_cost:.2f} reached")
        sys.exit(0)

    current.update(index=i - 1, trace=[], seen=0,
                   label=f"scenario {scenario['id']}, arm {arm}, repeat {repeat} ({i} of {len(plan)})")
    write_now(True, current["label"])
    log(f"start: {current['label']}")
    started = time.monotonic()
    run_id = f"{cfg['label']}-s{scenario['id']:02d}-{arm}-r{repeat}".replace(":", "_").replace("+", "_")
    run_id += "-" + args.condition
    if TEMP not in (0, "default"):
        run_id += f"-t{TEMP:g}"
    run_id += args.id_suffix
    current["meta"] = {"id": run_id, "model": cfg["label"], "condition": args.condition, "temperature": TEMP,
                       "scenario_id": scenario["id"], "arm": arm, "repeat": repeat, "label": current["label"],
                       "started": stamp()}
    current["controller"] = None
    write_live()

    try:
        row, journal = rx.one_run(scenario, arm, repeat)
        errors_in_a_row = 0
    except Exception as exc:  # an API error ends this run; the batch goes on
        errors_in_a_row += 1
        log(f"error: {type(exc).__name__}: {str(exc)[:300]}")
        doc = {"id": run_id, "model": cfg["label"], "condition": args.condition, "temperature": TEMP,
               "scenario_id": scenario["id"], "arm": arm, "repeat": repeat, "ts": stamp(), "error": f"{type(exc).__name__}: {str(exc)[:500]}",
               "steps": len(current["trace"]), "trace": current["trace"]}
        with RUNS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        write_live(done=True, outcome={"error": doc["error"]})
        if errors_in_a_row >= 3:
            log("three errors in a row, stopping")
            write_now(False, "Stopped: three errors in a row. See the launch log.")
            sys.exit(1)
        continue

    trace = current["trace"]
    curve, acc = [], 0
    for s in trace:
        acc += s["in"] + s["out"]
        curve.append(acc)
    doc = {
        "id": run_id, "model": cfg["label"], "condition": args.condition, "temperature": TEMP,
        "scenario_id": scenario["id"], "arm": arm, "repeat": repeat, "ts": stamp(), "steps": row["steps"], "tokens": row["tokens"],
        "cost_usd": row["cost_usd"], "halted": bool(row["halted"]),
        "halt_mechanism": row["halt_mechanism"], "halt_reason": row["halt_reason"],
        "expected_mechanism": row["expected_mechanism"],
        "mechanism_matched": bool(row["mechanism_matched"]),
        "task_completed": bool(row["task_completed"]),
        "task_completable": bool(row["task_completable"]),
        "deviations": row.get("deviations", []),
        "seconds": round(time.monotonic() - started, 1),
        "trace": trace, "curve": curve, "decisions": decision_rows(journal),
    }
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    # the finished run's own trace holds the last tool result; the live view takes it from here
    current["trace"] = trace
    write_live(done=True, outcome={k: doc[k] for k in ("steps", "tokens", "cost_usd", "halted", "halt_mechanism",
                                                        "halt_reason", "task_completed", "task_completable")})
    current["index"] = i
    log(f"done: {row['steps']} steps, {row['tokens']} tokens, ${row['cost_usd']:.4f}"
        + (f", halted by {row['halt_mechanism']}" if row["halted"] else ""))

write_now(False, f"Finished: {len(plan)} runs, {cfg['label']}, spent ${spent['usd']:.2f}")
log(f"finished, spent ${spent['usd']:.4f}")
