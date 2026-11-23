# Evaluation

What turns the recorded runs into the numbers of the study.

| File | What it is |
| --- | --- |
| `scenarios.json` | The nine scenarios, machine-readable (v2.0): what breaks, what the agent sees, why a model loops, whether the task can be completed, the expected decision and mechanism. Read by the stand and by the analysis; Table IV of the paper is drawn from it. |
| `analyse.py` | The analysis. Reads the database of runs, computes every control over each recorded run (cap and limit as cuts of the token curve, Agent Fuel and its mechanisms by replaying the real controller over the recorded calls), writes `results/summary.md` and `results/replay.csv`. The measures are defined in its docstring. |
| `compare_live.py` | The live check: each run made with the controller on, beside the replay of the matching run without control. Writes `results/live_vs_computed.md`. |
| `config_matrix.py` | The matrix of run configurations, one row per model setting, prompt, scenario and control. Writes `results/config_matrix.csv`. |
| `run_experiment.py` | The runner of the first design (October), all configurations live. Kept for the record; the runs behind the paper were made through `console/batch.py`. |

Run from the project root, in the project's Python environment:

```
python -m evaluation.analyse
python -m evaluation.compare_live
python -m evaluation.config_matrix
```
