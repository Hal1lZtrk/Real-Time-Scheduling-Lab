# Design notes

Decisions made while building the lab, and why.

## Time is discrete

Everything is integer ticks. That keeps the simulator exact (no floating-point drift) and the response times directly comparable with the analysis. A job released at tick t competes for the CPU in tick t.

## The simulator in one loop

For every tick:

1. **Release** the jobs whose release time is now.
2. **Find the blocked jobs:** a job whose next segment needs a resource that it cannot get (held by someone else, or, under PCP, blocked by the system ceiling). Each blocked job points at the job responsible.
3. **Effective priorities:** start from nominal priorities; NPP and HLP boost the lock holders; PIP and PCP propagate the priority of blocked jobs to their holders until nothing changes (this also handles transitive chains).
4. **Pick** the non-blocked job with the highest effective priority (ties: earlier release first, then task order). Under EDF the "priority" is the negated absolute deadline.
5. **Lock** the resource if the picked job is entering a critical section.
6. **Record** the tick (who ran, whether boosted, who was blocked, priority-inversion bookkeeping).
7. **Execute** one tick; release the lock when the critical section ends.

A job that misses its deadline keeps running to completion and the miss is recorded; the simulator does not abort jobs.

## Why critical sections are not nested

With nesting, locks can deadlock under plain mutex or PIP, and the blocking bounds become more complicated. Non-nested sections are enough to show priority inversion, inheritance, ceilings and chained blocking, and they allow exact, simple bounds. A deadlock check exists in the simulator (a `RuntimeError` if every ready job is blocked) as a safety net.

## Why EDF has only `none` and `npp`

Ceiling-based protocols assume static priorities. Their EDF counterpart is the Stack Resource Policy, which uses preemption levels and is not implemented here.

## Why "priority inversion time" is measured separately from "blocked time"

Under HLP and NPP a high-priority job never sits in a "blocked on lock" state: it just does not get the CPU while the boosted low-priority job runs. Counting only lock-wait ticks would hide the blocking. The lab therefore counts every tick in which a lower-priority job runs while the job is waiting, regardless of why. That number is what the blocking bound B<sub>i</sub> limits.

## Questions this repository should help me answer in an interview

- Why can a task set with U = 0.6 miss a deadline? (Blocking; the utilization tests ignore it.)
- What is the difference between priority inheritance and the priority ceiling protocol? (PIP reacts when blocking happens and allows chained blocking; PCP prevents it by refusing locks in advance.)
- Why is HLP simple to implement? (No dynamic bookkeeping: raise priority at lock, restore at unlock.) What is its cost? (Tasks are delayed even if the resource would not have been contended.)
- Why is response-time analysis exact only up to the first rejected task? (Earlier jobs of a higher-priority task can overrun into the next period; the formula assumes they do not.)
- Why does RM fail where EDF works for the same U? (Fixed priorities cannot always use 100 % of the CPU; the guaranteed fraction is n(2^(1/n) − 1).)
