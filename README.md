# Agent Fuel

Execution-level spend control for LLM agents, and the harness that evaluates it.

CSIT305 research project, University of Wollongong in Dubai.

> **New to the project? Start with [GETTING_STARTED.md](GETTING_STARTED.md)**:
> setting up from zero (VS Code, the local model, your own API key) and how
> the team works together.

## Project documents

- [Project progress report](https://uowmailedu-my.sharepoint.com/:w:/g/personal/dm527_uowmail_edu_au/IQDFO5vuNz18Tr3km1-UHGlXAT8HXiSojriNkj6aG3WAfLQ?rtime=eI6qdtVD30g)
  (SharePoint, UOW account): the course of the project, week by week.
- [Team contribution declaration](https://docs.google.com/document/d/1F7ZueZrQGv9BIYD56ktuSQMWgOo4KFPySDXiRp37D7I/edit?tab=t.0)
  (Google Docs): who did what.

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

## Requirements

What the stand has to do, and what each requirement is met by:

| Requirement | Met by |
| --- | --- |
| Make tool failures happen on command and the same way every time, without calling any real service | `sandbox/fake_tools.py`: a stub that breaks in the six failure scenarios and serves the healthy tasks |
| Run the same agent loop on a local model at no cost and on a hosted one | `agent/runner.py`: Qwen 2.5 7B through Ollama, Claude Haiku 5.5 through the Anthropic API |
| Record every run in full: each model call with its token counts, each tool call and result, every controller decision | `console/data/runs.jsonl`, one record per run with its trace |
| Apply every control configuration to the same runs and compute the two measures, tokens prevented and healthy tasks interrupted | `control/agent_fuel.py` replayed over the records by `evaluation/analyse.py` |
| Keep the controller deterministic and explainable: no training, no model of its own, a mechanism and a reason for every decision | `control/agent_fuel.py`, standard library only; the journal of decisions |
| Recompute every table and figure of the paper from the frozen record | the three commands under "Reproducing the paper's numbers" |
| Let a reader watch a run as it happens and browse the results, on their own machine | the console, `console/` |

## Status

The stand is complete and the data is in. 660 runs without control, nine
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
│   ├── run_experiment.py      the sweep from the command line
│   ├── analyse.py             the computed controls, tables and figures for the paper
│   ├── compare_live.py        the live controller runs set beside their replay
│   └── config_matrix.py       the matrix of run configurations, one row per cell
├── console/                   the local console, one page in two modes: Data (the results, the
│                              scenario matrix, any run step by step) and Run (start a run and
│                              watch it step by step); batch.py runs a named batch of runs;
│                              merge_runs.py joins result files. See console/README.md
│   └── data/runs.jsonl        the frozen database: every recorded run the paper is computed from
├── results/                   summary.md, replay.csv, config_matrix.csv, live_vs_computed.md
├── GETTING_STARTED.md         setup from zero and team rules
└── docs/
    ├── work_log.md            what was done, found and decided, by date
    ├── iteration_log.md       scenarios that defeated the controller
    └── real-prompts/          other frameworks' default prompts, copied word for word, with cards; Ahrefs API responses
```

## The console

```
python console/server.py        # then open http://127.0.0.1:8790
```

or double-click `console/Agent Fuel.command` on a Mac. **Data** shows the
frozen database, the controls computed over it, the scenario matrix and any run
step by step. **Run** starts a run on the local model or on Haiku (four presets
tell the paper's story) and shows it step by step as it happens; a finished run
joins the tables marked as a console run, and the matrix can leave such runs
out. Details: [console/README.md](console/README.md).

## Reproducing the paper's numbers

The database is `console/data/runs.jsonl`: 754 records after reruns replace
earlier ones, of which 660 are runs without control (the paper's "660
recorded runs"), 20 are pilot runs under a step cap and a run budget, and 54
are the live check of the full controller. Every table and figure in the paper
is recomputed from it by three commands, in the project's Python environment:

```
python -m evaluation.analyse          # results/summary.md, results/replay.csv, the figures
python -m evaluation.compare_live     # results/live_vs_computed.md: live runs beside their replay
python -m evaluation.config_matrix    # results/config_matrix.csv: what was run under which settings
```

`replay.csv` has one row per recorded run and control; every number in the
paper is a count, a sum or a ratio of sums over its rows. `config_matrix.csv`
has one row per model setting, prompt condition, scenario and control
configuration, with the record count, the repeats, the temperature and the
dates of the first and last run.

## Tests

```
python -m pytest tests
```

`tests/test_controller.py` plays a scripted agent against the stub under the
controller, one test per scenario: which mechanism stops each broken service
and at which call, that the flapping service and the forty-domain task run to
the end, the ablation ladder D to G on the authentication error, and the
components on their own. No model is called. The output of the last run is
kept in [`results/test_log.txt`](results/test_log.txt).

## Tested with

The runs behind the paper and the tests were made on this setup. Newer
versions are expected to work; these are the ones checked.

| Component | Version |
| --- | --- |
| Machine | Apple M5, macOS 26.5.2 |
| Python | 3.14.2 (3.10 or newer required) |
| Ollama | 0.40.16 |
| Local model | `qwen2.5:7b`, digest `845dbda0ea48` |
| Hosted model | `claude-haiku-5-5`, with and without thinking, effort low and high |
| anthropic | 2.3.0 |
| PyYAML | 6.0.3 |
| pandas | 3.1.0 |
| matplotlib | 3.11.2 |
| pytest | 9.2.0 |

## The controls

Every run is made under one control configuration. In the run records and
the result files each configuration has a letter code; the paper names them
in words. A is what the models do on their own. B and C are the two blunt
controls the study compares against. D through G switch the controller's
mechanisms on one at a time, so the difference between two adjacent rows is
that mechanism's contribution. Only A is run live (plus a live check of G, see
`results/live_vs_computed.md`); the rest are computed from A's recorded calls
in `evaluation/analyse.py`.

| Code | What is on |
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
first design were removed in week 8 of the project. Wrong data from the service is not a
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

Two kinds of prompt, in two places. The project's own prompts, the three
levels and the hint variant, are in `agent/runner.py`. The prompts in
`docs/real-prompts/` are not ours: they are the default instructions that
LangChain, CrewAI, SWE-agent and the other frameworks send to the model,
copied word for word from their repositories, with a card per prompt giving
the permanent link, the commit and the licence.

Models: `qwen2.5:7b` through Ollama at temperature 0 and 1, and
`claude-haiku-5-5` with thinking on and off at effort low and high. Within a
family the variants are compared directly; across families only the trends.
