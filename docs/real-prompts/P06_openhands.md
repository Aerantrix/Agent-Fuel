# P06 OpenHands

## Source
- Repository: OpenHands/software-agent-sdk (the agent code of OpenHands; the main repo All-Hands-AI/OpenHands, now OpenHands/OpenHands, is the frontend only and its README points here: "OpenHands/software-agent-sdk | Python SDK, Agent Server, agents, tools, conversations …", README.md L219)
- File: openhands-sdk/openhands/sdk/context/prompts/sections/static.py (string values of the section `body`/guidance constants, lines 84–451), composed in the order given by `_DEFAULT_STATIC_SECTIONS` in openhands-sdk/openhands/sdk/context/prompts/presets.py L84-104
- Permanent link: https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/context/prompts/sections/static.py and https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/context/prompts/presets.py#L84-L104
- Commit date: 2026-11-15 (snapshot sha 1d4c0249, default branch `main`); last commits that touched the files: static.py 2f2cd2bf7f19ca3bbf9f0c4a95c60f48094302a1 (2026-11-04), presets.py bec71283c15b8e4fce5a20e4758115725d938c59 (2026-10-02)
- Licence: MIT
- What was saved: several pieces. The Jinja file `system_prompt.j2` no longer exists ("Built-in `system_prompt_filename` values are back-compat sentinels (the .j2 files were removed)", openhands-sdk/openhands/sdk/agent/base.py L78-84). The default prompt is now assembled by `create_registry(PromptPreset.DEFAULT).build(ctx).static` (base.py L347-377) from Python section classes "ported verbatim from agent/prompts/system_prompt.j2" (static.py L1). I saved, joined with "\n\n" (the registry separator, registry.py L23, L61-63), every static section whose guard is true with no developer override, in registration order:
  1. `<SOUL>` with the built-in identity `OPENHANDS_SYSTEM_IDENTITY` (static.py L84-91; openhands-sdk/openhands/sdk/llm/utils/openhands_provider.py L16-19; used when no `~/.openhands/SOUL.md` exists, base.py L88-99)
  2. `<ROLE>` (static.py L94-100)
  3. `<MEMORY>` with `_AGENTS_MD_GUIDANCE` (static.py L123-128, L169-176; `memory_enabled` is false when no `agent_context` is set, base.py L399-402)
  4. `<EFFICIENCY>` (L179-189) 5. `<FILE_SYSTEM_GUIDELINES>` (L192-205) 6. `<CODE_QUALITY>` (L208-218) 7. `<VERSION_CONTROL>` (L221-231) 8. `<PULL_REQUESTS>` (L234-243) 9. `<PROBLEM_SOLVING_WORKFLOW>` (L246-264) 10. `<SELF_DOCUMENTATION>` (L267-286)
  11. `<SECURITY>` built-in policy (L289-336; guard true because `security_policy_filename` defaults to the sentinel "security_policy.j2", base.py L227-228)
  12. `<SECURITY_RISK_ASSESSMENT>` with the CLI tiers (L339-391; `Agent` forces `llm_security_analyzer=True`, openhands-sdk/openhands/sdk/agent/agent.py L495-508; `cli_mode` defaults to True, static.py L365-367)
  13. `<EXTERNAL_SERVICES>` (L406-413) 14. `<ENVIRONMENT_SETUP>` (L416-426) 15. `<TROUBLESHOOTING>` (L429-439) 16. `<PROCESS_MANAGEMENT>` (L442-451)
  Not saved because they depend on runtime data, not on a developer override: `ToolGuidanceSection` (text supplied by the loaded tools, L394-403), `ModelSpecificSection` `<IMPORTANT>` (depends on the model family: anthropic_claude, google_gemini, gpt-5, gpt-5-codex, L454-508), `PersonaSection` (only when a persona is set), and the dynamic tier (`<CURRENT_DATETIME>`, `<REPO_CONTEXT>`, `<SKILLS>`, `<CUSTOM_SECRETS>` …, sections/dynamic.py; emitted only when an `agent_context` is configured, base.py L542-544).

