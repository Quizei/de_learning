# Data Warehousing & Data Lakes — Practice Exercises

Thirteen exercises covering: OLTP/OLAP classification, warehouse
architecture philosophy (Kimball/Inmon), star schema design for a
warehouse, partition and bucketing strategy, file and table format
selection, data lake zone assignment, data swamp diagnosis, and —
extending past the original set — partition-pruning arithmetic, a
small-file cost calculation, and an Iceberg partition-evolution
scenario.

How to use this file: read the exercise, commit to your own answer
first, and only then expand the reference solution to check yourself.
Where useful, a solution includes runnable Python (standard library
only) exactly as it would run in a `python3` shell.

---

## Exercise 1: OLTP vs. OLAP Classification

Classify each of the following as **OLTP** or **OLAP**, and say why:

```text
a) INSERT INTO orders (customer_id, product_id, qty) VALUES (42, 7, 1)
b) SELECT region, SUM(revenue) FROM sales GROUP BY region
c) UPDATE users SET email = 'new@email.com' WHERE user_id = 123
d) SELECT product_category, AVG(rating), COUNT(*)
   FROM reviews JOIN products USING(product_id)
   WHERE review_date >= '2024-01-01'
   GROUP BY product_category
e) SELECT balance FROM accounts WHERE account_id = 9876
```

<details>
<summary>Reference answer</summary>

```text
a) OLTP -- single-row INSERT, transactional operation
b) OLAP -- aggregation (SUM) with GROUP BY across the whole table
c) OLTP -- single-row UPDATE, point lookup by primary key
d) OLAP -- multi-table JOIN with aggregation and a date-range filter,
           scans potentially millions of rows
e) OLTP -- single-row lookup by primary key, returns one value
```

Pattern: OLTP touches one row, quickly; OLAP touches many rows,
aggregated. *(See `concepts/01_warehouse_architecture.md`, section 1.)*

</details>

---

## Exercise 2: Choose the Warehouse Architecture Philosophy

For each scenario, would you recommend **Kimball** (bottom-up),
**Inmon** (top-down), or **Data Vault**? Justify it.

```text
Scenario A: A fast-growing startup, 3 teams (sales, marketing,
product), no existing warehouse, limited budget, results needed within
weeks.

Scenario B: A large bank, 50+ departments, strict regulatory
requirements demanding enterprise-wide consistent definitions, a
dedicated data team, an 18-month timeline.

Scenario C: A company already running two source systems that
disagree on "customer," bringing on a third with yet another
definition. Reconciliation rules aren't finalized. Loads from all three
must start immediately.
```

<details>
<summary>Reference answer</summary>

**Scenario A: Kimball.** Fast delivery matches startup urgency and
limited budget — build one data mart per team, starting with whichever
delivers value first, and use a bus matrix from day one so the marts
don't silently disagree on shared dimensions as more get added.

**Scenario B: Inmon.** Regulatory requirements demand enterprise-wide
consistency enforced structurally, not just agreed informally; a
dedicated team and 18-month timeline make the upfront normalized-core
investment affordable.

**Scenario C: Data Vault.** The defining constraint is that ingestion
can't wait on reconciliation rules that don't exist yet — hubs and
satellites let all three sources load independently and in parallel
today, with a conformed (Kimball-style) `dim_customer` built on top once
the rules are agreed. Neither pure Kimball nor pure Inmon solves the
"can't wait to agree" problem directly.

*(See `concepts/05_kimball_inmon_data_vault_architecture.md`.)*

</details>

---

## Exercise 3: Design a Star Schema for a Warehouse

A ride-sharing company wants to analyze:
- Revenue by city and time period
- Average trip duration by driver rating
- Busiest hours by day of week
- Rider retention (trips per rider per month)

**Your task:** (1) state the grain, (2) list dimensions and key
attributes, (3) list fact table measures, (4) sketch the star.

<details>
<summary>Reference answer</summary>

**Grain:** one row per completed trip.

```text
Fact table: fact_trips
    Measures: trip_duration_min, distance_miles, fare_amount,
              tip_amount, total_amount, surge_multiplier (non-additive)
    Foreign keys: date_key, time_key, rider_key, driver_key,
                  pickup_location_key, dropoff_location_key

Dimensions:
    dim_date:     date_key, full_date, year, month, day_of_week, is_weekend
    dim_time:     time_key, hour, minute, period (morning/afternoon/evening)
    dim_rider:    rider_key, name, signup_date, tier
    dim_driver:   driver_key, name, rating, vehicle_type
    dim_location: location_key, city, neighborhood, zip_code
                  (used twice: pickup and dropoff -- a role-playing dimension)

                dim_date       dim_time
                   |              |
    dim_rider --- fact_trips --- dim_driver
                   |      |
        dim_location   dim_location
        (pickup)       (dropoff)
```

