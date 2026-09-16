# Concept 01: Extraction Patterns

**Covers:**
- Full extraction vs. incremental extraction (watermarks)
- API extraction: pagination and retry logic
- File-based extraction (CSV) and messy source handling
- Database extraction patterns: projection, chunking, join-based extraction
- Tracking extraction metadata (the extraction registry pattern)

*All Python below is real, runnable stdlib + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. Full Extraction: The Simplest, Least Scalable Pattern

Extraction is the "E" in ETL/ELT — pulling data out of a source system before anything is done to it. The simplest possible extraction pattern is also the most expensive one: read every row, every time.

```python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("""CREATE TABLE orders (
    id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL,
    status TEXT, updated_at TEXT)""")
conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", [
    (1, 1, 120.0, "shipped", "2024-01-01T10:00:00"),
    (2, 2, 45.0,  "pending", "2024-01-01T11:00:00"),
    (3, 1, 300.0, "shipped", "2024-01-02T09:00:00"),
])
conn.commit()

rows = conn.execute("SELECT * FROM orders").fetchall()
print(f"Full extraction pulled {len(rows)} rows")
# Full extraction pulled 3 rows
```

Use it when the source table is small, you genuinely need a complete point-in-time snapshot every run, or — worth naming out loud in an interview — **no reliable "last modified" signal exists on the source at all**. A full extract is sometimes not a choice but the only option a source leaves you.

Why this doesn't scale: extraction time and source-system load both grow linearly with table size, forever, even on a day when nothing changed. This is the motivating problem the rest of this file (and `concepts/04_incremental_vs_full.md`) solves.

## 2. Incremental Extraction by Watermark

A **watermark** is the maximum value of some monotonically increasing column (almost always a timestamp) that was extracted on the previous run. Each subsequent run asks the source for only rows past that point.

```python
def incremental_extract(conn, watermark):
    rows = conn.execute(
        "SELECT * FROM orders WHERE updated_at > ? ORDER BY updated_at",
        (watermark,),
    ).fetchall()
    new_watermark = rows[-1][4] if rows else watermark   # updated_at of the last row
    return rows, new_watermark

# Run 1: no watermark yet -> use the epoch, pulls everything
rows, wm = incremental_extract(conn, "1970-01-01T00:00:00")
print(f"Run 1: {len(rows)} rows, watermark now {wm}")
# Run 1: 3 rows, watermark now 2024-01-02T09:00:00

conn.execute("INSERT INTO orders VALUES (4, 2, 60.0, 'pending', '2024-01-02T12:00:00')")
conn.commit()

rows, wm = incremental_extract(conn, wm)
print(f"Run 2: {len(rows)} rows, watermark now {wm}")
# Run 2: 1 rows, watermark now 2024-01-02T12:00:00
```

This is the workhorse of batch ETL. Its one hard requirement is a column the source actually maintains correctly — an `updated_at` bumped on every `UPDATE`, not just on `INSERT`. If the source can't guarantee that, incremental-by-timestamp silently misses updates forever — exactly the bug worked through in `interview_questions/03_critique_and_debug.md`, Case 2.

Watermark extraction can only ever see inserts and updates — it can never see a `DELETE`, because a deleted row can't show up in a `WHERE updated_at > ?` scan at all. That gap is the entire reason `concepts/05_change_data_capture.md` exists as its own topic.

## 3. API Extraction: Pagination and Retries

Most REST APIs return one page of results at a time and expect the caller to loop until a "no more pages" signal appears. Production API extraction always needs retry logic layered on top, because transient network/API errors are the norm at scale, not the exception.

```python
import time, random

class MockAPI:
    def __init__(self, total=47):
        self._data = [{"id": i, "value": f"record_{i}"} for i in range(1, total + 1)]

    def get(self, page, page_size=10):
        if random.random() < 0.2:                 # simulate a transient failure
            raise ConnectionError("transient API error")
        start = (page - 1) * page_size
        page_data = self._data[start:start + page_size]
        return {"data": page_data, "has_more": start + page_size < len(self._data)}

def fetch_with_retry(api, page, page_size, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            return api.get(page, page_size)
        except ConnectionError:
            time.sleep(0.01 * 2 ** attempt)        # exponential backoff, see concepts/06
    raise RuntimeError(f"failed after {max_retries} retries on page {page}")

def extract_all(api, page_size=10):
    records, page, has_more = [], 1, True
    while has_more:
        resp = fetch_with_retry(api, page, page_size)
        records.extend(resp["data"])
        has_more = resp["has_more"]
        page += 1
    return records

random.seed(42)
records = extract_all(MockAPI(total=47))
print(f"Extracted {len(records)} records across pages")
# Extracted 47 records across pages
```

