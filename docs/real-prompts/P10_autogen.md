# P10 AutoGen AssistantAgent (microsoft/autogen)

## Source
- Repository: microsoft/autogen
- File: python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py (lines 734–736, default value of the `system_message` parameter of `AssistantAgent.__init__`)
- Permanent link: https://github.com/microsoft/autogen/blob/31078550445f1e6f09adb40f96ee85d68a963f8c/python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py#L734-L736
- Commit date: 2025-08-31 (sha 31078550445f1e6f09adb40f96ee85d68a963f8c, last commit touching the file; content identical on main as of 2026-11-16)
- Licence: MIT for code (LICENSE-CODE); the repository's top-level LICENSE reported by the GitHub API is CC-BY-4.0 (documentation)
- What was saved: the string value of the `system_message` default — a single one-line Python string literal. There is no other default prompt piece: the agent sends `[SystemMessage(content=system_message)] + model_context messages` (L766-L770, L1086) and the tool list goes through the model client's `tools=` argument, not into the text.

## How the model calls a tool
Provider built-in tool calling: `AssistantAgent._call_llm` collects the tool schemas from the workbench(es) and hands them to the model client's `create`/`create_stream` as `tools=`, so the prompt says nothing about a call format.

```python
        tools = [tool for wb in workbench for tool in await wb.list_tools()] + handoff_tools
        ...
            model_result = await model_client.create(
                llm_messages,
                tools=tools,
                cancellation_token=cancellation_token,
                json_output=output_content_type,
            )
```
https://github.com/microsoft/autogen/blob/31078550445f1e6f09adb40f96ee85d68a963f8c/python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py#L1088-L1114 (`tools=` also at L1093-L1095 for streaming).

## What the model receives when a tool fails
The raw exception text is passed through. `StaticWorkbench.call_tool` catches any exception from the tool and turns `str(e)` into the tool result with `is_error=True`:

```python
        try:
            result_future = asyncio.ensure_future(tool.run_json(arguments, cancellation_token, call_id=call_id))
            cancellation_token.link_future(result_future)
            actual_tool_output = await result_future
            is_error = False
            result_str = tool.return_value_as_string(actual_tool_output)
        except Exception as e:
            result_str = self._format_errors(e)
            is_error = True
        return ToolResult(name=name, result=[TextResultContent(content=result_str)], is_error=is_error)
```
https://github.com/microsoft/autogen/blob/0bd99ee516ccc14f3d5edb33e7d9795363598fe3/python/packages/autogen-core/src/autogen_core/tools/_static_workbench.py#L115-L124 ; `_format_errors` = `f"{str(error)}\n"` per (sub)exception, stripped: L156-L167.

`AssistantAgent._execute_tool_call` wraps that into `FunctionExecutionResult(content=tool_result.to_text(), is_error=tool_result.is_error, ...)` (L1608-L1614) and the agent appends `FunctionExecutionResultMessage(content=exec_results)` to the model context (L1240). Two error texts are produced by the agent itself:
- bad JSON arguments: `f"Error: {e}"` (json.JSONDecodeError) — https://github.com/microsoft/autogen/blob/31078550445f1e6f09adb40f96ee85d68a963f8c/python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py#L1546-L1557
- unknown tool: `f"Error: tool '{tool_call.name}' not found in any workbench"` — same file L1616-L1624

## Default limits
| Limit | Value | Link |
|---|---|---|
| `max_tool_iterations` (model call → tool execution rounds per `run`) | 1 | https://github.com/microsoft/autogen/blob/31078550445f1e6f09adb40f96ee85d68a963f8c/python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py#L739 (loop L1149, break at L1258; docstring L218) |
| Model client retries (`max_retries`) | not set by AutoGen; `max_retries: int | None = None` is forwarded to the `openai` SDK client (SDK default is outside this repository) | https://github.com/microsoft/autogen/blob/e04564390361665325b2df9bf9e696ab72fe6946/python/packages/autogen-ext/src/autogen_ext/models/openai/config/__init__.py#L116-L117 ; https://github.com/microsoft/autogen/blob/f76f92dd8c22af51cc62cce738342bf4fb7e8970/python/packages/autogen-ext/src/autogen_ext/models/openai/_openai_client.py#L131-L134 |
| Request timeout | not set by AutoGen (`timeout: float | None = None`, forwarded to the SDK) | same config file L116 |
| Team termination / max turns | none by default: `termination_condition=None`, `max_turns=None` in `BaseGroupChat.__init__` | https://github.com/microsoft/autogen/blob/98e6bba168c784cc3d8ae9491453241b10f4f5ee/python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/_base_group_chat.py#L73-L74 |
| Opt-in termination conditions available | `TextMentionTermination` (e.g. "TERMINATE"), `MaxMessageTermination`, `TokenUsageTermination`, `TimeoutTermination` etc., all must be passed explicitly | https://github.com/microsoft/autogen/blob/7bdd7f6162f4207338909c8fd181bbe055c6e25d/python/packages/autogen-agentchat/src/autogen_agentchat/conditions/_terminations.py#L62 L111 L235 L358 |
| Token / cost budget | none found by default (only the opt-in `TokenUsageTermination`) | — |
| Tool-call retries | none found (looked in `_assistant_agent.py` and `_static_workbench.py`) | — |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Silent | no sentence about stopping when a task cannot be done ("Reply with TERMINATE when the task has been completed." covers completion only) |
| B. Tool errors | None | no sentence about tool failures |
| C. Supervision | Silent | no mention of a user or human |
| D. Budget awareness | No | no mention of cost, tokens, steps or time |
| E. Call format | Built-in | prompt says nothing about format; code: `tools=tools` in `model_client.create(...)`, `_assistant_agent.py` L1088-L1114 |

## Notes
- Repository status: the README (fetched from main on 2026-11-16) carries an "Archived" badge, says "AutoGen is now archived and no longer maintained by Microsoft", "AutoGen is in maintenance mode", and points new users to microsoft/agent-framework and a migration guide. The repository itself is not GitHub-archived (`archived: false`) and the prompt is still the published default in the code, so it was taken as instructed.
- The default is a parameter default, not a module constant; there is no `DEFAULT_SYSTEM_MESSAGE` name in the file. `system_message=None` disables the system message entirely (L767-L768).
- With the default `max_tool_iterations=1` and `reflect_on_tool_use=False` (default when no `output_content_type`, L845-L846), the tool result (including an error) is returned to the caller as a `ToolCallSummaryMessage` formatted with `tool_call_summary_format="{result}"` (L740); the model sees the error text only on the next `run` via the model context. `{is_error}` is one of the placeholders the summary format accepts (docstring L227).
- Whether `is_error` is forwarded to the provider (e.g. as a flag) was not checked beyond `_assistant_agent.py`; the OpenAI client file was only grepped for `max_retries`/`timeout`.
- Licence doubt: GitHub reports CC-BY-4.0 (top-level LICENSE, docs); code is under LICENSE-CODE (MIT). Both are stated above.
