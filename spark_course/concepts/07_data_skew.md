# Concept 07: Data Skew

**Covers:**
- What data skew is and why it's a partition-level problem
- Symptoms of skew visible in the Spark UI
- Common causes: skewed join keys, groupBy hotspots, date partitioning
- How to detect skew (Spark UI task view + manual groupBy/count check)
- Simulation: a clearly skewed key distribution and its task-time impact

*The PySpark snippets below are educational/conceptual — they describe what really happens against a real Spark session, but the worked examples are simulated in plain Python so you can follow along without a cluster.*

---

## 1. What is data skew?

Data skew happens when the rows for a shuffle are NOT evenly distributed across partitions/tasks — one or a handful of keys account for a disproportionate share of the data.

Spark parallelizes work by giving each task one partition to process. If partition sizes are roughly equal, all tasks finish around the same time. If one partition has, say, 70% of all the rows (because one key is extremely common — a popular `customer_id`, a "NULL"/"UNKNOWN" placeholder, a bot user, etc.), the task handling that partition takes far longer than the others, and the STAGE cannot finish until that one task finishes. The other executors sit idle waiting.

Skew is fundamentally a HASH PARTITIONING problem: a wide transformation (join, `groupBy`, `distinct`, `repartition`) hashes rows to partitions by key. Hashing distributes DISTINCT keys evenly, but says nothing about the ROW COUNT per key — a key with a million rows and a key with one row both hash to exactly one partition each.

```text
Balanced partitions (ideal):          Skewed partitions (problem):

Partition 0: [=====]  25%             Partition 0: [===============] 70%
Partition 1: [=====]  25%             Partition 1: [==]              8%
Partition 2: [=====]  25%             Partition 2: [==]              9%
Partition 3: [=====]  25%             Partition 3: [==]             13%

All 4 tasks finish in ~ the same time  Task 0 takes ~7x longer than the
                                        others -- stage waits on it alone
```

Why hashing alone can't prevent skew:

```text
hash("customer_42") % 4 = 0     <- 1,000,000 rows for customer_42
hash("customer_17") % 4 = 1     <- 3 rows for customer_17
hash("customer_88") % 4 = 2     <- 5 rows for customer_88
hash("customer_03") % 4 = 3     <- 2 rows for customer_03
```

Partition 0 gets 1,000,000 rows just because ONE popular key landed there — hashing balances the KEY SPACE, not the ROW COUNT.

---

## 2. Symptoms of skew in the Spark UI

Skew is usually diagnosed by looking at the Spark UI's Stages tab:

- **Task duration distribution**: the "Summary Metrics" table shows Min / 25th percentile / Median / 75th percentile / Max task duration. Skew shows up as Max >> Median (e.g. median 4s, max 8min).
- The stage's progress bar appears "stuck" near 100% — e.g. 199 of 200 tasks finished in seconds, and the job waits minutes for the last 1 task.
- The event timeline / executor tab shows one executor with very high "Task Time (GC Time)" — it's spending time garbage collecting a huge in-memory partition.
- **Shuffle Read size per task**, visible in the stage detail table, shows one task reading orders of magnitude more shuffle bytes than the rest ("Shuffle Read Size / Records" column).
- **Spill (memory and disk) metrics** are non-zero only for the skewed task — it couldn't fit its partition in memory and spilled to disk, which is much slower.

Spark UI — Stage detail, Summary Metrics (illustrative):

```text
    Metric              Min      25th%    Median   75th%    Max
    -------------------------------------------------------------
    Duration             1.2s     1.4s     1.6s     1.8s    9.4min   <- red flag
    Shuffle Read Size    2 MB     2 MB     2 MB     3 MB    1.4 GB   <- red flag
    GC Time               50ms     60ms     70ms     90ms    41s     <- red flag
    Spill (disk)          0 B      0 B      0 B      0 B     620 MB  <- red flag
```

Job progress bar symptom:

```text
    [======================================>  ] 199/200 tasks
    (stuck here for 8 more minutes while 1 task grinds through
     its oversized partition)
```

---

## 3. Common causes of skew

The most frequent real-world causes of skew:

1. **Join on a low-cardinality or skewed key** — e.g. joining on `"status"` (only 3 distinct values) or on `customer_id` where one `customer_id` (`"SYSTEM_ACCOUNT"`) appears in a huge fraction of rows.
2. **groupBy on a key with a dominant value** — e.g. grouping web events by `user_id` where one user is a bot generating far more events than any human.
3. **NULL / placeholder values concentrated in one key** — e.g. a `customer_id` column where unmatched or legacy records are all stamped NULL or "UNKNOWN" — these all hash to the same partition and can dwarf every real customer's row count.
4. **Date-based partitioning/grouping where one day dominates** — e.g. grouping by `event_date` where a Black Friday sale generates 50x the normal day's traffic, and everything for that date lands in one task.

| Cause | Example |
|---|---|
| Join on skewed key | `customer_id='SYSTEM_ACCOUNT'` present in 40% of rows |
| groupBy hotspot | `user_id` for a bot dominates event counts |
| NULL/placeholder overload | unmatched foreign keys all stored as NULL |
| Date partitioning | Black Friday date has 50x normal daily volume |

---

## 4. How to detect skew

Two practical ways to detect skew before it bites you in production:

