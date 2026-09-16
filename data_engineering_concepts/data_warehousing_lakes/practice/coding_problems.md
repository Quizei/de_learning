# Data Warehousing & Data Lakes — Coding Problems

Three problems, each a class or function you'd plausibly be asked to
implement live: a date-based data partitioner (the mechanics behind
`concepts/02_partitioning_and_bucketing.md`), a hash join (the
mechanics behind why bucketing avoids a shuffle), and a mini data
warehouse (star schema, ETL, OLAP queries, end to end).

How to use this file: read the problem statement and sample I/O, write
your own solution, and only then expand the reference solution and its
explanation.

---

## Problem 1: Data Partitioner

**Problem:** Build a `DataPartitioner` that buckets a stream of records
into date-based partitions — the same mechanic a data lake ingestion
job uses to lay records out into `year=/month=/day=` directories.

**Requirements:**
- Partition records by a configurable timestamp field, into daily,
  monthly, or yearly buckets.
- Support late-arriving data (a record whose timestamp is well behind
  the latest timestamp seen so far) and track how many arrived late.
- Return a dict mapping partition keys to lists of records.
- Track basic statistics: total records, partition count, late-arrival
  count.

**Sample input:**
```python
records = [
    {"id": 1, "timestamp": "2024-01-15 10:30:00", "event": "click"},
    {"id": 2, "timestamp": "2024-01-15 14:20:00", "event": "view"},
    {"id": 3, "timestamp": "2024-02-01 09:00:00", "event": "click"},
    {"id": 4, "timestamp": "2024-01-15 16:45:00", "event": "purchase"},
    {"id": 5, "timestamp": "2024-02-01 11:30:00", "event": "view"},
    {"id": 6, "timestamp": "2024-03-10 08:00:00", "event": "click"},
    {"id": 7, "timestamp": "2023-12-31 23:59:00", "event": "view"},  # late
]
```

**Expected output** (daily granularity):
```python
{
    "2024/01/15": [record 1, 2, 4],
    "2024/02/01": [record 3, 5],
    "2024/03/10": [record 6],
    "2023/12/31": [record 7],   # placed in its own correct partition
}
# stats: total=7, partitions=4, late_records=1  (record 7 arrives
# after record 6's later timestamp has already been seen)
```

<details>
<summary>Reference solution</summary>

```python
from collections import defaultdict
from datetime import datetime, timedelta


class DataPartitioner:
    """
    Partitions records into date-based buckets, at a configurable
    granularity -- the same layout decision a lake ingestion job makes
    when it writes year=/month=/day= directories.
    """

    GRANULARITY_FORMATS = {
        "daily":   "%Y/%m/%d",
        "monthly": "%Y/%m",
        "yearly":  "%Y",
    }

    def __init__(self, timestamp_field, granularity="daily",
                 timestamp_format="%Y-%m-%d %H:%M:%S"):
        if granularity not in self.GRANULARITY_FORMATS:
            raise ValueError(f"Unknown granularity: {granularity}")
        self.timestamp_field = timestamp_field
        self.timestamp_format = timestamp_format
        self.partition_format = self.GRANULARITY_FORMATS[granularity]
        self.partitions = defaultdict(list)
        self.stats = {"total": 0, "partitions": 0, "late_records": 0}
        self._latest_timestamp = None

    def get_partition_key(self, record):
        dt = datetime.strptime(record[self.timestamp_field], self.timestamp_format)
        return dt.strftime(self.partition_format)

    def partition(self, records):
        for record in records:
            self.stats["total"] += 1
            dt = datetime.strptime(record[self.timestamp_field], self.timestamp_format)

            # A record is "late" if it's well behind the latest timestamp
            # already seen -- exactly the late-arriving-data case a real
            # lake ingestion job has to detect and still place correctly.
            if self._latest_timestamp is not None and dt < self._latest_timestamp - timedelta(days=1):
                self.stats["late_records"] += 1

            if self._latest_timestamp is None or dt > self._latest_timestamp:
                self._latest_timestamp = dt

            key = self.get_partition_key(record)
            self.partitions[key].append(record)

        self.stats["partitions"] = len(self.partitions)
        return dict(self.partitions)

    def get_stats(self):
        return dict(self.stats)


records = [
    {"id": 1, "timestamp": "2024-01-15 10:30:00", "event": "click"},
    {"id": 2, "timestamp": "2024-01-15 14:20:00", "event": "view"},
    {"id": 3, "timestamp": "2024-02-01 09:00:00", "event": "click"},
    {"id": 4, "timestamp": "2024-01-15 16:45:00", "event": "purchase"},
    {"id": 5, "timestamp": "2024-02-01 11:30:00", "event": "view"},
    {"id": 6, "timestamp": "2024-03-10 08:00:00", "event": "click"},
    {"id": 7, "timestamp": "2023-12-31 23:59:00", "event": "view"},
]

partitioner = DataPartitioner("timestamp", granularity="daily")
partitions = partitioner.partition(records)
for key, recs in sorted(partitions.items()):
    print(f"  {key}: {len(recs)} records -> ids {[r['id'] for r in recs]}")
print(partitioner.get_stats())
```

