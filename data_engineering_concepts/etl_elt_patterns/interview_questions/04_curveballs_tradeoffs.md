# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

A question type that doesn't fit a full scenario or a flash-card definition — the interviewer takes whatever you just designed (in [file 1](01_worked_scenarios.md)) and pushes on one assumption. There's rarely one "correct" answer here; what's scored is whether you reason through the trade-off out loud instead of freezing or giving a one-word answer. Try answering each before expanding the model answer.

---

**Curveball: "The source system has no `updated_at` column, no CDC access, and the vendor won't add one. You still need incremental loads. What do you do?"**

<details>
<summary>Model answer</summary>

Without any native change-tracking signal, the options are all a form of computing change detection *yourself* rather than relying on the source to expose it: (1) a **checksum/hash-diff** approach — extract a lightweight hash of each row's contents (computed at extraction time) alongside its key, compare against the previous run's stored hashes, and only treat a row as changed if its hash differs; this still requires a full extraction pass to compute the hashes, so it saves on *transform/load* cost, not extraction cost. (2) Push for a **change-tracking column to be added at the database level** even without vendor cooperation — a trigger the team controls, if they have write access to the schema, even if the vendor's application code doesn't use it. (3) Accept **full load** if the table is small enough that the cost genuinely doesn't matter, rather than building elaborate machinery to avoid a cost that isn't actually a problem yet. The judgment call being scored is recognizing that "no updated_at" doesn't automatically mean "must build CDC" — sometimes the honest answer is that full load was fine all along, and the missing column was never actually blocking anything.

</details>

---

**Curveball: "This incremental batch pipeline runs every hour. Leadership now wants it near-real-time. What actually changes?"**

<details>
<summary>Model answer</summary>

The extraction *mechanism* has to change, not just the schedule — running the same hourly batch job every 30 seconds instead doesn't produce real-time freshness, it just produces a much more expensive batch job that mostly extracts nothing. A genuine shift to near-real-time means moving to log-based CDC (`concepts/05_change_data_capture.md`) or a native streaming source, paired with a stream consumer that applies changes continuously rather than in scheduled batches. This is a real architectural change — new infrastructure (a CDC connector, a stream processing/consumer layer), new failure modes (consumer lag, offset management, backpressure), and a fundamentally different idempotency story (continuous at-least-once delivery instead of a bounded batch that either fully succeeds or fully fails). Naming it explicitly as "that's a different system, not a cron schedule change" — and asking whether the *actual* business need is sub-minute freshness or just "faster than once an hour" (which might be solved by simply running the existing batch job every 5-10 minutes) — is the senior response, mirroring the same batch-vs-streaming boundary drawn in `data_modeling/interview_questions/04_curveballs_tradeoffs.md`.

</details>

---

**Curveball: "Two downstream teams want different transformation logic applied to the same raw source. Do you build two separate pipelines?"**

<details>
<summary>Model answer</summary>

No — this is exactly the case ELT is built for. Land the raw extract once, untransformed, in the warehouse/lake; let each team build its own transformation layer (its own dbt models, its own views or materialized tables) on top of that one shared raw copy. Building two separate end-to-end ETL pipelines (two extraction jobs, two sets of watermark-tracking, two load paths) duplicates the expensive, failure-prone part (extraction and loading) purely to get two different, comparatively cheap transformation outcomes. The one thing to watch for: if both teams' transformations derive a value that's supposed to mean the same thing (a "customer segment," an "active user" definition) and compute it independently, that's the OBT-drift problem from `data_modeling/interview_questions/03_critique_and_debug.md`, Case 8 — the fix there (centralize genuinely shared logic once, let team-specific logic diverge freely) applies here too.

</details>

---

**Curveball: "The source allows hard deletes, but you don't have CDC access — only a nightly full-table extract. How do you detect and apply those deletes?"**

<details>
<summary>Model answer</summary>

A single incremental extract can't see them — the fix is a periodic (need not be nightly; weekly is often enough) **key-reconciliation pass**: pull just the primary keys from the source (a cheap, narrow query) and anti-join against the warehouse's current keys for that table. Any key present in the warehouse but absent from the freshly-pulled source key list is a deletion candidate. Apply it as a soft delete (flag `is_deleted = true`, keep the row for historical/audit queries) by default, rather than a hard delete, for the same reason a hard delete is usually the wrong default in `data_modeling/interview_questions/01_worked_scenarios.md`'s account-deletion curveball — reversing a wrongly-detected "deletion" (a false positive from, say, a reconciliation query that ran against a stale replica) is far easier if the row was only flagged, not physically removed. The trade-off to name explicitly: this detects deletes on a real delay (up to the reconciliation interval), which is fine for most reporting use cases and not fine at all if deletes need to be reflected within minutes — which is the point where the conversation shifts to log-based CDC instead.

