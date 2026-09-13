# Spark Performance Tuning — Practice Exercises

Nine realistic "your job is slow/broken, what do you check and change" scenarios, covering: reading query plans and DAGs, caching decisions, partitioning and bucketing, data skew and salting, AQE and broadcast joins, Dynamic Partition Pruning (DPP), memory management, executor tuning, and shuffle partitions.

How to use this file: read the scenario, write down your own diagnosis and fix — genuinely commit to an answer before looking — and only then expand the reference answer to check yourself. Each reference answer notes which concept file(s) cover the relevant background, so if you get something wrong it's worth re-reading that concept file rather than just moving on.

---

## Exercise 1: Shuffle Spill at 200 Partitions

A job with the default `spark.sql.shuffle.partitions=200` is processing a 500GB join + groupBy pipeline. The Spark UI shows the shuffle stage "Shuffle Spill (Memory)" at several GB per task and "Shuffle Spill (Disk)" in the hundreds of MB per task on most tasks. The stage takes 3 hours; task times are fairly even across tasks (no obvious skew).

**Your task:** Work out (A) what you'd check first in the Spark UI to confirm the diagnosis, (B) the likely root cause given 500GB / 200 partitions, and (C) the specific config change you'd make, including what number you'd target it toward.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) Check Stages → the shuffle stage → Summary Metrics for Shuffle Spill (Memory) and (Disk), and confirm task times are roughly even (ruling out skew as the cause, since skew would show one/few outlier tasks). *(See Concept 13, section 5 — Shuffle Spill, and the Spark UI notes in Concept 11, section 7.)*

B) 500GB / 200 partitions = 2.5GB/partition on average — far above the recommended ~100-200MB/partition target, so each task's shuffle data doesn't fit in its share of execution memory and spills to disk. *(Concept 13, sections 2 and 4.)*

C) Increase `spark.sql.shuffle.partitions` using the sizing rule:
```text
partitions = total_shuffle_data_size / target_partition_size
           = 500GB / 150MB
           ~= 3400
```
So set `spark.sql.shuffle.partitions` to roughly 3000-4000 (round to a number that divides evenly across total cluster cores, e.g. a multiple of total_cores). Alternatively/additionally, enable AQE (`spark.sql.adaptive.enabled=true`) so future runs adapt automatically as data volume changes. *(Concept 13, sections 3 and 4.)*

</details>

---

## Exercise 2: Reading explain() Output

You run `df.explain()` on a join between a 2-billion-row `orders` table and a 200-row `country_codes` lookup table, and see this physical plan snippet:

```text
*(5) SortMergeJoin [country_id], [id], Inner
:- *(2) Sort [country_id ASC], false, 0
:  +- Exchange hashpartitioning(country_id, 200)
:     +- *(1) Filter isnotnull(country_id)
:        +- FileScan parquet orders...
+- *(4) Sort [id ASC], false, 0
   +- Exchange hashpartitioning(id, 200)
      +- *(3) Filter isnotnull(id)
         +- FileScan parquet country_codes...
```

**Your task:** Work out (A) what join strategy Spark chose and whether it's appropriate here, (B) what the "Exchange" step is and why there are two of them, and (C) what you'd expect the plan to look like instead, and why Spark didn't do that automatically.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) SortMergeJoin — expensive, requires shuffling AND sorting both sides. Not appropriate: `country_codes` is tiny (200 rows), a perfect candidate for a broadcast hash join instead.

B) `Exchange hashpartitioning(...)` is the shuffle step — each side is repartitioned by the join key so matching keys land on the same reduce partition. Two Exchanges appear because SortMergeJoin requires BOTH sides to be shuffled and sorted by the join key. *(Concept 13, section 1 — this is exactly the map-side/reduce-side shuffle mechanic described there, applied to both join inputs.)*

C) Expected instead: BroadcastHashJoin, with `country_codes` sent whole to every executor and NO exchange/shuffle needed at all — eliminates shuffling the 2-billion-row `orders` table entirely. Spark likely didn't do this automatically because `country_codes`' estimated size (from table/file statistics) exceeded `spark.sql.autoBroadcastJoinThreshold` (default 10MB) — possibly stats were stale/missing, or the threshold is set too low. Fix: `orders.join(broadcast(country_codes), "id")` to force it, or raise `autoBroadcastJoinThreshold`, or run `ANALYZE TABLE` to refresh size statistics.

</details>

---

## Exercise 3: Too Many Stages for a "Simple" Job

A colleague writes:

