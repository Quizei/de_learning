# Concept 06: Bucketing

**Covers:**
- What bucketing is: `.bucketBy(n, col).sortBy(col)` at write time
- How bucketing pre-shuffles and pre-sorts data by hash of the bucket column
- Why bucketing eliminates shuffle on repeated joins/aggregations
- Requirements for a bucket join to actually skip the shuffle
- The tradeoffs of bucketing (write cost, fixed bucket count)
- Bucketing vs partitioning: different problems, different mechanisms
- Simulation: bucketed join with zero data movement vs a shuffle join

*The PySpark snippets below are educational/conceptual — they describe what really happens against a real Spark session, but the worked examples are simulated in plain Python so you can follow along without a cluster.*

---

## 1. What is bucketing?

Bucketing is a write-time optimization that pre-partitions rows of a table into a FIXED number of files ("buckets") based on the hash of one or more columns, and (optionally) sorts rows within each bucket.

`.bucketBy(numBuckets, "col").sortBy("col")` tells Spark to:

1. Compute `hash(col) % numBuckets` for every row.
2. Write all rows with the same bucket number into the same file (one file per bucket per partition, unless the write is also partitioned by another column).
3. Sort rows within each bucket file by `"col"` (if `sortBy` is used).

This is fundamentally different from an ordinary parquet write, where the number of output files is arbitrary and rows are not organized by any key relationship between two tables.

```python
# ---- Writing a bucketed table ----
(df.write
    .bucketBy(8, "customer_id")     # 8 buckets, hashed on customer_id
    .sortBy("customer_id")          # sort rows within each bucket
    .mode("overwrite")
    .saveAsTable("sales_bucketed")  # MUST be saveAsTable, not .parquet()
)

# Under the hood, for each of the 8 buckets, Spark writes one file
# (per partition of the write job) containing only rows whose
# hash(customer_id) % 8 == bucket_number, sorted by customer_id.
```

```text
Bucketing at write time (numBuckets = 4):

    customer_id  -->  hash(customer_id) % 4  -->  bucket file
    ---------------------------------------------------------
    "C001"       -->  hash=... % 4 = 2        -->  bucket_2.parquet
    "C002"       -->  hash=... % 4 = 0        -->  bucket_0.parquet
    "C003"       -->  hash=... % 4 = 3        -->  bucket_3.parquet
    "C004"       -->  hash=... % 4 = 0        -->  bucket_0.parquet
    ...
```

**Simulation:** bucket assignment via hashing (numBuckets=4), using a simplified stand-in for Spark's internal Murmur3 hash:

```python
def spark_style_hash(value):
    """Simplified stand-in for Spark's internal Murmur3 hash."""
    h = 0
    for ch in str(value):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h

num_buckets = 4
customers = ["C001", "C002", "C003", "C004", "C005", "C006", "C007", "C008"]
buckets = {i: [] for i in range(num_buckets)}
for cust in customers:
    b = spark_style_hash(cust) % num_buckets
    buckets[b].append(cust)

for b, members in buckets.items():
    print(f"    bucket_{b}: {sorted(members)}")
```

**Output** (exact bucket numbers depend on the hash function — this is the real output of the simplified hash above):

```text
    bucket_0: ['C003', 'C007']
    bucket_1: ['C004', 'C008']
    bucket_2: ['C001', 'C005']
    bucket_3: ['C002', 'C006']
```

---

## 2. Why bucketing eliminates shuffle on joins

A standard join between two large tables on a key requires a SHUFFLE: both tables must be repartitioned (Exchange) so that matching keys land on the same executor, then sorted (for a sort-merge join).

If BOTH tables are bucketed the same way on the join column (same number of buckets, same column), Spark already knows:

- bucket *i* of table A contains exactly the rows that could match bucket *i* of table B (same hash function, same bucket count)
- within each bucket, rows are already sorted (if `sortBy` was used)

