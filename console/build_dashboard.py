"""Build dashboard.html (local, with Start/Stop) from dashboard.src.html (the claude.ai page).

The two pages share every chart and table; only the data source differs. The
claude.ai page reads its artifact database, the local one polls server.py and
adds the launch panel. Rebuild after any change to the source page:

    python build_dashboard.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "dashboard.src.html").read_text(encoding="utf-8")

CSS = """
.launch { margin-top: 18px; }
.launch .rows { display: grid; gap: 12px; }
.launch .row { display: grid; grid-template-columns: 120px 1fr; gap: 6px 14px; align-items: start; }
.launch .row > .k { padding-top: 6px; }
.opts { display: flex; flex-wrap: wrap; gap: 6px; }
.opt { display: inline-flex; align-items: center; gap: 6px; font: 500 12.5px var(--body); padding: 5px 9px; border: 1px solid var(--line); border-radius: 3px; background: var(--surface); color: var(--ink-2); cursor: pointer; }
.opt input { margin: 0; accent-color: var(--accent); }
.opt:has(input:checked) { color: var(--ink); border-color: var(--ink-3); background: var(--surface-2); }
.opt.num { font-family: var(--data); min-width: 44px; justify-content: center; }
.preset { font: 500 12px var(--body); padding: 5px 10px; border: 1px dashed var(--line); border-radius: 3px; background: transparent; color: var(--ink-2); cursor: pointer; }
.preset:hover { border-color: var(--ink-3); color: var(--ink); }
.go { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.btn { font: 600 14px var(--body); padding: 9px 22px; border-radius: 4px; border: 1px solid transparent; cursor: pointer; }
.btn.start { background: var(--guard); color: var(--surface); }
.btn.stop { background: transparent; color: var(--burn); border-color: var(--burn); }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.count { font-family: var(--data); font-size: 13px; color: var(--ink-2); }
.count b { color: var(--ink); }
.msg-err { color: var(--burn); font-size: 13px; }
.cost-in { width: 72px; font: 500 13px var(--data); padding: 4px 6px; border: 1px solid var(--line); border-radius: 3px; background: var(--surface); color: var(--ink); }
.console { font: 12px/1.55 var(--data); background: var(--surface-2); border: 1px solid var(--line-soft); padding: 10px 12px; max-height: 220px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--ink-2); margin: 0; }
.health { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; color: var(--ink-3); }
.ok-dot::before, .bad-dot::before { content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.ok-dot::before { background: var(--guard); } .bad-dot::before { background: var(--burn); }
@media (max-width: 600px) { .launch .row { grid-template-columns: 1fr; } }
"""

PANEL = """
<section class="panel launch" id="launch">
  <div class="panel-head">
    <div><h3>Launch</h3><p class="cap">Pick models, scenarios and arms, then press Start. Runs go one at a time and each result appears below as soon as it finishes.</p></div>
    <div class="health" id="health"></div>
  </div>
  <div class="rows">
    <div class="row"><span class="k">Models</span><div class="opts" id="l-configs">
      <label class="opt"><input type="checkbox" id="c-qwen" value="qwen">Qwen · local, free</label>
      <label class="opt"><input type="checkbox" id="c-haiku" value="haiku">Haiku 5.5 · thinking</label>
      <label class="opt"><input type="checkbox" id="c-haiku-nothink" value="haiku-nothink">Haiku 5.5 · no thinking</label>
    </div></div>
    <div class="row"><span class="k">Presets</span><div class="opts">
      <button type="button" class="preset" data-preset="calib">Calibration: scenarios 1, 2, 9, 11, 13 · arm A</button>
      <button type="button" class="preset" data-preset="one">Scenario 1 · A and G</button>
      <button type="button" class="preset" data-preset="all">Full sweep: 15 × 7 × 3</button>
    </div></div>
    <div class="row"><span class="k">Scenarios</span><div class="opts" id="l-scen"></div></div>
    <div class="row"><span class="k">Arms</span><div class="opts" id="l-arms"></div></div>
    <div class="row"><span class="k">Repeats</span><div class="opts" id="l-reps"></div></div>
    <div class="row"><span class="k">Spend cap</span><div class="opts" style="align-items:center">
      <input class="cost-in" type="number" id="l-cost" min="0.01" max="10" step="0.01" value="1.00" aria-label="Spend cap in dollars">
      <span class="cap">dollars per Haiku model for this launch; the launch stops itself when it gets there</span>
    </div></div>
    <div class="go">
      <button type="button" class="btn start" id="l-start">Start</button>
      <button type="button" class="btn stop" id="l-stop" disabled>Stop</button>
      <span class="count" id="l-count"></span>
      <span class="msg-err" id="l-err"></span>
    </div>
    <details><summary class="k" style="font-family:var(--body);font-size:11px">Launch log</summary><pre class="console" id="l-log">Nothing yet.</pre></details>
  </div>
</section>
"""

POLL = """
// --- local data source: poll server.py instead of the claude.ai database ----
const SC_PRESETS = {calib: {scen: [1, 2, 9, 11, 13], arms: ["A"], reps: 1},
  one: {scen: [1], arms: ["A", "G"], reps: 1}, all: {scen: SCENARIOS.map(s => s[0]), arms: ARMS.map(a => a[0]), reps: 3}};
function buildLaunch() {
  const sc = $("l-scen"), ar = $("l-arms"), rp = $("l-reps");
  SCENARIOS.forEach(([id, , title]) => { const l = el("label", "opt num"), c = el("input"); c.type = "checkbox"; c.value = id; c.id = "s-" + id; l.title = title; l.append(c, document.createTextNode(String(id))); sc.append(l); });
  ARMS.forEach(([a, n]) => { const l = el("label", "opt"), c = el("input"); c.type = "checkbox"; c.value = a; c.id = "a-" + a; l.append(c, document.createTextNode(a + " " + n)); ar.append(l); });
  [1, 2, 3].forEach(n => { const l = el("label", "opt num"), c = el("input"); c.type = "radio"; c.name = "reps"; c.value = n; c.id = "r-" + n; if (n === 1) c.checked = true; l.append(c, document.createTextNode(String(n))); rp.append(l); });
  document.querySelectorAll(".preset").forEach(b => b.onclick = () => {
    const p = SC_PRESETS[b.dataset.preset];
    sc.querySelectorAll("input").forEach(c => c.checked = p.scen.includes(Number(c.value)));
    ar.querySelectorAll("input").forEach(c => c.checked = p.arms.includes(c.value));
    rp.querySelectorAll("input").forEach(c => c.checked = Number(c.value) === p.reps);
    updateCount();
  });
  document.querySelectorAll("#launch input").forEach(c => c.addEventListener("change", updateCount));
  $("l-start").onclick = start; $("l-stop").onclick = stopRun;
  updateCount();
}
function launchParams() {
  const vals = sel => [...document.querySelectorAll(sel + " input:checked")].map(c => c.value);
  return {configs: vals("#l-configs"), scenarios: vals("#l-scen").map(Number), arms: vals("#l-arms"),
    repeats: Number(vals("#l-reps")[0] || 1), max_cost: Number($("l-cost").value || 1)};
}
function updateCount() {
  const p = launchParams(), n = p.scenarios.length * p.arms.length * p.repeats, total = n * p.configs.length;
  $("l-count").replaceChildren();
  if (!total) { $("l-count").textContent = "pick a model, scenarios and arms"; return; }
  $("l-count").append(document.createTextNode("will run "), el("b", null, String(total)), document.createTextNode(` run${total === 1 ? "" : "s"}: ${n} × ${p.configs.length} model${p.configs.length === 1 ? "" : "s"}`));
}
async function post(path, body) {
  const r = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json", "X-Agent-Fuel": "1"}, body: JSON.stringify(body || {})});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "The server returned error " + r.status);
  return j;
}
async function start() {
  $("l-err").textContent = "";
  try { await post("/api/start", launchParams()); poll(); } catch (e) { $("l-err").textContent = e.message; }
}
async function stopRun() { try { await post("/api/stop"); poll(); } catch (e) { $("l-err").textContent = e.message; } }

let lastKey = "";
async function poll() {
  let s;
  try { s = await (await fetch("/api/state", {cache: "no-store"})).json(); }
  catch { $("now-doing").textContent = "No connection to the local server. Start it again."; $("now-meta").textContent = ""; return; }
  renderNow(s.now);
  if (s.now && s.now.total) $("now-meta").textContent = `${s.now.config} · done ${s.now.done} of ${s.now.total} · spent $${(s.now.spent_usd || 0).toFixed(4)}` + (s.queued.length ? ` · next: ${s.queued.join(", ")}` : "");
  $("l-start").disabled = s.running; $("l-stop").disabled = !s.running;
  const h = $("health"); h.replaceChildren(
    el("span", s.has_key ? "ok-dot" : "bad-dot", s.has_key ? "Claude API key found" : "no Claude API key"),
    el("span", s.ollama ? "ok-dot" : "bad-dot", s.ollama ? "Ollama running" : "Ollama off, starts by itself on launch"));
  const lg = $("l-log"), atEnd = lg.scrollTop + lg.clientHeight >= lg.scrollHeight - 4;
  lg.textContent = s.log.length ? s.log.join("\\n") : "Nothing yet."; if (atEnd) lg.scrollTop = lg.scrollHeight;
  const good = s.runs.filter(r => !r.error), key = good.length + "|" + good.map(r => r.ts).join(",");
  if (key !== lastKey) { lastKey = key; runs = good; renderModelChips(); setCurveScenarios(); renderResults(); }
}
buildLaunch(); poll(); setInterval(poll, 2000);
"""

i = src.index("(async () => {")
j = src.index("})();", i) + len("})();")
out = src[:i] + POLL.strip() + src[j:]

now_end = out.index("</div>", out.index('<div class="meta" id="now-meta"></div>') + 1) + len("</div>")
out = out[:now_end] + "\n" + PANEL + out[now_end:]
out = out.replace("</style>", CSS + "</style>", 1)
out = out.replace("<title>Agent Fuel Tracker</title>", "<title>Agent Fuel Console</title>", 1)
out = out.replace("<h1>Agent Fuel Tracker</h1>", "<h1>Agent Fuel Console</h1>", 1)
# the page is served locally, so the frame-specific meta is not needed
out = out.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "", 1)
head = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>\n'
(ROOT / "dashboard.html").write_text(head + out + "\n</body></html>\n", encoding="utf-8")
print("wrote dashboard.html")