```python
result = (
    df.filter(F.col("amount") > 0)
      .groupBy("region").agg(F.sum("amount").alias("total"))
      .orderBy("total", ascending=False)
      .withColumn("rank", F.row_number().over(
          Window.orderBy(F.desc("total"))))
)
result.show()
```

They're confused why the Spark UI shows 3 separate stages for what looks like "one pipeline."

**Your task:** Work out (A) each shuffle boundary in this code and why it exists, and (B) whether the `Window.orderBy` with no `partitionBy` is a concern here, and why.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) Three shuffle boundaries → three stage transitions:
1. `groupBy("region").agg(...)` — wide transformation, shuffles by region.
2. `orderBy("total")` — a global sort requires a range-partitioning shuffle across ALL data (Spark samples the data to build range boundaries, then shuffles).
3. `Window.orderBy(...)` with no `partitionBy` — this is a GLOBAL window, meaning ALL rows get shuffled into a SINGLE partition to compute `row_number()` over the entire dataset in one unpartitioned window.

*(Each of these is a wide transformation in the sense described in Concept 13, section 1 — anything where an output partition can depend on data from any input partition triggers a shuffle/stage boundary.)*

B) Yes, this is a real concern: a window with no `partitionBy` collapses everything onto one task/partition, which doesn't parallelize and can OOM or run very slowly if there are many groups. Since this is after a `groupBy("region")` aggregation, the row count is small (one row per region) so it may be fine here — but the same pattern on ungrouped, high-cardinality data would be a serious anti-pattern. Prefer adding a `partitionBy` if there's any grouping key available.

</details>

---

## Exercise 4: Cache Placed in the Wrong Spot

A pipeline does:

```python
raw = spark.read.parquet("events/")          # 800GB
raw.cache()
cleaned = raw.filter(F.col("event_type").isNotNull()) \
              .withColumn("day", F.to_date("ts"))

report_a = cleaned.groupBy("day").count()
report_b = cleaned.groupBy("event_type").count()
report_a.show()
report_b.show()
```

The cluster has 400GB total executor memory. The job is slower than an uncached version a teammate wrote, and the Storage tab shows "Fraction Cached: 41%".

**Your task:** Work out (A) why caching `raw` here isn't helping (or is actively hurting), and (B) what should be cached instead, and why.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) `raw` is 800GB but the cluster only has 400GB total executor memory — it can never fully fit (confirmed by "Fraction Cached: 41%"). Spark spends time trying to cache blocks, evicting some, recomputing evicted ones later — pure overhead with no reuse benefit, since `raw` itself is only read once (it's immediately transformed into `cleaned`, which is the thing that's actually reused by `report_a` and `report_b`). *(This ties directly into Concept 11's storage-memory eviction mechanics — a partially-cached DataFrame above the storage safe zone gets evicted and recomputed rather than protected.)*

B) Cache `cleaned` instead of `raw` — it's the DataFrame that's reused twice (`report_a`, `report_b`), and depending on selectivity of the `isNotNull()` filter it should be meaningfully smaller than `raw`. Even then, check its size against 400GB before caching; if still too big, consider caching only the columns actually needed downstream (`select` before `cache`) to shrink it further, or skip caching and let AQE reuse the scan if the plan allows it.

</details>

---

## Exercise 5: Same Join, Every Day, Still Shuffling

Every night, a job joins a 3TB `transactions` table with a 200GB `accounts` table on `account_id`. Both tables are read fresh from Parquet each run, and both sides get shuffled (`Exchange hashpartitioning`) every single time, even though the join key and both tables' contents are largely stable day to day.

**Your task:** Work out (A) what Spark feature eliminates the repeated shuffle for a join that happens over and over on the same key, and (B) what you need to do differently at WRITE time, and the tradeoff involved.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) Bucketing. If both tables are written pre-bucketed by `account_id` with the same number of buckets, Spark can perform a bucketed join with NO shuffle on either side — each bucket file already holds exactly the rows for a hash-partition of `account_id`, matching what a shuffle would have produced anyway. *(This directly avoids the "Exchange" step described in Concept 13, section 1 and shown in Exercise 2's plan.)*

B) At write time:
```python
transactions_df.write.bucketBy(256, "account_id").sortBy("account_id") \
    .saveAsTable("transactions_bucketed")
accounts_df.write.bucketBy(256, "account_id").sortBy("account_id") \
    .saveAsTable("accounts_bucketed")
```
Both tables must use the SAME bucket count and be saved as managed tables (bucketing metadata lives in the metastore, not plain Parquet files read via `spark.read.parquet`). Tradeoff: bucketing is a write-time cost (extra sort/shuffle once, when the table is written or rewritten) traded for near-zero join-time shuffle cost on every subsequent read — worth it exactly because this join happens nightly, but a bad trade for a table written once and joined once.

