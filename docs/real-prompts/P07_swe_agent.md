# P07 SWE-agent

## Source
- Repository: SWE-agent/SWE-agent
- File: config/default.yaml (whole file, 69 lines; templates at L6–32, tool settings at L33–66)
- Permanent link: https://github.com/SWE-agent/SWE-agent/blob/a1193dd8fd84eb3e2cd6b0ecbd0bed1cdbb84993/config/default.yaml (last commit touching the file; byte-identical to main at 3ea751c087f32b16e039a2233dd6eefecef325d5 on 2026-07-16, which is the sha used for all code links below)
- Commit date: 2025-09-15
- Licence: MIT
- What was saved: whole file `config/default.yaml`. It is the default config file of the `sweagent run` CLI (`default_config_file: Path = CONFIG_DIR / "default.yaml"`, https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/run/common.py#L194). Pieces inside it, in source order:
  - `system_template` (L6–7) → the **system prompt**: rendered with Jinja and appended as `{"role": "system", ...}` (https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L609-L615).
  - `instance_template` (L8–27) → the **first user message**: rendered with `{{working_dir}}` and `{{problem_statement}}` and appended with `"role": "user"` (https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L748-L760 and #L703-L709).
  - `next_step_template` (L28–30) and `next_step_no_output_template` (L31–32) → wrap every tool observation; with function calling the message is sent with `"role": "tool"` and the tool_call_id (https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L729-L746 and #L706-L709).
  - `tools.bundles` (L41–44), `registry_variables.SUBMIT_REVIEW_MESSAGES` (L47–62, a message shown after the first `submit`), `enable_bash_tool: true` (L64), `parse_function.type: function_calling` (L65–66).
  - The tool list itself is not in the prompt: it is built from the built-in `bash` command plus the bundles and converted to OpenAI function schemas (https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L167-L195, https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/commands.py#L133-L170). A new tool would be added as a bundle, not by editing the templates.

## How the model calls a tool
The provider's built-in tool calling: `parse_function.type: function_calling` (default.yaml L65–66; also the code default `parse_function: ParseFunction = Field(default_factory=FunctionCallingParser)`, https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L112). The tool schemas are passed to `litellm.completion` as `tools`, and exactly one tool call per reply is expected.

```python
        if self.tools.use_function_calling:
            extra_args["tools"] = self.tools.tools
```
https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L708-L709

The built-in bash tool that is always injected (`enable_bash_tool: true`):
```python
BASH_COMMAND = Command(
    name="bash",
    # name="execute_bash",
    signature="<command>",
    # signature="echo '<command>'\n<command>\necho \"root@workspace:${{PWD}} #\n[Command finished with exit code ${{?}}]\"",
    docstring="runs the given command directly in bash",
    arguments=[
        Argument(
            name="command",
            type="string",
            description="The bash command to execute.",
            required=True,
        )
    ],
)
```
https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/commands.py#L210-L224

## What the model receives when a tool fails
Three different cases.

1. A command that runs but fails (non-zero exit): nothing special. The environment is called with `check="ignore"` (unless the private flag `_always_require_zero_exit_code` is set, default False), so the observation is simply the shell output, wrapped in `next_step_template` (`OBSERVATION:\n{{observation}}`), or `next_step_no_output_template` (`Your command ran successfully and did not produce any output.`) when the output is empty. No exit code is appended by SWE-agent.
https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L963-L968 and https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/environment/swe_env.py#L197-L227 (the `check` semantics: "`ignore`: do not extract exit code (more stable)"). The output text itself is produced by the SWE-ReX dependency, not this repo.

2. A command that times out (`execution_timeout`, 30 s): the observation is `command_cancelled_timeout_template`:
```
The command '{{command}}' was cancelled because it took more than {{timeout}} seconds. Please try a different command that completes more quickly. Note: A common source of this error is if the command is interactive or requires user input (it is impossible to receive user input in the current environment, so the command will never complete).
```
https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L112-L118 (used at #L983-L987)

3. A malformed tool call (no call, several calls, unknown tool, bad JSON, missing/extra arguments): the call is not executed; the model is re-queried (up to `max_requeries` = 3) with the parser's `format_error_template`, sent as a `"role": "user"` message after the faulty assistant message:
```
{%- if error_code == "missing" -%}
Your last output did not use any tool calls!
Please make sure your output includes exactly _ONE_ function call!
You must invoke the function directly using the function call format.
You cannot invoke commands with ```, you have to use the function call format.
If you think you have already resolved the issue, please submit your changes by running the `submit` command.
If you think you cannot solve the problem, please run `exit_forfeit` (if available) or `submit`.
Else, please continue with a new tool call!
{%- elif error_code == "multiple" -%}
Your last output included multiple tool calls!
Please make sure your output includes a thought and exactly _ONE_ function call.
{%- elif error_code == "unexpected_arg" -%}
Your action could not be parsed properly: {{exception_message}}.
Make sure your function call doesn't include any extra arguments that are not in the allowed arguments, and only use the allowed commands.
{%- else -%}
Your action could not be parsed properly: {{exception_message}}.
{% endif %}
```
https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/parsing.py#L374-L392 (`FunctionCallingParser.error_message`; `format_error_template` defaults to it, https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L219-L220). `{{exception_message}}` values: `Command '{name}' not found in list of available commands.`, `Tool call arguments are not valid JSON.`, `Required argument(s) missing: ...`, `Unexpected argument(s): ...` (parsing.py #L397-L422). Requery loop: https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L1086-L1124; the user-role error message: #L818-L821. Bash syntax errors use `shell_check_error_template` (#L102-L107). After 3 failed requeries the run ends with `exit_format` and an automatic `submit` (#L1214-L1221).

## Default limits
| Limit | Value | Link |
|---|---|---|
| Maximum steps / iterations | none found (no step cap; the run ends on submit, cost limit, or an error) | looked in sweagent/agent/agents.py and models.py |
| `per_instance_cost_limit` | 3.0 (USD) | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L73-L76 |
| `total_cost_limit` | 0.0 (= disabled) | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L77 |
| `per_instance_call_limit` | 0 (= disabled) | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L78 |
| Limit check (raises `InstanceCostLimitExceededError` / `InstanceCallLimitExceededError`) | after every API call | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L654-L670 |
| API retries (`RetryConfig`) | 20 attempts, random exponential wait 10–120 s | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L55-L63, loop at #L809-L812 |
| Format / blocklist / syntax requeries (`max_requeries`) | 3 | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L158 |
| `execution_timeout` (one command) | 30 s | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L139 |
| `total_execution_timeout` | 1800 s | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L145 |
| `max_consecutive_execution_timeouts` | 3 | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/tools/tools.py#L150 |
| `max_observation_length` | 100 000 characters | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L79 |
| Token budget | none found (context-window overflow ends the run with `exit_context`) | https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/agents.py#L1175-L1179 |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Silent | No sentence in default.yaml about stopping or giving up. (The permission to run `exit_forfeit` is only in the parser's error template in parsing.py, which is not part of the saved file.) |
| B. Tool errors | None | No sentence about failed tools. The only nearby instruction is about the bug being fixed, not the tool: "4. Rerun your reproduce script and confirm that the error is fixed!" |
| C. Supervision | Silent | The instance template is written in a user's voice ("Can you help me implement the necessary changes to the repository ...") but nothing says whether a human is available during the run. |
| D. Budget awareness | No | No mention of cost, tokens, steps or time. Closest sentence, about thinking length only: "Your thinking should be thorough and so it's fine if it's very long." |
| E. Call format | Built-in | default.yaml L65–66: `parse_function:` / `type: function_calling`; code: `extra_args["tools"] = self.tools.tools` (models.py #L708-L709) |

## Notes
- The repository has several configs; `config/default.yaml` is the one `sweagent run` loads when `--config` is not given (common.py #L194). The file header says it was "Formerly called: anthropic_filemap.yaml" and is "heavily inspired by anthropic's computer use demo".
- The saved file also contains `SUBMIT_REVIEW_MESSAGES` (L47–62): a review message the `review_on_submit_m` bundle returns after the first `submit`, with a `{{diff}}` variable. It is not sent at the start but is a default piece, so it is in the .txt as part of the whole file.
- Tool bundles in the default: `tools/registry`, `tools/edit_anthropic` (the `str_replace_editor` tool), `tools/review_on_submit_m` (the `submit` tool), plus the built-in `bash`. `exit_forfeit` lives in `tools/forfeit`, which is NOT in the default bundle list, so the "(if available)" wording in the format error template applies.
- The default.yaml link uses the last commit that touched the file (2025-09-15); the clone at main `3ea751c0` (2026-07-16) has a byte-identical file. Code links use `3ea751c0`.
- The observation text for a failed command comes from the SWE-ReX runtime (external package); not verified here whether it contains any exit-code marker. With `check="ignore"` SWE-agent itself adds none.
- `history_processors: cache_control, last_n_messages: 2` (L67–69) only affects prompt caching, not the prompt text.
