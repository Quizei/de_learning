# Concept 02: Partitioning & Bucketing

**Covers:**
- Why partition at all — partition pruning, shown concretely
- Partition strategies: by date, by a low-cardinality dimension, composite, hash
- Partition pruning simulated on an actual directory structure, the way Hive/Spark/Athena/BigQuery see it
- Bucketing (clustering) — hash-distributing rows so joins don't need a shuffle
- Over-partitioning: the small-file problem from the layout side, and how to size partitions correctly

*All Python below is real, runnable stdlib code — no external dependencies. It simulates what a warehouse/lake engine does physically; the mechanics (directory listing, footer stats, file splitting) map directly onto how Hive-style partitioning and cloud warehouse clustering actually work.*

---

## 1. Why Partition? Skip Data Before You Ever Read It

Partitioning is a **physical storage decision**: rows are grouped into separate files/directories by the value of one or more columns, so a query that filters on that column can skip entire partitions without opening them. This is distinct from an index (which still has to consult and read *something* per matching row) — a pruned partition is never touched at all, not even its metadata, once the query planner has decided it can't contain a match.

```text
Table: sales/
├── month=2025-01/   <- query WHERE month = '2025-01' reads ONLY this
├── month=2025-02/
├── month=2025-03/
...
└── month=2025-12/   <- everything else: skipped entirely, never opened
```

```python
import random, time

random.seed(42)
months = [f"2025-{m:02d}" for m in range(1, 13)]
data = [{"month": random.choice(months), "region": random.choice(["US","EU","APAC"]),
         "revenue": round(random.uniform(10, 1000), 2)} for _ in range(100_000)]

# Without partitioning: the query has no choice but a full scan
jan_total_full = sum(r["revenue"] for r in data if r["month"] == "2025-01")
rows_scanned_full = len(data)

# With partitioning: physically grouped by month first
partitions = {}
for r in data:
    partitions.setdefault(r["month"], []).append(r)

jan_partition = partitions["2025-01"]
jan_total_part = sum(r["revenue"] for r in jan_partition)
rows_scanned_part = len(jan_partition)

print(f"Full scan:    {rows_scanned_full:,} rows read")
print(f"Partitioned:  {rows_scanned_part:,} rows read "
      f"({rows_scanned_part/rows_scanned_full:.1%} of total)")
print(f"Partitions skipped: {len(partitions) - 1} of {len(partitions)}")
```

**Output:**
```text
Full scan:    100,000 rows read
Partitioned:  8,357 rows read (8.4% of total)
Partitions skipped: 11 of 12
```

The business case in one sentence: a 10 TB table partitioned by date lets "last 7 days" scan roughly 70 GB instead of 10 TB — and in a decoupled-compute world (`concepts/01_warehouse_architecture.md`, section 4), every gigabyte *not* scanned is both real latency and real dollars saved.

---

## 2. Partition Strategies

**By date/time** is the overwhelming default, because almost every analytical query filters by a date range somewhere. **By a low-cardinality dimension** (region, tenant, status) works when queries reliably filter on it and the number of distinct values stays small. **Composite** (date + region) narrows further, at the cost of more, smaller partitions. **Hash-based** partitioning is a fallback for when there's no natural filtering key but you still want even distribution across nodes/files.

```python
data = [{"month": random.choice(months), "region": random.choice(["US","EU","APAC"]),
         "revenue": round(random.uniform(10, 1000), 2)} for _ in range(100_000)]

by_month = {}
for r in data:
    by_month.setdefault(r["month"], []).append(r)

by_composite = {}
for r in data:
    by_composite.setdefault(f"{r['month']}/{r['region']}", []).append(r)

print(f"By month:            {len(by_month)} partitions, "
      f"~{len(data)//len(by_month):,} rows each")
print(f"By month + region:   {len(by_composite)} partitions, "
      f"~{len(data)//len(by_composite):,} rows each")
```

**Output:**
```text
By month:            12 partitions, ~8,333 rows each
By month + region:   36 partitions, ~2,777 rows each
```

