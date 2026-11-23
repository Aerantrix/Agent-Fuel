"""Local console for the Agent Fuel experiment: the dashboard, a Run view, Start and Stop.

    ~/.venvs/agent-fuel/bin/python console/server.py     then open http://127.0.0.1:8790

or double-click "Agent Fuel.command". One page, dashboard.html, with two
modes: Data (the frozen database and the computed controls) and Run (a
launch with its exact worker command shown, the run step by step as it
happens, and the result in the same tables).

Runs started from the console never touch the frozen database
console/data/runs.jsonl: they are written to console/data/console/ with a
suffix on their id, shown on the page beside the frozen records, and folded
into the database only by hand with console/merge_runs.py.

Listens on 127.0.0.1 only. The API key never leaves this machine: it is read
from ~/.config/agent-fuel/anthropic_key and handed to the worker process in
its environment, and never sent to the page.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONSOLE = DATA / "console"  # runs started from this page; separate from the frozen database
REPO = ROOT.parent  # the Agent Fuel repository this folder lives in
PYTHON = sys.executable  # the environment that runs this server also runs the worker
PROMPTS = REPO / "docs" / "real-prompts"


def ollama_binary():
    """Ollama from the installer (on PATH) or a manual install in ~/.local/ollama."""
    for candidate in (shutil.which("ollama"), HOME / ".local" / "ollama" / "ollama",
                      Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


KEYFILE = HOME / ".config" / "agent-fuel" / "anthropic_key"
PORT = int(os.environ.get("AGENT_FUEL_CONSOLE_PORT", "8790"))

CONFIGS = {"qwen": "ollama", "haiku-think-low": "anthropic", "haiku-think-high": "anthropic",
           "haiku-nothink-low": "anthropic", "haiku-nothink-high": "anthropic"}
ARMS = "ABCDEFG"
CONDITIONS = ("lenient", "base", "strict")

DATA.mkdir(exist_ok=True)
CONSOLE.mkdir(exist_ok=True)
lock = threading.Lock()
job = {"proc": None, "queue": [], "params": None, "stopped": False, "suffix": ""}
console_log = deque(maxlen=400)


def say(line):
    console_log.append(line.rstrip("\n"))


def ollama_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1).read()
        return True
    except Exception:
        return False


def ensure_ollama():
    if ollama_up():
        return True
    say("starting Ollama…")
    binary = ollama_binary()
    if not binary:
        say("Ollama is not installed")
        return False
    detached = {"creationflags": 0x00000008} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **detached)
    for _ in range(30):
        time.sleep(0.5)
        if ollama_up():
            return True
    return False


def read_key():
    try:
        return KEYFILE.read_text().strip()
    except OSError:
        return ""


def real_prompts():
    """The framework prompt files the stand can run (those with an adapter)."""
    return sorted(p.name for p in PROMPTS.glob("P0[1-9]_*.txt"))


def worker_cmd(config, p, suffix, display=False):
    """The worker command for one configuration. The same function builds the
    command that runs and the command the page shows, so they cannot differ."""
    py = "python" if display else PYTHON
    root = "console" if display else str(ROOT)
    data = "console/data/console" if display else str(CONSOLE)
    cmd = [py, "-u", f"{root}/worker.py", "--repo", "." if display else str(REPO), "--data", data,
           "--config", config, "--scenarios", ",".join(map(str, p["scenarios"])),
           "--arms", ",".join(p["arms"]), "--repeats", str(p["repeats"]),
           "--max-cost", str(p["max_cost"]), "--condition", p["condition"],
           "--temperature", str(p["temperature"])]
    if p.get("real_prompt"):
        cmd += ["--real-prompt", f"docs/real-prompts/{p['real_prompt']}" if display else str(PROMPTS / p["real_prompt"])]
    if p.get("error_hint"):
        cmd.append("--error-hint")
    if suffix:
        cmd.append(f"--id-suffix={suffix}")  # "=": the value starts with a dash
    return cmd


def launch_next():
    """Start the next configuration in the queue. Called with the lock held."""
    if job["stopped"] or not job["queue"]:
        job["proc"] = None
        return
    config = job["queue"].pop(0)
    p = job["params"]
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    if CONFIGS[config] == "anthropic":
        env["ANTHROPIC_API_KEY"] = read_key()
    elif not ensure_ollama():
        say("Ollama did not start, skipping this model")
        return launch_next()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = worker_cmd(config, p, job["suffix"])
    proc = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1,
                            encoding="utf-8", errors="replace")
    job["proc"] = proc
    threading.Thread(target=pump, args=(proc,), daemon=True).start()


def pump(proc):
    for line in proc.stdout:
        say(line)
    proc.wait()
    # A worker stopped on Windows cannot write its own final status.
    now = load_json(CONSOLE / "now.json", {})
    if now.get("active"):
        now.update(active=False, doing="Stopped")
        (CONSOLE / "now.json").write_text(json.dumps(now, ensure_ascii=False), encoding="utf-8")
    live = load_json(CONSOLE / "live.json", {})
    if live.get("active"):
        live.update(active=False, done=True)
        (CONSOLE / "live.json").write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
    with lock:
        if job["proc"] is proc:
            launch_next()


def read_jsonl(path):
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
    except FileNotFoundError:
        return


def load_runs():
    """The frozen database, the computed controls where no live run of the cell
    exists, and the runs started from this console, flagged."""
    runs = {}
    for doc in read_jsonl(DATA / "runs.jsonl"):
        runs[doc["id"]] = doc  # a re-run replaces the older record
    live = {(r["model"], r.get("condition"), str(r.get("temperature")), r["scenario_id"], r["arm"], r.get("repeat"))
            for r in runs.values()}
    for doc in read_jsonl(DATA / "computed.jsonl"):
        key = (doc["model"], doc.get("condition"), str(doc.get("temperature")), doc["scenario_id"], doc["arm"], doc.get("repeat"))
        if key not in live and doc["id"] not in runs:
            runs[doc["id"]] = doc
    for doc in read_jsonl(CONSOLE / "runs.jsonl"):
        doc["console"] = True
        runs[doc["id"]] = doc
    return list(runs.values())


def runs_version():
    """Changes whenever a run file changes, so the page reloads the runs only then."""
    parts = []
    for p in (DATA / "runs.jsonl", DATA / "computed.jsonl", CONSOLE / "runs.jsonl"):
        try:
            st = p.stat()
            parts.append(f"{int(st.st_mtime)}:{st.st_size}")
        except FileNotFoundError:
            parts.append("-")
    return "|".join(parts)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            pass  # the page navigated away mid-reply; nothing to do

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, (ROOT / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/state":
            with lock:
                running = job["proc"] is not None
                queued = list(job["queue"])
            return self.send(200, {
                "now": load_json(CONSOLE / "now.json", {"active": False, "doing": "No runs in progress"}),
                "running": running, "queued": queued, "log": list(console_log)[-120:],
                "has_key": bool(read_key()), "ollama": ollama_up(), "runs_version": runs_version(),
                "real_prompts": real_prompts(),
            })
        if self.path == "/api/runs":
            return self.send(200, {"runs": load_runs(), "runs_version": runs_version()})
        if self.path == "/api/live":
            return self.send(200, load_json(CONSOLE / "live.json", {"active": False}))
        self.send(404, {"error": "not found"})

    def parse_params(self, body):
        configs = [c for c in body.get("configs", []) if c in CONFIGS]
        scenarios = sorted({int(s) for s in body.get("scenarios", []) if 1 <= int(s) <= 15})
        seen, arms = set(), []
        for a in body.get("arms", []):  # the order given is the order run
            if a in ARMS and a not in seen:
                arms.append(a); seen.add(a)
        repeats = int(body.get("repeats", 1))
        max_cost = float(body.get("max_cost", 1.0))
        condition = body.get("condition", "base")
        if condition not in CONDITIONS:
            raise ValueError("Unknown condition.")
        temperature = float(body.get("temperature", 0))
        if temperature not in (0.0, 0.7, 1.0):
            raise ValueError("Temperature must be 0, 0.7 or 1.")
        real_prompt = body.get("real_prompt") or ""
        if real_prompt and real_prompt not in real_prompts():
            raise ValueError("Unknown framework prompt.")
        error_hint = bool(body.get("error_hint"))
        if not (configs and scenarios and arms and 1 <= repeats <= 3):
            raise ValueError("Pick a model, at least one scenario and one control.")
        if not 0 < max_cost <= 10:
            raise ValueError("The spend cap must be between $0.01 and $10.")
        return configs, {"scenarios": scenarios, "arms": arms, "repeats": repeats, "max_cost": max_cost,
                         "condition": condition, "temperature": temperature,
                         "real_prompt": real_prompt, "error_hint": error_hint}

    def do_POST(self):
        # A custom header forces a CORS preflight, which this server never answers,
        # so another website open in the browser cannot press Start.
        if self.headers.get("X-Agent-Fuel") != "1":
            return self.send(403, {"error": "forbidden"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        except ValueError:
            return self.send(400, {"error": "Malformed request."})

        if self.path == "/api/stop":
            with lock:
                job["stopped"] = True
                job["queue"] = []
                if job["proc"]:
                    job["proc"].terminate()
            say("stopped from the Stop button")
            return self.send(200, {"ok": True})

        if self.path in ("/api/start", "/api/command"):
            try:
                configs, p = self.parse_params(body)
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            suffix = f"-console-{datetime.now():%m%d-%H%M}"
            if self.path == "/api/command":
                lines = [" ".join(worker_cmd(c, p, suffix, display=True)) for c in configs]
                return self.send(200, {"commands": lines})
            if any(CONFIGS[c] == "anthropic" for c in configs) and not read_key():
                return self.send(400, {"error": "No Claude API key in ~/.config/agent-fuel/anthropic_key."})
            with lock:
                if job["proc"] is not None:
                    return self.send(409, {"error": "A launch is already running. Wait for it to finish or press Stop."})
                job.update(queue=configs, stopped=False, params=p, suffix=suffix)
                say(f"start: {', '.join(configs)} · {p['real_prompt'] or p['condition']}{'+hint' if p['error_hint'] else ''}"
                    f" · t={p['temperature']:g} · scenarios {p['scenarios']} · controls {''.join(p['arms'])} · repeats {p['repeats']}")
                launch_next()
            return self.send(200, {"ok": True, "suffix": suffix})

        self.send(404, {"error": "not found"})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Agent Fuel console: http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
