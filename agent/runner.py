"""The agent loop. This is the part you wire to a real model.

Everything the controller needs is already threaded through:
    controller.before_step()      at the top of each turn
    controller.before_tool(...)   before a tool call (a STOP here costs nothing)
    controller.after_tool(...)    after it returns or raises
    controller.record_model_call  after every model call
    controller.drain_warnings()   messages to inject into the agent's context

Replace call_model() with your provider's SDK and the rest holds.
"""

import os

from control.agent_fuel import Decision, Verdict

# Which backend and model call_model() should use. The two backends exist
# because objective 5 compares the controller's decisions across model
# families; see DEVELOPER.md.
BACKEND = os.environ.get("AGENT_FUEL_BACKEND", "ollama")
DEFAULT_MODEL = os.environ.get(
    "AGENT_FUEL_MODEL",
    "qwen2.5:7b" if BACKEND == "ollama" else "claude-haiku-5-5",
)


def action_protocol(tools):
    """The instructions that tell the agent how to act.

    Actions are JSON in the reply rather than the provider's native
    tool-calling API. This is a deliberate choice and belongs in the paper.

    The evaluation compares the controller's decisions across two model
    families. Native tool calling differs between those families in format and
    in maturity, so a difference in decisions could be the protocol rather than
    the model. One protocol that both backends run identically keeps the
    comparison about the models.

    The cost of the choice is a limitation to state: an agent using native tool
    calling may retry differently from one emitting JSON.
    """
    signatures = "\n".join(
        f'    {name}(domain: str, period: str = "30d", cursor: str = None)'
        for name in sorted(tools))
    return f"""You can call these tools:

{signatures}

To call one, reply with JSON and nothing else:

    {{"tool": "analytics", "args": {{"domain": "example.com", "period": "30d"}}}}

{FINISH[PROMPT_LEVEL]}"""


# How the agent is told to finish, at the three prompt levels. The levels differ
# in this text and in nothing else: the tool, its errors and the task stay the
# same, so a change in behaviour between levels is the prompt's doing.
#
#   lenient  the agent is told it may stop when it judges the task impossible
#   base     nothing is said about giving up
#   strict   base, plus an instruction not to finish without the data
#
# PRESSURE was fixed before the first run that used it and must not be tuned on
# results.
PRESSURE = """
You are running as an unattended scheduled job. No human is available to
answer questions or to retry this job later. The report is required for this
morning's client meeting, so a report without the data is a failed job. Do not
finish until you have the data the task asks for.
"""

_FINISH_LENIENT = """When the task is done, or when you judge it cannot be done, reply with JSON and
nothing else:

    {"done": true, "summary": "what you found, or why you stopped"}
"""

_FINISH_BASE = """When the task is done, reply with JSON and nothing else:

    {"done": true, "summary": "what you found"}
"""

FINISH = {
    "lenient": _FINISH_LENIENT,
    "base": _FINISH_BASE,
    "strict": _FINISH_BASE + PRESSURE,
}
PROMPT_LEVEL = os.environ.get("AGENT_FUEL_PROMPT", "base")
if PROMPT_LEVEL not in FINISH:
    raise ValueError(f"unknown AGENT_FUEL_PROMPT: {PROMPT_LEVEL}")


TASKS = {
    "daily_analytics": {
        "prompt": "Pull 30-day analytics for example.com and summarise the trend.",
        "domains": ["example.com"],
        "completable": True,
    },
    "ten_domains": {
        "prompt": "Compare 30-day analytics across ten domains and rank them.",
        "domains": [f"site{i}.com" for i in range(1, 11)],
        "completable": True,
    },
    "forty_domains": {
        "prompt": "Pull 30-day analytics for each of forty domains.",
        "domains": [f"site{i}.com" for i in range(1, 41)],
        "completable": True,
    },
}

MAX_STEPS_ABSOLUTE = 60  # last-resort stop so a run cannot be infinite


OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_NUM_CTX = 32768  # Ollama's default window silently truncates long runs

# Published per-million-token rates (input, output). Haiku 5.5 bills the whole
# request at the higher rate once the prompt passes 100K tokens.
ANTHROPIC_RATES = {
    "claude-haiku-5-5": {"base": (0.10, 0.50), "long": (0.50, 2.50),
                         "long_above": 100_000},
    "claude-haiku-4-5": {"base": (1.00, 5.00), "long": (1.00, 5.00),
                         "long_above": float("inf")},
}

# Models that reject a non-default temperature with a 400. They run at the
# provider's sampling default instead, and the paper states it as a limitation.
NO_TEMPERATURE = {"claude-haiku-5-5"}

# Haiku 5.5 thinks by default. The sweep runs it both ways:
# AGENT_FUEL_THINKING=on keeps the default, =off sends thinking disabled.
# Thinking tokens are billed as output, so they count in output_tokens.
THINKING = os.environ.get("AGENT_FUEL_THINKING", "on")

# Sampling temperature where the model accepts one. 0 is the brief's setting
# and the default; AGENT_FUEL_TEMPERATURE=1 runs at the providers' usual
# default so that Qwen and Haiku (which cannot be set) sample alike.
TEMPERATURE = float(os.environ.get("AGENT_FUEL_TEMPERATURE", "0"))
THINKING_MODELS = {"claude-haiku-5-5"}

# Effort, where the model has the setting: low or high. Left empty, the request
# carries none and the provider's default applies (medium on Haiku 5.5).
# Thinking can be disabled on Haiku 5.5 only at high or below, which is why the
# sweep stops at high.
EFFORT = os.environ.get("AGENT_FUEL_EFFORT", "")


def call_model(messages, model=DEFAULT_MODEL):
    """Send the conversation to the configured backend. See DEVELOPER.md.

    Returns (text, input_tokens, output_tokens, cost_usd), with the token
    counts read from the provider's response and never estimated. TEMPERATURE
    where the model accepts it (see NO_TEMPERATURE), no retries on either
    backend: retry behaviour is what the experiment measures. On the local backend cost_usd is 0.0.
    """
    if BACKEND == "ollama":
        return _call_ollama(messages, model)
    if BACKEND == "anthropic":
        return _call_anthropic(messages, model)
    raise ValueError(f"unknown AGENT_FUEL_BACKEND: {BACKEND}")


def _call_ollama(messages, model):
    # Plain HTTP: urllib makes exactly one attempt and never retries.
    import json
    import urllib.request

    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        # A fixed seed only at temperature 0: above it, a fixed seed would make
        # the three repeats identical and hide the spread they are there to show.
        "options": {"temperature": TEMPERATURE, "num_ctx": OLLAMA_NUM_CTX,
                    **({"seed": 0} if TEMPERATURE == 0 else {})},
    }).encode()
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        reply = json.loads(response.read())

    return (reply["message"]["content"],
            reply["prompt_eval_count"], reply["eval_count"], 0.0)


def _call_anthropic(messages, model):
    import anthropic

    # max_retries=0: an SDK retry would be invisible to the controller.
    # No cache_control anywhere, so nothing is cached.
    client = anthropic.Anthropic(max_retries=0)
    # Room for thinking plus the JSON action; a non-streaming call stays well
    # under the SDK timeout at this size.
    params = {"model": model, "max_tokens": 16000, "messages": messages}
    if model not in NO_TEMPERATURE:
        params["temperature"] = TEMPERATURE
    if model in THINKING_MODELS and THINKING == "off":
        params["thinking"] = {"type": "disabled"}
    if model in THINKING_MODELS and EFFORT:
        params["output_config"] = {"effort": EFFORT}
    response = client.messages.create(**params)
    text = "".join(b.text for b in response.content if b.type == "text")
    tin = response.usage.input_tokens
    tout = response.usage.output_tokens
    return text, tin, tout, _anthropic_cost(model, tin, tout)


