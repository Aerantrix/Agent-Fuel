# Console

The instrument panel of the experiment: one local page with two modes.

- **Data**: the frozen database every result is computed from, the controls
  computed over it, the charts, the scenario matrix and the step-by-step
  record of any run.
- **Run**: pick a run (four presets that tell the paper's story on the local
  model, or your own), read the exact worker command the console will
  execute, press Start, and watch the run step by step as it happens: the
  agent's reply, the tool's answer, the controller's verdict, the tokens.
  When it finishes it lands in the same tables, marked as a console run. The
  filters follow the launch, so what you started is what you see.

Runs started from the page never touch the frozen database. They go to
`data/console/` with a suffix on their id, are shown beside the frozen
records, and are folded into the database only by hand with `merge_runs.py`.

| File | What it is |
| --- | --- |
| `server.py` | The local server: serves the page, Start and Stop, the state of the current run, the command for a launch. Listens on 127.0.0.1 only. The API key is read from `~/.config/agent-fuel/anthropic_key` into the worker's environment and never sent to the page. |
| `dashboard.html` | The page, both modes. One file, no build step. |
| `worker.py` | One batch of runs for one model configuration (`qwen`, `haiku-think-low`, `haiku-think-high`, `haiku-nothink-low`, `haiku-nothink-high`): sets the `AGENT_FUEL_*` variables (see `agent/README.md`), runs the scenarios and repeats asked for, appends every finished run to `runs.jsonl` in its data folder, writes `live.json` at every step, stops past a spend cap. |
| `batch.py` | Named batches run from a terminal, each into `data/batches/<name>/` with a `launch.log`. The batches of weeks 9 and 10: `live-g`, `live-g-qwen` (the full controller live), `haiku-gaps`, `qwen-gaps` (single timeouts refilled), `qwen-langchain-r23`, `qwen-real-r23`, `haiku-real-r23` (repeats on the framework prompts). |
| `merge_runs.py` | Folds run files from batches or the console folder into `data/runs.jsonl`. A record with an id already present replaces the earlier one; the replaced records go to `data/superseded.jsonl`, so nothing is lost. |
| `Agent Fuel.command` | Opens the console with a double click on a Mac. |
| `data/runs.jsonl` | The frozen database: 775 records, 754 after replacements (see the root README, "Reproducing the paper's numbers"). The only data file in git; the console folder, batches, the pilot and superseded records stay local. |

## Running

The console, from the project root in the project's Python environment
(`GETTING_STARTED.md`, part 1):

```
python console/server.py        # then open http://127.0.0.1:8790
```

The Run mode shows the worker command for whatever is picked; this is what
it runs for the first preset:

```
python -u console/worker.py --repo . --data console/data/console --config qwen \
    --scenarios 4 --arms G,A --repeats 1 --max-cost 1.0 --condition strict \
    --temperature 0.0 --id-suffix=-console-<date>-<time>
```

`--arms` is the control configuration code, in the order to run (`A` no
control, `G` the full controller; see the root README, "The controls");
`--condition` the prompt level; `--real-prompt FILE` a framework's prompt in
place of ours; `--error-hint` the fourth condition; `--temperature` where
the model accepts one; `--repeat-ids 2,3` to fill particular repeats without
renumbering; `--max-cost` the spend cap in dollars; `--id-suffix` keeps the
run apart from the frozen records.

A named batch from a terminal, and folding its results in:

```
python console/batch.py --list
python console/batch.py live-g --dry-run      # print the worker commands
python console/batch.py live-g                # run them
python console/merge_runs.py console/data/batches/live-g
```

Paid runs (Haiku) need the key file; local runs (Qwen) need Ollama with
`qwen2.5:7b` pulled.

## The four presets

Qwen at temperature 0 with a fixed seed is deterministic, so these runs come
out the same every time. Each runs the full controller first, then no
control, on the strict prompt.

| Preset | Scenario | Without control | With Agent Fuel |
| --- | --- | --- | --- |
| Timeout: runaway against a stop | 4 | 60 steps, about 104,000 tokens | 4 steps, 1,198 tokens, loop detector |
| Authentication error: stopped at step 1 | 3 | 60 steps, about 95,000 tokens | 1 step, 223 tokens, error classifier |
| Flapping service: left alone | 6 | 21 steps, the task done | 21 steps, untouched |
| Forty domains: the budget's weakness | 13 | 41 steps, about 97,000 tokens, honest work | cut at step 29 by the run budget |

The uncontrolled runs of scenarios 3 and 4 go to the 60-step ceiling and
take several minutes on a local model; the controller's run comes first so
the stop is on screen while the runaway is still going.

## What a record holds

One JSON line per run: the model, condition, temperature, scenario, control
code and repeat; steps, tokens and cost; whether and by which mechanism the
controller halted it; the trace (every model reply and tool result), the
token curve, and the controller's decisions step by step. The analysis in
`evaluation/` reads nothing else.
