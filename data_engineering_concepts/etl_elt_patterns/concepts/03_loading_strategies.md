# Concept 03: Loading Strategies

**Covers:**
- INSERT (append-only) and why it isn't idempotent
- Upsert (`INSERT OR REPLACE` / `ON CONFLICT DO UPDATE`)
- Delete-then-insert and partition overwrite
- Bulk loading concepts: batching, staging, disabling constraints
- The staging-table pattern (the production-grade default)
- Decision guide: which strategy for which situation

*All Python below is real, runnable stdlib + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. INSERT (Append-Only): Simple, and Dangerous to Re-run

```python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE events (id INTEGER, event TEXT, ts TEXT)")

batch = [(1, "click", "2024-01-01T10:00:00"), (2, "view", "2024-01-01T10:01:00")]
conn.executemany("INSERT INTO events VALUES (?, ?, ?)", batch)
conn.commit()
print(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])   # 2

# Re-running the SAME batch (e.g. a retried job) ...
conn.executemany("INSERT INTO events VALUES (?, ?, ?)", batch)
conn.commit()
print(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])   # 4 -- duplicated!
```

Plain append is the right shape for immutable event/log tables loaded exactly once — but "loaded exactly once" is an operational promise, not something the `INSERT` statement itself guarantees. Any retry after a partial failure duplicates whatever already landed. This is the load strategy interviewers are testing when they ask "how do you make a pipeline idempotent" — see `concepts/06_idempotency_reliability.md`.

## 2. Upsert: `INSERT ... ON CONFLICT DO UPDATE`

If a row exists (matched by primary key), update it; otherwise insert it. This is the workhorse loading pattern for dimension/master data, and it's idempotent by construction — re-running the same upsert twice produces the same end state both times.

```python
conn.execute("""
    CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, updated TEXT)
""")
conn.execute("INSERT INTO products VALUES (1, 'Widget', 9.99, '2024-01-01')")
conn.commit()

merge_sql = """
    INSERT INTO products (id, name, price, updated) VALUES (?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET name=excluded.name, price=excluded.price, updated=excluded.updated
"""
update = (1, "Widget", 12.99, "2024-06-01")   # price changed

conn.execute(merge_sql, update); conn.commit()
conn.execute(merge_sql, update); conn.commit()   # re-run: no change
print(conn.execute("SELECT * FROM products").fetchall())
# [(1, 'Widget', 12.99, '2024-06-01')] -- same result both times
```

SQLite's older `INSERT OR REPLACE` achieves a similar effect by deleting-then-reinserting the conflicting row under the hood — fine for small dimension tables, but note it silently resets any column you don't explicitly re-supply to its default, which `ON CONFLICT DO UPDATE` does not.

## 3. Delete-Then-Insert (Partition Overwrite)

Delete a well-defined slice of the table (usually one partition, like a single day), then insert the fresh data for that slice. Idempotent because the delete makes the operation start from a known, empty state every time, regardless of what was there before.

```python
conn.execute("CREATE TABLE daily_sales (sale_date TEXT, region TEXT, amount REAL)")

def load_partition(conn, date, rows):
    conn.execute("DELETE FROM daily_sales WHERE sale_date = ?", (date,))
    conn.executemany("INSERT INTO daily_sales VALUES (?, ?, ?)", rows)
    conn.commit()

day1 = [("2024-01-01", "East", 1000), ("2024-01-01", "West", 1500)]
load_partition(conn, "2024-01-01", day1)
load_partition(conn, "2024-01-01", [("2024-01-01", "East", 1050), ("2024-01-01", "West", 1500)])  # corrected re-run
print(conn.execute("SELECT * FROM daily_sales").fetchall())
# [('2024-01-01', 'East', 1050.0), ('2024-01-01', 'West', 1500.0)] -- corrected, not duplicated
```

This is the standard pattern for date-partitioned fact tables in both warehouses and data lakes (Hive/Spark-style partition overwrite). It has one operational sharp edge worth naming: between the `DELETE` and the `INSERT` completing, the partition is briefly empty (or, worse, only partially reloaded if the job dies mid-insert) — any downstream reader querying at exactly that moment sees a hole that wasn't really there a second ago. Production loads guard against this with a transaction, a staging-then-atomic-swap pattern, or by writing to a new partition and swapping a pointer rather than deleting in place.

## 4. The MERGE Pattern, Generalized

