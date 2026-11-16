"""Turn the console's run records into the tables of the revised study design.

Run after a sweep:

    python -m evaluation.analyse            # reads console/data/runs.jsonl
    python -m evaluation.analyse FILE.jsonl # or any other run file

Writes into results/:
    summary.md     every table, ready to paste
    replay.csv     one row per run and control, the numbers behind the tables
    fig1-tradeoff.png

Design (settled 9 November 2026). The sweep runs arm A only: the agent with
no control, cut by the harness at 60 steps. Every control is then COMPUTED
over the recorded run, because the stub service is deterministic: the same
calls get the same answers, so the controller can be replayed over the
journal and will halt at the same step it would have halted live.

    without control   tokens the run spent (arm A)
    minimum           tokens spent by the end of step 3 without control
    excess            without control - minimum (what the run burnt for nothing)
    with control X    tokens up to the step where X halts the run; the whole
                      run when X never fires
    saving of X       without control - with control X ("at least": arm A is
                      cut at 60 steps, so the run could have burnt more)
    share of excess   sum of savings / sum of excess, over the refusal runs
    spoiled tasks     control runs (scenarios 6 and 13) that X halts; the
                      headline comparison is among controls that spoil none
    coverage          per refusal scenario: covered (X halted), not covered
                      (the run went past the minimum and X let it run), not
                      checked (the agent stopped by itself within the minimum)

Three controls are computed as caps over the token curve and need no replay:
the iteration cap (arm C) at each value from scenarios.json, and the account
limit (arm B) as a multiple of a normal day's spend, where a day is DAY_TASKS
healthy tasks (scenario 15) of the same model and condition. Arms D to G are
replayed with the real controller from control/agent_fuel.py.

One thing replay cannot reproduce: the warn rung. Live, a warning is put in
front of the agent and it may change course; replayed, the agent's recorded
replies stand. The halt itself is unaffected, because the controller only
warns one step before it stops.

Nothing here fits, fills or smooths anything. Every number is a count, a sum
or a ratio of sums, so a reader can recompute all of it from replay.csv.
"""

import csv
import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from control.agent_fuel import AgentFuel, build_controller  # noqa: E402
from sandbox.fake_tools import build_tools  # noqa: E402
from agent.runner import parse_action  # noqa: E402

RESULTS = ROOT / "results"
RUNS_FILE = ROOT / "console" / "data" / "runs.jsonl"
SCENARIOS = json.loads((ROOT / "evaluation" / "scenarios.json").read_text())
BY_ID = {s["id"]: s for s in SCENARIOS["scenarios"]}

MINIMUM_STEPS = 3            # the minimum is the spend by the end of this step
STEP_CAPS = (10, 15, 20, 30, 40)   # arm C, the values scenarios.json names
HEADLINE_STEP_CAP = 15
DAY_TASKS = 10               # a normal day: this many healthy tasks (scenario 15)
ACCOUNT_LIMIT_DAYS = (1, 2, 5, 10)  # arm B, the limit as a multiple of a day
HEADLINE_LIMIT_DAYS = 2
LADDER = ("D", "E", "F", "G")
# The three mechanisms without the run budget: what the controller does on
# evidence alone, with no ceiling that a long honest task can hit.
MECHANISMS_ONLY = {"loop_detector", "circuit_breaker", "error_classifier"}
CONDITIONS = ("lenient", "base", "strict")
REFUSAL = [s["id"] for s in SCENARIOS["scenarios"] if s["group"] == "A"]
CONTROL = [s["id"] for s in SCENARIOS["scenarios"] if s["group"] == "C"]
REFERENCE = [s["id"] for s in SCENARIOS["scenarios"] if s["group"] == "R"]

# The $2 cost ceiling is out of the design; the token ceiling stays.
REPLAY_OVERRIDES = dict(max_cost_usd=1e9)


# --- loading ---------------------------------------------------------------

def load(path):
    runs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "error" in r or r.get("arm") != "A" or r.get("scenario_id") not in BY_ID:
            continue
        runs.append(r)
    # A rerun of a cell replaces the earlier record, as the console does.
    latest = {}
    for r in runs:
        latest[r["id"]] = r
    return list(latest.values())


def variant(r):
    """The model as the paper compares it: Haiku by thinking and effort,
    Qwen by temperature."""
    m = r["model"]
    t = r.get("temperature")
    if m.startswith("qwen") and t not in (None, "default"):
        return f"{m} t={float(t):g}"
    return m


# --- replay ----------------------------------------------------------------

