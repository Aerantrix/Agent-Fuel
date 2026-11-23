# Documentation

| File or folder | What it is |
| --- | --- |
| `work_log.md` | The engineering log, by date, from the first end-to-end run in week 6: what was done, found and decided, with the numbers. The record of development and testing. |
| `iteration_log.md` | Failures, revisions and retests, one entry per defect: what was observed, the diagnosis, the change, the retest. Fourteen entries, weeks 6 to 10. |
| `timeline.md` | When things happened, week by week: methodology decisions, stand and data, documents. Weeks 1 to 3 to be added from the milestone submissions. |
| `methodology_changes.md` | How the study design changed from the brief to what was run: scenarios, conditions, models, configurations, stand, with the reason and week of each change, and a timeline. |
| `architecture-diagram.png` | The architecture of the stand: agent loop, controller, model API, fault harness, scenario suite, journal and analysis. |
| `real-prompts/` | The default prompts of other agent frameworks, copied word for word with a card each, and the documented responses of the Ahrefs API. Cited by the paper as [24]. |
| `archive/` | Documents of the first design, before anything ran. Kept for the record. |

The project's own prompts live in `agent/runner.py`; the scenarios the stand
runs are in `evaluation/scenarios.json`; the results and the files behind the
paper's tables are in `results/`.

Weeks are the project's weeks, counted from Monday 21 September 2026 as week 1; the final package is due at the end of week 10.
