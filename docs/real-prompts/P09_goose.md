# P09 Goose (block/goose)

## Source
- Repository: block/goose (the GitHub API now reports the canonical name as `aaif-goose/goose`; `block/goose` URLs redirect there)
- File: crates/goose/src/prompts/system.md (whole file, piece 1) and crates/goose/src/agents/moim.rs lines 8–22 (string `SYSTEM_PROMPT_BLOCK_TEMPLATE`, piece 2)
- Permanent link: https://github.com/block/goose/blob/7200970cb7d965952b585c1045df91cd3e6f9782/crates/goose/src/prompts/system.md
  - piece 2: https://github.com/block/goose/blob/3bff323e5f9666e4006d8333a99fd0d2d2b9286e/crates/goose/src/agents/moim.rs#L8-L22
- Commit date: 2026-08-10 (system.md, sha 7200970c); 2026-10-28 (moim.rs, sha 3bff323e). Both files are byte-identical in the main HEAD checked on 2026-11-16 (bf6e1df335a3e0ace08afb4a4c913b94356010ee).
- Licence: Apache-2.0
- What was saved: several pieces, in source order. Piece 1 = the whole Minijinja template `system.md`, unchanged. Piece 2 = the string value of `SYSTEM_PROMPT_BLOCK_TEMPLATE` from `moim.rs`, which the renderer injects into the `{{ moim_system_prompt_block }}` variable of piece 1 by default (`prompt_manager.rs` L135 calls `moim::system_prompt_block()`, which returns `Some(...)` unless a thread-local SKIP flag is set, `moim.rs` L28–34). The two pieces are separated in the .txt by one marker line that is not part of the source. The `{turn_context_tag}` placeholder in piece 2 is replaced at runtime by `turn-context` (`moim.rs` L32; constant in crates/goose-provider-types/src/conversation.rs L624).
  - Rendering code: https://github.com/block/goose/blob/6ec4e9a2abc0fdb13f8af2676ceaf848a1df716f/crates/goose/src/agents/prompt_manager.rs#L128-L145

## How the model calls a tool
Provider built-in tool calling: Goose converts every extension tool (MCP `Tool` with name, description, input_schema) into the provider's native tool schema and sends it in the request's `tools` field; the prompt only says the tools are "in your tool specification". Example from the OpenAI format (one tool spec entry):

```rust
        result.push(json!({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
                "strict": false,
            }
        }));
```
https://github.com/block/goose/blob/24931603210434464a0021ef400860594fa336f6/crates/goose-provider-types/src/formats/openai.rs#L732-L750 (added to the payload at L1828-L1830). Anthropic equivalent: https://github.com/block/goose/blob/ef8933ebfb06ae75cd1d417274414cc1b910f408/crates/goose-provider-types/src/formats/anthropic.rs#L558-L569 and L996-L1001. The agent passes `tools: &[rmcp::model::Tool]` to the provider stream in https://github.com/block/goose/blob/6ec4e9a2abc0fdb13f8af2676ceaf848a1df716f/crates/goose/src/agents/state_machine/ops_llm.rs#L148-L160.