def replay(r, arm):
    """Walk one recorded run through a controller built for `arm`.

    Mirrors agent/runner.py step for step: before_step, the recorded model
    call, parse_action on the recorded reply, before_tool, the stub tool,
    after_tool. Returns (tokens, steps, mechanism) at the halt, or at the
    end of the run when the controller never stopped it.
    """
    scenario = BY_ID[r["scenario_id"]]
    tools = build_tools(scenario)
    if arm == "M":
        ctl = AgentFuel(enabled=set(MECHANISMS_ONLY), **REPLAY_OVERRIDES)
    else:
        ctl = build_controller(arm, REPLAY_OVERRIDES)
    curve = r["curve"]
    spent = 0

    for i, step in enumerate(r["trace"]):
        if ctl.before_step().stops:
            return spent, i, ctl.halted.mechanism
        ctl.record_model_call(step["in"], step["out"], 0.0)
        spent = curve[i]

        action = parse_action(step["reply"])
        if action is None:
            break
        tool_name, args = action
        if ctl.before_tool(tool_name, args).stops:
            return spent, i + 1, ctl.halted.mechanism
        tool = tools.get(tool_name)
        if tool is None:
            continue
        try:
            result = tool.get_metrics(**args)
        except Exception as exc:  # the stub raises on purpose; so does a bad argument
            after = ctl.after_tool(tool_name, args, error=exc)
        else:
            after = ctl.after_tool(tool_name, args, result=result)
        if after.stops:
            return spent, i + 1, ctl.halted.mechanism

    return r["tokens"], r["steps"], None


def cap_by_steps(r, cap):
    """Arm C: the run is cut after `cap` steps."""
    if r["steps"] > cap:
        return r["curve"][cap - 1], cap, "step_cap"
    return r["tokens"], r["steps"], None


def cap_by_tokens(r, limit):
    """Arm B: the run is cut at the step where its spend reaches `limit`."""
    for i, spent in enumerate(r["curve"]):
        if spent >= limit:
            return spent, i + 1, "account_budget"
    return r["tokens"], r["steps"], None


def minimum_of(r):
    return r["curve"][min(MINIMUM_STEPS, r["steps"]) - 1] if r["curve"] else 0


def day_spend(runs):
    """Mean tokens of a healthy task per (variant, condition), times DAY_TASKS."""
    ref = pd.DataFrame([{"variant": variant(r), "condition": r["condition"], "tokens": r["tokens"]}
                        for r in runs if r["scenario_id"] in REFERENCE])
    if ref.empty:
        return {}
    return (ref.groupby(["variant", "condition"]).tokens.mean() * DAY_TASKS).to_dict()


def controls():
    out = [("Agent Fuel (G)", "G"), ("Mechanisms only, no run budget", "M")]
    out += [(f"Step cap {c}", f"C{c}") for c in STEP_CAPS]
    out += [(f"Account limit {d} day{'s' if d > 1 else ''}", f"B{d}") for d in ACCOUNT_LIMIT_DAYS]
    out += [(f"Ladder {a}", a) for a in LADDER if a != "G"]
    return out


def defect_of(r):
    """Why the stand, not the agent, ended this run; None if the agent ended it.

    A run ends when parse_action reads no tool call in the reply. When that
    reply does contain a tool call that the parser could not read (several
    calls in one reply, or prose before the JSON), the stand ended the run,
    not the agent, and the run is counted as not checked.
    """
    if not r["trace"] or r.get("halted"):
        return None
    reply = r["trace"][-1]["reply"]
    if parse_action(reply) is not None or '"tool"' not in reply:
        return None
    if reply.count('"tool"') > 1:
        return f"several calls in one reply at step {r['steps']}, read as finished"
    return f"reply at step {r['steps']} is not plain JSON, read as finished"


