# Results

Four files, all computed from the frozen database `console/data/runs.jsonl`
by the three commands below. Nothing here was written by hand; every number
is a count, a sum or a ratio of sums over the rows of `replay.csv`.

```
python -m evaluation.analyse          # summary.md, replay.csv
python -m evaluation.compare_live     # live_vs_computed.md
python -m evaluation.config_matrix    # config_matrix.csv
```

## summary.md

Every table of the study, more than the paper has room for: the runs without
control by model and prompt; the headline comparison of Agent Fuel against the
step cap and the account limit, by model family and by variant; the ladder
that switches the mechanisms on one at a time; coverage by scenario; the two
blunt controls across their parameter (cap 10 to 40 steps, limit 1 to 10
days); and the runs the stand itself spoiled. The paper's Tables VI and VII
and Fig. 2 are drawn from it.

## replay.csv

One row per recorded run and control: 660 runs without control × 14
controls, 9,212 rows (the account limit has no row where the model and prompt
had no healthy reference task to define a day's spend).

| Column | Meaning |
| --- | --- |
| `run_id` | the record in `console/data/runs.jsonl` |
| `variant`, `model`, `family`, `condition` | Haiku by thinking and effort, Qwen by temperature; the prompt condition |
| `scenario_id`, `group`, `repeat` | scenario 1 to 15; group A (failure), C (healthy control), R (reference) |
| `control`, `code` | the control applied: `G` Agent Fuel, `M` mechanisms without the run budget, `D` `E` `F` the ladder, `C10`…`C40` step caps, `B1`…`B10` account limits in days |
| `steps_without`, `tokens_without` | the run as recorded, with no control |
| `hit_ceiling`, `gave_up`, `defect` | cut by the harness at 60 steps; ended by the agent within the minimum; ended by a stand defect |
| `minimum`, `excess` | tokens by the end of step 3; tokens spent beyond that |
| `tokens_with`, `steps_with`, `halted`, `mechanism` | where the control would have stopped the run, and which mechanism fired |
| `saving`, `saving_in_excess` | tokens the control saves; the part of it that was excess |
| `status` | failure runs: `covered`, `not covered`, `not checked`; healthy runs: `intact`, `spoiled` |
| `expected_mechanism` | the mechanism the scenario names; attribution holds when it equals `mechanism` |

## config_matrix.csv

What was run under which settings: one row per model, thinking, effort,
temperature, prompt condition, scenario and control configuration, with the
number of records, the repeat numbers, how many came from the pilot, and the
dates of the first and last run. 376 rows, 754 records, of which 660 are runs
without control.

## live_vs_computed.md

The live check: 74 runs made with the controller switched on, each beside the
replay of the matching run without control. For each: steps and tokens live
and computed, who halted the run, whether the two agree and whether they end
at the same step. The paper's Section X.D is drawn from it.
