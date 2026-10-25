"""Regenerate every figure in images/ from the scenarios. Run from the repo root:

    python scripts/make_figures.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rtlab import simulate  # noqa: E402
from rtlab.plot import plot_compare  # noqa: E402
from rtlab.scenarios import (  # noqa: E402
    chained_blocking, plc_task_classes, priority_inversion, rm_vs_edf,
)

OUT = os.path.join(os.path.dirname(__file__), "..", "images")
os.makedirs(OUT, exist_ok=True)


def fixed(scenario, protocol):
    ts, prio, horizon = scenario
    return simulate(ts, "fixed", protocol, horizon, prio)


def main() -> None:
    ts = rm_vs_edf()
    plot_compare(
        [simulate(ts, "rm", horizon=21), simulate(ts, "edf", horizon=21)],
        ["Rate Monotonic: tau2 misses its deadline at t = 7", "EDF: both tasks meet every deadline (U = 0.971)"],
        os.path.join(OUT, "rm_vs_edf.png"),
    )

    inv = priority_inversion()
    plot_compare(
        [fixed(inv, "none"), fixed(inv, "pip")],
        ["Plain mutex: 'med' runs while 'high' waits for 'low' (priority inversion)",
         "Priority inheritance: 'low' runs at 'high' priority and finishes first"],
        os.path.join(OUT, "priority_inversion.png"), t_max=13,
    )
    plot_compare(
        [fixed(inv, p) for p in ("none", "npp", "hlp", "pip", "pcp")],
        ["none (plain mutex)", "NPP: non-preemptive critical sections", "HLP: highest locker priority",
         "PIP: priority inheritance", "PCP: priority ceiling"],
        os.path.join(OUT, "priority_inversion_all_protocols.png"), t_max=13,
    )

    ch = chained_blocking()
    plot_compare(
        [fixed(ch, "pip"), fixed(ch, "pcp")],
        ["PIP: 'high' is blocked twice, by low1 and then by low2 (response 6)",
         "PCP: low1 may not lock R1 while low2 holds R2, so 'high' is blocked once (response 3)"],
        os.path.join(OUT, "chained_blocking.png"), t_max=9,
    )

    long_ts = plc_task_classes(short_critical_section=False)
    short_ts = plc_task_classes(short_critical_section=True)
    plot_compare(
        [fixed(long_ts, "pcp"), fixed(short_ts, "pcp")],
        ["Logging holds the shared buffer for 3 ms: 'motion' misses its deadline",
         "Logging holds it for 0.5 ms: every deadline met"],
        os.path.join(OUT, "plc_task_classes.png"), t_max=44,
    )
    print("figures written to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
