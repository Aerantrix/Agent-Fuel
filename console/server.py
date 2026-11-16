"""Local console for the Agent Fuel experiment: dashboard plus Start and Stop.

    ~/.venvs/agent-fuel/bin/python console/server.py     then open http://127.0.0.1:8790

or double-click "Agent Fuel.command". dashboard.html is built on start from
dashboard.src.html, the same page that is published on claude.ai.

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPO = ROOT.parent  # the Agent Fuel repository this folder lives in
PYTHON = sys.executable  # the environment that runs this server also runs the worker


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
ARMS = set("ABCDEFG")

DATA.mkdir(exist_ok=True)
lock = threading.Lock()
job = {"proc": None, "queue": [], "params": None, "stopped": False}
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
    cmd = [PYTHON, "-u", str(ROOT / "worker.py"), "--repo", str(REPO), "--data", str(DATA),
           "--config", config, "--scenarios", ",".join(map(str, p["scenarios"])),
           "--arms", ",".join(p["arms"]), "--repeats", str(p["repeats"]),
           "--max-cost", str(p["max_cost"]), "--condition", p["condition"],
           "--temperature", str(p["temperature"])]
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
    now = load_now()
    if now.get("active"):
        now.update(active=False, doing="Stopped")
        (DATA / "now.json").write_text(json.dumps(now, ensure_ascii=False), encoding="utf-8")
    with lock:
        if job["proc"] is proc:
            launch_next()


def load_runs():
    runs = {}
    try:
        with (DATA / "runs.jsonl").open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    doc = json.loads(line)
                    runs[doc["id"]] = doc  # a re-run replaces the older record
    except FileNotFoundError:
        pass
    return list(runs.values())


def load_now():
    try:
        return json.loads((DATA / "now.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"active": False, "doing": "No runs in progress"}


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
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, (ROOT / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/state":
            with lock:
                running = job["proc"] is not None
                queued = list(job["queue"])
            return self.send(200, {
                "now": load_now(), "runs": load_runs(), "running": running, "queued": queued,
                "log": list(console_log)[-120:], "has_key": bool(read_key()), "ollama": ollama_up(),
            })
        self.send(404, {"error": "not found"})

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

        if self.path == "/api/start":
            configs = [c for c in body.get("configs", []) if c in CONFIGS]
            scenarios = sorted({int(s) for s in body.get("scenarios", []) if 1 <= int(s) <= 15})
            arms = [a for a in "ABCDEFG" if a in set(body.get("arms", []))]
            repeats = int(body.get("repeats", 1))
            max_cost = float(body.get("max_cost", 1.0))
            condition = body.get("condition", "base")
            if condition not in ("lenient", "base", "strict"):
                return self.send(400, {"error": "Unknown condition."})
            temperature = float(body.get("temperature", 0))
            if temperature not in (0.0, 0.7, 1.0):
                return self.send(400, {"error": "Temperature must be 0, 0.7 or 1."})
            if not (configs and scenarios and arms and 1 <= repeats <= 3):
                return self.send(400, {"error": "Pick a model, at least one scenario and one arm."})
            if not 0 < max_cost <= 10:
                return self.send(400, {"error": "The spend cap must be between $0.01 and $10."})
            if any(CONFIGS[c] == "anthropic" for c in configs) and not read_key():
                return self.send(400, {"error": "No Claude API key in ~/.config/agent-fuel/anthropic_key."})
            with lock:
                if job["proc"] is not None:
                    return self.send(409, {"error": "A launch is already running. Wait for it to finish or press Stop."})
                job.update(queue=configs, stopped=False,
                           params={"scenarios": scenarios, "arms": arms, "repeats": repeats, "max_cost": max_cost,
                                   "condition": condition, "temperature": temperature})
                say(f"start: {', '.join(configs)} · {condition} · t={temperature:g} · scenarios {scenarios} · arms {''.join(arms)} · repeats {repeats}")
                launch_next()
            return self.send(200, {"ok": True})

        self.send(404, {"error": "not found"})


if __name__ == "__main__":
    import build_dashboard  # noqa: F401  (rebuilds dashboard.html)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Agent Fuel console: http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