## How the model calls a tool
Built-in: the prompt has no call syntax; `Agent._step` passes the tool list to `llm.generate(messages=..., tools=list(self.tools_map.values()), ...)` (agent.py L853-859) and `LLM.completion` converts each tool with `to_openai_tool()` into an OpenAI `ChatCompletionToolParam` for LiteLLM:

```python
        # Convert Tool objects to ChatCompletionToolParam once here
        cc_tools: list[ChatCompletionToolParam] = []
        if tools:
            cc_tools = [
                t.to_openai_tool(
                    add_security_risk_prediction=add_security_risk_prediction,
                )
                for t in tools
            ]
```
https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/llm/llm.py#L1631-L1638
https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/agent/agent.py#L853-L859

## What the model receives when a tool fails
Two paths, both raw error text in a `role="tool"` message:

1. The tool returns an `Observation` with `is_error=True`: the header below is prepended to the observation content (openhands-sdk/openhands/sdk/tool/schema.py L390, L444-457):
```python
    ERROR_MESSAGE_HEADER: ClassVar[str] = "[An error occurred during execution.]\n"
    ...
        # If is_error is true, prepend error message
        if self.is_error:
            llm_content.append(TextContent(text=self.ERROR_MESSAGE_HEADER))
```
https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/tool/schema.py#L444-L457

2. The tool raises: the exception is passed through as text in an `AgentErrorEvent` (agent.py L1629-1640 for `ValueError`; openhands-sdk/openhands/sdk/agent/parallel_executor.py L315-335 for `ValueError` and any other `Exception`):
```python
            err = f"Error executing tool '{tool.name}': {e}"
            logger.warning(err)
            error_event = AgentErrorEvent(
                error=err,
                tool_name=tool.name,
                tool_call_id=action_event.tool_call.id,
                classification=AGENT_OUTCOME,
            )
```
which becomes `Message(role="tool", content=[TextContent(text=self.error)], name=self.tool_name, tool_call_id=self.tool_call_id)` (openhands-sdk/openhands/sdk/event/llm_convertible/observation.py L195-203).
https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/agent/agent.py#L1629-L1640
https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/agent/parallel_executor.py#L315-L335
https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/event/llm_convertible/observation.py#L195-L203

After 3 consecutive action/error pairs on the same tool (threshold `action_error`), the stuck detector sends one nudge as a user message, e.g. `` Your calls to `{tool}` have failed validation {threshold} times without resolving the failing fields. Latest error: {error}. Correct the invalid or missing … `` (openhands-sdk/openhands/sdk/conversation/stuck_detector.py L367-397; sent in openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py L870-883).

## Default limits
| Limit | Value | Link |
|---|---|---|
| Max iterations per run | `max_iteration_per_run: int = 500`; on reaching it the conversation goes to ERROR with "Agent reached maximum iterations limit (500)." | https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/conversation.py#L75 ; https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L2485-L2493 |
| Cost budget per run | `max_budget_per_run: float | None = None` (no cap by default); when set: "Agent reached maximum budget limit (${max}); accumulated cost ${spent}." | https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/conversation.py#L76 ; https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L829-L844 |
| Stuck detection | on by default (`stuck_detection: bool = True`); thresholds action_observation 4, action_error 3, monologue 3, alternating_pattern 6; scans the last 20 events; when stuck the run stops with status STUCK | https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/conversation.py#L77 ; https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/types.py#L150-L161 ; https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/stuck_detector.py#L24 ; https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L870-L891 |
| LLM retries | `num_retries = 5`, `retry_min_wait = 8` s, `retry_max_wait = 64` s, `retry_multiplier = 8.0` | https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/llm/llm.py#L388-L399 |
| LLM timeout | `timeout = 300` s per attempt | https://github.com/OpenHands/software-agent-sdk/blob/1d4c0249668c86d4327af51af1659330f8f0dbfc/openhands-sdk/openhands/sdk/llm/llm.py#L401-L405 |
| Token budget | none found (condenser is optional; context-window-exceeded triggers condensation only if a condenser is configured, agent.py L922-929) | |

