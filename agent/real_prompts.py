"""Run the stand under a real framework's default prompt instead of ours.

Set AGENT_FUEL_REAL_PROMPT to one of the files in docs/real-prompts/ (a
P0N_name.txt saved word for word from the framework's repository). The
adapter for that framework renders the prompt the way the framework does,
with our one tool put where the framework puts its tool list, and reads the
model's replies in the framework's own protocol. Our three prompt levels are
untouched; a real prompt is one more condition beside them.

Three adapters, for the three prompts whose protocol is text in the reply:

    llamaindex   P03  "Thought / Action / Action Input" with a JSON input
    langchain    P04  "Thought / Action / Action Input" with a string input (MRKL)
    smolagents   P01  Action: {"name": ..., "arguments": {...}}, final_answer tool

The other seven prompts use the provider's built-in tool calling and need a
different path to the API; they are not covered here.

Two simplifications, the same for all three and stated in the paper: the
tool's reply and its error reach the model as "Observation: <text>", the
error text being the exception message as in LlamaIndex (LangChain raises by
default; smolagents adds a retry hint, which our design keeps out); and the
prompt goes as the first user message of a chat, since our backends are
chat-shaped, where LangChain's MRKL prompt was written for a completion call.
"""

import json
import re
from pathlib import Path

TOOL_NAME = "analytics"
TOOL_DESCRIPTION = "Analytics metrics for a domain over a period."
TOOL_ARGS = {
    "domain": {"type": "string", "description": "the domain, e.g. example.com"},
    "period": {"type": "string", "description": "the period, e.g. 30d", "default": "30d"},
    "cursor": {"type": "string", "description": "the cursor of the next page, if the result was truncated", "nullable": True},
}


def _first_json(text, start=0):
    """The first JSON object in text at or after start, or None."""
    decoder = json.JSONDecoder()
    i = text.find("{", start)
    while i >= 0:
        try:
            obj, _ = decoder.raw_decode(text, i)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        i = text.find("{", i + 1)
    return None


