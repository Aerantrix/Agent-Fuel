# P03 LlamaIndex ReAct agent

## Source
- Repository: run-llama/llama_index
- File: llama-index-core/llama_index/core/agent/react/templates/system_header_template.md (whole file; it is loaded and exposed as `REACT_CHAT_SYSTEM_HEADER` in llama-index-core/llama_index/core/agent/react/prompts.py lines 6-13)
- Permanent link: https://github.com/run-llama/llama_index/blob/b021ce53b894c376c8b90044e311c63ee5821971/llama-index-core/llama_index/core/agent/react/templates/system_header_template.md
- Commit date: 2025-05-23 (template file); the loader prompts.py was last touched 2026-05-20, https://github.com/run-llama/llama_index/blob/cbc24a58a36421089eaebc7158fc0549acfc8c98/llama-index-core/llama_index/core/agent/react/prompts.py#L6-L22
- Licence: MIT
- What was saved: whole file `system_header_template.md`, byte for byte. Two things happen to it before it reaches the model, both in code, not in the file: (1) `REACT_CHAT_SYSTEM_HEADER` is the file with the single placeholder `{context_prompt}` (line 10) replaced by an empty string (prompts.py L11-13); (2) `ReActChatFormatter.format()` runs `str.format(tool_desc=..., tool_names=...)` on it (formatter.py L74-81), so the doubled braces `{{"input": ...}}` on lines 19 and 26 arrive at the model as single braces. The other variant, `CONTEXT_REACT_CHAT_SYSTEM_HEADER` (prompts.py L15-22), replaces `{context_prompt}` with "Here is some context to help you answer the question and plan:\n{context}" and is used only when a `system_prompt`/context is given (react_agent.py L32-35, L50-67); it is not the default and was not saved.

