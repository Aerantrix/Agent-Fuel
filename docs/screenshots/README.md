# Screenshots of the console

The console (`console/`, see its README) as it ran on 26 November 2026, on the
frozen database with the filters at the strict prompt, Qwen 2.5 7B,
temperature 0, and two runs started from the console that morning (scenario 3,
the authentication error, under the full controller and with no control).

| File | What it shows |
| --- | --- |
| `01-data-filters-and-results.png` | Data mode: the filters (prompt levels, real framework prompts, temperature, models, the toggle for console runs) and the four result tiles: tokens burned without control, tokens saved by the controller, false interruptions, runs in view. |
| `02-results-charts.png` | The burn curve (cumulative tokens per step, one line per control configuration) and safety against utility (tokens saved against healthy tasks interrupted, one point per configuration). |
| `03-scenario-matrix.png` | The scenario matrix: one cell per scenario and configuration, median tokens with the steps of the median repeat, coloured by the worst ending; dashed cells are computed over the uncontrolled run; below it, the run opened from a cell. |
| `04-run-presets-and-command.png` | Run mode: the four presets that tell the paper's story, and the exact worker command the console will execute. |
| `05-run-step-by-step.png` | A run as it happens: scenario 3 with no control on Qwen, 60 identical calls answered by the same 401, 94,800 tokens, stopped only by the 60-step ceiling. The same scenario under the full controller stops at step 1 with 223 tokens. |
| `06-controller-decisions.png` | The controller's decision trail for that run, every check with its verdict and the tokens spent so far: the evidence behind the results. |
| `07-how-the-experiment-works.png` | The end of the trail and the page's own explanation of the stand: scenarios, fault harness, agent loop, model provider, controller, result files. |