</details>

---

## Exercise 6: One Task Runs 45 Minutes, the Rest Finish in 90 Seconds

A join between `orders` (2B rows) and `products` (5M rows) on `product_id` shows in the Spark UI: 199 of 200 tasks finish within 90 seconds, but one task is still running 45 minutes later. Digging into the partition, you find `product_id = "UNKNOWN"` accounts for 35% of all rows in `orders`.

**Your task:** Work out (A) the root cause, precisely (not just "skew"), (B) a salting fix in enough detail to implement it, given that `products` (5M rows) is too big to broadcast outright, and (C) whether there's an alternative to salting for this specific case, given that "UNKNOWN" is a known, single bad key (not distributed skew).

<details>
<summary>Reference answer (try it yourself first)</summary>

A) Hash-partitioning by `product_id` sends every row with the SAME key to the SAME reduce partition. Since "UNKNOWN" is 35% of 2B rows (~700M rows), one partition/task gets ~700M rows while the other 199 split the remaining 65% roughly evenly — one task inherently has ~100x+ more work than its peers.

B) Salting:
1. Add a random salt column (0..N-1) to the skewed side:
```python
salted_orders = orders.withColumn("salt", (F.rand() * 10).cast("int")) \
    .withColumn("salted_key", F.concat("product_id", F.lit("_"), "salt"))
```
2. Explode the small side across all salt values so every salted key has a match:
```python
salted_products = products.crossJoin(spark.range(10).withColumnRenamed("id", "salt")) \
    .withColumn("salted_key", F.concat("product_id", F.lit("_"), "salt"))
```
3. Join on `salted_key` instead of `product_id`. "UNKNOWN"'s ~700M rows now split across 10 partitions (~70M each) instead of 1.

C) Since it's a single known bad key, isolate-and-union is simpler than full salting: filter `orders` into two DataFrames (`product_id == "UNKNOWN"` vs not), handle "UNKNOWN" separately (e.g. broadcast just the one matching `products` row, or process it with extra repartitioning for parallelism), join the rest normally, then union the results. Also worth trying: `spark.sql.adaptive.skewJoin.enabled=true` (AQE skew join), which detects and auto-splits skewed partitions without manual salting — try this FIRST since it requires no code change.

</details>

---

## Exercise 7: AQE Enabled, Still Getting a Shuffle Join

`spark.sql.adaptive.enabled` is true (default). A join between a large fact table and a dimension table that's "usually small" still executes as a SortMergeJoin, not a broadcast join, even though AQE is supposed to be able to convert joins at runtime.

Later you find the dimension table query includes a filter that, at plan time, Spark's optimizer couldn't estimate well (a UDF-based filter), so the pre-shuffle size estimate was wrong — but AFTER the shuffle, the actual side turned out to be only 40MB.

**Your task:** Work out (A) why the static optimizer didn't choose a broadcast join up front, (B) what AQE feature should have caught this at runtime and what config controls it, and (C) a more robust fix that doesn't rely on AQE guessing correctly.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) The static (pre-execution) Catalyst optimizer relies on table/column statistics to estimate output sizes. A UDF-based filter is a black box to the optimizer — it can't estimate its selectivity, so it likely fell back to a conservative/default estimate that exceeded `spark.sql.autoBroadcastJoinThreshold`, ruling out a broadcast join at plan time.

B) AQE's dynamic join strategy conversion: after the shuffle map stage completes and Spark has the ACTUAL post-filter size (40MB), AQE can replace a planned SortMergeJoin with a BroadcastHashJoin at runtime. This is controlled by `spark.sql.adaptive.enabled` (must be true, which it is) — there isn't a separate toggle beyond AQE itself being on, though `spark.sql.autoBroadcastJoinThreshold` still governs the size cutoff AQE uses for the runtime decision. If it still didn't convert, check whether the threshold itself is set too low for actual 40MB.

C) A more robust fix regardless of AQE's runtime guess: explicitly hint the join — `fact.join(broadcast(dim_filtered), "key")` — so the decision doesn't depend on statistics estimation succeeding at all. Explicit broadcast hints are unaffected by UDF-opacity issues.

</details>

---

## Exercise 8: Full Table Scan Despite a Partitioned Table