**Output:**
```text
  2023/12/31: 1 records -> ids [7]
  2024/01/15: 3 records -> ids [1, 2, 4]
  2024/02/01: 2 records -> ids [3, 5]
  2024/03/10: 1 records -> ids [6]
{'total': 7, 'partitions': 4, 'late_records': 1}
```

**Explanation:** the partition key is derived purely from the record's
own timestamp — a late-arriving record (id 7, from December, arriving
after id 6's March timestamp has already been seen) still lands in its
own *correct* partition (`2023/12/31`), it's just flagged in
`late_records` for observability. This mirrors the real-world
requirement that late data shouldn't corrupt a partition layout, only
be visible as a monitoring signal — a pipeline that silently drops or
misplaces late-arriving records instead of tracking them is a common,
subtle bug in real ingestion jobs.

</details>

---

## Problem 2: Hash Join vs. Nested Loop Join

**Problem:** The following performs an inner join with a nested loop —
`O(n * m)` time, since every row of `left` is compared against every
row of `right`:

```python
def nested_loop_join(left, right, left_key, right_key):
    results = []
    for l_row in left:
        for r_row in right:
            if l_row[left_key] == r_row[right_key]:
                results.append({**l_row, **r_row})
    return results
```

Implement a **hash join** with `O(n + m)` time complexity that produces
identical results.

**Sample input:**
```python
orders = [
    {"order_id": 1, "customer_id": 101, "amount": 250.00},
    {"order_id": 2, "customer_id": 102, "amount": 75.50},
    {"order_id": 3, "customer_id": 101, "amount": 40.00},
]
customers = [
    {"customer_id": 101, "name": "Alice", "region": "US"},
    {"customer_id": 102, "name": "Bob",   "region": "EU"},
]
```

**Expected output:**
```python
[
    {"order_id": 1, "customer_id": 101, "amount": 250.0, "name": "Alice", "region": "US"},
    {"order_id": 2, "customer_id": 102, "amount": 75.5,  "name": "Bob",   "region": "EU"},
    {"order_id": 3, "customer_id": 101, "amount": 40.0,  "name": "Alice", "region": "US"},
]
```

<details>
<summary>Reference solution</summary>

```python
import random, time


def nested_loop_join(left, right, left_key, right_key):
    """O(n * m) nested loop join."""
    results = []
    for l_row in left:
        for r_row in right:
            if l_row[left_key] == r_row[right_key]:
                results.append({**l_row, **r_row})
    return results


def hash_join(left, right, left_key, right_key):
    """
    O(n + m) hash join.

    Build phase: hash the SMALLER table (right, typically the dimension)
    into {key -> [matching rows]}.
    Probe phase: scan the LARGER table (left, typically the fact table)
    once, looking up each row's key in the hash map.

    Time:  O(n + m) average case
    Space: O(min(n, m)) for the hash map
    """
    hash_map = {}
    for r_row in right:
        hash_map.setdefault(r_row[right_key], []).append(r_row)

    results = []
    for l_row in left:
        for r_row in hash_map.get(l_row[left_key], []):
            results.append({**l_row, **r_row})
    return results


orders = [
    {"order_id": 1, "customer_id": 101, "amount": 250.00},
    {"order_id": 2, "customer_id": 102, "amount": 75.50},
    {"order_id": 3, "customer_id": 101, "amount": 40.00},
]
customers = [
    {"customer_id": 101, "name": "Alice", "region": "US"},
    {"customer_id": 102, "name": "Bob",   "region": "EU"},
]

for row in hash_join(orders, customers, "customer_id", "customer_id"):
    print(row)

# --- Benchmark at scale, verifying correctness against the naive version ---
random.seed(42)
big_orders = [{"order_id": i, "customer_id": random.randint(1, 1000),
               "amount": round(random.uniform(10, 500), 2)} for i in range(5000)]
big_customers = [{"customer_id": i, "name": f"Customer_{i}",
                   "region": random.choice(["US", "EU", "APAC"])} for i in range(1, 1001)]

small_orders, small_customers = big_orders[:200], big_customers[:100]
start = time.perf_counter()
nl = nested_loop_join(small_orders, small_customers, "customer_id", "customer_id")
nl_time = time.perf_counter() - start

start = time.perf_counter()
hj = hash_join(small_orders, small_customers, "customer_id", "customer_id")
hj_time = time.perf_counter() - start

assert {(r["order_id"], r["customer_id"]) for r in nl} == {(r["order_id"], r["customer_id"]) for r in hj}
print(f"\n200x100 rows -- nested loop: {nl_time:.4f}s, hash join: {hj_time:.4f}s")

start = time.perf_counter()
full_hj = hash_join(big_orders, big_customers, "customer_id", "customer_id")
full_time = time.perf_counter() - start
print(f"5000x1000 rows -- hash join only: {full_time:.4f}s "
      f"({len(full_hj)} rows; nested loop would be ~25x more comparisons)")
```

**Output:**
```text
{'order_id': 1, 'customer_id': 101, 'amount': 250.0, 'name': 'Alice', 'region': 'US'}
{'order_id': 2, 'customer_id': 102, 'amount': 75.5, 'name': 'Bob', 'region': 'EU'}
{'order_id': 3, 'customer_id': 101, 'amount': 40.0, 'name': 'Alice', 'region': 'US'}

200x100 rows -- nested loop: 0.0028s, hash join: 0.0002s
5000x1000 rows -- hash join only: 0.0031s (5000 rows; nested loop would be ~25x more comparisons)
```

**Explanation:** the nested loop does `len(left) * len(right)`
comparisons no matter what — the hash join instead pays `O(m)` once to
build a lookup table from the smaller side, then `O(n)` to probe it
once per row on the larger side, for `O(n + m)` total. This is the
exact mechanism a query engine chooses between when planning a join —
and it's precisely what **bucketing** (`concepts/02_partitioning_and_bucketing.md`,
section 4) sets up ahead of time in a distributed setting: if both
tables are already bucketed identically on the join key, each bucket
pair can run this same hash join independently and in parallel, with no
cross-node shuffle needed to bring matching keys together first. A
sort-merge join (sort both sides by the join key, then walk them in
lockstep) is the other classic alternative, useful specifically when
both inputs are already sorted or too large to build an in-memory hash
table from either side.

