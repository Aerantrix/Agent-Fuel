# Console

The instrument panel of the experiment: the runs were started from here, and
the results were watched here. A local web page with Start and Stop, a worker
that runs one configuration at a time, named batches for runs outside the
page, and the merge that folds everything into one database.

| File | What it is |
| --- | --- |
| `server.py` | The local console: serves the dashboard, Start and Stop, the state of the current run. Listens on 127.0.0.1 only. The API key is read from `~/.config/agent-fuel/anthropic_key` into the worker's environment and never sent to the page. |
| `worker.py` | One batch of runs for one model configuration (`qwen`, `haiku-think-low`, `haiku-think-high`, `haiku-nothink-low`, `haiku-nothink-high`): sets the `AGENT_FUEL_*` variables (see `agent/README.md`), runs the scenarios and repeats asked for, appends every finished run to `runs.jsonl`, stops past a spend cap. |
| `batch.py` | Named batches run outside the console, each into `data/batches/<name>/` with a `launch.log`, so the results can be inspected before they are merged. The batches of weeks 9 and 10: `live-g`, `live-g-qwen` (the full controller live), `haiku-gaps`, `qwen-gaps` (single timeouts refilled), `qwen-langchain-r23`, `qwen-real-r23`, `haiku-real-r23` (repeats on the framework prompts). |
| `merge_runs.py` | Folds run files from batches into `data/runs.jsonl`. A record with an id already present replaces the earlier one; the replaced records go to `data/superseded.jsonl`, so nothing is lost. |
| `dashboard.src.html`, `build_dashboard.py` | The dashboard page: run status, the headline figures, the token curve, the trade-off of tokens saved against healthy runs spoiled, the scenario matrix, run detail. One source, two builds: the local page with the launch panel (`dashboard.html`, built on start, not in git) and the read-only page published on claude.ai. |
| `Agent Fuel.command` | Opens the console with a double click on a Mac. |
| `data/runs.jsonl` | The frozen database every result is computed from: 775 records, 754 after replacements (see the root README, "Reproducing the paper's numbers"). The only data file in git; batches, the pilot and superseded records stay local. |

## Running

The console, from the project root in the project's Python environment
(`GETTING_STARTED.md`, part 1):

```
python console/server.py        # then open http://127.0.0.1:8790
```

One configuration by hand, the way the console starts it:

```
python console/worker.py --repo . --data console/data --config haiku-think-low \
    --scenarios 1,2,3,4,5,6,8,13,15 --arms A --repeats 3 --condition strict --max-cost 1.0
```

`--arms` is the control configuration code (`A` no control, `G` the full
controller; see the root README, "The controls"); `--condition` the prompt
level; `--real-prompt FILE` a framework's prompt in place of ours;
`--error-hint` the fourth condition; `--temperature` where the model accepts
one; `--repeat-ids 2,3` to fill particular repeats without renumbering;
`--max-cost` the spend cap in dollars for the batch.

A named batch, and folding its results in:

```
python console/batch.py --list
python console/batch.py live-g --dry-run      # print the worker commands
python console/batch.py live-g                # run them
python console/merge_runs.py console/data/batches/live-g
```

Paid runs (Haiku) need the key file; local runs (Qwen) need Ollama with
`qwen2.5:7b` pulled.

## What a record holds

One JSON line per run: the model, condition, temperature, scenario, control
code and repeat; steps, tokens and cost; whether and by which mechanism the
controller halted it; the trace (every model reply and tool result), the
token curve, and the controller's decisions step by step. The analysis in
`evaluation/` reads nothing else.
