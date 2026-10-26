# Agent Fuel

Execution-level spend control for LLM agents, and the harness that evaluates it.

CSIT305 research project, University of Wollongong in Dubai.

## The question

How do execution-level spend controls compare with account-level limits and
iteration caps under external tool failure, measured in tokens prevented
against legitimate tasks interrupted, and which failure modes does none of
them cover?

## What is here

```
agent-fuel/
├── sandbox/
│   └── fake_tools.py          tools that fail on command; no real service is called
├── agent/
│   └── runner.py              the agent loop; wire call_model() to a provider
├── control/
│   ├── agent_fuel.py          the controller: six components, one policy
│   └── policies.yaml          thresholds, editable without touching code
├── evaluation/
│   ├── scenarios.json         15 failure scenarios in three groups
│   └── run_experiment.py      the sweep: 15 x 7 x 3 = 315 runs
├── results/                   runs.csv and decisions.csv land here
└── docs/
    └── iteration_log.md       what broke, what changed, what was retested
```

## Before the first real run

Set `HARD_CEILING_TOKENS` in `evaluation/run_experiment.py`. Configuration A
is designed to burn tokens; without a sweep-wide ceiling this reproduces the
incident the project is about, at your own expense.

## Order of work

1. `sandbox/fake_tools.py` already covers all 15 failure modes. Nothing to do.
2. Wire `call_model()` and `parse_action()` in `agent/runner.py` to a provider.
   Use a cheap model: the experiment studies loop behaviour, not reasoning.
3. Run configuration A on scenario 1 alone. Watch the token count climb and
   confirm the harness ceiling stops it.
4. Run arm E on the same scenario, rerun, compare. Two token counts side by
   side are the first evidence that the controller changes anything.
5. Run the full sweep.
6. Read `results/decisions.csv` for the mechanism attribution table.

## The seven arms

A, B and C are the approaches being compared against. D through G take the
controller apart one mechanism at a time, so the difference between two
adjacent arms is that mechanism's contribution.

| Arm | What is on |
| --- | --- |
| A | Nothing. The baseline, bounded only by the harness ceiling |
| B | Account-level allowance, shared across the whole sweep |
| C | Iteration cap, swept at 10, 15, 20, 30 and 40 steps |
| D | Run budget |
| E | D plus the loop detector |
| F | E plus the circuit breaker |
| G | F plus the error classifier and the warn rung |

## The three groups of scenarios

**A, eight scenarios: the tool is broken.** Unavailable, empty response, auth
error, timeout, broken pagination, flapping, degradation, malformed body.

**B, three scenarios: nothing is broken and spend still runs away.** Unreachable
goal, conflicting data, context accumulation. None of these is caught by the
loop detector or the breaker; only the run budget stops them, and saying so is
half the answer to the research question.

**C, four scenarios: the control group.** A long legitimate task, forty
legitimate repetitions, a slow but working service, and an ordinary healthy
run. Without this group the project proves only that a hard limit stops
spending, which is obvious.

## The two numbers

From `results/runs.csv`:

- **Overspend prevented**: tokens under each configuration against configuration A.
- **Legitimate tasks interrupted**: `false_interruption` across group C.

Plot one point per configuration with these as the axes. Up and to the left is
better. That chart is the answer.

## Reproducing a single scenario

```bash
python -m evaluation.run_experiment --list                  # scenarios and arms
python -m evaluation.run_experiment --dry-run               # count, then stop
python -m evaluation.run_experiment --only 2 --arms A G     # one scenario, two arms
python -m evaluation.run_experiment                         # the full 315 runs
python -m evaluation.analyse                                # tables and figures
```

Every run prints the run count on its first line. Check it before letting a
sweep proceed.

## Notes for the paper

`control/agent_fuel.py` carries a docstring per component explaining which
scenario it exists for and, where relevant, which naive implementation fails on
it. The error classifier is the one component that makes a judgement rather
than counting a fact; its rule is small and explicit so a reader can disagree
with it.
