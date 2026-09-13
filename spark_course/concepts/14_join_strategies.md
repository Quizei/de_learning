# Concept 14: Join Strategies Deep Dive

**Covers:**
- The 4 physical join strategies Spark's optimizer chooses from
- Broadcast Hash Join (BHJ)
- Shuffle Hash Join (SHJ)
- Sort-Merge Join (SMJ)
- Broadcast Nested Loop Join / Cartesian Product
- The decision tree Spark walks through to pick a strategy
- Forcing a strategy with hints
- Reading which join strategy was picked from explain()
- Cost simulation: BHJ vs SMJ for a small-join-large scenario

> *Note: this topic isn't in the source YouTube playlist — added because it's essential and commonly asked about.*

*The PySpark snippets below reflect what you'd run against a real Spark session; the worked examples and their output are simulated here in pure Python so you can follow the mechanics without a cluster.*

---

## 1. The four physical join strategies

When you write `df1.join(df2, "key")`, that's a LOGICAL operation. Catalyst's physical planner must pick one of several PHYSICAL implementations to actually execute it. The choice is driven by:

- equi-join vs non-equi-join (does the condition use `==`?)
- the estimated size of each side (from stats or AQE runtime stats)
- configured thresholds and hints

The four strategies, roughly best-case to worst-case:

1. Broadcast Hash Join (BHJ) — no shuffle, one side small
2. Sort-Merge Join (SMJ) — shuffle + sort both sides (default)
3. Shuffle Hash Join (SHJ) — shuffle both sides, hash build
4. Broadcast Nested Loop / Cartesian — O(n\*m), last resort

```text
+----------------------------+---------------+------------------+
| Strategy                   | Shuffle?      | Needs equi-join? |
+----------------------------+---------------+------------------+
| Broadcast Hash Join (BHJ)  | No            | Yes (preferred)  |
| Sort-Merge Join (SMJ)      | Yes (both)    | Yes              |
| Shuffle Hash Join (SHJ)    | Yes (both)    | Yes              |
| Broadcast Nested Loop      | No (broadcast)| No -- any cond.  |
| Cartesian Product          | No            | No -- no cond.   |
+----------------------------+---------------+------------------+
```

Rule of thumb: BHJ > SMJ > SHJ > BNLJ/Cartesian, in terms of "how much you want the optimizer to pick this."

---

## 2. Broadcast Hash Join (BHJ)

Broadcast Hash Join (BHJ):

- One side of the join is small enough to fit comfortably in executor memory (default threshold: `spark.sql.autoBroadcastJoinThreshold` = 10MB, based on estimated/collected byte size).
- The driver collects that small side, builds a hash table, and BROADCASTS the whole hash table to every executor.
- Each executor then does a local hash-join: for every row in the large side's partitions, probe the local copy of the hash table.
- NO SHUFFLE of the large side is needed — huge win, because the large side (the expensive one to move) never moves at all.

Cost: driver collect + broadcast cost (network + memory per executor) is O(size of small side), completely independent of the large side's size. This is why BHJ is the fastest strategy when it's applicable.

Caveat: if the "small" side turns out to be bigger than it looks (bad stats, skew, an exploded join), you can get a driver OOM or executor OOM trying to build/hold the broadcast hash table.

```text
Large table (fact, 1B rows)      Small table (dim, 500 rows)
+---------+---------+---------+          |
| Part 0  | Part 1  | Part 2  |    broadcast to every executor
+---------+---------+---------+    (hash table built once, copied N times)
     |          |          |               |
     v          v          v               v
+---------+---------+---------+   each partition probes its LOCAL
| probe   | probe   | probe   |   copy of the small table's hash map
+---------+---------+---------+
     |          |          |
     v          v          v
  results   results    results   <-- NO SHUFFLE of the fact table!
```

```python
from pyspark.sql import functions as F

result = fact_df.join(F.broadcast(dim_df), "dim_id")

# Or via config (auto-applied below this size):
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", 10 * 1024 * 1024)  # 10MB default
```

**Simulation:** broadcast join cost model — 1M-row fact table, 500-row dim table, 4 executors. In BHJ, only the small side is moved, and it's moved once per executor.

```python
fact_rows = 1_000_000
dim_rows = 500
executors = 4

bytes_per_row_dim = 40   # bytes, illustrative
bytes_per_row_fact = 120

broadcast_bytes_moved = dim_rows * bytes_per_row_dim * executors
fact_bytes_moved = 0  # fact table stays where it is, read locally
```

