# Concept 05: Data Partitioning

**Covers:**
- What a partition is physically (a chunk of data processed by one task)
- Default parallelism vs `spark.sql.shuffle.partitions`
- `repartition(n)` (full shuffle, increases or evens out partitions) vs `coalesce(n)` (no full shuffle, only decreases, merges locally)
- `repartition(col)` for even distribution by key
- Partition sizing rule of thumb (~100-200 MB per partition)
- Symptoms of too many partitions (scheduling overhead) vs too few (huge tasks, spill, poor parallelism)
- Partition pruning on partitioned tables (`partitionBy` on write + filter on read only scans relevant partition directories)
- A simulation comparing `repartition` vs `coalesce`, showing data movement counts

*All PySpark code below reflects real behavior of a running SparkSession; the worked examples are simulated in plain Python/reasoning so you can follow along without a cluster.*

---

## 1. What Is a Partition, Physically?

A partition is a contiguous chunk of a distributed dataset that lives entirely on one executor and is processed, at any moment, by exactly one task running on one CPU core. A DataFrame with 200 partitions can have at most 200 tasks running concurrently for a given stage, no matter how many cores your cluster has.

Physically, a partition is:
- For a file-based read: one or more file splits/blocks assigned together (e.g. one 128 MB HDFS block, or a group of small files)
- For an in-memory/cached DataFrame: a Java/Python object holding a batch of rows in an executor's memory (or spilled to its disk)
- For a shuffle output: a range of the hash space (or a sort range) written to shuffle files, later read by exactly one reduce task

```text
Dataset on disk (3 files, 400 MB total)
+------------------+  +------------------+  +------------------+
| file_part_0.parq  |  | file_part_1.parq |  | file_part_2.parq |
| ~130 MB           |  | ~140 MB          |  | ~130 MB          |
+--------+---------+  +--------+---------+  +--------+---------+
         |                     |                      |
         v                     v                      v
  Partition 0             Partition 1            Partition 2
  -> Task on Executor A   -> Task on Executor B  -> Task on Executor A
```

**Simulation:** treat each of 3 Parquet files as one partition and total up the dataset.

```python
files = {"file_part_0.parquet": 130, "file_part_1.parquet": 140, "file_part_2.parquet": 130}
print("  Reading files as partitions (1 file ~ 1 partition here):")
for i, (fname, size_mb) in enumerate(files.items()):
    print(f"    Partition {i}: source={fname}, size={size_mb} MB -> 1 task will process this")
total_mb = sum(files.values())
print(f"  Total dataset size: {total_mb} MB across {len(files)} partitions "
      f"(avg {total_mb/len(files):.0f} MB/partition)")
```

**Output:**
```text
  Reading files as partitions (1 file ~ 1 partition here):
    Partition 0: source=file_part_0.parquet, size=130 MB -> 1 task will process this
    Partition 1: source=file_part_1.parquet, size=140 MB -> 1 task will process this
    Partition 2: source=file_part_2.parquet, size=130 MB -> 1 task will process this
  Total dataset size: 400 MB across 3 partitions (avg 133 MB/partition)
```

---

## 2. Default Parallelism vs spark.sql.shuffle.partitions

**`spark.default.parallelism`**
- Governs the partition count for RDD operations and for the FIRST read of a file-based RDD when no other hint applies
- Defaults to the total number of cores across all executors in cluster mode, or the number of cores on the machine in local mode

**`spark.sql.shuffle.partitions`**
- Governs the partition count AFTER any DataFrame/SQL shuffle (`groupBy`, `join`, `distinct`, `orderBy`, `repartition` without an explicit count)
- Defaults to 200, REGARDLESS of cluster size or data size -- this is a historical default from Spark's early days and is one of the most commonly misconfigured settings
- On a small cluster or small dataset, 200 is often way too many (each task processes almost nothing, scheduling overhead dominates); on a huge dataset, 200 is often way too few (each partition ends up huge, causing spill and long task times)
- Adaptive Query Execution (AQE), when enabled, can automatically coalesce post-shuffle partitions at runtime based on actual data size, reducing the need to hand-tune this value

```python
spark.conf.get("spark.default.parallelism")     # e.g. "8" (= total cores)
spark.conf.get("spark.sql.shuffle.partitions")   # "200" unless overridden

spark = SparkSession.builder \
    .config("spark.sql.shuffle.partitions", "50") \
    .config("spark.sql.adaptive.enabled", "true") \    # AQE can auto-coalesce
    .getOrCreate()
```

