# Concept 09: Adaptive Query Execution (AQE) & Broadcast Joins

**Covers:**
- What a broadcast join is and why it avoids shuffling the large side
- `autoBroadcastJoinThreshold` and the `broadcast()`/`F.broadcast()` hint
- Risks of broadcasting a table that's too large (OOM)
- What Adaptive Query Execution (AQE) is and why it needs a shuffle boundary to kick in
- AQE's three runtime optimizations: coalescing partitions, switching to broadcast join, and splitting skewed partitions
- Simulation: static plan (SMJ) vs AQE re-optimized plan (BHJ) driven by actual post-shuffle row counts

*The PySpark snippets below are educational/conceptual — they describe what really happens against a real Spark session, but the worked examples are simulated in plain Python so you can follow along without a cluster.*

---

## 1. What is a broadcast join?

A broadcast join avoids shuffling the LARGE side of a join entirely. Instead, Spark copies the SMALL side's entire dataset to every executor (a "broadcast" — one copy per executor, not per task), and each executor performs the join locally against its local partition of the large side.

This eliminates the need to redistribute (shuffle) the large table by join key, which is normally the most expensive part of a join.

Requirements / triggers:

- Spark auto-broadcasts a side if its ESTIMATED size (from table statistics or a file-size estimate) is below `spark.sql.autoBroadcastJoinThreshold` (default: 10 MB, `"10485760"`).
- You can force it regardless of the estimate with a hint: `df_large.join(F.broadcast(df_small), "key")` or the SQL hint `/*+ BROADCAST(small_table) */`.

```text
Shuffle join (both sides large):        Broadcast join (one side small):

large_df      large_df                  large_df (stays put, no shuffle)
   |             |                         |         |         |
   v             v                      Partition Partition Partition
Exchange      Exchange                     0         1         2
(shuffle)     (shuffle)                    |         |         |
   |             |                         +----+----+----+----+
   +------+------+                              |
          v                                      v  (small_df copied whole
    SortMergeJoin                          to EVERY executor)
                                          +-----------------+
                                          |  small_df (full) |
                                          +-----------------+
                                          BroadcastHashJoin locally,
                                          zero shuffle of large_df
```

```python
from pyspark.sql import functions as F

# Spark decides automatically if small_df's estimated size
# is below spark.sql.autoBroadcastJoinThreshold (default 10MB):
result = large_df.join(small_df, "customer_id")

# Force a broadcast regardless of the size estimate:
result = large_df.join(F.broadcast(small_df), "customer_id")

# Check the threshold / change it:
spark.conf.get("spark.sql.autoBroadcastJoinThreshold")   # '10485760' (10MB)
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", 50 * 1024 * 1024)

result.explain()
# == Physical Plan ==
# *(2) BroadcastHashJoin [customer_id], [customer_id], Inner, BuildRight
# :- *(2) FileScan parquet large_df ...
# +- BroadcastExchange HashedRelationBroadcastMode
#    +- *(1) FileScan parquet small_df ...
```

---

## 2. Risks of broadcasting too-large data

Broadcasting is only safe when the "small" side genuinely fits comfortably in memory on every executor:

- The FULL broadcast table is materialized in the driver first (to build the broadcast variable), then sent to every executor. A too-large broadcast can OOM the DRIVER before it even reaches the executors.
- Each executor holds one full copy of the broadcast table IN ADDITION to its normal partition data and other memory needs — broadcasting a 5 GB table to 20 executors doesn't cost 5GB total, it costs roughly 5GB PER EXECUTOR that must all fit in the executor's memory budget alongside everything else it's doing.
- Manually forcing `F.broadcast()` on a table that turns out larger than expected (e.g. after an upstream filter didn't reduce it as much as assumed) is a common cause of executor OOM errors in production Spark jobs.
- Spark will refuse to auto-broadcast anything above `spark.sql.autoBroadcastJoinThreshold`, but an explicit `F.broadcast()` hint OVERRIDES that safety check — use explicit hints carefully.

Rule of thumb sizing check before forcing `F.broadcast()`:

```text
    estimated_table_size_per_executor <= 0.3 x executor_memory
    (leaving room for the executor's own task data, shuffle buffers,
     and JVM/Python overhead)
```

Failure modes when the "small" side is actually too large:

- Driver OOM while collecting/building the broadcast variable
- Executor OOM holding the broadcast copy in memory
- Extremely slow broadcast distribution over the network (multi-GB "small" tables sent to every executor)

**Simulation:** a broadcast sizing check against an 8 GB executor, using the 0.3x rule of thumb (safe limit = 2.4 GB).

```python
executor_memory_gb = 8
safe_fraction = 0.3
safe_limit_gb = executor_memory_gb * safe_fraction

candidates = [
    ("dim_customers", 0.05),
    ("dim_products", 2.5),
    ("fact_orders_filtered", 6.0),
]
for name, size_gb in candidates:
    verdict = "SAFE to broadcast" if size_gb <= safe_limit_gb else "RISK OF OOM -- do not force broadcast"
    print(f"    {name:<22} {size_gb:>5.2f} GB  -> {verdict}")
```

**Output:**

```text
    dim_customers          0.05 GB  -> SAFE to broadcast
    dim_products           2.50 GB  -> RISK OF OOM -- do not force broadcast
    fact_orders_filtered   6.00 GB  -> RISK OF OOM -- do not force broadcast
```

With an 8 GB executor and the 0.3x rule of thumb, the safe limit works out to `8 x 0.3 = 2.4` GB. `dim_customers` at 0.05 GB is comfortably under that and is safe to broadcast. `dim_products` at 2.5 GB actually exceeds the 2.4 GB limit (even though it looks "small" next to a multi-GB fact table), so it lands in the RISK OF OOM bucket too — a good illustration of why the rule of thumb should be applied literally rather than by gut feel. `fact_orders_filtered` at 6.0 GB is obviously unsafe.

---

## 3. What is Adaptive Query Execution (AQE)?

Adaptive Query Execution (`spark.sql.adaptive.enabled`, default TRUE since Spark 3.2) lets Spark re-optimize the physical plan MID-QUERY, using ACTUAL runtime statistics gathered after a shuffle — rather than relying solely on the static optimizer's pre-execution ESTIMATES (which come from table metadata, file sizes, and cardinality guesses that can be badly wrong, especially after several transformations).

AQE needs a SHUFFLE BOUNDARY to work: Spark can only re-optimize between STAGES, because a shuffle is a materialization point — Spark has already written the shuffle output to disk/memory and knows exactly how many rows and bytes resulted, for each partition. Before the first shuffle in a query, there's no new information yet, so the static plan is used as-is; AQE re-plans the REMAINING query using the real stats it just observed.

AQE performs three main runtime optimizations:

1. **Coalescing shuffle partitions** that turned out too small (avoids many-small-tasks overhead by merging them into fewer, larger ones).
2. **Switching a sort-merge join to a broadcast join** when actual post-shuffle stats show one side is small enough to broadcast.
3. **Optimizing skewed joins** by detecting an oversized partition and splitting it into multiple smaller tasks (see concept 08 for the manual salting equivalent of this).

```text
Static optimizer (pre-execution, estimates only):

    Query -> Catalyst analyzes -> Logical Plan -> Physical Plan
                                    (uses ESTIMATED stats: file size,
                                     table metadata, guesses through
                                     several chained transformations)
                                            |
                                            v
                                      Execute AS PLANNED
                                      (no matter how wrong the
                                       estimate turns out to be)

AQE (re-optimizes AFTER each shuffle, using REAL stats):

    Stage 1 (shuffle write) --> ACTUAL row counts/bytes now known
            |
            v
    AQE re-optimizes the plan for Stage 2+ using real stats:
      - is a "large" side actually small?  -> switch SMJ to BHJ
      - are partitions tiny?               -> coalesce them
      - is one partition huge?              -> split it (skew join)
            |
            v
    Stage 2 executes the UPDATED plan
```

```python
spark.conf.set("spark.sql.adaptive.enabled", "true")   # default true (3.2+)
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", 10 * 1024 * 1024)

# AQE's broadcast switch uses THIS threshold too -- if post-shuffle
# actual size of a side drops below it, AQE swaps in a broadcast join
# even though the static plan chose SortMergeJoin.
```

---

## 4. AQE optimization #1: coalescing shuffle partitions

`spark.sql.shuffle.partitions` defaults to 200 — a fixed number chosen statically. If your actual data after a shuffle is much smaller than what 200 partitions warrants (e.g. after a highly selective filter), you'd end up with 200 tiny tasks, each with high scheduling/overhead cost relative to the small amount of data they process.

AQE looks at the ACTUAL post-shuffle partition sizes and merges (coalesces) adjacent small partitions together, targeting a configurable size (`spark.sql.adaptive.advisoryPartitionSizeInBytes`, default 64MB), producing far fewer, better-sized tasks.

**Simulation:** coalescing 200 tiny (0.3MB) shuffle partitions toward a 64MB target.

```python
static_partition_count = 200
actual_partition_sizes_mb = [0.3] * static_partition_count  # tiny after filter
target_size_mb = 64

coalesced = []
running = 0.0
for size in actual_partition_sizes_mb:
    if running + size > target_size_mb:
        coalesced.append(running)
        running = size
    else:
        running += size
if running:
    coalesced.append(running)

print(f"    Static plan: {static_partition_count} shuffle partitions "
      f"({actual_partition_sizes_mb[0]}MB each -- way too small)")
print(f"    AQE coalesced into: {len(coalesced)} partitions "
      f"(~{target_size_mb}MB target each)")
```

**Output:**

```text
    Static plan: 200 shuffle partitions (0.3MB each -- way too small)
    AQE coalesced into: 1 partitions (~64MB target each)
```

All 200 partitions at 0.3MB each sum to only 60MB total, which never crosses the 64MB target threshold in the accumulation loop — so every partition gets folded into a single running total, and AQE ends up coalescing all 200 tiny partitions into just 1 output partition.

---

## 5. AQE optimizations #2 & #3: broadcast switch and skew split

This simulates the classic AQE story: the static optimizer only has ESTIMATES before execution, so it picks a SortMergeJoin (SMJ) believing both sides are large. After the shuffle actually runs, AQE observes the REAL post-shuffle row/byte counts and finds one side is actually small enough to broadcast — so it swaps the plan to a BroadcastHashJoin (BHJ) for the remaining stage.

```python
broadcast_threshold_mb = 10

# --- Static optimizer's pre-execution ESTIMATES (often wrong) ---
estimated_size_mb = {"orders_filtered": 850, "regions_after_filter": 450}
for name, size in estimated_size_mb.items():
    print(f"    Estimated size of {name}: {size} MB")
static_choice = "SortMergeJoin (SMJ)"
if all(size > broadcast_threshold_mb for size in estimated_size_mb.values()):
    print(f"    Both sides estimated > {broadcast_threshold_mb}MB threshold "
          f"-> static plan chooses: {static_choice}")

# --- What actually happens after the shuffle runs ---
# The estimate for regions_after_filter was way off: an upstream filter
# (e.g. WHERE region = 'EU') that the static optimizer couldn't size
# accurately actually shrank it to a few MB.
actual_size_mb = {"orders_filtered": 850, "regions_after_filter": 6}
for name, size in actual_size_mb.items():
    print(f"    Actual post-shuffle size of {name}: {size} MB")

small_side = min(actual_size_mb, key=actual_size_mb.get)
if actual_size_mb[small_side] <= broadcast_threshold_mb:
    print(f"    '{small_side}' actual size ({actual_size_mb[small_side]}MB) "
          f"<= threshold ({broadcast_threshold_mb}MB)")
    print(f"    -> AQE RE-OPTIMIZES remaining stage: "
          f"SortMergeJoin REPLACED with BroadcastHashJoin (BHJ)")
else:
    print("    -> No side small enough; static SMJ plan is kept")
```

**Output:**

```text
  (a) Estimated size of orders_filtered: 850 MB
      Estimated size of regions_after_filter: 450 MB
      Both sides estimated > 10MB threshold -> static plan chooses: SortMergeJoin (SMJ)
  (b) Actual post-shuffle size of orders_filtered: 850 MB
      Actual post-shuffle size of regions_after_filter: 6 MB
      'regions_after_filter' actual size (6MB) <= threshold (10MB)
      -> AQE RE-OPTIMIZES remaining stage: SortMergeJoin REPLACED with BroadcastHashJoin (BHJ)
```

Why the estimate was wrong: the static optimizer estimates `regions_after_filter`'s size from table metadata BEFORE the filter executes. Filters with unpredictable selectivity (data-dependent predicates, UDFs, multi-stage transformations) routinely fool static estimates. AQE doesn't guess — it measures the real shuffle output.

AQE's third optimization, dynamically optimizing skewed joins, detects (after the shuffle) that one partition's size is far above the median (default threshold: `skewedPartitionFactor=5`, i.e. >5x the median AND above `skewedPartitionThresholdInBytes`, default 256MB) and automatically splits that oversized partition into several smaller sub-partitions, each joined separately against a duplicated copy of the corresponding other-side partition — conceptually the same outcome as the manual salting technique from concept 08, but performed by Spark automatically with no code change required.

```text
spark.sql.adaptive.skewJoin.enabled = true (default)
spark.sql.adaptive.skewJoin.skewedPartitionFactor = 5      (5x median size)
spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes = 256MB

If partition_size > median_size * factor AND partition_size > threshold:
    split it into N smaller sub-partitions and join each piece
    separately (see concept 08 for the manual version of this idea)
```

---

## Key Takeaways

- A broadcast join copies the small side whole to every executor, eliminating the need to shuffle the large side entirely.
- `autoBroadcastJoinThreshold` (default 10MB) controls auto-broadcast; `F.broadcast(df)` forces it and OVERRIDES the safety check — size carefully, or risk driver/executor OOM.
- AQE (on by default since Spark 3.2) re-optimizes the plan mid-query using ACTUAL post-shuffle statistics instead of pre-execution estimates — and it can only do this at a shuffle boundary, since that's the first point real stats exist.
- AQE coalesces shuffle partitions that turned out too small, saving task-scheduling overhead from over-partitioning.
- AQE can swap a SortMergeJoin for a BroadcastHashJoin mid-query when actual (not estimated) stats show one side is small enough.
- AQE can split a skewed partition into smaller pieces automatically — achieving, without code changes, what manual salting does by hand.
- Static estimates are frequently wrong after filters, joins, or UDFs with unpredictable selectivity — this is exactly the gap AQE closes.
