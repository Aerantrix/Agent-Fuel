# Agent Fuel: getting started

Everything a new team member needs, in one place: setting up the project from
zero, then how we work together. For what the project is and how it is built,
see the [README](README.md).

# Part 1. Setting up from zero

This part is for someone who has never used GitHub, VS Code or a coding
assistant. Follow it in order. It takes about an hour, most of it downloads.

## What you will end up with

- A copy of this project on your computer, linked to the team's GitHub.
- An AI coding assistant inside VS Code that can run commands for you.
- A local language model (Qwen) that costs nothing to run.
- Your own Claude API key, with a spending limit you set, for the paid model.
- A page in your browser with a Start button that runs the experiment and
  shows the results.

Everything runs on your machine. The only things that leave it are the
messages the agent sends to the Claude API when you choose a Claude model, and
whatever you push to GitHub yourself.

You need about 8 GB of free disk space and at least 8 GB of RAM for the local
model.

## 1. Accounts

1. **GitHub.** Create an account at <https://github.com> if you do not have
   one, and send your user name to Nataliya. You will get an email invitation
   to the private repository `Aerantrix/Agent-Fuel`; accept it.
2. **Anthropic Console** (for the paid model). Create an account at
   <https://console.anthropic.com> and add a few dollars of credit. Each person
   uses their own account and pays for their own runs. A full scenario sweep on
   Haiku 5.5 costs a few cents; see `docs/work_log.md` for measured figures.

## 2. VS Code and an assistant

1. Install VS Code from <https://code.visualstudio.com>.
2. Install an assistant extension. Press `Cmd+Shift+X` (Mac) or
   `Ctrl+Shift+X` (Windows) to open Extensions, then either:
   - **Claude Code** by Anthropic (recommended, used to build this project).
     Sign in when it asks: any paid Claude plan (Pro, Max, Team, Enterprise) or
     a Console account works. Open it with the Spark icon in the top-right
     corner of an open file, or in the left sidebar.
   - **Codex** by OpenAI, if you have ChatGPT. Sign in with your ChatGPT
     account. Check the extension page for the plans it supports.
3. **Talk to it in plain words**, in any language. Every step below has a
   request you can paste, marked **Ask your assistant**. You can also do the
   steps yourself with the commands given.

### Permissions: what the assistant asks and what to answer

The assistant works on your computer: it reads files, edits them and runs
commands in a terminal. Before doing something it may ask you to allow it.

- **Start in Manual mode.** In Claude Code, click the mode name at the bottom
  of the prompt box and pick **Manual**: it then asks before every file edit
  and most commands, so you see everything it does while you learn. Other
  modes (**Auto**, **Edit automatically**) let it act without asking.
- **Allow** commands you asked for and understand: installing Python packages,
  `git` commands, starting the console.
- **Deny, or ask what it is for,** anything that deletes files you did not
  mention, changes files outside the project folder, or sends data somewhere.
- **"Allow once" versus "Always allow":** prefer "once" until you trust a
  command.
- **Never paste an API key into the chat.** Use the steps in section 6.

## 3. Git and the project

1. **Install Git.**
   - Mac: open Terminal and type `git --version`. If Git is missing, macOS
     offers to install the developer tools; accept.
   - Windows: install Git for Windows from <https://git-scm.com>, keeping the
     default options.
2. **Get the project.** In VS Code press `Cmd+Shift+P` / `Ctrl+Shift+P`, choose
   **Git: Clone**, paste `https://github.com/Aerantrix/Agent-Fuel.git`, pick a
   folder such as `Documents`, and open the project when asked. Sign in to
   GitHub if VS Code asks.

   > **Ask your assistant:** Clone https://github.com/Aerantrix/Agent-Fuel.git into my Documents folder and open it.

## 4. Python and the project environment

The project needs **Python 3.10 or newer**. The Python that comes with macOS is
too old.

- Mac: install the latest Python from <https://www.python.org/downloads/>.
- Windows: install it from <https://www.python.org/downloads/> and tick
  **Add python.exe to PATH** on the first screen.

Then create the project's own environment inside the project folder (it is
called `.venv` and is never uploaded to GitHub) and install what it needs.

> **Ask your assistant:** In this project, create a Python virtual environment called .venv with Python 3.10 or newer, and install requirements.txt into it.

Or yourself, in VS Code's terminal (**Terminal → New Terminal**):

```bash
# Mac
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

```powershell
# Windows
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## 5. The local model (required)

The free local model, **Qwen 2.5 7B**, runs through a program called Ollama.
The model is a 4.7 GB download.

1. Install Ollama from <https://ollama.com/download> (Mac or Windows) and start
   it once. It then runs in the background.
2. Download the model:

   ```bash
   ollama pull qwen2.5:7b
   ```

   > **Ask your assistant:** Check that Ollama is installed and running, then download the model qwen2.5:7b.

3. Check it is there: `ollama list` should show `qwen2.5:7b`.

## 6. Your Claude API key (each person their own)