**Output:**
```text
Fact table rows:        1,000,000
Dim table rows:         500
Executors:              4
Bytes moved (broadcast dim to each executor): 80,000 bytes
Bytes moved (fact table, shuffled):           0 bytes
Total bytes moved over network: 80,000
```

---

## 3. Shuffle Hash Join (SHJ)

Shuffle Hash Join (SHJ):

- Both sides are SHUFFLED (repartitioned) by the join key, so all rows for a given key land on the same executor — same as SMJ.
- Unlike SMJ, there's no sort step: instead, on each partition, Spark builds an in-memory hash table on the SMALLER side's partition, then streams the larger side's partition rows through it, probing the hash table.
- Requires the smaller side's PER-PARTITION data to fit in memory (not the whole table — just one partition's worth, post-shuffle).

Why it's rarely chosen by default:

- Spark's config `spark.sql.join.preferSortMergeJoin` defaults to TRUE, meaning the optimizer prefers SMJ over SHJ whenever both are viable equi-joins on sortable keys, because SMJ is more robust to partition-level data size variance (spills more gracefully; SHJ's hash table can blow executor memory if a partition is larger than expected).
- SHJ is only picked when `preferSortMergeJoin=false` AND one side is still reasonably small (but too big to broadcast) after the shuffle.

Cost: same shuffle cost as SMJ (both sides shuffled), but skips the sort — cheaper CPU-wise per partition IF the hash table fits memory.

```text
Both sides shuffled by join key (same as SMJ):

Table A (large)         Table B (medium)
+----+----+----+        +----+----+----+
| P0 | P1 | P2 |        | P0 | P1 | P2 |
+----+----+----+        +----+----+----+
  |    |    |             |    |    |
  +----+----+ shuffle +---+----+----+
            by key
  v    v    v             v    v    v
+----+----+----+        +----+----+----+
| P0 | P1 | P2 |        | P0 | P1 | P2 |   <-- matching keys co-located
+----+----+----+        +----+----+----+

Per output partition: build hash table on B's slice, probe with A's rows.
No sort step (that's the difference vs SMJ).
```

```python
# PySpark hint to request it:
result = big_df.join(medium_df.hint("shuffle_hash"), "key")

# Config:
spark.conf.set("spark.sql.join.preferSortMergeJoin", "false")
```

**Simulation:** SHJ vs SMJ CPU cost per partition. Illustrative cost units: SMJ pays O(n log n) sort on both sides + O(n+m) merge; SHJ pays O(n) hash build + O(m) probe, no sort.

```python
import math

rows_per_partition_small_side = 50_000
rows_per_partition_large_side = 200_000

smj_sort_cost = (rows_per_partition_small_side * math.log2(rows_per_partition_small_side)
                 + rows_per_partition_large_side * math.log2(rows_per_partition_large_side))
smj_merge_cost = rows_per_partition_small_side + rows_per_partition_large_side
smj_total = smj_sort_cost + smj_merge_cost

shj_build_cost = rows_per_partition_small_side
shj_probe_cost = rows_per_partition_large_side
shj_total = shj_build_cost + shj_probe_cost
```

**Output:**
```text
SMJ cost units (sort both sides + merge): 4,552,410
SHJ cost units (hash build + probe, no sort): 250,000
SHJ is cheaper here IF the 50,000-row partition's hash table fits in executor memory.
```

---

## 4. Sort-Merge Join (SMJ) — the default for large x large

Sort-Merge Join (SMJ) — the DEFAULT strategy for large-large equi-joins:

1. SHUFFLE: both sides are repartitioned by the join key's hash, so matching keys land on the same partition (a wide transformation).
2. SORT: within each partition, rows are sorted by the join key.
3. MERGE: a single linear pass over both sorted partitions — like merging two sorted lists — emits matches. No hash table needed because sorted order means matching keys are already adjacent.

Why sorting first? Once both sides are sorted by the same key, you can merge them with two pointers in O(n + m) *after* the O(n log n) sort — and critically, SMJ can SPILL sorted runs to disk gracefully if a partition doesn't fit in memory, unlike a hash table which either fits or blows up. That robustness is exactly why `preferSortMergeJoin=true` is the default.

SMJ is chosen when:
- Both sides are too large to broadcast, AND
- The join is an equi-join on a sortable key type.

