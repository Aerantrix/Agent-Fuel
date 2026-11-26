# A working session with the AI assistant

Screenshots of one session with Claude Code (Anthropic) on 9 November 2026,
week 8, in which the author walked through the study design scenario by
scenario. It is the session behind the week 8 entry of
[`timeline.md`](../timeline.md): fifteen scenarios became nine, and the
controller's settings were fixed. The requests and answers are shown as they
were written, in Russian, without translation.

| File | What it shows |
| --- | --- |
| `01-the-problem-on-fingers.png` | The author asks to take the design document apart in plain terms, starting from the agent that calls an external service; the assistant explains the agent loop and why every retry costs more than the last. |
| `02-what-the-stub-returns.png` | The author notes there are fifteen scenarios and asks for the stub's answer in each; the table of what the agent receives, scenario by scenario. |
| `03-circuit-breaker-window.png` | The author does not follow why the breaker counts failures among the last five calls; the assistant compares three ways of counting, then explains again with phone calls to an office. |
| `04-scenarios-keep-or-remove.png` | The author asks which scenarios to keep, which to remove and why, and which controller mechanism should catch each, or could spoil healthy work. |
| `05-fewer-control-scenarios.png` | The author decides to remove scenarios 7, 9, 10 and 14 and finds five control scenarios too many and partly duplicated; scenario 11 goes, and scenario 15 is kept as a reference outside the false-interruption count. |
| `06-final-scenarios-and-settings.png` | The final list of scenarios with what the agent receives and what the controller should do, and the controller's settings. |
| `07-settings-and-calculations.png` | The settings again, then the author's questions on how the savings, the account limit and the interrupted tasks are to be calculated. |
