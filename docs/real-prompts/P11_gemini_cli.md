# P11 Gemini CLI

## Source
- Repository: google-gemini/gemini-cli
- File: packages/core/src/prompts/snippets.ts (whole file). The entry point named in the task, packages/core/src/core/prompts.ts, is now a 42-line shim: `getCoreSystemPrompt()` (L23-35) delegates to `PromptProvider.getCoreSystemPrompt()` in packages/core/src/prompts/promptProvider.ts (L47-294), which composes the prompt from the render functions in snippets.ts.
- Permanent link: https://github.com/google-gemini/gemini-cli/blob/f5dc904d21da337a038f215c433b74382ca82bdb/packages/core/src/prompts/snippets.ts
  - shim: https://github.com/google-gemini/gemini-cli/blob/f7b2632939d3c0ecd74be46fbf9bd6e9d3cd794b/packages/core/src/core/prompts.ts#L23-L35
  - composer: https://github.com/google-gemini/gemini-cli/blob/665228e983c611007c4e2d36550e67b34f75055e/packages/core/src/prompts/promptProvider.ts#L47-L294
- Commit date: 2026-09-29 (snippets.ts); prompts.ts 2026-04-17; promptProvider.ts 2026-06-01. Head of `main` at collection time: 4ed06ed0ddc523a6d356a4ad35ddfea331041888 (2026-11-13).
- Licence: Apache-2.0
- What was saved: the whole file snippets.ts, byte for byte (sha1 4f3f6bba5a0eb8bf3ddb49bc56af6d98ca278911). The default prompt is not one string: `getCoreSystemPrompt(options)` (snippets.ts L136-164) interpolates, in this order, `renderPreamble` (L183), `renderCoreMandates` (L198), `renderSubAgents` (L273), `renderAgentSkills` (L314), `renderHookContext` (L336), `renderPlanningWorkflow` (L598, Plan mode only) or `renderPrimaryWorkflows` (L347), `renderTaskTracker` (L578, only if the tracker is enabled), `renderOperationalGuidelines` (L384), `renderInteractiveYoloMode` (L482, YOLO only), `renderSandbox` (L440), `renderGitRepo` (L501); then `renderFinalShell` (L169) appends `renderUserMemory` (L524). Each render function is a template literal with `${...}` branches on runtime flags (interactive or not, approval mode, sandbox, git repo, which tools are enabled). Flattening them into one string would mean choosing branches, i.e. running the code, so the file is saved as is with the template expressions untouched. `getCompressionPrompt` (L898-977) is in the same file but is the history-compression prompt, not the agent prompt.

## How the model calls a tool
Built-in: the prompt says nothing about a call syntax; tool declarations are collected from the tool registry and sent to the Gemini API as `functionDeclarations`, and tool results come back as `functionResponse` parts (the prompt refers to them: "After receiving a `functionResponse`, you MUST ALWAYS execute one of the following two actions", snippets.ts L417).

```
const toolRegistry = this.context.toolRegistry;
const toolDeclarations = toolRegistry.getFunctionDeclarations(modelId);
const tools: Tool[] = [{ functionDeclarations: toolDeclarations }];
this.getChat().setTools(tools);
```
Copied from https://github.com/google-gemini/gemini-cli/blob/bfb26ed80f972b462c5a5f84b39c13aa61b9aa3a/packages/core/src/core/client.ts#L340-L343. The request itself is built in geminiChat.ts with `systemInstruction: this.systemInstruction, tools: this.tools` (https://github.com/google-gemini/gemini-cli/blob/bfb26ed80f972b462c5a5f84b39c13aa61b9aa3a/packages/core/src/core/geminiChat.ts#L1159-L1165). The prompt refers to tools only by name constants imported from tool-names.ts (e.g. `${GREP_TOOL_NAME}`), so `analytics(domain, period, cursor)` registers like any other tool without editing the prompt.

## What the model receives when a tool fails
A `functionResponse` part whose `response` is `{ error: <message> }`. Built by `ToolExecutor.createErrorResponse`:

```
responseParts: [
  {
    functionResponse: {
      id: request.callId,
      name: request.originalRequestName || request.name,
      response: { error: error.message },
    },
  },
],
```
https://github.com/google-gemini/gemini-cli/blob/5e5e9a32df5991fd75ee01c7f9736395f5487685/packages/core/src/scheduler/tool-executor.ts#L625-L649

