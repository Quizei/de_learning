# 3. Critique & Debug: "What's Wrong With This?"

Part of the [Interview Questions](README.md) series.

A different interview mode from [file 1](01_worked_scenarios.md): instead of "design
something from scratch," you're handed a DAG, a config, or an on-call symptom and asked
**"what's wrong with this?"** This tests whether you can *read* an orchestration setup
critically, not just produce one. Every case below is described in plain prose — no DAG
code — because the skill being tested is spotting the flaw from a description, the same way
it'd be described to you out loud in an interview.

Read the symptom, form your diagnosis, then expand the debrief.

---

## Case 1: The Hidden Circular Dependency

**Setup:** A DAG has `extract -> transform -> load`. Later, someone adds a `validate_load`
task after `load` that reconciles row counts, and wires it as
`load -> validate_load -> transform` — the idea being "if validation fails, retry the
transform." The DAG fails to even appear in the UI; it shows up as a DAG import error
instead of a red/failed run.

<details>
<summary>Debrief</summary>

**Diagnosis:** `load -> validate_load -> transform` closes a cycle:
`transform -> load -> validate_load -> transform`. The intent ("if validation fails, redo
the transform") is reasonable, but expressing it as a dependency edge back to an *upstream*
task is not how a DAG can express "retry a previous step" — a DAG's edges are a one-way
execution order, not a state machine with loops. Airflow's DAG parser rejects this at
import time, which is why it never even reaches a scheduled run.

**Fix:** "retry a previous step based on a later step's result" isn't a DAG dependency at
all — it's either (a) a validation check performed *before* declaring the extract/transform
step done (move the check earlier, so there's nothing to loop back to), or (b) a
task-level retry/sensor loop *within* a single task rather than a graph edge, or (c) two
separate DAG runs with an explicit human or automated decision in between, not an automatic
graph cycle.

**The interview tell:** recognizing immediately that "retry an earlier step" is not
expressible as a plain dependency edge — and that reaching for a cycle to express it is
the bug — rather than trying to find some clever wiring that makes the cycle "work."

</details>

---

## Case 2: The Sensor That Ate the Worker Pool

**Setup:** A DAG has a `FileSensor` waiting for a partner's file to land in S3, configured
with `poke_interval=60`, `timeout=14400` (4 hours), and no `mode` specified (defaulting to
`poke`). On a day the partner runs late, three separate DAG runs end up with this sensor
active simultaneously. Unrelated DAGs across the whole Airflow instance start failing to
schedule at all, with no errors in their own logs.

<details>
<summary>Debrief</summary>

**Diagnosis:** `mode='poke'` (the default) holds a full worker slot for the entire wait —
sleeping, but still occupying a slot — rather than releasing it between checks. Three
instances of a 4-hour sensor in poke mode can tie up three worker slots for hours doing
nothing but sleeping. If the worker pool is small, that's enough to starve every *other*
DAG in the instance of a slot to run in, and because those other DAGs aren't erroring —
they're just queued, waiting for a free worker — there's nothing in their own logs to point
at the real cause.

**Fix:** `mode='reschedule'` releases the worker slot between pokes and re-queues the sensor
task for its next check instead of holding a slot the whole time — the standard fix for any
sensor that can realistically wait more than a few minutes. Where available, a deferrable
version of the same sensor is stronger still: it doesn't occupy a worker at all while
waiting, handing off to an async triggerer process instead.

**The interview tell:** connecting an *unrelated* DAG's scheduling stall to a sensor in a
completely different DAG is the actual diagnostic skill here — the failure surfaces
somewhere that looks disconnected from its cause, which is exactly what makes this a
realistic on-call symptom rather than a textbook one.

</details>

---

## Case 3: The Retry Policy That Made a Bad Situation Worse

**Setup:** A task calls a payment-processing API to charge a customer and record the
charge in a `charges` table. It's configured with `retries=3` and a fixed 5-second delay,
"to handle flaky network calls." After a deploy, customer support starts getting complaints
about duplicate charges. Investigation shows the payment API IS occasionally slow to
respond, but is actually succeeding on the far side even when the task's own HTTP call
times out.

<details>
<summary>Debrief</summary>

**Diagnosis:** the task is not idempotent — retrying it after an ambiguous failure (the
charge succeeded on the payment provider's side; only the response back to the task timed
out) causes the exact same charge to be submitted again on the next attempt. The retry
policy is doing exactly what it was configured to do; the bug is that it was ever safe to
apply blind retries to this specific task in the first place. This is the textbook case of
a retry policy actively making a non-idempotent task *worse* on failure, not better — three
retries against a flaky-but-often-successful call means up to four real charge attempts
for what looks like "one" logical charge.

**Fix:** the task needs to be made idempotent before it's safe to retry at all — typically
by generating an idempotency key per logical charge and passing it to the payment provider
(most payment APIs support exactly this), so the provider itself deduplicates retried
requests with the same key rather than processing each attempt as a new charge. Only once
that's true is `retries=3` actually safe to leave configured; removing the retries instead
of fixing the underlying idempotency problem would just trade "duplicate charges" for
"legitimate transient failures go unretried and silently fail."

**The interview tell:** correctly refusing to "fix" this by just lowering `retries` to 0 —
that only hides the actual defect (the task isn't safe to retry) instead of fixing it, and
leaves genuinely transient failures unhandled.

</details>

---

## Case 4: `catchup=True` Silently Triggers Years of Backfill Runs

**Setup:** A data engineer writes a new DAG to compute a metric that's needed going
forward, sets `start_date=datetime(2021, 1, 1)` out of habit (copied from another DAG's
template), and deploys it. Within minutes of deploying, the warehouse's query queue is
saturated, several unrelated jobs start timing out, and the on-call engineer for a
completely different team is paged.

<details>
<summary>Debrief</summary>

**Diagnosis:** `catchup` was left at its default (`True` in the Airflow version in use).
The moment the DAG was deployed and un-paused, the scheduler queued a DAG Run for **every**
daily interval between `2021-01-01` and today — several years' worth, all at once, each one
hitting the same warehouse the rest of the company's DAGs are actively using. Nobody asked
for a backfill; it happened as an unintended side effect of a `start_date` that was copied
from an unrelated template without thinking about what it meant for *this* DAG's rollout.

**Fix:** `catchup=False` should be the default posture on any new DAG unless a deliberate,
scoped backfill is genuinely intended at deploy time — and if history genuinely does need
to be populated, that should be run explicitly (via a scoped `airflow dags backfill`
command with its own concurrency limits and pool, per
`concepts/05_backfills_and_catchup.md`, section 5) as a conscious, controlled action, never
as whatever `catchup` happens to default to.

**The interview tell:** naming that the root cause is a `start_date` copy-pasted without
considering its consequence under the DAG's `catchup` setting — not "catchup is a bad
feature" in the abstract, since catchup is exactly the correct behavior when it's actually
wanted (e.g., a scheduler outage causing a few missed days that genuinely should run once
it's back).

</details>

---

## Case 5: The Dashboard That Silently Went Stale

**Setup:** A daily DAG feeding an executive dashboard has been "green" (all tasks
succeeded) every day for three weeks. A VP notices the dashboard's numbers haven't actually
changed in that entire time. Every task instance shows `SUCCESS`.

<details>
<summary>Debrief</summary>

**Diagnosis:** "the task succeeded" and "the task did the right thing" are different
claims, and this DAG only ever verified the first one. A task can complete without error
while silently processing zero new rows, reading from a stale cached extract, or writing to
the wrong partition — none of which raises an exception, so none of which shows up as a
failed task instance. This is a data-quality gap sitting immediately adjacent to
orchestration: the DAG's job is proven to have *run*, but nothing in it asserts that the
*output* actually changed or matched expectations.

**Fix:** add an explicit check task, distinct from "did the callable throw" — a row-count
delta check against the previous run, a freshness assertion on the source data's own
timestamp column, or a small assertion on a known aggregate — and make failing that check
a real task failure, not a log line nobody reads. This is squarely the domain
`data_quality_governance` covers in depth; the orchestration-specific lesson here is
narrower: **a green DAG run is proof of "no exception was thrown," not proof of "the data is
correct,"** and conflating the two is exactly how a three-week-stale dashboard survives
every single run undetected.

**The interview tell:** not reaching for "add more logging" as the fix — the logs almost
certainly already showed zero rows processed each day, and nobody was looking. The actual
fix is turning that already-visible fact into an assertion that can fail the task, not
adding more information that's just as easy to ignore.

</details>
