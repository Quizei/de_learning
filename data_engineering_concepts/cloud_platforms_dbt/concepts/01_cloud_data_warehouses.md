# Concept 01: Cloud Data Warehouse Architecture

**Covers:**
- Why "separate compute from storage" is the one architectural idea that explains almost everything else in this file
- Snowflake, BigQuery, and Redshift compared head-to-head: pricing unit, isolation model, concurrency
- Virtual warehouses / slots / node clusters — the three vendors' names for the same underlying idea
- Time travel and fail-safe — querying and restoring data as it looked in the past
- Materialized views and result caching — paying compute once instead of on every query
- Auto-scaling — handling a burst of concurrent queries without permanently over-provisioning

*All examples below are simulated with Python's `sqlite3` standard library — sqlite has no notion of virtual warehouses, credits, or slots, so each simulation stands in for the real cloud behavior, with the real SQL/DDL shown in comments. Nothing here needs a cloud account to run.*

For the underlying storage concepts these platforms are built on — Parquet/Iceberg/Delta table formats, partitioning and bucketing, OLTP vs. OLAP, MPP query execution — see `data_warehousing_lakes/concepts/01_warehouse_architecture.md` and `concepts/03_file_and_table_formats.md`. This file focuses specifically on what's *platform-specific*: how Snowflake, BigQuery, and Redshift each package compute, pricing, and isolation differently on top of that shared foundation.

---

## 1. Compute/Storage Separation: The Idea Everything Else Follows

Every mainframe-era and early Hadoop-era warehouse coupled compute and storage: to get more query throughput, you bought more disks *and* more CPUs together, whether you needed both or not. The single architectural shift that defines "cloud data warehouse" as a category is decoupling the two: storage lives cheaply and durably in object storage (S3, GCS, or a vendor-managed equivalent), and compute is provisioned, scaled, and billed independently on top of it.

This is why a Snowflake warehouse can be resized from `XSMALL` to `XLARGE` in seconds without touching a single byte of data, and why BigQuery can serve a one-off ad-hoc query without you ever provisioning anything at all — the data was never tied to a fixed cluster to begin with.

```
Coupled (old world):              Decoupled (cloud warehouse):
+-------------------+             +-------------------+     +------------------+
| Disk + CPU + RAM  |             | Compute (elastic)  | <-> | Storage (S3/GCS, |
| one fixed cluster |             | virtual WH / slots |     | cheap, durable)  |
+-------------------+             +-------------------+     +------------------+
scale = buy a bigger box          scale compute and storage independently
```

### The Three Vendors, One Table

| Feature | Snowflake | BigQuery | Redshift |
|---|---|---|---|
| Vendor / cloud | Snowflake Inc. (multi-cloud) | Google Cloud | AWS |
| Architecture | Multi-cluster shared data | Serverless MPP (Dremel engine) | Provisioned MPP (leader + compute nodes) |
| Compute/storage separation | Full (virtual warehouses) | Full (slots) | Full on RA3 nodes; coupled on older DC2 nodes |
| Pricing model | Credits, billed per-second of compute | On-demand (per TB scanned) or flat-rate slots | Per-node-hour (reserved or on-demand) |
| Auto-scaling | Multi-cluster warehouses (up to 10 clusters) | Slots scale automatically, transparently | Concurrency scaling + elastic resize |
| Concurrency | Scales with clusters per virtual warehouse | ~2,000 concurrent queries | ~50 connections by default + concurrency scaling |
| Semi-structured data | `VARIANT` type — native JSON/Avro/Parquet | `STRUCT`/`ARRAY` — native nested/repeated fields | `SUPER` type, PartiQL-style access |
| Time travel | 0–90 days, edition-dependent | 7 days (table snapshots) | No native equivalent — use manual snapshots |
| Partitioning | Automatic micro-partitions | Manual or automatic partitioning by column | Distribution keys + sort keys (manual) |
| Best for | Multi-workload isolation, data sharing, simplicity | GCP-native ad-hoc analytics, serverless, ML | AWS-native shops, heavy ETL, Redshift Spectrum over S3 |

Every one of these differences is a direct consequence of decoupled compute and storage — Snowflake and BigQuery just made different choices about *how* to expose and bill for that elastic compute.

---

## 2. MPP: Same Query, Many Nodes, One Answer

