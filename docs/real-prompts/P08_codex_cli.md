# P08 OpenAI Codex CLI

## Source
- Repository: openai/codex
- File: codex-rs/models-manager/prompt.md (whole file, 275 lines). Embedded as `pub const BASE_INSTRUCTIONS: &str = include_str!("../prompt.md");` (https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/models-manager/src/model_info.rs#L16). A byte-identical copy is `codex-rs/protocol/src/prompts/base_instructions/default.md`, embedded as `BASE_INSTRUCTIONS_DEFAULT` and used by `impl Default for BaseInstructions` (https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/protocol/src/models.rs#L1805 and #L1829-L1836). The path named in the brief, `codex-rs/core/prompt.md`, no longer exists on main (GitHub API returns 404).
- Permanent link: https://github.com/openai/codex/blob/2cf2a6a844f1fc2ddd489c8a67fa8bc2f59a6f3d/codex-rs/models-manager/prompt.md (last commit touching the file; identical on main at 75fc67e8f4284a669eebd90ab6bc9ef7697e876e, 2026-11-16, the sha used for all code links)
- Commit date: 2026-06-23
- Licence: Apache-2.0
- What was saved: whole file `prompt.md`. It is sent as the first item of the request input, a `developer`-role message (`BaseInstructionsFragment`, role `"developer"`, https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/context/base_instructions.rs#L42-L48; pushed into the request prefix at https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/client.rs#L1240-L1249). The tool definitions are NOT in this text: they are serialised separately from `ToolSpec` structs (see below), so an extra tool (e.g. an MCP tool) is added without editing the prompt.

## How the model calls a tool
The provider's built-in (Responses API) function calling: tools are serialised as raw JSON `tools` on the request and the model emits `function_call` items; the prompt only says "Emit function calls to run terminal commands and apply patches." (prompt.md L7) and never prescribes a text format.

```rust
            Some(create_tools_raw_json_for_responses_api(&prompt.tools)?.into())
        };
        if !prompt.base_instructions.text.is_empty() {
            let mut instructions = ContextualUserFragment::into(BaseInstructionsFragment(
                prompt.base_instructions.text.clone(),
            ));
```
https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/client.rs#L1238-L1243

The tool specs are `ToolSpec::Function(ResponsesApiTool)` (`#[serde(rename = "function")]`, https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/tools/src/tool_spec.rs#L22-L24; `create_tools_raw_json_for_responses_api` at #L144-L149). The default shell tool is `exec_command`:
```rust
    ToolSpec::Function(ResponsesApiTool {
        name: "exec_command".to_string(),
        description: if options.include_windows_shell_guidance {
            ...
        } else {
            "Runs a command in a PTY, returning output or a session ID for ongoing interaction."
                .to_string()
        },
```
https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/handlers/shell_spec.rs#L75-L98 (registered in `add_shell_tools`, https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/spec_plan.rs#L1289-L1324).

## What the model receives when a tool fails
1. Shell command finishing with a non-zero exit code: the formatted output is returned as the error text of a `function_call_output` with `success: Some(false)`. Format (`format_exec_output_for_model`):
```
Exit code: {exit_code}
Wall time: {duration_seconds} seconds
[Total output lines: {total_lines}]   <- only when truncated
Output:
{aggregated output, truncated by the model's truncation policy}
```
https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/mod.rs#L95-L119. Exit code != 0 → `Err(FunctionCallError::RespondToModel(content))`: https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/events.rs#L393-L410. The error becomes `FunctionCallOutputPayload { body: Text(message), success: Some(false) }`: https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/parallel.rs#L484-L508.

2. Timeout: the output body is prefixed with
```
command timed out after {millis} milliseconds
{aggregated output}
```
https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/mod.rs#L133-L142 (exit code reported as 124, https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/exec.rs#L69). For the unified-exec (PTY) path the header is `Wall time: {s} seconds` / `Process exited with code {exit_code}` (https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/context.rs#L555-L575).

3. Unknown tool name: `unsupported call: {tool_name}` (or `unsupported custom tool call: {tool_name}`), https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/tools/registry.rs#L1231-L1236. Handler errors are `FunctionCallError::RespondToModel(String)` (rendered as the string itself) or `Fatal(String)` (rendered `Fatal error: {0}`), https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/tools/src/function_call_error.rs. Argument parse failures are passed through as the raw error, e.g. `failed to parse tool_search arguments: {err}` (router.rs #L319-L320).

## Default limits
| Limit | Value | Link |
|---|---|---|
| Maximum turns / tool-call iterations | none found (grep for max_turns, MAX_ITERATIONS, max_tool_calls in codex-rs/core/src: no hits) | — |
| `request_max_retries` | 4 (cap 100) | https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/model-provider-info/src/lib.rs#L75 and #L82, #L543-L547 |
| `stream_max_retries` | 5 (cap 100) | https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/model-provider-info/src/lib.rs#L74 and #L80, #L550-L554; used at https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/session/turn.rs#L1979 |
| `stream_idle_timeout_ms` | 300 000 ms | https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/model-provider-info/src/lib.rs#L73, #L557-L562 |
| Shell command timeout (`DEFAULT_EXEC_COMMAND_TIMEOUT_MS`) | 10 000 ms (yield time; exec_command returns a session id for longer commands) | https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/exec.rs#L62 |
| Tool output truncation (fallback model info) | 10 000 bytes | https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/models-manager/src/model_info.rs#L127 |
| Cost budget | none found (no cost limit in core or config schema) | — |
| Token budget | none found as a hard limit; context window of the fallback model 272 000 with `effective_context_window_percent: 95`, auto-compaction configurable via `model_auto_compact_token_limit` | https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/models-manager/src/model_info.rs#L129-L133; https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/config.schema.json#L8921 |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Mixed | Forbids stopping early: "Please keep going until the query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved." (L125) but allows handing back what it could not do: "If there's something that you couldn't do (even with approval) but that the user might want to do (such as verifying changes by running the app), include those instructions succinctly." (L189) and "if you still can't manage it's better to save the user time and present them a correct solution where you call out the formatting in your final message." (L155) |
| B. Tool errors | Retry, Limit stated, Try another way | "If there are issues you can iterate up to 3 times to get formatting right, but if you still can't manage it's better to save the user time ..." (L155); "(If the `rg` command is not found, then use alternatives.)" (L264); "The tool call will fail if it didn't work." (L143) |
| C. Supervision | Human available | "The user is working on the same computer as you, and has access to your work." (L187); "you can request that these function calls be escalated to the user for approval before running" (L7); "hold off on running tests or lint commands until the user is ready ... let the user confirm first." (L162). The text also acknowledges an unattended mode: "When running in the non-interactive approval mode **never**, proactively run tests, lint and do whatever you need to ensure you've completed the task." (L161) |
| D. Budget awareness | Yes | "Do not waste tokens by re-reading files after calling `apply_patch` on them." (L143); "you can iterate up to 3 times to get formatting right" (L155) |
| E. Call format | Built-in | Prompt: "Emit function calls to run terminal commands and apply patches." (L7). Code: `create_tools_raw_json_for_responses_api(&prompt.tools)` (client.rs #L1238), `ToolSpec::Function(ResponsesApiTool { name: "exec_command" ... })` (shell_spec.rs #L75-L76) |

## Notes
- DOUBT on criterion 3 ("what the framework sends when the developer overrides nothing"). On main today, `prompt.md`/`BASE_INSTRUCTIONS` is the base prompt only for (a) `BaseInstructions::default()` and (b) models missing from the catalog (`model_info_from_slug` → `local_model_messages()`, https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/models-manager/src/model_info.rs#L97-L99 and #L151-L156), i.e. local/OSS or unknown models. Catalog models (fetched remotely, with the bundled `codex-rs/models-manager/models.json` as fallback) each carry their own `model_messages.instructions_template`, which becomes the thread's base instructions (`BaseInstructionsProvenance::Model`, https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/core/src/session/session.rs#L845-L863). In the bundled models.json (last commit 126a0ee92ed2c5e73cd8a8f7e37563e8527552d7, 2026-10-26) the lowest-priority (= default, `mark_default_by_picker_visibility`, https://github.com/openai/codex/blob/75fc67e8f4284a669eebd90ab6bc9ef7697e876e/codex-rs/protocol/src/openai_models.rs#L1163-L1176) model is `gpt-6.1-sol`, whose template starts "You are Codex, an agent based on GPT-6. You and the user share one workspace..." (21 769 chars); `gpt-5.5`'s starts "You are Codex, a coding agent based on GPT-5..." (21 459 chars). Link: https://github.com/openai/codex/blob/126a0ee92ed2c5e73cd8a8f7e37563e8527552d7/codex-rs/models-manager/models.json. So for a ChatGPT/API user with a catalog model, the prompt actually sent is the models.json template, not prompt.md. I saved prompt.md as the brief asked; a reviewer may prefer the gpt-6.1-sol template (copies for both slugs are in my scratch folder, not in docs/real-prompts). The model-specific files the brief mentions (`codex-rs/core/gpt_5_codex_prompt.md`, `gpt_5_1_prompt.md`, `gpt_5_2_prompt.md`, `gpt-5.1-codex-max_prompt.md`, `gpt-5.2-codex_prompt.md`) still exist on main but are referenced by no Rust, Bazel or JSON file (grep over the clone: zero hits), so they look stale.
- Other default pieces NOT saved: the harness appends further developer messages after the base instructions (permissions/sandbox text from `codex-rs/prompts/templates/permissions/approval_policy/*.md` and `sandbox_mode/*.md`, `AGENTS.md` content, `<environment_context>`), which depend on the configured approval policy and sandbox mode. They are not in the .txt.
- `prompt.md` mentions tools by name (`update_plan`, `apply_patch`, shell/`rg`) and includes one JSON example of calling `apply_patch` through the shell tool (L132); this is guidance, not a call-format instruction.
- `config.personality = none` strips the `# Personality` section from the instructions template (model_info.rs #L46-L56); the default keeps it. `update_plan` lines are removed from a Model-provenance template when the plan tool is disabled (session/mod.rs #L1729-L1745).
- Permanent link for prompt.md uses the last commit touching it (2cf2a6a8, 2026-06-23); code links use main at 75fc67e8 (2026-11-16, date of the clone).
