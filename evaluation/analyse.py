"""Turn results/runs.csv and results/decisions.csv into the paper's tables and figures.

Run after a sweep:

    python -m evaluation.analyse

Writes into results/:
    summary.md          every table, ready to paste
    fig1-tradeoff.png   the answer to the research question
    fig2-sweep.png      the fair-comparison curves, when a sweep was run

Nothing here fits, fills or smooths anything. Every number is a count or a mean
of counts, so a reader can recompute all of it from the CSVs by hand.
"""

import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

BASELINE = "A"  # the arm with no control of any kind


# --- loading ---------------------------------------------------------------

def load():
    runs_path = RESULTS / "runs.csv"
    if not runs_path.exists():
        sys.exit(
            "No results/runs.csv. Run the sweep first:\n"
            "    AGENT_FUEL_BACKEND=ollama python -m evaluation.run_experiment"
        )

    runs = pd.read_csv(runs_path)
    for col in ("halted", "task_completed", "false_interruption", "mechanism_matched"):
        if col in runs:
            runs[col] = runs[col].astype(str).str.lower().isin(("true", "1", "yes"))

    decisions_path = RESULTS / "decisions.csv"
    decisions = pd.read_csv(decisions_path) if decisions_path.exists() else None
    return runs, decisions


# --- the two numbers -------------------------------------------------------

def per_arm(runs):
    """One row per arm: the two numbers the research question asks for.

    Overspend prevented is computed as a difference against the baseline arm
    rather than from an explicit fault-onset column, and the two are the same
    quantity. Overspend is defined as the tokens spent after the injected
    fault. Every arm runs the same task with the same fault injected at the
    same step at temperature zero, so the tokens spent BEFORE the fault are
    the same in both runs and cancel in the subtraction:

        (tokens_A - pre_fault) - (tokens_X - pre_fault) = tokens_A - tokens_X

    For control-group scenarios there is no fault, so the same subtraction
    measures what the controller itself costs. A negative figure there is the
    controller's overhead, not a saving, and is reported separately below.
    """
    faulted = runs[runs.group == "A"]
    control = runs[runs.group == "C"]

    base = (faulted[faulted.config == BASELINE]
            .groupby(["scenario_id", "repeat"]).tokens.mean())

    rows = []
    for arm, grp in runs.groupby("config"):
        f = grp[grp.group == "A"].set_index(["scenario_id", "repeat"])
        prevented = (base - f.tokens).dropna()

        c = grp[grp.group == "C"]
        # Overhead is only meaningful where the control group run finished. A
        # halted one spent fewer tokens because it was cut short, which is an
        # interruption and is counted in the column beside this one, not a saving.
        c_done = c[~c.halted]
        c_base = (control[control.config == BASELINE]
                  .groupby(["scenario_id", "repeat"]).tokens.mean())
        overhead = (c_done.set_index(["scenario_id", "repeat"]).tokens - c_base).dropna()

        rows.append({
            "Arm": arm,
            "Tokens, mean per run": round(grp.tokens.mean()),
            "Overspend prevented, mean": round(prevented.mean()) if len(prevented) else 0,
            "Legitimate tasks interrupted": f"{c.false_interruption.sum()} of {len(c)}",
            "False interruption rate": round(100 * c.false_interruption.mean(), 1) if len(c) else 0.0,
            "Overhead on completed control runs": round(overhead.mean()) if len(overhead) else "n/a",
            "Tasks completed": f"{grp.task_completed.sum()} of {len(grp)}",
        })

    return pd.DataFrame(rows).sort_values("Arm")


# --- verification ----------------------------------------------------------

def attribution(runs):
    """Did the mechanism that fired match the one the scenario predicted?

    A run can stop at the right token count for the wrong reason. This is the
    only check that catches it, so a low figure here matters even when the
    headline numbers look good.
    """
    halted = runs[runs.halted & (runs.expected_mechanism.notna())]
    if halted.empty:
        return pd.DataFrame()
    out = (halted.groupby(["scenario_id", "scenario_slug"])
           .agg(halts=("mechanism_matched", "size"),
                matched=("mechanism_matched", "sum"))
           .reset_index())
    out["Matched"] = (100 * out.matched / out.halts).round(1)
    return out.rename(columns={"scenario_id": "#", "scenario_slug": "Scenario",
                               "halts": "Halts", "matched": "Of which expected"})


def uncovered(runs):
    """Scenarios no arm ever halted. The research question names these in advance."""
    halted_by = runs[runs.halted].groupby("scenario_id").config.nunique()
    all_ids = runs[["scenario_id", "scenario_slug", "group"]].drop_duplicates()
    never = all_ids[~all_ids.scenario_id.isin(halted_by.index)]
    return never[never.group == "A"].rename(
        columns={"scenario_id": "#", "scenario_slug": "Scenario", "group": "Group"})


def false_completions(runs):
    """Runs that ended of the agent's own accord on a task that cannot be done.

    The runner records task_completed when the agent stops without being
    halted. Six scenarios cannot be completed at all, so a stop there means
    the agent gave up, not that it succeeded. Counting those as completions
    would overstate every arm equally and flatter the uncontrolled one most,
    because it has the most steps in which to give up.
    """
    bad = runs[runs.task_completed & ~runs.task_completable.astype(bool)]
    if bad.empty:
        return pd.DataFrame()
    out = (bad.groupby(["scenario_id", "scenario_slug", "config"])
           .size().reset_index(name="Runs"))
    return out.rename(columns={"scenario_id": "#", "scenario_slug": "Scenario",
                               "config": "Arm"})


