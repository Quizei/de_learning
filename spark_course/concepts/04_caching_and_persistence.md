# Concept 04: Caching and Persistence

**Covers:**
- `.cache()` vs `.persist(StorageLevel)`
- StorageLevel options: MEMORY_ONLY, MEMORY_AND_DISK, MEMORY_ONLY_SER, DISK_ONLY, and the `_2` replication variants
- When caching helps (reused DataFrame, iterative algorithms) vs when it hurts (single-use DataFrame, cache larger than memory, caching too early before filters/projections)
- Lazy caching: `cache()` doesn't materialize until an action runs
- `.unpersist()` and why forgetting it leaks memory
- Checking cache status via `df.storageLevel` and the Spark UI Storage tab
- A simulation showing a DataFrame reused 3 times with and without caching, comparing relative work done

*All PySpark code below reflects real behavior of a running SparkSession; the worked examples are simulated in plain Python/reasoning so you can follow along without a cluster.*

---

## 1. .cache() vs .persist(StorageLevel)

`.cache()` is shorthand for `.persist(StorageLevel.MEMORY_AND_DISK)` for DataFrames (and `MEMORY_ONLY` for the legacy RDD API). It marks the DataFrame/RDD to be kept around after it's first computed, instead of being recomputed from scratch every time it's used again.

`.persist(level)` is the general form -- you choose exactly where and how the data is stored (memory, disk, both; serialized or not; replicated or not) via a `StorageLevel`.

Both are transformations in the sense that they don't do anything immediately -- see section 4 on lazy caching.

```python
from pyspark import StorageLevel

df.cache()                                    # shorthand: MEMORY_AND_DISK
df.persist(StorageLevel.MEMORY_ONLY)           # explicit: memory only, no disk fallback
df.persist(StorageLevel.DISK_ONLY)             # explicit: disk only
df.persist(StorageLevel.MEMORY_AND_DISK_SER)   # explicit: memory (serialized) + disk fallback
```

**Simulation:** confirm that `.cache()`'s implicit level matches `.persist()`'s default level.

```python
cache_level = "MEMORY_AND_DISK"
persist_default_level = "MEMORY_AND_DISK"
print(f"    df.cache()  internally requests level = {cache_level}")
print(f"    df.persist() with no args             = {persist_default_level}")
print(f"    Equivalent? {cache_level == persist_default_level}")
```

**Output:**
```text
    df.cache()  internally requests level = MEMORY_AND_DISK
    df.persist() with no args             = MEMORY_AND_DISK
    Equivalent? True
```

---

## 2. Storage Levels

`StorageLevel` controls WHERE cached partitions live and HOW they're encoded:

