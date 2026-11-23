"""Live controller runs against the replay: does the computed arm agree?

    python -m evaluation.compare_live            # console/data/runs.jsonl
    python -m evaluation.compare_live FILE.jsonl [FILE.jsonl ...]

For every live run of a controlled arm (D to G) the matching arm A run of
the same model, condition, temperature, scenario and repeat is replayed
through the same controller, as evaluation/analyse.py does, and the two are
put side by side: the step and mechanism at which each halted, and the
tokens each spent. The live run is a fresh sample of the model, so steps and
tokens differ by sampling; what should agree is whether the controller
halted and by which mechanism. Writes results/live_vs_computed.md and
prints it.
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation import analyse  # noqa: E402

RESULTS = ROOT / "results"


def read(paths):
    rows = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if "error" not in r and not r.get("computed"):
                    rows.append(r)
    latest = {}
    for r in rows:
        latest[r["id"]] = r
    return list(latest.values())


def key(r):
    return (r["model"], r.get("condition"), str(r.get("temperature")), r["scenario_id"], r.get("repeat"))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    paths = argv or [analyse.RUNS_FILE]
    runs = read(paths)
    base = {key(r): r for r in runs if r["arm"] == "A"}
    live = [r for r in runs if r["arm"] in ("D", "E", "F", "G")]
    if not live:
        sys.exit("No live runs of arms D to G in the file(s).")
    out = []
    for r in sorted(live, key=lambda r: (r["arm"], r["model"], r.get("condition"), r["scenario_id"], r.get("repeat"))):
        a = base.get(key(r))
        row = {
            "Arm": r["arm"], "Model": analyse.variant(r), "Prompt": r.get("condition"),
            "Scenario": r["scenario_id"], "Repeat": r.get("repeat"),
            "Live steps": r["steps"], "Live tokens": r["tokens"],
            "Live halt": r.get("halt_mechanism") or (
                "stopped itself after a warning" if any(d.get("decision") == "warn" for d in r.get("decisions", []))
                else ("gave up" if not r.get("task_completed") else "finished")),
        }
        if a is None:
            row.update({"Computed steps": None, "Computed tokens": None, "Computed halt": "no arm A run"})
        else:
            tokens, steps, mech = analyse.replay(a, r["arm"])
            row.update({"Computed steps": steps, "Computed tokens": tokens,
                        "Computed halt": mech or ("gave up" if not a.get("task_completed") else "finished"),
                        "A steps": a["steps"], "A tokens": a["tokens"]})
        row["Agree"] = (row["Live halt"] == row["Computed halt"]) if a is not None else None
        row["Same step"] = (row["Computed steps"] == row["Live steps"]) if a is not None else None
        out.append(row)
    df = pd.DataFrame(out)
    checked = df[df.Agree.notna()]
    lines = [f"# Live controller runs against the replay",
             f"",
             f"{len(df)} live runs; {int(checked.Agree.sum())} of {len(checked)} agree on the halt "
             f"(same mechanism, or both let the run end); {int(checked['Same step'].sum())} of {len(checked)} end at the "
             f"same step. A live run that stopped itself after the controller's warning ends where the replay has the "
             f"controller stop it: the warn rung changes who stops the run, not when.", "",
             df.to_markdown(index=False), ""]
    for (arm, model, cond), g in checked.groupby(["Arm", "Model", "Prompt"]):
        lines.append(f"- {arm}, {model}, {cond}: {int(g.Agree.sum())} of {len(g)} agree, {int(g['Same step'].sum())} same step; "
                     f"live {g['Live tokens'].mean():.0f} tokens on average, computed {g['Computed tokens'].mean():.0f}, "
                     f"arm A {g['A tokens'].mean():.0f}.")
    text = "\n".join(lines)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "live_vs_computed.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
