# ETL/ELT — Practice Exercises

Twelve exercises covering: extraction strategy design, CSV/transform cleaning, deduplication, upsert loading, idempotent partition loads, transform pipelines, watermark tracking, late-arriving data, retry decorators, a mini validated ETL, replaying a CDC change stream, and choosing full vs. incremental for a given scale/freshness requirement.

How to use this file: read the exercise, write down your own solution — genuinely commit to one before looking — and only then expand the reference solution to check yourself. Every solution is real, runnable Python (stdlib + `sqlite3` only).

---

## Exercise 1: Design an Extraction Strategy

Given a source table `web_events` with columns `event_id (INT), user_id (INT), event_type (TEXT), page_url (TEXT), created_at (TIMESTAMP)` — 50 million rows, growing ~500K rows/day, **rows are never updated after creation**.

**Your task:** write `extract_new_events(conn, last_event_id, chunk_size=10000)` that efficiently extracts only new events since the last run, returning the extracted rows and the new high-water mark.

<details>
<summary>Reference solution</summary>

```python
def extract_new_events(conn, last_event_id, chunk_size=10000):
    all_rows = []
    current_hwm = last_event_id

    while True:
        rows = conn.execute(
            "SELECT * FROM web_events WHERE event_id > ? ORDER BY event_id LIMIT ?",
            (current_hwm, chunk_size),
        ).fetchall()
        if not rows:
            break
        all_rows.extend(rows)
        current_hwm = rows[-1][0]   # event_id of the last row in this chunk

    new_hwm = current_hwm if all_rows else last_event_id
    return all_rows, new_hwm
```

Since rows are never updated, ID-based incremental extraction (`concepts/04_incremental_vs_full.md`, section 3) is exactly the right tool — no timestamp column is needed, and there's no update-detection gap to worry about because updates structurally can't happen. Looping in chunks of 10,000 (rather than one `SELECT * WHERE event_id > ?` with no `LIMIT`) bounds memory usage regardless of how many new rows arrived since the last run.

</details>

---

## Exercise 2: CSV Cleaning Transform

```text
id,name,category,price,added_date
1, Widget A ,electronics, 29.99 ,01/15/2024
2,Gadget B,  TOYS  ,NULL,2024-02-20
3, Doohickey C,Electronics,invalid,March 5 2024
4,Thing D, home ,15.50,N/A
```

**Your task:** write `clean_products(csv_string)` returning a list of dicts where: whitespace is stripped from every field, empty/`NULL`/`N/A` become `None`, `price` is cast to float (default `0.0` if invalid), `added_date` is standardized to `YYYY-MM-DD`, and `category` is uppercased.

<details>
<summary>Reference solution</summary>

```python
import csv, io
from datetime import datetime

def clean_products(csv_string):
    reader = csv.DictReader(io.StringIO(csv_string))
    cleaned = []
    date_formats = ["%m/%d/%Y", "%Y-%m-%d", "%B %d %Y"]

    for row in reader:
        record = {}
        for k, v in row.items():
            v = v.strip() if v else ""
            record[k] = None if v.upper() in ("", "NULL", "N/A") else v

        try:
            record["price"] = float(record["price"]) if record["price"] else 0.0
        except (ValueError, TypeError):
            record["price"] = 0.0

        parsed = None
        if record["added_date"]:
            for fmt in date_formats:
                try:
                    parsed = datetime.strptime(record["added_date"], fmt); break
                except ValueError:
                    continue
        record["added_date"] = parsed.strftime("%Y-%m-%d") if parsed else None

        if record["category"]:
            record["category"] = record["category"].upper()

        cleaned.append(record)
    return cleaned
```

Row 3's `price` is `"invalid"`, which correctly falls back to `0.0` rather than raising and killing the whole batch — this is the same "route around, don't crash on" instinct as `concepts/02_transformation_patterns.md`, section 6. Note that `"invalid"` silently becoming `0.0` also hides a real data-quality problem — in a production pipeline this row's original bad value belongs in a dead-letter/error table too (`concepts/06_idempotency_reliability.md`, section 5), not just quietly defaulted.

</details>

---

## Exercise 3: Implement Deduplication

```python
records = [
    {"id": 1, "name": "Alice",   "email": "alice@example.com"},
    {"id": 2, "name": "Bob",     "email": "bob@example.com"},
    {"id": 1, "name": "Alice",   "email": "alice@example.com"},  # exact dup
    {"id": 3, "name": "alice",   "email": "alice@example.com"},  # same email, higher id
    {"id": 4, "name": "Charlie", "email": "charlie@example.com"},
    {"id": 5, "name": "Bob Jr",  "email": "bob@example.com"},    # same email as Bob
]
```