- **MEMORY_ONLY** -- deserialized Java/Python objects in RAM only. Fastest reads. Partitions that don't fit are simply NOT cached (recomputed on demand).
- **MEMORY_AND_DISK** -- same, but partitions that don't fit in RAM spill to local disk instead of being dropped.
- **MEMORY_ONLY_SER** -- serialized byte arrays in RAM. Much more compact (2-5x less space) but costs CPU to deserialize on every read.
- **MEMORY_AND_DISK_SER** -- serialized in RAM, spills serialized to disk.
- **DISK_ONLY** -- never uses RAM; all cached partitions on disk.
- **`_2` suffix** -- replicates each partition on 2 executors, trading memory/disk for fault tolerance (a lost executor doesn't force recomputation).

Rule of thumb: `MEMORY_ONLY` for small/medium data that fits easily; `MEMORY_AND_DISK` (the `.cache()` default) as a safe general choice; `*_SER` variants when data is large and memory-constrained; `DISK_ONLY` rarely, mainly for huge datasets you still want to avoid recomputing.

**Simulation:** print a comparison table of the six common levels.

```python
levels = [
    ("MEMORY_ONLY",          "RAM",        "deserialized", "no",  "fastest reads, lost if evicted"),
    ("MEMORY_AND_DISK",      "RAM+disk",   "deserialized", "no",  "safe default (.cache())"),
    ("MEMORY_ONLY_SER",      "RAM",        "serialized",   "no",  "compact, extra CPU to deserialize"),
    ("MEMORY_AND_DISK_SER",  "RAM+disk",   "serialized",   "no",  "compact + spill-safe"),
    ("DISK_ONLY",            "disk",       "serialized",   "no",  "never touches RAM"),
    ("MEMORY_AND_DISK_2",    "RAM+disk",   "deserialized", "yes", "replicated x2, survives executor loss"),
]
print(f"  {'Level':<22}{'Where':<12}{'Encoding':<14}{'Replicated':<12}{'Notes'}")
print("  " + "-" * 90)
for level, where, encoding, replicated, notes in levels:
    print(f"  {level:<22}{where:<12}{encoding:<14}{replicated:<12}{notes}")
```

**Output:**
```text
  Level                 Where       Encoding      Replicated  Notes
  ------------------------------------------------------------------------------------------
  MEMORY_ONLY           RAM         deserialized  no          fastest reads, lost if evicted
  MEMORY_AND_DISK       RAM+disk    deserialized  no          safe default (.cache())
  MEMORY_ONLY_SER       RAM         serialized    no          compact, extra CPU to deserialize
  MEMORY_AND_DISK_SER   RAM+disk    serialized    no          compact + spill-safe
  DISK_ONLY             disk        serialized    no          never touches RAM
  MEMORY_AND_DISK_2     RAM+disk    deserialized  yes         replicated x2, survives executor loss
```

---

## 3. When Caching Helps vs When It Hurts

Caching HELPS when:
- The same DataFrame is used as input to MULTIPLE actions (e.g. you call `.count()` then `.show()` then `.write()` on it)
- An iterative algorithm re-reads the same DataFrame across loop iterations (classic ML training loops, graph algorithms)
- Recomputing the DataFrame is expensive (a big join/aggregation upstream) relative to the cost of holding it in memory

Caching HURTS when:
- The DataFrame is used exactly ONCE -- you pay the cache-write cost for zero reuse benefit
- The cached data doesn't fit in available executor memory -- partitions get evicted (LRU) and silently recomputed anyway, so you paid the caching overhead for nothing, or (with `MEMORY_AND_DISK`) you pay slow disk spill costs instead
- You cache TOO EARLY, before filtering/projecting -- you end up caching far more data (and more columns) than the query actually needs downstream

```text
HELPS:                                  HURTS:
- reused across >=2 actions             - used exactly once
- iterative algorithms (ML, graph)       - doesn't fit in memory (spill/evict)
- expensive upstream computation         - cached before filter/select
                                          (caching unfiltered raw data)

BAD ORDER (caches too much):             GOOD ORDER (caches only what's needed):
df = spark.read.parquet(...).cache()     df = spark.read.parquet(...) \
result = df.filter(...).select(...)            .filter(...).select(...) \
                                                 .cache()
```

**Simulation:** compare memory held when caching before vs. after a filter/select.

```python
raw_size_mb = 5000
after_filter_select_mb = 800
print(f"  Caching BEFORE filter/select: {raw_size_mb} MB held in cache")
print(f"  Caching AFTER filter/select:  {after_filter_select_mb} MB held in cache")
print(f"  Memory saved by caching later: {raw_size_mb - after_filter_select_mb} MB "
      f"({100*(1 - after_filter_select_mb/raw_size_mb):.0f}% less)")
```

**Output:**
```text
  Caching BEFORE filter/select: 5000 MB held in cache
  Caching AFTER filter/select:  800 MB held in cache
  Memory saved by caching later: 4200 MB (84% less)
```

---

## 4. Lazy Caching

Calling `.cache()` (or `.persist()`) does NOT materialize anything by itself -- it just marks the DataFrame/RDD as "should be cached when next computed." Nothing is actually stored until an action runs and forces Spark to compute the partitions for the first time. That first action pays the full computation cost AND the cache-write cost; every subsequent action reading the same DataFrame reads straight from the cache instead of recomputing.

```python
df = spark.read.parquet("big_table.parquet").filter(F.col("amount") > 0)
df.cache()          # marks df as "cache me" -- NOTHING happens yet
df.count()          # ACTION #1: computes df AND populates the cache
df.show()           # ACTION #2: reads straight from cache, no recompute
```

**Simulation:** a stand-in `SimDataFrame` that tracks whether it's marked for caching and whether it's actually been materialized yet.

```python
class SimDataFrame:
    def __init__(self, name):
        self.name = name
        self.marked_for_cache = False
        self.materialized = False

    def cache(self):
        self.marked_for_cache = True
        print(f"  [SIM] {self.name}.cache() called -- marked only, nothing computed yet")
        return self

    def action(self, action_name):
        if self.marked_for_cache and self.materialized:
            print(f"  [SIM] {action_name}: reading '{self.name}' from CACHE (no recompute)")
        else:
            print(f"  [SIM] {action_name}: computing '{self.name}' from scratch...")
            if self.marked_for_cache:
                self.materialized = True
                print(f"  [SIM]   ... and populating the cache for next time")

df = SimDataFrame("filtered_orders")
df.cache()
df.action("count()")
df.action("show()")
df.action("write.parquet()")
```

**Output:**
```text
  [SIM] filtered_orders.cache() called -- marked only, nothing computed yet
  [SIM] count(): computing 'filtered_orders' from scratch...
  [SIM]   ... and populating the cache for next time
  [SIM] show(): reading 'filtered_orders' from CACHE (no recompute)
  [SIM] write.parquet(): reading 'filtered_orders' from CACHE (no recompute)
```

---

## 5. .unpersist() and Why Forgetting It Leaks Memory

Cached data occupies executor memory (and/or disk) for the lifetime of the SparkSession, or until explicitly released with `.unpersist()` -- or until Spark's LRU cache eviction forces it out under memory pressure. In a long-running application (a notebook session, a streaming job, a service) that caches many DataFrames across its lifetime without ever unpersisting old ones, cached blocks accumulate and reduce the memory available for new caching, execution, and shuffles -- effectively a memory leak, even though the JVM garbage collector is doing its job correctly (the references are intentional, held by Spark's BlockManager).

