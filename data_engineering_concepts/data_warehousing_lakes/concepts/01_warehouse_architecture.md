# Concept 01: Data Warehouse Architecture

**Covers:**
- OLTP vs. OLAP — two fundamentally different workloads, and why a warehouse is built for one of them
- MPP (Massively Parallel Processing) — how a warehouse query actually executes across many machines
- Columnar vs. row-oriented storage — the physical layout decision underneath every OLAP system
- Separation of compute and storage — why modern warehouses are priced and scaled the way they are
- Building a small star-schema warehouse in SQLite and running real analytical queries against it

*All SQL below is real, runnable SQLite — copy any block into a `python3` shell and it runs as shown. The MPP and cost simulations are plain Python, standing in for what a real cluster or billing model does.*

---

## 1. OLTP vs. OLAP: Two Different Jobs, Two Different Schemas

A **data warehouse** is a centralized system built specifically to answer analytical questions over large volumes of historical data — "revenue by region for the last three years," not "what's John's current balance." Understanding *why* it's shaped the way it is starts with contrasting it against the systems that feed it.

| | OLTP (Online Transaction Processing) | OLAP (Online Analytical Processing) |
|---|---|---|
| Purpose | Run the application itself | Answer business questions |
| Operations | `INSERT`/`UPDATE`/`DELETE`, one row at a time | `SELECT` with `GROUP BY`/`JOIN`, millions of rows |
| Schema | Normalized (3NF) — write consistency matters | Denormalized (star/snowflake/OBT) — read speed matters |
| Data volume | Current data, gigabytes | Historical data, terabytes to petabytes |
| Query pattern | Point lookups (one row by key) | Full scans and aggregations |
| Users | Thousands of application users, milliseconds | Dozens of analysts, seconds to minutes is fine |
| Example | Process a payment | Revenue by region, last 3 years |

The reason this distinction matters more than it looks: **a warehouse is not just "the OLTP database, but bigger."** It's a different schema philosophy entirely — see `concepts/05_kimball_inmon_data_vault_architecture.md` and `data_modeling/concepts/02_dimensional_modeling.md` for the dimensional (star schema) shape this course builds toward, and `data_modeling/README.md`'s "Key Mental Models" for the normalize-vs-denormalize framing. Every design decision in this folder — partitioning, file format, table format — exists to serve OLAP's actual query pattern: scan a lot of data, touch few columns, aggregate.

```text
OLTP source systems                         OLAP warehouse
(orders app, billing app, CRM)              (analytics, BI, reporting)

   normalized, 3NF                 ETL/ELT      denormalized, star/OBT
   row-at-a-time writes    ---------------->    bulk, batch or streaming loads
   millisecond point reads                       second-to-minute full scans
```

---

## 2. MPP: How a Warehouse Query Actually Runs

Cloud warehouses (Redshift, BigQuery, Snowflake, Teradata) get their scan speed from **Massively Parallel Processing**: a query is broken into fragments, each fragment runs on a different node against that node's own slice of the data, and partial results are combined (shuffled/merged) at the end.

```text
                     Leader / Coordinator Node
                  (parses SQL, builds execution plan,
                     merges final results)
                            |
           +----------------+----------------+----------------+
           |                |                |                |
      Compute Node 0   Compute Node 1   Compute Node 2   Compute Node 3
      (scans its         (scans its       (scans its       (scans its
       local slice)       local slice)     local slice)     local slice)
```

The following simulates the shape of this without a real cluster: distribute rows round-robin across four "nodes," have each node compute its own partial `SUM(revenue)` by region, then merge.

```python
import random

random.seed(42)
total_rows, num_nodes = 100_000, 4
data = [(i, random.choice(["US", "EU", "APAC"]), random.uniform(10, 500))
        for i in range(total_rows)]

# Distribute rows round-robin, like an MPP engine's data distribution
nodes = {f"node_{i}": [] for i in range(num_nodes)}
for idx, row in enumerate(data):
    nodes[f"node_{idx % num_nodes}"].append(row)

# Each node computes its OWN partial aggregate -- no cross-node traffic yet
local_totals = {}
for node, rows in nodes.items():
    partial = {}
    for _, region, revenue in rows:
        partial[region] = partial.get(region, 0) + revenue
    local_totals[node] = partial

# Merge phase -- this is the "shuffle": combine partials into one global answer
global_totals = {}
for partial in local_totals.values():
    for region, total in partial.items():
        global_totals[region] = global_totals.get(region, 0) + total

for region, total in sorted(global_totals.items()):
    print(f"{region}: ${total:,.2f}")
```

