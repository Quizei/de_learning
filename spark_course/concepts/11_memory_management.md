# Concept 11: Spark Memory Management

**Covers:**
- JVM heap breakdown for an executor (Reserved / User / Unified memory)
- The Unified Memory Model: spark.memory.fraction and spark.memory.storageFraction
- Execution memory vs storage memory, and why the boundary is "soft"
- Why it's called "unified" (pre-1.6 static split vs the movable boundary today)
- Off-heap memory (Tungsten, spark.memory.offHeap.*)
- Common causes of executor OOM
- Reading executor memory usage from the Spark UI (Executors / Storage tabs)

*All PySpark code below is educational/conceptual — it reflects real Spark configuration and behavior, but the worked examples are simulated in plain Python reasoning so you can follow along without a live cluster.*

---

## 1. The Executor JVM Heap: A High-Level Breakdown

Every Spark executor is a JVM process. When you set `--executor-memory 8g`, you are **not** saying "8GB is available for my data." The JVM heap itself is carved into three regions:

1. **Reserved Memory (~300MB, hardcoded)**
   Reserved for Spark's own internal objects and bookkeeping. It is not configurable — it's a hardcoded constant, `RESERVED_SYSTEM_MEMORY_BYTES`, in Spark's source. If your executor-memory is set below roughly 450-470MB, Spark will refuse to start ("please increase executor memory").

2. **User Memory `((heap - reserved) * (1 - spark.memory.fraction))`**
   Holds user-defined data structures, UDF working memory, RDD lineage metadata, and anything Spark itself doesn't directly track as execution/storage (e.g. objects your own Python/Scala code creates during a map/UDF call, before Arrow/Tungsten serialization). Default: 40% of (heap - reserved), since `spark.memory.fraction=0.6`.

3. **Unified Memory `((heap - reserved) * spark.memory.fraction)`**
   A shared pool for EXECUTION memory (shuffles, joins, sorts, aggregations) and STORAGE memory (cached RDDs/DataFrames, broadcast variables). Default: 60% of (heap - reserved). This region is what the rest of this file is really about.

```text
executor-memory = 8GB (example)

+--------------------------------------------------------------+
|                    JVM HEAP (8192 MB)                        |
+--------------------------------------------------------------+
| Reserved Memory        | ~300 MB  (hardcoded, not tunable)    |
+--------------------------------------------------------------+
| remaining = heap - reserved = 8192 - 300 = 7892 MB            |
+--------------------------------------------------------------+
|         User Memory (40%)        |   Unified Memory (60%)     |
|         = 7892 * 0.4             |   = 7892 * 0.6             |
|         = 3156.8 MB              |   = 4735.2 MB              |
|  (your objects, UDF state,       |  +----------------------+  |
|   lineage metadata)              |  | STORAGE   | EXECUTION|  |
|                                   |  | (cache)   | (shuffle,|  |
|                                   |  |           |  join,   |  |
|                                   |  |           |  sort)   |  |
|                                   |  +----------------------+  |
+--------------------------------------------------------------+

(Off-heap memory, if enabled, lives OUTSIDE this JVM heap entirely --
 see section 5.)
```

```python
# PySpark configuration (usually left at defaults unless tuning):

spark.conf.set("spark.memory.fraction", "0.6")          # unified memory share
spark.conf.set("spark.memory.storageFraction", "0.5")   # protected storage share
```

---

## 2. The Unified Memory Model in Detail

Introduced in Spark 1.6 (SPARK-10000), the Unified Memory Manager replaced the old static 60/40 execution/storage split (StaticMemoryManager) with a model where execution and storage share ONE pool and can borrow from each other, governed by two knobs:

- **`spark.memory.fraction` (default 0.6)** — fraction of (heap - reserved) given to the unified region at all. The rest is "user memory" for your own objects.
- **`spark.memory.storageFraction` (default 0.5)** — of the unified region, this fraction is the "storage safe zone": cached blocks that live in this zone CANNOT be evicted by execution. The remaining `(1 - storageFraction)` of unified memory is where execution can always reclaim space from storage if needed.

Eviction rules (this is the core mechanic):
- Execution memory requests are NEVER blocked by storage. If execution needs more space, it can evict cached blocks that sit ABOVE the storageFraction "safe" line.
- Storage cannot evict execution memory. If a task is actively shuffling or sorting and holding execution memory, cached data cannot force it out.
- This means storageFraction is a floor for cache, not a ceiling — storage CAN grow past storageFraction into unused execution space when execution isn't using it; it just becomes evictable once execution needs it.

