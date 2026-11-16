# P05 Cline

## Source
- Repository: cline/cline
- File: sdk/packages/shared/src/prompt/system/act.ts (lines 1–36, string value of `CLINE_SYSTEM_PROMPT_ACT_MODE`) and sdk/packages/shared/src/prompt/cline.ts (lines 15–17, string value of `MODE_TAG_INSTRUCTIONS`)
- Permanent link: https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/shared/src/prompt/system/act.ts#L1-L36 and https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/shared/src/prompt/cline.ts#L15-L17
- Commit date: 2026-11-13 (snapshot sha 72b3d714, default branch `main`); last commits that touched the files: act.ts 722b640c281f52e713e2ce88d05af1a3993af8d2 (2026-09-15), cline.ts 0cbfb91ac75c64b7a63535fde6f7f51e670dfa1b (2026-09-25)
- Licence: Apache-2.0
- What was saved: several pieces, in the order the builder emits them: (1) the whole `CLINE_SYSTEM_PROMPT_ACT_MODE` template literal, template variables `{{PLATFORM_NAME}}`, `{{CURRENT_DATE}}`, `{{IDE_NAME}}`, `{{CWD}}`, `{{CLINE_RULES}}`, `{{CLINE_METADATA}}` left as they are; (2) `MODE_TAG_INSTRUCTIONS`, which is what replaces `{{CLINE_RULES}}` in the default (act mode, no user rules). `{{CLINE_METADATA}}` is replaced by an empty string unless the provider is Cline's own (cline.ts L205-210), so nothing was saved for it.

### Which pieces make up the default
The old monolithic `src/core/prompts/system.ts` and the later `src/core/prompts/system-prompt/` directory no longer exist in `main`; the repository was reorganised into `apps/` (VS Code extension, CLI) and `sdk/packages/` (shared runtime). Both the VS Code extension (apps/vscode/src/sdk/cline-session-factory.ts L1049-1061) and the CLI (apps/cli/src/runtime/prompt.ts L14-41) build the system prompt with `buildClineSystemPrompt()` in sdk/packages/shared/src/prompt/cline.ts L152-213:
- Base template: `DEFAULT_CLINE_SYSTEM_PROMPTS.ACT` unless `mode === "yolo"` (cline.ts L181-184); `DEFAULT_CLINE_SYSTEM_PROMPT = CLINE_SYSTEM_PROMPT_ACT_MODE` (sdk/packages/shared/src/prompt/system/index.ts L1-9). The VS Code extension defaults `mode` to `"act"` (cline-session-factory.ts L889).
- `{{CLINE_RULES}}` <- `[rules, MODE_TAG_INSTRUCTIONS, plan-mode block only in plan mode].filter(Boolean).join("\n\n")` (cline.ts L188-198). With no `.clinerules`/user rules, `rules` is `undefined` (`mergeRulesForSystemPrompt` returns `undefined` when both inputs are empty, sdk/packages/core/src/runtime/safety/rules.ts L23-33), so only `MODE_TAG_INSTRUCTIONS` is inserted.
- `{{PLATFORM_NAME}}`, `{{CWD}}`, `{{CURRENT_DATE}}`, `{{IDE_NAME}}` <- runtime values (cline.ts L200-204).
- `{{CLINE_METADATA}}` <- workspace JSON only for the Cline provider, otherwise `""` (cline.ts L205-210).
- Tools are not in the prompt text: they are passed as schemas to the AI SDK (see next section). The YOLO variant (sdk/packages/shared/src/prompt/system/yolo.ts) and the plan-mode blocks (cline.ts L28-53) are non-default and were not saved.

## How the model calls a tool
Built-in: the prompt gives no call syntax; tool definitions (`name`, `description`, `inputSchema`) are converted to an AI SDK `ToolSet` and passed to the provider's function-calling API (sdk/packages/llms/src/providers/ai-sdk.ts L879-899, `toAiSdkTools`). The prompt only says "You can call multiple tools in a single response" (act.ts L22). No in-prompt example exists; code citation:

```ts
function toAiSdkTools(request: GatewayStreamRequest): ToolSet | undefined {
	if (!request.tools?.length) {
		return undefined;
	}
	...
	const tools: ToolSet = {};
	for (const definition of request.tools) {
		tools[definition.name] = {
			description: definition.description,
			inputSchema: jsonSchema(
				normalizeAiSdkToolInputSchema(definition.inputSchema),
			),
		};
	}
	return tools;
}
```
https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/llms/src/providers/ai-sdk.ts#L879-L899

## What the model receives when a tool fails
The raw exception message, wrapped in a JSON object, returned as a tool result flagged `isError`. In sdk/packages/agents/src/agent-runtime.ts L2588-2630 the runtime builds:

```ts
result = {
	output: {
		error: error instanceof Error ? error.message : String(error),
	},
	isError: true,
};
```
(unknown tool: `{ error: \`Unknown tool: ${prepared.toolCall.toolName}\` }`; skipped tool: `{ error: prepared.skipReason }`). The part is forwarded to the provider as an AI SDK `tool-result` content part with `output: part.output, isError: part.isError ?? false` (sdk/packages/llms/src/providers/ai-sdk.ts L838-845).
https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/agents/src/agent-runtime.ts#L2588-L2630
https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/llms/src/providers/ai-sdk.ts#L838-L845