**Your task:** write `deduplicate_users(records)` that removes exact duplicates, then for any remaining same-email conflicts keeps the record with the highest `id`.

<details>
<summary>Reference solution</summary>

```python
def deduplicate_users(records):
    seen, unique = set(), []
    for r in records:
        key = (r["id"], r["name"], r["email"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    by_email = {}
    for r in unique:
        email = r["email"].lower()
        if email not in by_email or r["id"] > by_email[email]["id"]:
            by_email[email] = r

    return list(by_email.values())

deduped = deduplicate_users(records)
print(len(deduped))   # 3 -- alice (id=3), bob (id=5), charlie (id=4)
```

This is key-based dedup ("keep the record that wins under a rule"), not fuzzy dedup — the email is an exact, shared key. `practice/coding_problems.md`, Problem 2, extends this into genuine fuzzy matching, where records don't share a clean key at all.

</details>

---

## Exercise 4: Implement Upsert Loading

**Your task:** write `upsert_customers(conn, records)` that creates a `customers` table if needed (`id` PRIMARY KEY, `name`, `email`, `tier`, `updated_at`), upserts each record via `ON CONFLICT`, sets `updated_at` on every insert/update, and returns the row count after loading.

```python
test_records = [
    {"id": 1, "name": "Alice", "email": "a@test.com", "tier": "gold"},
    {"id": 2, "name": "Bob", "email": "b@test.com", "tier": "silver"},
    {"id": 1, "name": "Alice V2", "email": "alice@new.com", "tier": "platinum"},
]
```

<details>
<summary>Reference solution</summary>

```python
from datetime import datetime

def upsert_customers(conn, records):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY, name TEXT, email TEXT, tier TEXT, updated_at TEXT
        )
    """)
    now = datetime.now().isoformat()
    for r in records:
        conn.execute("""
            INSERT INTO customers (id, name, email, tier, updated_at) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name, email = excluded.email,
                tier = excluded.tier, updated_at = excluded.updated_at
        """, (r["id"], r["name"], r["email"], r["tier"], now))
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

import sqlite3
conn = sqlite3.connect(":memory:")
print(upsert_customers(conn, test_records))   # 2 -- id=1 landed twice, upserted to its final state
```

</details>

---

## Exercise 5: Idempotent Partition Load

**Your task:** write `load_partition(conn, partition_date, rows)` against `daily_sales(sale_date TEXT, product TEXT, revenue REAL)` that deletes all rows for `partition_date`, inserts the new rows, is safe to call repeatedly, and returns the total row count afterward.

<details>
<summary>Reference solution</summary>

```python
def load_partition(conn, partition_date, rows):
    conn.execute("CREATE TABLE IF NOT EXISTS daily_sales (sale_date TEXT, product TEXT, revenue REAL)")
    conn.execute("DELETE FROM daily_sales WHERE sale_date = ?", (partition_date,))
    conn.executemany("INSERT INTO daily_sales VALUES (?, ?, ?)", rows)
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM daily_sales").fetchone()[0]

conn = sqlite3.connect(":memory:")
data = [("2024-01-01", "Widget", 100.0), ("2024-01-01", "Gadget", 200.0)]
for run in range(1, 4):
    print(load_partition(conn, "2024-01-01", data))
# 2, 2, 2 -- idempotent regardless of how many times it runs
```

</details>

---

## Exercise 6: Build a Transform Pipeline

**Your task:** write a `TransformPipeline` class with `add_step(name, func)` and `run(data)` (executing steps in order, logging the row count remaining after each), then register these steps: `clean_nulls` (drop rows with no `name`), `cast_amount` (string → float), `add_tier` (`high`/`med`/`low` by amount), `filter_positive` (drop `amount <= 0`).

<details>
<summary>Reference solution</summary>

```python
class TransformPipeline:
    def __init__(self):
        self.steps = []

    def add_step(self, name, func):
        self.steps.append((name, func))

    def run(self, data):
        result = list(data)
        for name, func in self.steps:
            result = func(result)
            print(f"after '{name}': {len(result)} records")
        return result

def clean_nulls(rows): return [r for r in rows if r.get("name")]
def cast_amount(rows):
    for r in rows: r["amount"] = float(r["amount"])
    return rows
def add_tier(rows):
    for r in rows:
        a = r["amount"]
        r["tier"] = "high" if a >= 500 else ("med" if a >= 100 else "low")
    return rows
def filter_positive(rows): return [r for r in rows if r["amount"] > 0]

pipe = TransformPipeline()
for name, fn in [("clean_nulls", clean_nulls), ("cast_amount", cast_amount),
                  ("add_tier", add_tier), ("filter_positive", filter_positive)]:
    pipe.add_step(name, fn)

data = [{"name": "Alice", "amount": "750"}, {"name": "", "amount": "200"},
        {"name": "Bob", "amount": "-50"}, {"name": None, "amount": "100"}]
result = pipe.run(data)
# after 'clean_nulls': 2, after 'cast_amount': 2, after 'add_tier': 2, after 'filter_positive': 1
```