```python
unified_memory = (heap - reserved) * spark.memory.fraction        # 0.6 default
storage_safe   = unified_memory * spark.memory.storageFraction    # 0.5 default
execution_safe = unified_memory - storage_safe
```

```text
+---------------------- UNIFIED MEMORY POOL ----------------------+
|                                                                  |
|   STORAGE "safe zone"        |  shared/borrowable region         |
|   (storageFraction, cannot   |  (execution can evict cached      |
|    be evicted by execution)  |   blocks here; storage can use    |
|                               |   it too when execution is idle)  |
|                                                                  |
+------------------------------------------------------------------+
```

**Simulation:**

This is a simplified simulation of the execution/storage borrowing rules — a small pool with a `cache_block` operation (storage side) and a `request_execution` operation (execution side) that evicts unprotected cached blocks when it needs to.

```python
class UnifiedMemoryPool:
    """Simplified simulation of execution/storage borrowing rules."""

    def __init__(self, unified_mb, storage_fraction=0.5):
        self.total = unified_mb
        self.storage_safe = unified_mb * storage_fraction
        self.storage_used = 0.0
        self.execution_used = 0.0

    def cache_block(self, size_mb):
        if self.storage_used + self.execution_used + size_mb <= self.total:
            self.storage_used += size_mb
            print(f"  [CACHE] Stored {size_mb}MB block. "
                  f"storage_used={self.storage_used:.0f}MB")
            return True
        print(f"  [CACHE] Not enough free space for {size_mb}MB block -- rejected/spilled")
        return False

    def request_execution(self, size_mb):
        free = self.total - self.storage_used - self.execution_used
        if size_mb <= free:
            self.execution_used += size_mb
            print(f"  [EXEC] Got {size_mb}MB from free space. "
                  f"execution_used={self.execution_used:.0f}MB")
            return
        # Need to evict storage blocks ABOVE the safe zone
        evictable = max(0.0, self.storage_used - self.storage_safe)
        need = size_mb - free
        evict = min(evictable, need)
        if evict > 0:
            self.storage_used -= evict
            print(f"  [EXEC] Evicted {evict:.0f}MB of cached (unprotected) storage")
        self.execution_used += size_mb
        print(f"  [EXEC] Got {size_mb}MB (after eviction). "
              f"execution_used={self.execution_used:.0f}MB, "
              f"storage_used={self.storage_used:.0f}MB")

# --- Simulating a 1000MB unified pool, storageFraction=0.5 ---
pool = UnifiedMemoryPool(unified_mb=1000, storage_fraction=0.5)
pool.cache_block(400)          # cached DataFrame, fits in free space
pool.cache_block(300)          # another cache -- total storage_used=700MB
pool.request_execution(500)    # a big shuffle needs 500MB
```

**Output:**
```text
  [CACHE] Stored 400MB block. storage_used=400MB
  [CACHE] Stored 300MB block. storage_used=700MB
  [EXEC] Evicted 200MB of cached (unprotected) storage
  [EXEC] Got 500MB (after eviction). execution_used=500MB, storage_used=500MB
```

Explanation: `storage_safe = 1000 * 0.5 = 500MB`. Storage was using 700MB, so 200MB (the amount above the 500MB safe line) was evictable. Free space was `1000 - 700 = 300MB`, execution needed 500MB total, so it evicted the 200MB shortfall and storage settled back down to its protected 500MB floor.

---

## 3. Why It's Called "Unified": Execution vs Storage, Before and After Spark 1.6

**Before Spark 1.6 (StaticMemoryManager):**
- Execution memory and storage memory had FIXED, separate regions.
- `spark.shuffle.memoryFraction` (execution) and `spark.storage.memoryFraction` (storage) were independent — if execution ran out, it spilled to disk even if storage had gigabytes of unused cache space sitting idle.
- This wasted memory badly: a job with light caching but heavy shuffling would OOM/spill while storage's reserved region sat empty.

**After Spark 1.6+ (UnifiedMemoryManager, still current):**
- ONE pool, and the boundary between execution and storage is SOFT — it moves at runtime based on actual demand.
- Execution memory has priority: it can evict storage's cached blocks (down to the storageFraction floor) whenever it needs the space.
- This is why it's called "unified" — not because there's no distinction between execution and storage (there still is, they track separately), but because they draw from a common, elastic pool instead of two rigid, wasteful partitions.