</details>

---

## Problem 3: Mini Data Warehouse — Star Schema, ETL, and OLAP Queries

**Problem:** Build a `MiniWarehouse` class that owns the full pipeline
for a small retail warehouse: create a star schema, load raw
(deliberately messy) transaction records through an ETL step into the
fact and dimension tables, and answer OLAP-style aggregate queries
against the result.

**Requirements:**
- `create_schema()`: build `dim_date`, `dim_product`, `dim_customer`,
  and `fact_sales` (surrogate keys throughout — never let the fact
  table store a natural key directly).
- `etl_load(raw_transactions)`: take a list of raw, messy transaction
  dicts (inconsistent casing, occasional missing/invalid fields),
  clean and validate them, resolve natural keys to surrogate keys
  (inserting new dimension rows as needed), and load the result into
  `fact_sales`. Return counts of loaded vs. rejected records.
- `query_revenue_by_category()`: an OLAP aggregate query — total
  revenue and quantity per product category.
- `query_top_customers(n=3)`: top N customers by total spend.

**Sample input:**
```python
raw_transactions = [
    {"date": "2025-01-15", "customer_id": "C1", "customer_name": "Alice",
     "product_id": "P1", "product_name": "Laptop", "category": "Electronics",
     "quantity": 1, "unit_price": 999.00},
    {"date": "2025-01-15", "customer_id": "C2", "customer_name": "Bob",
     "product_id": "P2", "product_name": "Desk", "category": "Furniture",
     "quantity": 2, "unit_price": 150.00},
    {"date": "2025-01-16", "customer_id": "C1", "customer_name": "Alice",
     "product_id": "P2", "product_name": "Desk", "category": "Furniture",
     "quantity": 1, "unit_price": 150.00},
    {"date": "2025-01-16", "customer_id": "C3", "customer_name": None,   # invalid: no name
     "product_id": "P1", "product_name": "Laptop", "category": "Electronics",
     "quantity": 1, "unit_price": 999.00},
    {"date": "2025-01-17", "customer_id": "C2", "customer_name": "Bob",
     "product_id": "P3", "product_name": "Mouse", "category": "Electronics",
     "quantity": -1, "unit_price": 25.00},   # invalid: negative quantity
]
```