## What the model receives when a tool fails
A tool call produces `Result<CallToolResult, ErrorData>`; the `Err` is stored unchanged in the `ToolResponse` (https://github.com/block/goose/blob/0bf8b62407201ce11cac7da2582d25eb0fe620f5/crates/goose/src/agents/state_machine/ops_toolcalling.rs#L184-L203) and each provider format renders it as a tool-result message. The raw error (the Display of `rmcp::model::ErrorData`) is passed through with a fixed prefix:

Anthropic format (tool_result block, `is_error: true`):
```rust
                        Err(tool_error) => {
                            content.push(json!({
                                TYPE_FIELD: TOOL_RESULT_TYPE,
                                TOOL_USE_ID_FIELD: tool_response.id,
                                CONTENT_FIELD: format!("Error: {}", tool_error),
                                IS_ERROR_FIELD: true
                            }));
                        }
```
https://github.com/block/goose/blob/ef8933ebfb06ae75cd1d417274414cc1b910f408/crates/goose-provider-types/src/formats/anthropic.rs#L432-L439

OpenAI format (role `tool` message):
```rust
                            // A tool result error is shown as output so the model can interpret the error message
                            output.push(OpenAiMessage {
                                role: "tool".to_string(),
                                content: Some(json!(format!(
                                    "The tool call returned the following error:\n{}",
                                    e
                                ))),
                                tool_call_id: Some(response.id.clone()),
                                ..Default::default()
                            });
```
https://github.com/block/goose/blob/24931603210434464a0021ef400860594fa336f6/crates/goose-provider-types/src/formats/openai.rs#L431-L441

Example of an error text Goose itself produces (unknown tool name): `Tool '{}' not found. Available tools: [{}]` — https://github.com/block/goose/blob/c94a2abef71b7382a9710b8d7c338b007ddaadf3/crates/goose/src/agents/extension_manager/lease.rs#L628-L635. For tool calls the model made to a tool no extension claims, the agent appends `Available tools: [...]` to the result before the next LLM call: https://github.com/block/goose/blob/6ec4e9a2abc0fdb13f8af2676ceaf848a1df716f/crates/goose/src/agents/state_machine/ops_llm.rs#L39-L75.

## Default limits
| Limit | Value | Link |
|---|---|---|
| Maximum turns (assistant turns per user message, `GOOSE_MAX_TURNS`) | 1000 | https://github.com/block/goose/blob/b855a1a13dc3911a815545b9db74b309f185f17d/crates/goose/src/config/base.rs#L1358-L1360 ; used in https://github.com/block/goose/blob/2365bc5e898a38133c373eef2d1357416acd66e2/crates/goose/src/agents/services.rs#L735 |
| What happens at the limit | Assistant message `I've reached the maximum number of actions I can do without user input. Would you like me to continue?` ends the turn | https://github.com/block/goose/blob/0c5b5e2f2e7933fca4de5377d239645dcbe4cbb3/crates/goose-agent/src/max_turns.rs#L16 and L56-L78 |
| Turn-budget notice to the model | `<turn-budget>{turns_taken}/{max_turns} used</turn-budget>` injected into the per-turn `<turn-context>` message once turns_taken*2 >= max_turns | https://github.com/block/goose/blob/3bff323e5f9666e4006d8333a99fd0d2d2b9286e/crates/goose/src/agents/moim.rs#L155-L164 |
| Provider request retries | 3 retries, initial 1000 ms, backoff x2.0, max 30 000 ms | https://github.com/block/goose/blob/ef8933ebfb06ae75cd1d417274414cc1b910f408/crates/goose-provider-types/src/retry.rs#L14-L17 |
| Tool-call retries | none found (looked in agents/state_machine/ops_toolcalling.rs, agents/retry.rs — the latter is recipe "success checks", opt-in) | — |
| Context limit / auto-compaction | compaction at 0.8 of the model context limit (`GOOSE_AUTO_COMPACT_THRESHOLD`), token limit 225 000 (`GOOSE_AUTO_COMPACT_TOKEN_LIMIT`); context limit override `GOOSE_CONTEXT_LIMIT` | https://github.com/block/goose/blob/d2bf0d127318c3cc0b1071bda4c8dd8b149f06b9/crates/goose-context-management/src/lib.rs#L32 ; https://github.com/block/goose/blob/e5858a27fa74c66805b97db626c149071d2cf491/crates/goose/src/context_mgmt/mod.rs#L25-L38 ; https://github.com/block/goose/blob/b855a1a13dc3911a815545b9db74b309f185f17d/crates/goose/src/config/base.rs#L1362 |
| Extension (MCP) call timeout | 300 s (`DEFAULT_EXTENSION_TIMEOUT`, override `GOOSE_DEFAULT_EXTENSION_TIMEOUT`) | https://github.com/block/goose/blob/b855a1a13dc3911a815545b9db74b309f185f17d/crates/goose/src/config/extensions.rs#L10 |
| Cost budget | none found (searched `crates/goose/src` for budget/cost limits; only cost reporting found) | — |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Silent | no sentence in the saved text about stopping when a task cannot be done |
| B. Tool errors | None | no sentence about tool failures |
| C. Supervision | Human available | "No extensions are defined. You should let the user know that they should add extensions." (piece 1); also "use it as a signal for how much autonomous work remains" (piece 2) |
| D. Budget awareness | Yes | "When `<turn-budget>` is present, use it as a signal for how much autonomous work remains. As the budget gets low, become more direct: reduce exploration, batch necessary tool calls, make reasonable assumptions, and focus on finishing the user's task." (piece 2) |
| E. Call format | Built-in | prompt: "Each of these extensions provides tools that are in your tool specification."; code: tools passed as native schema, formats/openai.rs L732-L750, L1828-L1830 |

## Notes
- The repository was renamed: the API returns `full_name: aaif-goose/goose` and the file's `html_url` points at `github.com/aaif-goose/goose`. `block/goose` links still resolve by redirect. The prompt text itself names the author as "AAIF (Agentic AI Foundation)".
- The system.md on main is short (39 lines). It no longer contains the date/time or goose-mode text; `current_date_time`, `goose_mode`, `is_autonomous` are still passed in the template context (`prompt_manager.rs` L29-L37) but are unused by the default template. The current time and working directory are instead sent per turn in a `<turn-context>` user message built by `moim.rs` (`compose_moim`, L113-L133); that message is runtime data, not a default prompt piece, so it was not saved.
- Label C is a judgement call: the only "user" sentence is conditional (when no extensions are loaded). If the checker prefers a stricter reading, C becomes Silent.
- Pieces that exist in code but were NOT saved because they are not sent by default: `# Additional Instructions:` suffix (`prompt_manager.rs` L183-L195) appears only when `.goosehints` files exist, `system_prompt_extras` are set, or goose mode is `chat`; `tiny_model_system.md`, `subagent_system.md` are alternative prompts; the `moim` turn-context user message is skipped for models with context < 32 000 tokens (`MIN_CONTEXT_FOR_MOIM`, moim.rs L6).
- `{turn_context_tag}` in piece 2 is a Rust `str::replace` placeholder, not a Minijinja variable; left as in source.
- The exact Display text of `rmcp::model::ErrorData` (external crate rmcp 3.9.0) was not verified in this repository; the card only states that Goose passes it through with the prefixes shown.
- Clone used for grep: shallow clone of main at bf6e1df335a3e0ace08afb4a4c913b94356010ee (2026-11-16); line numbers above were checked against that checkout and the per-file last-commit shas in the links.
