# Work log

What was done, found and decided while bringing the instrument up for the first
time. Newest entries last. `iteration_log.md` stays the record of scenarios
that defeat the controller; this file is the record of the work around it.

---

## 2026-10-26

### Review of the brief before any code

Read `DEVELOPER.md` and the code before writing anything. Seven issues were
raised with the author, all fixed by the author in `b39a323` and `a57cac7`:

1. `--only` was documented but not parsed, so the check command would have
   started the full 315-run sweep. Now `--only`, `--arms`, `--repeats`,
   `--list`, `--dry-run`.
2. The runner passes plain text between `call_model` and `parse_action`, so
   native tool calling could not reach the parser. Decision: one JSON action
   protocol for both backends (`action_protocol()`), stated as a limitation.
3. Default model disagreed between the stub and the brief. Now `DEFAULT_MODEL`.
4. Ollama may cache the prompt prefix and under-report input tokens. The brief
   now asks for a check that `prompt_eval_count` grows every step.
5. The per-run bound is `MAX_STEPS_ABSOLUTE = 60`, not the sweep token ceiling.
6. Arm C set a sentinel instead of a verdict, so `summary()` would raise on
   every halted arm C run. Arm B halts were also unrecorded. Both fixed.
7. No git. Initialised by the author.

### Environment

- Ollama 0.40.11 in `~/.local/ollama`, model `qwen2.5:7b`.
- Python 3.14 venv in `~/.venvs/agent-fuel`. The system Python is 3.9, which
  cannot import `control/agent_fuel.py` (`str | None` annotations).
- Claude API key in `~/.config/agent-fuel/anthropic_key`, outside the
  repository, in a dedicated Console workspace `agent-fuel` with a $10 monthly
  spend limit. Verified with a free model lookup.

### `call_model` and `parse_action`

- Ollama over plain HTTP (`urllib`, one attempt, no retries), temperature 0,
  seed 0, `num_ctx` 32768 so long runs are not silently truncated. Token counts
  from `prompt_eval_count` and `eval_count`, cost 0.
- Anthropic SDK with `max_retries=0`, no `cache_control`. Token counts from
  `usage`. Cost from published rates, with the Haiku 5.5 price step above
  100K prompt tokens.
- `parse_action` reads the JSON protocol strictly: invalid JSON or a reply
  without `"tool"` returns `None`; unknown tool names are returned unchanged.

### Probe: scenario 1, arm A, qwen2.5:7b

**2 steps. The agent stopped by itself.** Step 1 called `analytics` and got
`Service unavailable`; step 2 replied
`{"summary": "The analytics service is currently unavailable. Please try again later."}`
and the run ended. Neither the 60-step ceiling nor the controller was involved.

Findings from the probe, reported rather than corrected:

- The step 2 reply has no `"done": true`, so the model does not follow the
  protocol exactly. `parse_action` returns `None`, as specified.
- The run is recorded `task_completed=True` on a task that cannot be done.
  `analyse.py` separates these in `false_completions`.
- `mechanism_matched` is false (expected `circuit_breaker`): the agent quit
  before any mechanism had anything to do.
- `prompt_eval_count` grew from 144 to 183 between steps, so Ollama reports
  the whole context, not a cached delta. Provider counts are used, not a
  tokenizer. Checked on two steps only; to be repeated on a long run.

Conclusion per the brief: the local model does not reproduce the behaviour
under study, so the sweep goes to the hosted model and Qwen is kept for the
cross-family comparison.

The check command `--only 1 --arms A G --repeats 1` ran and wrote real
provider counts to `results/runs.csv` and `results/decisions.csv`: 370 tokens
in both arms.

### Decisions

- **Haiku 5.5 runs without `temperature`.** The API rejects a non-default
  temperature on this model with a 400. It runs at the provider's sampling
  default; the three repeats and the spread check in `analyse.py` cover it.
  One sentence in the paper's limitations. Code: `NO_TEMPERATURE`.
- **Haiku 5.5 runs twice: thinking at its default and thinking disabled.**
  Thinking tokens are billed as output and add variance, and Qwen does not
  think, so the disabled run keeps the cross-family comparison fair while the
  default run shows how the model is normally used. Code:
  `AGENT_FUEL_THINKING=on|off`, `thinking: {"type": "disabled"}`.
- Haiku 4.5 is not used.

### Findings outside the two functions, not changed

- **Latency is invisible to the controller.** `latency_counts_as_failure` in
  `policies.yaml` is read by no code, so scenario 14 passes whatever its value
  and protected decision 2 cannot be caught being broken.
- **The slow failure modes never wait.** `FakeAnalytics.sleep_enabled`
  defaults to `False` and `build_tools` never sets it, so `timeout`,
  `slow_degrade` and `slow_healthy` return at once and `time_budget` cannot
  fire in any scenario.
- Scenario 14 is described as 15 s per call; the code sleeps 1.5 s.
- Scenario 7 returns correct data on the first call to a one-call task, so the
  agent will probably finish in two steps before any slowdown builds up.

Proposed to the author: a simulated clock. The fake tool reports how long it
would have taken, the controller adds that to elapsed time and reads the
latency flag. No real waiting, identical timing across repeats. Waiting for a
decision.

### Local console

`console/` holds a local dashboard with Start and Stop, because a page hosted
on claude.ai cannot start processes on this machine. It runs the sweep one
configuration at a time (`worker.py`), stops itself at a per-model spend cap,
and shows each run as it finishes. The same page, without the launch panel, is
published on claude.ai for sharing. See `console/server.py`.

### Open

- Calibration on Haiku 5.5: scenarios 1, 2, 9, 11, 13, arm A, both thinking
  modes, before `HARD_CEILING_TOKENS` is set for the full sweep.
