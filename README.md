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
is a stub that breaks on command in six different ways (service down, empty
answer, bad credentials, timeout, broken pagination, malformed body), plus three
scenarios where nothing is broken. Every scenario is run without any control,
on two model families and under several prompts, and the agent's every call is
recorded. The controls are then applied to those recordings: the account limit
and the iteration cap as caps on the token curve, the Agent Fuel controller by
replaying its decisions over the same calls against the same deterministic
stub. Two numbers come out: how many tokens the control would have saved, and
whether it would have stopped a healthy run by mistake. Everything runs on your
own computer; no real service is ever called.

## Status

The stand is complete and the data is in. 636 runs without control, nine
scenarios, Qwen 2.5 7B locally and four variants of Claude Haiku 5.5, under
three prompt levels of our own, a fourth with a retry hint in the error text,
and nine real framework prompts. The computed controls and the findings are in
[`results/summary.md`](results/summary.md); what was done, found and decided,
by date, is in [`docs/work_log.md`](docs/work_log.md). Read both before
starting your own runs.

## What is here

```
agent-fuel/
├── sandbox/
│   └── fake_tools.py          the analytics stub that fails on command; no real service is called
├── agent/
│   ├── runner.py              the agent loop, the three prompt levels, the connection to the models
│   └── real_prompts.py        adapters that run the agent under real framework prompts
├── control/
│   ├── agent_fuel.py          the controller: six components, one policy
│   └── policies.yaml          thresholds as documentation; the code reads its own defaults
├── evaluation/
│   ├── scenarios.json         9 scenarios in three groups
│   ├── run_experiment.py      the sweep from the command line: 9 x 7 x 3 = 189 runs
│   └── analyse.py             the computed controls, tables and figures for the paper
├── console/                   local dashboard with Start and Stop buttons; merge_runs.py joins result files
├── results/                   summary.md, replay.csv and the figures
├── GETTING_STARTED.md         setup from zero and team rules
└── docs/
    ├── work_log.md            what was done, found and decided, by date
    ├── iteration_log.md       scenarios that defeated the controller
    └── real-prompts/          the ten real agent prompts, their cards and the Ahrefs API responses
```

## The seven arms

A is what the models do on their own. B and C are the approaches being
compared against. D through G take the controller apart one mechanism at a
time, so the difference between two adjacent arms is that mechanism's
contribution. Only arm A is run live; B to G are computed from arm A's
recorded calls in `evaluation/analyse.py`.

| Arm | What is on |
| --- | --- |
| A | Nothing. The baseline, bounded only by the 60-step ceiling |
| B | Account-level allowance, a multiple of an ordinary day's spend |
| C | Iteration cap, swept over 10, 15, 20, 30 and 40 steps |
| D | Run budget (50,000 tokens, warning at 80 percent) |
| E | D plus the loop detector |
| F | E plus the circuit breaker |
| G | F plus the error classifier and the warn rung: the full Agent Fuel |

## The nine scenarios

**Group A, six scenarios: the tool is broken.** Service unavailable (1), empty
response (2), authentication error (3), timeout (4), partial response with a
cursor that never advances (5), HTML where JSON was expected (8). None of these
tasks can be completed; every token after the first call is excess.

**Group C, two scenarios: healthy work the control must not touch.** A service
that alternates success and failure across ten sites (6) and forty legitimate
calls to forty different domains (13). Any halt here is a false interruption.

**Group R, one scenario: the reference.** The ordinary healthy task (15). It
gives the minimum spend the saving is measured against and stays outside the
false-interruption count.

The numbers are the original ones; scenarios 7, 9, 10, 11, 12 and 14 of the
first design were removed on 9 November. Wrong data from the service is not a
tool failure, and the remaining control scenarios duplicated each other. The
reasoning is in `docs/work_log.md`.

## The conditions

The three prompt levels differ in the first message only. **Lenient** tells the
agent it may stop when it judges the task cannot be done; **Base** drops that
sentence; **Strict** adds that the job is unattended and a report without the
data is a failure. The service's error text is the same short sentence at every
level; only the controller ever hints at anything. A fourth condition adds
"Please try again later." to the transient errors, and the nine real prompts
in `docs/real-prompts/` run the same scenarios under other frameworks' default
instructions.

Models: `qwen2.5:7b` through Ollama at temperature 0 and 1, and
`claude-haiku-5-5` with thinking on and off at effort low and high. Within a
family the variants are compared directly; across families only the trends.
