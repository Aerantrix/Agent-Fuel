# P04 LangChain ReAct (MRKL / ZeroShotAgent, `langchain_classic`)

## Source
- Repository: langchain-ai/langchain
- File: libs/langchain/langchain_classic/agents/mrkl/prompt.py (lines 1-15; three string constants PREFIX L1, FORMAT_INSTRUCTIONS L2-11, SUFFIX L12-15)
- Permanent link: https://github.com/langchain-ai/langchain/blob/4d1cfa494ab3040698fcb8164fe860a7ef87f979/libs/langchain/langchain_classic/agents/mrkl/prompt.py#L1-L15
- Commit date: 2025-10-04
- Licence: MIT
- What was saved: several pieces in source order: the string values of PREFIX, FORMAT_INSTRUCTIONS and SUFFIX. The three `=== NAME (...) ===` marker lines in the .txt are mine, not source text. The framework assembles them as `f"{prefix}\n\n{tool_strings}\n\n{format_instructions}\n\n{suffix}"` in `ZeroShotAgent.create_prompt`, https://github.com/langchain-ai/langchain/blob/5a9b1ec2dcdc5132e1529e0b60b7ff795f5efe5b/libs/langchain/langchain_classic/agents/mrkl/base.py#L82-L111, where `tool_strings` is `render_text_description(tools)` ("name(signature) - description", one line per tool, https://github.com/langchain-ai/langchain/blob/6fc21afbc9528b7f072897bd09e5c3d96169b0d1/libs/core/langchain_core/tools/render.py#L13-L38) and `{tool_names}` is the comma-joined tool names. Nothing is hand-written into the prompt, so `analytics(domain, period, cursor)` plugs in unchanged. This is what `initialize_agent(tools, llm)` sends when nothing is overridden: `agent=None` resolves to `AgentType.ZERO_SHOT_REACT_DESCRIPTION` (https://github.com/langchain-ai/langchain/blob/5a9b1ec2dcdc5132e1529e0b60b7ff795f5efe5b/libs/langchain/langchain_classic/agents/initialize.py#L70-L94), i.e. `ZeroShotAgent.from_llm_and_tools` with the three defaults (mrkl/base.py L113-159).