def compute(runs):
    """One row per run and control."""
    days = day_spend(runs)
    rows = []
    for r in runs:
        v, cond = variant(r), r["condition"]
        base = r["tokens"]
        minimum = minimum_of(r)
        excess = max(0, base - minimum)
        group = BY_ID[r["scenario_id"]]["group"]
        defect = defect_of(r)
        gave_up = group == "A" and r.get("task_completed") and r["steps"] <= MINIMUM_STEPS \
            and not defect
        for name, code in controls():
            if code.startswith("C"):
                tokens, steps, mech = cap_by_steps(r, int(code[1:]))
            elif code.startswith("B"):
                limit = days.get((v, cond))
                if limit is None:
                    continue
                tokens, steps, mech = cap_by_tokens(r, int(code[1:]) * limit)
            else:
                tokens, steps, mech = replay(r, code)
            halted = mech is not None
            if defect:
                status = "not checked"
            elif group == "A":
                status = "covered" if halted else ("not checked" if excess == 0 else "not covered")
            else:
                status = "spoiled" if halted else "intact"
            rows.append({
                "run_id": r["id"], "variant": v, "condition": cond, "model": r["model"],
                "family": "Qwen 2.5 7B" if r["model"].startswith("qwen") else "Haiku 5.5",
                "scenario_id": r["scenario_id"], "group": group, "repeat": r["repeat"],
                "control": name, "code": code,
                "steps_without": r["steps"], "tokens_without": base,
                "hit_ceiling": r["steps"] >= 60, "gave_up": bool(gave_up),
                "defect": defect or "",
                "minimum": minimum, "excess": excess,
                "tokens_with": tokens, "steps_with": steps, "halted": halted,
                "mechanism": mech or "", "saving": base - tokens,
                # The part of the saving that lies above the minimum: a halt
                # before step 3 saves more than the excess, and only the
                # excess is what the question asks about.
                "saving_in_excess": max(0, base - max(tokens, minimum)),
                "status": status,
                "expected_mechanism": BY_ID[r["scenario_id"]]["expected_mechanism"] or "",
            })
    df = pd.DataFrame(rows)
    order = sorted(df.variant.unique(), key=lambda v: (not v.startswith("qwen"), v))
    df["variant"] = pd.Categorical(df.variant, order)
    # Our three levels first, then any real prompts (P01_..., P03_...) in name order.
    conds = list(CONDITIONS) + sorted(c for c in df.condition.unique() if c not in CONDITIONS)
    df["condition"] = pd.Categorical(df.condition, conds)
    return df.sort_values(["variant", "condition", "scenario_id", "repeat"]).reset_index(drop=True)


def share(ref):
    """Share of the excess saved, as text: 'n/a' when there was no excess."""
    return f"{pct(ref.saving_in_excess.sum(), ref.excess.sum()):g}" if ref.excess.sum() else "n/a"


def spoiled(x):
    """'k of n' control runs halted, with the mechanisms that did it. Runs
    the stand itself spoiled are left out of n and counted separately."""
    bad = x[x.defect != ""]
    x = x[x.defect == ""]
    mechs = sorted(set(m for m in x[x.halted].mechanism if m))
    text = f"{int(x.halted.sum())} of {len(x)}"
    if mechs:
        text += f" ({', '.join(m.replace('loop_detector_', 'loop/') for m in mechs)})"
    if len(bad):
        text += f", {len(bad)} not checked"
    return text


def pooled(df, codes):
    """The headline by model family and prompt level, variants pooled."""
    rows = []
    for (fam, c), g in df.groupby(["family", "condition"], sort=False, observed=True):
        for name, code in codes:
            x = g[g.code == code]
            if x.empty:
                continue
            ref = x[x.group == "A"]
            rows.append({
                "Model": fam, "Prompt": c, "Control": name,
                "Refusal runs": len(ref),
                "Without control, mean tokens": round(ref.tokens_without.mean()),
                "With control, mean tokens": round(ref.tokens_with.mean()),
                "Share of excess saved, %": share(ref),
                "Covered / not / not checked": f"{int((ref.status == 'covered').sum())} / "
                                               f"{int((ref.status == 'not covered').sum())} / "
                                               f"{int((ref.status == 'not checked').sum())}",
                **{f"Spoiled sc. {sid}": spoiled(x[x.scenario_id == sid]) for sid in CONTROL},
            })
    return pd.DataFrame(rows)


# --- tables ----------------------------------------------------------------

def pct(num, den):
    return round(100.0 * num / den, 1) if den else float("nan")


def inventory(df):
    one = df[df.code == "G"]
    rows = []
    for (v, c), g in one.groupby(["variant", "condition"], sort=False, observed=True):
        ref = g[g.group == "A"]
        rows.append({
            "Model": v, "Prompt": c, "Runs": len(g),
            "Refusal runs": len(ref),
            "Mean steps": round(ref.steps_without.mean(), 1),
            "Mean tokens": round(ref.tokens_without.mean()),
            "Gave up by step 3": f"{int(ref.gave_up.sum())} of {len(ref)}",
            "Hit 60 steps": int(ref.hit_ceiling.sum()),
            "Excess, sum": int(ref.excess.sum()),
        })
    return pd.DataFrame(rows)


