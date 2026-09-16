# 1. Worked Scenarios

Part of the [Interview Questions](README.md) series — see that index for
the full taxonomy of question types.

This file is deliberately **code-free** — no `CREATE` statements, no
SQL, no Python, no directory-listing commands. The point is to rehearse
the *reasoning* an interviewer is actually scoring: how you scope the
problem, name the constraints that actually drive the design, and
narrate the physical layout out loud. Once the reasoning is solid, the
SQL/config is easy — that's what `concepts/` and `practice/` are for.

Four scenarios, each a full worked walkthrough: a multi-TB clickstream
lake storage design, a warehouse-vs-lakehouse architecture decision, a
live diagnosis of a slow query from its physical layout, and a
multi-year IoT retention design that forces a table-format choice.

---

## A. Design the Storage Layout for a Multi-TB Clickstream Lake

**Interviewer prompt:**
> "We ingest roughly 50 million clickstream events a day — page views,
> clicks, add-to-carts — from a web and mobile app. Design the storage
> layout for this in our data lake, from ingestion through to what
> analysts and data scientists actually query."

### Step 1 — Ask clarifying questions before naming a single directory

- **What's the read pattern?** Analysts run daily/weekly aggregate
  reports (funnel conversion, DAU); a separate ML team needs raw,
  ungoverned event-level access for feature engineering. → Two
  different consumers, two different needs — this alone argues for a
  layered (bronze/silver/gold) lake rather than one flat table
  (`concepts/04_data_lake_and_lakehouse_architecture.md`).
- **What's the actual volume?** 50M events/day at roughly 0.5 KB/event
  (JSON) is ~25 GB/day raw, ~9 TB/year — well into "partitioning is not
  optional" territory, not a toy dataset.
- **Do we ever need to update or delete an already-ingested event?**
  Rarely for raw click events themselves, but yes for GDPR-style
  right-to-be-forgotten deletes against a specific user's history. →
  This is the signal that a plain Hive-style Parquet lake isn't enough
  — deleting scattered rows out of immutable files at scale is exactly
  the problem a table format exists to solve
  (`concepts/03_file_and_table_formats.md`).
- **What do queries filter on most?** Almost always a date range; very
  often also filtered or joined by `user_id` for session/funnel
  analysis. → Date is the partition key; `user_id` is a bucketing/join
  key, not a partition key (50M events/day means user_id cardinality is
  far too high to partition on directly — see the over-partitioning
  guidance in `concepts/02_partitioning_and_bucketing.md`).
- **Freshness requirement?** Next-day for most reporting; the ML team
  is fine with the same freshness. → Confirms a batch (or micro-batch)
  ingestion pattern rather than requiring a fully streaming warehouse
  design.

### Step 2 — Bronze: land it raw, exactly as it arrives

> "Raw events land in bronze as JSON Lines (or Avro if we're consuming
> straight off a Kafka topic, since the event schema will evolve as new
> fields get added by app teams), partitioned by ingestion date. No
> transformation, append-only, immutable — this is the replay source if
> anything downstream goes wrong."

```text
s3://lake/bronze/clickstream/date=2025-06-01/*.jsonl
s3://lake/bronze/clickstream/date=2025-06-02/*.jsonl
...
```

Say explicitly *why* Avro (or JSON) rather than Parquet at this stage:
bronze is write-heavy and the schema is still moving — new event types
and fields get added by app teams on their own schedule, and Avro's
reader/writer schema reconciliation (`concepts/03_file_and_table_formats.md`,
section 1) means the ingestion pipeline never breaks because of it.
Bronze is not what analysts or the ML team query directly.

### Step 3 — Silver: Parquet, partitioned by date, at the record grain

> "Silver is the cleaned, validated, deduplicated event stream —
> Parquet, partitioned by event date, still at the individual-event
> grain. Standardize timestamps, drop obviously malformed events,
> dedupe on event ID, and resolve the schema drift bronze allowed."

```text
s3://lake/silver/clickstream/date=2025-06-01/part-0000.parquet
s3://lake/silver/clickstream/date=2025-06-01/part-0001.parquet
...
```

This is where the table-format decision from Step 1's GDPR-delete
requirement actually gets made:

> "I'd put silver (and gold) under an Iceberg table, not plain Hive-style
> Parquet directories. Two reasons: the GDPR delete requirement needs
> row-level `DELETE`, which plain immutable Parquet files can't do
> safely at scale without a table format managing atomic file swaps;
> and 50M events/day means the partition/file layout will need to
> evolve as volume grows — Iceberg's partition evolution means that's a
> metadata change, not a full table rewrite."