```text
PRE-1.6 (Static split -- wasteful):        POST-1.6 (Unified -- elastic):
+----------------+----------------+        +------------------------------+
| Execution 20%  | Storage 60%    |        |   ONE POOL (60% of heap)     |
| (fixed, can't  | (fixed, can't  |        |   execution <-> storage      |
|  grow even if  |  shrink even   |        |   boundary MOVES based on    |
|  storage idle) |  if unused)    |        |   which side needs memory    |
+----------------+----------------+        +------------------------------+

EXECUTION memory holds:                    STORAGE memory holds:
  - shuffle intermediate buffers              - cached RDDs / DataFrames (.cache()/.persist())
  - hash tables for joins/aggregations         - broadcast variables
  - sort buffers (external sort/spill)         - unroll memory for deserializing cached blocks
```

Key rule: execution can steal from storage; storage can never steal from execution while execution is actively using its memory. This protects running tasks from being OOM-killed because of cached data.

---

## 4. What Actually Lives in Execution Memory vs Storage Memory

A concrete look at what lands in each side of the unified pool during a real query.

```python
df_cached = df.filter(F.col("amount") > 0).cache()   # -> STORAGE memory
df_cached.count()                                      # materializes cache

joined = df_cached.join(other_df, "id")                # SortMergeJoin
# -> hash tables / sort buffers for the join land in EXECUTION memory

result = joined.groupBy("region").agg(F.sum("amount")) # shuffle + aggregation
# -> shuffle write/read buffers, aggregation hash maps -> EXECUTION memory
```

**Simulation:**

```python
events = [
    ("cache() a 2GB filtered DataFrame", "STORAGE", 2000),
    ("SortMergeJoin needs sort buffers", "EXECUTION", 1500),
    ("groupBy aggregation hash map", "EXECUTION", 800),
    ("broadcast variable for small dim table", "STORAGE", 50),
]

# --- Simulating memory attribution across a query ---
running_storage, running_execution = 0, 0
for desc, kind, mb in events:
    if kind == "STORAGE":
        running_storage += mb
    else:
        running_execution += mb
    print(f"    [{kind:<9}] {desc:<42} (+{mb}MB) "
          f"-> storage={running_storage}MB, execution={running_execution}MB")
```

**Output:**
```text
    [STORAGE  ] cache() a 2GB filtered DataFrame           (+2000MB) -> storage=2000MB, execution=0MB
    [EXECUTION] SortMergeJoin needs sort buffers            (+1500MB) -> storage=2000MB, execution=1500MB
    [EXECUTION] groupBy aggregation hash map                (+800MB) -> storage=2000MB, execution=2300MB
    [STORAGE  ] broadcast variable for small dim table      (+50MB) -> storage=2050MB, execution=2300MB
```

---

## 5. Off-Heap Memory

Off-heap memory stores data OUTSIDE the JVM heap, in raw allocated memory (via `sun.misc.Unsafe` / `java.nio.DirectByteBuffer`), managed by Spark's Tungsten execution engine rather than the JVM garbage collector.

