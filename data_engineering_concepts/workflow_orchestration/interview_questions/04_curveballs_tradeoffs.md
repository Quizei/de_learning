# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

A question type that doesn't fit a full scenario or a flash-card definition — the
interviewer takes whatever you just designed (in [file 1](01_worked_scenarios.md)) and
pushes on one assumption. There's rarely one "correct" answer here; what's scored is
whether you reason through the trade-off out loud instead of freezing or giving a one-word
answer. Try answering each before expanding the model answer.

---

**Curveball: "Your DAG has a task that calls three different external APIs, sequentially,
inside one `PythonOperator`. Any problem with that?"**

<details>
<summary>Model answer</summary>

Yes — collapsing three independent external calls into one task throws away parallelism
and, worse, ties their failure/retry behavior together. If API 2 is flaky and API 1 and
API 3 are reliable, a retry of the whole task re-calls all three, including the two that
already succeeded (and may not be idempotent to call again). The fix is splitting into
three separate tasks, each with its own retry policy tuned to that specific API's actual
reliability characteristics, running in parallel where nothing forces them to be
sequential. The only case for keeping them in one task is when a later call genuinely
depends on an earlier one's result and truly cannot be parallelized — worth stating
explicitly rather than assuming, since it's the exception, not the default.

</details>

---

**Curveball: "You've set `retries=5` with exponential backoff on every task in a DAG, as a
blanket policy. What's wrong with that as a strategy?"**

<details>
<summary>Model answer</summary>

A single retry policy applied uniformly ignores that different failure modes call for
different responses. A transient network blip genuinely benefits from a handful of quick
retries. A task failing because of a real bug, a schema mismatch, or bad input data will
fail identically all 5 times, just slower — burning 5x the wall-clock time before reporting
the same failure a first attempt would have surfaced immediately, delaying the alert an
on-call engineer needed to see. Worse, if the task isn't idempotent, blanket retries on
every task risk duplicating side effects on tasks where retrying was never actually safe
(the payment-charge case in `interview_questions/03_critique_and_debug.md`, Case 3). The
stronger answer: retries should be set per task based on (a) whether the failure mode is
plausibly transient at all, and (b) whether the task is actually idempotent — not applied
as one global default.

</details>

---

**Curveball: "Your team is small — two engineers — and just inherited a 200-task Airflow
deployment with dozens of DAGs, most undocumented. Where do you even start?"**

<details>
<summary>Model answer</summary>

Not by reading all 200 tasks. Start from the failure/alert history: which DAGs have
actually paged someone in the last month, and which have been silently green (or silently
never checked) the whole time — that ordering tells you where the real operational risk
actually is, versus where it's merely unfamiliar. In parallel, identify which DAGs feed
something a human actually looks at or acts on (an exec dashboard, a billing run) versus
which produce output nobody has checked in months — the latter are candidates for pausing
outright rather than maintaining, and a shrunken team's first real leverage move is often
turning off things nobody was using. This is the same reasoning
`system_design_performance/interview_questions/04_curveballs_tradeoffs.md`'s "team shrinks"
curveball drills from the architecture side — here it's applied to inherited *operational*
surface area instead of a from-scratch design decision.

</details>

---

**Curveball: "A downstream consumer team says your DAG's data is sometimes late, but your
Airflow UI shows every run finishing well within its historical average duration. What
would you check?"**

<details>
<summary>Model answer</summary>

"The task ran fast" and "the task ran on time" are different claims. The likely gap is
between when the DAG's run was *scheduled/queued* and when it actually *started* — if the
worker pool is saturated (by other DAGs, or by a poke-mode sensor eating slots, per
`interview_questions/03_critique_and_debug.md`, Case 2), a task instance can sit in `queued`
state for a long stretch before a worker frees up, and that queued time doesn't show up in
"task duration" at all — only in the gap between scheduled time and start time. The check:
compare `queued_at` to `started_at` for the tasks in question, not just each task's own
execution duration, and look at overall worker-pool utilization around the times the
consumer reports lateness.

</details>

---

**Curveball: "You migrate from a nightly batch DAG to a DAG triggered by an event (a
message landing in a queue, or a sensor firing) instead of a fixed cron schedule. What
changes about how you have to think about failure handling?"**

<details>
<summary>Model answer</summary>

A cron-scheduled DAG has a bounded, predictable arrival rate — one run per interval, and
`max_active_runs` caps overlap cleanly. An event-triggered DAG's arrival rate is whatever
the upstream event source produces, which can burst (a backlog of queued messages all
arriving at once after an upstream outage clears) far beyond what a fixed schedule ever
would. The failure-handling question shifts from "did this one scheduled run succeed" to
"can the DAG handle N runs firing in a tight burst without exhausting worker capacity or
overwhelming a downstream system it writes to" — `max_active_runs` and pool sizing become
load-shedding decisions, not just correctness ones, and idempotency matters even more,
since an event source redelivering a message it's uncertain was processed (an at-least-once
delivery guarantee) is a completely ordinary occurrence, not an edge case.

</details>

---

**Curveball: "Your DAG's `transform` task reads its input by querying 'yesterday's data'
from a source table using `WHERE event_date = CURRENT_DATE - 1`. What's the risk?"**

<details>
<summary>Model answer</summary>

This is the same trap as reading `datetime.now()` instead of the DAG Run's logical date
(`concepts/01_dag_fundamentals.md`, section 4), expressed in SQL instead of Python. On a
normal daily run it happens to give the right answer, because "when this task runs" and
"the date it's processing" are the same day, minus one. The moment this DAG is rerun for a
past date, or backfilled for a historical range, `CURRENT_DATE` still evaluates to *today*,
not the logical date being processed — every backfilled run silently pulls the same
(actual) yesterday's data instead of the correct historical date, and produces plausible,
wrong output with no error at all. The fix: the query must be parameterized on the DAG
Run's logical date (`{{ ds }}` in Airflow templating, or the equivalent in another
orchestrator), never on the database's own notion of "now."

</details>

---

**Curveball: "Two teams both want to add tasks to the same shared DAG — one team's tasks
depend on the other's output. How do you handle DAG ownership as the org grows?"**

<details>
<summary>Model answer</summary>

A single shared DAG with cross-team dependencies inside it is a coordination bottleneck
waiting to happen — either team's change to their own tasks risks breaking the DAG's
import for everyone, and "whose on-call gets paged" becomes ambiguous the moment a shared
DAG fails. The stronger pattern at that point is splitting into two DAGs, one per team,
wired together with a cross-DAG dependency mechanism (Airflow's `ExternalTaskSensor`,
or a dataset/asset-based trigger in newer Airflow versions and in Dagster's asset model) —
each team owns, deploys, and gets paged for their own DAG independently, and the
dependency between them is an explicit, visible contract (a sensor waiting on the other
team's DAG's completion) rather than an implicit shared file both teams edit. This is
effectively the same "conformed" reasoning `data_modeling`'s conformed-dimension curveball
applies to schema ownership, applied here to pipeline ownership instead.

</details>
