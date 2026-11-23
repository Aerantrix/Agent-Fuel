# How the methodology changed from the brief to the design that was run

Sections 1 to 6 are the document of 16 November 2026 (also on the team's
Drive as "Agent Fuel - Methodology changes 2026-11-16"); section 7 brings it
to 23 November. Each change: what the brief said, what was run, why, and the
date of the decision, with the work-log entry that records it.

**In brief.**

- **Scenarios:** was 15 in three groups → is 9 (failures 1, 2, 3, 4, 5, 8;
  healthy work 6 and 13; reference 15), because 7 and 14 tested time rather
  than tokens, 9 would have duplicated 2, 10 is not a tool failure, and 11
  and 12 are the same task as 13 (work log, 9 Nov).
- **Conditions:** was three pressure conditions in the pilot (baseline / P1 /
  P2), the strict one adding a "retry" hint to the service errors → is three
  prompt levels lenient / base / strict that differ only in the first
  message, plus a fourth condition with the hint and nine real framework
  prompts, because the prompt must be the only variable and the hint is a
  lever of its own (work log, 9 and 16 Nov).
- **Models:** was claude-haiku-5-5 at temperature 0 and a second model on 2–3
  scenarios → is Haiku 5.5 without a temperature setting in four variants
  (thinking × effort) and Qwen 2.5 7B on all scenarios at t = 1 (×3) and
  t = 0 (×1), because the Haiku API rejects a temperature and at t = 0 Qwen
  loops where it does not at t = 1 (work log 26 Oct, design document).
- **Configurations and computation:** was seven live configurations × 15 × 3
  = 315 runs → is the uncontrolled configuration run live only, the controls
  computed from its records, with new measures (minimum at step 3, excess,
  coverage), because the stub is deterministic and the controller can be
  replayed over the record (work log, 16 Nov). Section 7: plus a live check
  of the full controller, 54 runs.
- **Stand:** was identical metrics for every domain, a strict parser and a
  verdict checked only after an error → is per-domain metrics, a cursor, a
  tolerant parser and a STOP check on both branches, because those defects
  spoiled scenarios 11–13 and cut short 81 of 431 runs (work log, 26 Oct –
  16 Nov; `iteration_log.md`).

The research question has not changed: "How do execution-level spend
controls compare with account-level limits and iteration caps under external
tool failure, measured in tokens saved against legitimate tasks interrupted,
and which failure modes does none of them cover?"

## 1. Scenarios

**Was.** Fifteen scenarios: A, eight external service failures (1–8); B,
three overspends with no service failure (9–11); C, four control cases
(12–15), where any halt is a false interruption. (README, scenarios.json
v1.0.)

**Is.** Nine: A, 1, 2, 3, 4, 5, 8 (a failure = the service not returning what
it should: an error, nothing, a part, or garbage); C, 6 and 13 (healthy work;
a halt = a false interruption); R, 15 (reference: what the ordinary task
costs). No group B. (scenarios.json v2.0.)

**Why.** 9 Nov, work log: decided with the author after a walk through the
design scenario by scenario. 7 and 14 test wall-clock time rather than tokens,
and the stub's delay was never switched on; 9 would duplicate 2 once fixed;
10, wrong values are not a failure; 11 and 12 are the same task as 13,
shorter. 6 reworked into healthy work because with a flapping service a retry
succeeds and the right verdict is to leave it alone; 15 taken out of the
false-interruption rate because a two-step run cannot plausibly be halted.

| No. and title | Was | Is | Reason | Date |
| --- | --- | --- | --- | --- |
| 1, 2, 3, 4, 8 — Service unavailable, Empty response, Authentication error, Timeout, Malformed response | Group A. Expected mechanism: 1, 4 circuit breaker; 2, 8 result fingerprint. | Group A, same task. Expected mechanism: 1, 2, 4, 8 loop detector; 3 error classifier. | `expected_mechanism` now names the mechanism that the detector logic actually makes fire. | 9 Nov |
| 5 — Partial response with broken pagination | The service returns the same page every time. | The tool takes a cursor and returns the same page whatever cursor is sent. | So that the agent can ask for the next page and never get one. | 9 Nov |
| 6 — Flapping service | Group A; a stop by the sliding-window circuit breaker is expected. | Group C: ten sites, every failed call succeeds on retry; the right verdict is to leave it alone. | It tests whether the controller tells an unreliable service from a broken one; the breaker must stay closed. | 9 Nov |
| 7 — Gradual degradation | Group A: response time grows with every call. | Removed. | Tests time, not tokens; the stub's delay was never switched on (found 26 Oct). | 9 Nov |
| 9 — Unreachable goal | Group B: a period that does not exist in the system. | Removed. | The stub returned data for the "impossible" period (found 26 Oct); once fixed it would duplicate scenario 2. | 9 Nov |
| 10 — Conflicting data | Group B: two tools give different values. | Removed. | Wrong values are not a tool failure. | 9 Nov |
| 11 — Context accumulation | Group B: twenty domains, everything working. | Removed. | The same healthy task as 13, shorter; 26 Oct: twenty domains fit in 30K tokens. | 9 Nov |
| 12 — Long legitimate task | Group C: ten domains. | Removed; the ten-site task is used in the reworked scenario 6. | The same healthy task as 13, shorter. | 9 Nov |
| 13 — Legitimate repetition | Group C: forty domains, forty calls with different arguments. | Group C, unchanged in design. | Stand fixes of 26 Oct and 9 Nov (section 5). | 26 Oct, 9 Nov |
| 14 — Slow but working service | Group C: responds in 15 s instead of 1 s. | Removed. | Tests time, not tokens; the delay was never switched on; the `latency_counts_as_failure` flag was read by no code (26 Oct). | 9 Nov |
| 15 — Healthy task | Group C, about eight steps. | Group R (reference); left out of the false-interruption rate. | Nothing can plausibly halt a two-step run and it would only flatter the rate. | 9 Nov |

