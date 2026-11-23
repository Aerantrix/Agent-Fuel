# Iteration log

What broke, what changed, what was retested. The assessment asks for
successes, failures, revisions and retesting; this file is that record, one
entry per defect, in the order found. Each entry: what was observed, with
numbers; the diagnosis; the change, and where; the retest. The numbers are
the ones recorded at the time and are not updated afterwards. The work around
these entries, by date, is in `work_log.md`; the changes to the study design
itself are in `methodology_changes.md`. Weeks are the project's weeks, counted from Monday 21 September 2026 as week 1; the final package is due at the end of week 10.

---

## Week 6 — Review of the brief before the first run

**Observed.** Reading `DEVELOPER.md` and the code before anything ran: the
documented `--only` flag was not parsed, so the check command would have
started the full 315-run sweep; the default model differed between the stub
and the brief; the iteration-cap configuration set a sentinel instead of a
verdict, so the summary would have raised on every halted run under it, and
account-limit halts were not recorded at all; there was no git repository.

**Diagnosis.** Code written before it was run, against a brief written before
the code.

**Change.** Seven fixes by the author in `b39a323` and `a57cac7`: `--only`,
`--arms`, `--repeats`, `--list`, `--dry-run`; `DEFAULT_MODEL`; verdicts on
both blunt controls; `MAX_STEPS_ABSOLUTE = 60` as the per-run bound; one JSON
action protocol for both backends; git initialised.

**Retest.** The check command `--only 1 --arms A G --repeats 1` ran end to
end and wrote real provider token counts (370 tokens in both configurations).

## Week 6 — The multi-domain tasks never named their domains

**Observed.** First hosted sweep, Haiku 5.5, 105 runs. In scenarios 11, 12
and 13 the agent answered in one step that no domains had been given and
asked for the list. The three scenarios, including the forty-domain trap for
the loop detector, tested nothing.

**Diagnosis.** `TASKS` carried a `domains` list but `run_agent` sent only the
task sentence.

**Change.** `agent/runner.py`: `run_agent` appends "The domains are: ..." to
any task with more than one domain. Single-domain prompts unchanged.

**Retest.** Scenarios 11 to 13 rerun on Haiku 5.5 under all seven
configurations, 21 runs. Without control the tasks complete: ten domains in
11 steps (9K tokens), twenty in 21 steps (30K), forty in 41 steps (105K). The
loop detector passed its trap: forty calls to forty domains were never read
as a loop.

## Week 6 — The stub returned the same metrics for every domain

**Observed.** In the same rerun, four runs ended early because the agent
noticed that site 2 had the same figures as site 1, said so in prose, and the
non-JSON reply ended the run (11 G, 12 C, 13 B; 11 D gave up at step 7 for
the same reason). Those runs differed from their neighbours because of the
stub, not the controller.

**Diagnosis.** `FakeAnalytics` returned one fixed payload whatever the domain.

**Change.** Week 8, `sandbox/fake_tools.py`: healthy metrics derived from
a hash of domain and period, so they differ per domain and never change
between runs.

**Retest.** Scripted agents against the stub and the full controller:
scenarios 6, 13 and 15 run to the end. In the sweep after week 8 no run
ended on "the sites are identical".

## Week 6 — Latency was invisible, and the slow failures never waited

**Observed.** `latency_counts_as_failure` in `policies.yaml` was read by no
code; `FakeAnalytics.sleep_enabled` defaulted to `False` and nothing switched
it on, so the timeout, slow-degradation and slow-but-healthy modes returned at
once and the time budget could fire in no scenario. Scenario 14 was described
as 15 s per call and the code slept 1.5 s.

**Diagnosis.** The time-based scenarios (7 and 14) measured wall-clock time,
which the study does not count; nothing in the stand had been built to make
them measurable.

**Change.** A simulated clock was proposed and not built. In week 8
scenarios 7 and 14 were removed from the design: they test time rather than
tokens. The time budget stays in the controller as a sixth component and is
not studied.

**Retest.** None needed; the scenarios are gone. Recorded in
`methodology_changes.md`.

## Week 6 — The "impossible" period returned data

**Observed.** Scenario 9 (an unreachable goal, a period that does not exist)
was reachable: the tool returned normal metrics for January 1987 and the agent
reported them with a caveat.

**Diagnosis.** The scenario's failure mode was `healthy`; the stub had no
notion of an impossible period.

**Change.** Removed in week 8: once fixed it would have duplicated
scenario 2 (empty response).