`sales` is a Parquet table partitioned by `sale_date` on disk (2000+ date partitions, ~5 years of data). This query:

```python
active_regions = spark.table("regions").filter(F.col("is_active") == True)
result = spark.table("sales").join(active_regions, "region_id") \
               .filter(F.col("sale_date") >= "2024-01-01")
```

still scans far more `sale_date` partition directories than expected — close to the full table — based on the "number of files read" metric in the query plan / Spark UI.

**Your task:** Work out (A) why Dynamic Partition Pruning (DPP) would even be relevant here given `sale_date` is already in a static filter (`>= "2024-01-01"`), (B) the more likely explanation for scanning far more than expected and what you'd check, and (C) what conditions DPP requires to kick in for the JOIN side of a query like this.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) It's a trick in how the question is framed — the static filter (`sale_date >= "2024-01-01"`) should ALREADY be pruning most partitions via ordinary static partition pruning (no DPP needed for that part). DPP would matter if the partitioning column were filtered indirectly THROUGH the join (e.g. if `region_id`, not `sale_date`, were the partition column, and `active_regions` filtered which `region_id`s mattered) — so the real question is why even the STATIC filter isn't pruning.

B) Likely explanations: (1) the filter is applied AFTER the join in the DataFrame code but Catalyst failed to push it down (check `explain()` for a `PartitionFilters` entry on the `sales` FileScan — if it's empty or shows the full range, pushdown didn't happen); (2) `sale_date` is stored as a STRING and compared against a string literal in a way that defeats partition pruning (e.g. an implicit cast); (3) the table isn't actually registered with partition discovery (missing `MSCK REPAIR TABLE` / no partition metadata refreshed after new data landed). Check `explain()` for `PartitionFilters: []` (empty = not pruning) vs a populated list.

C) For DPP to prune the FACT table based on a filter applied to the dimension table through a join: (1) the join must be on the partitioned column (or DPP won't have anything to propagate), (2) the dimension side must be small enough to be broadcast (DPP's dynamic filter is built from a broadcast of the filtered dimension keys), and (3) `spark.sql.optimizer.dynamicPartitionPruning.enabled` must be true (default). Without a broadcast-eligible dimension side, DPP can't build the reused broadcast filter and won't prune.

</details>

---

## Exercise 9: Executor Lost: OutOfMemoryError During a Join

A job fails with executors dying mid-stage, logs showing `java.lang.OutOfMemoryError: Java heap space` during a SortMergeJoin stage. Config: `--executor-memory 8g`, `--executor-cores 8`, `--num-executors 20`, `spark.sql.shuffle.partitions=200`. The join is between a 900GB table and a 400GB table (neither broadcast-eligible), on a cluster with otherwise-healthy, evenly distributed partition sizes (no skew detected in the Spark UI).

**Your task:** Work out (A) using the sizing rule from Concept 13, roughly how big each shuffle partition is here, and whether that's consistent with the OOM; (B) independent of partition count, what `--executor-cores 8` with `--executor-memory 8g` implies about memory PER CONCURRENT TASK, and how that makes things worse; and (C) two concrete config changes (not "add more hardware") that address this from two different angles.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) Total shuffle data ~= 1.3TB (900GB+400GB, roughly, before considering join output size). 1.3TB / 200 partitions ~= 6.5GB per partition — far above the ~100-200MB target from Concept 13 and consistent with OOM: each task's execution memory share must hold a multi-GB sort buffer.

B) With `executor-cores=8`, up to 8 tasks run CONCURRENTLY in one 8GB executor, all drawing from the SAME unified memory pool (Concept 11). Even after the reserved/user memory split, each task might realistically get roughly `(unified_memory / 8)` under contention — a small fraction of an already modest 8GB heap. Combined with ~6.5GB partitions from (A), there's no way each concurrent task's slice covers its partition's sort buffer without spilling heavily or OOMing outright.

C) Two independent angles:
1. **Shuffle-partitions angle:** raise `spark.sql.shuffle.partitions` to roughly `1.3TB / 150MB ~= 9000` (round to a clean multiple of total cores), shrinking per-task memory needs directly. *(Concept 13.)*
2. **Executor-shape angle:** reduce `executor-cores` (e.g. to 4 or 5) and/or raise `executor-memory`, so fewer concurrent tasks compete for a larger or less-contended memory pool per executor — e.g. `--executor-cores 4 --executor-memory 16g` keeps similar total cluster memory-per-core but gives each concurrent task roughly 2x the room. *(Concept 12.)*

Either change alone likely helps; both together is the safer fix.

</details>