- Simulated clock for latency and time budget (author).
- Whether arm C is swept over five step caps, which makes 495 runs per model
  instead of 315 (author, `HANDOVER.md`).

### First hosted sweep: Haiku 5.5, thinking at default, 15 × 7 × 1

105 runs, launched from the console, about $0.03 in total. No API errors.

- **The agent does not loop.** 103 of 105 runs ended with a well-formed
  `{"done": true}`, at most 5 steps and about 200 to 1,800 tokens per run. In
  every failure scenario the agent tried once or twice, reported that it could
  not get the data, and stopped. There is no overspend for the controller to
  prevent at this setting.
- **The controller fired once.** Scenario 3 (authentication error), arm G: the
  error classifier stopped the run after one step, 199 tokens against 642 to
  1,023 in the other arms. That is the intended behaviour.
- **No false interruptions** on the 28 control-group runs, but every one of
  them ended within two steps, so this says nothing yet.
- **Differences between arms are noise, not control.** Scenario 1 spends about
  1,300 tokens in A to D and about 900 in E to G with nothing fired in any of
  them: the agent simply took four steps in one and three in the other.
- **Thinking barely engages.** The first reply is about 34 output tokens, the
  JSON action and little else.
- One protocol slip: scenario 4, arm B, the reply began
  `timeout is transient; retry once.` before the JSON. `parse_action` returns
  `None` as specified, so a run the agent meant to continue was recorded as
  finished.

Defects in the harness, found from the replies and not changed:

- **The multi-domain tasks never name their domains.** `TASKS` carries a
  `domains` list for `ten_domains`, `twenty_domains` and `forty_domains`, but
  `run_agent` sends only `spec["prompt"]`. In scenarios 11, 12 and 13 the agent
  answered in one step that no domains were given and asked for the list. Those
  three scenarios, including the scenario 13 false-positive test for the loop
  detector, did not test anything.
- **Scenario 9 is reachable.** Its failure mode is `healthy`, so the tool
  returns normal metrics for January 1987 and the agent reports them with a
  caveat instead of chasing an impossible goal.

Consequence: in its current form the sweep cannot answer the research
question, because neither model overspends and three scenarios do not run as
designed. Raised with the author: fix the two harness defects, then decide
whether the tasks should push the agent to persist, or whether "current
models give up by themselves" is reported as the finding.

### Fix: the multi-domain tasks now name their domains

With the user's go-ahead, `run_agent` appends `The domains are: ...` to the
prompt of any task with more than one domain (`ten_domains`, `twenty_domains`,
`forty_domains`). Single-domain prompts already name `example.com` and are
unchanged, so scenarios 1 to 10, 14 and 15 see the same text as before.
Retested by re-running scenarios 11 to 13 on Haiku 5.5 under all seven arms.
Scenario 9 (reachable "impossible" period) is still open with the author.

### Scenarios 11 to 13 after the fix: Haiku 5.5, thinking at default, 7 arms

21 runs, $0.07. The long tasks now reach the tool and the second research
number has data for the first time.

- **The tasks complete without control.** Arm A: 10 domains in 11 steps
  (9K tokens), 20 domains in 21 steps (30K), 40 domains in 41 steps (105K).
- **The iteration cap interrupts healthy work, as predicted.** Arm C (15 steps)
  halted both the 20-domain and the 40-domain task at step 15.
- **The run budget interrupts healthy work too.** With `max_tokens: 50000` in
  `policies.yaml`, arms D, E, F and G all halted the 40-domain task at step 28
  or 29 with `run_budget`. The legitimate task needs about 105K tokens, so
  Agent Fuel itself scores a false interruption on scenario 13. The threshold
  was never measured; changing it after seeing this result would tune the
  controller on its own test set, so it is raised with the author rather than
  changed.
- **The loop detector passed its trap.** Forty calls to forty domains were
  never read as a loop in E, F or G (protected decision 1 holds).
- **Scenario 11 is not an overspend.** Twenty domains finish legitimately at
  30K tokens, under the run budget, so there is nothing to stop and
  `expected_mechanism: run_budget` will not match.
- **A new harness artefact.** The fake tool returns the same metrics for every
  domain. In three runs (11 G, 12 C, 13 B) the agent noticed that site2 was
  identical to site1, said so in prose, and the non-JSON reply ended the run;
  in 11 D it gave up at step 7 for the same reason. Those runs differ from
  their neighbours because of the stub, not the controller. Suggested to the
  author: vary the metrics per domain.

### Team setup: README from zero, console runs on any Mac or Windows machine

The team is five people, two on Windows, each with their own API key. Decided
with the user: changes and results go through pull requests (no branch
protection on this plan, so it is a team rule), and the model set stays fixed
at Qwen 2.5 7B and Haiku 5.5 with and without thinking; a multi-provider model
page was considered and dropped.

- README rewritten with a "Getting started from zero" part: accounts, VS Code
  and an assistant (permission modes checked against the Claude Code docs),
  Git, Python environment in `.venv`, the local model through Ollama, a
  personal API key with a workspace spend limit, starting the console, and
  pull-request rules with requests to paste to the assistant.
- `console/server.py` no longer assumes this machine's paths: it runs the
  worker with its own Python and finds Ollama on PATH, in `~/.local/ollama` or
  in the Windows install folder. Worker output is read as UTF-8, and a worker
  stopped on Windows no longer leaves the status as running.
- `anthropic` added to `requirements.txt`; `.venv/` ignored.

Checked on this Mac with a free Qwen run through the console. The Windows
steps and the PowerShell key command are untested until a team member on
Windows runs them.
