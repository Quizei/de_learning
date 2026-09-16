# 3. Critique & Debug: "What's Wrong With This?"

Part of the [Interview Questions](README.md) series.

A different interview mode from [file 1](01_worked_scenarios.md):
instead of "design something from scratch," you're handed a storage
layout, a partitioning scheme, or a slow query and asked **"what's
wrong with this?"** Every case below is described in plain prose — no
DDL, no config files — because the skill being tested is spotting the
flaw from a description, the same way it'd be described to you out loud.

Read the symptom, form your diagnosis, then expand the debrief.

---

## Case 1: The Table With Two Million Partitions

**Setup:** A 500 GB orders table is partitioned by
`year/month/day/hour/customer_segment/payment_method`. It now has 2.1
million partitions, averaging 240 KB each. Queries against it are
noticeably *slower* than before this partitioning scheme was
introduced, and the Hive metastore takes about 10 minutes just to list
all of the table's partitions.

<details>
<summary>Debrief</summary>

**Diagnosis:** this is over-partitioning, textbook. Stacking six
partition columns — several of them (hour, customer_segment,
payment_method) adding cardinality that isn't needed for the queries
this table actually serves — multiplied the partition count into the
millions, each holding a tiny fraction of the table's data. Per-partition
fixed overhead (metastore listing, file-open cost, query-planning time
to enumerate every candidate partition) now dominates the actual work
of scanning ~240 KB of real data per partition.

**Fix:** repartition by `year/month` only (or `year/month/day` if daily
queries are truly common) — for a 500 GB table, that's roughly 24-750
partitions at a healthy multi-GB-to-hundreds-of-MB size each, well
within the 128 MB–1 GB guidance from `concepts/02_partitioning_and_bucketing.md`,
section 5. `customer_segment` and `payment_method` are low-cardinality
columns that belong as regular filterable columns (or, if genuinely
needed for join optimization, a **bucketing** key within each date
partition) — not additional partition levels.

**The interview tell:** naming this instantly as "too many partition
columns compounding cardinality" — and being able to say *which* of the
six columns should never have been a partition column and why — is what
separates a real diagnosis from "just partition it differently."

</details>

---

## Case 2: The Query That Scans the Whole Table Despite the Date Filter

**Setup:** `fact_events` is partitioned by `event_date` (a `DATE`
column). A dashboard runs `SELECT COUNT(*) FROM fact_events WHERE
CAST(event_timestamp AS DATE) = '2025-06-01'` and it scans the entire
multi-terabyte table every time, even though the table is partitioned
by date and the query is clearly asking for one day.

<details>
<summary>Debrief</summary>

**Diagnosis:** the query filters on `CAST(event_timestamp AS DATE)`, a
*different* column than the partition column (`event_date`), wrapped
in a function on top of that. Even setting the column mismatch aside,
wrapping any column in a function or cast defeats partition pruning
(and, separately, index usage) the same way it defeats sargability in
`sql_foundations/concepts/05_query_optimization_and_indexing.md` — the
engine can't evaluate "which partitions could this match" without
computing the cast for every row first, which requires reading every
row.

**Fix:** filter on the actual partition column directly, with no
wrapping expression: `WHERE event_date = '2025-06-01'`. If
`event_timestamp` genuinely needs to be the source of truth and
`event_date` was derived from it at load time, that derivation needs to
happen once, at write time (so the partition column is correct and
directly filterable), not be recomputed per-query against a
differently-named raw column.

**The interview tell:** recognizing that this is the *same class* of
bug as a non-sargable predicate defeating an index — partition pruning
and index usage both require the engine to evaluate the filter against
raw column values, unmodified, before it can decide what to skip. A
candidate who's internalized sargability from the SQL side should spot
this instantly rather than treating it as an unrelated warehousing
quirk.

</details>

---

## Case 3: Partitioned by the Wrong Column Entirely

**Setup:** A clickstream table is partitioned by `user_id` (hashed into
1,000 partition buckets via the partitioning DDL itself, not a separate
bucketing step). Nearly every analytical query filters by a date range
("events in the last 7 days"); almost none filter by a specific
`user_id`. Query times are poor across the board.

<details>
<summary>Debrief</summary>

**Diagnosis:** the table is partitioned on a column that essentially no
query actually filters by, and *not* partitioned on the column
(`event_date`) that nearly every query does filter by. A "last 7 days"
query against this layout has no partitions to prune on the filter it
actually has — it must scan all 1,000 user-hash partitions, each
containing a full date range of history, because date isn't a
partitioning boundary anywhere in the layout.