## Labels
| Label | Value | Quote |
|---|---|---|
| A. Giving up | Mixed | Forbids stopping in one case: "When user asks you to run an application, don't stop if the application is not installed. Instead, please install the application and run the command again." Tells the agent to hand back to the user in another: "When you run into any major issue while executing a plan from the user, please don't try to directly work around it. Instead, propose a new plan and confirm with the user before proceeding." |
| B. Tool errors | Try another way | "If you've made repeated attempts to solve a problem but tests still fail or the user reports it's still broken: 1. Step back and reflect on 5-7 different possible sources of the problem 2. Assess the likelihood of each possible cause 3. Methodically address the most likely causes, starting with the highest probability" |
| C. Supervision | Human available | "If the repository lacks testing infrastructure and implementing tests would require extensive setup, consult with the user before investing time in building testing infrastructure" ; "If unsure about committing certain files, check for the presence of .gitignore files or ask the user for clarification." |
| D. Budget awareness | Yes | "Each action you take is somewhat expensive. Wherever possible, combine multiple actions into a single action, e.g. combine multiple bash commands into one, using sed and grep to edit/view multiple files at once." |
| E. Call format | Built-in | No format instruction in the prompt; tools are passed as OpenAI function schemas via `to_openai_tool()` (llm.py L1631-1638). |

## Notes
- The brief expected `openhands/agenthub/codeact_agent/prompts/system_prompt.j2` in All-Hands-AI/OpenHands. That path is gone: the main repository is now a TypeScript frontend ("Agent Canvas") with no `openhands/` Python package at all (checked the shallow clone at 519b72b0456a7d0aae438a344e90c29177f30165, 2026-11-16), and its README/AGENTS.md point to OpenHands/software-agent-sdk for agents and prompts. The SDK repo is the authors' own publication, so criterion 1 holds, but it is a different repository than the one named in the brief: please confirm this is acceptable.
- The prompt is no longer a Jinja file but Python string constants (static.py); the saved .txt is my assembly of the default-guarded sections in `_DEFAULT_STATIC_SECTIONS` order, joined with the registry's "\n\n". I extracted the strings with a read-only `ast` parse of static.py, not by importing or running the module. The `<SECURITY_RISK_ASSESSMENT>` block is an f-string in `render()` (static.py L369-390); I substituted `{tiers}` with `_CLI_TIERS` (L345-351) because `cli_mode` defaults to True. Nothing else was edited. The project's own tests pin these bodies "byte-for-byte against the Phase 0 snapshot oracle" of the old template (static.py L4-5).
- Platform refinement: on Windows `_refine()` rewrites "bash" to "powershell" and "terminal" to "execute_powershell" in EFFICIENCY, SECURITY and SECURITY_RISK_ASSESSMENT (static.py L51-63). The saved text is the Linux/macOS form.
- The `<IMPORTANT>` model-specific block is part of what a user with a Claude or Gemini or GPT-5 model actually receives (static.py L462-494) but is not a developer override and was left out of the .txt to keep it model-neutral; say if you want it appended.
- Label A: no sentence permits abandoning the task; "propose a new plan and confirm with the user" is an escalation to the human, which is why I marked Mixed rather than Forbidden. Reasonable to argue for Forbidden or Silent.
- Label B quote is from `<TROUBLESHOOTING>`; it is about repeated failing attempts in general, not specifically about a tool call erroring. Nothing in the saved text mentions tool errors by name.
- Default agent in the SDK is `Agent` (agent.py); `system_prompt_filename` default "system_prompt.j2" selects `PromptPreset.DEFAULT` (base.py L218-219, L83). The PLANNING preset and `system_prompt` inline override are non-default and were not saved.
