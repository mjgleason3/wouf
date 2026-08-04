"""Generate README charts (light + dark SVG pairs) from benchmark results.

Usage:  python -m benchmarks.charts   (after benchmarks.run)
Writes: docs/assets/*.svg
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wouf.dynamics import reinforce, retrievability
from wouf.models import DAY, Memory, MemoryType

ASSETS = Path(__file__).parent.parent / "docs" / "assets"
RESULTS = Path(__file__).parent / "out" / "results.json"

# Entity-fixed palette (validated): wouf=blue, full-context=orange, flat-files=aqua
THEMES = {
    "light": {
        "series": {"wouf": "#2a78d6", "full-context": "#eb6834", "flat-files": "#1baf7a"},
        "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "baseline": "#c3c2b7",
    },
    "dark": {
        "series": {"wouf": "#3987e5", "full-context": "#d95926", "flat-files": "#199e70"},
        "ink": "#e6e6e3", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "baseline": "#383835",
    },
}
FONT_STACK = "system-ui,-apple-system,'Segoe UI',sans-serif"
SYSTEMS = ["wouf", "full-context", "flat-files"]


def new_axes(theme: dict, size=(7.2, 3.4)):
    fig, ax = plt.subplots(figsize=size)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(theme["baseline"])
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=theme["muted"], labelsize=9, length=3)
    ax.grid(axis="y", color=theme["grid"], linewidth=0.6)
    ax.set_axisbelow(True)
    return fig, ax


def finish(fig, ax, theme: dict, title: str, name: str, mode: str) -> None:
    ax.set_title(title, color=theme["ink"], fontsize=12, loc="left", pad=12, fontweight="bold")
    fig.tight_layout()
    out = ASSETS / f"{name}_{mode}.svg"
    fig.savefig(out, format="svg", transparent=True)
    plt.close(fig)
    svg = out.read_text().replace("DejaVu Sans", FONT_STACK.replace("'", ""))
    out.write_text(svg)


def chart_decay(mode: str, theme: dict) -> None:
    rehearsed = Memory.new("rehearsed fact", MemoryType.SEMANTIC, 0.0)
    ignored = Memory.new("ignored fact", MemoryType.SEMANTIC, 0.0)
    days, r_curve, i_curve = [], [], []
    for tick in range(0, 351):
        now = tick / 10 * DAY
        if tick in (100, 200) :  # recalled on day 10 and day 20
            reinforce(rehearsed, now)
        days.append(tick / 10)
        r_curve.append(retrievability(rehearsed, now))
        i_curve.append(retrievability(ignored, now))

    fig, ax = new_axes(theme)
    blue = theme["series"]["wouf"]
    orange = theme["series"]["full-context"]
    ax.plot(days, r_curve, color=blue, linewidth=2)
    ax.plot(days, i_curve, color=orange, linewidth=2)
    for day in (10, 20):
        ax.plot([day], [1.0], marker="o", markersize=6, color=blue)
    ax.axhline(0.05, color=theme["muted"], linewidth=0.8, linestyle=(0, (4, 4)))

    grown = f"recalled twice\n(S grew 30→{rehearsed.stability:.0f}d)"
    ax.text(35.6, r_curve[-1], grown, color=theme["ink2"], fontsize=9, va="center")
    ax.text(35.6, i_curve[-1], "never used", color=theme["ink2"], fontsize=9, va="center")
    ax.text(43.5, 0.115, "archive threshold", color=theme["muted"], fontsize=8, ha="right")
    ax.annotate("each recall boosts stability,\nso decay slows down",
                xy=(20.2, 0.97), xytext=(21.5, 0.62), color=theme["ink2"], fontsize=9,
                arrowprops={"arrowstyle": "-", "color": theme["muted"], "linewidth": 0.8})

    ax.set_xlim(0, 44)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("days since stated", color=theme["muted"], fontsize=9)
    ax.set_ylabel("retrievability R", color=theme["muted"], fontsize=9)
    finish(fig, ax, theme, "Use it or lose it — the same fact, with and without recall", "decay", mode)


def chart_tokens(mode: str, theme: dict, results: dict) -> None:
    rows = results["sessions"]
    fig, ax = new_axes(theme)
    for name in SYSTEMS:
        series = [r["tokens"][name] for r in rows]
        ax.plot(range(1, len(rows) + 1), series, color=theme["series"][name],
                linewidth=2, label=name)
        ax.text(len(rows) + 0.4, series[-1], name, color=theme["ink2"], fontsize=9, va="center")
    ax.axhline(results["summary"]["budget"], color=theme["muted"], linewidth=0.8, linestyle=(0, (4, 4)))
    ax.text(1, results["summary"]["budget"] + 12, "session budget (600)", color=theme["muted"], fontsize=8)
    ax.set_xlim(1, len(rows) + 6)
    ax.set_ylim(0, 660)
    ax.set_xlabel("session", color=theme["muted"], fontsize=9)
    ax.set_ylabel("context tokens", color=theme["muted"], fontsize=9)
    ax.legend(frameon=False, fontsize=9, labelcolor=theme["ink2"],
              loc="center", bbox_to_anchor=(0.42, 0.30))
    finish(fig, ax, theme, "Context cost per session — 30 sessions, 45 virtual days", "tokens", mode)


def chart_quality(mode: str, theme: dict, results: dict) -> None:
    summary = results["summary"]
    metrics = [("recall", "avg_recall"), ("precision", "avg_precision"), ("F1", "avg_f1")]
    fig, ax = new_axes(theme, size=(7.2, 3.2))
    width = 0.24
    for offset, name in enumerate(SYSTEMS):
        xs = [i + (offset - 1) * width for i in range(len(metrics))]
        values = [summary[key][name] for _, key in metrics]
        ax.bar(xs, values, width - 0.03, color=theme["series"][name], label=name)
        for x, v in zip(xs, values):
            ax.text(x, v + 0.03, f"{v:.2f}", ha="center", color=theme["ink2"], fontsize=8.5)
    ax.set_xticks(range(len(metrics)), [label for label, _ in metrics])
    ax.tick_params(axis="x", colors=theme["ink2"], length=0)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel(f"score ({summary['probes']} probes)", color=theme["muted"], fontsize=9)
    ax.legend(frameon=False, fontsize=9, labelcolor=theme["ink2"], loc="upper right", ncols=3)
    finish(fig, ax, theme, "Was the needed memory in context when asked?", "quality", mode)


def chart_cost(mode: str, theme: dict, results: dict) -> None:
    summary = results["summary"]
    fig, ax = new_axes(theme, size=(7.2, 3.6))
    for name in SYSTEMS:
        effective = summary["avg_tokens"][name] * summary["est_context_cost_ratio"][name]
        recall = summary["avg_recall"][name]
        ax.plot([effective], [recall], marker="o", markersize=11, color=theme["series"][name])
        restated = summary["restatements"][name]
        label = f"{name}\n{restated} re-statement{'s' if restated != 1 else ''}"
        offset = (10, -4) if name != "flat-files" else (10, 6)
        ax.annotate(label, xy=(effective, recall), xytext=offset, textcoords="offset points",
                    color=theme["ink2"], fontsize=9, va="top")
    ax.set_xlim(-18, 460)
    ax.set_ylim(0, 1.1)
    ax.set_xlabel("effective context tokens per session (after prompt-cache discount)",
                  color=theme["muted"], fontsize=9)
    ax.set_ylabel("probe recall", color=theme["muted"], fontsize=9)
    ax.text(8, 1.035, "◤ cheap and reliable", color=theme["muted"], fontsize=8.5)
    finish(fig, ax, theme, "The trade-off that matters — reliability vs. effective cost", "cost", mode)


def main() -> None:
    results = json.loads(RESULTS.read_text())
    ASSETS.mkdir(parents=True, exist_ok=True)
    for mode, theme in THEMES.items():
        chart_decay(mode, theme)
        chart_tokens(mode, theme, results)
        chart_quality(mode, theme, results)
        chart_cost(mode, theme, results)
    print(f"wrote {len(list(ASSETS.glob('*.svg')))} SVGs to {ASSETS}")


if __name__ == "__main__":
    main()