```text
Table A                       Table B
+----+----+----+             +----+----+----+
| P0 | P1 | P2 |             | P0 | P1 | P2 |
+----+----+----+             +----+----+----+
   |                            |
   v  SHUFFLE by join key       v  SHUFFLE by join key
+----+----+----+             +----+----+----+
| P0 | P1 | P2 |             | P0 | P1 | P2 |   same keys co-located
+----+----+----+             +----+----+----+
   |                            |
   v  SORT by key locally       v  SORT by key locally
[1,3,3,7,9]                  [1,3,5,7,7]
   \___________ MERGE (two-pointer scan) ___________/
                      |
                      v
              matched output rows
```

```python
# PySpark hint to force it explicitly:
result = a_df.join(b_df.hint("merge"), "key")
```

**Simulation:** the merge step itself, over two already-sorted partitions (each key handles all matching pairs, including duplicates on both sides).

```python
table_a_sorted = [(1, "a1"), (3, "a2"), (3, "a3"), (7, "a4"), (9, "a5")]
table_b_sorted = [(1, "b1"), (3, "b2"), (5, "b3"), (7, "b4"), (7, "b5")]

i, j = 0, 0
matches = []
while i < len(table_a_sorted) and j < len(table_b_sorted):
    key_a, val_a = table_a_sorted[i]
    key_b, val_b = table_b_sorted[j]
    if key_a == key_b:
        # emit all matching pairs for this key (handle duplicates on both sides)
        i_start = i
        while i < len(table_a_sorted) and table_a_sorted[i][0] == key_a:
            j_scan = j
            while j_scan < len(table_b_sorted) and table_b_sorted[j_scan][0] == key_a:
                matches.append((key_a, table_a_sorted[i][1], table_b_sorted[j_scan][1]))
                j_scan += 1
            i += 1
        j = j_scan
    elif key_a < key_b:
        i += 1
    else:
        j += 1

for m in matches:
    print(f"key={m[0]}: {m[1]} <-> {m[2]}")
```

**Output:**
```text
key=1: a1 <-> b1
key=3: a2 <-> b2
key=3: a3 <-> b2
key=7: a4 <-> b4
key=7: a4 <-> b5
```

---

## 5. Broadcast Nested Loop Join / Cartesian Product

Broadcast Nested Loop Join (BNLJ):

- Used for NON-EQUI joins (e.g. `a.start <= b.ts AND b.ts < a.end`) where there's no equality key to hash or sort on.
- One side is broadcast (if small enough), and for every row on the large side, Spark scans the ENTIRE broadcast side checking the condition. O(n \* m) comparisons.
- If neither side is small enough to broadcast, Spark falls back to a full CARTESIAN PRODUCT — shuffle-free, but O(n \* m) rows produced. This is the worst case and should be avoided.

When you see this in a plan, it usually means:
- You forgot a join condition (accidental cross join)
- Your join condition isn't a clean equality (range join, `<`, `OR`)

Fix: add an equi-join predicate if possible, or explicitly acknowledge intent with `df1.crossJoin(df2)` so it's not accidental, and consider bucketing/pre-filtering to shrink both sides first.

```text
Non-equi join example:
    events.join(sessions,
        (events.ts >= sessions.start) & (events.ts < sessions.end))

For every row in `events`, scan ALL rows in `sessions` (or vice versa):

    events row 1 -> check against session 1, 2, 3, ... N
    events row 2 -> check against session 1, 2, 3, ... N
    ...
    events row M -> check against session 1, 2, 3, ... N

    Total comparisons: M * N   <-- quadratic, avoid at scale!
```

**Simulation:** cost blow-up, BNLJ/Cartesian vs equi-join.

```python
for m, n in [(1_000, 1_000), (100_000, 1_000), (1_000_000, 10_000)]:
    comparisons = m * n
    print(f"events={m:>9,}  sessions={n:>7,}  ->  {comparisons:,} comparisons")
```

**Output:**
```text
events=    1,000  sessions=  1,000  ->  1,000,000 comparisons
events=  100,000  sessions=  1,000  ->  100,000,000 comparisons
events=1,000,000  sessions= 10,000  ->  10,000,000,000 comparisons
```

Compare to an equi-join with a hash/sort strategy: O(n + m), not O(n \* m). This is why cartesian joins are avoided at scale.

---

## 6. The decision tree

Simplified version of the decision Spark's physical planner walks through for a two-table join (`SparkStrategies.JoinSelection`):

