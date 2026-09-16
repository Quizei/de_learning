# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design and triage conversations. This file
is the other interview mode: **fast, direct definitional questions** with no scenario
attached — the kind asked in a phone screen, or dropped mid-conversation to check you
actually understand a term you just used. Answer each one out loud in under 30 seconds
before reading the model answer.

Every term used here is demonstrated somewhere in `concepts/` or in file 1 — the
cross-references point back to the concrete moment it showed up.

---

## Foundational

**Q: What is a DAG, and why does it have to be acyclic?**
> A Directed Acyclic Graph: nodes are tasks, edges are dependencies ("A must finish before
> B starts"). It has to be acyclic because a cycle (`A -> B -> A`) makes no valid execution
> order exist at all — A can't finish before B, which can't finish before A. Orchestrators
> validate this at parse time and refuse to schedule a cyclic DAG.
> (`concepts/01_dag_fundamentals.md`, section 1.)

**Q: What's the difference between a DAG, a DAG Run, and a Task Instance?**
> A DAG is the template (tasks + dependencies). A DAG Run is one concrete execution of that
> template for a specific interval. A Task Instance is one task, within one specific DAG
> Run — its state is independent of the same task in any other run.
> (`concepts/01_dag_fundamentals.md`, section 4.)

**Q: What's `execution_date`/`logical_date`, and why does it surprise people?**
> It's the START of the interval a run is FOR, not the wall-clock time it actually runs. A
> `@daily` DAG's `2024-01-15` run typically doesn't start executing until after midnight on
> the 16th, once that full interval has elapsed. A task that uses `datetime.now()` instead
> of its logical date silently breaks under backfill or rerun.
> (`concepts/01_dag_fundamentals.md`, section 4.)

**Q: How does topological sort relate to what a scheduler actually does?**
> It's the mechanism, not an analogy — Kahn's algorithm repeatedly finds tasks with no
> unmet dependency (in-degree 0), "runs" them, removes their outgoing edges, and repeats.
> Tasks that become ready in the same pass can run in parallel; that's the formal
> definition of "what can fan out" in a DAG. (`concepts/01_dag_fundamentals.md`, section 3.)

---

## Operators & Sensors

**Q: What's the difference between an operator and a sensor?**
> An operator does something (run Python, run a shell command, execute SQL). A sensor is a
> specialized operator whose entire job is to wait, repeatedly checking ("poking") a
> condition until it's true or a timeout is hit. (`concepts/02_operators_sensors.md`,
> section 2.)

**Q: Poke mode vs. reschedule mode vs. a deferrable operator — what's the actual
difference?**
> Poke mode holds a full worker slot for the entire wait, sleeping between checks —
> cheapest to write, most expensive to run. Reschedule mode frees the worker slot between
> checks and re-queues itself. A deferrable operator doesn't occupy a worker at all while
> waiting — it hands off to an async triggerer process. A long-waiting sensor left in poke
> mode is a classic way to silently exhaust a worker pool.
> (`concepts/02_operators_sensors.md`, section 2.)

**Q: What is XCom, and what's the one rule everyone needs to know about it?**
> Airflow's mechanism for passing small pieces of data between tasks — a task's return
> value is auto-pushed, downstream tasks pull it. The rule: XCom is for small metadata
> (counts, paths, flags), never for passing actual data payloads like a DataFrame — the
> metadata database isn't built to hold that, and most orchestrators cap XCom size for
> exactly this reason. (`concepts/02_operators_sensors.md`, section 3.)

**Q: When would you write a custom operator instead of a plain PythonOperator?**
> Once the same connection/auth/retry logic is copy-pasted across enough DAGs that it's
> worth naming and reusing — a custom operator also validates its parameters at DAG-parse
> time rather than failing deep inside a function body at runtime, and shows up in the UI
> under its own name instead of as an anonymous callable.
> (`concepts/02_operators_sensors.md`, section 4.)

---

## Scheduling & Dependencies

**Q: What's `catchup`, and why is `catchup=True` a common production incident on its own?**
> `catchup` decides whether every missed interval between `start_date` and now gets
> scheduled immediately (`True`, historically the default) or only the most recent interval
> going forward (`False`). Deploying a new DAG with a `start_date` set months in the past
> under `catchup=True` immediately queues every missed interval at once — a completely
> unintended backfill nobody asked for. (`concepts/05_backfills_and_catchup.md`, section 2.)

**Q: Name the trigger rules and what each means.**
> `all_success` (default: every parent succeeded), `all_failed`, `all_done` (every parent
> reached ANY terminal state), `one_success`, `one_failed`, `none_failed` (no parent
> failed — success or skipped both count), `none_skipped`.
> (`concepts/03_scheduling_dependencies.md`, section 3.)

