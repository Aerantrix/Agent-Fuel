# P12 AutoGPT Classic (original_autogpt, one-shot strategy)

## Source
- Repository: Significant-Gravitas/AutoGPT
- File: classic/original_autogpt/autogpt/agents/prompt_strategies/one_shot.py, lines 47-90 (`OneShotAgentPromptConfiguration.DEFAULT_BODY_TEMPLATE`, `DEFAULT_CHOOSE_ACTION_INSTRUCTION`), 148-158 (message order), 176-196 (`build_system_prompt`), 204-226 (`response_format_instruction`), 228-239 (`_generate_intro_prompt`), 241-256 (`_generate_os_info`); plus the defaults it pulls in: classic/forge/forge/config/ai_profile.py lines 3-10 and classic/forge/forge/components/system/system.py lines 18-84 and 113-116.
- Permanent link: https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/original_autogpt/autogpt/agents/prompt_strategies/one_shot.py#L47-L256
  - https://github.com/Significant-Gravitas/AutoGPT/blob/ef7cfbb8602385685e375f6a7740af223184683a/classic/forge/forge/config/ai_profile.py#L3-L10
  - https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/components/system/system.py#L18-L84
- Commit date: 2026-04-03 (one_shot.py, system.py); 2024-09-20 (ai_profile.py). Default branch `master`.
- Licence: MIT for `classic/` (the repository is dual-licensed: root LICENSE says everything outside `autogpt_platform/` is MIT; the GitHub API reports NOASSERTION; README.md L158 table lists `classic/` as MIT).
- What was saved: several pieces, in source order of one_shot.py and then of the files that fill its placeholders. In the order the model actually sees them the system prompt is: PIECE 6 (intro, with PIECE 8 filled in) + PIECE 7 (OS line, only if local command execution is on) + PIECE 1 (body template, with PIECES 9-13 filling `{constraints}`, `{resources}`, `{best_practices}` and the command list filling `{commands}`) + PIECE 4 ("Your Task") + PIECE 5 (response format); joined with blank lines (one_shot.py L176-200). Then the user message PIECE 3 (`"""{task}"""`), the history, and PIECE 2 as the final user message (L148-156). The task description named `DEFAULT_CONSTRAINTS`, `DEFAULT_RESOURCES`, `DEFAULT_BEST_PRACTICES`: those constants no longer exist; `AIDirectives` defaults to empty lists (ai_directives.py L19-21) and the directives are collected at run time from components via `DirectiveProvider` (agent.py L275-282), chiefly `SystemComponent` (PIECES 9-11). The `{response_format}` placeholder is a TypeScript-style interface generated from `AssistantThoughts` (observations, reasoning, self_criticism, plan) at run time (L117-119, L204-217); it is a schema, not prose, and was left as the placeholder.

## How the model calls a tool
Built-in function calling: the commands are passed to the provider as `functions=commands` (one_shot.py L158; agent.py L358-363 `functions=prompt.functions`) and the parser takes the call from `response.tool_calls` (L314-317); the JSON object the prompt demands carries only the thoughts (`use_tool` is deleted from the JSON schema because "use_tool comes from tool_calls", L207-209).

```
# use_tool comes from tool_calls, so remove from JSON schema
if "use_tool" in response_schema.properties:
    del response_schema.properties["use_tool"]
...
# Always expect tool calls - native tool calling is always enabled
if not response.tool_calls:
    raise InvalidAgentResponseError("Assistant did not use a tool")
assistant_reply_dict["use_tool"] = response.tool_calls[0].function
```
Copied from https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/original_autogpt/autogpt/agents/prompt_strategies/one_shot.py#L207-L209 and #L314-L317. The commands are also listed as text in the prompt (`{commands}`, rendered by `CompletionModelFunction.fmt_line()` as `name: description. Params: (a: type, b?: type)`, https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/llm/providers/schema.py#L139-L144), generated from the registered `Command` objects, so a new command is injected, not hand-written.

