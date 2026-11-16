"""Merge run files written elsewhere into console/data/runs.jsonl.

    python console/merge_runs.py DIR [DIR ...]

Every runs.jsonl found under the given directories is read; a record whose
id already exists in console/data/runs.jsonl replaces the earlier one (a
rerun of a cell supersedes it, as the console does), and the replaced
records are appended to console/data/superseded.jsonl so nothing is lost.
Records with an "error" field are skipped and counted.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "data" / "runs.jsonl"
SUPERSEDED = ROOT / "data" / "superseded.jsonl"


def read(path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def main(dirs):
    current = read(RUNS) if RUNS.exists() else []
    index = {r["id"]: i for i, r in enumerate(current)}
    added = replaced = errors = 0
    old = []
    for d in dirs:
        for f in sorted(Path(d).rglob("runs.jsonl")):
            for r in read(f):
                if "error" in r:
                    errors += 1
                    continue
                if r["id"] in index:
                    old.append(current[index[r["id"]]])
                    current[index[r["id"]]] = r
                    replaced += 1
                else:
                    index[r["id"]] = len(current)
                    current.append(r)
                    added += 1
    with RUNS.open("w", encoding="utf-8") as f:
        for r in current:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if old:
        with SUPERSEDED.open("a", encoding="utf-8") as f:
            for r in old:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"added {added}, replaced {replaced}, skipped {errors} with errors; "
          f"{len(current)} records in {RUNS}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