`.unpersist(blocking=True)` removes the cached blocks and blocks until done; `unpersist()` (non-blocking) schedules the removal asynchronously.

```python
df.cache()
df.count()          # materializes the cache
# ... use df many times ...
df.unpersist()       # release cached blocks -- ALWAYS do this when done
```

**Simulation:** four DataFrames cached in sequence, never unpersisted, tracking cumulative usage against a fixed executor memory budget.

```python
executor_memory_mb = 4000
cached_dataframes_mb = [800, 1200, 900, 700]  # accumulated over a session, never unpersisted

print(f"  Executor memory available for caching: {executor_memory_mb} MB")
total_cached = 0
for i, size in enumerate(cached_dataframes_mb, start=1):
    total_cached += size
    status = "OK" if total_cached <= executor_memory_mb else "EVICTING OLDEST BLOCKS"
    print(f"    DataFrame #{i} cached (+{size} MB) -> total cached: {total_cached} MB [{status}]")
```

**Output:**
```text
  Executor memory available for caching: 4000 MB
    DataFrame #1 cached (+800 MB) -> total cached: 800 MB [OK]
    DataFrame #2 cached (+1200 MB) -> total cached: 2000 MB [OK]
    DataFrame #3 cached (+900 MB) -> total cached: 2900 MB [OK]
    DataFrame #4 cached (+700 MB) -> total cached: 3600 MB [OK]
```

Without `unpersist()`, each new cached DataFrame competes for the same pool. Once total cached data exceeds available memory, Spark evicts the LEAST RECENTLY USED blocks -- possibly a DataFrame you still need, which then gets silently recomputed on its next use.

---

## 6. Checking Cache Status

Two ways to check whether/how a DataFrame is cached:

1. `df.storageLevel` -- returns the `StorageLevel` object Spark has recorded for this DataFrame (`useNone` if never persisted). You can inspect its `.useMemory`, `.useDisk`, `.deserialized`, `.replication` attributes.
2. **Spark UI -> Storage tab** -- lists every cached RDD/DataFrame by name, its storage level, fraction cached (0% to 100%; a partially-fitting cache shows less than 100%), size in memory, and size on disk. This is the ground truth for what's actually resident, as opposed to what you asked Spark to cache.

```python
df.cache()
df.count()
print(df.storageLevel)
# StorageLevel(True, True, False, True, 1)
#   useDisk=True, useMemory=True, useOffHeap=False, deserialized=True, replication=1
```

```text
Spark UI -> Storage tab (simulated listing):
+----------------------------+------------------+-------+----------+----------+
| RDD Name                  | Storage Level     | Cached% | Size Mem | Size Disk |
+----------------------------+------------------+-------+----------+----------+
| filtered_orders            | Memory Deserialized | 100%  | 812 MB   | 0 B      |
| large_join_result           | Memory+Disk        | 63%   | 2.1 GB   | 1.4 GB   |
+----------------------------+------------------+-------+----------+----------+
```