So Spark can join bucket 0 of A with bucket 0 of B directly, bucket 1 with bucket 1, etc. — with NO Exchange (shuffle) step, and no re-sort if `sortBy` was applied. The physical plan shows no "Exchange" node between the scans and the `SortMergeJoin`.

```text
WITHOUT bucketing:              WITH bucketing (both sides, same n):

Scan orders  Scan customers     Scan orders_bkt   Scan customers_bkt
    |             |             (buckets already   (buckets already
    v             v              aligned & sorted)  aligned & sorted)
Exchange      Exchange                 |                   |
(shuffle!)    (shuffle!)               +---------+---------+
    |             |                             v
    +------+------+                      SortMergeJoin
           v                        (NO Exchange node needed!)
    SortMergeJoin
```

```python
# Both tables written with the same bucketing scheme:
orders.write.bucketBy(8, "customer_id").sortBy("customer_id") \
    .saveAsTable("orders_bucketed")
customers.write.bucketBy(8, "customer_id").sortBy("customer_id") \
    .saveAsTable("customers_bucketed")

result = spark.table("orders_bucketed").join(
    spark.table("customers_bucketed"), "customer_id"
)
result.explain()
# == Physical Plan ==
# *(3) SortMergeJoin [customer_id], [customer_id], Inner
# :- *(1) FileScan parquet orders_bucketed ... (already bucketed & sorted)
# +- *(2) FileScan parquet customers_bucketed ...
# (Note: no Exchange operator between the scans and the join!)
```

A full working simulation of this — bucketed join vs shuffle join — is in section 6 below.

---

## 3. Requirements for a bucket join to skip the shuffle

Bucketing only avoids the shuffle if ALL of these hold:

1. Both tables have the SAME number of buckets (e.g. both 8, not 8 and 16 — Spark cannot line up buckets of different counts).
2. Both tables are bucketed on the SAME column(s) used in the join predicate.
3. Both tables were saved with `saveAsTable` (or `CREATE TABLE ... CLUSTERED BY ...`) so bucketing metadata is stored in the catalog. Writing plain `.parquet()` files with `bucketBy()` silently does NOT register bucket metadata that the planner can use for joins — the `DataFrameWriter` warns that bucketing is only supported for Hive/catalog tables via `saveAsTable`.
4. `spark.sql.sources.bucketing.enabled` is true (default true).

If any of these are violated, Spark falls back to a normal shuffle join — the query still returns correct results, just slower.

Checklist for a shuffle-free bucketed join:

- [PASS] Same bucket count on both tables
- [PASS] Same join column as the bucketing column
- [PASS] Saved via saveAsTable (catalog table)
- [PASS] `spark.sql.sources.bucketing.enabled=true`

Common mistake:

```text
orders.write.bucketBy(8, "customer_id").parquet("/data/orders")
# This writes bucketed FILES but does not persist bucketing
# metadata to the metastore -- a later join will still shuffle,
# because Spark cannot verify the bucketing scheme.
```

Correct:

```text
orders.write.bucketBy(8, "customer_id").saveAsTable("orders_b")
```

**Simulation:** a bucket-count mismatch.

```python
table_a_buckets = 8
table_b_buckets = 16
if table_a_buckets != table_b_buckets:
    print(f"    orders_bucketed has {table_a_buckets} buckets, "
          f"customers_bucketed has {table_b_buckets} buckets")
    print("    -> Bucket join NOT eligible. Falling back to shuffle join.")
```

**Output:**

```text
    orders_bucketed has 8 buckets, customers_bucketed has 16 buckets
    -> Bucket join NOT eligible. Falling back to shuffle join.
```

---

## 4. Tradeoffs of bucketing

Bucketing is not free:

- **Write cost**: producing well-sorted, evenly bucketed output requires a shuffle+sort AT WRITE TIME (moved once, paid once, but still real cost, and often more expensive than an unbucketed write).
- **Fixed bucket count**: you choose `numBuckets` once. As the table grows, buckets grow with it — there is no automatic rebalancing. Too few buckets on a huge table means huge per-bucket files (poor parallelism); too many buckets on a small table means tiny files (small-file problem). Unlike partitioning, you cannot cheaply add "more buckets" later without a full rewrite of the table.
- Bucketing pays off only when the bucketed column is reused across MANY future joins/aggregations — if you bucket and then only query the table once, you paid the write cost for no benefit.

Cost paid ONCE at write time:
- Shuffle to gather rows per bucket
- Sort within each bucket (if `sortBy` used)

Benefit reaped MANY times at read time:
- Every future join/`groupBy` on the bucketed column skips shuffle

Break-even intuition:

```text
write_cost < num_future_queries x shuffle_cost_saved_per_query
```

**Simulation:** finding the break-even point for bucketing.

```python
write_overhead_units = 50       # extra cost to bucket at write time
shuffle_saved_per_query = 12    # cost saved per query by skipping shuffle

for num_queries in [1, 2, 4, 6, 8]:
    total_saved = num_queries * shuffle_saved_per_query
    worth_it = total_saved > write_overhead_units
    print(f"    {num_queries} queries -> total saved = {total_saved} units "
          f"vs write overhead {write_overhead_units} -> "
          f"{'WORTH IT' if worth_it else 'not yet worth it'}")
```

**Output:**

```text
    1 queries -> total saved = 12 units vs write overhead 50 -> not yet worth it
    2 queries -> total saved = 24 units vs write overhead 50 -> not yet worth it
    4 queries -> total saved = 48 units vs write overhead 50 -> not yet worth it
    6 queries -> total saved = 72 units vs write overhead 50 -> WORTH IT
    8 queries -> total saved = 96 units vs write overhead 50 -> WORTH IT
```

---

## 5. Bucketing vs partitioning

Bucketing and partitioning solve DIFFERENT problems and are often used together (partition by date, bucket by customer_id, for example).

**Partitioning:**
- Splits data into separate DIRECTORIES by the value of a column (e.g. `/year=2024/month=01/`).
- Helps at READ time: a filter on the partition column lets Spark skip reading entire directories (partition pruning).
- Number of partitions grows naturally with the data (one more directory per new date, for example) — no rebalancing problem.
- Bad choice for high-cardinality columns (too many tiny directories).

**Bucketing:**
- Splits data into a FIXED number of files by hash of a column, within each partition (or the whole table if unpartitioned).
- Helps at JOIN/AGGREGATE time: avoids shuffling on repeated operations on the bucketed column.
- Works well even for high-cardinality columns like `customer_id`, because the bucket COUNT is fixed regardless of cardinality.

| Aspect | Partitioning | Bucketing |
|---|---|---|
| Mechanism | Separate directories | Hash into N files |
| Helps at | Read time (pruning) | Join/agg time (no shuffle) |
| Good for | Low-cardinality columns | High-cardinality columns |
| Grows with data? | Yes, automatically | No, fixed bucket count |
| Typical column | date, region | customer_id, user_id |

Combined example:

```python
df.write \
  .partitionBy("event_date") \
  .bucketBy(8, "customer_id") \
  .sortBy("customer_id") \
  .saveAsTable("events_optimized")

# Reads filtering on event_date prune directories.
# Joins on customer_id within a date skip the shuffle.
```

---

## 6. Full simulation: bucketed join vs shuffle join

This end-to-end simulation compares a bucketed join (zero data movement) against an ordinary shuffle join (both sides must be exchanged across the "network") for the same logical join.