`ON CONFLICT DO UPDATE` above *is* a MERGE for the single-table, single-key case. The general MERGE pattern (standard SQL `MERGE INTO`, or its equivalent in every major warehouse) does the same insert-or-update decision but is usually driven from a whole staged batch at once rather than one row at a time — which is exactly the staging pattern in section 5.

## 5. Bulk Loading Concepts

Three techniques that matter once row counts get large, independent of which strategy above you're using:

- **Batch inserts, not row-by-row.** `executemany()` (or a warehouse's native bulk-load/`COPY` command) batches network round-trips and transaction overhead; a loop of single-row `INSERT`s pays that overhead per row.
- **Batch the transaction.** Commit every N rows (or once at the end), not once per row — every `commit()` forces a durability sync.
- **Drop indexes/constraints before a big load, rebuild after.** Maintaining an index on every single inserted row is far more expensive than building it once over the finished table.

```python
import time
conn.execute("CREATE TABLE bulk_test (id INTEGER PRIMARY KEY, val TEXT)")
rows = [(i, f"value_{i}") for i in range(10000)]

start = time.perf_counter()
for r in rows:
    conn.execute("INSERT INTO bulk_test VALUES (?, ?)", r)
conn.commit()
row_by_row = time.perf_counter() - start

conn.execute("DELETE FROM bulk_test")
start = time.perf_counter()
conn.executemany("INSERT INTO bulk_test VALUES (?, ?)", rows)
conn.commit()
batched = time.perf_counter() - start

print(f"row-by-row: {row_by_row:.3f}s, executemany: {batched:.3f}s "
      f"({row_by_row / batched:.1f}x faster)")
# executemany is meaningfully faster -- exact multiple varies by machine
```

## 6. Staging Tables: The Production-Grade Default

Load raw data into a **staging** table first, then merge staging into the real **target** table in one deliberate step. This is the pattern every serious ETL/ELT pipeline converges on, and it's what `projects/mini_etl_pipeline.md` builds in full.

```
Source  -->  staging table (raw, disposable)  -->  MERGE  -->  target table (clean, durable)
```

```python
conn.execute("CREATE TABLE dim_customer (id INTEGER PRIMARY KEY, name TEXT, email TEXT, loaded TEXT)")
conn.execute("CREATE TABLE stg_customer (id INTEGER, name TEXT, email TEXT)")
conn.execute("INSERT INTO dim_customer VALUES (1, 'Alice', 'alice@v1.com', '2024-01-01')")
conn.commit()

conn.execute("DELETE FROM stg_customer")   # clean slate every run
conn.executemany("INSERT INTO stg_customer VALUES (?, ?, ?)", [
    (1, "Alice", "alice@v2.com"), (2, "Bob", "bob@v1.com"),
])
conn.commit()

conn.execute("""
    INSERT INTO dim_customer (id, name, email, loaded)
    SELECT id, name, email, '2024-06-01' FROM stg_customer
    WHERE true
    ON CONFLICT(id) DO UPDATE SET name=excluded.name, email=excluded.email, loaded=excluded.loaded
""")
conn.execute("DELETE FROM stg_customer")
conn.commit()
print(conn.execute("SELECT * FROM dim_customer").fetchall())
# [(1, 'Alice', 'alice@v2.com', '2024-06-01'), (2, 'Bob', 'bob@v1.com', '2024-06-01')]
```

Why this earns "production-grade" over a direct load: raw data is preserved for debugging until the merge succeeds; the merge itself is one auditable SQL statement instead of scattered application logic; data-quality checks have a natural place to live (between staging and merge); and staging tables are cheap to drop and recreate, which makes the whole load safely re-runnable from scratch.

## 7. Choosing a Strategy

| Strategy | Idempotent? | Best for |
|---|---|---|
| `INSERT` (append) | No | Immutable event/log tables, with dedup handled downstream |
| `INSERT OR REPLACE` | Yes | Small dimension tables |
| Delete + insert (partition overwrite) | Yes | Date-partitioned fact tables, corrections to a bounded slice |
| `MERGE` / `ON CONFLICT DO UPDATE` | Yes | SCD-style dimensions, large tables where a full partition rewrite is wasteful |
| Staging + merge | Yes | Anything production-facing — the default to reach for first |

Start with staging + merge unless there's a specific reason not to; treat plain append as something you only choose deliberately, for tables where every row really is immutable and duplicate-safety is handled somewhere else in the pipeline.

---

See `concepts/06_idempotency_reliability.md` for why idempotency matters beyond the load step alone, and `interview_questions/03_critique_and_debug.md`, Case 1, for the classic bug this file's section 1 sets up: a non-idempotent append that silently double-counts revenue on retry.