def spread(runs, threshold=0.20):
    """Repeats that disagree too much for their mean to mean anything.

    Temperature is zero, so three repeats of one scenario under one arm should
    land close together. Anything above the threshold is a reproducibility
    problem to fix before the averages are reported, not a result.
    """
    g = runs.groupby(["scenario_id", "scenario_slug", "config"]).tokens
    out = g.agg(["mean", "min", "max"]).reset_index()
    out["Spread"] = ((out["max"] - out["min"]) / out["mean"].replace(0, pd.NA)).round(3)
    bad = out[out.Spread > threshold]
    return bad.rename(columns={"scenario_id": "#", "scenario_slug": "Scenario",
                               "config": "Arm", "mean": "Mean tokens"})


# --- figures ---------------------------------------------------------------

def fig_tradeoff(summary, path):
    """The answer to the research question: both numbers on one plane.

    Up and to the left is better. Neither axis means anything alone: the
    uncontrolled arm scores perfectly on interruptions because it cannot
    interrupt anything, and the tightest cap scores well on tokens because it
    halts everything.
    """
    fig, ax = plt.subplots(figsize=(7, 5.5))
    x = summary["False interruption rate"]
    y = summary["Overspend prevented, mean"]

    ax.scatter(x, y, s=90, zorder=3)
    for _, r in summary.iterrows():
        ax.annotate(r["Arm"], (r["False interruption rate"], r["Overspend prevented, mean"]),
                    textcoords="offset points", xytext=(8, 6), fontsize=11, weight="bold")

    ax.set_xlabel("Legitimate tasks interrupted, percent of control group")
    ax.set_ylabel("Overspend prevented, mean tokens per run")
    ax.set_title("Better is up and to the left")
    ax.grid(alpha=0.3, zorder=0)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_sweep(runs, path):
    """One curve per mechanism across its parameter, not one point.

    A single setting invites the objection that the competing mechanism was
    given an unfavourable one. Returns False when the sweep was not run, in
    which case the comparison rests on single points and the paper should say so.
    """
    if "param" not in runs.columns or runs.param.nunique(dropna=True) < 2:
        return False

    fig, ax = plt.subplots(figsize=(7, 5.5))
    base = runs[(runs.config == BASELINE) & (runs.group == "A")].tokens.mean()
    drawn = 0

    for arm, grp in runs[runs.param.notna()].groupby("config"):
        pts = []
        for value, sub in grp.groupby("param"):
            faulted = sub[sub.group == "A"]
            control = sub[sub.group == "C"]
            if faulted.empty or control.empty:
                continue
            pts.append((100 * control.false_interruption.mean(),
                        base - faulted.tokens.mean(), value))
        if len(pts) < 2:
            continue
        pts.sort()
        drawn += 1
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label=f"Arm {arm}")
        for px, py, value in pts:
            ax.annotate(str(value), (px, py), textcoords="offset points",
                        xytext=(6, -12), fontsize=9, alpha=0.7)

    if not drawn:
        plt.close(fig)  # a parameter column exists but no arm has two settings
        return False

    ax.set_xlabel("Legitimate tasks interrupted, percent of control group")
    ax.set_ylabel("Overspend prevented, mean tokens per run")
    ax.set_title("Curves, not points: each mechanism across its parameter")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


# --- report ----------------------------------------------------------------

def md_table(df, empty="None."):
    return df.to_markdown(index=False) if len(df) else empty


def main():
    runs, _ = load()
    summary = per_arm(runs)

    fig_tradeoff(summary, RESULTS / "fig1-tradeoff.png")
    swept = fig_sweep(runs, RESULTS / "fig2-sweep.png")

    att = attribution(runs)
    unc = uncovered(runs)
    bad = spread(runs)

    report = [
        "# Results",
        "",
        f"{len(runs)} runs, {runs.scenario_id.nunique()} scenarios, "
        f"{runs.config.nunique()} arms, {runs.repeat.nunique()} repeats.",
        "",
        "## The two numbers",
        "",
        md_table(summary),
        "",
        "Overspend prevented is measured against arm " + BASELINE +
        ". The controller overhead column is the same subtraction over the "
        "control group, where no fault is injected: a positive figure there is "
        "what the controller costs when nothing is wrong.",
        "",
        "![Trade-off](fig1-tradeoff.png)",
        "",
    ]

    if swept:
        report += ["![Parameter sweep](fig2-sweep.png)", ""]
    else:
        report += [
            "> No parameter sweep in this data: every arm ran at a single "
            "setting. The comparison therefore rests on single points, which "
            "the paper must state, because a reader can reasonably ask whether "
            "a competing mechanism was given an unfavourable setting.",
            "",
        ]

    report += [
        "## Verification",
        "",
        "### Mechanism attribution",
        "",
        "A run can halt at the right token count for the wrong reason.",
        "",
        md_table(att, "No halts recorded."),
        "",
        "### Scenarios no arm covered",
        "",
        "Named in the research question in advance as an expected outcome.",
        "",
        md_table(unc, "Every scenario was halted by at least one arm. "
                      "This contradicts the stated expectation and is itself a finding."),
        "",
        "### Agents that gave up on an impossible task",
        "",
        "Recorded as completions by the runner. They are not completions, and "
        "the completion column should be read with this table beside it.",
        "",
        md_table(false_completions(runs),
                 "No run ended of its own accord on a task that cannot be done."),
        "",
        "### Repeats that disagree",
        "",
        "Temperature is zero, so repeats should land close together.",
        "",
        md_table(bad, "All repeats agree within 20 percent."),
        "",
    ]

    out = RESULTS / "summary.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Wrote {RESULTS / 'fig1-tradeoff.png'}")
    if swept:
        print(f"Wrote {RESULTS / 'fig2-sweep.png'}")
    else:
        print("No parameter sweep found: fig2 skipped.")


if __name__ == "__main__":
    main()
