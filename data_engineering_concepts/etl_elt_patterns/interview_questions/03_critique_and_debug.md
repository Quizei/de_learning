# 3. Critique & Debug: "What's Wrong With This Pipeline?"

Part of the [Interview Questions](README.md) series.

A different interview mode from [file 1](01_worked_scenarios.md): instead of "design something from scratch," you're handed a pipeline or a wrong number and asked **"what's wrong with this?"** This tests whether you can *read* a pipeline critically, not just build one. Every case is described in plain prose — the skill being tested is spotting the flaw from a description, the same way it'd be described to you out loud in an interview.

Read the symptom, form your diagnosis, then expand the debrief.

---

## Case 1: The Retry That Doubled Revenue

**Setup:** A nightly job extracts yesterday's orders and loads them into `fact_orders` with a plain `INSERT INTO fact_orders SELECT * FROM stg_orders`. Last night the job failed with a network timeout *after* the insert had already committed, but *before* the orchestrator marked the run as successful. The orchestrator's automatic retry policy re-ran the entire job. This morning, yesterday's revenue is exactly double what finance expected.

<details>
<summary>Debrief</summary>

**Diagnosis:** the load step is a plain append with no idempotency guarantee at all. The first run's `INSERT` fully committed — the timeout happened *after* the data landed, in the step that reports success back to the orchestrator — so the retry re-ran the exact same insert against the exact same source rows, which had no way of knowing they'd already been loaded once.

**Fix:** the load must be keyed on a natural business key (the order ID) and applied as an upsert (`INSERT ... ON CONFLICT(order_id) DO UPDATE`) or via the staging + merge pattern, not a plain `INSERT`. Either makes a re-run land on the same final rows regardless of how many times it executes — see `concepts/03_loading_strategies.md`.

**The interview tell:** naming precisely *where* the failure landed relative to the commit — "the timeout was cosmetic to the database; the insert had already succeeded" — rather than assuming the retry is inherently the problem. The retry did exactly what it was configured to do; the load step's lack of idempotency is what turned a safe retry into a real data-quality incident. This is the canonical version of the bug `concepts/06_idempotency_reliability.md`, section 1, opens with.

</details>

---

## Case 2: The Watermark That Silently Drops Records

**Setup:** An incremental pipeline reads `updated_at`, computes the new watermark as `MAX(updated_at)` from the extracted batch, and writes that watermark to the metadata table **immediately after extraction, before the transform-and-load steps run**. Most nights this is fine. One night, the transform step crashes on a malformed row partway through, and the load never happens at all. The next night's run proceeds normally — and nobody notices that an entire night's orders are permanently missing from the warehouse.

<details>
<summary>Debrief</summary>

**Diagnosis:** the watermark advances the moment extraction finishes, not after the load actually succeeds. When the transform step crashes before load, the extracted rows are lost — but the watermark has already moved past them, so the next run's `WHERE updated_at > watermark` filter starts *after* those rows, and they are never extracted again. There is no error, no exception, no alert — the rows simply never appear, and the failure looks identical to "there just wasn't much data that night."

**Fix:** the watermark must be written only after the load into the target has committed successfully — the same principle stated explicitly in `concepts/01_extraction_patterns.md` and `concepts/04_incremental_vs_full.md`. If extraction, transform, and load are separate steps in an orchestrator, the watermark update belongs in (or immediately after) the load step, gated on its success — never in the extraction step.

**The interview tell:** this is the single most consequential ordering bug in incremental ETL, precisely because it fails silently. A candidate who says "the watermark should only move after the load commits" *before* being shown this case has clearly internalized why, rather than needing the failure spelled out first.

</details>

---

## Case 3: The Transform That Broke When the Source Added a Column

**Setup:** A transform step unpacks each extracted row positionally: `id, name, email, amount = row`. It's worked in production for months. One day the source team adds a `phone` column to the `customers` table, inserted *between* `email` and `amount` in the table's column order. The next pipeline run either crashes with a "too many values to unpack" error, or — worse, in a version of the code that used `row[:4]` defensively — silently loads `phone` values into the `amount` column for every single row.

<details>
<summary>Debrief</summary>

**Diagnosis:** positional field access assumes the source's column order (and count) is a stable contract. It never was one — a source team adding a column is a routine, backward-compatible change from *their* point of view, and nothing about it obligates them to notify every downstream consumer of their table. The pipeline's assumption, not the source's change, is the actual bug.

**Fix:** extract and transform using named field access (`row["amount"]`, or a `DictReader`/named-tuple/dict-based row, never positional unpacking), so a new column is simply ignored by code that doesn't reference it by name, rather than silently shifting every subsequent field over by one position. Layer a schema-change detector (`practice/coding_problems.md`, Problem 3) upstream of the transform so an actual breaking change — a column removed, or retyped in a way that breaks a cast — is caught and flagged *before* it corrupts a batch, rather than discovered by a stakeholder asking why `amount` looks wrong.