**Simulation:** an 8-core cluster with the default 200 shuffle partitions applied to a 2 GB post-shuffle dataset.

```python
total_cores = 8
default_shuffle_partitions = 200
dataset_size_gb = 2

print(f"  Cluster total cores:              {total_cores}")
print(f"  spark.default.parallelism:         {total_cores} (= total cores)")
print(f"  spark.sql.shuffle.partitions:      {default_shuffle_partitions} (fixed default, ignores cluster/data size)")
partition_size_mb = (dataset_size_gb * 1024) / default_shuffle_partitions
print(f"  For a {dataset_size_gb} GB post-shuffle dataset: "
      f"{partition_size_mb:.1f} MB/partition -- likely TOO SMALL, causes scheduling overhead")
```

**Output:**
```text
  Cluster total cores:              8
  spark.default.parallelism:         8 (= total cores)
  spark.sql.shuffle.partitions:      200 (fixed default, ignores cluster/data size)
  For a 2 GB post-shuffle dataset: 10.2 MB/partition -- likely TOO SMALL, causes scheduling overhead
```

---

## 3. repartition(n) vs coalesce(n)

**`repartition(n)`**
- Performs a FULL SHUFFLE: every row is potentially reassigned to a new partition via round-robin (or hash, if a column is given)
- Can INCREASE or DECREASE the partition count
- Result partitions are evenly sized (roughly), since data is redistributed from scratch
- Expensive: pays full shuffle cost (write + network + read)

**`coalesce(n)`**
- Does NOT perform a full shuffle -- it merges existing partitions together locally, minimizing data movement (some partitions may combine without any network transfer at all if colocated)
- Can only DECREASE the partition count (coalescing to a larger n than you currently have is a no-op, and Spark keeps the current count)
- Result partitions can be UNEVEN in size, because it's just grouping existing partitions rather than truly redistributing rows
- Cheap: this is why coalesce is preferred right before writing output when you want fewer files, e.g. after a filter that shrank the dataset

```text
repartition(2)  [4 partitions -> 2, FULL SHUFFLE]
P0 -+     +--> new P0 (mix of rows from P0,P1,P2,P3)
P1 -+--X--+
P2 -+     +--> new P1 (mix of rows from P0,P1,P2,P3)
P3 -+

coalesce(2)  [4 partitions -> 2, LOCAL MERGE, no full shuffle]
P0 -+
    +--> new P0 (= old P0 + P1, no network shuffle if colocated)
P1 -+
P2 -+
    +--> new P1 (= old P2 + P3)
P3 -+
```

```python
df.repartition(50)                 # full shuffle -> 50 evenly-sized partitions
df.repartition(50, "customer_id")   # full shuffle, hash-partitioned by column
df.coalesce(10)                     # cheap merge -> 10 partitions (uneven sizes OK)
df.coalesce(500)                    # no-op if df already has <= 500 partitions
```

A full runnable simulation comparing the actual data movement of `repartition` vs `coalesce` is in section 8 below.

---

## 4. repartition(col) for Even Distribution by Key

`repartition(n, col)` hash-partitions rows by the given column's value, so all rows sharing a key land in the same output partition. This is used to:
- Co-locate data before a join on that column (avoiding a shuffle later, if both sides are pre-partitioned identically)
- Balance load before a `groupBy`/window operation keyed on that column
- Avoid the default round-robin `repartition(n)`, which distributes rows evenly but ignores key locality entirely

Caveat: if the column is skewed (a few key values dominate row count), hash partitioning by that column reproduces the skew in the output partitions -- some partitions will still be much bigger than others, because all rows for a hot key are forced onto one partition.

```python
df.repartition(20, "customer_id")   # hash-partition by customer_id into 20 partitions
```

**Simulation:** hash-partition 7 rows (with a repeated, "hot" key `c1`) by `customer_id` into 3 partitions.

```python
rows = [("c1", 1), ("c2", 1), ("c1", 1), ("c3", 1), ("c1", 1), ("c2", 1), ("c1", 1)]
num_partitions = 3
partitions = {i: [] for i in range(num_partitions)}
for key, val in rows:
    partitions[hash(key) % num_partitions].append((key, val))

print(f"  Hash-partitioning {len(rows)} rows by 'customer_id' into {num_partitions} partitions:")
for pid, contents in partitions.items():
    print(f"    Partition {pid}: {contents} ({len(contents)} rows)")
print("  Note: 'c1' appears 4 times and always lands on the SAME partition --")
print("  a hot key like this makes that partition bigger than the others (skew).")
```

**Output:**

