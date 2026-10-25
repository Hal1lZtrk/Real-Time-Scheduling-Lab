"""Gantt-chart rendering of simulation results (matplotlib)."""

from __future__ import annotations

from typing import List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

from .simulator import SimResult  # noqa: E402

PALETTE = ["#2a6fb0", "#d98c1f", "#3b9b6d", "#8e5ea2", "#c0504d", "#4f8a8b", "#7a7a7a"]
BLOCKED_FACE = "#e6e6e6"
BLOCKED_EDGE = "#8a8a8a"


def _row_order(res: SimResult) -> List[str]:
    """Most urgent task on top (fixed priorities); for EDF keep the given order."""
    names = [t.name for t in res.taskset]
    if res.algorithm == "edf":
        return names
    return sorted(names, key=lambda n: -res.priorities[n])


def plot_gantt(
    res: SimResult,
    ax=None,
    title: Optional[str] = None,
    t_max: Optional[int] = None,
    show_legend: bool = True,
):
    created = ax is None
    rows = _row_order(res)
    if created:
        fig, ax = plt.subplots(figsize=(10, 0.55 * len(rows) + 2.3))
    t_max = t_max or res.horizon
    color = {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(n.name for n in res.taskset)}
    y_of = {n: len(rows) - 1 - i for i, n in enumerate(rows)}  # first row at the top
    h = 0.5

    for t, slot in enumerate(res.slots[:t_max]):
        for name in slot.blocked:
            ax.add_patch(Rectangle((t, y_of[name] - h / 2), 1, h, facecolor=BLOCKED_FACE,
                                   edgecolor=BLOCKED_EDGE, hatch="////", linewidth=0.4, zorder=1))
        if slot.task is None:
            continue
        ax.add_patch(Rectangle(
            (t, y_of[slot.task] - h / 2), 1, h, facecolor=color[slot.task],
            edgecolor="#c0392b" if slot.boosted else "white",
            linewidth=1.8 if slot.boosted else 0.6, hatch="xx" if slot.resource else None, zorder=2))

    for job in res.jobs:
        y = y_of[job.task.name]
        if job.release < t_max:
            ax.annotate("", xy=(job.release, y + h / 2 + 0.28), xytext=(job.release, y + h / 2 - 0.02),
                        arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.0), zorder=3)
        if job.abs_deadline <= t_max:
            miss = res.missed(job)
            ax.plot([job.abs_deadline], [y - h / 2 - 0.14], marker="v" if not miss else "X",
                    color="#c0392b" if miss else "#333333", markersize=7 if miss else 5, zorder=4,
                    clip_on=False)

    ax.set_xlim(0, t_max)
    ax.set_ylim(-0.6, len(rows) - 0.3)
    ax.set_yticks([y_of[n] for n in rows])
    ax.set_yticklabels(rows)
    step = 1 if t_max <= 30 else (2 if t_max <= 60 else 5 if t_max <= 150 else 10)
    ax.set_xticks(range(0, t_max + 1, step))
    ax.tick_params(axis="x", labelsize=8)
    ax.set_xlabel("time (ticks)")
    ax.grid(axis="x", color="#dddddd", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if title:
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")

    if created:
        fig = ax.figure
        if show_legend:
            _legend(fig)
        fig.tight_layout(rect=(0, LEGEND_INCH / fig.get_figheight(), 1, 1))
    return ax


LEGEND_INCH = 0.75


def _legend(fig) -> None:
    base = PALETTE[0]
    handles = [
        Patch(facecolor=base, edgecolor="white", label="running"),
        Patch(facecolor=base, edgecolor="white", hatch="xx", label="running inside critical section"),
        Patch(facecolor=base, edgecolor="#c0392b", linewidth=1.8, label="running at boosted priority"),
        Patch(facecolor=BLOCKED_FACE, edgecolor=BLOCKED_EDGE, hatch="////", label="blocked on resource"),
        Line2D([0], [0], marker="^", color="#333333", linestyle="None", markersize=6, label="release"),
        Line2D([0], [0], marker="v", color="#333333", linestyle="None", markersize=6, label="deadline"),
        Line2D([0], [0], marker="X", color="#c0392b", linestyle="None", markersize=7, label="missed deadline"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8)


def plot_compare(
    results: Sequence[SimResult],
    titles: Sequence[str],
    path: str,
    t_max: Optional[int] = None,
    dpi: int = 160,
) -> None:
    """Stack several Gantt charts (same task set, different policy) in one PNG."""
    n_rows = len(results[0].taskset)
    fig, axes = plt.subplots(len(results), 1, sharex=True,
                             figsize=(10, (0.5 * n_rows + 0.9) * len(results) + 0.6 + LEGEND_INCH))
    if len(results) == 1:
        axes = [axes]
    for ax, res, title in zip(axes, results, titles):
        plot_gantt(res, ax=ax, title=title, t_max=t_max, show_legend=False)
        ax.set_xlabel("")
    axes[-1].set_xlabel("time (ticks)")
    _legend(fig)
    fig.tight_layout(rect=(0, LEGEND_INCH / fig.get_figheight(), 1, 1))
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_gantt(res: SimResult, path: str, title: Optional[str] = None, t_max: Optional[int] = None,
               dpi: int = 160) -> None:
    ax = plot_gantt(res, title=title, t_max=t_max)
    ax.figure.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(ax.figure)