</details>

---

## Exercise 7: Watermark Tracker

**Your task:** write a `WatermarkTracker` class backed by a SQLite `watermarks` table: `get(table_name)` returns the stored watermark or `'1970-01-01'` if none exists, `set(table_name, value)` saves it idempotently.

<details>
<summary>Reference solution</summary>

```python
class WatermarkTracker:
    def __init__(self, conn):
        self.conn = conn
        conn.execute("CREATE TABLE IF NOT EXISTS watermarks (table_name TEXT PRIMARY KEY, watermark TEXT)")
        conn.commit()

    def get(self, table_name):
        row = self.conn.execute("SELECT watermark FROM watermarks WHERE table_name=?", (table_name,)).fetchone()
        return row[0] if row else "1970-01-01T00:00:00"

    def set(self, table_name, value):
        self.conn.execute("""
            INSERT INTO watermarks VALUES (?, ?)
            ON CONFLICT(table_name) DO UPDATE SET watermark = excluded.watermark
        """, (table_name, value))
        self.conn.commit()

conn = sqlite3.connect(":memory:")
wt = WatermarkTracker(conn)
print(wt.get("orders"))              # 1970-01-01T00:00:00
wt.set("orders", "2024-06-15T10:00:00")
print(wt.get("orders"))              # 2024-06-15T10:00:00
```

</details>

---

## Exercise 8: Handle Late-Arriving Data

```python
test_orders = [
    {"id": 101, "created_at": "2024-01-05T10:00:00"},
    {"id": 102, "created_at": "2024-01-03T08:00:00"},   # late!
    {"id": 103, "created_at": "2024-01-06T12:00:00"},
    {"id": 104, "created_at": "2024-01-02T15:00:00"},   # late!
]
current_watermark = "2024-01-04T00:00:00"
```

**Your task:** write `process_with_late_data(orders, watermark)` returning `(on_time, late, new_watermark)`, where `on_time` has `created_at > watermark`, `late` has `created_at <= watermark`, and late records are still processed (flagged, not dropped).

<details>
<summary>Reference solution</summary>

```python
def process_with_late_data(orders, watermark):
    on_time, late, max_ts = [], [], watermark
    for o in orders:
        if o["created_at"] > watermark:
            on_time.append(o)
            max_ts = max(max_ts, o["created_at"])
        else:
            late.append({**o, "_late": True})
    return on_time, late, max_ts

on_time, late, new_wm = process_with_late_data(test_orders, "2024-01-04T00:00:00")
print(len(on_time), [o["id"] for o in late])   # 2 [102, 104]
```

The watermark advances only from `on_time` records' timestamps, never from wall-clock time — see `concepts/04_incremental_vs_full.md`, section 4, for why advancing it any other way would cause a genuinely late row to be silently skipped forever once it does arrive.

</details>

---

## Exercise 9: Retry Decorator

**Your task:** write a `retry` decorator taking `max_retries`, `base_delay`, and `exceptions` (a tuple of exception types to catch), using exponential backoff (`base_delay * 2^attempt`), that raises the last exception once retries are exhausted.

<details>
<summary>Reference solution</summary>

```python
import functools, time

def retry(max_retries=3, base_delay=0.01, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(base_delay * (2 ** attempt))
        return wrapper
    return decorator

call_count = 0
@retry(max_retries=4, base_delay=0.01, exceptions=(ValueError,))
def flaky():
    global call_count
    call_count += 1
    if call_count < 3:
        raise ValueError(f"fail #{call_count}")
    return "OK"

print(flaky(), call_count)   # OK 3
```

Only catching the exception types passed in `exceptions` matters as much as the backoff math itself — a bare `except Exception` would also silently retry a programming bug (a `TypeError` from a code defect) as if it were a transient network blip, masking a real error behind a few wasted retries before it finally surfaces.

</details>

---

## Exercise 10: Mini ETL With Validation

```text
id,email,amount
1,alice@test.com,100.50
2,bad-email,200.00
3,charlie@test.com,-50
4,diana@test.com,300.75
-5,eve@test.com,150.00
6,,75.00
```

**Your task:** build a mini ETL that extracts this CSV, validates each record (`id` must be a positive integer, `email` must contain `@`, `amount` must be positive), transforms/loads valid records via upsert, and routes invalid records to an error table. Return `(loaded_count, error_count)`.