def headline(df, codes):
    rows = []
    for (v, c), g in df.groupby(["variant", "condition"], sort=False, observed=True):
        for name, code in codes:
            x = g[g.code == code]
            if x.empty:
                continue
            ref = x[x.group == "A"]
            rows.append({
                "Model": v, "Prompt": c, "Control": name,
                "Saved, mean tokens": round(ref.saving.mean()),
                "Share of excess, %": share(ref),
                "Covered": int((ref.status == "covered").sum()),
                "Not covered": int((ref.status == "not covered").sum()),
                "Not checked": int((ref.status == "not checked").sum()),
                **{f"Spoiled sc. {sid}": spoiled(x[x.scenario_id == sid]) for sid in CONTROL},
            })
    return pd.DataFrame(rows)


def sweep(df, prefix, label):
    """One row per model and condition, one column per parameter value:
    share of excess saved and spoiled control runs."""
    rows = []
    for (v, c), g in df.groupby(["variant", "condition"], sort=False, observed=True):
        row = {"Model": v, "Prompt": c}
        for name, code in controls():
            if not code.startswith(prefix) or len(code) == 1:
                continue
            x = g[g.code == code]
            ref, ctl = x[x.group == "A"], x[x.group == "C"]
            row[f"{label} {code[1:]}"] = f"{share(ref)} / {int(ctl.halted.sum())}"
        rows.append(row)
    return pd.DataFrame(rows)


def per_scenario(df, code):
    x = df[(df.code == code) & (df.group == "A")]
    rows = []
    for sid, g in x.groupby("scenario_id"):
        matched = g[g.halted & g.mechanism.str.startswith(g.expected_mechanism.iloc[0] or "\0")]
        rows.append({
            "#": sid, "Scenario": BY_ID[sid]["slug"], "Runs": len(g),
            "Covered": int((g.status == "covered").sum()),
            "Not covered": int((g.status == "not covered").sum()),
            "Not checked": int((g.status == "not checked").sum()),
            "Halted by expected mechanism": f"{len(matched)} of {int(g.halted.sum())}",
            "Mechanisms": ", ".join(sorted(set(m for m in g.mechanism if m))) or "none",
            "Share of excess, %": share(g),
        })
    return pd.DataFrame(rows)


def defects(runs):
    """Runs the stand itself spoiled, to read beside every table."""
    rows = [{"Run": r["id"], "What": defect_of(r)} for r in runs if defect_of(r)]
    return pd.DataFrame(rows)


def fig_tradeoff(df, path):
    """Share of excess saved against spoiled control runs, one point per
    model, condition and control. Up and to the left is better."""
    pts = []
    for (v, c, name), g in df.groupby(["variant", "condition", "control"], observed=True):
        ref, ctl = g[g.group == "A"], g[g.group == "C"]
        if ref.excess.sum() == 0 or ctl.empty:
            continue
        pts.append((name, pct(ctl.halted.sum(), len(ctl)),
                    pct(ref.saving_in_excess.sum(), ref.excess.sum())))
    if not pts:
        return False
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    for name in sorted({p[0] for p in pts}):
        xs = [p[1] for p in pts if p[0] == name]
        ys = [p[2] for p in pts if p[0] == name]
        ax.scatter(xs, ys, s=40, alpha=0.75, label=name)
    ax.set_xlabel("Control tasks spoiled, percent")
    ax.set_ylabel("Excess spend saved, percent")
    ax.set_title("One point per model, prompt level and control. Better is up and left.")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


COMPUTED_FILE = ROOT / "console" / "data" / "computed.jsonl"
COMPUTED_ARMS = {f"B{HEADLINE_LIMIT_DAYS}": "B", f"C{HEADLINE_STEP_CAP}": "C",
                 "D": "D", "E": "E", "F": "F", "G": "G"}


