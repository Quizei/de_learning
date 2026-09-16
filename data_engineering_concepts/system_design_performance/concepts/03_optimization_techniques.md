# Concept 3: Optimization Techniques for Data Pipelines

**Covers:**
- Query optimization: predicate pushdown, partition pruning, column pruning
- Indexing strategies and their write-side cost
- Caching strategies: result cache, materialized views, pre-aggregation
- Compression trade-offs (Snappy/LZ4 vs. Gzip vs. Zstd)
- Data skew handling (the system-design-level version)
- The small-file problem and compaction

*This file generalizes optimization principles across warehouses and engines. `../../spark_course/` covers the Spark-specific mechanics (shuffle partitions, AQE, broadcast joins) in much more depth — read this file for the vocabulary that transfers to Snowflake/BigQuery/Redshift/any engine, and that file for Spark internals specifically.*

---

## 1. Query Optimization: Pushdown and Pruning

Three techniques that all share one idea: **do less work by deciding what to skip as early as possible**, ideally before data is even read off disk.

- **Predicate pushdown** — apply filters at the storage/scan layer instead of loading everything and filtering in application code. `WHERE product_category = 'electronics'` evaluated by the storage engine reads only matching rows; the same filter applied in Python after `SELECT *` reads and discards everything else first.
- **Partition pruning** — skip entire partitions (files/directories) that can't match the filter, based on partition metadata alone, without opening the files.
- **Column pruning** — read only the columns a query actually needs. Trivial in a row store (you read the row either way) but a major win in a columnar format (Parquet/ORC), where unread columns are genuinely never touched on disk.

```sql
-- Bad: full scan, filter happens after every row is already read
SELECT * FROM orders;   -- then filter in application code

-- Good: pushdown + column pruning in one query
SELECT id, amount FROM orders
WHERE product_category = 'electronics' AND amount > 100;
```

**Worked comparison** (50,000-row table, realistic magnitudes for this class of fix):
```text
Full scan + Python-side filter:      ~45 ms
Predicate pushed into SQL:           ~4 ms      (~11x faster)
SELECT * (all columns):              baseline
SELECT id, amount only:              measurably faster, more so on a columnar store
```

Read the actual query plan rather than assuming pushdown happened — `EXPLAIN` (any engine) shows whether a filter was applied at the scan node or after it:
```text
EXPLAIN SELECT * FROM orders WHERE product_category = 'electronics';
-- SEARCH orders USING INDEX idx_cat_region (product_category=?)   <- pushed down, good
-- SCAN orders                                                     <- full scan, filter applied later, bad
```

---

## 2. Indexing Strategies

Indexes trade write-time and storage cost for read speed — a decision that must be justified per column, not applied blindly everywhere.

```sql
CREATE INDEX idx_cat_region ON orders(product_category, region);   -- composite index
```

**Worked speedup** (100 repeated lookups on a composite-key query, illustrative magnitudes):
```text
No index:          ~38 ms  (full scan, every lookup)
Composite index:    ~2 ms  (~19x faster)
```

Types worth knowing by name:
- **B-tree index** — the default in most RDBMS; good for equality and range lookups.
- **Composite index** — indexes multiple columns together; column ORDER matters (an index on `(category, region)` serves a `WHERE category = ?` query but not efficiently a `WHERE region = ?`-only query).
- **Covering index** — includes every column a query needs, so the engine never has to go back to the base table row at all.

**The cost side, stated explicitly:** every index is maintained on every write — an OLTP table with ten indexes pays that overhead on every INSERT/UPDATE. This is exactly why OLTP schemas index sparingly and OLAP/warehouse tables lean on partitioning/clustering instead of many secondary indexes.

---

## 3. Caching Strategies

Three distinct techniques, often confused for one another:

**Result cache** — store the exact output of a specific query, keyed by the query (+ params). Fastest possible repeat-read, but only helps if the SAME query runs again; a single changed WHERE clause is a cache miss.

```python
class ResultCache:
    def query(self, sql, params=()):
        key = (sql, params)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        result = self._run(sql, params)
        self.cache[key] = result
        return result
```

**Materialized view** — a precomputed, stored result of a query, refreshed on a schedule or incrementally, queryable like a table. Unlike a result cache, OTHER queries can filter/aggregate further on top of it — it isn't tied to one exact query shape.

```sql
CREATE TABLE mv_daily_sales AS
SELECT order_date, product_category, region,
       COUNT(*) AS order_count, SUM(amount) AS total_amount
FROM orders
GROUP BY order_date, product_category, region;
-- Queries against mv_daily_sales run against a table 100-1000x smaller
-- than the raw orders table, at the cost of staleness = refresh interval.
```

**Pre-aggregation** — the same idea, purpose-built for a specific known reporting need (a `summary_monthly` table built specifically for a finance dashboard) rather than a general-purpose rollup.

**Worked comparison** (querying "top categories in June" against raw orders vs. a pre-built materialized view):
```text
Raw table aggregation (GROUP BY over the full table, filtered):   ~9 ms
Materialized view (pre-aggregated, same filter):                  ~0.6 ms
```

**The trade-off to name explicitly:** every cache/materialized view is a staleness bet. State the acceptable staleness window out loud ("this dashboard can be 15 minutes stale") rather than leaving it implicit — an un-stated staleness assumption is how "the dashboard shows the wrong number" tickets happen.

---

## 4. Compression Trade-offs