1. **Spark UI, Stages tab**: look at the task duration / shuffle-read distribution as described above (Max task time >> median).
2. **Manual, proactive check** on any suspected join/groupBy key:
   ```python
   df.groupBy(key).count().orderBy(F.desc("count")).show()
   ```
   If the top row's count is far larger than the rest (an order of magnitude or more, or a large % of the total row count), that key is a skew risk for any join or aggregation on it.

```python
# Manual skew check before running a big join/groupBy
df.groupBy("customer_id").count() \
  .orderBy(F.desc("count")) \
  .show(10)

# +------------+-------+
# |customer_id |count  |
# +------------+-------+
# |NULL        |702145 |   <- dominant key, classic skew signal
# |C00931      |1042   |
# |C00456      |988    |
# |C00120      |975    |
# +------------+-------+
```

**Simulation:** `df.groupBy(key).count().orderBy(desc)`, using a synthetic distribution where "NULL" makes up 7000 of the rows and everything else is spread thinly across ~300 customer ids.

```python
from collections import Counter
import random

random.seed(7)
rows = ["NULL"] * 7000 + [f"C{n:03d}" for n in range(1, 300) for _ in range(random.randint(1, 5))]
random.shuffle(rows)

counts = Counter(rows)
top = counts.most_common(5)
total = sum(counts.values())
print(f"    Total rows: {total}")
for key, cnt in top:
    pct = 100 * cnt / total
    print(f"    {key:<10} count={cnt:<6} ({pct:.1f}% of all rows)")
```

**Output:**

```text
    Total rows: 7898
    NULL       count=7000   (88.6% of all rows)
    C233       count=5      (0.1% of all rows)
    C232       count=5      (0.1% of all rows)
    C094       count=5      (0.1% of all rows)
    C090       count=5      (0.1% of all rows)
```

NULL alone accounts for nearly 89% of all rows here — a textbook skew signal. Every other key contributes at most a handful of rows (1-5 each, from the random per-key repeat count), so any join or `groupBy` on this column will pile almost 7,000 rows into whatever single partition NULL happens to hash to, while every other partition sits nearly empty.

---

## 5. Simulating skewed task times

This simulates a groupBy/join shuffle where one key holds 70% of the rows, and translates partition row-counts into approximate task durations to make the imbalance concrete (as you'd see it in the Spark UI).

```python
total_rows = 1_000_000
num_partitions = 4

# Key "CUST_HOT" makes up 70% of rows and all hash to partition 0.
# The rest of the keys are spread evenly across all 4 partitions.
hot_key_rows = int(total_rows * 0.70)
remaining_rows = total_rows - hot_key_rows

partition_rows = {0: hot_key_rows}
for p in range(num_partitions):
    partition_rows[p] = partition_rows.get(p, 0) + remaining_rows // num_partitions

print("  Simulated shuffle partition sizes (1 key = 70% of all rows):")
time_per_million_rows_sec = 12.0  # simulated processing rate per task
task_times = {}
for p in range(num_partitions):
    rows = partition_rows[p]
    task_time = (rows / 1_000_000) * time_per_million_rows_sec
    task_times[p] = task_time
    bar = "#" * int(rows / 10_000)
    print(f"    Partition {p}: {rows:>7} rows  [{bar}]  ~{task_time:.1f}s")

median_time = sorted(task_times.values())[len(task_times) // 2]
max_time = max(task_times.values())
slowdown = max_time / median_time if median_time else float("inf")

print(f"\n  Median task time: {median_time:.1f}s")
print(f"  Max task time:    {max_time:.1f}s")
print(f"  Slowdown factor:  {slowdown:.1f}x  (stage must wait for the slowest task)")
```

**Output:**

```text
  Simulated shuffle partition sizes (1 key = 70% of all rows):
    Partition 0:  775000 rows  [#############################################################################]  ~9.3s
    Partition 1:   75000 rows  [#######]  ~0.9s
    Partition 2:   75000 rows  [#######]  ~0.9s
    Partition 3:   75000 rows  [#######]  ~0.9s

  Median task time: 0.9s
  Max task time:    9.3s
  Slowdown factor:  10.3x  (stage must wait for the slowest task)
```

Note that partition 0 ends up with 775,000 rows rather than exactly 700,000: the code seeds `partition_rows[0]` with the hot key's 700,000 rows, then the loop over all four partitions *adds* an even share of the remaining 300,000 rows (75,000) to every partition **including partition 0** — so the hot partition ends up with both the hot key's rows and its even share of the rest. The other three partitions get only their 75,000-row share. The result: one task takes over 9 seconds while the other three finish in under a second, a slowdown of roughly 10x — and the stage as a whole cannot finish until that one slow task completes.

---

## Key Takeaways

- Data skew is an UNEVEN distribution of rows per key/partition after a hash-based shuffle — hashing balances the key space, not row counts.
- Symptoms in the Spark UI: one task's duration/shuffle-read is orders of magnitude above the median, jobs "hang" near 100% completion, and the skewed executor shows high GC time or disk spill.
- Common causes: skewed/low-cardinality join keys, groupBy hotspots (bots, power users), NULL/placeholder overload, and lopsided date-based partitioning (e.g. a sale day).
- Detect it proactively with `df.groupBy(key).count().orderBy(desc())` before running an expensive join or aggregation on that key.
- A single oversized partition forces the whole stage to wait for one task — adding more executors does not help if the work isn't split.
- Skew is a prerequisite concept for the fixes in the next two files: manual salting and Spark's automatic AQE skew join optimization.