**Massively Parallel Processing** is the execution model underneath all three: data is split across many nodes (or micro-partitions, or slots), each node scans and aggregates its own slice in parallel, and a coordinator combines the partial results. This is why a query against a billion-row table doesn't take a thousand times longer than one against a million-row table — most of that billion rows' worth of scanning happens concurrently, not sequentially.

```python
import sqlite3, random, time
from datetime import datetime, timedelta

conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("""
    CREATE TABLE sales (
        id INTEGER PRIMARY KEY, region TEXT, product TEXT,
        revenue REAL, sale_date TEXT
    )
""")

random.seed(42)
regions = ["North", "South", "East", "West"]
products = ["Widget", "Gadget", "Doohickey", "Thingamajig"]
base_date = datetime(2024, 1, 1)
rows = []
for i in range(1, 10001):
    region = random.choice(regions)
    product = random.choice(products)
    revenue = round(random.uniform(10, 1000), 2)
    date = (base_date + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")
    rows.append((i, region, product, revenue, date))
cur.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?)", rows)
conn.commit()

# MAP phase: each simulated "node" aggregates only its own region
node_results = {}
for region in regions:
    cur.execute("""
        SELECT region, SUM(revenue), COUNT(*)
        FROM sales WHERE region = ? GROUP BY region
    """, (region,))
    node_results[region] = cur.fetchone()

# REDUCE phase: coordinator combines the partial results
grand_total = sum(r[1] for r in node_results.values())
grand_count = sum(r[2] for r in node_results.values())
print(f"Combined: total=${grand_total:,.2f}  rows={grand_count:,}")
```

```
Combined: total=$5,085,123.30  rows=10,000
```

Real warehouse SQL that triggers this same MPP execution needs nothing special — the parallelism is transparent to the query author:

```sql
-- Snowflake: warehouse size controls node count (XL = 16 nodes)
ALTER WAREHOUSE analytics_wh SET WAREHOUSE_SIZE = 'XLARGE';

-- BigQuery: automatically parallelizes across thousands of slots
SELECT region, SUM(revenue) FROM sales GROUP BY region;

-- Redshift: rows are distributed by DISTKEY, sorted within nodes by SORTKEY
CREATE TABLE sales (id INT, region VARCHAR(50), revenue DECIMAL(10,2))
DISTKEY(region) SORTKEY(sale_date);
```

---

## 3. Virtual Warehouses / Slots / Node Clusters: Isolating Workloads

The single most interview-relevant consequence of decoupled compute is **workload isolation**: an ETL job and a dashboard refresh can run on entirely separate compute allocations, against the *same* underlying data, without competing for resources or slowing each other down.

```python
class VirtualWarehouse:
    """Simplified simulation of a Snowflake virtual warehouse."""
    SIZES = {"XSMALL": 1, "SMALL": 2, "MEDIUM": 4, "LARGE": 8, "XLARGE": 16}

    def __init__(self, name, size="MEDIUM"):
        self.name = name
        self.size = size
        self.state = "SUSPENDED"
        self.credits_used = 0.0

    def run_query(self, query_name, duration_sec):
        if self.state == "SUSPENDED":
            self.state = "RUNNING"
            print(f"  [{self.name}] resumed ({self.size})")
        credits = (duration_sec / 3600) * self.SIZES[self.size]
        self.credits_used += credits
        print(f"  [{self.name}] '{query_name}' -- {credits:.4f} credits")

etl_wh = VirtualWarehouse("ETL_WH", "LARGE")
analytics_wh = VirtualWarehouse("ANALYTICS_WH", "MEDIUM")

etl_wh.run_query("daily_etl_load", duration_sec=300)
analytics_wh.run_query("dashboard_refresh", duration_sec=10)
# ETL and analytics never compete for the same compute -- fully isolated
```

```
  [ETL_WH] resumed (LARGE)
  [ETL_WH] 'daily_etl_load' -- 0.6667 credits
  [ANALYTICS_WH] resumed (MEDIUM)
  [ANALYTICS_WH] 'dashboard_refresh' -- 0.0111 credits
```

Real Snowflake SQL creates exactly this isolation:

