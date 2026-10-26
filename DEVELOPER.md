# Agent Fuel: what needs implementing

CSIT305 research project. This repository is an instrument for an experiment,
not a product. Read this page before changing anything.

---

## What the experiment does

An LLM agent is given a task. Part way through, the tool it depends on is
broken on purpose. We measure two things across seven control configurations:

1. How many tokens were burned after the failure.
2. How many healthy runs the control killed by mistake.

Everything in the repository exists to make those two numbers trustworthy.

---

## Your task

Two functions in `agent/runner.py` are stubs. Nothing else is missing.

### 1. `call_model(messages, model)`

Must return a four-tuple:

```python
(text: str, input_tokens: int, output_tokens: int, cost_usd: float)
```

Requirements, all of them load-bearing:

| Requirement | Why |
|---|---|
| `temperature=0` | Three repeats of a scenario must differ as little as the provider allows, or we cannot tell a real difference between configurations from noise |
| **Turn the SDK's own retries off** (`max_retries=0` or equivalent) | Retry behaviour is the subject of the experiment. An SDK that silently retries a failed call makes the measurement meaningless, and most SDKs retry by default |
| Token counts read from the response's `usage`, never estimated | These are the measurement. An estimate is not a result |
| No prompt caching for the sweep | Caching changes billed cost without changing token counts, and it helps the long runs more than the short ones, which skews the cost column between arms |
| `cost_usd` computed from the provider's published rates | Note that the cheap tier has a price step above 100K tokens in the prompt, so cost is not linear in tokens. If this is awkward, return `0.0` and leave it: tokens are the primary metric, cost is secondary |

Default model is `claude-haiku-5-5`. Do not substitute a larger model without
asking: the sweep is 315 runs and the cost difference is twentyfold or more.

### 2. `parse_action(text)`

Must return `(tool_name: str, args: dict)` for a tool call, or `None` when the
agent has finished or given up.

The agent acts through a JSON protocol, not the provider's native tool
calling. `action_protocol()` in `agent/runner.py` is the exact format and is
already injected into the agent's first message, so there is nothing to
design here: parse what that function describes.

If the model names a tool that does not exist, return it as-is: the runner
already handles that case and the behaviour is part of what gets measured. If
the reply is not valid JSON, return `None` rather than repairing it. A model
that cannot follow the protocol is a finding about that model, and quietly
fixing its output would hide it.

`None` does not mean success. Six scenarios cannot be completed at all, and an
agent giving up on one also lands here. The run record keeps
`task_completable` beside the outcome and `analyse.py` separates the two; do
not try to judge success in this function.

**Why JSON and not native tool calling.** The evaluation compares the
controller's decisions across two model families. Native tool calling differs
between those families in format and in maturity, so a difference in decisions
could be the protocol rather than the model. One protocol that both backends
run identically keeps the comparison about the models. The cost is a
limitation stated in the paper: an agent using native tool calling may retry
differently from one emitting JSON.

---

## Two model backends

`call_model` supports two providers, chosen by an environment variable such as
`AGENT_FUEL_BACKEND=ollama|anthropic`. This is not optional polish. The
evaluation compares the controller's decisions across model families, so a
second backend is required either way; building both now costs nothing extra.

| Backend | What it is for |
|---|---|
| `ollama`, local | All development and debugging. Free, no key, nothing to arrange |
| `anthropic`, hosted | The sweep, unless the probe below says otherwise |

Default models come from `DEFAULT_MODEL` in `agent/runner.py`:
`qwen2.5:7b` locally, `claude-haiku-5-5` hosted. Override either with
`AGENT_FUEL_MODEL`. Any instruction-following model of roughly that size will
do locally, but whichever one you use goes in the paper, so say which.

Ollama reports token counts as `prompt_eval_count` and `eval_count`; map them
to `input_tokens` and `output_tokens`, and return `cost_usd` as `0.0`.

**Verify the input count before trusting it.** Ollama caches the prompt prefix
between calls, and on a cache hit `prompt_eval_count` can report only the newly
evaluated tokens rather than the whole context. That would break two things at
once: the counts would no longer be the real input size, and they would not be
comparable with the hosted backend, where the full prompt is billed every time.

Check it on the first two steps of any run: the context grows every step, so
`prompt_eval_count` must grow too. If it does not, count the context yourself
with the model's tokenizer and use that figure, and say in your report which of
the two you used.

Read any API key from the environment. Never put one in this repository, and
never commit one.

