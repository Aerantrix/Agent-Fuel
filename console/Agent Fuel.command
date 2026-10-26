#!/bin/zsh
# Double-click to open the Agent Fuel console. Keep this window open while runs are going.
cd "$(dirname "$0")" || exit 1
if ! curl -s -m 1 http://127.0.0.1:8790/api/state >/dev/null; then
  # the project environment from the README, or an older one in ~/.venvs
  PY=../.venv/bin/python; [ -x "$PY" ] || PY=~/.venvs/agent-fuel/bin/python
  "$PY" server.py &
  for i in {1..20}; do curl -s -m 1 http://127.0.0.1:8790/api/state >/dev/null && break; sleep 0.3; done
fi
open http://127.0.0.1:8790
echo "Agent Fuel console is open: http://127.0.0.1:8790"
echo "Keep this window open while runs are going."
wait