This is the identical grain/schema-shape reasoning covered in full
depth, with SCD and query-narration detail, in
`data_modeling/interview_questions/01_worked_scenarios.md`, scenario A
— this exercise is the warehouse-physical-layout half of that same
design (see Exercise 6 below for the partition/bucketing layer on top
of this schema).

</details>

---

## Exercise 4: Partition Strategy Design

For each dataset, design a partition strategy: partition key(s),
expected partition count, and estimated partition size. Say whether
bucketing would help, and on which column.

```text
Dataset A: Web server access logs, 500 GB/day, 3-year retention.
           Common queries: filter by date, aggregate by hour.
           Total size: ~500 TB.

Dataset B: E-commerce transactions, 10 million customers,
           50 GB/month of new data. Common queries: filter by date
           AND by customer_id.

Dataset C: IoT sensor readings, 10,000 devices, 1 reading/sec/device.
           Common queries: readings for one device, last hour.
```

<details>
<summary>Reference answer</summary>

**Dataset A:** partition by `year/month/day/hour` — 365 × 24 × 3 ≈
26,280 partitions, ~21 GB each (500 GB ÷ 24 hours). Healthy size, no
bucketing needed — queries are pure time-range scans with no join key
to distribute by.

**Dataset B:** partition by `year/month` (~50 GB/partition, a healthy
size); do **not** partition by `customer_id` (10M customers would
create an unusable partition count). Bucket by `customer_id` — say, 64
buckets — to optimize the join against a customer dimension without
multiplying partition count.

**Dataset C:** partition by `date` (10,000 devices × 86,400 sec/day ≈
864M readings/day — daily partitions stay a reasonable size). Do
**not** partition by `device_id` (10,000 devices would still be too
many partitions relative to the data volume per device per day). Bucket
by `device_id` — say, 128 buckets — so "readings for one device" scans
roughly 1/128th of a day's partition instead of all of it.

*(See `concepts/02_partitioning_and_bucketing.md`, sections 2 and 4.)*

</details>

---

## Exercise 5: File Format Selection

Choose the best file format (CSV, JSON, Parquet, Avro, ORC) for each
scenario and justify it.

```text
a) A data science team runs ad-hoc SQL over 5 TB of sales data in
   Spark, typically selecting 3-4 of 50 columns.
b) A microservice emits click events to Kafka. The event schema
   changes every few weeks. Three different downstream systems
   consume the same topic.
c) A small business exports daily reports for a partner who imports
   them into Excel.
d) A web scraper collects nested product listings with a varying
   JSON structure, stored for later processing.
e) A Hive-based warehouse on Hadoop needs ACID support for upserts
   in nightly batch jobs.
```

<details>
<summary>Reference answer</summary>

```text
a) PARQUET -- columnar layout means Spark reads only the 3-4 needed
   columns' bytes; compression reduces I/O further. Textbook case.
b) AVRO -- schema evolution (fields added over time) is Avro's
   defining strength; a schema registry keeps all three downstream
   consumers working without a coordinated deploy.
c) CSV -- simple, universal, opens directly in Excel; no optimization
   is needed for a small daily export.
d) JSON Lines -- nested, variable structure matches JSON naturally;
   JSONL keeps it appendable and splittable for later processing
   (typically converted to Parquet once it reaches silver).
e) ORC -- native to the Hive ecosystem with built-in ACID transaction
   support; if migrating away from Hive were on the table, Parquet
   plus a table format (concepts/03) would be the modern equivalent.
```

*(See `concepts/03_file_and_table_formats.md`, section 1.)*

</details>

---

## Exercise 6: Data Lake Zone Assignment

Assign each dataset to **Bronze**, **Silver**, or **Gold**, and name the
transformation(s) needed to get it there from the previous zone.

```text
a) Raw JSON from a third-party API, exactly as received.
b) A daily revenue summary table used by the CEO's dashboard.
c) User profiles with standardized addresses, deduped, nulls filled.
d) Raw CSV exports from a legacy CRM system.
e) A pre-joined orders + customers + products table, aggregated by
   month and category, used by the BI tool.
f) Cleaned transaction data with enforced schema, validated amounts,
   standardized currency codes.
```