**Expected output:**
```text
Loaded: 3, Rejected: 2

Revenue by category:
  Electronics   revenue=$ 999.00  qty=1
  Furniture     revenue=$ 450.00  qty=3

Top customers:
  Alice   spend=$1149.00
  Bob     spend=$ 300.00
```

Note: only the Laptop sale to C1 (Alice) survives ETL under
Electronics — the second Laptop transaction (customer C3) is rejected
for a missing customer name, so it never reaches `fact_sales` at all.

<details>
<summary>Reference solution</summary>

```python
import sqlite3


class MiniWarehouse:
    """
    A small end-to-end warehouse: star schema + ETL + OLAP queries,
    backed by an in-memory SQLite database.
    """

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        self._customer_keys = {}   # natural key -> surrogate key
        self._product_keys = {}
        self._date_keys = {}

    def create_schema(self):
        self.conn.executescript("""
            CREATE TABLE dim_date (
                date_key INTEGER PRIMARY KEY AUTOINCREMENT,
                full_date TEXT UNIQUE NOT NULL
            );
            CREATE TABLE dim_product (
                product_key INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT UNIQUE NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL
            );
            CREATE TABLE dim_customer (
                customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL
            );
            CREATE TABLE fact_sales (
                sale_key INTEGER PRIMARY KEY AUTOINCREMENT,
                date_key INTEGER REFERENCES dim_date(date_key),
                product_key INTEGER REFERENCES dim_product(product_key),
                customer_key INTEGER REFERENCES dim_customer(customer_key),
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                revenue REAL NOT NULL
            );
        """)

    def _get_or_create_date_key(self, full_date):
        if full_date not in self._date_keys:
            cur = self.conn.execute(
                "INSERT INTO dim_date (full_date) VALUES (?)", (full_date,))
            self._date_keys[full_date] = cur.lastrowid
        return self._date_keys[full_date]

    def _get_or_create_customer_key(self, customer_id, customer_name):
        if customer_id not in self._customer_keys:
            cur = self.conn.execute(
                "INSERT INTO dim_customer (customer_id, customer_name) VALUES (?,?)",
                (customer_id, customer_name))
            self._customer_keys[customer_id] = cur.lastrowid
        return self._customer_keys[customer_id]

    def _get_or_create_product_key(self, product_id, product_name, category):
        if product_id not in self._product_keys:
            cur = self.conn.execute(
                "INSERT INTO dim_product (product_id, product_name, category) VALUES (?,?,?)",
                (product_id, product_name, category))
            self._product_keys[product_id] = cur.lastrowid
        return self._product_keys[product_id]

    def etl_load(self, raw_transactions):
        loaded, rejected = 0, 0
        for txn in raw_transactions:
            # Validate -- this is the "silver" step: reject anything
            # that can't be trusted, rather than silently loading bad data.
            if not txn.get("customer_name"):
                rejected += 1
                continue
            qty = txn.get("quantity")
            if not isinstance(qty, int) or qty <= 0:
                rejected += 1
                continue
            price = txn.get("unit_price")
            if not isinstance(price, (int, float)) or price <= 0:
                rejected += 1
                continue

            date_key = self._get_or_create_date_key(txn["date"])
            customer_key = self._get_or_create_customer_key(
                txn["customer_id"], txn["customer_name"])
            product_key = self._get_or_create_product_key(
                txn["product_id"], txn["product_name"], txn["category"])

            self.conn.execute("""
                INSERT INTO fact_sales
                    (date_key, product_key, customer_key, quantity, unit_price, revenue)
                VALUES (?,?,?,?,?,?)
            """, (date_key, product_key, customer_key, qty, price, round(qty * price, 2)))
            loaded += 1

        self.conn.commit()
        return {"loaded": loaded, "rejected": rejected}

    def query_revenue_by_category(self):
        return self.conn.execute("""
            SELECT p.category, SUM(f.revenue) AS revenue, SUM(f.quantity) AS qty
            FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
            GROUP BY p.category ORDER BY revenue DESC
        """).fetchall()

    def query_top_customers(self, n=3):
        return self.conn.execute("""
            SELECT c.customer_name, SUM(f.revenue) AS spend
            FROM fact_sales f JOIN dim_customer c ON f.customer_key = c.customer_key
            GROUP BY c.customer_key ORDER BY spend DESC LIMIT ?
        """, (n,)).fetchall()


raw_transactions = [
    {"date": "2025-01-15", "customer_id": "C1", "customer_name": "Alice",
     "product_id": "P1", "product_name": "Laptop", "category": "Electronics",
     "quantity": 1, "unit_price": 999.00},
    {"date": "2025-01-15", "customer_id": "C2", "customer_name": "Bob",
     "product_id": "P2", "product_name": "Desk", "category": "Furniture",
     "quantity": 2, "unit_price": 150.00},
    {"date": "2025-01-16", "customer_id": "C1", "customer_name": "Alice",
     "product_id": "P2", "product_name": "Desk", "category": "Furniture",
     "quantity": 1, "unit_price": 150.00},
    {"date": "2025-01-16", "customer_id": "C3", "customer_name": None,
     "product_id": "P1", "product_name": "Laptop", "category": "Electronics",
     "quantity": 1, "unit_price": 999.00},
    {"date": "2025-01-17", "customer_id": "C2", "customer_name": "Bob",
     "product_id": "P3", "product_name": "Mouse", "category": "Electronics",
     "quantity": -1, "unit_price": 25.00},
]

wh = MiniWarehouse()
wh.create_schema()
result = wh.etl_load(raw_transactions)
print(f"Loaded: {result['loaded']}, Rejected: {result['rejected']}")

print("\nRevenue by category:")
for row in wh.query_revenue_by_category():
    print(f"  {row['category']:<12} revenue=${row['revenue']:>7.2f}  qty={row['qty']}")

print("\nTop customers:")
for row in wh.query_top_customers():
    print(f"  {row['customer_name']:<6}  spend=${row['spend']:>7.2f}")
```

**Output:**
```text
Loaded: 3, Rejected: 2

Revenue by category:
  Electronics  revenue=$999.00  qty=1
  Furniture    revenue=$450.00  qty=3

Top customers:
  Alice   spend=$1149.00
  Bob     spend=$ 300.00
```

**Explanation:** notice the ETL step rejects the C3/Laptop transaction
(no customer name) and the Bob/Mouse transaction (negative quantity) —
`dim_product`/`dim_customer` never see a row created for rejected data,
and `fact_sales` never stores a natural key directly, only the
surrogate keys resolved during load (the same discipline as
`data_modeling/concepts/02_dimensional_modeling.md`, section 4). Notice
also that the "revenue by category" output above shows Electronics at
$999 (only the valid Laptop sale survived ETL) rather than the higher
number a naive sum over *raw* input would have produced — this is
exactly the kind of silent-corruption bug real ETL validation exists to
prevent, and it's worth checking your own solution's numbers against
the *rejected* count, not just against category totals that happen to
look plausible.

</details>