The key is a long string that starts with `sk-ant-`. Whoever holds it can spend
from your account, so it is kept in a file on your computer that only you can
read, never in the project folder, never in GitHub and never in a chat.

### Create the key with a spending limit

1. At <https://console.anthropic.com>, open **Settings → Workspaces**
   (`platform.claude.com/settings/workspaces`) and click **Create workspace**.
   Name it `agent-fuel`.
2. Click the new workspace in the list. In the panel that opens, click
   **Spend limits** and set a monthly limit, for example $10. This is your
   safety net: whatever goes wrong, the experiment cannot spend more.
3. In the left menu open **API keys** and click **Create Key**. Name it, for
   example, `agent-fuel-laptop`, and set **Scope** to `agent-fuel`.
4. The key is shown **once**. Copy the long string that starts with `sk-ant-`,
   not the short `apikey_...` identifier next to it.

### Save it on your computer

The command below asks for the key and writes it to
`~/.config/agent-fuel/anthropic_key` (your home folder). What you paste is not
shown on screen; that is expected.

**Mac**, in Terminal or VS Code's terminal:

```bash
mkdir -p ~/.config/agent-fuel && printf 'Paste the key and press Enter: ' && read -rs k && printf '%s' "$k" > ~/.config/agent-fuel/anthropic_key && chmod 600 ~/.config/agent-fuel/anthropic_key && unset k && echo && echo Saved
```

**Windows**, in PowerShell or VS Code's terminal:

```powershell
New-Item -ItemType Directory -Force "$HOME\.config\agent-fuel" | Out-Null; $k = Read-Host "Paste the key and press Enter" -AsSecureString; [System.Net.NetworkCredential]::new('', $k).Password | Set-Content -NoNewline "$HOME\.config\agent-fuel\anthropic_key"; Remove-Variable k; "Saved"
```

Order matters: run the command first, then copy the key in the Console and
paste it when the terminal asks. To replace the key later, run the same
command again. Keys expire; when yours does, create a new one the same way.

The console page shows **Claude API key found** when the key is in place. You
can work with the local model without any key.

## 7. Start the console

- **Mac:** in Finder, open the project's `console` folder and double-click
  `Agent Fuel.command`. A Terminal window opens and the page opens in your
  browser. Keep that window open while runs are going.
- **Windows:** in VS Code's terminal, from the project folder:

  ```powershell
  .venv\Scripts\python console\server.py
  ```

  then open <http://127.0.0.1:8790> in your browser. Keep the terminal open.

> **Ask your assistant:** Create a desktop shortcut that starts the Agent Fuel console: it should run console/server.py with the project's .venv Python from the project folder and open http://127.0.0.1:8790 in the browser. I'm on Windows. (or: I'm on a Mac)

The page is only reachable from your own computer.

## 8. Run the experiment

On the console page:

1. **Models:** tick Qwen (free) and/or the Haiku models (paid, your key).
2. **Presets:** *Calibration* runs five scenarios under arm A; *Scenario 1 · A
   and G* is a quick check; *Full sweep* is everything.
3. Check **will run N runs**, set a **Spend cap**, and press **Start**.
4. Watch **Run status**. Each finished run appears in the results below; click
   a cell in the scenario matrix to read the run step by step.

Your runs are saved in `console/data/` on your computer and are not uploaded.

# Part 2. Working together

## Rules

- **Never push to `master` directly.** Every change goes through a branch and a
  pull request that someone else reads first. (GitHub cannot enforce this on
  our plan, so it is a team rule.)
- **Changes that alter the experiment** (thresholds in `control/policies.yaml`,
  the agent's instructions or tasks in `agent/runner.py`, scenarios, fake tool
  behaviour) need a pull request that says why. Results made before and after
  such a change cannot be compared.
- **Do not "fix" the six deliberate decisions** listed under *Do not change
  these* in [`DEVELOPER.md`](DEVELOPER.md). They look like bugs and are not.
- **Write it down.** Anything you find or change goes into
  [`docs/work_log.md`](docs/work_log.md) under the date.

## Propose a change

> **Ask your assistant:** Create a new branch called short-description-of-change, commit my changes with a clear message, push the branch and open a pull request to master describing what changed and why.

Before you start new work, get the latest version:

> **Ask your assistant:** Switch to master and pull the latest changes from GitHub.

## Share your results

Results go to the team the same way as code, in a folder named with the date
and your name:

> **Ask your assistant:** Copy console/data/runs.jsonl to results/YYYY-MM-DD-myname/runs.jsonl (today's date, my first name), commit it on a new branch and open a pull request titled "Results: <what I ran>".

Say in the pull request which models, scenarios and arms you ran, and anything
odd you saw.

## When something does not work

- **The page does not open:** the console is not running; start it again
  (section 7). If it says the address is in use, it is already running in
  another window.
- **No Claude API key:** redo section 6 and reload the page.
- **Ollama off:** start the Ollama app; the console also tries to start it.
- **Anything else:** describe what you did and paste the error to your
  assistant, or look at the **Launch log** at the bottom of the Launch panel.