**Fix:** partition by `event_date` (or a coarser date grain matching
actual query patterns), and move the `user_id`-based hashing to
**bucketing** within each date partition instead — bucketing is exactly
the mechanism for distributing by a join/lookup key without needing
queries to filter on it to see a benefit, and it doesn't fight against
the date-range pruning every other query depends on.

**The interview tell:** this is the mirror image of Case 1 — Case 1 had
too many partition columns (including sensible ones diluted by
unnecessary ones); this one has exactly one partition column, but it's
the wrong one. Both are cured by the same discipline: partition on
what queries actually filter by (usually date), and use bucketing for
join/lookup keys that don't belong as partitions.

</details>

---

## Case 4: Bucketed for the Wrong Join Pattern

**Setup:** `fact_orders` and `dim_customer` are both bucketed by
`customer_id` into 64 buckets, specifically to speed up the join
between them. Query logs show that in practice, the overwhelming
majority of analytical queries join `fact_orders` to `dim_product`, not
`dim_customer` — and those product joins are just as slow as before
bucketing was introduced.

<details>
<summary>Debrief</summary>

**Diagnosis:** bucketing was set up for a join pattern that isn't
actually the dominant one. Bucketing only pays off for a join on the
*exact* column two tables are bucketed by — `fact_orders` and
`dim_customer` sharing a `customer_id` bucket layout does nothing for a
join against `dim_product`, which isn't bucketed by anything compatible
at all (or isn't bucketed the same way). The team optimized based on
an assumption about the access pattern rather than the actual query
logs.

**Fix:** rebucket `fact_orders` (and `dim_product`, if it's large enough
to matter) by `product_id` instead, matching the join that's actually
dominant — or, if both join patterns matter roughly equally, evaluate
whether a single fact table can only usefully be bucketed by one key at
a time, and a second bucketed/sorted copy (or a different join strategy
entirely for the less-common pattern) is the more honest trade-off than
optimizing for the wrong one.

**The interview tell:** this is the concrete failure mode behind the
curveball in `04_curveballs_tradeoffs.md` about how you know which
column to bucket on — the honest answer is always "look at actual query
logs before guessing," and this case is what happens when that step
gets skipped in favor of an assumption that felt reasonable at design
time.

</details>

---

## Case 5: The Lakehouse Table That's Somehow Still a Small-File Mess

**Setup:** A team migrated a Hive-style Parquet lake table to Apache
Iceberg specifically to solve small-file problems from streaming
ingestion. Six months later, the table has over 500,000 tiny data
files, and query performance hasn't improved — if anything, planning
time got worse, since the engine now also has to resolve Iceberg's
manifest metadata across all those files.

<details>
<summary>Debrief</summary>

**Diagnosis:** migrating to a table format did not, on its own, fix the
small-file problem — it was never going to. Iceberg (like Delta Lake
and Hudi) still stores ordinary Parquet files underneath; adopting a
table format adds atomicity, schema enforcement, and time travel, and
it adds the *capability* to compact small files automatically, but that
compaction has to actually be scheduled and run. If streaming ingestion
keeps writing small files every micro-batch and nobody runs
`rewrite_data_files` (or the Delta/Hudi equivalent) on a schedule, the
files just keep piling up — now with the added overhead of manifest
metadata tracking all of them, which can make planning *slower* than
plain Hive-style directory listing was.

**Fix:** schedule a recurring compaction job (Iceberg's
`rewrite_data_files` procedure, or the table format's equivalent) as an
operational commitment from day one of the migration, not an
afterthought. The migration's real value — safe deletes, schema
evolution, time travel, multi-engine support — is separate from the
file-size problem, and adopting it doesn't retroactively fix files that
were already small, nor prevent new ones from being written small if
ingestion patterns don't change.

**The interview tell:** recognizing that "we moved to Iceberg" and "we
fixed our small-file problem" are two different claims, and that the
second one requires an explicit, scheduled operational step — this is
exactly the caution named in `concepts/03_file_and_table_formats.md`,
section 4: table formats add automated compaction as a *capability*,
not as something that happens for free just by adopting the format.

</details>

---

**Next:** [04 — Curveballs & Trade-offs](04_curveballs_tradeoffs.md)