def write_computed(runs, df):
    """Computed arms as run records for the console, one per arm A run and
    control, so the dashboard can show the controller beside the live arm
    A cells. Marked computed; the console lets a live run of the same cell
    take precedence."""
    by_id = {r["id"]: r for r in runs}
    with COMPUTED_FILE.open("w", encoding="utf-8") as f:
        for _, x in df[df.code.isin(COMPUTED_ARMS)].iterrows():
            r = by_id[x.run_id]
            arm = COMPUTED_ARMS[x.code]
            steps = int(x.steps_with)
            rec = {
                "id": f"{r['id']}~{arm}", "computed": True, "computed_from": r["id"],
                "model": r["model"], "condition": r["condition"], "temperature": r.get("temperature"),
                "scenario_id": r["scenario_id"], "arm": arm, "repeat": r["repeat"], "ts": r["ts"],
                "steps": steps, "tokens": int(x.tokens_with), "cost_usd": 0.0,
                "halted": bool(x.halted), "halt_mechanism": x.mechanism or None,
                "halt_reason": f"computed over the arm A run: {x.control}" if x.halted else None,
                "expected_mechanism": r.get("expected_mechanism"),
                "mechanism_matched": bool(x.halted and x.mechanism.startswith(x.expected_mechanism or "\0")),
                "task_completed": bool(r.get("task_completed")) and not bool(x.halted),
                "task_completable": bool(r.get("task_completable")),
                "trace": r.get("trace", [])[:steps], "curve": r.get("curve", [])[:steps], "decisions": [],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {COMPUTED_FILE}")


# --- report ----------------------------------------------------------------

def md(df, empty="None."):
    return df.to_markdown(index=False) if len(df) else empty


def main(argv=None):
    path = Path(argv[0]) if argv else RUNS_FILE
    if not path.exists():
        sys.exit(f"No run file at {path}. Run the sweep from the console first.")
    runs = load(path)
    if not runs:
        sys.exit("No arm A runs in the file.")
    RESULTS.mkdir(exist_ok=True)

    df = compute(runs)
    df.to_csv(RESULTS / "replay.csv", index=False)
    write_computed(runs, df)

    head = [("Agent Fuel (G)", "G"), ("Mechanisms only, no run budget", "M"),
            (f"Step cap {HEADLINE_STEP_CAP}", f"C{HEADLINE_STEP_CAP}"),
            (f"Account limit {HEADLINE_LIMIT_DAYS} days", f"B{HEADLINE_LIMIT_DAYS}")]
    ladder = [(f"Ladder {a}", a) for a in LADDER if a != "G"] + [("Agent Fuel (G)", "G")]
    drawn = fig_tradeoff(df, RESULTS / "fig1-tradeoff.png")
    n_var = df.variant.nunique()

    report = [
        "# Results",
        "",
        f"{len(runs)} runs without control (arm A), {df.scenario_id.nunique()} scenarios, "
        f"{n_var} model variants, {df.condition.nunique()} prompt levels. "
        f"Source: `{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}`.",
        "",
        "Every control below is computed over these runs: the iteration cap and the "
        "account limit as caps on the token curve, arms D to G by replaying the "
        "controller over the recorded calls against the same deterministic stub. "
        "See the docstring of `evaluation/analyse.py` for the definitions.",
        "",
        "## Without control",
        "",
        "*Gave up by step 3*: the agent ended the run on its own within the minimum, "
        "so there was nothing for a control to save. *Hit 60 steps*: cut by the "
        "harness, so the saving measured on that run is a lower bound.",
        "",
        md(inventory(df)),
        "",
        "## The headline: Agent Fuel against the two blunt controls",
        "",
        f"Step cap at {HEADLINE_STEP_CAP} steps; account limit at {HEADLINE_LIMIT_DAYS} normal days, "
        f"a day being {DAY_TASKS} healthy tasks of the same model and prompt level. "
        "*Mechanisms only* is the controller without its run budget: the loop detector, "
        "the circuit breaker and the error classifier on evidence alone. "
        "Share of excess is the sum of savings above the minimum over the sum of excess "
        "across the refusal runs. Coverage counts refusal runs. Spoiled counts control runs "
        "the control halted, with the mechanism that did it; the comparison that matters is "
        "among controls that spoil none.",
        "",
        "### By model family, variants pooled",
        "",
        md(pooled(df, head)),
        "",
        "### By model variant",
        "",
        md(headline(df, head)),
        "",
        "## The ladder: one mechanism at a time",
        "",
        "D run budget; E adds the loop detector; F adds the circuit breaker; G adds the "
        "error classifier. The difference between adjacent rows is that mechanism's share.",
        "",
        md(headline(df, ladder)),
        "",
        "## Agent Fuel by scenario",
        "",
        md(per_scenario(df, "G")),
        "",
        "## The blunt controls across their parameter",
        "",
        "Each cell: share of excess saved / control runs spoiled.",
        "",
        "### Iteration cap, steps",
        "",
        md(sweep(df, "C", "Cap")),
        "",
        f"### Account limit, in normal days ({DAY_TASKS} healthy tasks each)",
        "",
        md(sweep(df, "B", "Days")),
        "",
        "## Runs the stand spoiled",
        "",
        "Read beside every table above. These runs are counted as *not checked*.",
        "",
        md(defects(runs), "None found."),
        "",
    ]
    if drawn:
        report += ["![Trade-off](fig1-tradeoff.png)", ""]

    out = RESULTS / "summary.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Wrote {RESULTS / 'replay.csv'}")
    if drawn:
        print(f"Wrote {RESULTS / 'fig1-tradeoff.png'}")


if __name__ == "__main__":
    main(sys.argv[1:])
