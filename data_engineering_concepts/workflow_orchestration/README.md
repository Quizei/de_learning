# Workflow Orchestration

## Why This Matters

Pipelines don't run themselves. Every data engineering interview loop that goes past a
pure-SQL round eventually asks some version of "how do you schedule and monitor this" —
and the reasoning behind that question (dependency graphs, retries, idempotency, what
happens when a task fails at 3am) is the same reasoning you use every time you're on call
for a production pipeline. **Airflow is still the orchestrator most interviews ask about by
name**, which is why this folder is Airflow-centric — but every concept here is taught in
orchestrator-agnostic terms first (DAGs, idempotent tasks, backfills, event-driven
triggers, SLAs) specifically so it transfers cleanly if an interviewer asks about Dagster,
Prefect, or Mage instead, which happens increasingly often.

The bar for this topic isn't "can you write a DAG" — it's **can you reason about a pipeline
as a live, operated system**: what happens when one of forty tasks fails, whether it's safe
to backfill six months of history while today's run is also in flight, and what you
actually do, in order, the moment a critical DAG pages you at 3am. That operational half is
tested at least as often as the DAG-design half, and it's the harder half to fake.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like notes, real runnable
  (dependency-free) Python wherever the topic needs it, an ASCII diagram where one helps
- `practice/` — DAG-design and implementation exercises, with the answer hidden in a
  collapsible block so you can quiz yourself, plus a scoped "hard" coding problem that
  builds a mini orchestration engine in three parts
- `interview_questions/` — a five-file, code-free drill covering every shape a real
  orchestration interview tends to take: worked design/triage scenarios, rapid-fire
  definitions, critique-a-broken-DAG, curveball trade-offs, and a dedicated on-call/incident
  triage drill
- `projects/` — one capstone project brief that has you implement a reusable
  `PipelineOrchestrator` class, not just recognize the concepts behind one

Every `concepts/*.md` file follows the same shape:
1. **Covers** — the bullet list of sub-topics in that file
2. One `##`/`###` section per sub-topic: prose explanation (the "why," not just the "how")
   → an ASCII diagram where one helps → real, runnable, dependency-free Python → a worked
   example with its actual output shown in a separate block
3. Ends with a **Key Takeaways** summary

Every Python block is plain, copy-pasteable, and needs nothing beyond the standard library
— paste it into a `python3` shell and it runs exactly as shown. Nothing needs a real Airflow
install to follow along.

---

## How to Use This Folder

Work through it in this order:

1. **`concepts/`** (01 → 05) — the vocabulary: what a DAG actually guarantees, what an
   operator/sensor does versus what the DAG itself decides, how scheduling and trigger
   rules interact, how retries/SLAs/circuit breakers fit together, and — its own dedicated
   file — how backfills and `catchup` actually work. Read these first; everything else
   assumes this vocabulary.
2. **`practice/exercises.md`** — apply the vocabulary directly: compute execution order,
   write cron expressions, detect cycles, design a DAG for a real scenario, resolve trigger
   rules by hand, implement retry-with-backoff, wire cross-task data passing, and design a
   failure-handling strategy end to end. Commit to an answer before expanding each solution.
3. **`practice/coding_problems.md`** — a single interview-length "hard" problem, built in
   three parts (execute a DAG in order → add retries → persist state so a failed run can
   resume), covering exactly the three mechanisms an orchestration engine is built from.
4. **`interview_questions/`** — the conversation an interviewer actually scores, rehearsed
   end to end: DAG design walkthroughs, safe-backfill and 3am-incident scenarios,
   rapid-fire definitions, critique-the-broken-DAG cases, curveball follow-ups, and a
   dedicated on-call/incident-triage drill. See `interview_questions/README.md` for how the
   five files fit together.
5. **`projects/pipeline_orchestrator.md`** — a capstone that asks you to build a small,
   reusable orchestration engine: topological execution, retries, and — the part that
   makes it more than a toy — durable state so a partially-failed run can be resumed
   without redoing completed work.

---

## Topics Covered

### Concepts

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | DAG Fundamentals | `concepts/01_dag_fundamentals.md` | "What is a DAG, and why is it directed and acyclic?" / "How does a scheduler decide what to run next?" |
| 2 | Operators & Sensors | `concepts/02_operators_sensors.md` | "What's the difference between an operator and a sensor?" / "Poke mode vs. reschedule mode?" |
| 3 | Scheduling & Dependencies | `concepts/03_scheduling_dependencies.md` | "Write a cron expression for X" / "What are trigger rules, and how do they interact with skipped tasks?" |
| 4 | Error Handling & Retries | `concepts/04_error_handling_retries.md` | "How do you handle task failures?" / "SLA vs. timeout — what's the difference?" |
| 5 | Backfills & Catchup | `concepts/05_backfills_and_catchup.md` | "How would you backfill 6 months of history without breaking today's live run?" / "What does `catchup=True` actually do?" |

