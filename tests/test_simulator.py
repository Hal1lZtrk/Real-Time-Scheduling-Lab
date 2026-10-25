import pytest

from rtlab import Task, TaskSet, simulate
from rtlab.scenarios import chained_blocking, plc_task_classes, priority_inversion, rm_vs_edf


def run(scenario, protocol):
    ts, prio, horizon = scenario
    return simulate(ts, "fixed", protocol, horizon, prio)


def test_rm_misses_edf_meets():
    ts = rm_vs_edf()
    rm = simulate(ts, "rm")
    edf = simulate(ts, "edf")
    assert any(m.task.name == "tau2" for m in rm.misses)
    assert not edf.misses
    assert rm.max_response("tau2") == 8


def test_trace_has_one_slot_per_tick_and_work_is_conserved():
    ts = rm_vs_edf()
    r = simulate(ts, "edf", horizon=35)
    assert len(r.slots) == 35
    busy = sum(1 for s in r.slots if s.task)
    done_work = sum(j.task.wcet for j in r.jobs if j.finish is not None)
    assert busy >= done_work


@pytest.mark.parametrize(
    "protocol,high_response,med_response",
    [("none", 11, 6), ("pip", 5, 10), ("pcp", 5, 10), ("hlp", 5, 10), ("npp", 5, 10)],
)
def test_priority_inversion_scenario(protocol, high_response, med_response):
    r = run(priority_inversion(), protocol)
    high = r.jobs_of("high")[0]
    med = r.jobs_of("med")[0]
    assert high.response == high_response
    assert med.response == med_response
    assert r.missed(high) == (protocol == "none")


def test_unbounded_inversion_only_without_protocol():
    r_none = run(priority_inversion(), "none")
    assert "med#0" in r_none.jobs_of("high")[0].inverters
    for p in ("pip", "pcp", "hlp", "npp"):
        assert "med#0" not in run(priority_inversion(), p).jobs_of("high")[0].inverters


def test_pcp_prevents_chained_blocking_but_pip_does_not():
    pip = run(chained_blocking(), "pip").jobs_of("high")[0]
    pcp = run(chained_blocking(), "pcp").jobs_of("high")[0]
    assert pip.inverters == {"low1#0", "low2#0"} and pip.response == 6
    assert pcp.inverters == {"low2#0"} and pcp.response == 3


def test_edf_rejects_ceiling_protocols():
    with pytest.raises(ValueError):
        simulate(rm_vs_edf(), "edf", "pcp")
    with pytest.raises(ValueError):
        simulate(rm_vs_edf(), "rm", "nonsense")


def test_plc_scenario_long_vs_short_critical_section():
    ts, prio, h = plc_task_classes(short_critical_section=False)
    long_cs = simulate(ts, "fixed", "pcp", h, prio)
    ts, prio, h = plc_task_classes(short_critical_section=True)
    short_cs = simulate(ts, "fixed", "pcp", h, prio)
    assert long_cs.misses and any(m.task.name == "motion" for m in long_cs.misses)
    assert not short_cs.misses


def test_phase_and_deadline_miss_at_horizon_edge():
    ts = TaskSet([Task("late", period=10, wcet=6, deadline=5)])
    r = simulate(ts, "rm", horizon=6)
    assert r.misses and r.misses[0].finish == 6