**Q: A task's upstream failed. What state does the task itself end up in, and does that
propagate?**
> `skipped`, not `pending` or `failed` — and yes, that `skipped` state propagates forward
> through every subsequent `all_success` task all the way to the end of the DAG, unless
> something downstream has a trigger rule (`all_done`, `none_failed`) specifically designed
> to catch it. A cleanup/notification task has to opt out of the default explicitly to run
> regardless of upstream failure. (`concepts/03_scheduling_dependencies.md`, section 3.)

**Q: What does `max_active_runs` actually control?**
> How many DAG Runs of the SAME DAG can be running concurrently — `max_active_runs=1`
> means run #2 physically cannot start until run #1 finishes. It governs concurrency
> *across* runs, not dependency order *within* one run.
> (`concepts/03_scheduling_dependencies.md`, section 5.)

**Q: What does `depends_on_past=True` do, and when is it actually correct?**
> Forces a task in today's run to wait for the SAME task in yesterday's run to succeed
> before starting — strict serialization across runs, task by task. Correct for a genuinely
> accumulating computation (a running balance); wrong for stateless/idempotent tasks, where
> it just adds needless serialization and can turn a parallelizable backfill into a slow,
> forced-sequential one. (`concepts/05_backfills_and_catchup.md`, section 6.)

---

## Error Handling & Retries

**Q: Why add jitter to exponential backoff instead of just backing off?**
> Backoff alone still lets every task that failed at the same instant retry in perfect
> unison — recreating the same load spike against a recovering dependency (a "thundering
> herd"). Jitter adds randomness on top so retries spread out instead of syncing up.
> (`concepts/04_error_handling_retries.md`, section 1.)

**Q: What's the difference between an SLA and a timeout in Airflow?**
> An SLA alerts if a task/DAG takes longer than expected — the task keeps running. A
> timeout forcibly kills the task once it exceeds a duration. Confusing these ("the SLA
> kills the task") is a specific, checkable tell in an interview answer.
> (`concepts/04_error_handling_retries.md`, section 3.)

**Q: What's a dead letter queue, and what's the one thing people get wrong about the
threshold?**
> A DLQ isolates individually bad records so a task doesn't fail wholesale over a small bad
> fraction of a batch. The mistake: treating the DLQ as an unconditional escape valve — a
> failure ratio high enough (say 30-50%) is itself a signal the source data is
> systemically broken, and the pipeline should halt and alert rather than silently
> quarantine half the day's data and continue.
> (`concepts/04_error_handling_retries.md`, section 4.)

**Q: How is a circuit breaker different from a retry policy?**
> A retry policy assumes ONE call's failure is transient and retries the same call. A
> circuit breaker tracks failures across MANY calls and, past a threshold, stops even
> attempting the call for a cooldown period, assuming the dependency is systemically down.
> They compose — a retry loop behind a tripped circuit breaker fails fast without spending
> its retries at all. (`concepts/04_error_handling_retries.md`, section 5.)

**Q: Why is idempotency load-bearing for retries specifically, not just nice to have?**
> Retrying a non-idempotent task (an insert, a charge, a send) after a failure that
> happened AFTER the side effect but BEFORE the success response risks duplicating that
> side effect — a network timeout on the response, not the request, makes this an ordinary
> occurrence, not an edge case. A retry policy is a band-aid over a non-idempotent task, not
> a substitute for making the task idempotent.
> (`concepts/04_error_handling_retries.md`, section 2b.)

---

## Backfills & Catchup

**Q: What's the difference between `catchup` and a deliberate backfill?**
> Mechanically identical — both schedule historical DAG Runs. The difference is intent and
> control: catchup is an automatic side effect of a DAG's `start_date`/schedule; a backfill
> is triggered on purpose, for a chosen range, at a chosen concurrency.
> (`concepts/05_backfills_and_catchup.md`, sections 2-3.)

**Q: What's the one precondition that has to be true before you backfill anything?**
> Every task has to be idempotent — reprocessing a date must replace exactly that date's
> rows (delete-then-insert on a partition key, or an upsert on a stable natural key), never
> append on top of what's already there. Backfilling a non-idempotent DAG doesn't fix bad
> data, it corrupts it a second way. (`concepts/05_backfills_and_catchup.md`, section 4.)

**Q: How do you keep a backfill from competing with a DAG's live production runs?**
> A dedicated worker pool for the backfill's task instances (separate from production's),
> a throttled concurrency for the backfill itself (`max_active_runs`/`-j`), and per-date
> partitioned writes so historical and live writes can never race the same rows.
> (`concepts/05_backfills_and_catchup.md`, section 5.)
