# P01 smolagents

## Source
- Repository: huggingface/smolagents
- File: src/smolagents/prompts/toolcalling_agent.yaml (whole file; the default run uses the `system_prompt` key, lines 1–119)
- Permanent link: https://github.com/huggingface/smolagents/blob/48a566404fa6f1ee3e129403e0ebd9fc5ed8e5e0/src/smolagents/prompts/toolcalling_agent.yaml
- Commit date: 2025-07-31 (last commit touching the file; repository main at e1249d373d58db6abc73882ee394f6bb3854c89f, 2026-11-15, has identical content)
- Licence: Apache-2.0
- What was saved: whole file. The YAML has four top-level keys: `system_prompt` (the default system message of `ToolCallingAgent`), `planning` (three templates, used only when `planning_interval` is set; default `None`), `managed_agent` (two templates, used only when the agent is called by another agent), `final_answer` (two templates, used only after `max_steps` is exhausted). `ToolCallingAgent.__init__` loads this file when `prompt_templates` is not given: https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L1241-L1243. The tool list is injected by Jinja (`{%- for tool in tools.values() %} - {{ tool.to_tool_calling_prompt() }}`, lines 92–95) from `Tool.to_tool_calling_prompt()` (`f"{self.name}: {self.description}\n    Takes inputs: {self.inputs}\n    Returns an output of type: {self.output_type}"`, https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/tools.py#L289-L290); `initialize_system_prompt` renders it with `tools`, `managed_agents`, `custom_instructions` (https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L1265-L1274). `custom_instructions` and the team-members block are empty by default.

## How the model calls a tool
The prompt text tells the model to write an `Action:` line followed by a JSON object with `"name"` and `"arguments"` (the runtime additionally passes the tools to the provider's function-calling API, see label E).

```
Action:
{
  "name": "final_answer",
  "arguments": {"answer": "insert your final answer here"}
}
```
Copied from https://github.com/huggingface/smolagents/blob/48a566404fa6f1ee3e129403e0ebd9fc5ed8e5e0/src/smolagents/prompts/toolcalling_agent.yaml#L21-L25

## What the model receives when a tool fails
The exception raised by the tool is caught in `ToolCallingAgent.execute_tool_call` and re-raised as `AgentToolExecutionError` with this message (the raw exception type and text are embedded):

```
Error executing tool '{tool_name}' with arguments {str(arguments)}: {type(e).__name__}: {e}
Please try again or use another tool
```
https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L1490-L1502

For a managed agent the text is `Error executing request to team member '{tool_name}' with arguments {str(arguments)}: {e}\nPlease try again or request to another team member` (same lines, L1493-L1496). Argument validation failures raise `AgentToolCallError(str(e))` (L1476-L1478); an unknown tool name gives `Unknown tool {tool_name}, should be one of: {', '.join(available_tools)}.` (L1464-L1468).

The run loop stores the error on the step (`action_step.error = e`, https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L597-L599) and `ActionStep.to_messages` turns it into a tool-response message the model sees on the next step:

```
Call id: {tool_call_id}
Error:
{error message above}
Now let's retry: take care not to repeat previous errors! If you have retried several times, try a completely different approach.
```
https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/memory.py#L138-L147

## Default limits
| Limit | Value | Link |
|---|---|---|
| Maximum steps | `max_steps: int = 20` (one step = one model call plus its tool calls) | https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L300 |
| After max steps | one extra model call without tools (`provide_final_answer`, templates `final_answer.pre_messages`/`post_messages`); the run ends with state `max_steps_error` | https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L606-L636 |
| Retries | none found as a parameter; a tool/parsing error is logged on the step and the loop continues, each failed step counts against `max_steps` | https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L594-L604 |
| Planning interval | `planning_interval: int | None = None` (no planning steps by default) | https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L305 |
| Parallel tool threads | `max_tool_threads: int | None = None` (ThreadPoolExecutor default) | https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L1238 |
| Timeouts | none found (searched agents.py for `timeout`) | — |
| Token or cost budget | none found (token usage is only recorded per step, `memory_step.token_usage`) | https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L1323 |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Silent | No sentence in `system_prompt` about stopping when the task cannot be done. Nearest text: "To provide the final answer to the task, use an action blob with "name": "final_answer" tool. It is the only way to complete the task, else you will be stuck on a loop." (line 20) and "1. ALWAYS provide a tool call, else you will fail." (line 114). Only the non-default `managed_agent.task` template says "And even if your task resolution is not successful, please return as much context as possible, so that your manager can act upon this feedback." (line 233). |
| B. Tool errors | None | No sentence in `system_prompt` about what to do when a tool fails. "4. Never re-do a tool call that you previously did with the exact same parameters." (line 117) is about repetition, not failure. The retry instruction ("Now let's retry...") is runtime text from memory.py, not in the prompt file. |
| C. Supervision | Silent | No sentence about a human user or supervisor. The conditional team-members block (line 99, only rendered when `managed_agents` is set) says "Since this team member is a real human, be as detailed and verbose as necessary in your task description." which describes the callee, not an available supervisor. |
| D. Budget awareness | No | `system_prompt` only says "This Action/Observation can repeat N times, you should take several steps when needed." (line 6), no cost, token, step or time budget. The non-default planning template `update_plan_post_messages` says "Beware that you have {remaining_steps} steps remaining." (line 195). |
| E. Call format | JSON | "Action:\n{\n  \"name\": \"final_answer\",\n  \"arguments\": {\"answer\": \"insert your final answer here\"}\n}" (lines 21–25). The runtime nevertheless passes the tools to the provider's native tool-calling API: `model.generate(..., tools_to_call_from=self.tools_and_managed_agents)` (https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/agents.py#L1310-L1314) and `completion_kwargs["tools"] = [get_tool_json_schema(tool) ...]` with `tool_choice="required"` (https://github.com/huggingface/smolagents/blob/e1249d373d58db6abc73882ee394f6bb3854c89f/src/smolagents/models.py#L510, #L539-L542); if the response has no native tool calls it falls back to parsing the JSON from the text (`model.parse_tool_calls`, agents.py#L1327-L1331). |

## Notes
- Criterion 2: our `analytics(domain, period, cursor)` tool would be injected through the `{%- for tool in tools.values() %}` loop and through the JSON schema sent to the API; no prompt edit needed.
- Default = `ToolCallingAgent` with no `instructions`, no `managed_agents`, `planning_interval=None`. Under these defaults only the `system_prompt` key is sent at the start of a run; the `planning`, `managed_agent` and `final_answer` keys are saved because they are in the same file, but they are not part of the start-of-run prompt (planning never runs; `final_answer` runs only after `max_steps`).
- Labels A–D were judged on `system_prompt` only; the other keys are noted in the Quote column where relevant.
- The ToolCallingAgent docstring (agents.py L1217) says "This agent uses JSON-like tool calls, using method `model.get_tool_call` to leverage the LLM engine's tool calling capabilities." so the prompt's JSON instruction and the API's native tool calling coexist; E is labelled on the prompt text as the brief requires.
- The task text itself is sent as a separate user message (`TaskStep`), not part of this file.
- `agents.py` was last changed on 2026-05-29 (sha fd871374573ddd7cafa06309452c72b90513cf25); links above use the main sha e1249d37 at which the files were read, content identical.