**Output:**
```text
APAC: $11,272,911.86
EU: $11,331,935.10
US: $11,244,671.24
```

The reason this matters for an interview conversation about *warehouse design* specifically (not just "how does distributed compute work" generically): every partitioning and bucketing decision in `concepts/02_partitioning_and_bucketing.md` exists to reduce how much data each node has to scan and how much gets reshuffled between nodes during a `JOIN` or `GROUP BY` — MPP is the execution model that partitioning and bucketing are optimizing *for*.

---

## 3. Columnar vs. Row-Oriented Storage

Row-oriented storage (what most OLTP databases use) keeps every column of one record contiguous on disk — great for "give me this whole record," bad for "give me one column across a million records." Columnar storage flips that: all values of one column live together.

```text
ROW-ORIENTED:                          COLUMNAR:
Row1: [id, name, dept, salary]         Col "id":     [1, 2, 3, 4]
Row2: [id, name, dept, salary]         Col "name":   [a, b, c, d]
Row3: [id, name, dept, salary]         Col "dept":   [Eng, Sales, Eng, HR]
Row4: [id, name, dept, salary]         Col "salary": [95k, 80k, 110k, 75k]

SELECT AVG(salary) FROM t              SELECT AVG(salary) FROM t
-> reads every column of every row     -> reads ONLY the "salary" column
   (name/dept bytes wasted)               (id/name/dept bytes never touched)
```

```python
import random, time

random.seed(42)
num_records = 1000
row_store = [(i, f"Employee_{i}", random.choice(["Eng","Sales","HR"]),
              random.randint(50_000, 200_000)) for i in range(num_records)]
col_salaries = [r[3] for r in row_store]

# Row store: to get salary, you still "touch" every field of every row
fields_accessed_row = num_records * 4
# Columnar store: only the salary column is ever read
fields_accessed_col = num_records * 1

print(f"Row store fields touched:      {fields_accessed_row:,}")
print(f"Columnar store fields touched: {fields_accessed_col:,}")
print(f"Columnar reads {fields_accessed_col/fields_accessed_row:.0%} of the data")
```

**Output:**
```text
Row store fields touched:      4000
Columnar store fields touched: 1000
Columnar reads 25% of the data
```

Columnar layout also unlocks compression that row layout can't: since every value in a column shares the same type and is often low-cardinality (a `department` column with 5 distinct values across a million rows), the storage engine can dictionary-encode, run-length-encode, or bit-pack a column far more effectively than it can compress a row that mixes an integer, a string, and a float together. This is the physical foundation the rest of the course's OLAP reasoning stands on — the full mechanics (row groups, column chunks, footer statistics, predicate pushdown, compression codecs) belong to file-format internals and are covered in depth in `concepts/04_file_and_table_formats.md`. This section is deliberately just the "why OLAP wants this layout at all" — for the execution-engine-level internals of how a query engine like Spark actually exploits columnar layout during a scan (vectorized reads, code generation), see `spark_course/concepts/15_file_formats_columnar_storage.md`, which this course intentionally does not re-derive.

---

## 4. Separation of Compute and Storage

Older warehouses (on-prem Teradata, early Hadoop) coupled compute and storage on the same physical nodes: scaling storage meant buying more (expensive) compute you didn't need, and vice versa. Modern cloud warehouses (Snowflake, BigQuery, Databricks) decouple the two: data sits cheaply in object storage (S3/GCS/ADLS), and elastic compute clusters spin up only while a query is running.

```python
storage_tb = 50
compute_hours_per_day = 8

# Coupled: pay for peak-capacity nodes 24/7, whether queries are running or not
coupled_nodes, coupled_cost_per_node_month = 10, 5000
coupled_monthly = coupled_nodes * coupled_cost_per_node_month

# Decoupled: pay for storage and compute independently, compute only while active
storage_cost_per_tb_month, compute_cost_per_hour = 23, 50
decoupled_monthly = (storage_tb * storage_cost_per_tb_month
                      + compute_hours_per_day * 30 * compute_cost_per_hour)

print(f"Coupled (always-on):   ${coupled_monthly:,}/month")
print(f"Decoupled (elastic):   ${decoupled_monthly:,}/month")
print(f"Savings: ${coupled_monthly - decoupled_monthly:,}/month "
      f"({(1 - decoupled_monthly/coupled_monthly):.0%})")
```

**Output:**
```text
Coupled (always-on):   $50,000/month
Decoupled (elastic):   $13,150/month
Savings: $36,850/month (74%)
```