<details>
<summary>Reference solution</summary>

```python
import json

def mini_etl(csv_string):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE results (id INTEGER PRIMARY KEY, email TEXT, amount REAL)")
    conn.execute("CREATE TABLE errors (id TEXT, raw_data TEXT, reason TEXT)")

    reader = csv.DictReader(io.StringIO(csv_string))
    loaded = errors = 0

    for r in reader:
        reasons = []
        try:
            rid = int(r.get("id", ""))
            if rid <= 0: reasons.append("non-positive id")
        except ValueError:
            reasons.append("invalid id"); rid = r.get("id", "?")

        if not r.get("email") or "@" not in r["email"]:
            reasons.append("invalid email")

        try:
            amount = float(r.get("amount", ""))
            if amount <= 0: reasons.append("non-positive amount")
        except ValueError:
            reasons.append("invalid amount"); amount = 0

        if reasons:
            conn.execute("INSERT INTO errors VALUES (?, ?, ?)", (str(rid), json.dumps(r), "; ".join(reasons)))
            errors += 1
        else:
            conn.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?)", (rid, r["email"].strip(), amount))
            loaded += 1

    conn.commit()
    return loaded, errors

test_csv = "id,email,amount\n1,alice@test.com,100.50\n2,bad-email,200.00\n3,charlie@test.com,-50\n4,diana@test.com,300.75\n-5,eve@test.com,150.00\n6,,75.00\n"
print(mini_etl(test_csv))   # (2, 4) -- only ids 1 and 4 pass every rule
```

</details>

---

## Exercise 11: Replay a CDC Change Stream

```python
change_log = [
    {"op": "INSERT", "id": 1, "data": {"name": "Alice", "status": "active"}},
    {"op": "UPDATE", "id": 1, "data": {"name": "Alice", "status": "inactive"}},
    {"op": "INSERT", "id": 2, "data": {"name": "Bob",   "status": "active"}},
    {"op": "DELETE", "id": 1, "data": None},
    {"op": "UPDATE", "id": 2, "data": {"name": "Bob",   "status": "vip"}},
]
```

**Your task:** write `apply_cdc_stream(change_log)` that replays these ordered events into a final `{id: data}` state dict, correctly handling `DELETE` as a removal rather than a no-op or a stale row left behind.

<details>
<summary>Reference solution</summary>

```python
def apply_cdc_stream(change_log):
    state = {}
    for event in change_log:
        op, eid = event["op"], event["id"]
        if op in ("INSERT", "UPDATE"):
            state[eid] = event["data"]
        elif op == "DELETE":
            state.pop(eid, None)
    return state

print(apply_cdc_stream(change_log))
# {2: {'name': 'Bob', 'status': 'vip'}} -- id=1 correctly absent after its DELETE
```

The bug this exercise is designed to catch: if `DELETE` events are silently ignored (e.g. the function only branches on `INSERT`/`UPDATE`), id=1 would incorrectly remain in the final state at its last-known value — see `concepts/05_change_data_capture.md`, section 5, on why a delete must be applied as an explicit tombstone, not skipped.

</details>

---

## Exercise 12: Full Load or Incremental? Justify the Call

For each scenario, decide **full load**, **incremental by timestamp**, **incremental by ID**, or **CDC**, and justify in one sentence:

```text
a) A 40,000-row `product_categories` reference table that changes a few times a month.
b) A 200-million-row `orders` table with a reliable `updated_at`, refreshed hourly.
c) A 2-billion-row, strictly append-only `clickstream_events` table with a monotonic `event_id`.
d) A `customer_accounts` table where downstream fraud detection needs every update AND
   every account closure (delete) reflected within seconds.
```

<details>
<summary>Reference solution</summary>

```text
a) FULL LOAD.       Small (well under 100K rows) and changes infrequently -- the
                     simplicity of "just reload everything" costs almost nothing here,
                     and avoids maintaining watermark state for no real benefit.

b) INCREMENTAL BY TIMESTAMP.  Large enough that a full scan every hour is wasteful,
                     has a reliable updated_at, and doesn't need sub-minute freshness
                     or delete-capture -- the textbook case for a watermark.

c) INCREMENTAL BY ID.  Strictly append-only removes the one weakness of ID-based
                     incremental (blindness to updates) entirely, and it needs no
                     timestamp column or CDC infrastructure to do the job.

d) CDC (log-based).  Needs both delete-capture and near-real-time latency -- the two
                     things timestamp/ID-based incremental extraction structurally
                     cannot provide (concepts/04_incremental_vs_full.md, section 5).
```

</details>