Two ways in: (1) the tool returned a `ToolResult` with `error` set, then `error.message` is `toolResult.error.message` (L158-176); (2) the tool threw, then the exception is wrapped as `new Error(String(executionError))` with type `UNHANDLED_EXCEPTION`, so the raw exception message is passed (L177-200). A cancelled call gets `response: { error: "[Operation Cancelled] <reason>" }` (L460, L496-510). The prompt text itself does not describe this format.

## Default limits
| Limit | Value | Link |
|---|---|---|
| Max model turns per user prompt | `MAX_TURNS = 100`; `sendMessageStream(..., turns = MAX_TURNS)` and `boundedTurns = Math.min(turns, MAX_TURNS)`; when it is exhausted the stream yields `MaxSessionTurns` | https://github.com/google-gemini/gemini-cli/blob/bfb26ed80f972b462c5a5f84b39c13aa61b9aa3a/packages/core/src/core/client.ts#L86 , #L958 , #L1004 |
| Max session turns | `maxSessionTurns` setting, default `-1` (unlimited); checked at the start of each turn, yields `MaxSessionTurns` when exceeded | https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/config/config.ts#L1258 , #L2035-L2037 ; https://github.com/google-gemini/gemini-cli/blob/bfb26ed80f972b462c5a5f84b39c13aa61b9aa3a/packages/core/src/core/client.ts#L665-L672 ; docs https://github.com/google-gemini/gemini-cli/blob/488d71b8c9fc3700cb454f22c5553a680d4fb288/docs/cli/settings.md#L106 |
| Loop detection | `TOOL_CALL_LOOP_THRESHOLD = 5` identical tool calls, `CONTENT_LOOP_THRESHOLD = 10` repeated content chunks; LLM-based loop check starts after `LLM_CHECK_AFTER_TURNS = 30` turns, every 5-15 turns, confidence threshold 0.9; a detected loop ends the turn (`LoopDetected` event) | https://github.com/google-gemini/gemini-cli/blob/acae7124bdd849e554eaa5e090199a0cf08cd782/packages/core/src/services/loopDetectionService.ts#L29-L65 ; https://github.com/google-gemini/gemini-cli/blob/bfb26ed80f972b462c5a5f84b39c13aa61b9aa3a/packages/core/src/core/client.ts#L791-L795 |
| API retries | `DEFAULT_MAX_ATTEMPTS = 10`, `initialDelayMs: 5000`, `maxDelayMs: 30000`, exponential backoff with jitter | https://github.com/google-gemini/gemini-cli/blob/4d557496887ef1160c256eb7f1200873612cda91/packages/core/src/utils/retry.ts#L20 , #L42-L47 |
| Thinking budget | `DEFAULT_THINKING_MODE = 8192` ("Cap the thinking at 8192 to prevent run-away thinking loops") | https://github.com/google-gemini/gemini-cli/blob/8e372f99fa1bca5f1b0de565b4f0ee2edd3bc475/packages/core/src/config/models.ts#L178-L179 |
| Timeout | none found (looked in client.ts, tool-executor.ts, retry.ts, config.ts for `timeout`) | |
| Token or cost budget | none found as a hard stop; history compression exists (`ChatCompressionService`, client.ts L105-122, L735) but its thresholds were not read | |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Mixed | Keep going: "**Proactiveness:** When executing a Directive, persist through errors and obstacles by diagnosing failures in the execution phase and, if necessary, backtracking to the research or strategy phases to adjust your approach until a successful, verified outcome is achieved." (L259) and "You should only seek user intervention if you have exhausted all possible routes" (L258). May stop: "**Handling Inability:** If unable/unwilling to fulfill a request, state so briefly without excessive justification. Offer alternatives if appropriate." (L409) |
| B. Tool errors | Try another way; Limit stated | "persist through errors and obstacles by diagnosing failures in the execution phase and, if necessary, backtracking to the research or strategy phases to adjust your approach" (L259); "**Strategic Re-evaluation:** If you have attempted to fix a failing implementation more than 3 times without success, you must: 1. Stop and remind yourself of the original task description. 2. List your current assumptions and identify which ones might be wrong. 3. Propose a different architectural approach rather than continuing to patch the current one." (L371-374); "**Confirmation Protocol:** If a tool call is declined or cancelled, respect the decision immediately. Do not re-attempt the action ... Offer an alternative technical path if possible." (L432) |
| C. Supervision | Human available | "**Confirm Ambiguity/Expansion:** Do not take significant actions beyond the clear scope of the request without confirming with the user. If the user implies a change (e.g., reports a bug) without explicitly asking for a fix, **ask for confirmation first**." (L677, interactive branch, the default); "the user will be presented with a confirmation dialogue upon use" (L412) |
| D. Budget awareness | Yes | "## Context Efficiency:\nBe strategic in your use of the available tools to minimize unnecessary context usage" (L221-223); "The agent passes the full history with each subsequent message. The larger context is early in the session, the more expensive each subsequent turn is." (L227); "Your own context window is your most precious resource. Every turn you take adds to the permanent session history." (L290) |
| E. Call format | Built-in | No call syntax in the prompt; tools go to the API as `functionDeclarations` (client.ts L340-343, geminiChat.ts L1159-1165, links above). The prompt only presupposes the API's `functionResponse` parts (L417) |

