You are working in a Python repository called Agent Fuel. It is a research
instrument for a university experiment, not a product. Read `DEVELOPER.md` in
the repository root before writing any code: it is the authority, and this
message is a summary of it.

**Context.** The experiment runs an LLM agent against tools that fail on
command and measures two things across seven control configurations: how many
tokens are burned after a failure, and how many healthy runs the control kills
by mistake.

**Your task.** Two functions in `agent/runner.py` are stubs. Implement only
those two. Everything else in the repository is finished.

1. `call_model(messages, model)` returns
   `(text, input_tokens, output_tokens, cost_usd)`. Support two backends,
   selected by `AGENT_FUEL_BACKEND`: `ollama` (local, the default for
   development) and `anthropic` (hosted). Token counts must come from the
   provider's response and must never be estimated. Temperature 0.
   **Disable the SDK's built-in retries** (`max_retries=0` or the equivalent):
   retry behaviour is the subject of the experiment, and a silent SDK retry
   invalidates the measurement. No prompt caching. Read any API key from the
   environment; never write one into the repository.

2. `parse_action(text)` returns `(tool_name, args_dict)`, or `None` when the
   agent is finished. Prefer the structured tool call over parsing prose. If a
   response carries both text and a tool call, the tool call wins. If the model
   names a tool that does not exist, return it unchanged: the runner handles
   that case and the behaviour is part of what gets measured.

**Constraints that will look like bugs.** The repository contains six
deliberate design decisions, each with a scenario built to catch anyone who
"improves" it. `DEVELOPER.md` lists all six with reasons. Do not change: the
loop detector's conservative argument normalisation; `latency_counts_as_failure:
false`; the circuit breaker's sliding window; the `ARMS` table; the position of
`time_budget` outside the ablation ladder; or any `expected_mechanism` value in
`evaluation/scenarios.json`. If a run reports `mechanism_matched: false`, that
is a result to report, not a field to correct.

**Done means** this completes and writes real provider token counts into
`results/runs.csv` and `results/decisions.csv`:

```
AGENT_FUEL_BACKEND=ollama python -m evaluation.run_experiment --only 1
```

**Then run the probe and report one number.** Scenario 1 under arm A on
Ollama: how many steps does the agent take before it stops? Report that number
before doing anything that costs money. It decides whether the full sweep runs
locally for free or on a paid model.

Do not refactor, rename or restructure anything outside the two functions. If
something looks broken, check `DEVELOPER.md` before changing it; if it is not
covered there, ask rather than fixing.
