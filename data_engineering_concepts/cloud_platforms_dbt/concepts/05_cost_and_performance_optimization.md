# Concept 05: Cost & Performance Optimization in Cloud Warehouses

**Covers:**
- Why "the warehouse bill is too high" is a real, frequently-asked interview question, and how to structure an answer
- Clustering keys and partition pruning — reducing bytes scanned, the single biggest lever in a per-byte-priced warehouse
- Warehouse sizing, auto-suspend, and auto-resume — reducing idle compute cost
- Query result caching — paying for a query's compute exactly once
- dbt-specific levers: incremental models, model selection, and materialization choice as cost decisions, not just correctness decisions
- A worked cost-diagnosis walkthrough, tying every lever above into one decision tree

This file exists because none of the source concepts above cover cost optimization with real interview depth on their own — "the warehouse bill is too high, what do you do" deserves its own file, because a strong answer requires reasoning across *all* of concepts 01–04 at once, not recalling one fact. For the underlying storage-layout concepts (partitioning schemes, small-file problems, file formats) this file assumes, see `data_warehousing_lakes/concepts/02_partitioning_and_bucketing.md` and `concepts/03_file_and_table_formats.md`.

---

## 1. The Two Cost Axes: Bytes Scanned, and Compute-Time Idle

Every cloud warehouse bills along one or both of two axes, and almost every optimization technique reduces one of them:

```
Axis 1: BYTES SCANNED           Axis 2: COMPUTE TIME (running, whether busy or idle)
(BigQuery on-demand,             (Snowflake credits, Redshift node-hours,
 any per-TB-scanned pricing)      BigQuery flat-rate slots)

Levers: partition pruning,        Levers: warehouse sizing, auto-suspend,
        clustering, column        auto-resume, query result caching,
        pruning (SELECT only      concurrency scaling instead of a
        needed columns)           permanently oversized cluster
```

A strong answer to "the bill is too high" starts by identifying *which* axis is actually driving the cost — a BigQuery on-demand bill is almost always a bytes-scanned problem; a Snowflake or Redshift bill is almost always an idle-compute-time problem — because the fix looks completely different depending on which one it is.

---

## 2. Reducing Bytes Scanned: Partition Pruning and Clustering

**Partition pruning** means the warehouse skips reading entire partitions (typically date-based directories or micro-partition ranges) that can't contain matching rows, based on the query's `WHERE` filter.

```python
import sqlite3, random
from datetime import datetime, timedelta

conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, revenue REAL, sale_date TEXT, partition_month TEXT)")
random.seed(1)
base = datetime(2023, 1, 1)
for i in range(1, 50001):
    d = base + timedelta(days=random.randint(0, 729))  # 2 years of data
    cur.execute("INSERT INTO sales VALUES (?, ?, ?, ?)",
                (i, round(random.uniform(10, 500), 2), d.strftime("%Y-%m-%d"), d.strftime("%Y-%m")))
conn.commit()

cur.execute("SELECT COUNT(*) FROM sales")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sales WHERE partition_month = '2024-06'")
one_month = cur.fetchone()[0]
print(f"No partition filter: {total:,} rows scanned (2 years of history)")
print(f"Filtered to one month: {one_month:,} rows scanned")
print(f"Reduction: {(1 - one_month/total)*100:.1f}%")
```

```
No partition filter: 50,000 rows scanned (2 years of history)
Filtered to one month: 2,123 rows scanned
Reduction: 95.8%
```

The single most common way pruning silently fails: the query filters on a *derived* expression instead of the raw partition column.

```sql
-- BAD: wrapping the partitioned column in a function usually defeats pruning --
-- the warehouse can't prove which partitions EXTRACT(YEAR FROM sale_date) = 2024
-- could possibly match without evaluating the function on every row first.
SELECT SUM(revenue) FROM sales WHERE EXTRACT(YEAR FROM sale_date) = 2024;

-- GOOD: filter on the literal partition column/range directly.
SELECT SUM(revenue) FROM sales WHERE sale_date BETWEEN '2024-01-01' AND '2024-12-31';
```