1. Is there an equi-join condition?
   - NO -> can one side be broadcast? YES -> BroadcastNestedLoopJoin; NO -> CartesianProduct (or error)
   - YES -> continue to step 2
2. Is one side small enough to broadcast? (size <= `spark.sql.autoBroadcastJoinThreshold`, default 10MB, or explicitly hinted with `F.broadcast()` / `.hint("broadcast")`)
   - YES -> BroadcastHashJoin (BHJ)
   - NO -> continue to step 3
3. Is `spark.sql.join.preferSortMergeJoin` true (default)?
   - YES -> SortMergeJoin (SMJ)
   - NO -> is one side small enough for a per-partition hash table after shuffling (but too big to broadcast)? YES -> ShuffleHashJoin (SHJ); NO -> SortMergeJoin (SMJ) anyway (fallback)

AQE (Adaptive Query Execution) can also convert a planned SMJ into a BHJ AT RUNTIME if actual shuffle stats show one side turned out to be small (see `concepts/09_aqe_and_broadcast_joins.py`).

```text
equi-join condition present?
  |
  +-- NO --> broadcastable side exists? --> YES: BroadcastNestedLoopJoin
  |                                     --> NO:  CartesianProduct
  |
  +-- YES --> one side <= autoBroadcastJoinThreshold (or hinted)?
                |
                +-- YES --> BroadcastHashJoin (BHJ)      <- best case
                |
                +-- NO  --> preferSortMergeJoin (default true)?
                              |
                              +-- YES --> SortMergeJoin (SMJ)   <- default
                              |
                              +-- NO  --> small enough for hash
                                          table per partition?
                                            +-- YES --> ShuffleHashJoin
                                            +-- NO  --> SortMergeJoin
```

---

## 7. Forcing a strategy with hints

Spark supports SQL/DataFrame hints to override the optimizer's choice. Hints are a strong signal but not an absolute guarantee — Spark will still refuse an impossible plan (e.g. broadcasting a table larger than driver/executor memory can hold may still fail or be ignored with a warning depending on version/config).

| Hint | DataFrame API | SQL |
|---|---|---|
| Broadcast | `F.broadcast(df)` / `df.hint("broadcast")` | `/*+ BROADCAST(t) */` |
| Sort-Merge | `df.hint("merge")` | `/*+ MERGE(t) */` |
| Shuffle Hash | `df.hint("shuffle_hash")` | `/*+ SHUFFLE_HASH(t) */` |
| Shuffle Replicate NL | `df.hint("shuffle_replicate_nl")` | `/*+ SHUFFLE_REPLICATE_NL(t) */` |

```python
from pyspark.sql import functions as F

# Force broadcast (most common hint in practice)
result = fact_df.join(F.broadcast(dim_df), "dim_id")
# equivalent:
result = fact_df.join(dim_df.hint("broadcast"), "dim_id")

# Force sort-merge join even if one side looks small
result = a_df.join(b_df.hint("merge"), "key")

# Force shuffle hash join
result = a_df.join(b_df.hint("shuffle_hash"), "key")

# Force shuffle-and-replicate nested loop (for non-equi joins you
# want parallelized rather than a full broadcast)
result = a_df.join(b_df.hint("shuffle_replicate_nl"), condition)

# SQL form
spark.sql("""
    SELECT /*+ BROADCAST(dim) */ *
    FROM fact JOIN dim ON fact.dim_id = dim.dim_id
""")
```