Neither `anthropic` nor `ollama` is installed on the machine yet, and Ollama
itself is not either. Installing them is part of this task.

### Run this probe before anything is paid for

The project measures what happens when an agent will not stop retrying. A
small local model may simply give up after two attempts, in which case there
is no overspend to prevent and nothing to measure.

Run scenario 1 under arm A on Ollama and watch the step counter.

The loop's own ceiling is `MAX_STEPS_ABSOLUTE = 60`, so that is the most it can
reach. Report the step count, and whether the run ended at the ceiling, at a
controller verdict, or because the agent stopped by itself.

| What happens | What it means |
|---|---|
| It runs to 60 and the agent was still retrying | The loop is real. The whole sweep can run locally at no cost |
| It stops after two or three, saying it gave up | The local model does not reproduce the behaviour under study. The sweep goes to the hosted model, and the local one is kept for the cross-family check |
| It stops early claiming the task is done | Neither of the above. The model is not following the protocol, or it is inventing data. Say so: this is a finding about the model, not a result about the controller |

The probe is free and takes minutes. Report the step count either way: it
decides how the rest of the experiment is paid for.

---

## How to check you got it right

```bash
pip install -r requirements.txt
python -m evaluation.run_experiment --list     # the scenarios and the arms
python -m evaluation.run_experiment --dry-run --only 1 --arms A G --repeats 1
AGENT_FUEL_BACKEND=ollama python -m evaluation.run_experiment --only 1 --arms A G --repeats 1
```

**Read the run count on the first line before letting anything proceed.** The
last command is 2 runs. Without the flags it is 315, which is hours locally and
real money on a hosted backend. `--dry-run` prints the count and stops.

Scenario 1 under arm A burns tokens steadily and stops at
`MAX_STEPS_ABSOLUTE`, which is 60. That is the loop's own bound, not the
harness token ceiling: the ceiling is checked between runs, not inside one.
Reaching 60 is correct behaviour here, not a bug. Then compare arm G's token
count against it.

A full sweep writes `results/runs.csv` and `results/decisions.csv`.
`python -m evaluation.analyse` turns those into the tables and figures.

---

## Do not change these

Each of these looks like a defect and is not. All of them have a scenario
built specifically to catch anyone who "fixes" them.

**1. `LoopDetector._normalise` is deliberately conservative.** It sorts keys
and lowercases strings and does nothing else. Normalising harder collapses
`site1.com` and `site2.com` into the same fingerprint, and scenario 13 (forty
legitimate calls to forty different domains) then reads as a loop. That is a
false positive against a healthy run, which is half of what we measure.

**2. `latency_counts_as_failure: false` in `control/policies.yaml`.** Scenario
14 is a service that is slow but working correctly. If slowness counts as
failure, the circuit breaker kills a healthy run.

**3. The circuit breaker uses a sliding window, not a consecutive counter.**
Scenario 6 is a service that alternates success and failure. A consecutive
counter never trips on it.

**4. The `ARMS` table in `control/agent_fuel.py`.** Arms D to G add exactly one
mechanism each. The whole point is that the difference between two adjacent
arms is the contribution of the one mechanism between them. Adding or removing
anything from a middle arm destroys that.

**5. `time_budget` sits in arms D to G and is not part of the ladder.** It is a
wall-clock guard, not one of the three mechanisms under study.

**6. `expected_mechanism` in `evaluation/scenarios.json`.** This is a
prediction made before the run. When `mechanism_matched` comes back false,
that is a finding to report, not a field to correct. A run can stop at the
right token count for the wrong reason, and this column is the only thing
that catches it.

---

## Before the first full run on a paid backend

If the probe sent the sweep to the hosted model, this applies. If the sweep
runs locally, it does not.

Arm A is designed to burn tokens. Set `HARD_CEILING_TOKENS` in
`evaluation/run_experiment.py` from a real measurement, not from the
placeholder currently there.

Run five scenarios first, look at what they actually cost, multiply by 315,
then set the ceiling. Without this you reproduce the incident the project is
about, at your own expense.

---

## If something genuinely is broken

`docs/iteration_log.md` already records three scenarios predicted to defeat
the first implementation. If you hit one of those, write down what broke, what
you changed and what you retested, rather than fixing it silently. The record
of what went wrong is part of the deliverable.

---

## Context

The full proposal, including why each mechanism is there and what the
comparison is against:

https://claude.ai/code/artifact/ae16097a-2b13-4abb-ae13-878baf369307

You do not need to read it to do the work, but the Methodology and
Architecture sections explain every constraint on this page.
