# P02 CrewAI

## Source
- Repository: crewAIInc/crewAI
- File: lib/crewai/src/crewai/translations/en.json (whole file, 102 lines; the default pieces are the JSON string values listed under "What was saved")
- Permanent link: https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/translations/en.json (last commit that changed the file: https://github.com/crewAIInc/crewAI/blob/1357491f0d801abf75850f541c2e5d0525b1ff99/lib/crewai/src/crewai/translations/en.json, identical content, verified by diff)
- Commit date: 2026-06-03 (last change to en.json); repository main read at 758b2c1d527e433750c46a06baa93708057d9d4d, 2026-11-16
- Licence: MIT
- What was saved: whole file. `I18N` loads `translations/en.json` as the default language file (https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/utilities/i18n.py#L42) and `Prompts.task_execution` composes the agent prompt from its `slices` (https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/utilities/prompts.py#L93-L141). Which slices form the default prompt for an agent WITH tools depends on one runtime check, `Agent._supports_native_tool_calling` (https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agent/core.py#L692-L706, used at #L1309-L1322):
  1. **Default path, native function calling** (the default LLM is `DEFAULT_LLM_MODEL = "gpt-6-luna"`, https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/constants.py#L355, served by the OpenAI provider whose `supports_function_calling()` returns `not self.is_o1_model`, https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/llms/providers/openai/completion.py#L3150-L3152; the litellm fallback also defaults to True, llm.py#L2577-L2595). `slices` list = `["role_playing"]` only (prompts.py#L99-L104: the `"tools"` slice is appended only when NOT native; `"native_tools"` is an empty string and is never appended), then `task_slice = "native_task"` (#L112-L113). With `use_system_prompt=True` (default, core.py#L285-L288) the result is a `SystemPromptResult`: **system message = `slices.role_playing`** (en.json line 11) + skill block (empty, no skills by default) + date block (empty, `inject_date=False` by default), **user message = `slices.native_task`** (en.json line 16); `_setup_messages` sends them as `system` and `user` roles (https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agents/agent_executor.py#L536-L548). `{input}` in `native_task` is `task.prompt()`, which is the task description followed by `slices.expected_output` ("This is the expected criteria for your final answer: {expected_output}\nyou MUST return the actual complete content as the final answer, not a summary.", en.json line 22; https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/task.py#L1087-L1089) and, when context is passed, `slices.task_with_context`. The tools themselves are not in the text: they are converted to OpenAI function schemas (`setup_native_tools` -> `convert_tools_to_openai_schema`, https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/utilities/agent_utils.py#L1422-L1437, #L248) and passed as `tools=self._openai_tools` on every LLM call (agent_executor.py#L1756-L1767).
  2. **Fallback path, text (ReAct)**, only when the LLM reports no function-calling support: system message = `slices.role_playing` + `slices.tools` (en.json lines 11–12; `{tools}` and `{tool_names}` filled from `render_text_description_and_args`), user message = `slices.task` (line 9). Runtime additions in this path: `slices.post_tool_reasoning` (line 17) appended as a user message after every tool result (agent_executor.py#L1969-L1974, #L2000-L2005), `slices.format` (line 18) appended to tool error messages, `slices.tools` re-appended to every 3rd tool result (`_remember_format`, tool_usage.py#L111, #L772-L777), `slices.final_answer_format` / `slices.format_without_tools` (lines 19–20) on parser errors (agents/parser.py#L118-L124).
  3. Common to both paths: `errors.force_final_answer` (line 47) is appended as a user message when `max_iter` is reached (see limits). All other keys of en.json (`hierarchical_manager_agent`, `memory`, `reasoning`, `planning`, `tools`, the `lite_agent_*`, `summar*`, `hitl_*`, `conversational_*` slices) belong to optional features and are not sent in a default run.

## How the model calls a tool
Default path: the provider's built-in function calling; the prompt text says nothing about a call format, the tool schemas are passed as `tools=self._openai_tools` and the returned `tool_calls` are executed and answered with `role: "tool"` messages (https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agents/agent_executor.py#L1756-L1774 and #L2010-L2060). Fallback text path: ReAct-style `Thought:/Action:/Action Input:/Observation:` lines, instructed by `slices.tools`:

```
Thought: you should always think about what to do
Action: the action to take, only one name of [{tool_names}], just the name, exactly as it's written.
Action Input: the input to the action, just a simple JSON object, enclosed in curly braces, using " to wrap keys and values.
Observation: the result of the action
```
Copied from https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/translations/en.json#L12 (JSON string value, `\n` rendered as line breaks)

## What the model receives when a tool fails
Default (native) path: the raw exception is stringified and sent back as the content of the `tool` message, with no extra instruction:

```
Error executing tool: {e}
```
https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agents/agent_executor.py#L2376-L2379 (sequential execution) and #L2103-L2106 (parallel execution); the message is appended as a `role: "tool"` message at #L2130-L2136 / #L2172-L2178. An unknown tool name returns the string `Tool not found` (#L2304, #L2396, #L2408). Argument-parsing failures return the result of `parse_tool_call_args` (#L2252-L2262).

Fallback (text) path, `ToolUsage.use`: after `_max_parsing_attempts` (3) failed attempts the model gets `errors.tool_usage_exception` plus `slices.format`:

```
I encountered an error while trying to use the tool. This was the error: {error}.
 Tool {tool} accepts these inputs: {tool_inputs}.
Moving on then. Decide if you need a tool or can provide the final answer. Use one at a time.
To use a tool, use:
Thought: [reasoning]
Action: [name from {tool_names}]
Action Input: [JSON object]

To provide the final answer, use:
Thought: [reasoning]
Final Answer: [complete response]
```
https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/tools/tool_usage.py#L451-L469 (strings from en.json lines 53 and 18). If the executor itself catches the exception it appends `\nObservation: Error executing tool: {e}` to the action text and then `slices.post_tool_reasoning` (agent_executor.py#L1964-L1974). Related runtime texts in en.json: `errors.wrong_tool_name` (line 52, utilities/tool_utils.py#L182, #L346), `errors.task_repeated_usage` (line 49, tool_usage.py#L256, #L512), `errors.tool_arguments_error` (line 51, tool_usage.py#L900-L905). Both paths also append, on the 4th identical call with the same result (`MAX_REPEATED_TOOL_CALLS - 1`), "You have called '{tool_name}' with the same arguments {streak} times in a row and got the same result. Calling it again will not change it: use what you have and give your final answer." (agent_utils.py#L1999-L2050).

## Default limits
| Limit | Value | Link |
|---|---|---|
| Maximum iterations | `max_iter: int = Field(default=25)` | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agents/agent_builder/base_agent.py#L285-L287 |
| After max iterations | `errors.force_final_answer` appended as a user message, one more LLM call, run ends (`check_max_iterations` -> `handle_max_iterations_exceeded`) | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agents/agent_executor.py#L2520-L2531 and https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/utilities/agent_utils.py#L387-L433 |
| Repeated identical tool calls | `MAX_REPEATED_TOOL_CALLS = 5` also forces the final answer | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/utilities/agent_utils.py#L1996, #L2097-L2099 |
| Retries (task level) | `max_retry_limit: int = Field(default=2)` re-runs the whole task on an exception | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agent/core.py#L325-L328, #L932-L934 |
| Retries (tool call, text path) | `_max_parsing_attempts = 3` (2 for `OPENAI_BIGGER_MODELS`) | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/tools/tool_usage.py#L110, #L130-L135 |
| Requests per minute | `max_rpm: int | None = Field(default=None)` | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agents/agent_builder/base_agent.py#L274-L277 |
| Timeout | `max_execution_time: int | None = Field(default=None)` (seconds) | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agent/core.py#L277-L280 |
| Token or cost budget | none found; only `respect_context_window: bool = True` (summarises history when the context window is exceeded, not a budget) | https://github.com/crewAIInc/crewAI/blob/758b2c1d527e433750c46a06baa93708057d9d4d/lib/crewai/src/crewai/agent/core.py#L317-L320 |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Silent | No sentence in `role_playing` ("You are {role}. {backstory}\nYour personal goal is: {goal}") or `native_task` ("\nCurrent Task: {input}") about stopping when the task cannot be done. The text-path `task` slice only says "Begin! This is VERY important to you, use the tools available and give your best Final Answer, your job depends on it!" |
| B. Tool errors | None | No sentence in the default start-of-run text about what to do when a tool fails. Runtime-only, text path, sent after a failure: "I encountered an error while trying to use the tool. This was the error: {error}.\n Tool {tool} accepts these inputs: {tool_inputs}" then "Moving on then." (en.json line 53 + tool_usage.py#L468). |
| C. Supervision | Silent | No sentence about a human. `slices.human_feedback` ("You got human feedback on your work, re-evaluate it and give a new Final Answer when ready.") exists in the file but is used only when `Task.human_input=True`, not by default. |
| D. Budget awareness | No | No mention of cost, tokens, steps or time in `role_playing`, `native_task`, `expected_output`, `tools` or `task`. Only the non-default `planning.create_plan_prompt` says "Hard limit: {max_steps} steps." |
| E. Call format | Built-in | The default prompt text gives no call format; tools go through the provider's function-calling API: `use_native_tool_calling = self._supports_native_tool_calling(raw_tools)` (core.py#L1309) and `answer = get_llm_response(llm=self.llm, messages=list(self.state.messages), ..., tools=self._openai_tools, ...)` (agent_executor.py#L1756-L1767). In the text fallback the value would be Text: "Action: the action to take, only one name of [{tool_names}], just the name, exactly as it's written.\nAction Input: the input to the action, just a simple JSON object, enclosed in curly braces, using \" to wrap keys and values." (en.json line 12). |

## Notes
- Criterion 2: our `analytics(domain, period, cursor)` tool would enter through the OpenAI function schema (`convert_tools_to_openai_schema`) in the default path, or through `{tools}`/`{tool_names}` in `slices.tools` in the text path; no prompt edit needed. `{role}`, `{goal}`, `{backstory}`, `{input}`, `{expected_output}` are developer-supplied agent/task fields that the framework substitutes.
- Doubt: "default" here means a fresh `Agent(role, goal, backstory, tools=[...])` executed by a `Crew`/`Task` with no `llm` set. That resolves to `DEFAULT_LLM_MODEL = "gpt-6-luna"` (constants.py#L355) through the OpenAI provider, so native function calling is on; with a model whose provider reports no function calling (e.g. Azure non-OpenAI models, azure/completion.py#L1311-L1313, or Gemini/Bedrock/Anthropic when `supports_tools` is False) the framework switches to the text path. Both pieces are in the saved file; labels were judged on the native default and the text alternative is quoted where it differs.
- The repository was restructured into a monorepo: the paths named in the task (`src/crewai/...`) now live under `lib/crewai/src/crewai/...`.
- `function_calling_llm` is deprecated (core.py#L294-L302) and not involved in the native path.
- `Agent.use_system_prompt` defaults to `True` in `agent/core.py` (#L285) while the `Prompts` class default is `False` (prompts.py#L83); the agent value is passed explicitly (core.py#L1315), so the default run uses separate system and user messages.
- en.json was last changed on 2026-06-03 (sha 1357491f...). All code links use the main commit 758b2c1d... (2026-11-16) at which every file above was read; line numbers refer to that commit.