When to use hints:
- Stats are stale/missing (e.g. reading from a source Spark can't estimate well) and you KNOW one side is small.
- AQE isn't enabled or isn't converting the join as expected.
- You need a deterministic plan for testing/benchmarking.

---

## 8. Reading the strategy from explain()

Physical plan operator names to look for in `df.explain()`:

- "BroadcastHashJoin" -> BHJ
- "SortMergeJoin" -> SMJ
- "ShuffleHashJoin" -> SHJ
- "BroadcastNestedLoopJoin" -> BNLJ
- "CartesianProduct" -> cartesian

You'll also see supporting operators around them:
- "Exchange hashpartitioning(key, N)" -> a shuffle happened (SMJ/SHJ)
- "BroadcastExchange" -> the broadcast collection step
- "Sort" -> confirms SMJ's sort phase

```text
Example BHJ plan (df.explain()):
---------------------------------------------------------------
== Physical Plan ==
*(2) BroadcastHashJoin [dim_id#12], [dim_id#34], Inner, BuildRight
:- *(2) FileScan parquet fact_table ...
+- BroadcastExchange HashedRelationBroadcastMode
   +- *(1) FileScan parquet dim_table ...
---------------------------------------------------------------
Read as: "small side (dim_table) is broadcast (BuildRight), large
side (fact_table) is scanned and probed directly -- no Exchange
(shuffle) on the fact side."

Example SMJ plan:
---------------------------------------------------------------
== Physical Plan ==
*(5) SortMergeJoin [key#1], [key#2], Inner
:- *(2) Sort [key#1 ASC], false, 0
:  +- Exchange hashpartitioning(key#1, 200)
:     +- *(1) FileScan parquet table_a ...
+- *(4) Sort [key#2 ASC], false, 0
   +- Exchange hashpartitioning(key#2, 200)
      +- *(3) FileScan parquet table_b ...
---------------------------------------------------------------
Read as: BOTH sides have "Exchange" (shuffle) + "Sort" before the
SortMergeJoin -- this is the fingerprint of SMJ.
```

---

## 9. Cost comparison simulation: BHJ vs SMJ

A concrete "should this have been a broadcast join?" simulation: fixed large table, varying small table size, comparing simulated bytes-moved for BHJ vs SMJ.

- BHJ cost model (simplified): `small_side_bytes * num_executors` (the small side gets copied to every executor once)
- SMJ cost model (simplified): `large_side_bytes + small_side_bytes` (both sides get shuffled across the network once, total ~2x each row's bytes: read + write of the shuffle)

```python
large_rows = 500_000_000       # 500M row fact table
large_row_bytes = 100
large_bytes = large_rows * large_row_bytes  # 50 GB
executors = 20

for small_mb in [1, 10, 50, 200, 1000]:
    small_bytes = small_mb * 1024 * 1024

    bhj_bytes_moved = small_bytes * executors      # broadcast to each executor
    smj_bytes_moved = large_bytes + small_bytes    # both sides shuffled once

    winner = "BHJ" if bhj_bytes_moved < smj_bytes_moved else "SMJ"
```

**Output:**
```text
Large (fact) table: 500,000,000 rows, ~50.0 GB
Executors: 20

Small table size    BHJ bytes moved       SMJ bytes moved       Winner
------------------------------------------------------------------------------
     1 MB             0.021 GB           50.001 GB         BHJ
    10 MB             0.210 GB           50.010 GB         BHJ
    50 MB             1.049 GB           50.052 GB         BHJ
   200 MB             4.194 GB           50.210 GB         BHJ
  1000 MB            20.972 GB           51.049 GB         BHJ
```

Takeaway: broadcasting the small side is cheaper across a very wide range of sizes, because SMJ must move the ENTIRE large side across the network regardless of how small the other side is. This is why `autoBroadcastJoinThreshold` exists, and why bumping it up (or hinting broadcast explicitly) for a "medium" dimension table is often a big win — but note the default is a conservative 10MB precisely because broadcasting too aggressively risks driver/executor memory pressure.

---

## Key Takeaways

- Spark picks from 4 physical join strategies: BHJ, SMJ, SHJ, and BNLJ/Cartesian — the choice depends on equi-join-ness and size.
- BHJ (Broadcast Hash Join) avoids shuffling the large side entirely by broadcasting a hash table of the small side to every executor — fastest when applicable, but risks OOM if the "small" side isn't.
- SMJ (Sort-Merge Join) is the default for large-large equi-joins: shuffle both sides, sort each partition, merge with two pointers. It's preferred over SHJ because it spills to disk gracefully.
- SHJ (Shuffle Hash Join) skips the sort and builds a per-partition hash table instead — only chosen when `preferSortMergeJoin=false` and the smaller side's partitions fit comfortably in memory.
- BNLJ/Cartesian are O(n\*m) fallbacks for non-equi joins or missing join conditions — a red flag in an `explain()` plan at any scale.
- Use `F.broadcast(df)`, `.hint("merge")`, `.hint("shuffle_hash")`, or `.hint("shuffle_replicate_nl")` to override the optimizer's choice.
- Read `explain()` for "BroadcastHashJoin"/"BroadcastExchange" (BHJ) vs "SortMergeJoin" with "Exchange"+"Sort" on both sides (SMJ).
- AQE can convert a planned SMJ into a BHJ at runtime once actual shuffle-write sizes are known — see `concepts/09_aqe_and_broadcast_joins.py`.
