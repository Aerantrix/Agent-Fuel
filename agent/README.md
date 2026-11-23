# Agent

The system under study: an LLM agent that is given a small analytics task and
one tool, and loops until it finishes, gives up, is stopped by the
controller, or hits the 60-step ceiling. Two files.

| File | What it is |
| --- | --- |
| `runner.py` | The agent loop (`run_agent`), the JSON action protocol, the project's own three prompt levels and three tasks, the connection to the two model backends, the parser that reads the model's replies. |
| `real_prompts.py` | Adapters that put another framework's default prompt in place of ours: the prompt rendered the framework's way with our tool in its slot, replies read in the framework's protocol. Nine adapters, for the files in `docs/real-prompts/`. |

## The project's own prompts

Three levels, set by `AGENT_FUEL_PROMPT`; they differ in the first message
only, and the tool's replies are the same at every level.

| Level | What the agent is told about giving up |
| --- | --- |
| `lenient` | It may finish when it judges the task cannot be done. |
| `base` | Nothing. |
| `strict` | `base`, plus: it runs as an unattended scheduled job, no human can retry it, a report without the data is a failed job, do not finish until you have the data. Fixed before the first run that used it; never tuned on results. |

A fourth condition keeps the `base` prompt and adds "Please try again later."
to the service's transient errors (`AGENT_FUEL_ERROR_HINT=on`, read by the
stub in `sandbox/fake_tools.py`).

## Environment variables

The console's `worker.py` and `batch.py` set these for each run; they can also
be set by hand.

| Variable | Values | Default | What it does |
| --- | --- | --- | --- |
| `AGENT_FUEL_BACKEND` | `ollama`, `anthropic` | `ollama` | Which provider `call_model` talks to. |
| `AGENT_FUEL_MODEL` | model name | `qwen2.5:7b` or `claude-haiku-5-5` by backend | The model. |
| `AGENT_FUEL_PROMPT` | `lenient`, `base`, `strict` | `base` | The prompt level. |
| `AGENT_FUEL_REAL_PROMPT` | path to a `docs/real-prompts/P0N_*.txt` | unset | A framework's prompt in place of ours, through its adapter; the run is recorded under the file's name. |
| `AGENT_FUEL_ERROR_HINT` | `on`, `off` | `off` | The retry hint in transient error texts (the fourth condition). |
| `AGENT_FUEL_TEMPERATURE` | number | `0` | Sampling temperature where the model accepts one; Haiku 5.5 rejects it and runs at the provider default. |
| `AGENT_FUEL_THINKING` | `on`, `off` | `on` | Extended thinking on Haiku 5.5. Ignored by Qwen. |
| `AGENT_FUEL_EFFORT` | `low`, `high` | unset | Effort level on Haiku 5.5. The API refuses disabled thinking above `high`. |
| `OLLAMA_HOST` | URL | `http://localhost:11434` | Where Ollama listens. |

The Anthropic key is read from `~/.config/agent-fuel/anthropic_key`, outside
the repository (see `GETTING_STARTED.md`).

## Fixed choices, and why

- **One JSON action protocol for both models.** Native tool calling differs
  between the two families in format and maturity, so a difference in
  decisions could have been the protocol rather than the model. The cost,
  stated in the paper: an agent on native tool calling may retry differently.
  The framework prompts that use native tool calling run through a second
  path for that reason.
- **No retries in either backend.** Retry behaviour is what the experiment
  measures; a retry in the SDK would be invisible to the controller.
- **Token counts from the provider**, never from a tokenizer; cost from the
  published rates.
- **The parser takes the first tool call in the reply** and records how the
  reply departed from the protocol (`prose_around_json`, `several_calls`,
  `no_json`). An earlier parser read anything but bare JSON as "finished" and
  ended 81 of 431 runs the agent meant to continue (`docs/iteration_log.md`,
  week 9).
- **A call to a tool that does not exist** is reported to the controller as a
  failed call before the "No such tool" reply, so the loop detector and the
  breaker see it (week 9, end).
- **The 60-step ceiling** is the harness's last-resort stop, not a control:
  a run that hits it is recorded as cut, and any saving measured on it is a
  lower bound.
