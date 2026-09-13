# Concept 13: Shuffle Partitions

**Covers:**
- What a shuffle physically does (map-side write, reduce-side all-to-all fetch)
- spark.sql.shuffle.partitions (default 200) and why that default is often wrong
- How AQE's coalescePartitions fixes it dynamically at runtime
- A manual rule of thumb for sizing shuffle partitions (target ~100-200MB/partition)
- Shuffle spill (memory vs disk) and where to see it in the Spark UI
- spark.sql.shuffle.partitions vs spark.default.parallelism

*All PySpark configuration and query plans below are real and educational; the sizing/coalescing simulations are computed in plain Python so you can trace the numbers without a live cluster.*

---

## 1. What a Shuffle Physically Does

A shuffle is triggered by a "wide" transformation (`groupBy`, `join`, `distinct`, `repartition`, `orderBy`, etc.) — any operation where an output partition needs data that could come from ANY input partition, not just one.

Physically, a shuffle happens in two halves:

**MAP SIDE (shuffle write):**
- Each map task reads its input partition and, for every output record, computes which of the N reduce-side partitions it belongs to (by hashing the shuffle key, by default — `HashPartitioner` — or by range for range partitioning).
- It writes those records to local disk, organized into per-reduce-partition shuffle files (Spark's sort-based shuffle writer sorts and writes one file + an index file per map task, indexed by partition).
- This is "shuffle write" — visible in the Spark UI as bytes written.

**REDUCE SIDE (shuffle read):**
- Each reduce task is responsible for ONE output partition.
- It must fetch the relevant slice of EVERY map task's shuffle file — an "all-to-all" data movement across the network (or local disk read, if map and reduce tasks happen to share a node).
- With M map tasks and R reduce tasks, this is up to M*R individual network/disk fetches in the worst case.
- This is "shuffle read" — visible in the Spark UI as bytes read.

This is why shuffles are expensive: they involve disk I/O (writing AND reading shuffle files) plus network I/O (fetching across executors), unlike narrow transformations which stay in memory within a partition.

```text
MAP SIDE (M map tasks)              REDUCE SIDE (R reduce tasks)

Map Task 0 --> writes shuffle       Reduce Task 0 <-- fetches its slice
  partitioned into R files             from ALL M map tasks' output
Map Task 1 --> writes shuffle       Reduce Task 1 <-- fetches its slice
  partitioned into R files             from ALL M map tasks' output
Map Task 2 --> writes shuffle       Reduce Task 2 <-- fetches its slice
  partitioned into R files             from ALL M map tasks' output
     ...                                    ...

Every map task's output is split R ways (by hash of the shuffle key).
Every reduce task pulls its 1/R slice from EVERY map task.
-> up to M x R network/disk fetches -- "all-to-all" shuffle.

+--------+     +--------+     +--------+
| Map 0  |--+--| Map 1  |--+--| Map 2  |     (shuffle WRITE: to local disk,
+--------+  |  +--------+  |  +--------+      partitioned by reduce key)
     \      |      |       |      /
      \     |      |       |     /
       v    v      v       v    v
     +-----------------------------+
     | Reduce 0 | Reduce 1 | ...   |          (shuffle READ: fetch across
     +-----------------------------+           network from every map task)
```

```python
df.groupBy("region").sum("amount")   # triggers a shuffle -- default 200
                                      # reduce-side partitions unless
                                      # spark.sql.shuffle.partitions is set
                                      # or AQE coalesces them
```

---

## 2. spark.sql.shuffle.partitions — The Default 200

`spark.sql.shuffle.partitions` controls how many reduce-side partitions (R, above) a shuffle produces for DataFrame/SQL operations. Default: 200.

Where does 200 come from? It's a historical default dating back to early Spark SQL, tuned for small/medium clusters of that era. It is a STATIC, FIXED number — Spark does NOT look at your actual data size and choose a sensible R automatically (pre-AQE). It applies the same 200 whether your shuffle involves 10MB or 10TB of data.

Why 200 is often wrong:
- **Too many for a SMALL job:** if you're shuffling only 500MB, splitting it into 200 partitions means ~2.5MB per partition. Task scheduling overhead (launching a task, serialization, JVM bookkeeping — roughly milliseconds to low tens of ms per task) starts to dominate over the tiny amount of actual work each task does. You pay more in overhead than in useful computation.
- **Too few for a BIG job:** if you're shuffling 2TB, 200 partitions means ~10GB per partition. That's far larger than a single task's execution memory can typically hold, forcing heavy spill to disk (see section 5), very slow individual tasks, GC pressure, and possible OOM.

This is why "just leave it at 200" is a common performance bug: it's right for roughly ONE data size and wrong for everything else.

```python
spark.conf.get("spark.sql.shuffle.partitions")  # "200" by default

# Small job (500MB shuffle) with 200 partitions:
#   500MB / 200 = 2.5MB/partition  -> way too small, overhead-dominated

# Big job (2TB shuffle) with 200 partitions:
#   2TB / 200 = 10GB/partition     -> way too big, spills to disk, slow tasks
```

---

## 3. How AQE's coalescePartitions Fixes This Dynamically

Adaptive Query Execution (AQE), enabled by default since Spark 3.2 (`spark.sql.adaptive.enabled=true`), re-optimizes the physical plan at RUNTIME using actual statistics from completed shuffle map stages — something the static, pre-execution optimizer can't do.

`spark.sql.adaptive.coalescePartitions.enabled = true` (default when AQE is on)

Mechanism:
1. Spark still initially targets `spark.sql.shuffle.partitions` (e.g. 200) reduce-side partitions when planning the shuffle.
2. After the map side of the shuffle finishes, Spark KNOWS the actual size of each of those 200 (potentially tiny) partitions, because map tasks report bytes written per partition.
3. The AQE coalesce rule then MERGES adjacent small partitions together so that each final reduce task processes a partition close to a target size (`spark.sql.adaptive.advisoryPartitionSizeInBytes`, default 64MB, though the effective target is also influenced by `coalescePartitions.minPartitionSize`).
4. The result: a query that would have run 200 tiny tasks instead runs, say, 8 right-sized tasks — decided AFTER seeing the real data, not guessed beforehand.

This does NOT help the "too few partitions for a huge job" direction by itself — coalescing only merges partitions DOWN, it doesn't split an oversized partition into smaller ones. (Skew-specific splitting is a separate AQE feature: `spark.sql.adaptive.skewJoin.enabled`.)

```python
spark.conf.set("spark.sql.adaptive.enabled", "true")                        # default in 3.2+
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")     # default when AQE on
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "64m")    # target size per partition
```

**Simulation:**

Simulating AQE coalescing a small shuffle: 480MB spread evenly across 200 initial partitions (~2.4MB each), merged up toward a 64MB target.

```python
initial_partitions = 200
total_mb = 480
sizes = [total_mb / initial_partitions] * initial_partitions  # ~2.4MB each

target_size_mb = 64
coalesced = []
current = 0.0
for s in sizes:
    if current + s > target_size_mb and current > 0:
        coalesced.append(current)
        current = s
    else:
        current += s
if current > 0:
    coalesced.append(current)

print(f"    Before AQE coalesce: {initial_partitions} partitions, "
      f"~{total_mb/initial_partitions:.2f}MB each")
print(f"    After AQE coalesce:  {len(coalesced)} partitions, "
      f"sizes ~{min(coalesced):.1f}-{max(coalesced):.1f}MB (target {target_size_mb}MB)")
```

**Output:**
```text
    Before AQE coalesce: 200 partitions, ~2.40MB each
    After AQE coalesce:  8 partitions, sizes ~43.2-62.4MB (target 64MB)
```

(Tracing it out: each group accumulates 2.4MB partitions until adding one more would exceed 64MB — that happens after 26 partitions, at 62.4MB, so seven groups land at exactly 62.4MB. The 200 partitions don't divide evenly by 26, so the last group is a remainder of 18 partitions, totaling 43.2MB — giving 8 groups ranging from 43.2MB to 62.4MB, both comfortably under the 64MB advisory target.)

---

## 4. Manual Rule of Thumb for Sizing Shuffle Partitions

When AQE isn't available (older Spark, or coalescing disabled), or when you want to set a sane baseline anyway, use this rule of thumb:

```text
shuffle_partitions = total_shuffle_data_size / target_partition_size
```

Target partition size: ~100-200MB is the commonly recommended sweet spot.
- Large enough that per-task overhead (scheduling, serialization) is a small fraction of total task time.
- Small enough to fit comfortably in a task's share of execution memory without spilling, and to give good parallelism across the cluster (many tasks means better load balancing across executors).

Also sanity-check against your cluster's total core count: you want AT LEAST enough partitions that all cores can be busy simultaneously (ideally 2-4x total cores, so that if a few tasks run long, others can fill the gap — this is separate from the byte-size target above and both should be considered together).

```python
shuffle_partitions = total_shuffle_data_size_MB / target_partition_size_MB

# Also check: shuffle_partitions >= 2-4 * total_cluster_cores
# (so all cores stay busy; avoids a handful of huge tasks bottlenecking
#  while most executors sit idle)
```

---

## 5. Shuffle Spill

Shuffle spill happens when a task's shuffle data (being sorted/aggregated in memory, either on the map or reduce side) doesn't fit in the execution memory available to that task. Spark spills the in-memory data to local disk in sorted runs, then merges them later — correctness is preserved, but at a real performance cost (extra disk I/O, extra serialization).

Controlled by `spark.shuffle.spill` (effectively always enabled in modern Spark — there's no safe way to disable spilling without risking OOM; the relevant tuning lever is really the size of execution memory available per task, and the partition sizes feeding into it).

Visible in the Spark UI (Stages → stage detail → Summary Metrics, and per-task metrics) as two SEPARATE columns:
- **"Shuffle Spill (Memory)"**: size of the data BEFORE it was spilled (i.e. how much memory it would have taken uncompressed/unspilled).
- **"Shuffle Spill (Disk)"**: size actually written to disk (usually smaller, since spilled data is compressed).

A large ratio of spill to shuffle read/write size is a strong signal that partitions are too large for the available execution memory — the fix is usually to INCREASE `spark.sql.shuffle.partitions` (smaller partitions) or increase executor-memory, not to disable spilling (which isn't really a supported option).

```text
Spark UI -> Stages -> (a stage) -> Summary Metrics for Completed Tasks:
+------------------------+-----------+-----------+-----------+
| Metric                 | Min       | Median    | Max       |
+------------------------+-----------+-----------+-----------+
| Shuffle Spill (Memory) | 0.0 B     | 1200.0 MB | 4100.0 MB |
| Shuffle Spill (Disk)   | 0.0 B     | 340.0 MB  | 980.0 MB  |
+------------------------+-----------+-----------+-----------+
Large spill on the "Max" task (4.1GB in-memory / 980MB on disk) versus a
much smaller median suggests skew AND undersized partitions combined.
```

**Simulation:**

A task is simulated as spilling only the amount of data that overflows its available execution memory, with disk usage estimated at a compressed ~35% of the overflow.

```python
def simulate_task(data_mb, available_memory_mb):
    if data_mb <= available_memory_mb:
        return {"spilled": False, "spill_memory_mb": 0, "spill_disk_mb": 0}
    overflow = data_mb - available_memory_mb
    spill_disk_mb = overflow * 0.35  # compressed on disk, illustrative ratio
    return {"spilled": True, "spill_memory_mb": overflow, "spill_disk_mb": round(spill_disk_mb, 1)}

# --- Simulating spill for two partition sizes, 300MB execution memory/task ---
for partition_mb in [150, 900]:
    result = simulate_task(partition_mb, available_memory_mb=300)
    print(f"    Partition size {partition_mb}MB -> {result}")
```

**Output:**
```text
    Partition size 150MB -> {'spilled': False, 'spill_memory_mb': 0, 'spill_disk_mb': 0}
    Partition size 900MB -> {'spilled': True, 'spill_memory_mb': 600, 'spill_disk_mb': 210.0}
```

---

## 6. spark.sql.shuffle.partitions vs spark.default.parallelism

Two similarly-named but DIFFERENT configs, for two different APIs:

**`spark.sql.shuffle.partitions` (default 200)**
- Governs the number of partitions after a shuffle in the DataFrame / Dataset / Spark SQL API.
- This is the one that matters for almost all modern Spark code.

**`spark.default.parallelism`**
- Governs the default number of partitions for RDD API operations (e.g. `sc.parallelize`, and RDD wide transformations like `reduceByKey` when no explicit partition count is given).
- Default value: for cluster managers, it's the total number of cores across all executors (or 2 if running locally without a cluster manager reporting cores) — NOT 200.
- Rarely relevant unless you're writing raw RDD code; DataFrame/SQL code ignores this setting entirely for its own shuffles.

Common mistake: tuning `spark.default.parallelism` and being confused when a DataFrame-based job's shuffle partition count doesn't change — you tuned the wrong knob for the API you're using.

```text
+-----------------------------+-------------------------+------------------------+
| Config                      | Applies to               | Default                |
+-----------------------------+-------------------------+------------------------+
| spark.sql.shuffle.partitions| DataFrame / SQL shuffles | 200 (fixed)            |
| spark.default.parallelism   | RDD API shuffles         | total cores (varies)   |
+-----------------------------+-------------------------+------------------------+
```

---

## 7. Simulation: Right-Sizing Shuffle Partitions for Different Data Sizes

Computes the "right" number of shuffle partitions for a few data sizes using the ~100-200MB/partition rule of thumb (targeting the 150MB midpoint), and compares against the naive default of 200.

**Simulation:**
```python
target_partition_mb = 150  # midpoint of the 100-200MB recommended range
scenarios_gb = [0.5, 5, 50, 500, 2000]

print(f"  {'Shuffle data':>14} | {'Default=200 -> MB/part':>24} | "
      f"{'Recommended partitions':>24} | {'MB/part (recommended)':>22}")
print("  " + "-" * 92)
for size_gb in scenarios_gb:
    size_mb = size_gb * 1024
    default_mb_per_partition = size_mb / 200
    recommended_partitions = max(1, round(size_mb / target_partition_mb))
    recommended_mb_per_partition = size_mb / recommended_partitions
    print(f"  {size_gb:>11.1f}GB | {default_mb_per_partition:>21.2f}MB | "
          f"{recommended_partitions:>24} | {recommended_mb_per_partition:>19.1f}MB")
```

**Output:**
```text
  Shuffle data | Default=200 -> MB/part | Recommended partitions | MB/part (recommended)
  --------------------------------------------------------------------------------------
        0.5GB |                  2.56MB |                       3 |               170.7MB
        5.0GB |                 25.60MB |                      34 |               150.6MB
       50.0GB |                256.00MB |                     341 |               150.1MB
      500.0GB |               2560.00MB |                    3413 |               150.0MB
     2000.0GB |              10240.00MB |                   13653 |               150.0MB
```

Note how default=200 is reasonable only somewhere around the ~30GB mark (256.00MB/part is already drifting past the 100-200MB target there) and gets increasingly wrong (in both directions) the further data size drifts from that one sweet spot — at 0.5GB the default wastes overhead on 200 nearly-empty partitions, and at 2TB it would produce partitions roughly 68x larger than the recommended size.

---

## Key Takeaways

- A shuffle is a two-phase all-to-all data movement: map tasks write partitioned shuffle files to disk, reduce tasks fetch their slice from every map task over the network.
- `spark.sql.shuffle.partitions` defaults to 200 — a static, historical number that is right for roughly one data size and wrong for the rest.
- Too many partitions for small data means scheduling overhead dominates; too few for big data means oversized partitions, spill, and slow/OOM tasks.
- AQE's `coalescePartitions.enabled` merges small post-shuffle partitions at runtime based on ACTUAL measured sizes — but only merges down, never splits an oversized partition.
- Manual rule of thumb: `shuffle_partitions ~= total_shuffle_data_size / target_partition_size`, targeting ~100-200MB per partition.
- Shuffle spill (memory vs disk, visible separately in the Spark UI) signals partitions too large for available execution memory — fix by resizing partitions or executor memory, not by trying to disable spill.
- `spark.sql.shuffle.partitions` is for DataFrame/SQL; `spark.default.parallelism` is the separate, RDD-API equivalent — tuning the wrong one silently does nothing for the other API.
