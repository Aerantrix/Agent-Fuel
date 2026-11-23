"""The architecture diagram (Fig. 1 of the paper): the stand as it was run.

    python docs/architecture_diagram.py [en|ru] [out.png] [dpi]

Boxes and arrows in matplotlib; the only dependency is matplotlib."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

lang = sys.argv[1] if len(sys.argv) > 1 else "en"
out = sys.argv[2] if len(sys.argv) > 2 else f"fig1_{lang}.png"
DPI = int(sys.argv[3]) if len(sys.argv) > 3 else 300

EN = {
    "agent": ("Agent loop", "plan, call the tool,\nread the result"),
    "ctl": ("Agent Fuel controller", "run budget, loop detector,\ncircuit breaker, error classifier;\nverdict on every step: allow, warn or stop"),
    "api": ("Model API", "one call per step;\nreturns input and\noutput token counts"),
    "harness": ("Fault harness", "stub analytics service,\nno real call; returns data,\nan error, an empty or\nrepeated page, or HTML"),
    "suite": ("Scenario suite", "9 scenarios in 3 groups:\nfailure mode, task,\nexpected mechanism"),
    "journal": ("Decision journal", "before and after\neach call: step,\nmechanism, reason,\ntokens"),
    "record": ("Run record", "runs.jsonl: one\nrecord per run, with\nthe trace and\nthe decisions"),
    "results": ("Analysis", "every control\nreplayed over\nthe record;\nreplay.csv, summary.md"),
    "e_step": "each step", "e_verdict": "verdict", "e_model": "model call", "e_tool": "tool call",
    "e_mode": "failure mode", "e_rec": "per run", "e_rep": "replayed",
    "tag_agent": "major technology: agentic AI with tool use",
    "tag_ctl": "supporting technology: fault-tolerance patterns",
}
RU = {
    "agent": ("Цикл агента", "план, вызов инструмента,\nчтение результата"),
    "ctl": ("Контроллер Agent Fuel", "бюджет прогона, детектор повторов,\nразмыкатель, классификатор ошибок;\nвердикт на каждом шаге:\nпропустить, предупредить, остановить"),
    "api": ("API модели", "один вызов на шаг;\nвозвращает счётчики\nвходных и выходных\nтокенов"),
    "harness": ("Стенд отказов", "подменный сервис\nаналитики, без реальных\nвызовов; возвращает данные,\nошибку, пустую или ту же\nстраницу, либо HTML"),
    "suite": ("Набор сценариев", "9 сценариев в 3 группах:\nрежим отказа, задача,\nожидаемый механизм"),
    "journal": ("Журнал решений", "до и после каждого\nвызова: шаг, механизм,\nпричина, токены"),
    "record": ("Запись прогона", "runs.jsonl: одна\nзапись на прогон,\nс трассой\nи решениями"),
    "results": ("Анализ", "каждый контроль\nпрогнан по записи;\nreplay.csv,\nsummary.md"),
    "e_step": "каждый шаг", "e_verdict": "вердикт", "e_model": "вызов модели", "e_tool": "вызов инструмента",
    "e_mode": "режим отказа", "e_rec": "на прогон", "e_rep": "по записи",
    "tag_agent": "основная технология: агентный ИИ с инструментами",
    "tag_ctl": "вспомогательная технология: паттерны отказоустойчивости",
}
L = EN if lang == "en" else RU
TF, BF = (6.6, 5.2) if lang == "en" else (6.2, 4.8)

plt.rcParams.update({"font.family": "serif"})
fig, ax = plt.subplots(figsize=(3.5, 3.95), dpi=DPI)
ax.set_xlim(0, 100); ax.set_ylim(18, 135); ax.axis("off")

def box(x, y, w, h, title, body, bold=False, tag=""):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.5",
                       linewidth=1.1 if bold else 0.6, edgecolor="black", facecolor="#f2f2f2" if bold else "white")
    ax.add_patch(p)
    ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="top", fontsize=TF, fontweight="bold")
    ax.text(x + w / 2, y + h - 7.6, body, ha="center", va="top", fontsize=BF, linespacing=1.2)
    if tag:
        ax.text(x + w / 2, y + 1.6, tag, ha="center", va="bottom", fontsize=4.3 if lang == "en" else 3.7, style="italic", color="#444444")

def arrow(x1, y1, x2, y2, label="", lx=0, ly=0):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=6, linewidth=0.6, color="black",
                        shrinkA=0, shrinkB=0)
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, fontsize=4.8, ha="center", va="center",
                bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none"))

box(12, 116, 52, 18, *L["agent"], tag=L["tag_agent"])
box(2, 82, 64, 28, *L["ctl"], bold=True, tag=L["tag_ctl"])
box(2, 54, 28, 22, *L["api"])
box(34, 50, 32, 26, *L["harness"])
box(34, 20, 32, 20, *L["suite"])
box(70, 90, 28, 22, *L["journal"])
box(70, 60, 28, 22, *L["record"])
box(70, 30, 28, 22, *L["results"])

arrow(30, 116, 30, 110, L["e_step"], lx=-8)
arrow(44, 110, 44, 116, L["e_verdict"], lx=6)
arrow(16, 82, 16, 76, L["e_model"], lx=-9)
arrow(50, 82, 50, 76, L["e_tool"], lx=8 if lang == "en" else -13)
arrow(50, 40, 50, 50, L["e_mode"], lx=9 if lang == "en" else 10)
arrow(66, 101, 70, 101)
arrow(84, 90, 84, 82, L["e_rec"], lx=7)
arrow(84, 60, 84, 52, L["e_rep"], lx=7)

fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
fig.savefig(out, facecolor="white")
print("wrote", out)
