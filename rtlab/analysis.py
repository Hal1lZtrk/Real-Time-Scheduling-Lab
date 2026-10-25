"""Schedulability analysis.

Everything here is closed-form or fixed-point iteration; nothing simulates.
The simulator in ``simulator.py`` is later used to cross-check these results.

Conventions: integer time, larger priority number = more urgent.
"""

from __future__ import annotations

import math
from functools import reduce
from typing import Dict, List, Optional, Tuple

from .model import TaskSet

INF_PRIORITY = 10**9

# ---------------------------------------------------------------- utilization


def utilization(ts: TaskSet) -> float:
    return sum(t.utilization for t in ts)


def liu_layland_bound(n: int) -> float:
    """Least upper bound of RM utilization: n (2^(1/n) - 1). Valid for D = T."""
    return n * (2 ** (1.0 / n) - 1)


def hyperbolic_test(ts: TaskSet) -> bool:
    """Bini-Buttazzo hyperbolic bound: prod(U_i + 1) <= 2. Sufficient for RM, D = T."""
    prod = 1.0
    for t in ts:
        prod *= t.utilization + 1.0
    return prod <= 2.0


def hyperperiod(ts: TaskSet) -> int:
    return reduce(math.lcm, (t.period for t in ts), 1)


# ------------------------------------------------------- resource protocols

PROTOCOLS = ("none", "npp", "hlp", "pip", "pcp")


def ceilings(ts: TaskSet, prio: Dict[str, int]) -> Dict[str, int]:
    """Ceiling of a resource = highest priority among the tasks that use it."""
    ceil: Dict[str, int] = {}
    for t in ts:
        for r in t.resources:
            ceil[r] = max(ceil.get(r, 0), prio[t.name])
    return ceil


def blocking_bounds(ts: TaskSet, prio: Dict[str, int], protocol: str) -> Dict[str, Optional[int]]:
    """Worst-case blocking time B_i of each task under a resource access protocol.

    Only critical sections of *lower*-priority tasks can block tau_i, and only
    those on resources whose ceiling is >= p_i (they are used by tau_i itself,
    which is direct blocking, or by a higher-priority task, which causes
    push-through blocking).

    none  tasks that share a resource with a lower-priority task: no bound
          exists (medium-priority tasks can preempt the lock holder), None.
          Other tasks are never blocked: 0
    npp   longest critical section of any lower-priority task
    hlp   longest relevant critical section of a lower-priority task (one)
    pcp   same bound as HLP (a job is blocked at most once)
    pip   min(B_l, B_s): sum over lower tasks of their longest relevant CS,
          or sum over resources of the longest relevant CS (chained blocking)
    """
    protocol = protocol.lower()
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r}; choose from {PROTOCOLS}")
    ceil = ceilings(ts, prio)
    out: Dict[str, Optional[int]] = {}
    for ti in ts:
        pi = prio[ti.name]
        # (task name, resource, duration) of every critical section that may block tau_i
        relevant: List[Tuple[str, str, int]] = []
        for tj in ts:
            if prio[tj.name] >= pi:
                continue
            for cs in tj.critical_sections():
                if protocol == "none":
                    # without inheritance only direct blocking exists (no push-through)
                    hit = cs.resource in ti.resources
                else:
                    hit = protocol == "npp" or ceil[cs.resource] >= pi
                if hit:
                    relevant.append((tj.name, cs.resource, cs.duration))
        if not relevant:
            out[ti.name] = 0
            continue
        if protocol == "none":
            out[ti.name] = None  # unbounded: medium-priority tasks can prolong the wait
        elif protocol in ("npp", "hlp", "pcp"):
            out[ti.name] = max(d for _, _, d in relevant)
        else:  # pip
            per_task: Dict[str, int] = {}
            per_res: Dict[str, int] = {}
            for tn, r, d in relevant:
                per_task[tn] = max(per_task.get(tn, 0), d)
                per_res[r] = max(per_res.get(r, 0), d)
            out[ti.name] = min(sum(per_task.values()), sum(per_res.values()))
    return out


# --------------------------------------------------------- response time (FP)


def response_times(
    ts: TaskSet,
    prio: Dict[str, int],
    blocking: Optional[Dict[str, Optional[int]]] = None,
) -> Dict[str, Optional[int]]:
    """Response-time analysis for preemptive fixed priorities.

        R_i = C_i + B_i + sum_{j in hp(i)} ceil(R_i / T_j) * C_j

    solved by fixed-point iteration, synchronous release (critical instant).
    Requires D_i <= T_i. The iteration stops as soon as R_i exceeds D_i; the
    value returned then is the first iterate above the deadline, which is
    enough to report the task as unschedulable. Returns None if some B_i is
    unbounded (protocol 'none' with shared resources).
    """
    for t in ts:
        if t.deadline > t.period:
            raise ValueError(f"task {t.name}: RTA here assumes D <= T")
    blocking = blocking or {t.name: 0 for t in ts}
    result: Dict[str, Optional[int]] = {}
    for ti in ts:
        b = blocking[ti.name]
        if b is None:
            result[ti.name] = None
            continue
        hp = [tj for tj in ts if prio[tj.name] > prio[ti.name]]
        r = ti.wcet + b
        while True:
            nxt = ti.wcet + b + sum(math.ceil(r / tj.period) * tj.wcet for tj in hp)
            if nxt == r or nxt > ti.deadline:
                r = nxt
                break
            r = nxt
        result[ti.name] = r
    return result


def fp_schedulable(
    ts: TaskSet, prio: Dict[str, int], protocol: str = "none"
) -> Tuple[bool, Dict[str, Optional[int]], Dict[str, Optional[int]]]:
    """Convenience wrapper: (schedulable?, B_i, R_i)."""
    b = blocking_bounds(ts, prio, protocol)
    r = response_times(ts, prio, b)
    ok = all(r[t.name] is not None and r[t.name] <= t.deadline for t in ts)
    return ok, b, r


# ---------------------------------------------------------------------- EDF


def demand_bound(ts: TaskSet, t: int) -> int:
    """Processor demand dbf(t): work that must be done within [0, t]."""
    total = 0
    for task in ts:
        if t >= task.deadline:
            total += ((t - task.deadline) // task.period + 1) * task.wcet
    return total


def edf_feasible(ts: TaskSet) -> Tuple[bool, str]:
    """Exact EDF test for synchronous periodic tasks, preemptive, no resources.

    D = T for all tasks: feasible iff U <= 1 (Liu & Layland).
    Otherwise: U <= 1 and the processor demand criterion dbf(t) <= t at every
    absolute deadline t up to hyperperiod + max D.
    """
    u = utilization(ts)
    if u > 1 + 1e-12:
        return False, f"U = {u:.3f} > 1"
    if all(t.deadline == t.period for t in ts):
        return True, f"D = T for all tasks and U = {u:.3f} <= 1"
    limit = hyperperiod(ts) + max(t.deadline for t in ts)
    points = sorted(
        {k * t.period + t.deadline for t in ts for k in range(0, limit // t.period + 1)
         if k * t.period + t.deadline <= limit}
    )
    for p in points:
        if demand_bound(ts, p) > p:
            return False, f"dbf({p}) = {demand_bound(ts, p)} > {p}"
    return True, f"U = {u:.3f} <= 1 and dbf(t) <= t at all {len(points)} checked deadlines"
