"""The matrix of run configurations behind the paper's tables.

    python -m evaluation.config_matrix            # reads console/data/runs.jsonl
    python -m evaluation.config_matrix FILE.jsonl

Writes results/config_matrix.csv, one row per (model setting, prompt
condition, scenario, control configuration): how many records, which repeats,
the temperature, and the dates of the first and last run. The paper cites this
file as the record of what was run under which settings.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_FILE = ROOT / "console" / "data" / "runs.jsonl"
OUT = ROOT / "results" / "config_matrix.csv"

ARMS = {"A": "no control (live)", "C": "step cap (live, pilot)", "D": "run budget (live, pilot)",
        "G": "Agent Fuel (live check)"}
FIELDS = ["model", "thinking", "effort", "temperature", "condition", "scenario", "control",
          "records", "repeats", "pilot", "first_run", "last_run"]


def split_model(label):
    """'claude-haiku-5-5+thinking+low' -> (model, thinking, effort); Qwen has neither."""
    parts = label.split("+")
    if len(parts) == 3:
        return parts[0], "on" if parts[1] == "thinking" else "off", parts[2]
    return label, "", ""


def main(path=RUNS_FILE):
    # A rerun of a cell replaces the earlier record, as the console and
    # evaluation/analyse.py do: the last record with an id wins.
    latest = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                latest[r["id"]] = r
    cells = defaultdict(list)
    for r in latest.values():
        if True:
            model, thinking, effort = split_model(r["model"])
            key = (model, thinking, effort, str(r.get("temperature", "default")), r["condition"],
                   r["scenario_id"], r["arm"])
            cells[key].append(r)
    rows = []
    for key in sorted(cells, key=lambda k: (k[0], k[1], k[2], k[3], k[4], k[5], k[6])):
        rs = cells[key]
        rows.append({
            "model": key[0], "thinking": key[1], "effort": key[2], "temperature": key[3],
            "condition": key[4], "scenario": key[5], "control": ARMS.get(key[6], key[6]),
            "records": len(rs),
            "repeats": " ".join(str(r["repeat"]) for r in sorted(rs, key=lambda r: r["repeat"])),
            "pilot": sum(1 for r in rs if r.get("pilot")),
            "first_run": min(r["ts"] for r in rs)[:10], "last_run": max(r["ts"] for r in rs)[:10],
        })
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    total = sum(r["records"] for r in rows)
    live = sum(r["records"] for r in rows if r["control"].startswith("no control"))
    print(f"{len(rows)} cells, {total} records ({live} without control) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RUNS_FILE)
