# 1. Worked Scenarios

Part of the [Interview Questions](README.md) series — see that index for the full
taxonomy of question types and how the files fit together.

This file is deliberately **code-free** — no DAG definitions, no Python. The point is to
rehearse the *reasoning* an interviewer is actually scoring: how you scope the problem,
ask the questions that separate a real answer from a memorized one, and narrate trade-offs
out loud. Once the reasoning is solid, the DAG code is the easy part — that's what
`concepts/` and `practice/` are for.

Three full scenarios below, each a complete mock-interview walkthrough. Read them straight
through the first time, including the debriefs; come back and answer the "Now You Try"
companion yourself before expanding its hidden debrief.

---

## Scenario 1: Design the DAG for a 40-Task Daily Pipeline Across 3 Source Systems

**Interviewer prompt:**
> "You need to build a daily pipeline that pulls from three source systems — a Postgres
> application database, a third-party billing API, and an S3 bucket where a partner drops
> event files — and produces about 40 interdependent tasks downstream: cleaning, joins,
> several layers of aggregation, and a handful of reports. Walk me through how you'd
> structure the DAG."

### Step 1 — Ask clarifying questions before drawing anything

A candidate who starts naming 40 tasks immediately is the red flag here, not the strength.
The questions themselves are part of the signal:

- **Do all three sources refresh on the same cadence?** If the billing API's data lands at
  a different time than the Postgres extract, the DAG's schedule needs to account for the
  *slowest* source, or use sensors to decouple "when the DAG kicks off" from "when each
  source's data is actually ready."
- **What's the acceptable end-to-end latency?** Determines whether 40 tasks in one DAG is
  even the right shape, versus splitting into multiple DAGs wired together.
- **Which of the 40 tasks are genuinely independent, and which form the "spine"?** Most
  real 40-task pipelines are not 40 flat dependencies — they're a handful of extract/clean
  stages that fan out into many narrow, mostly-independent downstream reports.
- **What's the blast radius of one task failing?** Should a broken report on task 38 hold
  up 39 other unrelated tasks, or should the pipeline be structured so unrelated failures
  are contained?

### Step 2 — Structure, not just count, is the actual design decision

The honest answer to "design a 40-task DAG" is: **don't design one 40-node flat graph** —
design it as a small number of logical stages, each internally parallel, connected by a
handful of "gate" tasks:

```text
Stage 1 (parallel):  extract_postgres, extract_billing_api, extract_s3_events
                       -- one task family per source, each with its own sensor/retry policy
                       appropriate to that source's own reliability characteristics

Stage 2 (parallel):  validate_postgres, validate_billing, validate_events
                       -- validation is source-specific; keep it a separate task per
                       source so ONE source's schema drift doesn't block the other two

Stage 3 (gate):       join_all_sources
                       -- the ONE point where all three streams must agree to proceed;
                       this is deliberately a single narrow gate, not 40 tasks all
                       depending directly on all three extracts

Stage 4 (fan-out,     compute_revenue_metrics, compute_user_segments,
~15-20 parallel):     compute_inventory_aggregates, ... (the bulk of the 40 tasks live here)
                       -- these are mutually independent; a failure in one doesn't block
                       the others, and this is where TaskGroups earn their keep purely
                       for readability in the UI

Stage 5 (fan-in):     generate_report_a, generate_report_b, ...
                       -- each report depends on ONLY the specific stage-4 outputs it
                       actually needs, not on all of stage 4 -- a report using only revenue
                       metrics has no business waiting on the segmentation task
```

**Why this shape, stated explicitly:** grouping into stages with narrow gates between them
means a failure at stage 4 in one branch doesn't cascade into unrelated stage-4 branches —
each report-generating task's `trigger_rule` and dependency list should reference only what
it actually consumes, not "everything upstream" as a lazy default. This is the single
biggest quality signal in a 40-task design: **most candidates default every task to
depending on the entire previous stage; the strong answer prunes dependencies down to only
what's genuinely needed**, because unnecessary dependencies are exactly what turns one
unrelated task's bad day into an outage for the whole DAG.

### Step 3 — Naming the operational decisions, not just the shape

- **Retries per source, not one global policy.** The S3 partner drop might need a long
  timeout and generous retries (partner files land on their own schedule); the internal
  Postgres extract should fail fast — a long timeout there is more likely masking a real
  problem than waiting out a transient blip.