## What the model receives when a tool fails
A tool-result message flagged as error, containing the exception message and the exception repr (`ActionErrorResult.reason` and `.error`):

```
ToolResultMessage(
    content=f"{result.reason}\n\n{result.error or ''}".strip(),
    is_error=True,
    tool_call_id=episode.action.raw_message.tool_calls[0].id,
)
```
https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/components/action_history/action_history.py#L249-L254

`reason` is the exception's `message` or `args[0]` and `error` is `repr(exception)` (`ActionErrorResult.from_exception`, https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/models/action.py#L99-L112); `agent.execute()` builds it from any `AgentException` (agent.py L414-417; non-Agent exceptions are first wrapped in `CommandExecutionError(str(e))`, L496-497). So the raw exception text is passed. Other cases:
- without native tool_calls the fallback is a user message `"{tool name} raised an error: ```\n{reason}\n```"` (action_history.py L256-260);
- parallel calls: per-tool `"{name}: {error}"` or, when all fail, the reasons joined with "; " (action_history.py L177-213; agent.py L531-550);
- oversized output: `"Command(s) returned too much output. Do not execute these commands again with the same arguments."` (agent.py L423-428);
- permission denied: `"Permission denied for command '{tool.name}'. Try a different approach."` delivered as `ActionInterruptedByHuman` feedback (agent.py L393-402, L462-470; rendered as "Command not executed. User provided feedback: ..." action_history.py L263-275).
Links: https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/original_autogpt/autogpt/agents/agent.py#L393-L428 . The string "Command ... returned an error" from the task hint is not in this version; the nearest is the log line `logger.warning(f"{tool} raised an error: {e}")` (agent.py L416), which goes to the log, not to the model.

## Default limits
| Limit | Value | Link |
|---|---|---|
| Cycle budget / continuous limit | `continuous_mode = True`, `continuous_limit = 0`; `_get_cycle_budget` returns `math.inf` when the limit is 0, so the loop runs until `finish` or Ctrl+C ("The cycle budget is now only used for Ctrl+C handling graceful shutdown") | https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/original_autogpt/autogpt/app/config.py#L86-L88 ; https://github.com/Significant-Gravitas/AutoGPT/blob/98acc4b3d3d924c1dfa3769a4b125b59d98b1795/classic/original_autogpt/autogpt/app/main.py#L594-L600 , #L683-L684 , #L783-L784 |
| Consecutive unparseable replies | 3, then `AgentTerminated("The agent failed to output valid thoughts 3 times in a row.")` | https://github.com/Significant-Gravitas/AutoGPT/blob/98acc4b3d3d924c1dfa3769a4b125b59d98b1795/classic/original_autogpt/autogpt/app/main.py#L681-L707 |
| LLM API retries | `retries_per_request = 7` (tenacity `stop_after_attempt`, on connection errors / rate limits) | https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/llm/providers/schema.py#L194 ; https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/llm/providers/_openai_base.py#L104-L113 |
| Parse-fix retries inside the provider | `fix_failed_parse_tries = 3`; the model is re-asked with a system message `"ERROR PARSING YOUR RESPONSE:\n\n{parse_errors_fmt}"` | https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/llm/providers/schema.py#L195 ; https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/forge/forge/llm/providers/_openai_base.py#L251-L281 |
| Tool output size | result longer than `send_token_limit // 3` tokens is replaced by the "returned too much output" error | https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/original_autogpt/autogpt/agents/agent.py#L422-L428 |
| Thinking budget | `thinking_budget_tokens = None` (off) | https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/original_autogpt/autogpt/app/config.py#L77-L80 |
| Timeout | none found (looked in agent.py, main.py, config.py) | |
| Cost budget | none found as a limit; main.py L582 only prints the summed `total_cost` | |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Allowed | "If the user refuses this, and there is no other way to achieve your goals, you must terminate to avoid wasting time and energy." (PIECE 9, system.py L29-30); and the always-present `finish` command description "Use this to shut down once you have completed your task, or when there are insurmountable problems that make it impossible for you to finish your task." (PIECE 12, system.py L114-116). Nothing tells the agent to keep going until done; the closest is "Your job is to complete the task ... and terminate when done." (PIECE 4) |
| B. Tool errors | None | no sentence about a failing command. "FIX ROOT CAUSE: When debugging, fix the underlying issue, not symptoms." (PIECE 1) and "If tests fail, the bug is in your implementation" (PIECE 9) are about code bugs, not tool failures |
| C. Supervision | Human available | "Only use ask_user when you truly need clarification that cannot be inferred from the task or context." (PIECE 6); "you must ask the user to do it for you" (PIECE 9) |
| D. Budget awareness | Yes | "You have LIMITED steps. Be efficient:" (PIECE 1); "Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps." (PIECE 11) |
| E. Call format | Built-in | The prompt says "YOU MUST ALWAYS RESPOND WITH A JSON OBJECT OF THE FOLLOWING TYPE:\n{response_format}\n\nYOU MUST ALSO INVOKE A TOOL!" (PIECE 5) and "respond using the JSON schema specified previously" (PIECE 2), but the JSON holds only the thoughts; the tool call itself goes through the provider's tool_calls (code above). Checker may prefer "JSON" if the thoughts object counts; see Notes |