Composite partitioning cuts scanned data further *if* queries actually filter on both columns — but every extra partitioning column multiplies the partition count, which is exactly the trade-off that turns into over-partitioning in section 5.

---

## 3. Partition Pruning as the Engine Actually Sees It

In a Hive-style lake table (and this is exactly what Spark, Athena, Presto/Trino, and BigQuery's external tables do), partitions are literal directories, encoded as `key=value` path segments:

```text
s3://bucket/sales/year=2025/month=01/data.parquet
s3://bucket/sales/year=2025/month=02/data.parquet
s3://bucket/sales/year=2024/month=12/data.parquet
```

The query planner reads the partition *listing* (cheap — metadata only), compares each partition's key values against the query's `WHERE` clause, and never opens the file for a partition that can't match.

```python
import os, json, tempfile, shutil

base_dir = tempfile.mkdtemp(prefix="lake_sim_")
try:
    for year in [2024, 2025]:
        for month in range(1, 13):
            part_dir = os.path.join(base_dir, f"year={year}", f"month={month:02d}")
            os.makedirs(part_dir, exist_ok=True)
            with open(os.path.join(part_dir, "data.json"), "w") as f:
                json.dump([{"revenue": 100} for _ in range(200)], f)

    query_year, query_months = 2025, {1, 2, 3}
    scanned, pruned, records_read = 0, 0, 0
    for year in [2024, 2025]:
        for month in range(1, 13):
            if year != query_year or month not in query_months:
                pruned += 1
                continue  # PRUNED -- directory never opened
            scanned += 1
            path = os.path.join(base_dir, f"year={year}", f"month={month:02d}", "data.json")
            with open(path) as f:
                records_read += len(json.load(f))

    print(f"Partitions scanned: {scanned}   pruned: {pruned}")
    print(f"Records read: {records_read:,}")
finally:
    shutil.rmtree(base_dir, ignore_errors=True)
```

**Output:**
```text
Partitions scanned: 3   pruned: 21
Records read: 600
```

The interview-relevant detail: pruning happens **before any data file is opened**, purely from the partition path/listing — this is a coarser, cheaper cousin of the row-group statistics pruning covered in `concepts/04_file_and_table_formats.md` (Parquet footer min/max stats), which prunes *within* a file rather than at the directory level. A well-laid-out table gets both: partition pruning eliminates whole directories, then footer-stat pruning eliminates row groups within whatever files are left.

---

## 4. Bucketing: Hash Distribution for Join Optimization

Partitioning organizes data for *filtering*. **Bucketing** (clustering) organizes data for *joining*: rows are hashed on a key (typically a join key like `customer_id`) into a fixed number of buckets, so rows sharing a key always land in the same bucket — on the same node, in the same file. If two tables are bucketed the same way on the same key, a join only ever needs to compare bucket-to-matching-bucket, never every row against every row, and a distributed engine can skip the expensive shuffle it would otherwise need to co-locate matching keys.

```python
random.seed(42)
num_buckets = 4
customers = [{"customer_id": i, "city": random.choice(["NYC","LA","CHI"])} for i in range(1, 21)]
orders = [{"order_id": i, "customer_id": random.randint(1, 20)} for i in range(1, 101)]

def bucket_key(customer_id):
    return customer_id % num_buckets

customer_buckets = {b: [] for b in range(num_buckets)}
order_buckets = {b: [] for b in range(num_buckets)}
for c in customers:
    customer_buckets[bucket_key(c["customer_id"])].append(c)
for o in orders:
    order_buckets[bucket_key(o["customer_id"])].append(o)

# Bucketed join: only compare within each bucket -- no cross-bucket shuffle needed
total_comparisons = sum(len(customer_buckets[b]) * len(order_buckets[b]) for b in range(num_buckets))
naive_comparisons = len(customers) * len(orders)

print(f"Bucketed comparisons: {total_comparisons:,}")
print(f"Naive cross-join:     {naive_comparisons:,}")
print(f"Reduction: {1 - total_comparisons/naive_comparisons:.0%}")
```

**Output:**
```text
Bucketed comparisons: 500
Naive cross-join:     2,000
Reduction: 75%
```

The interview tell here: bucketing and partitioning solve *different* problems and are frequently combined — partition a fact table by date (so date-range queries prune directories), then bucket *within* each date partition by the column most frequently joined on (so joins against a dimension table don't need a full shuffle). Choosing which column to bucket on is an access-pattern question, not a guess: bucket on the highest-cardinality column that's actually used in `JOIN` conditions, not a low-cardinality status flag that wouldn't spread rows evenly.

---

## 5. Over-Partitioning: When Finer-Grained Becomes Worse, Not Better

Partitioning has a cost that's easy to ignore until it isn't: every partition is at minimum one file, one directory-listing entry, and (in Hive-style systems) one row in the metastore. Partition too finely and the *fixed cost per partition* — metadata lookups, file-open overhead, query-planning time to enumerate every candidate partition — starts to dominate the actual work being done. This is the storage-layout twin of the small-file problem covered from the read-task-scheduling angle in `spark_course/concepts/15_file_formats_columnar_storage.md`, section 5 — that file shows why thousands of tiny files punish a *read* job's task scheduling; this section shows why the *partitioning scheme itself* is usually the root cause of those tiny files in the first place.

```python
total_data_mb = 10_000  # 10 GB total table size
scenarios = [
    ("By year",                   5),
    ("By year/month",            60),
    ("By year/month/day",      1825),
    ("By year/month/day/hour", 43800),
    ("By customer_id (100K customers)", 100_000),
]
for strategy, num_parts in scenarios:
    avg_mb = total_data_mb / num_parts
    if avg_mb >= 128:
        status = "GOOD"
    elif avg_mb >= 10:
        status = "watch it"
    elif avg_mb >= 1:
        status = "WARNING: small files"
    else:
        status = "BAD: tiny files"
    print(f"{strategy:<34} {num_parts:>8,} partitions  {avg_mb:>9.2f} MB avg  [{status}]")
```

**Output:**
```text
By year                                  5 partitions   2000.00 MB avg  [GOOD]
By year/month                           60 partitions    166.67 MB avg  [GOOD]
By year/month/day                     1825 partitions      5.48 MB avg  [WARNING: small files]
By year/month/day/hour               43800 partitions      0.23 MB avg  [BAD: tiny files]
By customer_id (100K customers)     100000 partitions      0.10 MB avg  [BAD: tiny files]
```

**Guidelines that hold across Hive, Spark, Athena, Snowflake, and BigQuery alike:**
- Target partitions in the 128 MB – 1 GB range; below ~10 MB, per-partition overhead starts to dominate.
- Partition on columns actually used in `WHERE` clauses — date is the near-universal default; never partition on a high-cardinality column like `customer_id` or `order_id` directly (bucket on it instead).
- If a natural partition key is too fine-grained (hourly, per-customer), either coarsen the partition grain (daily instead of hourly) or move that column to bucketing, which distributes without multiplying directory/metadata count.
- Periodic compaction jobs can merge many small partition files into fewer, larger ones after the fact — a mitigation, not a substitute for choosing the right grain up front.

---

## Key Takeaways

- Partitioning physically groups rows by a column's value so a query can skip whole partitions (files/directories) it can't match — partition pruning happens at the metadata/listing level, before any data file is opened.
- Date is the default partition key because most analytical queries filter by date; composite and hash strategies exist for other access patterns, at the cost of more (smaller) partitions.
- Bucketing hash-distributes rows by a join key into a fixed number of buckets so joins on that key avoid a full shuffle — it solves a different problem than partitioning (join co-location vs. filter pruning) and the two are commonly combined.
- Over-partitioning (too many, too-small partitions) makes per-partition fixed overhead dominate actual work — target 128 MB–1 GB per partition, and use bucketing instead of partitioning for high-cardinality join keys.
- Partition pruning (directory-level) and footer-statistics pruning (row-group-level, inside a single file) are complementary; the second is covered in `concepts/04_file_and_table_formats.md`.