### Interview Questions

`interview_questions/` is a five-file, code-free drill:

1. [Worked Scenarios](interview_questions/01_worked_scenarios.md) — full mock-interview
   walkthroughs: designing a 40-task multi-source DAG, safely backfilling six months of
   live history, and triaging a DAG that paged on-call at 3am
2. [Rapid-Fire Q&A](interview_questions/02_rapid_fire_qna.md) — fast definitional
   questions, no scenario attached
3. [Critique & Debug](interview_questions/03_critique_and_debug.md) — "what's wrong with
   this DAG?" diagnostic cases: a hidden circular dependency, a poke-mode sensor starving a
   worker pool, a retry policy making a non-idempotent task worse, `catchup=True` triggering
   years of backfill, a dashboard silently gone stale
4. [Curveballs & Trade-offs](interview_questions/04_curveballs_tradeoffs.md) —
   mid-conversation follow-ups: blanket retry policies, inheriting an undocumented
   deployment, event-driven vs. cron scheduling, cross-team DAG ownership
5. [On-Call & Incident Triage](interview_questions/05_oncall_incident_triage.md) — the
   operational-maturity drill: a general triage framework plus five live-incident scenarios,
   scored on sequence and communication, not just eventual diagnosis

See `interview_questions/README.md` for how to use the set.

---

## Key Mental Models

### 1. A DAG Is a Dependency Graph With Two Load-Bearing Rules

```
Directed: A -> B means A must finish before B starts (not just "related to")
Acyclic:  no path can loop back -- otherwise no valid execution order can exist at all

extract_users  --> clean_users  --\
                                    --> join_data --> compute_metrics --> load_warehouse
extract_orders --> clean_orders --/
```

### 2. Operators Are the "What"; the DAG Is the "When" and "Order"

```
Action operators:    PythonOperator, BashOperator, SQL operators   -- do something
Transfer operators:  S3ToRedshiftOperator, etc.                    -- move data between systems
Sensors:             FileSensor, ExternalTaskSensor, etc.          -- wait for a condition
```

### 3. A Failed Task's Downstream Doesn't Just Sit There — It Gets Marked `SKIPPED`, and That Propagates

```
extract (FAILED) --all_success--> transform (SKIPPED) --all_success--> load (SKIPPED)
                                                                            |
                                          notify (trigger_rule='all_done') -+--> RUNS anyway
```

### 4. Backfilling Is `catchup`, Done on Purpose Instead of by Accident

```
catchup=True on a new DAG with an old start_date  -> unplanned, all-at-once historical
                                                      backfill on day one (a real incident)

A deliberate backfill needs: idempotent tasks + an isolated worker pool + throttled
concurrency (max_active_runs) + per-partition writes so live and historical runs can't race
```

### 5. Retries Assume Idempotency — They Don't Create It

```
Non-idempotent task + blind retries  -> a network timeout AFTER the side effect succeeded
                                         means the retry duplicates it (a double charge,
                                         a duplicate row, a duplicate email)

The fix is making the TASK idempotent (upsert on a stable key, delete-then-insert on a
partition) -- a retry policy is a band-aid over a non-idempotent task, not a substitute
for fixing it.
```

---

## Practice Goals

- [ ] Compute a valid execution order for a dependency graph by hand, and identify which
      tasks can run in parallel
- [ ] Write cron expressions for a range of business schedules, including lists, ranges,
      and steps
- [ ] Detect a cycle in a graph description without running any code
- [ ] Design a DAG for a real multi-source scenario, stating retry/timeout choices and
      `max_active_runs` explicitly, not just drawing arrows
- [ ] Resolve trigger-rule outcomes (RUNS/SKIPPED) for a DAG given a set of upstream states
- [ ] Implement retry-with-exponential-backoff-and-jitter from scratch
- [ ] State, from memory, why an SLA and a timeout are different mechanisms
- [ ] Explain why a retry policy requires idempotency, and name the classic non-idempotent
      task that makes blind retries dangerous
- [ ] Walk through safely backfilling a DAG that's also running live today, naming pool
      isolation, throttled concurrency, and partition-safe writes explicitly
- [ ] Run a full "you're on call, the DAG just paged you" triage out loud, in order, before
      touching any code
- [ ] Complete the capstone project end to end, including the resume-after-failure
      requirement

---

## Prerequisites

Helpful but not required: `../etl_elt_patterns/` — this folder assumes you already have a
rough sense of what a pipeline's extract/transform/load stages are actually doing;
orchestration is the layer that schedules, sequences, and recovers those stages, not a
replacement for understanding them. No specific tool is required to follow along — every
code block is dependency-free Python that runs with nothing beyond `python3`'s standard
library, simulating what Airflow (or Dagster, or Prefect) does internally, without needing
an actual install of any of them.