## 2. Conditions

**Was.** Three persistence conditions (design document): neutral, persistent
(an unattended job) and persistent with errors advising a retry. In the pilot
of 26 Oct – 3 Nov they were stored as baseline / P1 / P2 (Lenient / Base /
Strict on the console); Base and Strict carried the give-up wording, Strict
carried the "retry" hints in the service errors (work log, 9 Nov).

**Is.** Three prompt levels: lenient (the agent is told it may stop when it
judges the task impossible), base (nothing is said about giving up), strict
(base plus the unattended-job instruction, text from 2 Nov); they differ in
the first message only. From 16 Nov: a fourth condition (base plus "Please
try again later." in transient errors) and nine real framework prompts.

**Why.** 9 Nov: the prompt must be the only variable, "the only voices in a
run are the first message and the controller"; the hints are removed from the
errors. 16 Nov: the hint in the errors is a lever of its own that the sweep no
longer measured; Ahrefs documents no such text; measure it separately rather
than put it back into the scenarios. 16 Nov: real prompts, because the design
document required the condition texts to be justified by published prompts;
nine of ten are run, AutoGPT is not run by the author's decision and the
stand's own prompt counts as the tenth.

Not recorded in the log: which pilot scenarios the "retry" hints applied to;
the reason AutoGPT was left out.

## 3. Models

**Was.** claude-haiku-5-5 at temperature 0, three repeats (HANDOVER,
DEVELOPER); a second model of another family on 2–3 scenarios. The design
document also mentions "a stronger model on the overspend scenarios".

**Is.** Haiku 5.5 without a temperature parameter, four variants: thinking on
or off × effort low or high, three repeats. Qwen 2.5 7B on all nine
scenarios: t = 1 three repeats, t = 0 one (extra). Compared within a family;
across families by trend only. Haiku 4.5 is not used; no stronger model
appears in the log.

**Why.** 26 Oct: the API returns 400 on a non-default temperature for Haiku
5.5; the three repeats cover the spread. 26 Oct: thinking adds variance and
Qwen does not think, so without thinking for a fair comparison, with thinking
as the model is normally used. Design document: temperature 0 is unsuitable
as the main setting, at t = 0 Qwen produced a loop that does not occur at
t = 1; the main setting is t = 1, three repeats, spread reported. 9 Nov:
effort variants (the API refuses disabled thinking above high); the two
models cannot be put under identical settings, hence comparison by trend.

Not recorded in the log: why Haiku 4.5 was set aside; why Qwen at t = 0 and
the real prompts have a single repeat.

## 4. Configurations and the computation of the measures

**Was.** Seven live configurations (A no control, B account-level limit, C
iteration cap of 15 steps, D–G the ladder from the run budget to the full
Agent Fuel): 315 runs, or 495 with the cap swept over 10–40. Overspend =
tokens from the failure step to the end of the run; false interruption = the
share of control-group runs halted; the run budget carried a $2 cost ceiling
(HANDOVER, policies.yaml).

**Is.** Only A is run live (431 records by 16 Nov). B and C are cuts of the
token curve; D–G are the controller replayed over the recorded calls.
Measures: minimum (spend by the end of step 3 without control), excess
(without control minus minimum), saving "at least" (A is cut at 60 steps),
share of excess, spoiled tasks (6 and 13), coverage (covered / not covered /
not checked). The $2 ceiling is out; the 50,000-token run budget stays;
iteration cap 10–40 with 15 as the headline; account limit as a multiple of a
day of 10 healthy tasks, headline 2 days (analyse.py).

**Why.** 9 Nov: open item, the account limit and the iteration cap are to be
computed from A's journals rather than run. 16 Nov: the stub is
deterministic, so every control is computed over the A runs; the parameters
are open to the author; the $2 ceiling is "out of the design". Design
document: the account limit is modelled as a day of N tasks with a shared
limit; the covered / not covered / not checked triple is defined there too.
16 Nov evening, author's decision: the 50,000 budget stays; that it cuts the
honest forty-site task (about 106,000 tokens over 41 steps on Haiku) is
reported as a weakness of the controller; the "mechanisms only" row is the
explanation; setting the budget is future work.

## 5. Stand

**Was.** The multi-domain tasks did not name their domains; the stub returned
the same metrics for every domain; the result fingerprint included the
request; the parser read anything but bare JSON as "finished"; the
controller's verdict was checked only after an error.

**Is.** Domains in the prompt; per-domain and per-period metrics from a hash;
a cursor; the result fingerprint without the request, errors counting
towards the call fingerprint only; the breaker's warning reaches the agent;
the parser takes the first tool call and records the protocol deviation;
STOP is checked after a successful call too.

**Why.** Each defect, with its retest, is an entry in `iteration_log.md`: 26
Oct (domains, identical metrics), 9 Nov (fingerprints), 16 Nov (STOP after a
success; the parser, which cut short 81 of 431 runs, the four Haiku variants
rerun, Qwen left as it was).

## 6. Timeline

| Date | What changed |
| --- | --- |
| 26 Oct | Review of the brief, seven fixes; first Haiku 5.5 sweep: the agent does not loop; domains written into the prompt; Haiku without temperature, with and without thinking; the pilot begins. |
| 2 Nov | The unattended-job instruction text fixed (the future strict level); the pilot continues to 3 Nov, 2,765 runs in all. |
| 9 Nov | Stand v2: nine scenarios, three prompt levels with no hints in the errors, four Haiku variants, per-domain metrics, cursor, fingerprints; 60 pilot runs carried over. |
| 16 Nov | Controls computed from the uncontrolled runs, new measures; STOP and the parser fixed, Haiku rerun; the fourth condition, nine real prompts; author's decision: the 50,000-token budget stays. |
| 22 Nov | Unknown-tool calls go through the controller; batches outside the console; LangChain on Qwen repeated three times; the live check planned. |
| 23 Nov | The full controller run live, 27 runs on Haiku and 27 on Qwen, set beside the replay; the gaps filled; the database frozen at 775 records; the paper's final figures. |

Pilot: all 2,765 runs are kept locally
(`console/data/pilot_runs_2026-10-26_to_2026-11-03.jsonl`, not in the
repository); 60 of them (Qwen, scenarios 1–4 and 8, configurations A, C, D)
match the lenient level and were carried over marked `pilot` (work log,
9 Nov).

## 7. Changes of 22–23 November

**A live check of the full controller.** Was: only the uncontrolled
configuration run live, every control computed (section 4). Is: the full
controller was also run live, 27 runs on Haiku 5.5 (thinking, low effort,
strict) and 27 on Qwen 2.5 7B (t = 1, strict), each set beside the replay of
the matching recorded run (`evaluation/compare_live.py`,
`results/live_vs_computed.md`). Why: replay reproduces the halt but not the
warn rung, where a live agent reads the controller's notice one step before
the stop and may change course. Found: where the controller stops without a
warning, live and replay agree exactly; where it warns, the agent usually
stops itself at the step the replay has the detector stop it; on the healthy
flapping-service task the warning alone led Haiku to abandon the task in all
three runs, which replay counts as intact. Reported in the paper as a cost of
the warn rung (work log, 23 Nov; `iteration_log.md`).

**Unknown-tool calls.** Was: a call to a tool that does not exist bypassed
the controller (open item of 16 Nov). Is: reported to the controller as a
failed call, in the live loop and in the replay alike; the error classifier
lets it pass, the breaker and the loop detector count it. Why: that is what a
framework's tool layer would show the controller. Effect on the data: none;
over the 636 runs recorded by then the replay did not change by a row (work
log, 22 Nov).

**Repeats on the real prompts.** Was: every framework prompt once per model.
Is: LangChain on Qwen three times, because its first repeat held the only
real-prompt runaway; the runaway repeated in two of three (493,799 and
291,452 tokens). The other prompts stay at one repeat, and the paper reports
their rows as observations, not rates (work log, 22 Nov).

**Coverage.** Was: six of 430 refusal runs not covered (five timeouts with
changing requests, one run of invented tools). Is: eight of 444 (six
timeouts with changing requests, one run under the SWE-agent prompt that
never made a well-formed call, one run of invented tools). In all eight the
agent changed the request, the format or the tool name at every step, so
the repetition the controller catches never arose.

**The database.** Was: 431 records on 16 Nov, 636 by that evening. Is: 775
records on 23 Nov, 754 after a rerun of a cell replaces the earlier record:
660 runs without control, 20 pilot runs under a step cap and a run budget,
54 live runs of the full controller. Frozen and published in the repository
(`console/data/runs.jsonl`), with `results/replay.csv`,
`results/config_matrix.csv` and the commands that recompute every table
(README, "Reproducing the paper's numbers").

**Names.** The letter codes A–G stay in the records and the result files;
the paper names the configurations in words (no control; step cap; account
limit; Agent Fuel; the mechanisms one at a time) and no longer uses the
letters.