Two details worth naming unprompted in an interview: retries need **exponential backoff** so a flaky API isn't hammered harder while it's already struggling (full treatment in `concepts/06_idempotency_reliability.md`), and pagination loops need a real termination condition (`has_more`, a `next_cursor`, or a page returning fewer than `page_size` rows) — a naive `while True` with no exit condition is a real production incident waiting to happen.

## 4. File Extraction: CSVs Are Never Clean

```python
import csv, io

csv_content = """\
id,name,email,amount,signup_date
1,Alice,alice@example.com,120.50,2024-01-15
2,Bob,,85.00,2024-02-20
3,"Charlie, Jr.",charlie@example.com,,2024-03-10
"""

reader = csv.DictReader(io.StringIO(csv_content))
extracted = [
    {
        "id": int(row["id"]),
        "name": row["name"].strip(),
        "email": row["email"] or None,
        "amount": float(row["amount"]) if row["amount"] else None,
    }
    for row in reader
]
print(extracted[1])   # {'id': 2, 'name': 'Bob', 'email': None, 'amount': 85.0}
print(extracted[2])   # {'id': 3, 'name': 'Charlie, Jr.', 'email': 'charlie@example.com', 'amount': None}
```

Row 2 has an empty `email` field and row 3 has an empty `amount` and a comma embedded inside a quoted name — `csv.DictReader` handles the quoting correctly for free, but null-handling and type-casting are the extraction job's responsibility, not the file format's. Deeper cleaning (standardizing formats, validating business rules) is deliberately deferred to `concepts/02_transformation_patterns.md` — extraction's job here is only to get the raw values out safely.

## 5. Database Extraction Patterns

Three small techniques compound into a real difference at scale:

**Projection** — select only the columns the pipeline actually needs, not `SELECT *`. Cheaper to transfer, and insulates the pipeline from an unrelated column being added later (a schema-evolution concern in its own right — see `interview_questions/03_critique_and_debug.md`, Case 3).

**Chunked extraction** — for a source with no usable timestamp, paging through with `LIMIT`/`OFFSET` bounds memory usage on both ends:

```python
chunk_size, offset, total = 2, 0, 0
while True:
    chunk = conn.execute(
        "SELECT * FROM orders ORDER BY id LIMIT ? OFFSET ?", (chunk_size, offset)
    ).fetchall()
    if not chunk:
        break
    total += len(chunk)
    offset += chunk_size
print(f"Extracted {total} rows in chunks of {chunk_size}")
# Extracted 4 rows in chunks of 2
```

`LIMIT`/`OFFSET` chunking has a sharp failure mode worth knowing: if rows are being inserted into the table *while* you page through it, offset-based paging can skip or duplicate rows, because "row 10,001" shifts underneath you between pages. Paging by a stable, unique, monotonically increasing column instead (`WHERE id > last_seen_id ORDER BY id LIMIT n`) avoids this — the same high-water-mark idea as incremental extraction, applied here for a different reason (bounding memory, not freshness).

**Join-based extraction** — denormalizing at the source with a `JOIN` can save a downstream join later, at the cost of coupling the extraction query to the source schema's relationships:

```python
conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
conn.execute("INSERT INTO customers VALUES (1, 'Alice'), (2, 'Bob')")
conn.commit()

rows = conn.execute("""
    SELECT o.id AS order_id, c.name AS customer_name, o.amount
    FROM orders o JOIN customers c ON o.customer_id = c.id
""").fetchall()
print(rows[0])
# (1, 'Alice', 120.0)
```

## 6. Tracking Extraction Metadata

Production pipelines never just extract — they record *what* they extracted and *where they left off*, so the next run (and anyone debugging a 3am page) can answer "what did this job load, and when":

```python
class ExtractionRegistry:
    def __init__(self):
        self._jobs = {}

    def register(self, name, source_type, mode="full"):
        self._jobs[name] = {"source_type": source_type, "mode": mode,
                             "watermark": None, "rows_extracted": 0}

    def record_run(self, name, watermark, rows):
        self._jobs[name]["watermark"] = watermark
        self._jobs[name]["rows_extracted"] = rows

reg = ExtractionRegistry()
reg.register("orders", "database", mode="incremental")
reg.record_run("orders", "2024-01-02T12:00:00", rows=4)
print(reg._jobs["orders"])
# {'source_type': 'database', 'mode': 'incremental', 'watermark': '2024-01-02T12:00:00', 'rows_extracted': 4}
```

This is a scaled-down version of what `concepts/04_incremental_vs_full.md`'s watermark table and `projects/mini_etl_pipeline.md`'s `etl_watermarks` table do for real — every incremental job in this whole topic ultimately persists its watermark somewhere durable, not in a Python variable that dies with the process.

---

See `concepts/04_incremental_vs_full.md` for the full trade-off comparison between full, timestamp-incremental, and ID-incremental extraction, and `concepts/05_change_data_capture.md` for what to do when even a watermark isn't enough (deletes, guaranteed ordering, near-real-time delivery).