### Step 4 — File sizing: don't let 50M events/day become a small-file problem

> "At ~25 GB/day, if this were written as one file per micro-batch every
> few minutes, that's hundreds of tiny files a day, compounding into
> tens of thousands over a year — exactly the over-partitioning/
> small-file trap from `concepts/02_partitioning_and_bucketing.md`. I'd
> target a handful of well-sized (128 MB–1 GB) files per day, either by
> batching writes or by relying on the table format's compaction
> (Iceberg's `rewrite_data_files`) to merge small streaming-ingest files
> into well-sized ones on a schedule."

### Step 5 — Bucketing for the join pattern that actually matters

> "Session and funnel analysis joins clickstream events back to
> `dim_user` constantly. I'd bucket silver on `user_id` — say, 256
> buckets — within each date partition, so that join doesn't require a
> full shuffle every time it runs. I would *not* partition on `user_id`
> directly — cardinality is in the tens of millions, which would create
> an unusable number of partitions; bucketing distributes without
> multiplying partition/metadata count."

### Step 6 — Gold: the two different shapes for two different consumers

> "Gold has two tracks, because the two consumers from Step 1 actually
> need different things. For BI/analyst dashboards: pre-aggregated
> tables — daily funnel conversion by channel, DAU/WAU/MAU — small,
> fast, and exactly what a dashboard queries. For the ML team: gold
> doesn't flatten anything away; it's closer to a curated, feature-ready
> version of silver (session-level rollups, user-level feature
> aggregates) that still preserves event-level granularity where
> needed, because ML feature engineering can't work off pre-aggregated
> BI summaries."

### Step 7 — Trade-offs, stated unprompted

> "The biggest cost in this design is the table format and compaction
> job maintenance — Iceberg buys us safe deletes and partition
> evolution, but it's an operational commitment, not a free upgrade
> over plain Parquet. If GDPR-style deletes and partition scheme changes
> weren't requirements, a simpler Hive-style Parquet lake partitioned by
> date, with periodic manual compaction, would have been a defensible,
> lower-overhead choice for the same 50M-events/day scale."

---

## B. Warehouse vs. Lakehouse for a Mid-Size Company

**Interviewer prompt:**
> "A mid-size e-commerce company (roughly 200 people, a data team of 6)
> is choosing between a Snowflake/BigQuery-style managed warehouse and a
> lakehouse on S3 with Iceberg. Walk me through how you'd decide."

### Step 1 — Refuse to answer in the abstract; ask what's actually driving the question

- **What workloads exist today, and what's coming?** Today: BI
  dashboards, finance reporting, marketing analytics — all SQL-shaped.
  Coming: a data science team wants to build a recommendation model and
  needs raw event-level access, and there's a stated goal of eventually
  running Spark and Trino side by side. → This is the single most
  important fact in the whole scenario — a workload that's *purely*
  BI-shaped today and stays that way argues one direction; a stated
  near-term ML/multi-engine need argues the other, well before either
  system is priced out.
- **Headcount and operational appetite?** A 6-person data team, none of
  whom have run a lakehouse stack (catalog, compaction jobs, table
  format upgrades) before. → A real cost, not a footnote.
- **Existing tooling?** Already deep in dbt against a SQL warehouse
  interface; no existing Spark/Trino investment yet.
- **Budget sensitivity?** Storage/compute cost matters, but not to the
  point of accepting materially worse reliability or slower time-to-
  value to save on it.

### Step 2 — Name the actual trade-off, not the marketing trade-off

> "A managed warehouse (Snowflake/BigQuery) gives the best out-of-box
> query performance, governance, and operational simplicity for
> SQL-shaped BI workloads — someone else runs the compaction jobs, the
> catalog, the query optimizer tuning. A lakehouse on Iceberg gives open
> file access for the ML team's raw-event feature engineering and lets
> Spark and Trino share the exact same tables without duplicating data
> into two systems — at the cost of the data team now owning the table
> format, the catalog, and compaction as operational responsibilities
> themselves, on top of everything a managed warehouse would have
> handled for them."

### Step 3 — Give a decision, with the reasoning stated, not just a name

> "Given a 6-person team with no lakehouse operational experience, and a
> data-science/multi-engine need that's real but not immediate, I'd
> recommend starting with a managed warehouse now, and treating 'move
> the raw event layer to an Iceberg lakehouse, feeding curated tables
> into the warehouse' as the next phase once the ML/multi-engine
> workload is concrete rather than anticipated. The wrong failure mode
> here would be building the full lakehouse stack speculatively, before
> the workload that actually needs it exists, and paying the operational
> cost with nothing yet to show for it."

### Step 4 — Anticipate the natural follow-up

**"What if the ML team's need were already live today, not hypothetical?"**
> Then the calculus changes: duplicating the full event-level dataset
> into a separate lake *and* a warehouse is itself an ongoing cost and a
> conformed-dimension risk (two copies of the same data drifting apart —
> the same failure mode as `data_modeling/interview_questions/03_critique_and_debug.md`,
> Case 8, one layer further down the stack). At that point, a lakehouse
> with curated gold tables also queryable from the warehouse (or gold
> tables loaded *into* the warehouse from the lakehouse) becomes the
> more defensible starting architecture, even with the added operational
> cost, because the alternative — two independently maintained copies of
> the data — is worse.

### Step 5 — Close with the meta-point

> "This is a 'not yet' answer, not a 'never' answer — the architecture
> should track where the actual workload is today, and be revisited
> explicitly as a follow-up decision once the ML/multi-engine need is
> real, rather than treated as a one-time, permanent choice."

---

## C. Diagnose a Slow Query From Its Physical Layout

**Interviewer prompt:**
> "Here's a warehouse query that used to run in a few seconds and now
> takes several minutes: `SELECT customer_id, SUM(amount) FROM
> fact_orders WHERE order_date >= '2025-06-01' AND order_date <
> '2025-07-01' GROUP BY customer_id`. `fact_orders` is a 2 TB table,
> partitioned by `order_date`. What do you check, in what order?"

### Step 1 — Confirm what "used to be fast" implies before guessing

> "Before touching the layout, I'd ask what changed recently — a new ETL
> job, a schema migration, a partitioning change, a big jump in data
> volume — because 'used to be fast, now isn't' usually means something
> *changed*, not that the original design was always wrong."

### Step 2 — Check whether partition pruning is actually happening at all

> "First real check: is the query actually pruning to roughly 30 days of
> partitions, or scanning the whole 2 TB table? I'd look at the query
> plan (`EXPLAIN`) for evidence of partition elimination. If it's
> scanning everything despite the date filter, the most common causes
> are: the filter wraps the partition column in a function or implicit
> cast (`WHERE CAST(order_date AS DATE) >= ...`, or a string/date type
> mismatch) — which defeats pruning the same way a non-sargable
> predicate defeats an index, covered in `sql_foundations/concepts/05_query_optimization_and_indexing.md`
> — or the table's physical partition column doesn't actually match
> what the query is filtering on (e.g. partitioned by `ingested_at`
> while the query filters on `order_date`, a genuinely different
> column)."

### Step 3 — If pruning IS working, check partition and file sizing next

> "If pruning is correctly narrowing to ~30 partitions, the next
> question is whether those partitions themselves are the problem — are
> they reasonably sized (100s of MB to low GBs), or has this table
> quietly become over-partitioned (partitioned by `order_date` AND
> several other columns, or partitioned at too fine a grain), producing
> thousands of tiny files per day that dominate with per-file overhead
> the way `concepts/02_partitioning_and_bucketing.md`, section 5,
> describes? A sudden volume increase (say, the business tripled order
> volume, or a bug started writing many more, smaller batches per day)
> can turn a previously fine partition scheme into a small-file problem
> without anyone changing the partitioning DDL itself."

### Step 4 — Check the aggregation side, not just the scan side

> "`GROUP BY customer_id` over a 30-day window still needs to shuffle
> and aggregate however many rows survive pruning. If `customer_id` has
> very high cardinality and the engine's default parallelism/shuffle
> partition count hasn't been tuned for the data volume, the aggregation
> step itself — not the scan — can be the bottleneck. I'd check whether
> the *scan* time or the *aggregation/shuffle* time dominates the plan
> before assuming it's purely a partitioning problem."

### Step 5 — Name the fix, matched to whichever diagnosis is confirmed

> "If it's a pruning problem: fix the predicate to match the partition
> column's actual type/expression, or repartition the table on the
> column queries actually filter by. If it's a small-file problem: run
> compaction (or fix the ingestion job producing too many small
> batches), and reconsider whether every one of the extra partition
> columns is pulling its weight. If it's a shuffle/aggregation problem:
> that's a compute-tuning fix, not a storage-layout fix, and worth
> naming as a different category of problem rather than reflexively
> reaching for 'add more partitioning.'"

**The interview tell:** the difference between a candidate who says "add
an index" and one who's actually diagnosed the problem is exactly this
sequence — confirm pruning is happening at all, check partition/file
sizing, then check whether the bottleneck is even on the scan side
before proposing a storage-layout fix. See `03_critique_and_debug.md`
for three fully worked versions of this exact family of bug.

---

## D. Multi-Year IoT Sensor Retention and Table Format Choice

**Interviewer prompt:**
> "An industrial IoT platform ingests sensor readings from equipment
> across several factories — potentially billions of readings a day at
> full resolution. The business wants years of historical trend data
> available for analysis, but obviously can't keep raw per-second
> readings at full resolution forever. Design the storage tiering and
> pick a table format."

### Step 1 — Clarifying questions

- **What resolution do different consumers actually need?**
  Operational dashboards want near-real-time, full-resolution alerts
  (handled by a separate streaming system, out of scope here — see the
  IoT scenario's scoping move in `data_modeling/interview_questions/01_worked_scenarios.md`,
  section D, for the identical framing move at the *modeling* layer);
  the *warehouse-facing* trend/reporting use case only ever needs
  minute-level rollups for recent history and daily rollups for
  anything older than roughly a year.
- **Retention requirements?** Minute-level rollups: 13 months. Daily
  rollups: indefinitely, for long-term trend analysis and compliance.
- **Does anything ever need to be corrected after the fact?** Yes —
  sensor calibration errors are occasionally discovered after the fact
  and historical readings need to be recomputed for an affected date
  range. → This is the signal that plain immutable Parquet files aren't
  enough on their own; some mechanism for a safe, auditable overwrite of
  a historical partition is required.
- **Multiple engines?** Yes — Spark for the nightly rollup batch jobs,
  Trino for ad-hoc analyst SQL against the same tables.

### Step 2 — Tiered storage, not one flat table

> "This needs at least two physical tables at two different grains, not
> one table with a 'resolution' column: `sensor_readings_1min` (recent,
> 13-month retention) and `sensor_readings_daily` (indefinite
> retention). Both partitioned by date; the minute-level table also
> bucketed by `sensor_id` for the sensor-level trend queries analysts
> actually run."

```text
sensor_readings_1min:   partitioned by date, bucketed by sensor_id, 13mo retention
sensor_readings_daily:  partitioned by date (coarser: by month once old enough), indefinite retention
```

### Step 3 — Table format decision, argued from the requirements, not by default

> "I'd put both under Iceberg specifically, for two concrete reasons
> tied directly to what was asked, not as a default reach: the
> calibration-correction requirement needs a safe, atomic way to rewrite
> a historical date range's readings — exactly the `MERGE`/`UPDATE`
> guarantee a table format provides over plain Parquet
> (`concepts/03_file_and_table_formats.md`, section 2) — and the
> Spark-plus-Trino multi-engine requirement is Iceberg's strongest
> differentiator among the three table formats (section 3 of that same
> concept file). If this were a single-engine, Databricks-only shop, I'd
> have given the same reasoning but landed on Delta Lake instead — the
> requirements, not brand preference, are what point at Iceberg here."

### Step 4 — Retention as an explicit lifecycle policy, not a manual chore

> "Retention isn't 'someone remembers to delete old partitions' — I'd
> implement it as an automated lifecycle policy: partitions in
> `sensor_readings_1min` older than 13 months are dropped (or archived
> to cold storage) on a schedule, since the daily rollup table already
> preserves the long-term trend signal those minute-level readings
> exist to feed. This is also a real storage-cost lever worth naming
> unprompted — keeping years of minute-level data around indefinitely
> at billions of readings/day would dwarf the cost of the daily rollups
> that actually serve the long-term use case."

### Step 5 — Trade-offs, stated unprompted

> "The daily rollup table trades resolution for retention length — a
> calibration correction discovered two years later can still fix the
> daily aggregates, but the underlying minute-level detail needed to
> recompute a *different* rollup shape from scratch is gone after 13
> months. If a future requirement needed full-resolution reprocessing
> further back than that, this design would need revisiting; I'd flag
> that as a real limitation of this tiering choice, not something the
> design silently papers over."

---

**Next:** [02 — Rapid-Fire Q&A](02_rapid_fire_qna.md)
