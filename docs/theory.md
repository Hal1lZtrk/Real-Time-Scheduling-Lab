# Theory primer

A short summary of the ideas the lab implements, in the notation used in the code. Details and proofs are in the textbooks listed in the README.

## Task model

A periodic task τ<sub>i</sub> releases a *job* every T<sub>i</sub> ticks. Each job needs C<sub>i</sub> ticks of CPU and must finish within D<sub>i</sub> ticks of its release (default D<sub>i</sub> = T<sub>i</sub>). Utilization is U = Σ C<sub>i</sub> / T<sub>i</sub>. The *hyperperiod* is lcm(T<sub>i</sub>); the schedule repeats after it.

## Fixed priorities: RM and DM

Rate Monotonic gives the highest priority to the shortest period; Deadline Monotonic to the shortest relative deadline. Both are optimal among fixed-priority assignments (RM for D = T, DM for D ≤ T).

- **Liu-Layland bound:** n tasks are schedulable under RM if U ≤ n(2<sup>1/n</sup> − 1). The bound tends to ln 2 ≈ 0.693. It is sufficient, not necessary.
- **Hyperbolic bound:** Π(U<sub>i</sub> + 1) ≤ 2. Also sufficient and less pessimistic.
- **Response-time analysis (exact for D ≤ T):** the worst case is when all tasks are released together (critical instant).

  R<sub>i</sub> = C<sub>i</sub> + B<sub>i</sub> + Σ<sub>j ∈ hp(i)</sub> ⌈R<sub>i</sub> / T<sub>j</sub>⌉ C<sub>j</sub>

  Start with R<sub>i</sub> = C<sub>i</sub> + B<sub>i</sub>, iterate until the value stops changing; the task is schedulable if R<sub>i</sub> ≤ D<sub>i</sub>. B<sub>i</sub> is the blocking term (below).

## EDF

Earliest Deadline First always runs the job with the nearest absolute deadline. For D = T it is feasible exactly when U ≤ 1. For D < T the exact test is the *processor demand criterion*: for every t, the work that must be finished by t, dbf(t) = Σ max(0, ⌊(t − D<sub>i</sub>) / T<sub>i</sub>⌋ + 1) · C<sub>i</sub>, must not exceed t.

## Shared resources and priority inversion

When tasks share a resource protected by a lock, a high-priority task can wait for a low-priority lock holder. That is acceptable if the wait is bounded by the critical section. It becomes **priority inversion** when a medium-priority task preempts the holder, so the wait is no longer bounded by anything in the high-priority task's own design.

| Protocol | Rule | Blocking bound B<sub>i</sub> (non-nested sections) |
|---|---|---|
| NPP | holder runs non-preemptively | longest critical section of any lower-priority task |
| HLP (immediate ceiling) | on locking, holder runs at the *ceiling* of the resource (highest priority of its users) | longest critical section of a lower-priority task on a resource with ceiling ≥ p<sub>i</sub> |
| PIP | holder inherits the priority of the highest job it blocks | min(Σ over lower tasks, Σ over resources) of those longest sections; a job may be blocked several times (chained blocking) |
| PCP | a job may lock only if its priority is higher than the ceilings of all resources locked by *other* jobs; otherwise it blocks and the responsible holder inherits | same as HLP; a job is blocked at most once |

Only critical sections of lower-priority tasks on resources with ceiling ≥ p<sub>i</sub> can block τ<sub>i</sub>. That includes sections on resources τ<sub>i</sub> never touches, as long as a higher-priority task uses them (*push-through blocking*).

## What the utilization bound does not tell you

The Liu-Layland and hyperbolic tests ignore blocking. A task set can pass them and still miss a deadline because a slow task holds a lock for too long. That is the PLC example in the README.
