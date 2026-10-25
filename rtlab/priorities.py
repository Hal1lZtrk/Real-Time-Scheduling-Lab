"""Fixed-priority assignment. A larger number means a more urgent task."""

from __future__ import annotations

from typing import Dict

from .model import TaskSet


def assign_priorities(ts: TaskSet, policy: str = "rm") -> Dict[str, int]:
    """Return {task name: priority}, unique, highest number = highest priority.

    rm  rate monotonic: shorter period -> higher priority
    dm  deadline monotonic: shorter relative deadline -> higher priority
    Ties are broken by position in the task set (earlier = higher).
    """
    policy = policy.lower()
    if policy == "rm":
        key = lambda it: (it[1].period, it[0])
    elif policy == "dm":
        key = lambda it: (it[1].deadline, it[0])
    else:
        raise ValueError(f"unknown fixed-priority policy {policy!r} (use 'rm' or 'dm')")
    order = sorted(enumerate(ts), key=key)  # most urgent first
    n = len(order)
    return {task.name: n - rank for rank, (_, task) in enumerate(order)}