```sql
CREATE WAREHOUSE etl_wh WITH WAREHOUSE_SIZE = 'LARGE'
    AUTO_SUSPEND = 300 AUTO_RESUME = TRUE
    MIN_CLUSTER_COUNT = 1 MAX_CLUSTER_COUNT = 3;

CREATE WAREHOUSE analytics_wh WITH WAREHOUSE_SIZE = 'MEDIUM'
    AUTO_SUSPEND = 600 AUTO_RESUME = TRUE;

USE WAREHOUSE etl_wh;
INSERT INTO fact_sales SELECT ... FROM staging.raw_sales;

USE WAREHOUSE analytics_wh;
SELECT region, SUM(revenue) FROM fact_sales GROUP BY region;
```

BigQuery's equivalent is a **reservation** of slots (a fixed pool of parallel query-execution units) assigned to a project or folder; Redshift's is a separate **cluster** or, more cheaply, **workload management (WLM) queues** inside one cluster. The name changes; the reason — don't let a heavy batch job starve an executive's dashboard of compute — doesn't.

---

## 4. Auto-Scaling: Absorbing a Burst Without Permanent Over-Provisioning

A warehouse sized for typical Tuesday-afternoon load will queue queries the moment fifty analysts all run a report at 9am Monday. Auto-scaling adds (and later removes) compute automatically in response to queueing, rather than requiring a human to resize anything.

```python
class AutoScalingWarehouse:
    def __init__(self, min_clusters=1, max_clusters=5, queries_per_cluster=5):
        self.min_clusters = min_clusters
        self.max_clusters = max_clusters
        self.queries_per_cluster = queries_per_cluster
        self.active_clusters = min_clusters

    def submit_queries(self, count):
        needed = max(self.min_clusters,
                     min(self.max_clusters, -(-count // self.queries_per_cluster)))
        scaled = needed > self.active_clusters
        self.active_clusters = needed
        print(f"  queries={count:>3}  clusters={self.active_clusters}  "
              f"{'SCALED UP' if scaled else 'steady'}")

wh = AutoScalingWarehouse(min_clusters=1, max_clusters=5)
for queries in [2, 4, 8, 15, 22, 25, 20, 12, 5, 2]:
    wh.submit_queries(queries)
```

```
  queries=  2  clusters=1  steady
  queries=  4  clusters=1  steady
  queries=  8  clusters=2  SCALED UP
  queries= 15  clusters=3  SCALED UP
  queries= 22  clusters=5  SCALED UP
  queries= 25  clusters=5  steady
  queries= 20  clusters=4  steady
  queries= 12  clusters=3  steady
  queries=  5  clusters=1  steady
  queries=  2  clusters=1  steady
```

Snowflake calls this **multi-cluster warehouses** (`MIN_CLUSTER_COUNT`/`MAX_CLUSTER_COUNT`, `SCALING_POLICY = 'STANDARD'`); BigQuery does it invisibly by allocating more slots to a larger query; Redshift calls it **concurrency scaling** — spinning up transient clusters for a burst, then tearing them down. All three trade a small amount of extra cost during the burst for not queueing (or permanently paying for) peak capacity around the clock.

---

## 5. Time Travel and Fail-Safe

**Time travel** lets you query — or restore — a table as it existed at some point in the recent past, without a separate backup system. It's implemented by retaining prior versions of data (Snowflake keeps micro-partition versions; BigQuery keeps table snapshots) rather than by literally storing a second copy per change.

```python
import sqlite3
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("""CREATE TABLE orders_versions (
    id INTEGER, customer TEXT, amount REAL, status TEXT,
    valid_from TEXT, valid_to TEXT)""")
cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer TEXT, amount REAL, status TEXT)")

t0 = "2024-06-15 10:00:00"
cur.execute("INSERT INTO orders VALUES (1, 'Alice', 250.00, 'pending')")
cur.execute("INSERT INTO orders_versions VALUES (1, 'Alice', 250.00, 'pending', ?, '9999-12-31')", (t0,))
conn.commit()

# T1: the order ships -- this is what an UPDATE does to the version log
t1 = "2024-06-15 10:30:00"
cur.execute("UPDATE orders_versions SET valid_to = ? WHERE id = 1 AND valid_to = '9999-12-31'", (t1,))
cur.execute("UPDATE orders SET status = 'shipped' WHERE id = 1")
cur.execute("INSERT INTO orders_versions VALUES (1, 'Alice', 250.00, 'shipped', ?, '9999-12-31')", (t1,))
conn.commit()

# TIME TRAVEL: what did order 1 look like at T0?
cur.execute("""SELECT status FROM orders_versions
               WHERE id = 1 AND valid_from <= ? AND valid_to > ?""", (t0, t0))
print(cur.fetchone())   # ('pending',) -- the original value, even though the live row now says 'shipped'
```

