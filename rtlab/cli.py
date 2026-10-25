"""Command line interface: python -m rtlab <analyze|simulate|validate> ..."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .analysis import (
    PROTOCOLS, blocking_bounds, edf_feasible, fp_schedulable, hyperbolic_test,
    hyperperiod, liu_layland_bound, utilization,
)
from .model import load_taskset
from .priorities import assign_priorities
from .simulator import simulate


def _fmt(x) -> str:
    return "unbounded" if x is None else str(x)


def cmd_analyze(args: argparse.Namespace) -> int:
    ts = load_taskset(args.taskset)
    u = utilization(ts)
    print(f"{len(ts)} tasks, utilization U = {u:.3f}, hyperperiod = {hyperperiod(ts)} ticks")
    implicit = all(t.deadline == t.period for t in ts)
    if implicit:
        print(f"RM least upper bound for n={len(ts)}: {liu_layland_bound(len(ts)):.3f}  "
              f"(U {'<=' if u <= liu_layland_bound(len(ts)) else '>'} bound -> "
              f"{'RM guaranteed' if u <= liu_layland_bound(len(ts)) else 'test inconclusive'}); "
              f"hyperbolic test: {'pass' if hyperbolic_test(ts) else 'fail'}")
    ok, why = edf_feasible(ts) if not ts.resources else (None, "")
    if ok is not None:
        print(f"EDF (preemptive, no resources): {'feasible' if ok else 'NOT feasible'} - {why}")
    policy = args.policy
    if any(t.deadline > t.period for t in ts):
        print("note: response-time analysis needs D <= T; skipped")
        return 0
    prio = assign_priorities(ts, policy)
    ok, b, r = fp_schedulable(ts, prio, args.protocol)
    print(f"\nFixed priority ({policy.upper()}), protocol = {args.protocol}")
    print(f"{'task':<12}{'prio':>5}{'C':>5}{'T':>6}{'D':>6}{'B':>11}{'R':>8}  verdict")
    for t in sorted(ts, key=lambda t: -prio[t.name]):
        rt = r[t.name]
        verdict = "OK" if rt is not None and rt <= t.deadline else ("UNBOUNDED BLOCKING" if rt is None else "MISSES DEADLINE")
        shown = "-" if rt is None else (str(rt) if rt <= t.deadline else f">{t.deadline}")
        print(f"{t.name:<12}{prio[t.name]:>5}{t.wcet:>5}{t.period:>6}{t.deadline:>6}{_fmt(b[t.name]):>11}{shown:>8}  {verdict}")
    print("\nSCHEDULABLE" if ok else "\nNOT SCHEDULABLE")
    return 0 if ok else 1


def cmd_simulate(args: argparse.Namespace) -> int:
    ts = load_taskset(args.taskset)
    res = simulate(ts, args.alg, args.protocol, args.horizon)
    print(res.format_summary())
    if res.misses:
        print("\nDeadline misses:")
        for j in res.misses[:20]:
            fin = "never" if j.finish is None else str(j.finish)
            print(f"  {j.label}: released {j.release}, deadline {j.abs_deadline}, finished {fin}")
    if args.png:
        from .plot import save_gantt
        save_gantt(res, args.png, title=f"{args.alg.upper()} / protocol {args.protocol}", t_max=args.window)
        print(f"\nGantt chart written to {args.png}")
    return 1 if res.misses else 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .validate import cross_validate
    out = cross_validate(args.sets, args.seed)
    for k, v in out["counts"].items():
        print(f"{k:<32}{v}")
    print(f"\nfailures: {len(out['failures'])}")
    for f in out["failures"][:10]:
        print("  ", f)
    return 1 if out["failures"] else 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="rtlab", description="Real-time scheduling analysis and simulation")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="schedulability analysis of a JSON task set")
    a.add_argument("taskset")
    a.add_argument("--policy", choices=["rm", "dm"], default="rm")
    a.add_argument("--protocol", choices=PROTOCOLS, default="none")
    a.set_defaults(func=cmd_analyze)

    s = sub.add_parser("simulate", help="simulate a JSON task set and print statistics")
    s.add_argument("taskset")
    s.add_argument("--alg", choices=["rm", "dm", "edf"], default="rm")
    s.add_argument("--protocol", choices=PROTOCOLS, default="none")
    s.add_argument("--horizon", type=int, default=None, help="ticks to simulate (default: hyperperiod)")
    s.add_argument("--png", help="write a Gantt chart to this file")
    s.add_argument("--window", type=int, default=None, help="only draw the first N ticks")
    s.set_defaults(func=cmd_simulate)

    v = sub.add_parser("validate", help="cross-check analysis against simulation on random task sets")
    v.add_argument("--sets", type=int, default=500)
    v.add_argument("--seed", type=int, default=1)
    v.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
