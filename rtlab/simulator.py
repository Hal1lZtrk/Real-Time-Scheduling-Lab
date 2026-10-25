"""Tick-accurate preemptive uniprocessor simulator.

Time advances in integer ticks. In every tick the scheduler picks one ready,
non-blocked job and runs it for exactly one tick.

Scheduling algorithms: 'rm', 'dm' (fixed priority), 'edf', or 'fixed' with
an explicit priority map.

Resource protocols (fixed-priority algorithms): 'none', 'npp', 'hlp',
'pip', 'pcp'. With 'edf' only 'none' and 'npp' are available.

Rules, kept deliberately simple so they can be read in one sitting:

* A job locks the resource of a critical-section segment when the segment
  starts and releases it when the segment ends. Sections are not nested.
* none  plain mutex: a job waits if the resource is held.
* npp   Non-Preemptive Protocol: a lock holder runs at the highest priority.
* hlp   Highest Locker Priority (immediate ceiling): on locking, the holder
        runs at the ceiling of the resource.
* pip   Priority Inheritance: a holder inherits the priority of the highest
        job it blocks (transitively).
* pcp   Priority Ceiling: a job may lock only if its priority is higher than
        the ceiling of every resource currently locked by *other* jobs;
        otherwise it blocks and the responsible holder inherits its priority.
* A job that misses its deadline keeps running to completion; the miss is
  recorded and reported.
* Ties between equal priorities are broken FIFO (earlier release first,
  then task order).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional, Tuple

from .analysis import INF_PRIORITY, PROTOCOLS, ceilings, hyperperiod
from .model import Task, TaskSet
from .priorities import assign_priorities


class Slot(NamedTuple):
    """What happened during one tick."""
    task: Optional[str]       # running task, None = idle
    job: Optional[int]        # job index k of that task
    resource: Optional[str]   # resource held while running (critical section)
    boosted: bool             # running above its nominal priority (inheritance/ceiling)
    blocked: Tuple[str, ...]  # tasks whose current job is blocked this tick


@dataclass(eq=False)
class Job:
    task: Task
    task_idx: int
    k: int
    release: int
    abs_deadline: int
    seg_i: int = 0
    seg_left: int = 0
    held: Optional[str] = None
    finish: Optional[int] = None
    inversion_ticks: int = 0
    inverters: set = field(default_factory=set)  # lower-priority jobs that ran while this one waited

    def __post_init__(self) -> None:
        self.seg_left = self.task.segments[0].duration

    @property
    def segment(self):
        return self.task.segments[self.seg_i]

    @property
    def label(self) -> str:
        return f"{self.task.name}#{self.k}"

    @property
    def response(self) -> Optional[int]:
        return None if self.finish is None else self.finish - self.release


@dataclass
class SimResult:
    taskset: TaskSet
    algorithm: str
    protocol: str
    horizon: int
    slots: List[Slot]
    jobs: List[Job]
    priorities: Dict[str, int]
    events: List[Tuple[int, str, str, str]] = field(default_factory=list)  # (t, kind, job, resource)

    # ---- derived data ------------------------------------------------
    def missed(self, job: Job) -> bool:
        if job.finish is None:
            return self.horizon > job.abs_deadline
        return job.finish > job.abs_deadline

    @property
    def misses(self) -> List[Job]:
        return [j for j in self.jobs if self.missed(j)]

    def jobs_of(self, name: str) -> List[Job]:
        return [j for j in self.jobs if j.task.name == name]

    def max_response(self, name: str) -> Optional[int]:
        done = [j.response for j in self.jobs_of(name) if j.finish is not None]
        return max(done) if done else None

    def max_inversion(self, name: str) -> int:
        js = self.jobs_of(name)
        return max((j.inversion_ticks for j in js), default=0)

    def summary(self) -> List[dict]:
        rows = []
        for t in self.taskset:
            js = self.jobs_of(t.name)
            done = [j.response for j in js if j.finish is not None]
            rows.append(
                {
                    "task": t.name,
                    "C": t.wcet,
                    "T": t.period,
                    "D": t.deadline,
                    "jobs": len(js),
                    "max_R": max(done) if done else None,
                    "avg_R": (sum(done) / len(done)) if done else None,
                    "misses": sum(1 for j in js if self.missed(j)),
                    "max_inversion": max((j.inversion_ticks for j in js), default=0),
                }
            )
        return rows

    def format_summary(self) -> str:
        head = f"{'task':<10}{'C':>4}{'T':>6}{'D':>6}{'jobs':>6}{'maxR':>6}{'avgR':>8}{'miss':>6}{'inv':>5}"
        lines = [f"algorithm={self.algorithm}  protocol={self.protocol}  horizon={self.horizon}", head]
        for r in self.summary():
            avg = "-" if r["avg_R"] is None else f"{r['avg_R']:.1f}"
            mx = "-" if r["max_R"] is None else str(r["max_R"])
            lines.append(
                f"{r['task']:<10}{r['C']:>4}{r['T']:>6}{r['D']:>6}{r['jobs']:>6}{mx:>6}{avg:>8}"
                f"{r['misses']:>6}{r['max_inversion']:>5}"
            )
        return "\n".join(lines)


def simulate(
    ts: TaskSet,
    algorithm: str = "rm",
    protocol: str = "none",
    horizon: Optional[int] = None,
    priorities: Optional[Dict[str, int]] = None,
) -> SimResult:
    algorithm = algorithm.lower()
    protocol = protocol.lower()
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r}; choose from {PROTOCOLS}")
    edf = algorithm == "edf"
    if edf and protocol not in ("none", "npp"):
        raise ValueError("with EDF only the protocols 'none' and 'npp' are supported")
    if algorithm == "fixed":
        if priorities is None:
            raise ValueError("algorithm 'fixed' needs a priorities map")
        prio = dict(priorities)
    elif edf:
        prio = assign_priorities(ts, "rm")  # only used for display/ordering ties
    else:
        prio = assign_priorities(ts, algorithm)

    ceil = ceilings(ts, prio) if not edf else {}
    if horizon is None:
        horizon = max(t.phase for t in ts) + hyperperiod(ts)

    active: List[Job] = []
    all_jobs: List[Job] = []
    holder: Dict[str, Job] = {}
    slots: List[Slot] = []
    events: List[Tuple[int, str, str, str]] = []

    def base(j: Job) -> int:
        return -j.abs_deadline if edf else prio[j.task.name]

    def blocker(j: Job) -> Optional[Job]:
        """Job that prevents j from entering its next critical section, if any."""
        res = j.segment.resource
        if res is None or j.held is not None:
            return None
        if protocol == "pcp":
            best: Optional[Job] = None
            best_c = -1
            for r, h in holder.items():
                if h is not j and ceil[r] > best_c:
                    best, best_c = h, ceil[r]
            if best is not None and prio[j.task.name] <= best_c:
                return best
            return None
        return holder.get(res)

    for t in range(horizon):
        # 1. releases
        for idx, task in enumerate(ts):
            if t >= task.phase and (t - task.phase) % task.period == 0:
                k = (t - task.phase) // task.period
                job = Job(task, idx, k, t, t + task.deadline)
                active.append(job)
                all_jobs.append(job)
                events.append((t, "release", job.label, ""))

        # 2. who is blocked, and effective priorities
        blocked: Dict[Job, Job] = {}
        for j in active:
            b = blocker(j)
            if b is not None:
                blocked[j] = b
        eff: Dict[Job, int] = {j: base(j) for j in active}
        for j in active:
            if j.held is not None:
                if protocol == "npp":
                    eff[j] = INF_PRIORITY
                elif protocol == "hlp":
                    eff[j] = max(eff[j], ceil[j.held])
        if protocol in ("pip", "pcp"):
            changed = True
            while changed:
                changed = False
                for waiting, hold in blocked.items():
                    if eff[hold] < eff[waiting]:
                        eff[hold] = eff[waiting]
                        changed = True

        # 3. pick the job to run
        runnable = [j for j in active if j not in blocked]
        run: Optional[Job] = None
        if runnable:
            run = max(runnable, key=lambda j: (eff[j], -j.release, -j.task_idx))
        elif active:
            raise RuntimeError(f"deadlock at t={t}: every ready job is blocked")

        # 4. lock if the job enters a critical section
        if run is not None:
            res = run.segment.resource
            if res is not None and run.held is None:
                holder[res] = run
                run.held = res
                events.append((t, "lock", run.label, res))

        # 5. bookkeeping for the tick
        if run is not None:
            for j in active:
                if base(j) > base(run):
                    j.inversion_ticks += 1
                    j.inverters.add(run.label)
            slots.append(
                Slot(
                    run.task.name, run.k, run.held, eff[run] > base(run),
                    tuple(sorted(j.task.name for j in blocked)),
                )
            )
        else:
            slots.append(Slot(None, None, None, False, ()))

        # 6. execute one tick
        if run is not None:
            run.seg_left -= 1
            if run.seg_left == 0:
                if run.held is not None:
                    events.append((t + 1, "unlock", run.label, run.held))
                    del holder[run.held]
                    run.held = None
                run.seg_i += 1
                if run.seg_i == len(run.task.segments):
                    run.finish = t + 1
                    active.remove(run)
                    events.append((t + 1, "finish", run.label, ""))
                else:
                    run.seg_left = run.segment.duration

    return SimResult(ts, algorithm, protocol, horizon, slots, all_jobs, prio, events)
