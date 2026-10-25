"""Hand-built scenarios used by the examples, the tests and the README figures.

Each function returns (TaskSet, priorities, horizon) for algorithm 'fixed'
unless stated otherwise. Time unit: one tick.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .model import Segment, Task, TaskSet

Scenario = Tuple[TaskSet, Dict[str, int], int]


def rm_vs_edf() -> TaskSet:
    """U = 0.971: above the RM least upper bound, so RM fails; EDF still works."""
    return TaskSet([Task("tau1", period=5, wcet=2), Task("tau2", period=7, wcet=4)])


def priority_inversion() -> Scenario:
    """The classic three-task priority inversion.

    low  grabs resource R at t=0 and needs it for 4 ticks.
    high arrives at t=1, computes 1 tick, then needs R (deadline 6).
    med  arrives at t=2 and computes 6 ticks without touching R.

    With a plain mutex 'med' runs while 'high' waits for 'low': unbounded
    inversion. With a protocol, 'low' finishes its section quickly.
    """
    ts = TaskSet(
        [
            Task("high", period=40, deadline=6, phase=1,
                 segments=(Segment(None, 1), Segment("R", 1))),
            Task("med", period=40, deadline=40, phase=2, segments=(Segment(None, 6),)),
            Task("low", period=40, deadline=40, phase=0, segments=(Segment("R", 4),)),
        ]
    )
    return ts, {"high": 3, "med": 2, "low": 1}, 16


def chained_blocking() -> Scenario:
    """Why the Priority Ceiling Protocol exists.

    high needs R1 and then R2. low1 holds R1 and low2 holds R2 when high
    arrives. Under PIP, high is blocked twice (by low1, then by low2). Under
    PCP, low1 is not even allowed to lock R1 while low2 holds R2 (ceiling of
    R2 is high's priority), so high is blocked at most once.
    """
    ts = TaskSet(
        [
            Task("high", period=40, deadline=40, phase=2,
                 segments=(Segment("R1", 1), Segment("R2", 1))),
            Task("low1", period=40, deadline=40, phase=1, segments=(Segment("R1", 3),)),
            Task("low2", period=40, deadline=40, phase=0, segments=(Segment("R2", 3),)),
        ]
    )
    return ts, {"high": 3, "low1": 2, "low2": 1}, 12


def plc_task_classes(short_critical_section: bool = False) -> Scenario:
    """Illustrative PLC-style cyclic task classes (not measured on real hardware).

    Time unit: 0.5 ms per tick.
      motion   every  2 ms (T=4),   0.5 ms of work (C=1)   fastest class
      control  every 10 ms (T=20),  2 ms of work   (C=4)
      logging  every 100 ms (T=200), 15 ms of work (C=30) slowest class

    'motion' and 'logging' share a data buffer. If logging holds the buffer
    while it copies a whole recipe (3 ms critical section), the motion task
    can be blocked for almost 3 ms: more than its own 2 ms period. Copying
    the data out in a short 0.5 ms critical section fixes it.
    """
    cs = 1 if short_critical_section else 6
    rest = 30 - cs
    ts = TaskSet(
        [
            Task("motion", period=4, segments=(Segment("buf", 1),)),
            Task("control", period=20, wcet=4),
            Task("logging", period=200,
                 segments=(Segment(None, 10), Segment("buf", cs), Segment(None, rest - 10))),
        ]
    )
    return ts, {"motion": 3, "control": 2, "logging": 1}, 200