## How the model calls a tool
Text protocol: the model writes "Action:" and "Action Input:" lines (plain text input, not JSON); `MRKLOutputParser.parse` extracts them with a regex (https://github.com/langchain-ai/langchain/blob/0bc831495ca20024373a4c83a7ce8ce444d941a2/libs/langchain/langchain_classic/agents/mrkl/output_parser.py#L31-L66), the LLM call is stopped at "\nObservation:" (agent.py L736-740), and the tool result is appended to the scratchpad as "\nObservation: {observation}\nThought:" (https://github.com/langchain-ai/langchain/blob/fa8be624262c47c4b971b127020da3c20f85caa4/libs/langchain/langchain_classic/agents/agent.py#L742-L751).

```
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
```
Copied from https://github.com/langchain-ai/langchain/blob/4d1cfa494ab3040698fcb8164fe860a7ef87f979/libs/langchain/langchain_classic/agents/mrkl/prompt.py#L6-L8

## What the model receives when a tool fails
By default nothing: the exception propagates and the run aborts. `AgentExecutor._perform_agent_action` calls `tool.run(...)` with no error handling (https://github.com/langchain-ai/langchain/blob/fa8be624262c47c4b971b127020da3c20f85caa4/libs/langchain/langchain_classic/agents/agent.py#L1380-L1404), and `BaseTool.run` re-raises both `ToolException` (when `handle_tool_error` is unset, its default) and any other `BaseException`:

```
except ToolException as e:
    if not self.handle_tool_error:
        error_to_raise = e
    else:
        content = _handle_tool_error(e, flag=self.handle_tool_error)
        status = "error"
except BaseException as e:
    error_to_raise = e

if error_to_raise:
    run_manager.on_tool_error(error_to_raise, tool_call_id=tool_call_id)
    raise error_to_raise
```
https://github.com/langchain-ai/langchain/blob/1dd41b2279ff5e9c5fb0c635accbadb9f6545291/libs/core/langchain_core/tools/base.py#L1122-L1132 (default `handle_tool_error: bool | str | Callable | None` at #L528-L531). Only if the developer sets `handle_tool_error=True` does the model get the raw exception message as the observation (`e.args[0]` or "Tool execution error", #L1314-L1350).

Unknown tool name (not an exception; sent as the observation):
```
{requested_tool_name} is not a valid tool, try one of [{available_tool_names_str}].
```
https://github.com/langchain-ai/langchain/blob/66889e280439e2c2e85376078bc6889c791ea163/libs/langchain/langchain_classic/agents/tools.py#L11-L31 (invoked from agent.py L1405-L1415).

Related, model-format errors: `handle_parsing_errors` defaults to `False`, which raises `ValueError("An output parsing error occurred. ...")`; if set to `True`, the observation sent back is the parser's `observation` ("Invalid Format: Missing 'Action:' after 'Thought:" or "Invalid Format: Missing 'Action Input:' after 'Action:'", output_parser.py L10-15) or "Invalid or incomplete response" (agent.py L1301-1359).

## Default limits
| Limit | Value | Link |
|---|---|---|
| Max iterations | 15 (`AgentExecutor.max_iterations: int | None = 15`); loop condition in `_should_continue` | https://github.com/langchain-ai/langchain/blob/fa8be624262c47c4b971b127020da3c20f85caa4/libs/langchain/langchain_classic/agents/agent.py#L1023-L1027 and #L1235-L1238 |
| Timeout | `max_execution_time: float | None = None` (no wall-clock limit by default) | https://github.com/langchain-ai/langchain/blob/fa8be624262c47c4b971b127020da3c20f85caa4/libs/langchain/langchain_classic/agents/agent.py#L1028-L1031 |
| On limit | `early_stopping_method = "force"`: the run returns the constant "Agent stopped due to iteration limit or time limit." without another LLM call; "generate" makes one last call with the scratchpad plus "I now need to return a final answer based on the previous steps:" | #L1032-L1041 , #L920-L972 , #L1617-L1622 |
| Retries | none found (no retry count in agent.py; a parsing error is either raised or sent back as an observation, and each such step counts as an iteration) | #L1042-L1050 , #L1301-L1359 |
| Token or cost budget | none found (looked in agent.py, mrkl/base.py, initialize.py) | |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Silent | no sentence about stopping or refusing; the only exit is "Thought: I now know the final answer\nFinal Answer: the final answer to the original input question" |
| B. Tool errors | None | no sentence about a failed tool; "Observation: the result of the action" is the only tool-result text |
| C. Supervision | Silent | no mention of a human, user or supervisor; "Answer the following questions as best you can." |
| D. Budget awareness | No | nothing about cost, tokens, steps or time; "... (this Thought/Action/Action Input/Observation can repeat N times)" sets no limit |
| E. Call format | Text | "Action: the action to take, should be one of [{tool_names}]\nAction Input: the input to the action" |

## Notes
- DOUBT, please decide: the brief's alternate rule said to reject LangChain if "the repo no longer ships it (only the Hub does)". The repo does still ship it, but inside `langchain_classic` (the legacy package that `libs/langchain` now installs; the path `libs/langchain/langchain/agents/mrkl/prompt.py` from the task no longer exists). `ZeroShotAgent`, `MRKLChain`, `AgentType` and `initialize_agent` all carry `@deprecated("0.1.0", removal="2.0.0")` with the message "Use `langchain.agents.create_agent` for new applications. ..." (https://github.com/langchain-ai/langchain/blob/5a9b1ec2dcdc5132e1529e0b60b7ff795f5efe5b/libs/langchain/langchain_classic/_api/deprecation.py#L10-L16 ; mrkl/base.py L40-44). The newer `create_react_agent` in langchain_classic/agents/react/agent.py has NO default prompt: `prompt` is a required argument and its docstring points to `hub.pull("hwchase17/react")` (https://github.com/langchain-ai/langchain/blob/751d8957ea8cf40940002862c65b5cf103790840/libs/langchain/langchain_classic/agents/react/agent.py#L17-L72). The v1 `langchain.agents.create_agent` (libs/langchain_v1) uses provider tool calling and ships no ReAct text prompt. I followed the brief literally ("if present in the repo, save it") and accepted; if the checker considers a deprecated package as "not shipped", the alternate (Gemini CLI) still needs to be collected.
- The three pieces are joined with "\n\n" and the tool list is inserted between PREFIX and FORMAT_INSTRUCTIONS; `{input}` and `{agent_scratchpad}` in SUFFIX are filled at run time. The saved .txt does not include the assembled form.
- libs/langchain/langchain_classic/agents/react/ holds `wiki_prompt.py` and `textworld_prompt.py` (few-shot prompts for the docstore ReAct agent, `REACT_DOCSTORE`); they are not the default and were not saved.
- Tool failure behaviour comes from `langchain_core` (libs/core), a different package in the same monorepo; the permanent links above point at its own file.
- master head at collection time: 5838640178981fdd4ddcfbb03577cff4a2b5b750 (2026-11-15).