**The interview tell:** distinguishing "the source added a column" (routine, non-breaking, should never have broken anything) from "the source removed a column" or "retyped it incompatibly" (genuinely breaking) is the real signal — a candidate who treats every source change as equally dangerous hasn't thought about *why* positional access was ever the wrong call in the first place. See `interview_questions/02_rapid_fire_qna.md`'s "Transformation & Data Quality" section for the one-line version of this answer.

</details>

---

## Case 4: The Full-Table Reload That Served an Empty Table

**Setup:** A dimension table is refreshed nightly with `DELETE FROM dim_products; INSERT INTO dim_products SELECT * FROM stg_products;` run as two separate statements, not wrapped in an explicit transaction. Most nights the gap between the two statements is milliseconds and nobody notices. One night, the insert step ran slowly due to an unrelated warehouse load spike, and for about four minutes, a BI dashboard querying `dim_products` during that window returned zero products, causing a brief false "site outage" page.

<details>
<summary>Debrief</summary>

**Diagnosis:** delete-then-insert is idempotent (re-running it doesn't duplicate anything), but idempotency and *atomicity* are different properties — the table is genuinely, visibly empty for the entire gap between the `DELETE` committing and the `INSERT` completing. Any reader querying during that window sees a real, if temporary, empty table, not a stale-but-valid one.

**Fix:** wrap both statements in a single transaction if the target database supports transactional DDL/DML across them, so readers either see the old data or the new data, never a gap; or load into a new table/partition and atomically swap a pointer/view rather than deleting in place; or use the `ON CONFLICT DO UPDATE` merge pattern instead of delete-then-insert, which never removes rows before their replacements exist. `concepts/03_loading_strategies.md`, section 3, names this exact risk.

**The interview tell:** recognizing that "safe to re-run" (idempotent) and "never visibly broken mid-run" (atomic) are two separate guarantees, and that a pattern can have one without the other, is the deeper answer here — a candidate who only checks "is it idempotent?" would sign off on this design and miss the outage risk entirely.

</details>

---

## Case 5: The Non-Idempotent Side Effect Behind an Idempotent Load

**Setup:** A pipeline processes a batch of pending refunds: for each record, it calls a third-party payment API to issue the refund, then upserts a `refunds` table (keyed on refund ID) to mark it as processed. The pipeline crashes after successfully calling the payment API for refund #4821, but before the upsert marking it processed commits. The orchestrator retries the whole batch. Refund #4821 is charged back to the customer twice.

<details>
<summary>Debrief</summary>

**Diagnosis:** the *database* load is idempotent (an upsert keyed on refund ID), but the pipeline has a non-idempotent **side effect outside the database** — a real call to an external payment API — that happens *before* the idempotent bookkeeping step commits. No amount of upsert logic on the `refunds` table can undo a refund that was already issued twice in the real world; the database's idempotency guarantee only covers the database.

**Fix:** either make the external call itself idempotent (many payment APIs support an idempotency key — a client-generated unique ID per logical operation — so calling the same operation twice with the same key has no additional effect on their end), or restructure the pipeline so the "has this refund already been attempted" check happens durably *before* the external call is made, not just after. If the API supports idempotency keys, that's almost always the right fix — it pushes the guarantee to the one place that actually needs it.

**The interview tell:** this is the sharpest version of the idempotency question in this whole topic, because the database-level answer ("just use an upsert") is necessary but not sufficient — a candidate who stops at "the load is idempotent, so we're fine" hasn't noticed that the *load* was never the risky part. Full drill: `interview_questions/05_idempotency_and_exactly_once.md`.

</details>

---

## Case 6: The CDC Consumer That Silently Skipped a Gap

**Setup:** A log-based CDC pipeline replicates a `subscriptions` table. The CDC connector briefly disconnected from the source during a maintenance window and reconnected a few minutes later, resuming from its last committed offset — but a bug in the connector's reconnection logic caused it to skip ahead past a handful of change events that occurred during the disconnection, rather than replaying them. Weeks later, an auditor notices a subscription that should have shown a cancellation event in its history, but the warehouse shows it as still active.

<details>
<summary>Debrief</summary>

**Diagnosis:** this is a gap in the CDC event sequence that went undetected because the consumer only checked "did I get *an* event with a sequence number greater than my last one," not "did I get *every* event, with no skipped sequence numbers." A skipped event (the cancellation) is indistinguishable, from the consumer's point of view, from an event that simply never happened — unless the consumer is explicitly tracking sequence continuity.

**Fix:** the consumer must track the exact last-applied sequence number (or offset/LSN) and treat any arriving event whose sequence number isn't exactly one more than the last as a **gap**, flagged for investigation or automatic re-sync from the source's log — never silently advanced past. `practice/coding_problems.md`, Problem 5, builds exactly this gap-detection logic as its own explicit concern, separate from applying the events themselves.

**The interview tell:** recognizing that "the pipeline kept running without erroring" is not the same claim as "the pipeline captured every change" — CDC's core value proposition (capturing *every* change, including deletes) is silently undermined the moment gap detection is missing, even though nothing about the pipeline looks broken from the outside. This is the CDC-specific version of Case 2's silent-drop bug.

</details>

---

**Next:** [04 — Curveballs & Trade-offs](04_curveballs_tradeoffs.md)