<details>
<summary>Reference answer</summary>

```text
a) BRONZE -- raw API JSON, no transformation applied
b) GOLD   -- pre-aggregated summary for dashboard consumption
c) SILVER -- cleaned, deduped, standardized, still record-level
d) BRONZE -- raw CSV dump, stored as-is from the legacy system
e) GOLD   -- pre-joined, aggregated, BI-tool ready
f) SILVER -- validated, schema-enforced, standardized transactions

Transformations:
    Bronze -> Silver: parse, validate, dedupe, standardize, enforce schema
    Silver -> Gold: join dimensions, aggregate, compute KPIs
```

*(See `concepts/04_data_lake_and_lakehouse_architecture.md`, section 2.)*

</details>

---

## Exercise 7: Data Swamp Diagnosis

Identify the anti-pattern in each symptom and suggest a fix:

```text
1. An analyst asks "do we have clickstream data?" Nobody knows; they
   search S3 and find 3 folders that might be it.
2. The sales dashboard shows $2M revenue; the finance report shows
   $2.3M. Both are supposedly from the same underlying data.
3. A pipeline writes to s3://lake/customers/ but the JSON sometimes
   has "phone", sometimes "phone_number", sometimes neither.
4. An intern deletes a production partition; there is no way to
   recover it.
5. There are 47 tables with "user" in the name. Some haven't been
   updated in 2 years. Nobody knows which is authoritative.
```

<details>
<summary>Reference answer</summary>

```text
1. NO CATALOG/DISCOVERY
   Fix: a data catalog (Glue Catalog, DataHub, OpenMetadata), with
   every dataset tagged with an owner and description.

2. NO CONFORMED SOURCE OF TRUTH (metrics computed twice, differently)
   Fix: define canonical metrics in one place (a dbt metrics layer or
   a single shared gold table); both dashboards read from it.

3. NO SCHEMA ENFORCEMENT
   Fix: a schema registry at ingestion, validated before writing to
   the lake -- this is precisely what a table format's schema
   enforcement (concepts/03_file_and_table_formats.md) exists to
   prevent at the storage layer, on top of any registry upstream.

4. NO ACCESS CONTROLS / NO VERSIONING OR BACKUP
   Fix: least-privilege IAM policies, plus a table format's snapshot/
   time-travel history (concepts/03) as a built-in rollback path.

5. NO OWNERSHIP / NO LIFECYCLE MANAGEMENT
   Fix: assigned data stewards, and lifecycle policies that archive
   or deprecate tables nobody has touched in a defined window.
```

*(See `concepts/04_data_lake_and_lakehouse_architecture.md`, section 4.)*

</details>

---

## Exercise 8: Table Format Comparison

A streaming e-commerce platform must choose between Delta Lake,
Iceberg, and Hudi, with these requirements:

```text
1. ~100K order events/second ingested from Kafka
2. UPDATE orders when status changes (placed -> shipped)
3. Partition strategy may change as data grows
4. Uses Spark, Trino, AND Flink
5. Needs 90-day time travel for audit/compliance
6. Wants to avoid vendor lock-in
```

For each requirement, name the strongest format; give an overall
recommendation.

<details>
<summary>Reference answer</summary>

```text
1. 100K events/sec ingestion:  Hudi (Merge-on-Read, purpose-built
                                for high-throughput streaming upserts)
2. UPDATE on status change:    all three support it; Hudi's MoR is
                                most naturally suited to it
3. Partition may change:       Iceberg (partition evolution --
                                the only one of the three that avoids
                                a full rewrite)
4. Multi-engine (Spark/Trino/Flink): Iceberg (broadest, most mature
                                multi-engine support)
5. 90-day time travel:         all three support it; not a
                                differentiator on its own
6. Avoid vendor lock-in:       Iceberg (fully open specification,
                                broadest vendor-neutral adoption)

OVERALL: Iceberg, on the strength of requirements 3, 4, and 6 -- but
flag requirement 1 honestly: a Hudi-style Merge-on-Read ingestion path
(or a tuned Iceberg write pattern) may still be worth pairing in for
the highest-throughput part of the pipeline specifically. Naming this
nuance, rather than declaring one format an unqualified winner on
every axis, is the stronger answer.
```

*(See `concepts/03_file_and_table_formats.md`, section 3, and
`interview_questions/05_lakehouse_table_format_tradeoffs.md` for the
full drill.)*

</details>

---

## Exercise 9: Over-Partitioning Fix

