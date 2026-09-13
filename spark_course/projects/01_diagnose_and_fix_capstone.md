# Capstone Project: Diagnose and Fix a Slow Spark Pipeline

## Scenario

You've inherited a nightly PySpark job at a mid-size retailer. It:

1. Reads a partitioned Parquet fact table of order line items (`orders_fact`, partitioned by `order_date`, ~500GB, highly skewed towards a handful of "mega" customer_ids that place huge bulk orders).
2. Joins it against a small dimension table (`customers_dim`, ~50k rows, a few MB) to bring in customer tier/region.
3. Computes, per customer per day: total spend (groupBy + sum) and a running 7-day spend total (a window function).
4. Filters down to a specific recent date range.
5. Writes the result out as Parquet, partitioned by `order_date`.

On paper this is a simple job. In production it takes 3+ hours, spills heavily to disk, and one task in the join stage runs 40x longer than the rest. The code below is a realistic "as we found it" version with SEVERAL deliberately-planted performance problems layered on top of each other — exactly the kind of thing you'll be asked to diagnose in a senior data engineering interview, or on an actual on-call shift.

## Learning Goal

Given only the "BEFORE" code and a rough description of symptoms, identify each planted problem, explain WHY it hurts, and describe the fix — before looking at the "AFTER" reference solution. This exercises nearly every concept in this course at once: join strategy selection, shuffle partition sizing, skew, salting, caching discipline, file sizing on write, and partition pruning.