Two follow-up messages can also be appended as `role: "user"` text:
- Loop detection, soft threshold: `` Detected ${n} consecutive identical calls to `${call.name}`; consider trying a different approach. `` (sdk/packages/core/src/runtime/safety/loop-detection.ts L153; appended in session-runtime-orchestrator.ts L1536-1543).
- Mistake limit reached: `Stopped after ${consecutiveMistakes}/${maxConsecutiveMistakes} consecutive mistakes (${reason}) at iteration ${iteration}. Error: ${details} Session state was preserved. Send a new prompt to resume from the latest state.` (sdk/packages/core/src/runtime/safety/mistake-tracker.ts L165-191; appended then the run is aborted, session-runtime-orchestrator.ts L1567-1592).

The legacy `formatResponse.toolError` still exists in apps/vscode/src/core/prompts/responses.ts L27 (`The tool execution failed with the following error:\n<error>\n${error}\n</error>`) but no caller was found outside tests.
https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/apps/vscode/src/core/prompts/responses.ts#L27

## Default limits
| Limit | Value | Link |
|---|---|---|
| Max iterations per run | none (`maxIterations` undefined = loop until the model stops; VS Code passes `undefined`) | https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/agents/src/agent-runtime.ts#L849-L852 ; https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/apps/vscode/src/sdk/cline-session-factory.ts#L1175 |
| Max consecutive mistakes | 6 (`config.execution?.maxConsecutiveMistakes ?? 6`); a turn with failed tool calls and no successful one counts as one mistake; at the limit the run is aborted | https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/core/src/runtime/orchestration/session-runtime-orchestrator.ts#L474 ; https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/core/src/runtime/orchestration/session-runtime-orchestrator.ts#L1415-L1436 |
| Loop detection (identical tool calls) | soft 3 (warning appended), hard 5 (forces the mistake limit, run stops) | https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/core/src/runtime/safety/loop-detection.ts#L113-L116 ; https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/core/src/runtime/orchestration/session-runtime-orchestrator.ts#L1536-L1554 |
| Context window handling (compaction) | trigger at 90% of the model's max input tokens (default 128 000 when unknown), target 70%, preserve last 20 000 tokens, summary up to 8 192 output tokens | https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/sdk/packages/core/src/extensions/context/compaction-shared.ts#L15-L34 |
| Auto-approval max requests | `maxRequests: 20`, marked "Legacy field … Max requests limit feature has been removed" | https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/apps/vscode/src/shared/AutoApprovalSettings.ts#L10-L12 ; https://github.com/cline/cline/blob/72b3d7140553a733242126e51a7c2e87efe75c64/apps/vscode/src/shared/AutoApprovalSettings.ts#L32 |
| Retries / timeouts | none found (searched sdk/packages/agents, sdk/packages/core for retry/timeout defaults on the agent loop) | |
| Token or cost budget | none found | |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Silent | No sentence allows or forbids stopping when the task cannot be done. Closest: "If you need more information, use one of the available tools or ask for clarification instead of making assumptions or lies." (asking, not stopping) |
| B. Tool errors | None | No sentence about tool failures in the saved text. |
| C. Supervision | Human available | "If you need more information, use one of the available tools or ask for clarification instead of making assumptions or lies." Also: "If the mode attribute changes between messages, the user switched modes" |
| D. Budget awareness | No | No mention of cost, tokens, steps or time. ("Do not split independent reads, searches, checks, or edits across separate turns" is about parallelism, not budget.) |
| E. Call format | Built-in | No format instruction in the prompt; tools go through the provider's function-calling API via `toAiSdkTools` (ai-sdk.ts L879-899). |

## Notes
- The brief expected the XML-tag protocol (`<tool_name><param>…</param></tool_name>`) and E = Text. That prompt is gone from `main`: no `src/core/prompts/system-prompt/` directory exists at sha 72b3d714 (checked with `find` over the whole clone); the current default is the short SDK prompt above and the runtime uses native tool calling (`toAiSdkTools`). The saved text contains no XML call syntax, so by labelling rule 3 E must be Built-in. If the study needs the XML-era prompt, it has to be taken from an older tag of cline/cline, which I did not do (not asked).
- `{{CURRENT_DATE}}` is filled with `new Date().toLocaleDateString()` and `{{IDE_NAME}}` with "VS Code" (extension) or "Terminal Shell" (CLI); these are runtime values, left as variables in the .txt.
- The `{{CLINE_RULES}}` slot sits on its own line after the last paragraph, so in the default rendering `MODE_TAG_INSTRUCTIONS` follows directly after "answer it directly without using any tools." In the .txt the two pieces are separated by a blank line for readability; the builder inserts no extra blank line.
- `formatResponse.noToolsUsed`, `tooManyMistakes`, `missingToolParameterError` in apps/vscode/src/core/prompts/responses.ts look like leftovers of the pre-SDK extension; I found no callers in the apps/vscode source and did not use them for labels.
- Commit date in the header is the snapshot date of the shallow clone (HEAD 72b3d714, committed 2026-11-13); the per-file last-touch commits are listed separately.