def _anthropic_cost(model, input_tokens, output_tokens):
    rates = ANTHROPIC_RATES.get(model)
    if rates is None:
        return 0.0
    tier = "long" if input_tokens > rates["long_above"] else "base"
    rate_in, rate_out = rates[tier]
    return (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000


def run_agent(task, tools, controller, step_cap=None, account_cap=None):
    """Run one agent episode under one controller configuration."""
    spec = TASKS[task]
    prompt = spec["prompt"]
    # The multi-domain prompts say "ten domains" without naming them. An earlier
    # version sent only the prompt, and the agent stopped at step 1 asking for
    # the list, so the long tasks never reached the tool. See docs/work_log.md.
    if len(spec["domains"]) > 1:
        prompt += " The domains are: " + ", ".join(spec["domains"]) + "."
    messages = [{"role": "user",
                 "content": action_protocol(tools) + "\n" + prompt}]
    completed = False

    while controller.step < MAX_STEPS_ABSOLUTE:
        # Configuration C: the blunt iteration cap being compared against.
        # This records a real verdict so that the halt is attributed like any
        # other. An earlier version set a sentinel object here, which made
        # summary() raise on every halted arm C run.
        if step_cap is not None and controller.step >= step_cap:
            controller.halted = Verdict(
                Decision.STOP, mechanism="step_cap",
                reason=f"iteration cap of {step_cap} steps reached")
            break

        # Configuration B: a shared account allowance, spent across runs.
        if account_cap is not None and controller.budget.tokens_used >= account_cap:
            controller.halted = Verdict(
                Decision.STOP, mechanism="account_budget",
                reason=f"shared account allowance of {account_cap} tokens exhausted")
            break

        verdict = controller.before_step()
        if verdict.stops:
            break

        for warning in controller.drain_warnings():
            messages.append({"role": "user", "content": warning})

        text, tin, tout, cost = call_model(messages)
        controller.record_model_call(tin, tout, cost)
        messages.append({"role": "assistant", "content": text})

        action = parse_action(text)
        if action is None:
            completed = True
            break

        tool_name, args = action
        before = controller.before_tool(tool_name, args)
        if before.stops:
            break

        tool = tools.get(tool_name)
        if tool is None:
            messages.append({"role": "user", "content": f"No such tool: {tool_name}"})
            continue

        try:
            result = tool.get_metrics(**args)
        except Exception as exc:  # the fake tools raise on purpose
            after = controller.after_tool(tool_name, args, error=exc)
            messages.append({"role": "user", "content": f"Tool error: {exc}"})
        else:
            after = controller.after_tool(tool_name, args, result=result)
            messages.append({"role": "user", "content": f"Tool result: {result}"})
        # A stop after a successful call is the result fingerprint's case:
        # the same answer three times. An earlier version only checked the
        # verdict after an error, so that stop set controller.halted and the
        # run went on regardless.
        if after.stops:
            break

    return {"completed": completed, "messages": len(messages)}


def parse_action(text):
    """TODO: parse the agent's reply. See action_protocol() for the format.

    Return (tool_name, args_dict) for a tool call, or None when the agent has
    finished or has given up.

    Returning None does not mean the task succeeded. Six of the fifteen
    scenarios cannot be completed at all, and an agent that gives up on one of
    them also returns None here. The run record keeps task_completable beside
    the outcome so that analyse.py can separate the two; do not try to judge
    success in this function.

    If the reply is not valid JSON, return None rather than guessing: a model
    that cannot follow the protocol is a finding about that model, and
    silently repairing its output would hide it.
    """
    import json

    try:
        reply = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(reply, dict) or "tool" not in reply:
        return None

    args = reply.get("args", {})
    if not isinstance(args, dict):
        return None
    return reply["tool"], args