A team partitions their 500 GB orders table by
`year/month/day/hour/customer_segment/payment_method`. It now has 2.1
million partitions, averaging 240 KB each, queries are slower than
before partitioning, and the metastore takes 10 minutes to list all
partitions.

**Your task:** (a) explain why performance degraded, (b) propose a
better strategy, (c) calculate the expected partition size, (d) say
whether bucketing would help.

<details>
<summary>Reference answer</summary>

**(a)** 2.1M partitions × 240 KB is a severe small-file problem —
metastore listing, file-open overhead, and query-planning time to
enumerate millions of candidate partitions dominate over the trivial
amount of real data (240 KB) each one holds.

**(b)** Partition by `year/month` only.

**(c)** 500 GB ÷ (roughly 24 months of data) ≈ 20+ GB per partition —
comfortably in the healthy range, or split further to `year/month/day`
(≈ 500 GB ÷ 730 days ≈ 685 MB/day) if daily-grain queries are common
enough to justify it, still within the 128 MB–1 GB guidance.

**(d)** Yes — bucket by `customer_segment` (and drop `payment_method` as
a partition/bucket column entirely; low cardinality low-value columns
like this are better as plain filterable columns). Bucketing lets
segment-filtered queries benefit without multiplying the partition
count the way an extra partition level would.

*(See `concepts/02_partitioning_and_bucketing.md`, section 5, and
`interview_questions/03_critique_and_debug.md`, Case 1, for the fully
narrated version of this exact bug.)*

</details>

---

## Exercise 10: End-to-End Architecture Design

Design the data platform for a food delivery app: 5M monthly active
users, 200K orders/day, 50K restaurants, 20K drivers, real-time
tracking plus historical analytics.

**Your task:** (1) data sources, (2) lake zones and what lives in each,
(3) file formats per zone, (4) orders fact table partition strategy,
(5) warehouse vs. lake vs. lakehouse and why, (6) table format choice
and why, (7) three gold-layer tables with their schemas.

<details>
<summary>Reference answer</summary>

**(1) Sources:** app database (Postgres: users, restaurants, drivers,
menus); event stream (Kafka: orders, GPS pings, clicks); third-party
APIs (payments, maps/routing); operational logs.

**(2) Zones:** Bronze — raw CDC from Postgres, raw Kafka events, raw
API responses. Silver — cleaned orders, validated GPS tracks,
standardized user/restaurant records. Gold — daily revenue, restaurant
performance, driver efficiency, cohort retention.

**(3) Formats:** Bronze — Avro (Kafka streams), JSON (APIs), CSV
(batch exports). Silver/Gold — Parquet under a table format.

**(4) Orders partitioning:** partition `fact_orders` by `order_date`
(200K orders/day → tens to a couple hundred MB/day, a healthy size);
bucket by `customer_id` (32-64 buckets) for join optimization against
`dim_customer`.

**(5) Lakehouse.** Real-time driver tracking plus historical analytics
both need to be served, ideally from shared, open-format tables; ACID
support is needed for order status updates (placed → confirmed →
delivered) without the reliability compromises of a plain Hive lake;
cost-effectiveness at this scale favors open storage over a fully
proprietary warehouse. *(See `concepts/04_data_lake_and_lakehouse_architecture.md`,
section 5, for the fuller decision framework this answer is applying.)*

**(6) Iceberg** — multi-engine need (Spark for batch, Flink for
streaming), likely partition evolution as the business grows, and a
preference to avoid vendor lock-in at this scale.

**(7) Gold tables:**
```text
daily_order_summary:      date, city, total_orders, total_revenue,
                           avg_delivery_time_min, cancellation_rate
restaurant_performance:   restaurant_id, month, total_orders,
                           total_revenue, avg_prep_time_min, avg_rating
driver_efficiency:        driver_id, week, trips_completed,
                           total_earnings, avg_delivery_time_min
```

</details>

---

## Exercise 11: Calculate Partition Pruning Savings

A 20 TB `fact_events` table is partitioned by `event_date`, evenly
across 3 years (1,095 days) of data. A dashboard query filters
`WHERE event_date >= '2025-09-01' AND event_date < '2025-09-08'`
(7 days).

**Your task:** calculate (a) data scanned without partitioning, (b)
data scanned with correct partition pruning, (c) the percentage
reduction, and (d) what would happen to this calculation if the query
instead filtered `WHERE CAST(event_date AS TEXT) LIKE '2025-09%'`.

<details>
<summary>Reference answer</summary>

