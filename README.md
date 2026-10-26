# Agent Fuel

Execution-level spend control for LLM agents, and the harness that evaluates it.

CSIT305 research project, University of Wollongong in Dubai.

> **New to the project? Start with [GETTING_STARTED.md](GETTING_STARTED.md)**:
> setting up from zero (VS Code, the local model, your own API key) and how
> the team works together.

## The question

How do execution-level spend controls compare with account-level limits and
iteration caps under external tool failure, measured in tokens prevented
against legitimate tasks interrupted, and which failure modes does none of
them cover?

## How it works in one paragraph

An LLM agent is given a small analytics task and a tool to do it with. The tool
is a stub that breaks on command in fifteen different ways (service down, empty
answer, slow, flapping and so on). Each scenario is run under seven control
configurations, from no control at all to the full Agent Fuel controller, and
two numbers are recorded: how many tokens the agent burned after the failure,
and whether a healthy run was stopped by mistake. Everything runs on your own
computer; no real service is ever called.

## Status

The harness runs end to end. The first sweeps on Claude Haiku 5.5 and the
findings so far are in [`docs/work_log.md`](docs/work_log.md). Read it before
starting your own runs.

## What is here

```
agent-fuel/
├── sandbox/
│   └── fake_tools.py          tools that fail on command; no real service is called
├── agent/
│   └── runner.py              the agent loop and the connection to the models
├── control/
│   ├── agent_fuel.py          the controller: six components, one policy
│   └── policies.yaml          thresholds, editable without touching code
├── evaluation/
│   ├── scenarios.json         15 failure scenarios in three groups
│   ├── run_experiment.py      the sweep from the command line: 15 x 7 x 3 = 315 runs
│   └── analyse.py             tables and figures for the paper
├── console/                   local dashboard with Start and Stop buttons
├── results/                   shared results, one folder per person and day
├── GETTING_STARTED.md         setup from zero and team rules
└── docs/
    ├── work_log.md            what was done, found and decided, by date
    └── iteration_log.md       scenarios that defeated the controller
```

## The seven arms

A, B and C are the approaches being compared against. D through G take the
controller apart one mechanism at a time, so the difference between two
adjacent arms is that mechanism's contribution.

| Arm | What is on |
| --- | --- |
| A | Nothing. The baseline, bounded only by the 60-step ceiling |
| B | Account-level allowance, shared across the whole sweep |
| C | Iteration cap (15 steps) |
| D | Run budget |
| E | D plus the loop detector |
| F | E plus the circuit breaker |
| G | F plus the error classifier and the warn rung |

## The three groups of scenarios

**A, eight scenarios: the tool is broken.** Unavailable, empty response, auth
error, timeout, broken pagination, flapping, degradation, malformed body.

**B, three scenarios: nothing is broken and spend still runs away.** Unreachable
goal, conflicting data, context accumulation.

**C, four scenarios: the control group.** A long legitimate task, forty
legitimate repetitions, a slow but working service, and an ordinary healthy
run. Any halt here is a false interruption.
