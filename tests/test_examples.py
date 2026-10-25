import os

from rtlab import assign_priorities, load_taskset
from rtlab.analysis import edf_feasible, fp_schedulable, utilization
from rtlab.scenarios import plc_task_classes

HERE = os.path.dirname(__file__)


def ex(name):
    return load_taskset(os.path.join(HERE, "..", "examples", name))


def test_json_examples_match_scenarios():
    for short, name in ((False, "plc_cyclic_classes_long_cs.json"), (True, "plc_cyclic_classes_short_cs.json")):
        ts_json = ex(name)
        ts_code, _, _ = plc_task_classes(short)
        assert [(t.name, t.period, t.segments) for t in ts_json] == [(t.name, t.period, t.segments) for t in ts_code]


def test_utilization_test_is_not_enough_with_shared_resources():
    ts = ex("plc_cyclic_classes_long_cs.json")
    prio = assign_priorities(ts, "rm")
    assert utilization(ts) == 0.6                      # well below the RM bound for 3 tasks (0.78)
    assert not fp_schedulable(ts, prio, "pcp")[0]      # but blocking makes 'motion' miss
    assert fp_schedulable(ex("plc_cyclic_classes_short_cs.json"), prio, "pcp")[0]


def test_rm_vs_edf_example():
    ts = ex("rm_vs_edf.json")
    assert edf_feasible(ts)[0]
    assert not fp_schedulable(ts, assign_priorities(ts, "rm"))[0]