```python
total_tb = 20
total_days = 1095
query_days = 7

per_day_tb = total_tb / total_days
scanned_with_pruning = per_day_tb * query_days
reduction = 1 - (scanned_with_pruning / total_tb)

print(f"Without pruning: {total_tb} TB scanned")
print(f"With pruning:    {scanned_with_pruning:.3f} TB scanned")
print(f"Reduction:       {reduction:.1%}")
```

```text
Without pruning: 20 TB scanned
With pruning:    0.128 TB scanned
Reduction:       99.4%
```

**(d)** Wrapping `event_date` in `CAST(... AS TEXT)` before comparing it
defeats pruning entirely — the engine can no longer evaluate "which
partitions could match" without first computing the cast on every
row, which requires reading every partition. The query would silently
fall back to scanning the full 20 TB despite still nominally "filtering
by date." *(See `interview_questions/03_critique_and_debug.md`, Case 2,
for the fully worked version of this exact failure.)*

</details>

---

## Exercise 12: Calculate the Small-File Cost

A streaming ingestion job writes one small file per micro-batch, every
2 minutes, 24/7. Each micro-batch is roughly 4 MB. Per-file read
overhead (open/close, scheduling, metadata) is ~50ms; once reading,
throughput is 2 MB/ms.

**Your task:** calculate the number of files produced per day, and
compare total query time to read one day's data (a) as written, versus
(b) after compacting into 8 well-sized files.

<details>
<summary>Reference answer</summary>

```python
files_per_day = (24 * 60) // 2          # a file every 2 minutes
mb_per_file = 4
total_mb = files_per_day * mb_per_file
per_task_overhead_ms = 50
throughput_mb_per_ms = 2.0

# (a) as written: one task per small file
time_as_written = files_per_day * (per_task_overhead_ms + mb_per_file / throughput_mb_per_ms)

# (b) compacted into 8 files
compacted_files = 8
mb_per_compacted_file = total_mb / compacted_files
time_compacted = compacted_files * (per_task_overhead_ms + mb_per_compacted_file / throughput_mb_per_ms)

print(f"Files/day as written: {files_per_day}  ({total_mb} MB total)")
print(f"Time as written:      {time_as_written:,.0f} ms")
print(f"Time after compaction ({compacted_files} files): {time_compacted:,.0f} ms")
print(f"Speedup: {time_as_written/time_compacted:.1f}x")
```

```text
Files/day as written: 720  (2880 MB total)
Time as written:      37,440 ms
Time after compaction (8 files): 580 ms
Speedup: 64.6x
```

Same logical data, dramatically less query time — purely from file
count, with format and compression held constant. This is the
arithmetic behind why a table format's scheduled compaction job
(`concepts/03_file_and_table_formats.md`, section 4) is an operational
necessity for streaming ingestion, not an optional nicety.

</details>

---

## Exercise 13: Iceberg Partition Evolution Scenario

A 5 TB Iceberg table is partitioned by `month`. Query patterns have
shifted: 80% of new queries now filter by a specific day, not a whole
month, and month-level partitions (each holding ~400 GB) are far larger
than what those queries need to scan.

**Your task:** describe what changes on an Iceberg table vs. what would
have been required on a plain Hive-style Parquet table, and state one
thing that does *not* change even with Iceberg's partition evolution.

<details>
<summary>Reference answer</summary>

**On Iceberg:** repartition new incoming data to `day` granularity by
updating the table's partition spec — a metadata operation. Existing
historical data stays exactly where it is, under the old `month` spec;
Iceberg's metadata layer tracks which spec applies to which files, and
a query spanning both old and new data reads correctly across the
boundary without anyone manually migrating historical files.

**On a plain Hive-style Parquet table:** there is no equivalent — the
entire 5 TB (or at least every historical partition someone wants
day-level pruning against going forward) would need to be physically
rewritten into the new directory layout, a real, costly, one-time
migration with a cutover window to manage.

**What does *not* change:** queries against the *old* data (still under
month-level partitioning) still only prune to month granularity — 
partition evolution changes the spec for new data going forward, it
does not retroactively re-lay-out historical files at the finer grain
for free. If day-level pruning is also needed against the historical
data specifically, that still requires an explicit (though
Iceberg-native, `rewrite_data_files`-driven) backfill/compaction pass —
partition evolution avoids a *disruptive* full-table rewrite, it
doesn't eliminate the need to reprocess history if finer pruning is
required there too.

*(See `concepts/03_file_and_table_formats.md`, section 3, and the
curveball on exactly this scenario in `interview_questions/04_curveballs_tradeoffs.md`.)*

</details>