Why it matters:
- The JVM garbage collector must scan/manage every on-heap object. Large heaps (many GB) can cause long "stop-the-world" GC pauses.
- Off-heap data (Tungsten's binary row format) is invisible to the GC — no pause cost, no object header overhead per record.
- Tungsten uses off-heap-style binary encoding for rows regardless, but `spark.memory.offHeap.enabled=true` lets Spark allocate that binary data truly off the JVM heap instead of inside it.

Configuration:
- `spark.memory.offHeap.enabled = false` (default)
- `spark.memory.offHeap.size = 0` (must set explicitly if enabled, e.g. `"4g"`)

Caveat: when off-heap is enabled, the unified memory model still applies conceptually (execution/storage still share and can evict each other) but now spans BOTH on-heap and off-heap unified regions — on-heap execution can still spill/borrow, and off-heap adds a separate pool sized by `spark.memory.offHeap.size`, on top of (not instead of) the JVM heap.

```python
spark.conf.set("spark.memory.offHeap.enabled", "true")
spark.conf.set("spark.memory.offHeap.size", "4g")   # in addition to executor-memory
```

```text
+---------------------------+     +---------------------------+
|     ON-HEAP (JVM heap)     |     |   OFF-HEAP (raw memory)   |
|  Reserved | User | Unified |     |   Unified (execution +    |
|           |      | (exec + |     |   storage), sized by      |
|           |      | storage)|     |   spark.memory.offHeap    |
|                            |     |   .size, NOT GC-managed   |
+---------------------------+     +---------------------------+
```

Trade-off: off-heap avoids GC pauses and per-object JVM overhead, but costs extra total memory footprint (it's ADDED to executor-memory, not carved out of it) and any bugs there are outside the JVM's memory safety.

---

## 6. What Causes Executor OOM

Common root causes of `java.lang.OutOfMemoryError` / executor lost errors:

1. **Partition too large relative to executor memory** — a single task processes one partition in one core's worth of memory. If a partition is, say, 10GB but the executor only has a few GB per core, that task OOMs even though the cluster overall has capacity.

2. **Huge broadcast variable** — `broadcast()` ships the FULL table to every executor's memory. If the "small" side of a broadcast join is misjudged (e.g. `autoBroadcastJoinThreshold` too high, or the table grew), it can blow up executor memory.

3. **Skewed partition** — one partition holds a disproportionate share of the data (data skew). That task needs far more memory than its peers and OOMs while others finish fine.

4. **Excess unevictable cached data** — if too much is cached with `MEMORY_ONLY` and doesn't fit, blocks are dropped and recomputed (not usually an OOM by itself) — but `MEMORY_AND_DISK` misconfigured, or off-heap cache pinned by long-running structured streaming state, can leave too little headroom for execution memory, especially when many concurrent tasks each need execution memory at once.

5. **Too many concurrent tasks per executor** — `executor-cores` set too high relative to `executor-memory` means many tasks share the same execution memory pool simultaneously, each getting a smaller slice (see spark.memory's fair-share division among concurrently running tasks) — more parallelism, but less memory per task.

6. **Driver-side OOM (different but often confused with executor OOM)** — `collect()`, `toPandas()`, or broadcasting from a huge collected dataset can OOM the DRIVER, not an executor. The symptom looks similar in logs but the fix (`driver-memory`, avoiding `collect()` on big data) is different.

```text
  - Partition too large            -> one task/core can't fit its partition in memory
  - Huge broadcast                 -> broadcast table doesn't fit in executor memory
  - Data skew                      -> one partition holds far more data than peers
  - Too many concurrent tasks      -> execution memory divided too thin per task
  - Cache pressure                 -> large persisted state leaves too little headroom
  - Driver OOM (lookalike)         -> collect()/toPandas() blows up the driver, not executors
```

First things to check when you see executor OOM:
1. Spark UI → Stages → find the failed stage → check "Shuffle Read" and "Input" size per task for skew (max vs median task size).
2. Spark UI → Executors tab → check "Peak Execution Memory" and "Storage Memory" columns for the failing executor.
3. Check `spark.sql.autoBroadcastJoinThreshold` vs actual size of the broadcast side.
4. Check `spark.sql.shuffle.partitions` — too few partitions for a big job means each partition (and each task) is oversized.

---

## 7. Reading Memory Usage from the Spark UI

The Spark UI (default port 4040 on the driver) exposes two tabs that are the primary tools for diagnosing memory issues:

**Executors tab:**
- "Storage Memory" column: shows used / total storage memory per executor (e.g. "512.3 MB / 2.1 GB") — this reflects the CURRENT unified memory split, which moves over time as execution borrows/returns space.
- "Peak JVM Memory" / "Peak Execution Memory" (Spark 3.x+ metrics): high-water marks, useful for seeing how close an executor got to OOM.
- "Task Time (GC Time)" column: high GC time relative to task time is a sign of memory pressure (lots of on-heap churn/allocation).

**Storage tab:**
- Lists every RDD/DataFrame that has been cached/persisted.
- Shows "Size in Memory", "Size on Disk" (if `MEMORY_AND_DISK` spilled), and "Fraction Cached" (what percentage of partitions actually got cached — less than 100% means some partitions were evicted or never fit).

```text
EXECUTORS TAB (simulated row):
+------------+----------+----------------------+------------------+
| Executor ID| Cores    | Storage Memory        | Task Time (GC)   |
+------------+----------+----------------------+------------------+
| 3          | 5        | 1.8 GB / 4.2 GB       | 45s (6.2s GC)    |
+------------+----------+----------------------+------------------+
High GC time (6.2s out of 45s task time = ~14%) suggests memory pressure.

STORAGE TAB (simulated row):
+------------------------+-------------+---------------+-----------------+
| RDD Name               | Size Memory | Size on Disk  | Fraction Cached |
+------------------------+-------------+---------------+-----------------+
| filtered_orders (cache)| 3.1 GB      | 0.9 GB        | 82%             |
+------------------------+-------------+---------------+-----------------+
82% cached, 18% spilled to disk -- storage memory was under pressure and
some partitions couldn't fit; those get recomputed or read from disk.
```

---

## 8. Simulation: Computing Memory Regions for a Given Executor Memory

This computes the real Spark unified-memory arithmetic for a given `--executor-memory` setting, exactly as Spark's `UnifiedMemoryManager` does.

**Simulation:**
```python
def simulate_memory_breakdown(executor_memory_mb, memory_fraction=0.6,
                               storage_fraction=0.5, reserved_mb=300):
    usable = executor_memory_mb - reserved_mb
    unified = usable * memory_fraction
    user_memory = usable * (1 - memory_fraction)
    storage_safe = unified * storage_fraction
    execution_safe = unified - storage_safe

    print(f"  Input: executor-memory = {executor_memory_mb} MB, "
          f"memory.fraction = {memory_fraction}, storageFraction = {storage_fraction}\n")
    print(f"    Reserved memory (fixed)         : {reserved_mb:>8.1f} MB")
    print(f"    Usable = total - reserved        : {usable:>8.1f} MB")
    print(f"    User memory   = usable*(1-{memory_fraction})  : {user_memory:>8.1f} MB")
    print(f"    Unified memory = usable*{memory_fraction}      : {unified:>8.1f} MB")
    print(f"      Storage 'safe zone' (0.5)     : {storage_safe:>8.1f} MB (never evicted by execution)")
    print(f"      Execution 'safe zone' (0.5)   : {execution_safe:>8.1f} MB (execution can always claim this)")
    print(f"      (storage can use MORE than its safe zone if execution isn't")
    print(f"       using its share -- but that extra becomes evictable)")

    return {
        "reserved_mb": reserved_mb,
        "user_memory_mb": round(user_memory, 1),
        "unified_memory_mb": round(unified, 1),
        "storage_safe_mb": round(storage_safe, 1),
        "execution_safe_mb": round(execution_safe, 1),
    }

simulate_memory_breakdown(8192)
```

**Output:**
```text
  Input: executor-memory = 8192 MB, memory.fraction = 0.6, storageFraction = 0.5

    Reserved memory (fixed)         :    300.0 MB
    Usable = total - reserved        :   7892.0 MB
    User memory   = usable*(1-0.6)   :   3156.8 MB
    Unified memory = usable*0.6      :   4735.2 MB
      Storage 'safe zone' (0.5)     :   2367.6 MB (never evicted by execution)
      Execution 'safe zone' (0.5)   :   2367.6 MB (execution can always claim this)
      (storage can use MORE than its safe zone if execution isn't
       using its share -- but that extra becomes evictable)
```

Calling it again with a different executor size and storage fraction (e.g. `simulate_memory_breakdown(4096, storage_fraction=0.3)`) recomputes all five numbers for that shape — the function is a general calculator, not tied to one executor size.

---

## Key Takeaways

- `executor-memory` splits into Reserved (~300MB fixed) + User memory + Unified memory (execution + storage), controlled by `spark.memory.fraction`.
- Unified memory is "unified" because execution and storage share one elastic pool instead of the old (pre-1.6) fixed 60/20 static split.
- Execution memory can evict storage (cached data) down to the storageFraction floor; storage can NEVER evict execution memory.
- `spark.memory.storageFraction` (default 0.5) sets the protected cache floor, not a hard cache ceiling — cache can use more when execution is idle.
- Off-heap memory (`spark.memory.offHeap.enabled`) avoids GC overhead by storing Tungsten's binary rows outside the JVM heap, at the cost of extra total memory footprint.
- OOM is usually skew, an oversized broadcast, too-large partitions, or too many concurrent tasks dividing execution memory too thin.
- The Spark UI's Executors tab (storage memory, GC time) and Storage tab (fraction cached, disk spill) are the first places to look for memory issues.
