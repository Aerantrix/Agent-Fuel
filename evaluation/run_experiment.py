"""Experiment runner: 15 scenarios x 7 configurations x 3 repeats = 315 runs.

Writes two CSVs:
    results/runs.csv       one row per run
    results/decisions.csv  one row per controller decision, for attribution

SAFETY: HARD_CEILING stops the whole sweep if total spend runs away. Set it
before the first real run. Configuration A is designed to burn tokens; without
this you repeat the incident the project is about, at your own expense.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from control.agent_fuel import build_controller, Decision  # noqa: E402
from sandbox.fake_tools import build_tools  # noqa: E402
from agent.runner import run_agent  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = json.loads((ROOT / "evaluation" / "scenarios.json").read_text())
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

HARD_CEILING_TOKENS = 5_250_000      # whole sweep, not one run; set this yourself
                                     # from the pilot before the first real run
STEP_CAP_FOR_CONFIG_C = 15           # the blunt instrument being compared
ACCOUNT_BUDGET_FOR_CONFIG_B = 500_000  # shared across runs, like a real plan

_spent_total = 0
_account_remaining = ACCOUNT_BUDGET_FOR_CONFIG_B


def one_run(scenario, config_code, repeat):
    """Execute a single run and return its result row."""
    global _spent_total, _account_remaining

    tools = build_tools(scenario)
    controller = build_controller(config_code)

    # Configuration-specific caps that are not part of Agent Fuel itself.
    step_cap = STEP_CAP_FOR_CONFIG_C if config_code == "C" else None
    account_cap = _account_remaining if config_code == "B" else None

    started = time.monotonic()
    outcome = run_agent(
        task=scenario["task"],
        tools=tools,
        controller=controller,
        step_cap=step_cap,
        account_cap=account_cap,
    )
    elapsed = time.monotonic() - started

    summary = controller.summary()
    _spent_total += summary["tokens"]
    if config_code == "B":
        _account_remaining = max(0, _account_remaining - summary["tokens"])

    return {
        "scenario_id": scenario["id"],
        "scenario_slug": scenario["slug"],
        "group": scenario["group"],
        "config": config_code,
        "repeat": repeat,
        # The setting this arm was run at, so analyse.py can draw a curve per
        # mechanism instead of a single point. With one value per arm there is
        # one point and the curve figure is skipped. To sweep, loop this
        # function over several values of STEP_CAP_FOR_CONFIG_C (arm C) or
        # max_tokens (arms D to G) and note that each extra value multiplies
        # the number of runs for that arm.
        "param": step_cap if config_code == "C" else (
            controller.budget.max_tokens if config_code in ("D", "E", "F", "G") else ""),
        "tokens": summary["tokens"],
        "cost_usd": summary["cost"],
        "steps": summary["steps"],
        "seconds": round(elapsed, 2),
        "halted": summary["halted"],
        "halt_mechanism": summary["halt_mechanism"],
        "halt_reason": summary["halt_reason"],
        "task_completed": outcome["completed"],
        "task_completable": scenario["task_completable"],
        # The two numbers that answer the research question:
        "false_interruption": (
            summary["halted"] and scenario["group"] == "C"
        ),
        "expected_mechanism": scenario["expected_mechanism"],
        "mechanism_matched": (
            summary["halt_mechanism"] == scenario["expected_mechanism"]
        ),
    }, controller.journal.to_csv_rows()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the Agent Fuel sweep, or any subset of it.")
    parser.add_argument("--only", type=int, nargs="+", metavar="ID",
                        help="run only these scenario ids")
    parser.add_argument("--arms", nargs="+", metavar="CODE",
                        help="run only these arms, e.g. --arms A G")
    parser.add_argument("--repeats", type=int,
                        help="override the repeat count (default %d)"
                             % SCENARIOS["repeats"])
    parser.add_argument("--list", action="store_true",
                        help="print the scenarios and arms, then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would run and the run count, then exit")
    return parser.parse_args(argv)


def select(args):
    scenarios = SCENARIOS["scenarios"]
    configs = SCENARIOS["configurations"]
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only]
        missing = set(args.only) - {s["id"] for s in scenarios}
        if missing:
            sys.exit(f"No such scenario id: {sorted(missing)}")
    if args.arms:
        wanted = {a.upper() for a in args.arms}
        configs = [c for c in configs if c["code"] in wanted]
        missing = wanted - {c["code"] for c in configs}
        if missing:
            sys.exit(f"No such arm: {sorted(missing)}")
    repeats = args.repeats or SCENARIOS["repeats"]
    return scenarios, configs, repeats


def main(argv=None):
    args = parse_args(argv)
    scenarios, configs, repeats = select(args)

    if args.list:
        for s in SCENARIOS["scenarios"]:
            print(f"  {s['id']:>2}  {s['slug']:<24} group {s['group']}  {s['title']}")
        print()
        for c in SCENARIOS["configurations"]:
            print(f"  {c['code']}  {c['name']}")
        return

    total = len(scenarios) * len(configs) * repeats
    print(f"{len(scenarios)} scenarios x {len(configs)} arms x {repeats} repeats "
          f"= {total} runs")
    if args.dry_run:
        for s in scenarios:
            print(f"  {s['id']:>2} {s['slug']:<24} "
                  f"{' '.join(c['code'] for c in configs)}")
        return

    rows = []
    decisions = []

    for scenario in scenarios:
        for config in configs:
            for repeat in range(1, repeats + 1):
                if _spent_total >= HARD_CEILING_TOKENS:
                    print(f"HARD CEILING HIT at {_spent_total} tokens. Stopping.")
                    _write(rows, decisions)
                    return

                print(f"  {scenario['slug']:<24} {config['code']}  run {repeat}", flush=True)
                row, journal = one_run(scenario, config["code"], repeat)
                rows.append(row)
                for d in journal:
                    decisions.append(dict(
                        d,
                        scenario_id=scenario["id"],
                        config=config["code"],
                        repeat=repeat,
                    ))

    _write(rows, decisions)
    print(f"\nDone. {len(rows)} runs, {_spent_total} tokens total.")


def _write(rows, decisions):
    if rows:
        with (RESULTS / "runs.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    if decisions:
        keys = sorted({k for d in decisions for k in d})
        with (RESULTS / "decisions.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(decisions)


if __name__ == "__main__":
    main()
