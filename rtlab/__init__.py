"""rtlab: a small lab for real-time scheduling theory.

Analysis (utilization tests, response-time analysis, EDF demand test,
blocking bounds) and a tick-accurate preemptive simulator, cross-checked
against each other by randomized tests.
"""

from .model import Segment, Task, TaskSet, load_taskset
from .analysis import (
    utilization,
    liu_layland_bound,
    hyperbolic_test,
    hyperperiod,
    ceilings,
    blocking_bounds,
    response_times,
    edf_feasible,
)
from .simulator import simulate, SimResult
from .priorities import assign_priorities

__all__ = [
    "Segment", "Task", "TaskSet", "load_taskset",
    "utilization", "liu_layland_bound", "hyperbolic_test", "hyperperiod",
    "ceilings", "blocking_bounds", "response_times", "edf_feasible",
    "simulate", "SimResult", "assign_priorities",
]
__version__ = "1.0.0"