</details>

---

**Curveball: "Your idempotent upsert-based pipeline runs hourly via a cron-style scheduler. What happens if the scheduler double-fires and two instances of the same run execute concurrently?"**

<details>
<summary>Model answer</summary>

Idempotency at the row level (an upsert on a primary key) doesn't automatically protect against two *concurrent* instances both reading the same watermark, both extracting the same window, and both racing to upsert — the data itself likely ends up correct (both instances converge to the same final row values), but the watermark bookkeeping can end up wrong: whichever instance's "update the watermark" write loses the race might get silently overwritten by the other, or worse, a watermark could theoretically move past a window that only one instance actually finished loading. The real fix isn't more idempotency — it's a **lock or lease**: acquire a distributed/database-level lock (or check-and-set a "run in progress" flag) at the start of the run and hold it for the run's duration, so a second concurrent trigger detects the lock and exits immediately instead of proceeding. This is a different problem from row-level idempotency, and treating "the load is idempotent" as sufficient protection against concurrent execution is a common, costly gap.

</details>

---

**Curveball: "How do you know your incremental pipeline actually caught everything — that nothing was silently missed?"**

<details>
<summary>Model answer</summary>

Name concrete, checkable properties, not "I'd test it": (1) **row-count reconciliation** — periodically compare a full count (or count-by-date-bucket) from the source against the warehouse, to catch a silent gap the incremental logic itself would never surface; (2) **watermark monotonicity checks** — alert if a watermark ever moves backward or fails to advance across multiple consecutive successful-looking runs, which usually indicates the update-before-load-succeeds bug from `interview_questions/03_critique_and_debug.md`, Case 2; (3) **freshness monitoring** — alert if the time since the last successful watermark advance exceeds the expected run interval by a wide margin, catching a pipeline that's silently stopped running rather than one that's running but wrong; (4) for CDC specifically, **gap detection on the event sequence itself** (`practice/coding_problems.md`, Problem 5), which is a different and additional check from row-count reconciliation. The unifying theme: none of these are "run it and eyeball the output" — they're automated checks that run on every execution, because a silent gap is by definition not something a human will notice without one.

</details>

---

**Curveball: "This ELT pipeline transforms data with SQL running inside the warehouse itself. A stakeholder asks: doesn't that mean bad raw data can corrupt the transformation layer with no safety net?"**

<details>
<summary>Model answer</summary>

Push back gently on the framing: ELT landing raw data first doesn't remove data-quality checks, it *relocates* them — from a separate pre-load validation step (the ETL-style approach) to a validation layer that runs against the landed raw data, before or as part of the transformation SQL (e.g. dbt tests/contracts run against staging models before a downstream mart model builds on top of them). The actual trade-off is real, though: because raw, unvalidated data does land in the warehouse under ELT (that's the whole point — transform-after-load), a raw layer with no query access restrictions could let an impatient analyst query un-validated staging tables directly and draw a wrong conclusion before the validated, transformed layer exists. The concrete mitigation is a naming/access convention — raw/staging schemas are understood (and ideally access-restricted) as "not yet validated," while only the transformed mart layer is presented as fit for general consumption — which is the same bronze/raw-vs-gold/mart layering named in `data_modeling/interview_questions/02_rapid_fire_qna.md`'s medallion-lakehouse answer.

</details>

---

**Curveball: "You backfilled two years of history successfully. Three months later, someone finds that a chunk from month 14 is missing about 5% of its rows, and nobody noticed until now. How do you prevent this next time?"**

<details>
<summary>Model answer</summary>

The gap here isn't the backfill design itself (chunking, idempotent merges) — it's the absence of a **per-chunk verification step** that would have caught this the same day, not three months later. Every chunk should be checked immediately after loading — a row count and/or checksum comparison against the source for that exact date range — before moving on to the next chunk, exactly the reconciliation discipline named in `interview_questions/01_worked_scenarios.md`'s backfill scenario, Step 5. Retroactively, the fix is the same reconciliation check run across the *entire* backfilled range now, to find every other chunk with the same silent gap, not just the one someone happened to notice — treating this as "found one bug, fixed one chunk" rather than "found one *symptom*, need to check everywhere the same failure mode could have occurred" is the mistake to avoid making twice.

</details>

---

**Next:** [05 — Idempotency & Exactly-Once Reasoning](05_idempotency_and_exactly_once.md)
