# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design conversations. This file is the other interview mode: **fast, direct definitional questions** with no scenario attached — the kind asked in a phone screen, or dropped mid-conversation to check you actually understand a term you just used. Answer each one out loud in under 30 seconds before reading the model answer.

Every term used here shows up somewhere in file 1 or in `concepts/` — the cross-references point back to the concrete moment it appeared.

---

## Foundational

**Q: What's the difference between ETL and ELT?**
> ETL: Extract → Transform → Load — transformation happens in a separate processing layer *before* data lands in the warehouse. ELT: Extract → Load → Transform — raw data lands in the warehouse (or lake) first, and transformation happens afterward, usually as SQL running inside the warehouse itself (e.g. a dbt model). ELT became the default with cheap, scalable cloud warehouses, because it's cheaper to let the warehouse's own compute do the transforming than to maintain a separate transformation cluster, and because it keeps a raw copy of the source data around for free, which is valuable when a transformation bug is discovered later and needs to be re-run against history.

**Q: Why does ELT decouple better when multiple teams need different transformations of the same raw data?**
> Because the raw extract lands once, untransformed, and each consuming team builds its own transformation logic (its own dbt models, its own views) on top of that same raw copy — nobody needs to agree on one shared transformation pipeline up front, and no team's transformation choices affect what data is available to another team. Under ETL, the transformation is baked in before the data ever lands, so a second team needing different logic either forces a second full extraction pipeline or fights over shared transform code. See `interview_questions/04_curveballs_tradeoffs.md` for the fully worked version of this trade-off.

**Q: What is a watermark, and why must it only advance after a successful load?**
> A watermark is the maximum value of some monotonically increasing source column (almost always a timestamp) seen as of the last successful incremental run — the next run only asks for rows past it. It must advance only *after* a load succeeds, never before, because advancing it early means a crash between "set watermark" and "actually finish loading" permanently loses whatever wasn't loaded yet — the next run's `WHERE updated_at > watermark` filter would skip right past it. This exact ordering bug is worked in `interview_questions/03_critique_and_debug.md`, Case 2.

**Q: Full load vs. incremental — how do you decide?**
> Full load when the table is small (roughly under 100K rows, as a rule of thumb) or no reliable change-tracking signal exists on the source at all. Incremental once the table is large enough that a full re-scan every run wastes meaningful time/source load, and a trustworthy `updated_at` (or CDC access) exists. Full treatment and decision table: `concepts/04_incremental_vs_full.md`, section 5.

---

## Extraction & Loading

**Q: Incremental by timestamp vs. incremental by ID — what's the one thing ID-based incremental can never detect?**
> Updates to already-extracted rows. Tracking `max(id)` and filtering `WHERE id > hwm` only ever looks forward past IDs already seen — it structurally cannot notice that an old row's *contents* changed, since the row's ID didn't change. It's the right choice only for genuinely append-only sources (event logs, immutable audit trails); the moment historical rows can be updated, it silently drops those updates. See `concepts/04_incremental_vs_full.md`, section 3.

**Q: Name the loading strategies from least to most production-grade, and say which are idempotent.**
> Plain `INSERT` (append) — not idempotent, duplicates on retry. `INSERT OR REPLACE` / upsert — idempotent, good for small dimension-style tables. Delete-then-insert / partition overwrite — idempotent, good for date-partitioned fact tables. `MERGE` / `ON CONFLICT DO UPDATE` — idempotent, the general-purpose version of upsert. Staging + merge — idempotent and the production default, because it keeps a raw copy for debugging and gives data-quality checks a natural place to run before the merge. Full comparison: `concepts/03_loading_strategies.md`, section 7.

**Q: Why stage before merging, instead of writing straight from the transform step into the target table?**
> Three reasons: raw data is preserved for debugging if the merge logic has a bug, the merge itself becomes one auditable SQL statement instead of scattered application-level upsert calls, and data-quality checks have an obvious place to run — between staging landing and the merge executing — rather than being bolted onto the transform step itself. `concepts/03_loading_strategies.md`, section 6.

**Q: What's the risk of `LIMIT`/`OFFSET` chunked extraction against a table receiving concurrent writes?**
> Rows can be skipped or duplicated, because `OFFSET` is a *position*, not an identity — if rows are inserted or deleted between pages, "row 10,001" isn't the same row on page 2 as it would have been if the table were static. The fix is paging by a stable, unique, monotonically increasing column (`WHERE id > last_seen_id ORDER BY id LIMIT n`) instead of `OFFSET`. `concepts/01_extraction_patterns.md`, section 5.

---

## Change Data Capture

**Q: Name the three CDC strategies and the one thing timestamp-based polling can never do that all three "real" CDC approaches can.**
> Query-based (polling with a version/timestamp column — really just incremental extraction under another name), trigger-based (the source database's own triggers write every change into a shadow change-log table), and log-based (reading the database's internal write-ahead log/binlog directly — Debezium, AWS DMS). All three can be run frequently enough to approximate low latency, but only trigger-based and log-based can see **deletes** — query-based polling can't, because a deleted row leaves nothing behind for a `WHERE` filter to find. `concepts/05_change_data_capture.md`, sections 1-4.

