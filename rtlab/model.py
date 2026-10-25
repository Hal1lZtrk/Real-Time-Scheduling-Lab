"""Task model.

A periodic task tau_i is described by

    C_i  worst-case execution time (sum of its segments)
    T_i  period
    D_i  relative deadline (default: T_i)
    phi_i  phase (release time of the first job, default 0)

Its body is a sequence of *segments*. A segment either computes freely
(``resource=None``) or runs a critical section on a named resource.
Critical sections are not nested; this keeps the protocols easy to reason
about and is documented as a limitation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Segment:
    resource: Optional[str]
    duration: int

    def __post_init__(self) -> None:
        if not isinstance(self.duration, int) or self.duration <= 0:
            raise ValueError(f"segment duration must be a positive int, got {self.duration!r}")


@dataclass(frozen=True)
class Task:
    name: str
    period: int
    wcet: int = 0
    deadline: int = 0
    phase: int = 0
    segments: Tuple[Segment, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        segs = tuple(self.segments)
        if not segs:
            if self.wcet <= 0:
                raise ValueError(f"task {self.name}: give wcet or segments")
            segs = (Segment(None, self.wcet),)
        wcet = sum(s.duration for s in segs)
        if self.wcet and self.wcet != wcet:
            raise ValueError(f"task {self.name}: wcet {self.wcet} != sum of segments {wcet}")
        object.__setattr__(self, "segments", segs)
        object.__setattr__(self, "wcet", wcet)
        if self.deadline == 0:
            object.__setattr__(self, "deadline", self.period)
        if self.period <= 0 or self.deadline <= 0 or self.phase < 0:
            raise ValueError(f"task {self.name}: period/deadline must be > 0 and phase >= 0")

    @property
    def utilization(self) -> float:
        return self.wcet / self.period

    @property
    def resources(self) -> set:
        return {s.resource for s in self.segments if s.resource is not None}

    def critical_sections(self) -> List[Segment]:
        return [s for s in self.segments if s.resource is not None]


class TaskSet(Sequence):
    """Ordered collection of tasks with unique names."""

    def __init__(self, tasks: Iterable[Task]):
        self._tasks = list(tasks)
        names = [t.name for t in self._tasks]
        if len(set(names)) != len(names):
            raise ValueError("task names must be unique")
        if not self._tasks:
            raise ValueError("empty task set")

    def __getitem__(self, i):
        return self._tasks[i]

    def __len__(self) -> int:
        return len(self._tasks)

    def by_name(self, name: str) -> Task:
        for t in self._tasks:
            if t.name == name:
                return t
        raise KeyError(name)

    @property
    def resources(self) -> List[str]:
        seen: List[str] = []
        for t in self._tasks:
            for s in t.segments:
                if s.resource is not None and s.resource not in seen:
                    seen.append(s.resource)
        return seen


def _task_from_dict(d: dict) -> Task:
    segs = tuple(Segment(s.get("resource"), int(s["duration"])) for s in d.get("segments", []))
    return Task(
        name=d["name"],
        period=int(d["period"]),
        wcet=int(d.get("wcet", 0)),
        deadline=int(d.get("deadline", 0)),
        phase=int(d.get("phase", 0)),
        segments=segs,
    )


def load_taskset(path: str) -> TaskSet:
    """Load a task set from a JSON file (see ``examples/*.json``)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return TaskSet(_task_from_dict(d) for d in data["tasks"])