## Notes
- Two prompt variants exist. `PromptProvider` picks `snippets.ts` when `supportsModernFeatures(model)` is true (Gemini 3 models or a custom model) and `snippets.legacy.ts` otherwise (promptProvider.ts L73-82; models.ts `supportsModernFeatures`, https://github.com/google-gemini/gemini-cli/blob/8e372f99fa1bca5f1b0de565b4f0ee2edd3bc475/packages/core/src/config/models.ts). The default model alias `auto`/`pro` resolves to `gemini-3-pro-preview` when the account has preview access (models.ts L260-283), and `hasAccessToPreviewModel` defaults to true in the provider (promptProvider.ts L77), so the modern file is the default today; the legacy file (https://github.com/google-gemini/gemini-cli/blob/c647533d6c017d032420e032f932953d7df900dc/packages/core/src/prompts/snippets.legacy.ts, 2026-09-08) is used for gemini-2.5 models and was not saved. Its "Final Reminder" ends with "Finally, you are an agent - please keep going until the user's query is completely resolved." (visible in the snapshot below), which would be a Forbidden quote for A, but it is not in the default (modern) prompt.
- Labels are for the default composition: interactive session, approval mode `Default`, outside a sandbox, no plan, no task tracker, no skills, no sub-agents registered. Branches not taken by default and therefore not quoted: non-interactive (`mandateContinueWork`, L717-721: "You are running in a headless/CI environment and cannot interact with the user ... If a tool fails because it requires user interaction, do not retry it indefinitely"), sandbox (L445-477: "AUTOMATICALLY retry the command ... providing the missing permissions"), YOLO (L482-499), Plan mode (L598-661). If the checker wants the headless variant, A/B/C change (C becomes Unattended, B adds a retry limit).
- `renderPreamble` has two sentences for the opening line (interactive vs autonomous, L191-193); `renderSandbox` returns '' when `SANDBOX` is unset (L479), so the default prompt has no sandbox section; `renderGitRepo` renders only inside a git repo (promptProvider.ts L246-250).
- A rendered example published by the authors is the vitest snapshot packages/core/src/core/__snapshots__/prompts.test.ts.snap (https://github.com/google-gemini/gemini-cli/blob/c647533d6c017d032420e032f932953d7df900dc/packages/core/src/core/__snapshots__/prompts.test.ts.snap); the case "should use chatty system prompt for preview model" (L4449) is the modern prompt in Default mode. It is a test fixture (mock config, mock paths), so it was not used as the .txt.
- The default can be replaced wholesale with `GEMINI_SYSTEM_MD` (promptProvider.ts L110-132; docs https://github.com/google-gemini/gemini-cli/blob/93844dfa10f6d71edc09be40dfde205edfbcc939/docs/cli/system-prompt.md), and `GEMINI_WRITE_SYSTEM_MD` dumps the rendered default to a file (L320-335).
- Loaded GEMINI.md content is appended after the prompt by `renderUserMemory` (L524-576); when topic narration is enabled a trailing `[Active Topic: ...]` line is added (promptProvider.ts L276-284). Neither is default text.
- Tool-call throttling via `MAX_TURNS` is per `sendMessageStream` call (one user prompt), not per session; `maxSessionTurns` is the session-wide one and is off by default.
