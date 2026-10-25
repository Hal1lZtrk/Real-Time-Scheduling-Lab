"""The analysis and the simulator are independent implementations. They must agree."""

import pytest

from rtlab.validate import cross_validate


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_analysis_matches_simulation(seed):
    result = cross_validate(n_sets=400, seed=seed)
    c = result["counts"]
    assert result["failures"] == [], "\n".join(result["failures"][:5])
    # make sure the checks were not vacuous
    assert c["A_exact_checks"] > 500
    assert c["A_reject_checks"] > 20
    assert c["B_feasible"] > 50 and c["B_infeasible"] > 50
    assert c["C_accepted_sets"] > 500
    assert c["C_tasks_with_blocking"] > 50
