# Validation

## Idea

`rtlab/analysis.py` and `rtlab/simulator.py` do not share code for scheduling decisions. If both produce the same answer on a large number of random inputs, a mistake in either one is unlikely to hide. `rtlab/validate.py` implements three families of checks.

## Random task sets

Periods are drawn from {4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 40, 60}; all divide 120, so the hyperperiod is at most 120 ticks and every simulation can cover it fully. Utilization is spread randomly over the tasks. Optional parts: constrained deadlines (D between C and T), random task phases, and one or two non-nested critical sections per task on up to three resources.

| Family | Setup | Assertion |
|---|---|---|
| A | RM/DM, no resources, synchronous release | For every task up to the first one the analysis rejects, simulated worst-case response time equals the analytic R<sub>i</sub>. The first rejected task really misses its first deadline. (Below that task the analysis is not exact because earlier jobs may overrun, so nothing is claimed.) |
| B | EDF, no resources | `edf_feasible()` says feasible if and only if the simulation over hyperperiod + max D shows no miss. |
| C | RM with NPP, HLP, PIP, PCP; random phases | If the analysis (with the protocol's blocking bound) accepts the set: no miss in the simulation; every measured response ≤ analytic bound; every measured priority-inversion time ≤ B<sub>i</sub>; under NPP/HLP/PCP no job is blocked by more than one lower-priority job. |

"Priority-inversion time" of a job counts the ticks in which the job is released and unfinished while a lower-priority job runs.

## Results

`python -m rtlab validate --sets 2000 --seed 42`:

```text
A_exact_checks                  6731      (all equal)
A_reject_checks                 701       (all confirmed)
B_checks                        2000      (1186 feasible, 814 infeasible; all agree)
C_task_checks                   29900     (7580 accepted set/protocol runs)
C_tasks_with_blocking           1233
C_within_one_tick_of_bound      842
failures: 0
```

## Do the checks actually bite?

A test suite that cannot fail proves nothing. I broke the code on purpose and re-ran 500 sets each time:

| Deliberate bug | Failures reported |
|---|---|
| NPP blocking bound forced to 0 | 410 |
| PIP blocking bound forced to 0 | 114 |
| PCP blocking bound forced to 0 | 115 |
| Response-time analysis off by one | 1811 |
| Simulator: HLP priority boost removed | 8 |
| Simulator: priority inheritance removed | 10 |
| Simulator: PCP ceiling rule removed | 0 (see below) |

The PCP ceiling rule only changes behaviour when a job holds one lock and another job asks for a second, free lock whose acquisition would create chained blocking. Random sets almost never produce that, so a deterministic test covers it: `test_pcp_prevents_chained_blocking_but_pip_does_not` fails when the rule is removed.

## What is *not* validated

- The simulator is checked against the theory, not against a real RTOS or a real PLC.
- Nested critical sections, multicore, overheads and release jitter are out of scope.
- The counts above come from seed 42 on the code in this repository; other seeds give other counts, and the number of failures should stay zero.
