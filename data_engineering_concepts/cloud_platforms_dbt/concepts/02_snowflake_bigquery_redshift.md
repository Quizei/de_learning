# Concept 02: Snowflake, BigQuery & Redshift — Platform-Specific Deep Dive

**Covers:**
- Snowflake: account/database/schema hierarchy, stages, `COPY INTO`, `VARIANT`, `FLATTEN`, streams for CDC
- BigQuery: project/dataset/table hierarchy, `STRUCT`/`ARRAY`, `UNNEST`, partitioned and clustered tables
- Redshift: distribution styles and sort keys, and why it lacks native `MERGE`
- A syntax-by-syntax comparison table for the operations you'll actually type in an interview or on the job

This file assumes the architecture vocabulary from `01_cloud_data_warehouses.md` (virtual warehouses, MPP, time travel) and goes one level more concrete: the actual SQL dialect and platform-native features each vendor ships. For the underlying table-format and lakehouse concepts (Iceberg, Delta Lake, Hudi, medallion architecture) that these warehouses increasingly sit alongside or on top of, see `data_warehousing_lakes/concepts/03_file_and_table_formats.md` and `concepts/04_data_lake_and_lakehouse_architecture.md` — this file does not re-cover that ground.

*Semi-structured data below is simulated as JSON text in `sqlite3`, since sqlite has no native `VARIANT`/`STRUCT` type — the real platform SQL is shown alongside every simulation.*

---

## 1. Snowflake: Hierarchy, Stages, and `COPY INTO`

Snowflake organizes objects as **Account → Database → Schema → Table**. Data usually arrives through a **stage** — a reference to a location holding files (an internal Snowflake-managed stage, or an external one pointing at S3/GCS/Azure Blob) — and gets bulk-loaded with `COPY INTO`.

```sql
CREATE DATABASE analytics;
CREATE SCHEMA analytics.staging;
CREATE SCHEMA analytics.marts;

CREATE STAGE analytics.staging.s3_stage
    URL = 's3://my-bucket/data/'
    CREDENTIALS = (AWS_KEY_ID='...' AWS_SECRET_KEY='...');

COPY INTO analytics.staging.raw_events
    FROM @analytics.staging.s3_stage/events/
    FILE_FORMAT = (TYPE = 'JSON');

COPY INTO analytics.staging.raw_orders
    FROM @analytics.staging.s3_stage/orders/
    FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"');
```

`COPY INTO` is idempotent by default — it tracks which staged files it has already loaded (via file metadata) and skips them on a re-run, which is exactly the property you want for a load step that might be retried after a partial failure.

---

## 2. Snowflake: `VARIANT` and `FLATTEN`

`VARIANT` stores semi-structured data (JSON, Avro, Parquet, XML) natively in a single column, queried with **colon notation** to reach into nested fields, and `LATERAL FLATTEN` to explode an array into rows.

```python
import sqlite3, json
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("CREATE TABLE raw_events (id INTEGER PRIMARY KEY, data TEXT)")  # data simulates VARIANT

events = [
    {"event_id": 2, "user_id": 102, "event": "checkout",
     "cart_items": [{"item": "Widget", "quantity": 2, "price": 29.99},
                    {"item": "Gadget", "quantity": 1, "price": 49.99}],
     "total": 109.97},
]
for i, e in enumerate(events, 1):
    cur.execute("INSERT INTO raw_events VALUES (?, ?)", (i, json.dumps(e)))
conn.commit()

# FLATTEN simulation -- explode cart_items into one row per item
cur.execute("SELECT data FROM raw_events")
for (raw,) in cur.fetchall():
    d = json.loads(raw)
    for item in d.get("cart_items", []):
        print(f"user={d['user_id']}  item={item['item']}  qty={item['quantity']}")
```

```
user=102  item=Widget  qty=2
user=102  item=Gadget  qty=1
```

Real Snowflake SQL:

```sql
CREATE TABLE raw_events (id INTEGER, data VARIANT);

SELECT
    data:event_id::INTEGER  AS event_id,
    data:event::STRING      AS event_type,
    data:properties:page::STRING AS page
FROM raw_events;

SELECT
    data:user_id::INTEGER AS user_id,
    f.value:item::STRING  AS item,
    f.value:quantity::INTEGER AS qty
FROM raw_events,
LATERAL FLATTEN(input => data:cart_items) f
WHERE data:event = 'checkout';
```

**Streams** (change data capture) let you consume only what changed since the stream was last read, without hand-rolling CDC logic:

```sql
CREATE STREAM orders_stream ON TABLE raw_orders;

SELECT * FROM orders_stream;
-- returns METADATA$ACTION (INSERT/DELETE), METADATA$ISUPDATE, METADATA$ROW_ID

INSERT INTO processed_orders
SELECT * FROM orders_stream WHERE METADATA$ACTION = 'INSERT';
-- the stream is now "consumed" -- empty until raw_orders changes again
```

Streams are frequently paired with **tasks** (Snowflake's built-in scheduler) to build lightweight, warehouse-native CDC pipelines without an external orchestrator.

---

## 3. BigQuery: `STRUCT`, `ARRAY`, and `UNNEST`

BigQuery organizes objects as **Project → Dataset → Table**, and — unlike Snowflake's colon-notation-over-a-single-VARIANT-column approach — supports nested (`STRUCT`) and repeated (`ARRAY`) fields as first-class parts of the table schema itself.

```sql
CREATE TABLE `project.dataset.orders` (
    order_id INT64,
    customer STRUCT<id INT64, name STRING, email STRING>,
    items ARRAY<STRUCT<product STRING, quantity INT64, unit_price FLOAT64>>,
    order_date DATE,
    total FLOAT64
);

-- Dot notation reaches into the STRUCT directly, no casting required
SELECT order_id, customer.name AS customer_name, total
FROM `project.dataset.orders`;

-- UNNEST flattens the repeated field into one row per array element
SELECT o.order_id, o.customer.name, item.product, item.quantity
FROM `project.dataset.orders` o, UNNEST(o.items) AS item;
```

```python
import sqlite3, json
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, data TEXT)")
order = {"order_id": 1001, "customer": {"name": "Alice Johnson"},
         "items": [{"product": "Laptop", "quantity": 1}, {"product": "Mouse", "quantity": 2}]}
cur.execute("INSERT INTO orders VALUES (?, ?)", (order["order_id"], json.dumps(order)))
conn.commit()

cur.execute("SELECT data FROM orders")
for (raw,) in cur.fetchall():
    d = json.loads(raw)
    for item in d["items"]:  # this loop is what UNNEST does inside the query engine
        print(f"{d['order_id']}  {d['customer']['name']}  {item['product']}  qty={item['quantity']}")
```

```
1001  Alice Johnson  Laptop  qty=1
1001  Alice Johnson  Mouse  qty=2
```

A `STRUCT`/`ARRAY` schema is BigQuery's preferred way to model a one-to-many relationship *without* a join — orders and their line items live in one physical row, avoiding both the join and the row-explosion a normalized `order_items` table would need at query time. The trade-off: updating a single nested item requires rewriting the whole containing row.

---

## 4. BigQuery: Partitioning and Clustering

**Partitioning** splits a table into segments (typically by date) so a query with a matching filter reads only the relevant segments — this is the single biggest lever for both query speed and cost in a per-byte-scanned pricing model. **Clustering** additionally sorts rows *within* each partition by one or more columns, so a filter on the clustered column can skip blocks without a filter on the partition column being present.

```python
import sqlite3, random
from datetime import datetime, timedelta

conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("""CREATE TABLE sales (id INTEGER PRIMARY KEY, region TEXT,
    revenue REAL, sale_date TEXT, partition_month TEXT)""")

random.seed(42)
base = datetime(2024, 1, 1)
for i in range(1, 10001):
    d = base + timedelta(days=random.randint(0, 180))
    cur.execute("INSERT INTO sales VALUES (?, ?, ?, ?, ?)",
                (i, random.choice(["US-East", "US-West", "EU", "APAC"]),
                 round(random.uniform(10, 500), 2), d.strftime("%Y-%m-%d"), d.strftime("%Y-%m")))
conn.commit()

cur.execute("SELECT COUNT(*) FROM sales")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sales WHERE partition_month = '2024-03'")
pruned = cur.fetchone()[0]
print(f"Full scan: {total:,} rows.  Partition-pruned (March only): {pruned:,} rows.")
print(f"Reduction: {(1 - pruned/total)*100:.1f}% less data scanned.")
```

```
Full scan: 10,000 rows.  Partition-pruned (March only): 1,697 rows.
Reduction: 83.0% less data scanned.
```

Real BigQuery DDL:

```sql
CREATE TABLE `project.dataset.sales`
PARTITION BY DATE(sale_date)
CLUSTER BY region, product_category
AS SELECT * FROM `project.dataset.raw_sales`;

-- Scans only the June 2024 partition -- not the whole table
SELECT SUM(revenue) FROM `project.dataset.sales`
WHERE sale_date BETWEEN '2024-06-01' AND '2024-06-30';

-- Auto-delete partitions older than 90 days
ALTER TABLE `project.dataset.sales`
SET OPTIONS (partition_expiration_days = 90);
```

Choosing partitioning and clustering columns well is one of the most concrete, checkable interview topics in this whole file — see `05_cost_and_performance_optimization.md` for the "the warehouse bill is too high" walkthrough that hinges on exactly this decision.

---

## 5. Redshift: Distribution Styles and Sort Keys

Redshift's MPP model is the most manual of the three: instead of automatic micro-partitions (Snowflake) or automatic slot allocation (BigQuery), you explicitly choose how rows are **distributed** across compute nodes and **sorted** within each node's disk blocks.

**Distribution style** controls which node a row lands on:

```sql
-- KEY distribution: rows with the same value hash to the same node --
-- essential for join performance, since matching rows on both sides
-- of a join end up co-located and never need to shuffle across nodes.
CREATE TABLE fact_sales (
    sale_id INT, customer_id INT, product_id INT, revenue DECIMAL(10,2)
) DISTSTYLE KEY DISTKEY(customer_id);

-- ALL distribution: the whole table is copied to every node -- good for
-- small, frequently-joined dimension tables (a few thousand rows), bad
-- for anything large (multiplies storage by the node count).
CREATE TABLE dim_date (date_key INT, full_date DATE) DISTSTYLE ALL;

-- EVEN distribution: round-robin across nodes -- the default when no
-- join pattern dominates, or the table is never joined at meaningful volume.
CREATE TABLE staging_raw_events (...) DISTSTYLE EVEN;
```

**Sort key** controls the physical row order within each node's blocks, which lets Redshift skip entire blocks during a scan when the query filters on (a prefix of) the sort key — conceptually the same payoff as BigQuery clustering, applied within Redshift's node-based storage instead:

```sql
CREATE TABLE fact_sales (
    sale_id INT, sale_date DATE, customer_id INT, revenue DECIMAL(10,2)
) DISTKEY(customer_id) SORTKEY(sale_date);
```

Choosing `DISTKEY` on the column a table is most frequently joined on, and `SORTKEY` on the column most frequently filtered by range (almost always a date), is the two-question decision tree that covers the large majority of real Redshift schema design.

### The Missing `MERGE`

Redshift has no native `MERGE`/upsert statement (this changed only recently and inconsistently across engines/versions — treat it as absent for interview purposes). The standard workaround is **stage, delete matching, insert**:

```sql
-- 1. Load new/changed rows into a staging table
-- 2. Delete rows in the target that match the staging table's keys
DELETE FROM target USING staging WHERE target.id = staging.id;
-- 3. Insert everything from staging
INSERT INTO target SELECT * FROM staging;
```

This DELETE+INSERT pattern is exactly what dbt's `delete+insert` incremental strategy automates — see `03_dbt_fundamentals_and_dag.md`, section 4.

---

## 6. Syntax Comparison Table

| Operation | Snowflake | BigQuery | Redshift |
|---|---|---|---|
| Semi-structured column | `data VARIANT` | `data JSON` (or `STRUCT`/`ARRAY`) | `data SUPER` |
| Parse a JSON field | `data:name::STRING` | `JSON_VALUE(data, '$.name')` | `data.name` (PartiQL-style) |
| Flatten an array | `LATERAL FLATTEN(data:items) f` | `UNNEST(items) AS item` | `t.data.items AS item` |
| Date truncation | `DATE_TRUNC('month', d)` | `DATE_TRUNC(d, MONTH)` | `DATE_TRUNC('month', d)` |
| String concatenation | `a \|\| ' ' \|\| b` | `CONCAT(a, ' ', b)` | `a \|\| ' ' \|\| b` |
| Upsert | `MERGE INTO ... WHEN MATCHED ...` | `MERGE INTO ... WHEN MATCHED ...` | No native `MERGE` — `DELETE` + `INSERT` |
| Materialized view refresh | Automatic | Automatic | `REFRESH MATERIALIZED VIEW` (manual) |

---

## Key Takeaways

- Snowflake, BigQuery, and Redshift share MPP and decoupled compute/storage, but diverge sharply on their SQL dialect, semi-structured data model, and how much manual physical-layout tuning they expect from you.
- Snowflake: `VARIANT` + colon notation + `FLATTEN` for semi-structured data; stages + `COPY INTO` for loading; streams + tasks for lightweight CDC.
- BigQuery: `STRUCT`/`ARRAY` as first-class schema elements + `UNNEST`; partitioning (almost always by date) is the single biggest cost lever in a per-byte-scanned pricing model, with clustering layered on top.
- Redshift is the most manual of the three: `DISTKEY` (join co-location) and `SORTKEY` (range-filter block skipping) are explicit, required design decisions, and there's no native `MERGE` — upserts go through stage/delete/insert.
- All three support `MERGE`-style upserts except Redshift's older/common configuration, and all three support materialized views with different refresh semantics (automatic vs. manual).