- **`max_active_runs=1`** on this DAG almost certainly, given the joins and aggregations
  depend on a fully-consistent snapshot across three sources — overlapping runs risk a
  join reading half of yesterday's data and half of today's.
- **TaskGroups** for the ~15-20 stage-4 aggregation tasks purely for UI legibility — a flat
  40-node graph view is unreadable; grouped by business domain (revenue, users, inventory)
  it's immediately scannable.

<details>
<summary>Debrief — what a strong answer sounds like end to end</summary>

The strongest version of this answer never says "40 tasks" as if it's one flat unit — it
immediately reframes to "a small number of stages, each parallel inside itself, connected
by narrow gates," and explicitly prunes each downstream task's dependency list to only what
it needs rather than defaulting to "depends on everything before it." The two things that
separate a senior answer from a mid-level one here: (1) naming that different sources need
different retry/timeout policies rather than one blanket setting, and (2) recognizing that
`max_active_runs=1` is a real design decision tied to a specific correctness risk (a join
reading an inconsistent mix of two days' data), not a default checkbox.

</details>

---

### Now You Try: A 25-Task Multi-Region Reporting Pipeline

**Scenario:** A retail company needs one daily DAG that ingests point-of-sale data from
5 regional systems (different formats, different SLAs — two regions are reliably on time,
three are frequently late), cleans and standardizes each region's data, computes
region-level and global metrics, and produces both a regional dashboard refresh and a
single global executive report. ~25 tasks total. Design the DAG structure and name your
key operational decisions.

<details>
<summary>Debrief — write your own design first</summary>

The core tension this scenario is built to surface: **two reliable regions and three
unreliable ones should not force the two reliable regions' downstream work to wait on the
slowest one, unless the global report genuinely requires all five.** Structure: per-region
extract → per-region validate → per-region "clean" tasks proceed as soon as *that region's*
sensor/extract completes, entirely independent of the other four regions. Region-level
dashboards depend only on their own region's pipeline finishing — a late region 3 should
never delay region 1's dashboard refresh. The global executive report is the one task that
legitimately needs `all_success` (or `none_failed`, if a missing region should still produce
a partial global report rather than none at all — worth stating as an explicit choice, not
an assumption) across all five regions, and is the one place a genuinely long timeout/sensor
wait for the slow regions belongs, rather than spreading that tolerance across the whole
DAG. Naming the trigger-rule choice for the global report explicitly (`all_success` blocks
the exec report on any one region; `none_failed` lets it proceed with 4-of-5 regions and
flag the gap) is the single detail that separates a strong answer here.

</details>

---

## Scenario 2: Safely Backfilling 6 Months of History for a DAG Running Live Today

**Interviewer prompt:**
> "Someone just realized a metric your daily pipeline computes has been subtly wrong for
> the last 6 months, and it needs to be recomputed for that entire range. The DAG is also
> running its normal daily schedule right now, in production, and downstream dashboards are
> actively being used. Walk me through how you'd backfill this safely."

### Step 1 — Confirm the precondition before touching anything

> "Before I schedule anything: is every task in this DAG idempotent — specifically, does
> reprocessing a given date replace exactly that date's rows (delete-then-insert on a date
> partition, or an upsert on a stable key), or does anything in the DAG *accumulate* on top
> of what's already there?"

If the answer is "we're not sure," that's the real first task — not the backfill itself.
Backfilling a non-idempotent DAG doesn't fix six months of bad data, it corrupts six months
of data a second, differently-wrong way. (Full mechanics: `concepts/05_backfills_and_catchup.md`, section 4.)

### Step 2 — Isolate the backfill's resource usage from production's

- **A dedicated pool** for the backfill's task instances, separate from the pool the live
  daily DAG uses — the backfill must not be able to starve today's normal run of worker
  slots, and today's normal run must not stall the backfill indefinitely either.
- **Throttle the backfill's own concurrency** (`max_active_runs` / `-j` on the backfill
  command) — running 180 days 10-at-a-time instead of all at once protects any
  rate-limited upstream API and the warehouse's own concurrent-query ceiling.
- **Confirm partition boundaries.** If every write is scoped to its own date partition, the
  backfill's June 2023 writes and today's live write to today's partition genuinely cannot
  race each other — this is the detail that makes "running alongside production" safe
  rather than a controlled gamble.

