"""Run a named batch of runs outside the console, into its own folder.

    python console/batch.py --list
    python console/batch.py live-g                 # run a batch
    python console/batch.py live-g --dry-run       # print the worker commands only
    python console/merge_runs.py console/data/batches/live-g   # fold the results in

Each batch is a list of worker.py invocations. The records go to
console/data/batches/<name>/runs.jsonl (not to the console's runs.jsonl),
so a batch can be inspected before it is merged; the worker's output is
also written to launch.log in the same folder. Haiku batches read the API
key from ~/.config/agent-fuel/anthropic_key, as the console does, unless
ANTHROPIC_API_KEY is already set.

Running a batch again writes the same run ids; merge_runs.py then replaces
the earlier records and keeps them in superseded.jsonl.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DATA = ROOT / "data" / "batches"
KEYFILE = Path.home() / ".config" / "agent-fuel" / "anthropic_key"
PROMPTS = REPO / "docs" / "real-prompts"
ALL = "1,2,3,4,5,6,8,13,15"
REFUSAL = "1,2,3,4,5,8"


def W(config, condition="base", scenarios=ALL, arms="A", repeats=None, repeat_ids=None,
      real_prompt=None, error_hint=False, temperature=None, max_cost=1.0):
    """One worker.py invocation, as a list of arguments."""
    a = ["--config", config, "--scenarios", scenarios, "--arms", arms, "--max-cost", str(max_cost)]
    if real_prompt:
        a += ["--real-prompt", str(PROMPTS / f"{real_prompt}.txt")]
    else:
        a += ["--condition", condition]
    if error_hint:
        a += ["--error-hint"]
    if repeat_ids:
        a += ["--repeat-ids", repeat_ids]
    else:
        a += ["--repeats", str(repeats or 1)]
    if temperature is None:
        temperature = 1.0 if config == "qwen" else 0.0  # Qwen's main series is t=1; Haiku ignores it
    a += ["--temperature", str(temperature)]
    return a


BATCHES = {
    # 1. The controller live: Agent Fuel (arm G) on one Haiku variant, the
    #    strict prompt, nine scenarios, three repeats. Strict is the one level
    #    where the computed controller fires on Haiku, so these 27 runs check
    #    the replay where it has something to say. Thinking+low is the variant
    #    the real prompts and base+hint were run on.
    "live-g": {
        "about": "Haiku thinking+low, strict, arm G, 9 scenarios x 3 repeats (27 paid runs, about $0.05)",
        "jobs": [W("haiku-think-low", "strict", ALL, arms="G", repeats=3)],
    },
    # 4. Single timeouts on Haiku, filled cell by cell.
    "haiku-gaps": {
        "about": "Haiku thinking+low: P01 s13, s15; P09 s13; base+hint s15 r2, r3 (5 paid runs)",
        "jobs": [
            W("haiku-think-low", scenarios="13,15", real_prompt="P01_smolagents"),
            W("haiku-think-low", scenarios="13", real_prompt="P09_goose"),
            W("haiku-think-low", "base", scenarios="15", error_hint=True, repeat_ids="2,3"),
        ],
    },
    # 2. Repeats on the real prompts, LangChain on Qwen first.
    "qwen-langchain-r23": {
        "about": "Qwen t=1 under LangChain MRKL, 9 scenarios, repeats 2 and 3 (18 local runs)",
        "jobs": [W("qwen", scenarios=ALL, real_prompt="P04_langchain_react", repeat_ids="2,3")],
    },
    # 4. Single timeouts on Qwen.
    "qwen-gaps": {
        "about": "Qwen t=1: P02 s6, s13; P05 s13; P08 s4; base+hint s6 r2, r3 and s13 r1; LangChain s13 r3 (8 local runs)",
        "jobs": [
            W("qwen", scenarios="6,13", real_prompt="P02_crewai"),
            W("qwen", scenarios="13", real_prompt="P05_cline"),
            W("qwen", scenarios="4", real_prompt="P08_codex_cli"),
            W("qwen", "base", scenarios="6", error_hint=True, repeat_ids="2,3"),
            W("qwen", "base", scenarios="13", error_hint=True, repeat_ids="1"),
            W("qwen", scenarios="13", real_prompt="P04_langchain_react", repeat_ids="3"),
        ],
    },
    # 1b. The controller live on Qwen, where the real runaways are.
    "live-g-qwen": {
        "about": "Qwen t=1, strict, arm G, 9 scenarios x 3 repeats (27 local runs)",
        "jobs": [W("qwen", "strict", ALL, arms="G", repeats=3)],
    },
    # 2. The other real prompts on Qwen, repeats 2 and 3, once LangChain is in.
    "qwen-real-r23": {
        "about": "Qwen t=1 under the other eight real prompts, repeats 2 and 3 (144 local runs)",
        "jobs": [W("qwen", scenarios=ALL, real_prompt=p, repeat_ids="2,3")
                 for p in ("P01_smolagents", "P02_crewai", "P03_llamaindex_react", "P05_cline",
                           "P06_openhands", "P07_swe_agent", "P08_codex_cli", "P09_goose")],
    },
    "haiku-real-r23": {
        "about": "Haiku thinking+low under the nine real prompts, repeats 2 and 3 (162 paid runs, about $0.5)",
        "jobs": [W("haiku-think-low", scenarios=ALL, real_prompt=p, repeat_ids="2,3", max_cost=2.0)
                 for p in ("P01_smolagents", "P02_crewai", "P03_llamaindex_react", "P04_langchain_react",
                           "P05_cline", "P06_openhands", "P07_swe_agent", "P08_codex_cli", "P09_goose")],
    },
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", choices=sorted(BATCHES))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.list or not args.name:
        for n, b in BATCHES.items():
            print(f"{n:22s} {b['about']}")
        return
    batch = BATCHES[args.name]
    out = DATA / args.name
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    needs_key = any("haiku" in j[j.index("--config") + 1] for j in batch["jobs"])
    if needs_key and not env.get("ANTHROPIC_API_KEY"):
        try:
            env["ANTHROPIC_API_KEY"] = KEYFILE.read_text().strip()
        except OSError:
            sys.exit(f"No API key: set ANTHROPIC_API_KEY or put the key in {KEYFILE}")
    print(f"{args.name}: {batch['about']}\n  -> {out}")
    log = (out / "launch.log").open("a", encoding="utf-8")
    for job in batch["jobs"]:
        cmd = [sys.executable, "-u", str(ROOT / "worker.py"), "--repo", str(REPO), "--data", str(out)] + job
        print("  " + " ".join(cmd[4:]))
        if args.dry_run:
            continue
        log.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} {' '.join(cmd[4:])}\n")
        log.flush()
        proc = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
            log.flush()
        proc.wait()
        log.flush()
        if proc.returncode not in (0, None):
            print(f"  worker exited with {proc.returncode}; see {out / 'launch.log'}")
    if not args.dry_run:
        print(f"\nDone. Fold the results in with:\n  python console/merge_runs.py {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
