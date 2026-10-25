import math

import pytest

from rtlab import (
    Segment, Task, TaskSet, assign_priorities, blocking_bounds, edf_feasible,
    hyperbolic_test, hyperperiod, liu_layland_bound, response_times, utilization,
)


def ts3():
    return TaskSet([Task("a", 4, 1), Task("b", 6, 2), Task("c", 13, 3)])


def test_utilization_and_bounds():
    ts = ts3()
    assert utilization(ts) == pytest.approx(1 / 4 + 2 / 6 + 3 / 13)
    assert liu_layland_bound(1) == pytest.approx(1.0)
    assert liu_layland_bound(2) == pytest.approx(2 * (math.sqrt(2) - 1))
    assert liu_layland_bound(1000) == pytest.approx(math.log(2), abs=1e-3)
    # prod(U+1) = 2.05 > 2: the hyperbolic test is only sufficient; RTA below still accepts the set
    assert not hyperbolic_test(ts)
    assert hyperbolic_test(TaskSet([Task('x', 10, 2), Task('y', 20, 4)]))


def test_hyperperiod():
    assert hyperperiod(ts3()) == 156


def test_priorities_rm_dm():
    ts = TaskSet([Task("slow", 20, 1), Task("fast", 5, 1), Task("mid", 10, 1, deadline=3)])
    assert assign_priorities(ts, "rm") == {"fast": 3, "mid": 2, "slow": 1}
    assert assign_priorities(ts, "dm") == {"mid": 3, "fast": 2, "slow": 1}
    with pytest.raises(ValueError):
        assign_priorities(ts, "nope")


def test_rta_hand_computed():
    # R_a = 1; R_b = 2 + ceil(3/4)*1 = 3; R_c converges to 10 (hand iteration 3, 6, 7, 9, 10)
    ts = ts3()
    prio = assign_priorities(ts, "rm")
    assert response_times(ts, prio) == {"a": 1, "b": 3, "c": 10}


def test_rta_rejects_unschedulable_and_needs_constrained_deadlines():
    ts = TaskSet([Task("t1", 5, 2), Task("t2", 7, 4)])
    prio = assign_priorities(ts, "rm")
    assert response_times(ts, prio)["t2"] == 8  # > D = 7
    bad = TaskSet([Task("x", 5, 1, deadline=9)])
    with pytest.raises(ValueError):
        response_times(bad, {"x": 1})


def test_edf_feasibility():
    assert edf_feasible(TaskSet([Task("t1", 5, 2), Task("t2", 7, 4)]))[0]       # U = 0.971
    assert not edf_feasible(TaskSet([Task("t1", 4, 3), Task("t2", 6, 2)]))[0]   # U > 1
    # U < 1 but demand criterion fails: two tasks need 3 units each within 4 ticks
    ts = TaskSet([Task("p", 20, 3, deadline=4), Task("q", 20, 3, deadline=4)])
    ok, why = edf_feasible(ts)
    assert not ok and "dbf(4)" in why


def test_blocking_bounds_simple():
    ts = TaskSet([
        Task("hi", 10, 0, segments=(Segment("R", 1), Segment(None, 1))),
        Task("lo", 20, 0, segments=(Segment("R", 3), Segment(None, 1))),
    ])
    prio = assign_priorities(ts, "rm")
    assert blocking_bounds(ts, prio, "none") == {"hi": None, "lo": 0}
    for p in ("npp", "hlp", "pcp", "pip"):
        assert blocking_bounds(ts, prio, p) == {"hi": 3, "lo": 0}


def test_blocking_ignores_resources_below_priority_level():
    # mid never touches R and the only other user of R (lo2) has lower priority
    ts = TaskSet([
        Task("mid", 10, 2),
        Task("lo1", 20, 0, segments=(Segment("R", 3),)),
        Task("lo2", 30, 0, segments=(Segment("R", 2),)),
    ])
    prio = assign_priorities(ts, "rm")
    assert blocking_bounds(ts, prio, "pcp")["mid"] == 0   # ceiling(R) < p(mid)
    assert blocking_bounds(ts, prio, "npp")["mid"] == 3   # NPP blocks everyone


def test_model_validation():
    with pytest.raises(ValueError):
        Task("bad", 0, 1)
    with pytest.raises(ValueError):
        Task("bad", 5)
    with pytest.raises(ValueError):
        Segment(None, 0)
    with pytest.raises(ValueError):
        TaskSet([Task("a", 5, 1), Task("a", 6, 1)])