```python
num_buckets = 4
orders = [(f"C{(i % 9) + 1:03d}", f"O-{100 + i}") for i in range(20)]
customers = [(f"C{c:03d}", f"Name{c}") for c in range(1, 10)]

def bucket_of(key, n):
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % n

# --- Bucketed join path ---
orders_by_bucket = {i: [] for i in range(num_buckets)}
customers_by_bucket = {i: [] for i in range(num_buckets)}
for cust_id, order_id in orders:
    orders_by_bucket[bucket_of(cust_id, num_buckets)].append((cust_id, order_id))
for cust_id, name in customers:
    customers_by_bucket[bucket_of(cust_id, num_buckets)].append((cust_id, name))

bucketed_result = []
network_bytes_bucketed = 0  # each bucket pair joins locally on its executor
for b in range(num_buckets):
    c_lookup = dict(customers_by_bucket[b])
    for cust_id, order_id in orders_by_bucket[b]:
        if cust_id in c_lookup:
            bucketed_result.append((cust_id, order_id, c_lookup[cust_id]))
print(f"    Joined {len(bucketed_result)} rows across {num_buckets} buckets, "
      f"network bytes moved = {network_bytes_bucketed}")

# --- Shuffle join path (no bucketing) ---
# Simulate a shuffle: both sides get re-hashed into spark.sql.shuffle.partitions
shuffle_partitions = 4
shuffled_orders = {i: [] for i in range(shuffle_partitions)}
shuffled_customers = {i: [] for i in range(shuffle_partitions)}
simulated_row_size_bytes = 40
network_bytes_shuffled = 0
for cust_id, order_id in orders:
    p = bucket_of(cust_id, shuffle_partitions)
    shuffled_orders[p].append((cust_id, order_id))
    network_bytes_shuffled += simulated_row_size_bytes  # every row crosses the network
for cust_id, name in customers:
    p = bucket_of(cust_id, shuffle_partitions)
    shuffled_customers[p].append((cust_id, name))
    network_bytes_shuffled += simulated_row_size_bytes

shuffle_result = []
for p in range(shuffle_partitions):
    c_lookup = dict(shuffled_customers[p])
    for cust_id, order_id in shuffled_orders[p]:
        if cust_id in c_lookup:
            shuffle_result.append((cust_id, order_id, c_lookup[cust_id]))
print(f"    Joined {len(shuffle_result)} rows across {shuffle_partitions} partitions, "
      f"network bytes moved = {network_bytes_shuffled}")

print(f"\n  Result correctness check: "
      f"{sorted(bucketed_result) == sorted(shuffle_result)} (both produce the same rows)")
print(f"  Network savings from bucketing: {network_bytes_shuffled} bytes avoided")
```

**Output:**

```text
    Joined 20 rows across 4 buckets, network bytes moved = 0
    Joined 20 rows across 4 partitions, network bytes moved = 1160

  Result correctness check: True (both produce the same rows)
  Network savings from bucketing: 1160 bytes avoided
```

Both paths join the exact same 20 orders against the exact same 9 customers and land on identical result rows — the bucketed path just does it with zero bytes moved across the network, because every matching pair was already co-located in the same bucket at write time, while the shuffle path has to move every single row (40 simulated bytes each, 29 rows total across orders + customers) before it can even start joining.

---

## Key Takeaways

- Bucketing pre-shuffles and pre-sorts data into a fixed number of files by `hash(bucket_column)` at WRITE time via `.bucketBy().sortBy()`.
- If two tables are bucketed identically on the join column, Spark can join matching buckets directly — no Exchange (shuffle) step needed.
- Bucket joins require: same bucket count, same bucketing column(s), and `saveAsTable` (catalog metadata) — plain `.parquet()` writes don't register bucketing for the planner to use.
- Bucketing costs a shuffle+sort at write time; it only pays off when the bucketed column is reused across many future joins/aggregations.
- Fixed bucket count does NOT rebalance as data grows — unlike partitioning, which naturally adds directories as new values appear.
- Partitioning prunes directories at READ time; bucketing avoids shuffle at JOIN/AGGREGATE time — they solve different problems and combine well (e.g. partition by date, bucket by customer_id).
- High-cardinality join keys are a good fit for bucketing but a bad fit for partitioning (too many tiny partitions).