**Retest.** None needed.

## Week 6 — The run budget cut the honest forty-domain task

**Observed.** With the run budget at 50,000 tokens, every controller
configuration halted the forty-domain task at step 28 or 29 by `run_budget`.
The task needs about 105,000 tokens, so the controller scored a false
interruption on its own control scenario.

**Diagnosis.** The threshold was a round number set before any honest task
had been measured.

**Change.** None to the code. Changing the threshold after seeing this result
would tune the controller on its own test set, so the question went to the
author. Decision of week 9: the budget stays at 50,000; that it cuts the
honest task is reported as a weakness of the controller, with the
"mechanisms only, no run budget" row kept beside it as the explanation;
setting the budget from the cost of honest tasks is future work.

**Retest.** Week 9, after the parser fix: the honest chain costs Haiku
about 106,000 tokens over 41 steps; the run budget spoils all 41 Haiku control
runs of that task; the three mechanisms without the budget spoil none. In the
live check of week 10 the budget ended every forty-domain run at step 29
live against 28 replayed.

## Week 8 — The result fingerprint included the request

**Observed.** The loop detector's result half (the same answer three times)
could not fire on its own: any change of query produced a new fingerprint
even when the service returned the same thing.

**Diagnosis.** The fingerprint hashed the whole tool reply, including the
fields that echo the request.

**Change.** `control/agent_fuel.py`: the result fingerprint excludes the
request and the fields that echo it.

**Retest.** Scripted agents against the stub and the full controller: varied
queries with the same answer stop on the third call (result fingerprint);
identical retries stop on the third (call fingerprint); varied queries
against a dead service stop before the fifth call (breaker); a 401 stops on
the first.

## Week 8 — Errors in the result fingerprint would have halted the flapping service

**Observed.** With the error text hashed as a result, the reworked scenario 6
(every failed call succeeds on retry) would have been stopped on its third
failure, the wrong verdict for a service that recovers.

**Diagnosis.** Two different failures with the same error text look like the
same result.

**Change.** Errors count towards the call fingerprint only; a circuit-breaker
warning is now passed to the agent as the loop detector's is, instead of
reaching the journal only.

**Retest.** Scripted check: scenario 6 runs to the end under the full
controller. In the sweep, the breaker spoils no Haiku run of scenario 6; on
Qwen under strict it spoils three of four, through a different property (see
week 9, the retry argument).

## Week 9 — A STOP after a successful call was ignored

**Observed.** A STOP from the result fingerprint (the same answer three
times: scenarios 2, 5, 8) set `controller.halted` and the loop went on.

**Diagnosis.** `agent/runner.py` checked the controller's verdict only after a
tool error.

**Change.** The verdict is checked on both branches, after a success and
after an error.

**Retest.** No live controlled run had been made on the new stand, so nothing
was invalidated; the pilot's controlled runs used the old detector and were
already set aside. In the replay the result fingerprint covers scenarios 2, 5
and 8 (9, 37 and 35 covered runs under the full controller).

## Week 9 — The parser ended runs the agent meant to continue

**Observed.** 81 of 431 runs without control ended because the reply held a
tool call the parser could not read: a sentence before the JSON, or several
calls in one reply. Haiku 5.5 without thinking under strict lost 28 of its 36
refusal runs this way, which had read as "gives up in two or three steps
whatever the prompt".

**Diagnosis.** `parse_action` returned `None` on anything but a bare JSON
object, and the runner read `None` as "finished".

**Change.** `agent/runner.py`: the parser takes the first tool call in the
reply and records the departure from the protocol in the run record
(`prose_around_json`, `several_calls`, `no_json`); on several calls the agent
is told that only the first was executed.

**Retest.** The four Haiku variants rerun, 81 runs each, plus the network
gaps; no run ended by the stand. Haiku without thinking under strict persists
about four steps for 1,800 tokens on average and never reaches the ceiling;
the morning's finding was withdrawn as a stand artefact. Qwen was left as
recorded: few of its runs were affected, and its remaining stand-ended runs
(all calls to a multi-domain task in one reply, 16 runs) are counted as *not
checked*, not as findings.

## Week 9 — Two tool calls in one reply broke the native tool path

**Observed.** The first batch of real-prompt runs through built-in tool
calling on the Anthropic API lost nine runs to a 400 error.

**Diagnosis.** When the model emits two `tool_use` blocks in one reply, every
id must receive a `tool_result` in the next turn; only the first was
answered.