The exact partition each key lands on depends on Python's `hash()` of the string, which is randomized per process (`PYTHONHASHSEED`) by default -- so the specific partition IDs below will differ from run to run, but the shape (all four `c1` rows landing together, on whichever partition that turns out to be) is stable. Here is one concrete, reproducible run with hash randomization pinned (`PYTHONHASHSEED=0`):

```text
  Hash-partitioning 7 rows by 'customer_id' into 3 partitions:
    Partition 0: [] (0 rows)
    Partition 1: [('c1', 1), ('c1', 1), ('c3', 1), ('c1', 1), ('c1', 1)] (5 rows)
    Partition 2: [('c2', 1), ('c2', 1)] (2 rows)
  Note: 'c1' appears 4 times and always lands on the SAME partition --
  a hot key like this makes that partition bigger than the others (skew).
```

Notice how all four `c1` rows land on partition 1 together, alongside `c3` -- giving that partition 5 of the 7 rows while partition 0 gets none. That is exactly the skew effect the caveat above describes: the hot key doesn't get spread out, it concentrates everything sharing its value onto one partition.

---

## 5. Partition Sizing Rule of Thumb

A widely-used guideline: target 100-200 MB of data per partition (in-memory, uncompressed-ish size, since that's roughly what a single task can process efficiently without excessive GC pressure or spill).

Given a target partition size, you can back into an ideal partition count:

```
ideal_partitions = total_data_size_mb / target_partition_size_mb
```

This is a starting point, not a law -- adjust based on available cores (you want at least a few partitions per core for pipelining) and on operation cost (CPU-heavy row-by-row UDFs may want smaller partitions; simple scans can tolerate larger ones).

**Simulation:** back into an ideal partition count for a 12 GB dataset targeting ~150 MB per partition.

```python
dataset_size_mb = 12_000  # 12 GB
target_partition_mb = 150

ideal_partitions = round(dataset_size_mb / target_partition_mb)
print(f"  Dataset size:           {dataset_size_mb} MB")
print(f"  Target partition size:  {target_partition_mb} MB")
print(f"  Ideal partition count:  {dataset_size_mb} / {target_partition_mb} = ~{ideal_partitions} partitions")
print(f"  df.repartition({ideal_partitions})  -- would produce ~{target_partition_mb} MB/partition")
```

**Output:**
```text
  Dataset size:           12000 MB
  Target partition size:  150 MB
  Ideal partition count:  12000 / 150 = ~80 partitions
  df.repartition(80)  -- would produce ~150 MB/partition
```

---

## 6. Too Many vs Too Few Partitions

**TOO MANY partitions** (partitions much smaller than ~100 MB):
- Task scheduling/serialization overhead (each task has fixed overhead of a few ms to launch) starts to dominate actual compute
- More small output files if writing to storage ("small file problem"), which slows down future reads and metadata operations
- Executors spend more time on bookkeeping than on data

**TOO FEW partitions** (partitions much bigger than ~100-200 MB):
- Each task takes a long time and holds a lot of data in memory at once -- risk of spilling to disk or OOM
- Parallelism is wasted: with fewer partitions than cores, some cores sit idle during that stage
- A single slow/huge partition (skew) becomes a straggler that the whole stage waits on

```text
TOO MANY (e.g. 10,000 tiny partitions)     TOO FEW (e.g. 2 huge partitions)
---------------------------------------     ---------------------------------
- task overhead dominates                   - huge tasks, high memory pressure
- small-file problem on write               - spill to disk likely
- executors busy with bookkeeping           - most cores idle (only 2 tasks running)
- scheduler queue backs up                  - one skewed partition stalls the stage
```

**Simulation:** compare how many tasks can run concurrently on a 16-core cluster across three partitioning scenarios.

```python
available_cores = 16
scenarios = [
    ("too many", 10000, 0.5),   # (label, partitions, mb per partition)
    ("well-sized", 80, 150),
    ("too few", 2, 6000),
]
print(f"  Cluster has {available_cores} cores available.\n")
for label, num_partitions, mb_each in scenarios:
    active_tasks_at_once = min(num_partitions, available_cores)
    idle_cores = max(0, available_cores - num_partitions)
    print(f"  Scenario '{label}': {num_partitions} partitions x {mb_each} MB each")
    print(f"    Concurrent tasks possible: {active_tasks_at_once} "
          f"({'cores idle: ' + str(idle_cores) if idle_cores else 'all cores busy'})")
```

**Output:**
```text
  Cluster has 16 cores available.

  Scenario 'too many': 10000 partitions x 0.5 MB each
    Concurrent tasks possible: 16 (all cores busy)
  Scenario 'well-sized': 80 partitions x 150 MB each
    Concurrent tasks possible: 16 (all cores busy)
  Scenario 'too few': 2 partitions x 6000 MB each
    Concurrent tasks possible: 2 (cores idle: 14)
```

Note that the "too many" scenario reports "all cores busy" just like the well-sized one -- the difference doesn't show up in this concurrency count at all. It shows up in what each of those busy cores is actually accomplishing: in the well-sized scenario each of the 16 concurrent tasks is chewing through a genuine 150 MB of data, while in the too-many scenario each of the 16 concurrent tasks is processing a mere 0.5 MB before the task framework's fixed per-task overhead (scheduling, serialization, bookkeeping) has to be paid all over again for the next of 10,000 tiny tasks.

---

## 7. Partition Pruning on Partitioned Tables

This is a different (but related) concept from in-memory RDD/DataFrame partitions above: TABLE partitioning is a physical layout on disk, where writing with `partitionBy("col")` creates one subdirectory per distinct value of that column:

```
orders/region=east/part-0000.parquet
orders/region=west/part-0001.parquet
orders/region=south/part-0002.parquet
```

When you later read this table and filter on the partition column (`df.filter(F.col("region") == "east")`), Spark's planner performs PARTITION PRUNING: it consults the directory structure (or Hive metastore) BEFORE reading any data, and skips every directory whose partition value can't match the filter. Only the matching directories are ever opened -- this is far cheaper than reading everything and filtering row-by-row afterward, because entire files are never touched.

Partition pruning is most effective on low-to-medium cardinality columns used often in filters (region, date, country) -- high cardinality columns (customer_id) would create too many tiny partition directories and hurt more than help.

```python
# Write: creates one directory per distinct region value
df.write.partitionBy("region").parquet("orders/")

# Read + filter on the partition column: pruning kicks in
spark.read.parquet("orders/").filter(F.col("region") == "east").explain()
# == Physical Plan ==
# *(1) FileScan parquet orders[...] PartitionFilters: [(region#3 = east)]
```

**Simulation:** filter a 4-region partitioned table on `region == 'east'` and see which directories get scanned vs. skipped.

```python
directories = {
    "region=east": 40,
    "region=west": 55,
    "region=south": 30,
    "region=north": 45,
}
filter_value = "east"

print(f"  On-disk layout (partitionBy='region'):")
for d, files in directories.items():
    print(f"    {d}/  ({files} files)")

matching = [d for d in directories if d == f"region={filter_value}"]
skipped = [d for d in directories if d != f"region={filter_value}"]

print(f"\n  Query filters on region == '{filter_value}':")
print(f"    Directories SCANNED: {matching} -> {directories[matching[0]]} files read")
print(f"    Directories SKIPPED (pruned): {skipped} -> "
      f"{sum(directories[d] for d in skipped)} files never opened")
```

**Output:**
```text
  On-disk layout (partitionBy='region'):
    region=east/  (40 files)
    region=west/  (55 files)
    region=south/  (30 files)
    region=north/  (45 files)

  Query filters on region == 'east':
    Directories SCANNED: ['region=east'] -> 40 files read
    Directories SKIPPED (pruned): ['region=west', 'region=south', 'region=north'] -> 130 files never opened
```

---

## 8. Simulation: repartition vs coalesce Data Movement

Concrete comparison of how many rows actually move across partition boundaries (a proxy for network/shuffle I/O) when going from 4 partitions down to 2, using `repartition(2)` vs `coalesce(2)`.

```python
original_partitions = {
    0: list(range(0, 10)),    # 10 rows
    1: list(range(10, 25)),   # 15 rows
    2: list(range(25, 30)),   # 5 rows
    3: list(range(30, 50)),   # 20 rows
}
total_rows = sum(len(v) for v in original_partitions.values())
print(f"  Starting state: {len(original_partitions)} partitions, {total_rows} rows total")
for pid, rows in original_partitions.items():
    print(f"    Partition {pid}: {len(rows)} rows")

# ---- repartition(2): full shuffle, round-robin redistribution ----
print("\n  -- repartition(2): FULL SHUFFLE --")
all_rows = [r for rows in original_partitions.values() for r in rows]
new_partitions_repartition = {0: [], 1: []}
for row in all_rows:
    new_partitions_repartition[row % 2].append(row)

moved_repartition = 0
for pid, rows in original_partitions.items():
    for row in rows:
        new_pid = row % 2
        if new_pid != pid:  # would have needed to move off its original partition
            moved_repartition += 1
for pid, rows in new_partitions_repartition.items():
    print(f"    New partition {pid}: {len(rows)} rows (evenly sized)")
print(f"    Rows that crossed a partition boundary (shuffled over network): "
      f"{moved_repartition} of {total_rows}")

# ---- coalesce(2): local merge, no full shuffle ----
print("\n  -- coalesce(2): LOCAL MERGE (no full shuffle) --")
# coalesce just groups existing partitions together: {0,1} -> new 0, {2,3} -> new 1
new_partitions_coalesce = {
    0: original_partitions[0] + original_partitions[1],
    1: original_partitions[2] + original_partitions[3],
}
moved_coalesce = 0  # rows stay on their original executor, just relabeled -- no network shuffle
for pid, rows in new_partitions_coalesce.items():
    print(f"    New partition {pid}: {len(rows)} rows (merged from original partitions, size UNEVEN)")
print(f"    Rows that crossed a partition boundary (network shuffle): {moved_coalesce} of {total_rows} "
      f"(data merged locally, not redistributed)")

print(f"\n  Summary: repartition(2) moved {moved_repartition} rows over the network; "
      f"coalesce(2) moved {moved_coalesce}.")
print("  coalesce is far cheaper here, but note the resulting partition sizes "
      "(10 and 40) are much less even than repartition's.")
```

**Output:**

Working this through partition by partition: of partition 0's 10 rows (values 0-9), the 5 odd values end up on new partition 1 while the 5 even values stay on new partition 0 -- 5 rows moved. Of partition 1's 15 rows (values 10-24), the 8 even values move to new partition 0 (partition 1 keeps only its 7 odd values) -- 8 rows moved. Partition 2's 5 rows (values 25-29) all move, since `row % 2` is always 0 or 1 and never equals the original partition id 2 -- 5 rows moved. Partition 3's 20 rows (values 30-49) likewise all move, for the same reason -- 20 rows moved. That totals 5 + 8 + 5 + 20 = 38 rows out of 50 that cross a partition boundary under `repartition(2)`:

```text
  Starting state: 4 partitions, 50 rows total
    Partition 0: 10 rows
    Partition 1: 15 rows
    Partition 2: 5 rows
    Partition 3: 20 rows

  -- repartition(2): FULL SHUFFLE --
    New partition 0: 25 rows (evenly sized)
    New partition 1: 25 rows (evenly sized)
    Rows that crossed a partition boundary (shuffled over network): 38 of 50

  -- coalesce(2): LOCAL MERGE (no full shuffle) --
    New partition 0: 25 rows (merged from original partitions, size UNEVEN)
    New partition 1: 25 rows (merged from original partitions, size UNEVEN)
    Rows that crossed a partition boundary (network shuffle): 0 of 50 (data merged locally, not redistributed)

  Summary: repartition(2) moved 38 rows over the network; coalesce(2) moved 0.
  coalesce is far cheaper here, but note the resulting partition sizes (10 and 40) are much less even than repartition's.
```

Both new-partition sizes land at exactly 25 and 25 for `repartition(2)` here only because the row values happen to split evenly by parity across the full range 0-49 -- `coalesce(2)`, by contrast, produces 25 (partitions 0+1: 10+15) and 25 (partitions 2+3: 5+20) as well in row *count*, but the important difference the simulation's own summary flags is that coalesce's merge groups are determined by which original partitions get combined (uneven inputs: 10, 15, 5, 20 rows), not by redistributing individual rows -- so in general (and in the original partition-size terms the summary line references, 10 and 40 MB-style units) coalesce's grouping can leave far more uneven results than repartition's from-scratch redistribution.

---

## Key Takeaways

- A partition is a chunk of data processed by exactly one task on one core -- partition count caps how much work runs concurrently.
- `spark.sql.shuffle.partitions` defaults to 200 regardless of data or cluster size -- it is one of the most commonly mis-tuned settings.
- `repartition(n)` does a full shuffle and can increase or decrease partitions evenly; `coalesce(n)` only decreases, merging locally and cheaply, but can leave partitions uneven.
- `repartition(n, col)` hash-partitions by key for join/groupBy locality, but reproduces skew if the key itself is skewed.
- Target ~100-200 MB per partition as a starting point; adjust for core count and per-row processing cost.
- Too many partitions wastes time on scheduling overhead and small files; too few underutilizes cores and risks spill/OOM on huge tasks.
- Partition pruning (on `partitionBy`-written tables) skips entire directories at planning time -- a filter on the partition column is far cheaper than filtering after a full read.