This project is meant to be READ and REASONED ABOUT more than executed line-by-line against a real cluster (there's no real 500GB table sitting around). The illustrative PySpark code below is still valid, runnable Python when embedded in the original script — it lives inside string blocks / behind `PYSPARK_AVAILABLE` guards, so the source file runs cleanly and prints the walkthrough even without a cluster.

---

## The Pipeline (as submitted for review)

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("nightly_customer_spend").getOrCreate()

# ---- Read partitioned fact table ----
orders_fact = spark.read.parquet("s3://lake/orders_fact/")   # partitioned by order_date

# ---- Read small dimension table ----
customers_dim = spark.read.parquet("s3://lake/customers_dim/")

# ---- Cache the fact table "just in case" ----
orders_fact.cache()

# ---- Join fact to dimension (no broadcast hint) ----
joined = orders_fact.join(
    customers_dim,
    orders_fact.customer_id == customers_dim.customer_id,
    "inner",
)

# ---- Filter to the last 30 days -- AFTER the join ----
recent = joined.filter(
    F.col("order_date") >= F.date_sub(F.current_date(), 30)
)

# ---- Daily spend per customer ----
daily_spend = (
    recent.groupBy("customer_id", "order_date", "region", "tier")
    .agg(F.sum("line_total").alias("daily_total"))
)

# ---- Running 7-day total per customer ----
w = (
    Window.partitionBy("customer_id")
    .orderBy("order_date")
    .rowsBetween(-6, Window.currentRow)
)
result = daily_spend.withColumn("rolling_7d_total", F.sum("daily_total").over(w))

# ---- Write out, partitioned by order_date ----
(
    result
    .repartition(400)
    .write
    .mode("overwrite")
    .partitionBy("order_date")
    .parquet("s3://lake/customer_spend_report/")
)
```

---

## Your Task

Before reading further, go through the pipeline above and find as many performance problems as you can. For each one, write down: what's wrong, and what you'd change.

1. The join between `orders_fact` (~500GB) and `customers_dim` (~50k rows, a few MB) has no broadcast hint, so Spark's default planner may still pick it correctly via auto-broadcast threshold detection — but if `customers_dim` isn't reliably under that threshold (stale stats, a slightly larger table than expected), it silently falls back to a full Sort-Merge Join, shuffling the entire 500GB fact table for no reason. (See `concepts/14_join_strategies.md` and `concepts/09_aqe_and_broadcast_joins.py`.)

2. The date-range filter (`order_date >= ...`) is applied AFTER the join, not before it and not on the raw partitioned read. Since `orders_fact` is partitioned by `order_date`, filtering before/at read time lets Spark PRUNE partitions and skip reading ~11+ months of irrelevant data entirely. Filtering after the join means the full table is read, joined, and shuffled first, and only THEN reduced down to 30 days' worth of rows. (See `concepts/10_dynamic_partition_pruning.py`.)

3. `orders_fact.cache()` is called on the raw fact table, but it's only ever used ONCE (in the join immediately after). Caching costs time (materializing to memory/disk) and memory pressure for a DataFrame that's never reused — pure overhead here. (See `concepts/04_caching_and_persistence.py`.)

4. `customer_id` is heavily skewed — a handful of "mega" customers dominate the row count. A plain groupBy/join on `customer_id` sends a disproportionate share of rows to whichever task handles those keys, and that task becomes the straggler that determines the whole stage's runtime (the "one task runs 40x longer" symptom). (See `concepts/07_data_skew.py` and `concepts/08_salting.py`.)

5. `spark.sql.shuffle.partitions` is left at its default (200), and `result.repartition(400)` is a second, independent, somewhat arbitrary number chosen right before the write. Neither number is derived from the actual data volume (500GB fact table filtered to 30 days is still likely tens of GB) — shuffle partition count should be sized to target ~100-200MB per partition, not left at a one-size-fits-all default or a guessed constant. (See `concepts/13_shuffle_partitions.py`.)

6. The final write is `.repartition(400).write.partitionBy("order_date")`. Combined with a 30-day date partitioning, this creates up to 400 x 30 = 12,000 potential file-partition combinations for what might be a modest amount of actual data after filtering — classic small-file problem on write. (See `concepts/15_file_formats_columnar_storage.md`.)

7. The window function's shuffle (`partitionBy("customer_id")`) and the join's shuffle (also effectively keyed around `customer_id` once its skew is addressed) are two SEPARATE wide operations with the same effective grouping key. There's an opportunity to reduce redundant shuffles by thinking about operation order and partitioning consistently, rather than shuffling by the same key twice without reusing that layout. (See `concepts/05_data_partitioning.py` and `concepts/16_window_functions.md`.)

8. There is no AQE-related configuration mentioned at all (adaptive broadcast conversion, coalescing post-shuffle partitions, or skew join handling), even though this job would benefit from all three given the symptoms described. (See `concepts/09_aqe_and_broadcast_joins.py`.)

---

## Reference Solution

<details>
<summary>Click to reveal — try the task yourself first</summary>

```python
# ============================================================
# reference solution -- try the TODOs yourself first!
# ============================================================
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = (
    SparkSession.builder
    .appName("nightly_customer_spend")
    # Fix TODO 8: enable AQE (often default-on in modern Spark, but explicit
    # here) -- lets Spark convert a planned SMJ to BHJ at runtime, coalesce
    # small post-shuffle partitions automatically, and split skewed partitions.
    .config("spark.sql.adaptive.enabled", "true")
    .config("spark.sql.adaptive.skewJoin.enabled", "true")
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    .getOrCreate()
)

# Fix TODO 5: don't leave shuffle partitions at a blind default OR a guessed
# constant -- size it off the expected post-filter data volume. (~20-30GB
# after the 30-day filter, targeting ~150MB/partition -> ~150-200 partitions.)
spark.conf.set("spark.sql.shuffle.partitions", "160")

# ---- Fix TODO 2: filter on order_date BEFORE the join, directly on the
# partitioned read, so Spark can PRUNE partitions and never read the other
# ~11 months of data at all. ----
recent_fact = (
    spark.read.parquet("s3://lake/orders_fact/")
    .filter(F.col("order_date") >= F.date_sub(F.current_date(), 30))
)

customers_dim = spark.read.parquet("s3://lake/customers_dim/")

# ---- Fix TODO 3: no .cache() here -- recent_fact is used exactly once
# (in the join below), so materializing a cache would be pure overhead. ----

# ---- Fix TODO 1: explicitly broadcast the small dimension table. This
# removes any dependency on auto-broadcast-threshold stats being fresh/
# correct, and guarantees no shuffle of the (now already-pruned) fact side. ----
joined = recent_fact.join(
    F.broadcast(customers_dim),
    recent_fact.customer_id == customers_dim.customer_id,
    "inner",
)

# ---- Fix TODO 4: salt the skewed customer_id key for the groupBy so no
# single "mega customer" key sends all its rows to one task. We spread
# each mega customer's rows across N salted sub-keys, aggregate at that
# finer grain, then re-aggregate back down to the true customer_id level. ----
SALT_BUCKETS = 12

salted = joined.withColumn(
    "salt",
    (F.rand() * SALT_BUCKETS).cast("int"),
)

partial_daily_spend = (
    salted.groupBy("customer_id", "order_date", "region", "tier", "salt")
    .agg(F.sum("line_total").alias("partial_total"))
)

daily_spend = (
    partial_daily_spend.groupBy("customer_id", "order_date", "region", "tier")
    .agg(F.sum("partial_total").alias("daily_total"))
)

# ---- Running 7-day total per customer (window logic unchanged -- the fix
# was upstream, in de-skewing the data feeding into it; see TODO 7 note
# below about shuffle reuse). ----
w = (
    Window.partitionBy("customer_id")
    .orderBy("order_date")
    .rowsBetween(-6, Window.currentRow)
)
result = daily_spend.withColumn("rolling_7d_total", F.sum("daily_total").over(w))

# Fix TODO 7 (partial): daily_spend's final groupBy already shuffles by
# customer_id; the window's partitionBy("customer_id") reuses a
# compatible partitioning, so with AQE's adaptive execution and the
# optimizer's plan, Spark can often avoid a second full re-shuffle if the
# partitioning already matches -- verify with .explain() rather than
# assuming; this is inherently something to confirm per Spark version.

# ---- Fix TODO 6: don't blindly repartition(400) right before a write
# that's ALSO partitioned by order_date. Since the shuffle partitions are
# now sized reasonably (TODO 5) and the data is pruned to 30 days (TODO 2),
# let the natural partition count flow through, or coalesce modestly if
# needed, instead of forcing a large arbitrary number that multiplies out
# against 30 date partitions into thousands of small files. ----
(
    result
    .coalesce(30)  # ~1 well-sized file per order_date partition, tune to data volume
    .write
    .mode("overwrite")
    .partitionBy("order_date")
    .parquet("s3://lake/customer_spend_report/")
)
```

### Summary: problem -> concept file -> fix

| Problem | Concept file | Fix |
|---|---|---|
| No broadcast hint on small dim table | `14_join_strategies.md` / `09_aqe_and_broadcast_joins.py` | `F.broadcast(customers_dim)` |
| Filter applied after join, no partition pruning | `10_dynamic_partition_pruning.py` | Filter `order_date` on the raw partitioned read, before the join |
| Caching a DataFrame used only once | `04_caching_and_persistence.py` | Remove the `.cache()` call |
| Skewed `customer_id` causing a straggler task | `07_data_skew.py` / `08_salting.py` | Salt the key, aggregate in two phases, then drop the salt |
| Shuffle partitions left at default / guessed constant | `13_shuffle_partitions.py` | Size `spark.sql.shuffle.partitions` off actual post-filter data volume |
| Over-partitioned output -> small-file problem | `15_file_formats_columnar_storage.md` | `coalesce()` to a sensible file count before the partitioned write |
| Redundant shuffles on the same effective key | `05_data_partitioning.py` / `16_window_functions.md` | Check `explain()` for reused partitioning instead of assuming a re-shuffle |
| No AQE configuration despite symptoms fitting it | `09_aqe_and_broadcast_joins.py` | Enable `adaptive.enabled`, `skewJoin.enabled`, `coalescePartitions.enabled` |

### Illustrative check: salting spreads a skewed key's rows

A tiny, real (non-Spark) sanity check standing in for "does the salting math work out" — purely illustrative, so it runs cleanly without a cluster or a real 500GB table. Simulated row counts per `customer_id` before salting show a few mega customers dominating, then the same rows spread across `salt_buckets` sub-keys.

```python
# Simulate row counts per customer_id before salting: a few mega
# customers dominate.
customer_row_counts = {
    "cust_normal_1": 500,
    "cust_normal_2": 800,
    "cust_normal_3": 650,
    "cust_mega_1": 2_000_000,   # dramatically skewed key
}

salt_buckets = 12

# After salting, cust_mega_1's rows are spread across `salt_buckets`
# sub-keys roughly evenly -- simulate the resulting max per-partition load.
salted_counts = {}
for cust, count in customer_row_counts.items():
    per_bucket = count // salt_buckets
    remainder = count % salt_buckets
    for b in range(salt_buckets):
        key = (cust, b)
        salted_counts[key] = per_bucket + (1 if b < remainder else 0)

max_before = max(customer_row_counts.values())
max_after = max(salted_counts.values())
```

**Output:**
```text
Original row counts per customer_id: {'cust_normal_1': 500, 'cust_normal_2': 800, 'cust_normal_3': 650, 'cust_mega_1': 2000000}

Max rows landing on a single key BEFORE salting: 2,000,000
Max rows landing on a single (key, salt) pair AFTER salting: 166,667
Reduction in worst-case single-task load: 12.0x
```

</details>

---

## How to Use This Capstone

1. Read the pipeline above. Without reading further, write down (or say out loud, interview-style) every performance problem you can spot and why each one hurts.
2. Compare your list against the numbered task list.
3. Read the reference solution and confirm you understand WHY each change fixes its corresponding problem — not just what changed syntactically.
4. If you have a real cluster available, try reproducing a scaled-down version of this scenario (a synthetic skewed dataset) and confirm the fixes actually change stage timings and task distributions in the Spark UI — reading about skew is not the same as watching one task take 40x longer in the Stages tab.