**Simulation:** a stand-in `SimStorageLevel` class showing what `df.storageLevel` reports.

```python
class SimStorageLevel:
    def __init__(self, use_disk, use_memory, deserialized, replication):
        self.useDisk = use_disk
        self.useMemory = use_memory
        self.deserialized = deserialized
        self.replication = replication

    def __repr__(self):
        return (f"StorageLevel(useDisk={self.useDisk}, useMemory={self.useMemory}, "
                f"deserialized={self.deserialized}, replication={self.replication})")

level = SimStorageLevel(use_disk=True, use_memory=True, deserialized=True, replication=1)
print(f"  df.storageLevel -> {level}")
```

**Output:**
```text
  df.storageLevel -> StorageLevel(useDisk=True, useMemory=True, deserialized=True, replication=1)
```

---

## 7. Simulation: A DataFrame Reused 3 Times, With vs Without Caching

Concrete comparison: a DataFrame built via an expensive upstream transformation (say, cost = 100 "work units" to compute) is then used by 3 separate actions. Without caching, each action recomputes the full upstream chain. With caching, only the FIRST action pays that cost -- the other two read from cache for near-zero cost.

```python
upstream_cost = 100   # work units to compute the DataFrame from raw source
cache_read_cost = 5   # work units to read an already-cached DataFrame
num_actions = 3

print(f"  Upstream computation cost: {upstream_cost} work units")
print(f"  Cache read cost:           {cache_read_cost} work units")
print(f"  Number of actions reusing the DataFrame: {num_actions}\n")

# Without caching: every action recomputes from scratch
without_cache_total = 0
print("  WITHOUT caching:")
for i in range(1, num_actions + 1):
    without_cache_total += upstream_cost
    print(f"    Action {i}: recompute from source -> cost {upstream_cost} "
          f"(running total: {without_cache_total})")

# With caching: first action computes + caches, rest read from cache
with_cache_total = 0
print("\n  WITH caching (.cache() called before the actions):")
for i in range(1, num_actions + 1):
    if i == 1:
        with_cache_total += upstream_cost
        print(f"    Action {i}: compute from source AND populate cache -> cost {upstream_cost} "
              f"(running total: {with_cache_total})")
    else:
        with_cache_total += cache_read_cost
        print(f"    Action {i}: read from cache -> cost {cache_read_cost} "
              f"(running total: {with_cache_total})")

savings = without_cache_total - with_cache_total
print(f"\n  Total work WITHOUT caching: {without_cache_total} units")
print(f"  Total work WITH caching:    {with_cache_total} units")
print(f"  Work saved by caching:      {savings} units "
      f"({100*savings/without_cache_total:.0f}% reduction)")
```

**Output:**
```text
  Upstream computation cost: 100 work units
  Cache read cost:           5 work units
  Number of actions reusing the DataFrame: 3

  WITHOUT caching:
    Action 1: recompute from source -> cost 100 (running total: 100)
    Action 2: recompute from source -> cost 100 (running total: 200)
    Action 3: recompute from source -> cost 100 (running total: 300)

  WITH caching (.cache() called before the actions):
    Action 1: compute from source AND populate cache -> cost 100 (running total: 100)
    Action 2: read from cache -> cost 5 (running total: 105)
    Action 3: read from cache -> cost 5 (running total: 110)

  Total work WITHOUT caching: 300 units
  Total work WITH caching:    110 units
  Work saved by caching:      190 units (63% reduction)
```

---

## Key Takeaways

- `.cache()` is shorthand for `.persist(StorageLevel.MEMORY_AND_DISK)`; `.persist()` lets you pick memory/disk, serialization, and replication.
- Cache DataFrames that are reused across multiple actions or loop iterations -- never a DataFrame used exactly once.
- `cache()`/`persist()` are lazy: nothing is stored until the next action actually materializes the partitions.
- Cache AFTER filtering/projecting, not before -- caching raw, unfiltered data wastes memory on columns/rows you don't need.
- If cached data doesn't fit in memory, `MEMORY_ONLY` silently drops partitions (recomputed later); `MEMORY_AND_DISK` spills to disk instead.
- Always `.unpersist()` when you're done with a cached DataFrame -- otherwise cached blocks accumulate and evict data you still need.
- Verify caching with `df.storageLevel` or the Spark UI's Storage tab -- don't just assume `cache()` "worked" as expected.