```text
Algorithm | Speed      | Ratio | CPU cost | Typical use
----------|------------|-------|----------|---------------------------------
Snappy    | Very fast  | Low   | Low      | Hot data, real-time (Kafka)
LZ4       | Very fast  | Low   | Low      | Similar to Snappy
Gzip      | Slow       | High  | High     | Archival, cold storage
Zstd      | Fast       | High  | Medium   | Best balance -- modern default
```

The decision axis is **how often this data is read vs. how much it costs to store**: hot data read constantly favors fast decompression (Snappy/Zstd) even at a worse ratio, since CPU spent decompressing on every read adds up; cold archival data favors maximum ratio (Gzip) since it's rarely read and storage cost dominates. Parquet + Snappy is the default pairing for analytics specifically because analytical scans decompress constantly — CPU-cheap decompression matters more than shaving another 10% off file size.

**Worked comparison** (illustrative, compressing three data shapes with zlib at low vs. high compression levels):
```text
High-repetition data (log lines):   fast level: ~85% smaller;  slow level: ~91% smaller, ~6x slower
Mixed CSV-like data:                 fast level: ~60% smaller;  slow level: ~68% smaller, ~4x slower
Random data (UUIDs):                 fast level: ~2% smaller;   slow level: ~3% smaller,  no real benefit
```
The random-data row is the important one: compression buys almost nothing on high-entropy data (UUIDs, hashes, already-compressed blobs) no matter the algorithm — don't spend CPU compressing what won't compress.

---

## 5. Data Skew, at System-Design Grain

(Spark-specific salting mechanics live in `../../spark_course/concepts/07_data_skew.md` and `08_salting.md` — this is the same idea at the level a system-design interview asks it: as a partitioning/sharding property, not a Spark tuning knob.)

Any system that partitions work by key — a shuffle, a shard, a Kafka partition-by-key — inherits that key's real-world distribution. If 1% of user IDs generate 80% of events (a very common real distribution — a handful of power users or automated accounts), naive `key % num_partitions` sends a hugely disproportionate share of work to whichever partition holds that 1%.

```text
Naive partitioning by user_id % 4, with 80% of events from 1% of users:
    Partition 0: 1,847 events
    Partition 1: 6,203 events   <- happens to catch a hot user, way overloaded
    Partition 2: 1,921 events
    Partition 3: 2,029 events
```

**The fix, generalized beyond Spark:** salt the hot key — append a random suffix (`user_42_salt7`) so ONE hot key's load spreads across N sub-partitions instead of landing on one. This applies identically to a Kafka producer partitioning by key, a sharded database's hot shard, or a Spark shuffle.

```python
salted_key = f"{user_id}_salt{random.randint(0, SALT_BUCKETS - 1)}" if user_id in hot_keys else str(user_id)
partition = hash(salted_key) % num_partitions
```

**Say the pre-requisite out loud:** you must first know which keys are hot (a monitoring/profiling step) before deciding whether to salt everything (wasteful for the 99% of keys that aren't skewed) or only the known hot keys (the usual production choice).

---

## 6. Small-File Problem and Compaction

Thousands of tiny files impose fixed per-file overhead (open/close, metadata lookup, scheduling a task to read it) that dominates over the trivial amount of actual data in each one — the data-lake equivalent of the "200 shuffle partitions on a 500MB job" problem.

```text
Before compaction: 500 files, ~2 records/file average   <- overhead-dominated
After compaction:    28 files, ~36 records/file average  <- one file per date partition
File count reduction: ~18x fewer files to open per query
```

**Root causes worth naming in an interview:** streaming jobs that flush small batches too frequently, over-partitioned writes (partitioning by a column with too many distinct values, or partitioning AND bucketing so finely that each cell holds almost nothing), and many small upstream writers landing files independently without a compaction step downstream.

**Fix:** periodic compaction — a scheduled job (or a lakehouse feature like Delta Lake's `OPTIMIZE` / Iceberg's rewrite-files action) that merges small files within a partition into a few well-sized ones. This is a write-time cost traded for read-time speed, the same shape of trade-off as bucketing in `../../spark_course/concepts/06_bucketing.md`.

---

## Optimization Checklist

```text
Query level:      push predicates down; prune partitions and columns; avoid SELECT *
Storage level:     columnar format for analytics; right-sized compression; compact
                    small files; partition by commonly-filtered columns
Caching level:     cache expensive aggregations; materialize dashboard queries;
                    pre-aggregate common roll-ups
Distribution level: watch for and salt hot keys; index frequently-filtered OLTP
                    columns; monitor partition size distribution, not just averages
```

---

## Key Takeaways

- Pushdown, partition pruning, and column pruning all reduce work by deciding what to skip BEFORE reading it — verify with the actual query plan, don't assume the optimizer did it.
- Indexes trade write-time cost for read speed — justify each one; OLTP tables index sparingly, OLAP tables lean on partitioning/clustering instead.
- Result caches, materialized views, and pre-aggregation are three different tools solving different repeat-query shapes — every one of them is a staleness bet, and the staleness window should be stated explicitly.
- Compression choice is a speed/ratio/CPU trade-off keyed to how often the data is read — Zstd/Snappy for hot data, Gzip for cold archival, and don't bother compressing high-entropy data at all.
- Data skew at the system-design level is the same problem as Spark data skew — a key's real-world distribution overwhelms one partition/shard — and salting the hot key is the general-purpose fix across any partitioned system.
- The small-file problem is an overhead problem, not a storage-size problem — fix it with scheduled compaction, not by reducing data volume.
