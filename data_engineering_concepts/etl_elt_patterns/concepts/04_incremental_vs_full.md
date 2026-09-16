# Concept 04: Incremental vs. Full Load

**Covers:**
- Full load: what it costs, and when it's still the right answer
- Incremental by timestamp (watermark): the default workhorse
- Incremental by ID (high-water mark): simpler, but blind to updates
- Late-arriving data and how it interacts with a watermark
- Side-by-side trade-off comparison and a decision guide

*All Python below is real, runnable stdlib + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. Full Load: Correct, Expensive, and Sometimes Still Right

A full load deletes (or overwrites) the target and reloads every row from the source, every run.

```python
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL, updated_at TEXT)")
conn.executemany("INSERT INTO orders VALUES (?, ?, ?)", [
    (i, float(i * 10), f"2024-01-{i:02d}T00:00:00") for i in range(1, 11)
])
conn.commit()

def full_load(source_conn, target_rows_holder):
    rows = source_conn.execute("SELECT * FROM orders").fetchall()
    target_rows_holder.clear()
    target_rows_holder.extend(rows)
    return len(rows)

target = []
print(f"Loaded {full_load(conn, target)} rows")   # Loaded 10 rows -- re-reads all 10 even if only 1 changed
```

Its appeal is real: no dependency on a timestamp column existing or being trustworthy, no watermark state to manage, and it self-heals from almost any kind of source-side inconsistency (a bad update, a botched incremental run) because it always reflects the source's *current* full state. That's exactly why it's still the right default for small tables (under roughly 100K rows, as a rule of thumb) — the "expensive" part of "simple but expensive" never actually bites at that size.

The cost shows up as size grows: extraction time and source load scale with total row count, not with how much actually changed. A pipeline that adds 500 rows a day to a 50-million-row table pays the same full-table-scan cost every single day.

## 2. Incremental by Timestamp: The Default Workhorse

Track the max `updated_at` seen on the last successful run (the **watermark**), and pull only rows past it next time. Full mechanics and code are in `concepts/01_extraction_patterns.md`, section 2 — the piece worth adding here is what it takes to make the *load* side of this idempotent too, not just the extraction side:

```python
def get_watermark(wh, table):
    row = wh.execute("SELECT watermark FROM etl_watermarks WHERE table_name=?", (table,)).fetchone()
    return row[0] if row else "1970-01-01T00:00:00"

def set_watermark(wh, table, value):
    wh.execute("""INSERT INTO etl_watermarks VALUES (?, ?)
                  ON CONFLICT(table_name) DO UPDATE SET watermark=excluded.watermark""", (table, value))

wh = sqlite3.connect(":memory:")
wh.execute("CREATE TABLE etl_watermarks (table_name TEXT PRIMARY KEY, watermark TEXT)")
wh.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL, updated_at TEXT)")

def incremental_load(src, wh, table="orders"):
    wm = get_watermark(wh, table)
    rows = src.execute(f"SELECT * FROM {table} WHERE updated_at > ? ORDER BY updated_at", (wm,)).fetchall()
    if rows:
        wh.executemany(f"""INSERT INTO {table} VALUES (?, ?, ?)
                           ON CONFLICT(id) DO UPDATE SET amount=excluded.amount, updated_at=excluded.updated_at""", rows)
        set_watermark(wh, table, rows[-1][2])
        wh.commit()
    return len(rows)

print(incremental_load(conn, wh))   # 10 (first run: everything is "new")
print(incremental_load(conn, wh))   # 0  (second run: nothing changed)
```

Upserting into the target (rather than plain-appending) is what makes an incremental *load* idempotent — extraction alone being incremental doesn't guarantee that; see `concepts/03_loading_strategies.md` and `concepts/06_idempotency_reliability.md`.

## 3. Incremental by ID (High-Water Mark): Simpler, but Blind to Updates

For append-only sources with a monotonically increasing ID and no reliable `updated_at`, tracking `max(id)` works and needs no timestamp at all:

```python
def incremental_by_id(src, hwm):
    rows = src.execute("SELECT * FROM orders WHERE id > ? ORDER BY id", (hwm,)).fetchall()
    new_hwm = rows[-1][0] if rows else hwm
    return rows, new_hwm

rows, hwm = incremental_by_id(conn, 0)
print(f"loaded {len(rows)}, hwm={hwm}")   # loaded 10, hwm=10

conn.execute("UPDATE orders SET amount = 999.0 WHERE id = 1")   # a real update to an old row
conn.commit()
rows, hwm = incremental_by_id(conn, hwm)
print(f"loaded {len(rows)} (the update to id=1 was MISSED)")   # loaded 0
```

This is a real, common failure mode, not a contrived edge case: ID-based incremental extraction is structurally incapable of noticing that an already-extracted row changed, because the `WHERE id > ?` filter never looks at old IDs again. It's the right choice only when the source table is genuinely append-only (event logs, immutable audit trails) — the moment updates to historical rows are possible, this silently drops them, which is exactly the kind of watermark bug drilled in `interview_questions/03_critique_and_debug.md`.

## 4. Late-Arriving Data and the Watermark

A **late-arriving fact** is a row whose business timestamp is old, but which only reaches the source (and therefore the pipeline) after the watermark has already moved past that point — a delayed insert, an offline mobile client syncing hours later, a batch job that ran out of order.

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

orders = [
    {"id": 101, "created_at": "2024-01-05T10:00:00"},
    {"id": 102, "created_at": "2024-01-03T08:00:00"},   # arrived late
]
on_time, late, new_wm = process_with_late_data(orders, "2024-01-04T00:00:00")
print(f"on_time={len(on_time)} late={[o['id'] for o in late]}")
# on_time=1 late=[102]
```

The watermark itself must advance based on `created_at`/`updated_at` values actually seen, not based on wall-clock "now" — advancing it by wall-clock time would let the watermark silently sail past a late row that hasn't arrived yet, causing the next run's `WHERE updated_at > watermark` filter to skip it forever once it does arrive. Flagging late rows explicitly (rather than quietly mixing them into "on time") lets downstream consumers decide whether an already-published report needs to be reopened — the full architecture question is worked in `interview_questions/01_worked_scenarios.md`.

## 5. Comparing the Approaches

| Approach | Detects updates? | Detects deletes? | Complexity | Typical latency |
|---|---|---|---|---|
| Full load | Yes | Yes | Low | High |
| Incremental (timestamp) | Yes | No | Medium | Medium |
| Incremental (ID) | No | No | Low | Medium |
| CDC (`concepts/05_change_data_capture.md`) | Yes | Yes | High | Low |

**Rules of thumb:**
- Small tables (roughly under 100K rows): full load is genuinely fine — don't build incremental machinery you don't need yet.
- Medium-to-large tables with updates: incremental by timestamp is the default.
- Strictly append-only logs: incremental by ID, for its simplicity.
- Large tables needing near-real-time freshness, or where deletes must be captured: CDC.

---

See `concepts/05_change_data_capture.md` for the approach that closes both gaps in this table at once (updates *and* deletes, with much lower latency), at the cost of real infrastructure complexity.