## Notes
- Legacy status: classic/README.md says "AutoGPT Classic was an experimental project ... **This project is unsupported, and dependencies will not be updated.** ... If you want to use AutoGPT, you should use the AutoGPT Platform" (https://github.com/Significant-Gravitas/AutoGPT/blob/e33b1e21052f729b29c8c396cd0a77f4a226d122/classic/README.md); the root README (L162-164) links it as "the original standalone AutoGPT". The code is nevertheless still being edited (one_shot.py 2026-04-03, main.py 2026-06-25) and now has parallel tool calls, a ReWOO strategy and a permission manager.
- `use_functions_api` no longer exists; the comment at one_shot.py L314 says "native tool calling is always enabled". The pre-2024 layout (JSON `command` block in text, `DEFAULT_*` constants in one_shot.py) is gone; if the study wants the historical text-JSON version, it would need an older commit.
- E is the doubtful label: the prompt instructs a JSON reply (thoughts) and a provider tool call at the same time. Labelled Built-in because E asks how the model calls a tool and the tool call is not in the JSON (`use_tool` is removed from the schema and read from `tool_calls`). `use_prefill = True` (L96) additionally prefills the reply with `{\n    "thoughts":` (L217).
- A quote is narrow: the "must terminate" sentence is inside the physical-objects constraint, and the `finish` description reaches the prompt as part of the command list (`{commands}`), i.e. injected text. Both are in the saved .txt (system.py is a default, always-registered component: agent.py L167). If the checker rules that injected command descriptions do not count, the remaining quote is only the physical-objects sentence.
- PIECE 13 was gathered by code search for `def get_resources` / `get_constraints` / `get_best_practices` under classic/ and by reading each hit; it lists what those components yield. Which of them appear in a given run depends on the component registration in agent.py L167-230 (e.g. `web_fetch` was not seen in that list; `platform_blocks` and `skills` yield only when configured, so they contribute nothing by default; `user_interaction` is dropped in `noninteractive_mode`). The numbering ("1. ...") is added by `format_numbered_list` at run time.
- PIECE 7 (OS line) is included only when `code_executor.config.execute_local_commands` is true (agent.py L303-307); its default was not checked.
- `AssistantThoughts` has four fields (observations, reasoning, self_criticism, plan), so `{response_format}` renders roughly `interface AssistantResponse { thoughts: { observations: string; reasoning: string; self_criticism: string; plan: string[]; } }`; this was not rendered (nothing was run) and the placeholder is kept.
- Default LLM: `smart_llm` defaults to `OpenAIModelName.GPT4_TURBO` (config.py L69-71), so the OpenAI provider's retry settings are the ones cited.
