# ETL/ELT Patterns

## Why This Matters

Building and operating pipelines is the core job of a data engineer — every company that moves data from a source system into a warehouse or lake needs this, and every data engineering interview loop asks about it, whether or not it also has a SQL round or a system-design round. The questions are rarely "can you write an `INSERT` statement" — they're about the reasoning that separates a pipeline that looks fine in a demo from one that survives a bad network day, a source schema change, or an on-call engineer hitting retry at 3am: is this load safe to re-run? What happens to a record that arrives late? How do you know a "successful" run didn't silently drop rows?

That reasoning — extraction strategy, idempotent loading, incremental vs. full, change data capture, and what "exactly-once" actually means — is what this folder drills.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like notes, with prose explaining the "why," an ASCII diagram where one clarifies the mechanism, and real, runnable Python + `sqlite3` code (no external dependencies, no warehouse account needed) showing the pattern and its actual output.
- `practice/` — `exercises.md` (12 build-it-yourself drills with the answer hidden behind `<details>`) and `coding_problems.md` (5 harder pipeline-design problems — an incremental loader, fuzzy deduplication, a schema-change detector, retry+DLQ, and a CDC replication system — each with a problem statement, sample input/output, and a hidden solution with an explanation of the pattern it tests).
- `interview_questions/` — a five-file, mostly-code-free drill covering every shape an ETL/ELT interview question tends to take: worked design scenarios, rapid-fire definitions, critique-a-broken-pipeline, curveball trade-offs, and a dedicated idempotency/exactly-once reasoning drill. See `interview_questions/README.md` for the full breakdown.
- `projects/` — one capstone project brief (`mini_etl_pipeline.md`) that forces you to implement most of the concepts as one working, idempotent, incremental pipeline — not just recognize them.

Every `concepts/*.md` file follows the same shape: a **Covers** list, one `##`/`###` section per sub-topic with a prose "why," an ASCII diagram where one helps, real runnable code, and a worked example with its actual output shown in a comment. Every code block is copy-pasteable stdlib Python + `sqlite3` — paste it into a `python3` shell and it runs exactly as shown.

---

## How to Use This Folder

Work through it in this order:

1. **`concepts/`** (01 → 06) — the implementation vocabulary: what makes a load idempotent, what a watermark is, why CDC exists as its own topic. Read these first; everything else assumes this vocabulary.
2. **`practice/exercises.md`**, then **`practice/coding_problems.md`** — apply the vocabulary directly: design an extraction strategy, implement upserts and partition loads, write a retry decorator, replay a CDC change stream. Commit to your own answer before expanding each hidden solution.
3. **`interview_questions/`** — the conversation an interviewer actually scores, rehearsed end to end: clarifying questions → extraction/load strategy → failure handling → narrated trade-offs, across several realistic scenarios, plus rapid-fire definitions, critique-the-broken-pipeline cases, curveball follow-ups, and a dedicated drill on the single most commonly-misunderstood idea in this topic (exactly-once vs. at-least-once).
4. **`projects/mini_etl_pipeline.md`** — a capstone that asks you to build a small, multi-source, incremental, idempotent pipeline as reusable code, then prove it's actually idempotent by running it twice.

---

## Topics Covered

### Concepts

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Extraction Patterns | `concepts/01_extraction_patterns.md` | "Design an extraction strategy for a REST API with pagination and retries." |
| 2 | Transformation Patterns | `concepts/02_transformation_patterns.md` | "How do you clean, deduplicate, and validate data during a transform step?" |
| 3 | Loading Strategies | `concepts/03_loading_strategies.md` | "What's the difference between append, upsert, and staging+merge — and which is idempotent?" |
| 4 | Incremental vs. Full Load | `concepts/04_incremental_vs_full.md` | "How would you implement incremental loading, and how do you handle late-arriving data?" |
| 5 | Change Data Capture | `concepts/05_change_data_capture.md` | "Log-based vs. trigger-based vs. query-based CDC — what's the difference, and why would you pick one?" |
| 6 | Idempotency & Reliability | `concepts/06_idempotency_reliability.md` | "How do you make a pipeline idempotent, and what's the difference between exactly-once and at-least-once?" |

### Interview Questions

`interview_questions/` is a five-file drill:

1. [Worked Design Scenarios](interview_questions/01_worked_scenarios.md) — full walkthroughs: a daily incremental load from Postgres, a pipeline handling late-arriving/out-of-order records, backfilling two years of history without downtime, and a log-based CDC replication design — each with clarifying questions, a narrated design, and failure-handling reasoning
2. [Rapid-Fire Q&A](interview_questions/02_rapid_fire_qna.md) — fast definitional questions, no scenario attached
3. [Critique & Debug](interview_questions/03_critique_and_debug.md) — classic ETL bugs: a non-idempotent retry that double-counted revenue, a watermark updated before the load committed, a transform that broke when the source added a column, and more
4. [Curveballs & Trade-offs](interview_questions/04_curveballs_tradeoffs.md) — mid-conversation follow-ups: no change-tracking column available, batch-to-streaming, ELT's decoupling story, deletes without CDC access, concurrent pipeline runs
5. [Idempotency & Exactly-Once Reasoning](interview_questions/05_idempotency_and_exactly_once.md) — a dedicated drill on the concept most candidates can define but few can reason about correctly under a follow-up

See `interview_questions/README.md` for how to use the set.

---

## Key Mental Models

### 1. ETL vs. ELT

```
ETL: Extract -> Transform -> Load
     (transform happens BEFORE loading, in a separate processing layer)

ELT: Extract -> Load -> Transform
     (raw data lands first; transform happens AFTER, usually as SQL
      inside the warehouse itself -- e.g. a dbt model)
```

### 2. Idempotency Is About Framing the Operation, Not Adding a Check

```
Non-idempotent:  INSERT new_data;                       (duplicates on retry)
Idempotent:      DELETE WHERE key = X; INSERT new_data;  (safe to re-run)
Idempotent:      INSERT ... ON CONFLICT(key) DO UPDATE;  (safe to re-run)

The pattern: "replace what should exist for this scope,"
not "add this to whatever's already there."
```

### 3. A Watermark Only Advances After the Load It Describes Actually Succeeds

```
extract (read watermark) -> transform -> load -> ONLY THEN advance watermark

Advancing it any earlier means a crash between "watermark moved" and
"load actually committed" permanently loses whatever didn't make it in.
```

### 4. Exactly-Once Effect = At-Least-Once Delivery + Idempotent Processing

```
True exactly-once DELIVERY across a network isn't achievable -- a caller
can't always tell "it failed" from "it succeeded but the response was lost."

What's achievable: retry freely (accept duplicates at the delivery layer),
and make processing idempotent (a duplicate has no additional effect).
```

### 5. Timestamp-Based Incremental Extraction Cannot See Deletes

```
WHERE updated_at > watermark   <-- a deleted row produces NOTHING to filter on

This is the entire reason Change Data Capture (concepts/05) exists as
its own topic: trigger-based and log-based CDC both capture deletes;
query-based polling structurally cannot.
```

---

## Practice Goals

- [ ] Design an extraction strategy for a large, append-only table and for a paginated, rate-limited API
- [ ] Implement upsert loading, partition-overwrite loading, and the staging+merge pattern, and state which are idempotent and why
- [ ] Convert a full-load pipeline to incremental-by-timestamp, and explain what breaks if the watermark advances before the load commits
- [ ] Explain query-based, trigger-based, and log-based CDC, and pick the right one for a stated latency/delete-sensitivity requirement
- [ ] Make a multi-step pipeline fully idempotent: staging+merge loading, checkpointing, retry with exponential backoff, and a dead-letter queue
- [ ] Distinguish a non-idempotent side effect (an external API call) from an idempotent database write, and explain why the database being idempotent isn't always enough
- [ ] Run a full "design a pipeline for X" conversation end to end, narrating extraction/load/failure-handling decisions without writing full code
- [ ] Diagnose a broken pipeline from a plain-English description of its symptom, not just from reading its code

---

## Prerequisites

`sql_foundations` and `data_modeling` are helpful — a few worked scenarios reference star-schema/SCD concepts and assume basic SQL fluency (`JOIN`, `WHERE`, `ON CONFLICT`) — but neither is required. Every concept file is self-contained Markdown with runnable Python + `sqlite3` code blocks: no warehouse, no orchestrator, no external service required. Any `python3` with the standard-library `sqlite3` module is enough to run every example in this folder yourself.