**Q: Why is log-based CDC lower-impact on the source than trigger-based CDC?**
> Trigger-based CDC adds an extra write (to the shadow change-log table) inside the same transaction as every single write to the source table — real, ongoing latency and lock contention on the OLTP system's hot path. Log-based CDC reads the write-ahead log/binlog the database already maintains for its own crash-recovery purposes, so it adds essentially zero extra load to the source beyond what it was already doing. `concepts/05_change_data_capture.md`, section 4.

**Q: What's a CDC "tombstone"?**
> The record of a delete event in a change stream — applied downstream as an explicit removal (or, more often in practice, a soft-delete flag) rather than being ignored. A consumer that only handles `INSERT`/`UPDATE` events and silently drops `DELETE` events leaves stale rows in the target forever. `concepts/05_change_data_capture.md`, section 5, and `practice/exercises.md`, Exercise 11.

**Q: Why must CDC events for the same key be applied in order, and how does log-based CDC typically guarantee that?**
> Applying an older update after a newer one (or a delete before the insert it depends on) produces a wrong final state — the last applied event wins, so order determines correctness. Log-based CDC connectors typically guarantee per-key ordering by partitioning the emitted event stream on the row's key, so all events for one key are delivered, in order, to the same consumer. `concepts/05_change_data_capture.md`, section 5.

---

## Idempotency & Reliability

**Q: What does "idempotent" mean for a pipeline, precisely?**
> Running the pipeline again, with the same input, from the same starting state, always produces the same end result — whether it runs once or ten times. Mechanically, this comes from framing an operation as "replace what should exist for this scope" (a merge keyed on a business key, a partition overwrite) rather than "add this to whatever's already there" (a plain append). `concepts/06_idempotency_reliability.md`, section 1.

**Q: Checkpointing vs. idempotent loading — what problem does each one solve, and why do you need both?**
> Idempotent loading guarantees that re-applying a batch is harmless — it won't duplicate or corrupt data. Checkpointing tracks *how far a multi-step run got*, so a retry after a crash resumes from the failed step instead of redoing every step from scratch. Idempotency alone would still let you safely retry the *whole* pipeline from zero every time; checkpointing is what makes that retry cheap rather than correct-but-wasteful. `concepts/06_idempotency_reliability.md`, section 3.

**Q: Why does retry logic need to distinguish transient from permanent failures?**
> Retrying a permanent failure (malformed data, a resource that will never exist) just delays the inevitable failure while wasting time and, if it's hitting an external system, adding needless load — it should route straight to a dead-letter queue instead. Retrying a transient failure (a network blip, a rate limit) is exactly the right response. Treating every failure the same, and retrying everything, is a common and costly mistake. `concepts/06_idempotency_reliability.md`, section 4.

**Q: What's a dead-letter queue, and why keep failed records instead of just dropping them?**
> A holding area for records that failed validation or processing, captured with their raw content and the specific error, so 1 bad row doesn't crash an entire batch and so the failure can be inspected and — once understood or fixed — reprocessed through the same idempotent load path as everything else. `concepts/06_idempotency_reliability.md`, section 5.

**Q: What's the difference between exactly-once, at-least-once, and at-most-once delivery?**
> At-least-once: an event may be delivered/processed more than once, but never lost — the realistic default for almost any real message transport, which is exactly why idempotent processing matters. At-most-once: an event may be lost, but is never duplicated — usually the result of acknowledging receipt before processing completes. Exactly-once: each event has exactly one effect — in practice achieved not by a magic delivery guarantee but by combining at-least-once delivery with idempotent processing, so duplicates are delivered but have no additional effect. Full drill: `interview_questions/05_idempotency_and_exactly_once.md`.

---

## Transformation & Data Quality

**Q: Why validate during transform instead of relying on the target table's constraints to catch bad data?**
> A database constraint violation typically fails (or rolls back) the whole batch containing the bad row, and surfaces late — after extraction and transformation work has already been spent. Validating during transform lets you route the one bad row to an error/dead-letter table and keep loading the other 99,999 valid rows in the same batch, with the failure visible and inspectable rather than a batch-wide rollback with a generic constraint-violation error. `concepts/02_transformation_patterns.md`, section 6.

**Q: Exact-match, key-based, and fuzzy deduplication — what's the actual difference?**
> Exact-match: rows are byte-for-byte identical; safe to collapse with no judgment call. Key-based ("keep the latest"): rows share a clean business key but disagree on other fields, so a rule decides which version wins (most recent timestamp, highest ID). Fuzzy: records don't share a clean key at all, but are plausibly the same real-world entity — this needs a similarity function (e.g. Jaccard similarity over character bigrams) and a clustering step (commonly Union-Find), not a dict lookup. `concepts/02_transformation_patterns.md`, section 2, and `practice/coding_problems.md`, Problem 2.

**Q: A source table adds a new column. Why does a naive transform break, and what's the fix?**
> A transform that assumes a fixed, known set of columns — positional unpacking, or code that silently expects exactly N fields — either crashes or silently ignores the new column (or worse, misaligns values into the wrong fields) the moment the source's shape changes underneath it. The fix is defensive, name-based access to fields (not positional), explicit handling of unexpected/missing keys, and a schema-change detection step upstream that flags a drift before it silently corrupts a transform — see `practice/coding_problems.md`, Problem 3, and the fully worked bug in `interview_questions/03_critique_and_debug.md`, Case 3.

---

**Next:** [03 — Critique & Debug](03_critique_and_debug.md)