**Clustering** (BigQuery `CLUSTER BY`, Redshift `SORTKEY`, Snowflake's automatic micro-partitioning plus optional explicit `CLUSTER BY`) sorts data *within* whatever partitions exist, so a filter on the clustering column can skip blocks even without a partition filter present:

```sql
CREATE TABLE `project.dataset.sales`
PARTITION BY DATE(sale_date)
CLUSTER BY region, customer_id
AS SELECT * FROM `project.dataset.raw_sales`;
```

The interview tell here is choosing the clustering column from **actual query patterns**, not guesswork — cluster on the column(s) most frequently filtered *within* a partition, and skip a column that's rarely filtered or very low-cardinality (e.g. a three-value status flag narrows almost nothing).

**Column pruning** is the simplest lever of all and the one most often forgotten: `SELECT *` in a columnar warehouse reads every column's data off disk even if only three are used downstream — always project only the columns actually needed, especially in a staging model that many other models will `ref()`.

---

## 3. Reducing Idle Compute: Warehouse Sizing and Auto-Suspend

A warehouse that's **running but idle** is the most common silent cost leak in Snowflake/Redshift-style architectures — compute is billed by time running, not by work actually done, so a warehouse left on between queries burns credits doing nothing.

```python
class Warehouse:
    def __init__(self, size="MEDIUM", auto_suspend_sec=300):
        self.size = size
        self.auto_suspend_sec = auto_suspend_sec
        self.state = "SUSPENDED"
        self.idle_seconds = 0
        self.credits_used = 0.0

    def tick(self, seconds, query_running):
        if query_running:
            self.state = "RUNNING"
            self.idle_seconds = 0
        elif self.state == "RUNNING":
            self.idle_seconds += seconds
            if self.idle_seconds >= self.auto_suspend_sec:
                self.state = "SUSPENDED"
                print(f"  auto-suspended after {self.idle_seconds}s idle -- credits stop accruing")
        if self.state == "RUNNING":
            self.credits_used += seconds / 3600 * {"XSMALL": 1, "MEDIUM": 4, "LARGE": 8}[self.size]

wh = Warehouse(size="LARGE", auto_suspend_sec=300)
wh.tick(60, query_running=True)      # a query runs for a minute
wh.tick(600, query_running=False)    # then nothing happens for 10 minutes
print(f"credits used: {wh.credits_used:.4f}, final state: {wh.state}")
```

```
  auto-suspended after 600s idle -- credits stop accruing
credits used: 0.1333, final state: SUSPENDED
```

This simulation ticks in coarse 60/600-second increments, so it only checks the auto-suspend threshold once per `tick()` call rather than continuously — in a real warehouse the suspend would trigger the moment 300 idle seconds actually elapse, not only when the next tick happens to be evaluated. The point still holds: without `AUTO_SUSPEND` at all, that same warehouse would have kept accruing credits for the full 11 minutes of this example instead of stopping once it went idle — the gap between "auto-suspend configured" and "not configured" scales linearly with how long a warehouse sits idle between business hours, which in practice is most of the day for a warehouse dedicated to ad-hoc analyst queries.

```sql
CREATE WAREHOUSE analytics_wh WITH
    WAREHOUSE_SIZE = 'MEDIUM'
    AUTO_SUSPEND = 60          -- suspend after 60 seconds idle (aggressive, good default)
    AUTO_RESUME = TRUE;        -- instantly resumes on the next query, transparent to the user
```

**Right-sizing** is the other half: doubling warehouse size doubles cost-per-second but doesn't necessarily halve query time — many queries are I/O- or latency-bound, not compute-bound, and oversizing a warehouse for a workload that was never actually queueing just multiplies the cost of every query that runs on it. The concrete diagnostic: check `INFORMATION_SCHEMA.WAREHOUSE_LOAD_HISTORY` (Snowflake) or the query execution/queueing metadata (BigQuery `INFORMATION_SCHEMA.JOBS`) — if queries aren't queueing waiting for compute, a bigger warehouse is pure waste; if they are, it's the correct fix.

---

## 4. Query Result Caching

If the exact same query runs again against unchanged underlying data, the warehouse can return the previously computed result at effectively zero compute cost — Snowflake's result cache persists 24 hours; BigQuery similarly caches recent identical query results, both invalidated the moment the source data changes.

```python
result_cache = {}
def cached_query(cur, sql, label):
    if sql in result_cache:
        print(f"[{label}] CACHE HIT -- zero compute cost")
        return result_cache[sql]
    cur.execute(sql)
    result_cache[sql] = cur.fetchall()
    print(f"[{label}] CACHE MISS -- full compute cost incurred")
    return result_cache[sql]
```

```
[Run 1] CACHE MISS -- full compute cost incurred
[Run 2] CACHE HIT -- zero compute cost
```

This is why a dashboard refreshed by many users hitting an identical query (not parameterized per-user) is dramatically cheaper than the same dashboard issuing a slightly different query per viewer — a `WHERE user_id = ?` clause with a different literal per user defeats the cache entirely, even if the query is otherwise identical.

---

## 5. dbt-Specific Cost Levers

Every materialization decision from `03_dbt_fundamentals_and_dag.md` is *also* a cost decision, not just a correctness one:

- **Incremental over table** for any large, append-heavy fact table — a `table` materialization re-scans and re-computes the *entire* source every single run; an `incremental` model with a correct `is_incremental()` filter only touches what actually changed. For a fact table with years of history and a small daily delta, this is frequently a 10-100x reduction in bytes processed per run.
- **`dbt run --select`** to avoid rebuilding the whole DAG when only a subtree changed — `dbt run --select stg_orders+` rebuilds only the changed model and its downstream dependents, not the entire project, which matters a great deal once a project has hundreds of models.
- **Ephemeral vs. view vs. table**, chosen deliberately rather than by habit — an ephemeral model inlined into five downstream models multiplies its own compute cost by five every time those five run; if it's genuinely reused often and isn't trivial, materializing it as a `view` (or `table`, if heavy) computes it once instead.
- **Test selectively in CI, fully in prod** — running the full `dbt build` test suite against a full-size warehouse on every single pull request is often unnecessary; many teams run a smaller/sampled dataset or a subset of tests in CI and reserve the full build for the scheduled production run.

---

## 6. Worked Diagnosis: "The Warehouse Bill Tripled This Quarter"

A strong interview answer walks this decision tree out loud rather than guessing at one fix:

1. **Which axis moved?** Check the billing breakdown — is it bytes scanned (BigQuery on-demand) or compute-hours (Snowflake credits, Redshift node-hours)? This determines which half of this file even applies.
2. **If bytes scanned:** pull the heaviest queries from query history. Are they filtering on a partitioned column, or on a derived expression that defeats pruning? Is a frequently-run query doing `SELECT *` where three columns would do? Did a table recently lose its clustering (e.g. a full rewrite without re-specifying `CLUSTER BY`)?
3. **If compute-hours:** check warehouse utilization history. Is a warehouse sized for peak load running 24/7 with mostly idle time (missing or too-long `AUTO_SUSPEND`)? Did a new dashboard get built issuing high-cardinality parameterized queries that never hit the result cache? Did a dbt model get switched from `incremental` to `table` (intentionally or by a config error), turning a small daily delta into a full rebuild every run?
4. **Check what changed, not just what's expensive** — a bill tripling in a quarter usually has a specific triggering change (a new table without partitioning, a dbt model's materialization flipped, a warehouse's `AUTO_SUSPEND` removed during a migration) rather than gradual organic drift. Query history and `dbt run` logs both have timestamps; correlate the cost inflection point against them before proposing a fix.
5. **Fix the specific cause, then add a monitor** — a resource monitor (Snowflake), budget alert (BigQuery/GCP), or scheduled query-cost report catches the *next* regression before it compounds for a full billing cycle.

Naming this as a structured diagnosis — "which axis, which query/warehouse, what changed, fix plus a monitor" — rather than reciting a list of tips is what separates a strong answer from a memorized checklist.

---

## Key Takeaways

- Cloud warehouse cost breaks into two axes — bytes scanned and idle compute time — and the fix for one does almost nothing for the other, so the first diagnostic step is always identifying which axis is actually driving the bill.
- Partition pruning and clustering reduce bytes scanned; both are silently defeated by filtering on a derived/wrapped expression instead of the raw partitioned/clustered column.
- Auto-suspend (and correct warehouse sizing, verified against actual queueing, not guessed) reduces idle compute cost — the most common Snowflake/Redshift cost leak is a warehouse running with nothing to do.
- Result caching makes a repeated identical query free, but only if it's genuinely identical — a per-user literal in the `WHERE` clause defeats it.
- In a dbt project specifically, `incremental` vs. `table`, `--select` scoping, and ephemeral/view/table choice are cost decisions as much as correctness ones — a materialization flipped from `incremental` to `table` is one of the most common single causes of a sudden warehouse-bill spike.
- "The bill is too high" answers best as a decision tree — which axis, which query or warehouse, what changed recently, fix the specific cause, then add a monitor — not as a list of unconnected tips.