def _args_from(value):
    """Arguments as a dict: a bare string is taken as the domain."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        s = value.strip().strip("'\"")
        obj = _first_json(s)
        return obj if obj is not None else {"domain": s}
    return {}


class Adapter:
    name = ""
    native = False    # True: tools go to the API as a schema, not in the text
    deviation = None  # set by parse(), like runner.parse_action.deviation

    def messages(self, task):
        """The conversation the run starts with."""
        return [{"role": "user", "content": self.first_message(task)}]

    def __init__(self, path=None):
        # Without a path the adapter can only parse replies, which is all the
        # replay in evaluation/analyse.py needs.
        self.path = Path(path) if path else None
        self.text = self.path.read_text(encoding="utf-8") if path else ""

    def first_message(self, task):
        raise NotImplementedError

    def parse(self, reply):
        raise NotImplementedError

    @staticmethod
    def observation(result):
        return f"Observation: {result}"

    @staticmethod
    def error(exc):
        return f"Observation: {exc}"


class LlamaIndexReAct(Adapter):
    """P03. `str.format` on the template, as ReActChatFormatter does, with
    {context_prompt} empty as in the default header."""
    name = "llamaindex"

    def first_message(self, task):
        schema = {"type": "object", "properties": TOOL_ARGS, "required": ["domain"]}
        tool_desc = (f"> Tool Name: {TOOL_NAME}\nTool Description: {TOOL_DESCRIPTION}\n"
                     f"Tool Args: {json.dumps(schema)}")
        header = self.text.replace("{context_prompt}", "").format(tool_desc=tool_desc, tool_names=TOOL_NAME)
        return header + "\n\n" + task

    _action = re.compile(r"Action:\s*([^\n]+?)\s*\n\s*Action Input:\s*", re.S)

    def parse(self, reply):
        self.deviation = None
        m = self._action.search(reply)
        if not m:
            if "Answer:" not in reply:
                self.deviation = "no_action_no_answer"
            return None
        args = _first_json(reply, m.end())
        if args is None:
            self.deviation = "action_input_not_json"
            args = _args_from(reply[m.end():].splitlines()[0] if reply[m.end():].strip() else "")
        if len(self._action.findall(reply)) > 1:
            self.deviation = "several_calls"
        if reply.lstrip().startswith("```"):
            self.deviation = self.deviation or "code_fence"
        return m.group(1).strip().strip("`"), args


class LangChainMRKL(Adapter):
    """P04. prefix, the tool list as "name: description", the format
    instructions and the suffix joined by blank lines, as ZeroShotAgent
    .create_prompt does. The saved file carries three marker lines of ours."""
    name = "langchain"

    def _pieces(self):
        parts = re.split(r"^=== (PREFIX|FORMAT_INSTRUCTIONS|SUFFIX)[^\n]*===\n", self.text, flags=re.M)
        return {parts[i]: parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}

    def first_message(self, task):
        p = self._pieces()
        tools = f"{TOOL_NAME}: {TOOL_DESCRIPTION}"
        body = "\n\n".join([p["PREFIX"], tools, p["FORMAT_INSTRUCTIONS"].format(tool_names=TOOL_NAME),
                            p["SUFFIX"].format(input=task, agent_scratchpad="")])
        return body

    _action = re.compile(r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)", re.S)

    def parse(self, reply):
        self.deviation = None
        if "Final Answer:" in reply and not self._action.search(reply):
            return None
        m = self._action.search(reply)
        if not m:
            self.deviation = "no_action_no_answer"
            return None
        if "Final Answer:" in reply:
            self.deviation = "action_and_final_answer"
        tool = m.group(1).strip().strip("`'\"")
        raw = m.group(2).strip().split("\nObservation")[0].strip()
        if len(self._action.findall(reply)) > 1:
            self.deviation = "several_calls"
        return tool, _args_from(raw)

    @staticmethod
    def observation(result):
        return f"Observation: {result}\nThought:"

    @staticmethod
    def error(exc):
        return f"Observation: {exc}\nThought:"


class Smolagents(Adapter):
    """P01. The system_prompt value of the YAML, with the Jinja tool loop
    rendered for our one tool and the two empty conditional blocks removed,
    as the framework renders it with no managed agents and no custom
    instructions."""
    name = "smolagents"

    def _system_prompt(self):
        lines = self.text.splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith("system_prompt:")) + 1
        end = next(i for i in range(start, len(lines)) if lines[i] and not lines[i].startswith(" "))
        return "\n".join(l[2:] if l.startswith("  ") else l for l in lines[start:end]).strip("\n")

    def first_message(self, task):
        body = self._system_prompt()
        inputs = {k: {kk: vv for kk, vv in v.items() if kk != "default"} for k, v in TOOL_ARGS.items()}
        tool_line = (f"\n- {TOOL_NAME}: {TOOL_DESCRIPTION}\n    Takes inputs: {inputs}\n"
                     f"    Returns an output of type: object")
        body = re.sub(r"\n\{%- for tool in tools\.values\(\) %\}.*?\{%- endfor %\}", tool_line, body, flags=re.S)
        body = re.sub(r"\n\{%- if managed_agents.*?\{%- endif %\}", "", body, flags=re.S)
        body = re.sub(r"\n\{%- if custom_instructions %\}.*?\{%- endif %\}", "", body, flags=re.S)
        return body + "\n\nTask: " + json.dumps(task)

    def parse(self, reply):
        self.deviation = None
        calls = []
        pos = 0
        while True:
            obj = _first_json(reply, pos)
            if obj is None:
                break
            pos = reply.find("{", pos) + 1
            if "name" in obj:
                calls.append(obj)
                pos = reply.find("}", pos) + 1
        if not calls:
            self.deviation = "no_action"
            return None
        if len(calls) > 1:
            self.deviation = "several_calls"
        call = calls[0]
        if call["name"] == "final_answer":
            return None
        return call["name"], _args_from(call.get("arguments", {}))


# --- built-in tool calling ------------------------------------------------
#
# These frameworks say nothing about a call format in the prompt: the tool
# goes to the provider as a schema and the call comes back as a structured
# block. The runner's native path records each reply as JSON
# {"text": ..., "tool_calls": [{"id", "name", "args"}]} so the trace, the
# replay and the parser below all read the same thing.

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": TOOL_DESCRIPTION,
    "input_schema": {"type": "object", "properties": {k: {kk: vv for kk, vv in v.items() if kk != "nullable"}
                                                      for k, v in TOOL_ARGS.items()},
                     "required": ["domain"]},
}


class NativeAdapter(Adapter):
    native = True

    def system_prompt(self):
        raise NotImplementedError

    def messages(self, task):
        return [{"role": "system", "content": self.system_prompt()},
                {"role": "user", "content": task}]

    def parse(self, reply):
        self.deviation = None
        try:
            r = json.loads(reply)
        except ValueError:
            self.deviation = "no_json"
            return None
        calls = r.get("tool_calls") or []
        if not calls:
            return None
        if len(calls) > 1:
            self.deviation = "several_calls"
        return calls[0]["name"], _args_from(calls[0].get("args", {}))

    @staticmethod
    def observation(result):
        return str(result)

    @staticmethod
    def error(exc):
        return str(exc)


class CodexCLI(NativeAdapter):
    """P08. prompt.md as it is: it has no template variables."""
    name = "codex"

    def system_prompt(self):
        return self.text


class Goose(NativeAdapter):
    """P09. system.md rendered as the framework does with one extension (ours)
    and the default turn-context block from moim.rs (piece 2 of the file)."""
    name = "goose"

    def system_prompt(self):
        main, piece2 = re.split(r"\n\n===== PIECE 2[^\n]*=====\n", self.text, maxsplit=1)
        moim = piece2.replace("{turn_context_tag}", "turn-context").strip("\n")
        out = main.replace("{% if moim_system_prompt_block is defined %}\n{{ moim_system_prompt_block }}\n{% endif %}", moim)
        out = out.replace("{% if include_extensions and not code_execution_mode %}\n", "")
        ext = (f"\n## {TOOL_NAME}\n\n")
        out = re.sub(r"\{% if \(extensions is defined\) and extensions %\}\n(.*?)\{% for extension in extensions %\}.*?\{% endfor %\}\n\n\{% else %\}.*?\{% endif %\}\n\{% endif %\}",
                     lambda m: m.group(1).rstrip("\n") + "\n" + ext, out, flags=re.S)
        return out.strip("\n") + "\n"


class SWEAgent(NativeAdapter):
    """P07. system_template is the system message; instance_template, with
    the task as the problem statement, is the first user message; tool
    output is wrapped in next_step_template."""
    name = "swe-agent"

    def _template(self, key):
        m = re.search(rf"^\s*{key}: \|-\n((?:      [^\n]*\n|\n)+)", self.text, re.M)
        return "\n".join(l[6:] for l in m.group(1).splitlines()).strip("\n")

    def system_prompt(self):
        return self._template("system_template")

    def messages(self, task):
        instance = self._template("instance_template").replace("{{working_dir}}", "/workspace") \
            .replace("{{problem_statement}}", task)
        return [{"role": "system", "content": self.system_prompt()}, {"role": "user", "content": instance}]

    @staticmethod
    def observation(result):
        return f"OBSERVATION:\n{result}"

    @staticmethod
    def error(exc):
        return f"OBSERVATION:\n{exc}"


ADAPTERS = {"P01": Smolagents, "P03": LlamaIndexReAct, "P04": LangChainMRKL,
            "P07": SWEAgent, "P08": CodexCLI, "P09": Goose}


def load(path):
    key = Path(path).name[:3]
    if key not in ADAPTERS:
        raise ValueError(f"no adapter for {path}: the stand runs P01, P03 and P04 (text protocols)")
    return ADAPTERS[key](path)


def label(path):
    """The condition label a run under this prompt is recorded with."""
    return Path(path).stem