## How the model calls a tool
Text protocol: the model writes "Thought:", "Action:" and "Action Input:" lines, the Action Input being a JSON object of kwargs; the framework parses it with a regex and JSON extraction (output_parser.py) and feeds the result back as an "Observation:" message. Tools are injected through `{tool_desc}` and `{tool_names}`, rendered by `get_react_tool_descriptions()` as "> Tool Name: ...\nTool Description: ...\nTool Args: <JSON schema>" (https://github.com/run-llama/llama_index/blob/8990dcd08d006855806291df18a4f00f3a80c6a1/llama-index-core/llama_index/core/agent/react/formatter.py#L22-L32 and #L74-L81), so `analytics(domain, period, cursor)` plugs in without editing the prompt.

```
Thought: The current language of the user is: (user's language). I need to use a tool to help me answer the question.
Action: tool name (one of {tool_names}) if using a tool.
Action Input: the input to the tool, in a JSON format representing the kwargs (e.g. {{"input": "hello world", "num_beams": 5}})
```
Copied from https://github.com/run-llama/llama_index/blob/b021ce53b894c376c8b90044e311c63ee5821971/llama-index-core/llama_index/core/agent/react/templates/system_header_template.md#L17-L19

## What the model receives when a tool fails
The framework passes the raw exception text. `BaseWorkflowAgent._call_tool` catches any `Exception` from the tool and wraps `str(e)` into a `ToolOutput` with `is_error=True`:

```
tool_output = ToolOutput(
    content=str(e),
    tool_name=tool.metadata.get_name(),
    raw_input=tool_input,
    raw_output=str(e),
    is_error=True,
    exception=e,
)
```
https://github.com/run-llama/llama_index/blob/f475afd8a9bbda84f252567e045d89d07b5701b3/llama-index-core/llama_index/core/agent/workflow/base_agent.py#L357-L390

The ReAct agent then turns that content into an observation step rendered as `Observation: {content}` (so the model sees `Observation: <exception message>`), https://github.com/run-llama/llama_index/blob/dc944910ffb835fbca0a78dd3b4f66f679a8cbe4/llama-index-core/llama_index/core/agent/workflow/react_agent.py#L264-L291 and https://github.com/run-llama/llama_index/blob/ad2efcdc5b57c30a3d9cd97ac3a750a0a97551ac/llama-index-core/llama_index/core/agent/react/types.py#L42-L50.

Unknown tool name:
```
Tool {ev.tool_name} not found. Please select a tool that is available.
```
https://github.com/run-llama/llama_index/blob/f475afd8a9bbda84f252567e045d89d07b5701b3/llama-index-core/llama_index/core/agent/workflow/base_agent.py#L645-L653

Not a tool failure but related: when the model's reply cannot be parsed, it is re-prompted with "Error while parsing the output: {e}\n\nThe output should be in one of the following formats: ..." (react_agent.py L192-225), and an empty reply gets "FAILURE: Your previous response was empty. ..." (L163-190).

(Note: the stand-alone helper `tools/calling.py` prefixes the message with "Encountered error: " + str(e), https://github.com/run-llama/llama_index/blob/e07b9623e5c6753fd25d50e295b6b97d01864d07/llama-index-core/llama_index/core/tools/calling.py#L46-L54, but the workflow ReActAgent uses `_call_tool` above, which does not add a prefix.)

## Default limits
| Limit | Value | Link |
|---|---|---|
| Max iterations | 20 (`DEFAULT_MAX_ITERATIONS`); counted per LLM step in `parse_agent_output`; on reaching it the run raises `WorkflowRuntimeError("Max iterations of {n} reached! ...")` because `early_stopping_method` defaults to "force"; with "generate" the model gets one last message "You have reached the maximum number of iterations ({max_iterations}). ... Do not attempt to use any more tools." | https://github.com/run-llama/llama_index/blob/f475afd8a9bbda84f252567e045d89d07b5701b3/llama-index-core/llama_index/core/agent/workflow/base_agent.py#L67 , #L138-L142 , #L531-L553 ; prompt text https://github.com/run-llama/llama_index/blob/32ab6648f005c4bf26c79e4695e09b8c08b18ee5/llama-index-core/llama_index/core/agent/workflow/prompts.py#L17-L19 |
| Timeout | None (disabled). The agent passes `timeout=None` to `Workflow.__init__`; the underlying `workflows.Workflow` default of 45.0 s is therefore not used ("`None` disables the timeout"). | https://github.com/run-llama/llama_index/blob/f475afd8a9bbda84f252567e045d89d07b5701b3/llama-index-core/llama_index/core/agent/workflow/base_agent.py#L169 and #L205 ; underlying default https://github.com/run-llama/workflows/blob/f3528e83f35dab5ae2a32615f8394927b3f20622/packages/llama-index-workflows/src/workflows/workflow.py#L100-L119 |
| Retries | No retry count. A malformed or empty model reply is sent back once per step as `retry_messages`; each retry counts toward the 20 iterations. Tool errors are not retried by the framework. | https://github.com/run-llama/llama_index/blob/dc944910ffb835fbca0a78dd3b4f66f679a8cbe4/llama-index-core/llama_index/core/agent/workflow/react_agent.py#L162-L225 ; https://github.com/run-llama/llama_index/blob/f475afd8a9bbda84f252567e045d89d07b5701b3/llama-index-core/llama_index/core/agent/workflow/base_agent.py#L556-L569 |
| Token or cost budget | none found (looked in base_agent.py, react_agent.py, multi_agent_workflow.py, function_agent.py) | |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Allowed | "Thought: I cannot answer the question with the provided tools.\nAnswer: [your answer here (In the same language as the user's question)]" (lines 42-43) |
| B. Tool errors | None | no sentence in the prompt about a tool failing; the only tool-result text is "Observation: tool response" (line 31) |
| C. Supervision | Silent | no sentence saying a human is available or unavailable; the prompt only refers to "the user's language" and "interleaving human and assistant messages" (lines 14, 48), which describe the conversation, not a supervisor |
| D. Budget awareness | No | nothing about cost, tokens, steps or time; the loop instruction is "You should keep repeating the above format till you have enough information to answer the question without using any more tools." (line 34) |
| E. Call format | Text | "Action: tool name (one of {tool_names}) if using a tool.\nAction Input: the input to the tool, in a JSON format representing the kwargs" (lines 18-19); the action input is JSON but the protocol is "Action:" lines, so Text per rule 3 |

## Notes
- The default prompt is a Markdown file, not a Python string as the task description expected: prompts.py only reads `templates/system_header_template.md` and does the `{context_prompt}` substitution. The saved .txt therefore still contains the literal line `{context_prompt}` (line 10); in the default `REACT_CHAT_SYSTEM_HEADER` that line is empty.
- Which agent class: the card describes `llama_index.core.agent.workflow.ReActAgent` (the current workflow-based agent). The task hinted at `agent/react/step.py`; that file no longer exists in the repo (the `agent/react/` directory holds only formatter.py, output_parser.py, prompts.py, templates/, types.py).
- The workflow runtime is a separate package `llama-index-workflows` (repo run-llama/workflows, MIT), pinned by llama-index-core pyproject as `llama-index-workflows>=2.14.0,<3`. The 45 s default timeout lives there but the agent explicitly overrides it with None.
- `max_iterations` can be changed per run (`.run(..., max_iterations=...)`), and `early_stopping_method="generate"` adds a system message (`DEFAULT_EARLY_STOPPING_PROMPT`) that is not part of the default prompt and was not saved.
- `observation_role` defaults to `MessageRole.USER`, so observations (including error text) arrive as user messages (formatter.py L56-63).
- The template file's last commit is 2025-05-23; the main branch head at the time of collection was 99d7433f6f71888951379ccca9294e272442c832 (2026-11-14).
