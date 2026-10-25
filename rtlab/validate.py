"""Randomized cross-validation of the analysis against the simulator.

The analysis (closed-form / fixed-point) and the simulator (tick by tick)
are two independent implementations of the same theory. If they ever
disagree on a random task set, one of them is wrong. ``cross_validate``
generates random task sets and checks:

  A. Fixed priority, no resources, D <= T:
       response-time analysis == simulated worst-case response time (exact),
       and the first task that RTA rejects really misses in the simulation.
  B. EDF, no resources:
       edf_feasible()  <=>  no deadline miss in the simulation.
  C. Fixed priority with shared resources and protocols npp/hlp/pip/pcp:
       if the analysis accepts the set, the simulation has no miss,
       every measured response time <= the analytic bound, and every
       measured priority-inversion time <= the analytic blocking bound B_i.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from .analysis import (
    blocking_bounds,
    edf_feasible,
    fp_schedulable,
    hyperperiod,
    response_times,
    utilization,
)
from .model import Segment, Task, TaskSet
from .priorities import assign_priorities
from .simulator import simulate

# every period divides 120, so the hyperperiod never exceeds 120 ticks
PERIODS = [4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 40, 60]


def random_taskset(
    rng: random.Random,
    n: Optional[int] = None,
    resources: bool = False,
    constrained_deadlines: bool = False,
    target_u: Optional[float] = None,
    phased: bool = False,
    cs_prob: float = 0.7,
) -> TaskSet:
    n = n or rng.randint(2, 6)
    target_u = target_u if target_u is not None else rng.uniform(0.3, 1.05)
    shares = [rng.random() + 0.05 for _ in range(n)]
    total = sum(shares)
    res_names = ["R1", "R2", "R3"][: rng.randint(1, 3)]
    tasks: List[Task] = []
    for i in range(n):
        period = rng.choice(PERIODS)
        wcet = max(1, round(period * target_u * shares[i] / total))
        wcet = min(wcet, period)
        deadline = period
        if constrained_deadlines:
            deadline = rng.randint(wcet, period)
        segs: tuple = ()
        if resources and wcet >= 2 and rng.random() < cs_prob:
            segs = _split_with_critical_sections(rng, wcet, res_names)
        phase = rng.randrange(period) if phased else 0
        tasks.append(Task(f"t{i}", period, 0 if segs else wcet, deadline, phase, segs))
    return TaskSet(tasks)


def _split_with_critical_sections(rng: random.Random, wcet: int, res_names: List[str]) -> tuple:
    """Split wcet into free compute and one or two critical sections."""
    n_cs = 2 if (wcet >= 4 and len(res_names) >= 2 and rng.random() < 0.4) else 1
    cs_lens = []
    budget = wcet
    for k in range(n_cs):
        left = n_cs - k - 1
        cs_lens.append(rng.randint(1, max(1, (budget - left) // 2)))
        budget -= cs_lens[-1]
    free = wcet - sum(cs_lens)
    cs_res = rng.sample(res_names, n_cs)
    parts: List[Segment] = []
    gaps = [rng.randint(0, free) for _ in range(n_cs)]
    gaps.sort()
    gaps = [gaps[0]] + [gaps[i] - gaps[i - 1] for i in range(1, n_cs)]
    used = 0
    for g, (res, ln) in zip(gaps, zip(cs_res, cs_lens)):
        if g:
            parts.append(Segment(None, g))
        parts.append(Segment(res, ln))
        used += g
    if free - used:
        parts.append(Segment(None, free - used))
    return tuple(parts)


def _check_fp_no_resources(ts: TaskSet, policy: str, failures: List[str], counts: Dict[str, int]) -> None:
    prio = assign_priorities(ts, policy)
    rta = response_times(ts, prio)
    sim = simulate(ts, policy, "none", horizon=hyperperiod(ts) + max(t.deadline for t in ts))
    order = sorted(ts, key=lambda t: -prio[t.name])
    for t in order:
        r = rta[t.name]
        if r <= t.deadline:
            counts["A_exact_checks"] += 1
            if sim.max_response(t.name) != r:
                failures.append(f"A: {t.name} RTA={r} sim={sim.max_response(t.name)} set={describe(ts)}")
        else:
            first = sim.jobs_of(t.name)[0]
            counts["A_reject_checks"] += 1
            if not sim.missed(first):
                failures.append(f"A: RTA rejects {t.name} (R>{t.deadline}) but sim meets it, set={describe(ts)}")
            break  # tasks below may suffer backlog; the analysis is only exact up to here


def _check_edf(ts: TaskSet, failures: List[str], counts: Dict[str, int]) -> None:
    ok, why = edf_feasible(ts)
    horizon = hyperperiod(ts) + max(t.deadline for t in ts) + 1
    sim = simulate(ts, "edf", "none", horizon=horizon)
    counts["B_checks"] += 1
    counts["B_feasible" if ok else "B_infeasible"] += 1
    if ok and sim.misses:
        failures.append(f"B: EDF says feasible ({why}) but sim misses, set={describe(ts)}")
    if not ok and not sim.misses:
        failures.append(f"B: EDF says infeasible ({why}) but sim has no miss, set={describe(ts)}")


def _check_resources(ts: TaskSet, protocol: str, failures: List[str], counts: Dict[str, int]) -> None:
    prio = assign_priorities(ts, "rm")
    ok, b, r = fp_schedulable(ts, prio, protocol)
    if not ok:
        counts["C_rejected_sets"] += 1
        return
    counts["C_accepted_sets"] += 1
    horizon = max(t.phase for t in ts) + hyperperiod(ts) + max(t.deadline for t in ts)
    sim = simulate(ts, "rm", protocol, horizon=horizon)
    if sim.misses:
        failures.append(f"C[{protocol}]: accepted by analysis but sim misses, set={describe(ts)}")
    for t in ts:
        counts["C_task_checks"] += 1
        mr = sim.max_response(t.name)
        if mr is not None and mr > r[t.name]:
            failures.append(f"C[{protocol}]: {t.name} sim R={mr} > bound {r[t.name]}, set={describe(ts)}")
        if protocol in ("npp", "hlp", "pcp"):
            counts["C_single_block_checks"] += 1
            worst = max((len(j.inverters) for j in sim.jobs_of(t.name)), default=0)
            if worst > 1:
                failures.append(f"C[{protocol}]: {t.name} blocked by {worst} different lower-priority jobs, set={describe(ts)}")
        inv = sim.max_inversion(t.name)
        if inv > 0:
            counts["C_tasks_with_blocking"] += 1
            if inv >= b[t.name] - 1:
                counts["C_within_one_tick_of_bound"] += 1
        if inv > b[t.name]:
            failures.append(f"C[{protocol}]: {t.name} inversion={inv} > B={b[t.name]}, set={describe(ts)}")


def describe(ts: TaskSet) -> str:
    parts = []
    for t in ts:
        body = ",".join(f"{s.resource or '-'}:{s.duration}" for s in t.segments)
        parts.append(f"{t.name}(T={t.period},D={t.deadline},[{body}])")
    return " ".join(parts)


def cross_validate(n_sets: int = 500, seed: int = 1) -> Dict[str, object]:
    rng = random.Random(seed)
    failures: List[str] = []
    counts: Dict[str, int] = {
        k: 0
        for k in (
            "A_sets", "A_exact_checks", "A_reject_checks",
            "B_checks", "B_feasible", "B_infeasible",
            "C_sets", "C_accepted_sets", "C_rejected_sets", "C_task_checks",
            "C_single_block_checks", "C_tasks_with_blocking", "C_within_one_tick_of_bound",
        )
    }
    for _ in range(n_sets):
        ts = random_taskset(rng, constrained_deadlines=rng.random() < 0.5)
        counts["A_sets"] += 1
        _check_fp_no_resources(ts, "dm" if any(t.deadline != t.period for t in ts) else "rm", failures, counts)

        ts = random_taskset(rng, constrained_deadlines=rng.random() < 0.5, target_u=rng.uniform(0.5, 1.1))
        _check_edf(ts, failures, counts)

        ts = random_taskset(rng, resources=True, target_u=rng.uniform(0.3, 0.8), phased=True, cs_prob=0.95)
        counts["C_sets"] += 1
        for proto in ("npp", "hlp", "pip", "pcp"):
            _check_resources(ts, proto, failures, counts)
    return {"counts": counts, "failures": failures, "seed": seed, "n_sets": n_sets}