### Step 3 — Protect downstream consumers from partial history

> "I would not let the backfill write directly into the table the dashboard reads from,
> date by date, as it progresses — a dashboard user querying mid-backfill would see some
> months corrected and some still wrong, with no way to tell which is which. I'd backfill
> into a staging table or a clearly-versioned partition set, validate the full 6-month
> range once it's complete — row counts, a few known aggregates spot-checked against a
> source of truth — and cut the read path over in one atomic swap (a view redirect, or a
> partition-swap) rather than incrementally."

### Step 4 — State the plan back in one sentence

> "Confirm idempotency, backfill into isolated storage using a separate resource pool at a
> throttled concurrency so it doesn't compete with or corrupt today's live run, validate the
> full range, then cut consumers over atomically."

<details>
<summary>Debrief</summary>

The interview tell here is treating "backfill" as a single CLI command rather than an
operational plan with four distinct concerns: correctness precondition (idempotency),
resource isolation (pools, throttled concurrency), partition-level write safety (so live
and historical writes can't race), and consumer-facing safety (no partial history visible
mid-flight). A candidate who jumps straight to "I'd run `airflow dags backfill`" without
naming any of the four has memorized the command, not the operational reasoning behind it.

</details>

---

## Scenario 3: A Critical DAG Paged On-Call at 3am — Walk Through Your Triage

**Interviewer prompt:**
> "You're on call. At 3am, PagerDuty fires: the DAG that feeds tomorrow's executive
> dashboard failed. Walk me through exactly what you do, in order, starting from the
> moment you open your laptop."

### Step 1 — Establish scope before touching anything

> "First question I'm answering for myself, not fixing anything yet: **is this one task
> failing, or is the whole DAG — or worse, the whole scheduler — down?** I'd check the
> Airflow UI's DAG view for this specific DAG first, and separately check whether *other*
> unrelated DAGs are also failing around the same time. If everything failed at once, this
> is probably infrastructure (the scheduler, a shared database, a credentials rotation) —
> a completely different investigation than one DAG having a bad night."

### Step 2 — Read the actual failure before assuming the cause

> "I'd open the failed task's logs, not just the fact that it's red. Specifically: is this
> the FIRST time this task has failed (a genuinely new problem), or has it been intermittently
> failing and finally exhausted its retries tonight (a known-flaky task that just got
> unlucky)? Is the error a clear, actionable one (a connection refused, a schema mismatch)
> or something vaguer that needs more digging?"

### Step 3 — Decide: fix forward, rerun, or roll back — and say why

> "If the cause is clearly transient (a downstream API had a bad few minutes and is fine
> now), I'd clear the failed task instance and let it rerun — assuming the task is
> idempotent, which for a dashboard-feeding pipeline it should be. If the cause is a real
> data or code problem, I would NOT just keep retrying — I'd assess whether the dashboard
> can tolerate being stale for a few hours while I actually fix the root cause, versus
> whether this needs an immediate escalation because someone specific is depending on fresh
> numbers first thing this morning."

### Step 4 — Communicate before you're fully done, not after

> "I would not wait until the problem is fully resolved to say anything. A short 'DAG X
> failed at 3am, investigating, dashboard may be stale until ~7am' to whatever channel the
> team actually watches is worth sending early — silence during an incident is its own
> failure mode, independent of how quickly the underlying issue actually gets fixed."

### Step 5 — After it's resolved: was this actually new?

> "Once it's green again, I'd check whether this is a first-time failure or the Nth time —
> and if it's recurring, that's a signal the retry policy or the underlying flakiness itself
> needs a real fix during business hours, not just another successful 3am rerun that quietly
> defers the same problem to next week."

<details>
<summary>Debrief</summary>

This scenario is scored on **sequence**, not just knowledge — an answer that jumps straight
to "I'd rerun the task" without first scoping whether it's isolated or systemic, without
reading the actual log, and without communicating status, demonstrates familiarity with
Airflow's UI but not with actually being on-call. The specific ordering — scope, diagnose,
decide (with a stated reason), communicate, and follow up on recurrence — is the same shape
drilled in much more depth, across more failure types, in
`interview_questions/05_oncall_incident_triage.md`.

</details>