**Change.** `agent/runner.py`, `_call_native`: every extra call is answered
with the one-call notice as an error result, tool results first in the turn.

**Retest.** The batch rerun landed without API errors; SWE-agent, Codex CLI
and Goose run on both providers.

## Week 9 — Qwen's retry argument trips the breaker on the flapping service

**Observed.** Qwen under strict spoils scenario 6 three times in four.

**Diagnosis.** On a retry Qwen adds `"retry": "true"` to the call; the stub
rejects the unknown argument, and the breaker counts the rejection as a
failure of the dependency. A property of the stand meeting the model's habit,
not the loop under study.

**Change.** None: accepting unknown arguments would hide a real class of
malformed calls. Reported beside the Qwen rows and in the paper's limitations.

**Retest.** The live check of week 10 reproduced it: the breaker halted
two of three live Qwen runs of scenario 6 at steps 6 and 7, as replayed.

## Week 9, end of week — Calls to tools that do not exist bypassed the controller

**Observed.** After two timeouts under the LangChain prompt, Qwen invented
tools ("Check service status", "Contact support"). The runner answered "No
such tool" without telling the controller, so the loop detector never saw the
calls and the run was *not covered*.

**Diagnosis.** Only `before_tool` saw an unknown call; `after_tool` was never
reached, so the controller never learnt how the call ended.

**Change.** `agent/runner.py`: an unknown tool is reported to the controller
as a failed call (`after_tool` with an `UnknownTool` error) before the "No
such tool" reply. The error carries no status, so the classifier lets it
pass; the breaker counts it against that name; the detector fingerprints it,
so the same invented call three times is a stop. `evaluation/analyse.py`
replays the same way.

**Retest.** Without a model: under no control the run goes on; under the full
controller the third identical unknown call stops it by the call fingerprint.
Over the 636 recorded runs the replay did not change by a single row: in the
six runs with invented tools no call repeated three times, and the one *not
covered* run among them (Qwen under LangChain, scenario 4, five different
invented tools in eight steps) stays not covered. Records without control
are unaffected, since the controller is inert there; nothing was rerun.

## Week 10 — The warning alone spoiled the flapping-service task

**Observed.** Full controller live on Haiku 5.5 (thinking, low effort,
strict), 27 runs. In all three runs of the flapping-service task the
controller only warned (loop detector at steps 3, 5, 7; breaker at 3 of 5
failed at step 7) and never stopped, yet Haiku abandoned the task after four
of ten domains with a partial report. The replay counted these runs as
intact.

**Diagnosis.** The notice's wording, "stop retrying this tool and either
proceed with partial results or report what you could not retrieve", tells
the agent to do exactly what a flapping service does not need. Replay cannot
see this, because the recorded agent never read a notice.

**Change.** None to the controller yet. `evaluation/compare_live.py` labels a
live run that stopped itself after a warning and counts same-step agreement.
Reported in the paper as a cost of the warn rung; a notice that reports
repetition without prescribing a stop is future work.

**Retest.** The same 27 runs on Qwen 2.5 7B at temperature 1: in the third
flapping-service run Qwen read four notices, ignored them and finished all
ten domains in 20 steps, so the effect is the model's reading of the notice,
not the notice alone. Everywhere the controller stops without a warning
first, live and replay agree exactly on both models (authentication error at
step 1; run budget at step 29 to 30 on the forty-domain task).

---

## The three failures predicted in week 5

Before the first run, three scenarios were written down as expected to defeat
the first implementation. What happened to each:

- **Scenario 2, empty response: an argument-only fingerprint would miss it,
  because the agent keeps rephrasing the query.** Confirmed in design and
  addressed in week 8 by the result fingerprint without the request; in
  the data, empty response is covered by the result fingerprint in every
  covered run (9 of 9), the rest of its runs ending by the agent's own choice.
- **Scenario 6, flapping service: a consecutive-error counter resets on every
  success and never trips.** The breaker was built on a sliding window rather
  than a consecutive counter, and in week 8 the scenario itself was
  reworked into healthy work that must not be halted, so "never trips" became
  the right behaviour. What did trip it on Qwen was the retry argument, a
  stand property (week 9).
- **Scenario 14, slow but working: a breaker that treats latency as failure
  opens the circuit on a healthy service.** Never tested: the latency flag was
  read by no code (week 6), and the scenario was removed in week 8 as
  a test of time rather than tokens.
