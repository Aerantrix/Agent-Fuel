# Real agent prompts

The default prompts of ten open-source agent frameworks, collected for the
task sheet of 9 November 2026: the text each framework sends to the model at
the start of a run, saved word for word from the framework's own repository,
with a card per prompt. Collected 16 November 2026 through the GitHub API; the
permanent links carry the commit sha of the file that was saved. Nothing was
run.

Files: `P0N_name.txt` is the prompt, unchanged. `P0N_name.md` is the card: the
permanent link, commit date and licence; how the model calls a tool, with one
example from the source; what the model receives when a tool fails, with a
link to the code; the framework's default limits; labels A to E with their
quotes. `api-responses.md` is the documented responses of one real analytics
API (Ahrefs).

## The ten prompts

| # | Framework | Saved from | Commit | Licence | A. Giving up | B. Tool errors | C. Supervision | D. Budget | E. Call format |
|---|---|---|---|---|---|---|---|---|---|
| P01 | smolagents | `src/smolagents/prompts/toolcalling_agent.yaml` | 2025-07-31 | Apache-2.0 | Silent | None | Silent | No | JSON |
| P02 | CrewAI | `lib/crewai/src/crewai/translations/en.json` | 2026-06-03 | MIT | Silent | None | Silent | No | Built-in |
| P03 | LlamaIndex ReAct | `…/agent/react/templates/system_header_template.md` | 2025-05-23 | MIT | Allowed | None | Silent | No | Text |
| P04 | LangChain ReAct (classic) | `libs/langchain/langchain_classic/agents/mrkl/prompt.py` | 2025-10-04 | MIT | Silent | None | Silent | No | Text |
| P05 | Cline | `sdk/packages/shared/src/prompt/system/act.ts` | 2026-09-15 | Apache-2.0 | Silent | None | Human available | No | Built-in |
| P06 | OpenHands (software-agent-sdk) | `…/sdk/context/prompts/sections/static.py` | 2026-11-04 | MIT | Mixed | Try another way | Human available | Yes | Built-in |
| P07 | SWE-agent | `config/default.yaml` | 2025-09-15 | MIT | Silent | None | Silent | No | Built-in |
| P08 | Codex CLI | `codex-rs/models-manager/prompt.md` | 2026-06-23 | Apache-2.0 | Mixed | Retry, Limit stated, Try another way | Human available | Yes | Built-in |
| P09 | Goose | `crates/goose/src/prompts/system.md` + `agents/moim.rs` | 2026-08-10 | Apache-2.0 | Silent | None | Human available | Yes | Built-in |
| P10 | AutoGen AssistantAgent | `…/autogen_agentchat/agents/_assistant_agent.py` | 2025-08-31 | MIT (code) | Silent | None | Silent | No | Built-in |

Every label has its quote in the card. Where the card says Silent, None or No,
no sentence in the saved text supports another value.

## Coverage against the task sheet

| Requirement | At least | Found | Status |
|---|---|---|---|
| A: Allowed | 2 | 1 (P03) | short by one |
| A: Silent | 2 | 7 | met |
| A: Forbidden | 2 | 0 | **not met**; P06 and P08 are Mixed: each tells the agent to keep going and, elsewhere, to stop and ask |
| Call format: plain text (Text or JSON in the reply) | 3 | 3 (P01, P03, P04) | met |
| Call format: built-in tool calling | 3 | 7 | met |

The gap on A is recorded rather than filled: in the ten defaults read, no
prompt forbids giving up outright. The two that come closest (Codex: "Please
keep going until the query is completely resolved"; OpenHands: "don't stop if
the application is not installed") both also instruct the agent to stop and
confirm with the user in another sentence, so by the labelling rules they are
Mixed, not Forbidden. Two further candidates (Gemini CLI, AutoGPT classic) are
being read for a possible swap; see the end of this file.

## What the ten have in common

- **Tool errors reach the model as the raw exception text.** Eight of ten
  pass `str(e)` through, with or without a prefix ("Error executing tool",
  "Observation: …", "[An error occurred during execution.]"). None of the ten
  tells the model in the prompt what to do when a tool fails, except Codex
  and OpenHands.
- **Step caps exist in most frameworks, budgets in almost none.** Defaults
  found: smolagents 20 steps, LlamaIndex 20, LangChain 15, CrewAI 25,
  OpenHands 500, Goose 1000 turns, Cline none, Codex none, AutoGen 1 tool
  iteration, SWE-agent none but a $3 per-instance cost limit. Only SWE-agent
  ships a cost ceiling on by default; none ships a token budget.
- **Loop or repetition detection is rare.** CrewAI forces a final answer
  after five identical tool calls; Cline warns at three identical calls and
  stops at five; OpenHands nudges after three action-error pairs; Goose,
  smolagents, LlamaIndex, LangChain, SWE-agent, Codex and AutoGen have none.
- **Seven of ten use the provider's built-in tool calling.** The three text
  protocols are the two ReAct prompts and smolagents' JSON. Our stand speaks
  JSON in the reply only, so the seven need a native tool-calling path before
  they can run on it.

## Fit with our stand

Criterion 2 of the task sheet (our `analytics(domain, period, cursor)` tool
plugs in without editing the text) holds for all ten: every framework injects
its tool list through a template variable or the API's tool schema. What the
stand lacks is the other direction: an adapter per call format (ReAct text,
JSON, built-in) so the model's reply can be read, and a "prompt from file"
mode that puts a real prompt in place of our three levels. The three prompt
levels of the study (lenient, base, strict) labelled by the same rules are
Allowed, Silent and Forbidden on A.

## Doubts to settle

- P04 LangChain: the pieces live in `langchain_classic`, marked deprecated
  since 0.1.0 with removal planned for 2.0. They are still published in the
  repository and still the default of `initialize_agent`, so they were kept.
- P06 OpenHands: the main repository `OpenHands/OpenHands` is now a frontend
  only; the agent and its prompt live in `OpenHands/software-agent-sdk`, to
  which the main README points. The default is assembled from Python section
  strings, not one file; the saved .txt is that assembly in the framework's
  own order.
- P08 Codex: `prompt.md` is the base prompt for `BaseInstructions::default()`;
  models from the model catalog carry their own instruction template in
  `models.json`, which is what a catalog model actually receives. The base
  prompt was saved as the published default; the card names the alternative.
- P10 AutoGen: the repository is in maintenance mode and points to
  `microsoft/agent-framework`; the prompt is still its published default.