```
('pending',)
```

Real SQL:

```sql
-- Snowflake: query data as it was 5 minutes ago, or at an exact timestamp
SELECT * FROM orders AT(OFFSET => -300);
SELECT * FROM orders AT(TIMESTAMP => '2024-06-15 10:30:00'::TIMESTAMP);
UNDROP TABLE orders;   -- restore a dropped table entirely
CREATE TABLE orders_backup CLONE orders AT(OFFSET => -3600);  -- zero-copy clone at a point in time

-- BigQuery: query a table snapshot from an hour ago
SELECT * FROM `project.dataset.orders`
FOR SYSTEM_TIME AS OF TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR);
```

Snowflake additionally offers **fail-safe**: a further 7-day window *after* time travel expires, accessible only by Snowflake support for disaster recovery — not something end users query directly, but worth naming when asked "what happens after time travel runs out."

`CLONE ... AT(...)` deserves its own callout: a **zero-copy clone** creates a full logical copy of a table (or an entire schema/database) that shares the underlying storage with the original until either side's data diverges — cloning a multi-terabyte production table for a dev/test environment is instant and free of storage cost at clone time, because no bytes are actually copied. This is one of Snowflake's most commonly-asked-about interview features precisely because it has no cheap equivalent in a traditional coupled-storage database.

---

## 6. Materialized Views and Result Caching

A **materialized view** precomputes and stores a query's result, refreshed automatically (Snowflake, BigQuery) or manually (Redshift) as the underlying data changes — trading storage and refresh compute for much faster reads on a query pattern that's run over and over.

```python
import time
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, region TEXT, revenue REAL, sale_date TEXT)")
# ... 5,000 rows inserted ...

# Without a materialized view: full aggregation on every query
cur.execute("SELECT sale_date, SUM(revenue) FROM sales GROUP BY sale_date")

# With one: pre-aggregated table, indexed, queried directly
cur.execute("""CREATE TABLE mv_daily_revenue AS
    SELECT sale_date, region, SUM(revenue) AS total_revenue, COUNT(*) AS order_count
    FROM sales GROUP BY sale_date, region""")
cur.execute("CREATE INDEX idx_mv_date ON mv_daily_revenue(sale_date)")
```

**Result caching** is a further, even cheaper layer: if the *exact same query* (byte-for-byte, against unchanged underlying data) runs again, the warehouse returns the cached result with essentially zero compute cost — Snowflake caches results for 24 hours, BigQuery's cache lasts a similar window subject to some conditions, both invalidated the instant the underlying data changes.

```sql
-- All three platforms
CREATE MATERIALIZED VIEW mv_daily_revenue AS
SELECT sale_date, SUM(revenue) AS total_revenue
FROM sales GROUP BY sale_date;

-- Redshift needs an explicit refresh; Snowflake/BigQuery auto-refresh in the background
REFRESH MATERIALIZED VIEW mv_daily_revenue;
```

---

## Key Takeaways

- Every difference between Snowflake, BigQuery, and Redshift traces back to one shared idea — compute and storage are decoupled — expressed through three different pricing/isolation models: credits + virtual warehouses, slots + serverless billing, node-hours + provisioned clusters.
- MPP means a query is split across many nodes/slots/partitions that each scan their own slice in parallel, then a coordinator combines the results — this is why query time doesn't scale linearly with data size.
- Virtual warehouses (and their BigQuery/Redshift equivalents) exist primarily to isolate workloads — an ETL job and a BI dashboard should never compete for the same compute.
- Auto-scaling adds compute in response to actual query queueing, so you pay for peak capacity only when there's a peak, not around the clock.
- Time travel (and Snowflake's zero-copy clone) let you query or restore historical data without a separate backup system — know the retention windows and that fail-safe is the last-resort layer behind time travel.
- Materialized views and result caching both trade stored/cached compute for faster reads — the difference is a materialized view survives underlying-data changes (refreshed), while a result cache is invalidated the moment the source data changes.