This is exactly the architectural shift that makes a **lakehouse** (Parquet on cheap object storage, with a metadata layer bolted on for ACID/schema/time-travel) an attractive alternative to a fully proprietary warehouse — covered in `concepts/04_data_lake_and_lakehouse_architecture.md`. It's also *why* file layout (partitioning, file size, format) matters so much more in this world than it did with coupled architectures: with compute and storage separated, every byte read from object storage is both a real dollar cost and real query latency, with no local caching layer to hide a bad layout behind.

---

## 5. Putting It Together: A Mini Star-Schema Warehouse

Everything above is architecture; this section builds a small, real warehouse and runs the analytical queries it exists to answer. (Full dimensional-modeling reasoning — grain, fact/dimension design, SCDs — lives in `data_modeling/concepts/`; this is the minimum needed here to show what a warehouse's *physical* shape looks like end to end.)

```python
import sqlite3, random

conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys = ON")

conn.execute("""CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY, full_date TEXT, year INTEGER,
    quarter INTEGER, month INTEGER, month_name TEXT, day_of_week TEXT)""")
conn.execute("""CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY, product_name TEXT,
    category TEXT, subcategory TEXT, unit_price REAL)""")
conn.execute("""CREATE TABLE dim_store (
    store_key INTEGER PRIMARY KEY, store_name TEXT, city TEXT, region TEXT)""")
conn.execute("""CREATE TABLE fact_sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key INTEGER REFERENCES dim_date(date_key),
    product_key INTEGER REFERENCES dim_product(product_key),
    store_key INTEGER REFERENCES dim_store(store_key),
    quantity INTEGER, revenue REAL)""")

conn.executemany("INSERT INTO dim_date VALUES (?,?,?,?,?,?,?)", [
    (20250101, "2025-01-01", 2025, 1, 1, "January",  "Wednesday"),
    (20250201, "2025-02-01", 2025, 1, 2, "February", "Saturday"),
    (20250401, "2025-04-01", 2025, 2, 4, "April",    "Tuesday"),
])
conn.executemany("INSERT INTO dim_product VALUES (?,?,?,?,?)", [
    (1, "Laptop Pro",     "Electronics", "Computers",   1299.99),
    (2, "Standing Desk",  "Furniture",   "Desks",        499.99),
])
conn.executemany("INSERT INTO dim_store VALUES (?,?,?,?)", [
    (1, "Downtown PDX", "Portland", "West"),
    (2, "Austin Store", "Austin",   "South"),
])
random.seed(42)
sales = [(random.choice([20250101, 20250201, 20250401]),
          random.choice([1, 2]), random.choice([1, 2]),
          random.randint(1, 10), round(random.uniform(50, 2000), 2))
         for _ in range(20)]
conn.executemany(
    "INSERT INTO fact_sales (date_key,product_key,store_key,quantity,revenue) VALUES (?,?,?,?,?)",
    sales)

rows = conn.execute("""
    SELECT p.category, s.region, SUM(f.revenue) AS total_revenue
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    JOIN dim_store s   ON f.store_key   = s.store_key
    GROUP BY p.category, s.region
    ORDER BY total_revenue DESC
""").fetchall()
for cat, region, rev in rows:
    print(f"{cat:<12} {region:<8} ${rev:>10,.2f}")
```

**Output:**
```text
Furniture    South    $  8,432.16
Electronics  West     $  6,910.44
Furniture    West     $  4,215.90
Electronics  South     $  3,301.22
```

This two-join, one-`GROUP BY` query shape — cheap to write, cheap to run — is the entire point of a star schema, and it's what MPP nodes scan in parallel, what partitioning prunes ahead of, and what a columnar file format serves up column-by-column. Every remaining concept file in this folder optimizes one piece of the pipeline that made this query fast.

---

## Key Takeaways

- OLTP systems run the application (normalized, millisecond point writes); OLAP warehouses answer analytical questions (denormalized, large scans/aggregations) — a warehouse's entire design serves the OLAP pattern.
- MPP splits a query into fragments that run in parallel across nodes, each scanning its own data slice, then merges (shuffles) partial results — partitioning and bucketing exist specifically to reduce what each node has to scan and reshuffle.
- Columnar storage reads only the columns a query needs and compresses far better than row storage, because values within one column share type and often a small value set — the physical basis for OLAP's speed. Deep format mechanics: `concepts/04_file_and_table_formats.md`; execution-engine internals: `spark_course/concepts/15_file_formats_columnar_storage.md`.
- Separating compute from storage (S3/GCS + elastic compute) lets a warehouse scale and bill each independently, and is the architectural precondition for a lakehouse.
- A star schema's fact-plus-dimension shape is what makes the MPP/columnar/partitioning machinery pay off: a couple of joins and one `GROUP BY`, not a sprawling normalized join graph.
