# Concept 05: Change Data Capture (CDC)

**Covers:**
- Why watermark-based incremental extraction isn't enough (the delete problem)
- Query-based CDC (polling with a version/timestamp column)
- Trigger-based CDC (the database writes its own change log)
- Log-based CDC (reading the WAL/binlog directly — Debezium, AWS DMS)
- Handling deletes, ordering, and schema changes in a CDC stream
- Trade-off comparison and when to reach for each

*All Python below is real, runnable stdlib + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

This file exists as its own topic — rather than being folded into extraction or incremental-load — because CDC keeps coming up as its own named interview topic ("how does CDC work," "log-based vs. trigger-based") independent of the broader incremental-vs-full framing in `concepts/04_incremental_vs_full.md`. `practice/coding_problems.md`'s CDC problem exercises the log-based flavor end to end.

---

## 1. The Gap Watermarks Can't Close

`concepts/04_incremental_vs_full.md` covers incremental-by-timestamp in depth. It has one structural blind spot worth restating precisely: a `WHERE updated_at > watermark` query can only ever see rows that **still exist** in the source. A row that gets `DELETE`d between one run and the next produces *no row at all* for the query to find — there's nothing to filter on, because the thing you'd filter on is gone. Incremental-by-timestamp is fundamentally incapable of detecting deletes, no matter how the watermark logic is tuned.

**Change Data Capture** is the general name for a family of techniques that capture *every* change — insert, update, **and delete** — as an explicit, ordered stream of events, rather than inferring "what changed" by diffing snapshots. There are three ways to build that stream, each with a different cost to the source system and a different latency/completeness trade-off.

## 2. Query-Based CDC: Polling With a Version Column

This is watermark-based incremental extraction, reframed as "the cheapest form of CDC" — poll on a schedule, compare against a stored high-water mark. It's what section 2 of `concepts/04_incremental_vs_full.md` already builds, so it isn't repeated here in full; the reason it's *called* CDC at all in some contexts is that "capturing changes by polling" is still change capture, just query-based instead of log-based.

```python
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance REAL, version INTEGER, updated_at TEXT)")
conn.execute("INSERT INTO accounts VALUES (1, 100.0, 1, '2024-01-01T00:00:00')")
conn.commit()

def poll_changes(conn, last_version):
    rows = conn.execute("SELECT * FROM accounts WHERE version > ? ORDER BY version", (last_version,)).fetchall()
    return rows, (rows[-1][2] if rows else last_version)

rows, v = poll_changes(conn, 0)
print(rows)   # [(1, 100.0, 1, '2024-01-01T00:00:00')]
```

Its two structural weaknesses, both worth naming explicitly in an interview: it still cannot see deletes (same gap as timestamp-based incremental — deleting the row also deletes the version number that would have flagged the change), and it only ever sees the **latest** state between polls — if a row is updated twice between two poll runs, the intermediate value is invisible. If an audit trail needs every intermediate state, query-based CDC can't provide it no matter how frequently it polls.

## 3. Trigger-Based CDC: The Database Writes Its Own Change Log

A database trigger fires synchronously on every `INSERT`/`UPDATE`/`DELETE` against the source table and writes a row describing that change into a separate change-log table, which the pipeline then reads (and clears/marks-as-processed) independently.

```python
conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, status TEXT)")
conn.execute("""
    CREATE TABLE customers_changelog (
        change_id INTEGER PRIMARY KEY AUTOINCREMENT,
        op TEXT, id INTEGER, name TEXT, status TEXT, changed_at TEXT
    )
""")
conn.executescript("""
    CREATE TRIGGER trg_customers_insert AFTER INSERT ON customers BEGIN
        INSERT INTO customers_changelog (op, id, name, status, changed_at)
        VALUES ('INSERT', NEW.id, NEW.name, NEW.status, datetime('now'));
    END;
    CREATE TRIGGER trg_customers_update AFTER UPDATE ON customers BEGIN
        INSERT INTO customers_changelog (op, id, name, status, changed_at)
        VALUES ('UPDATE', NEW.id, NEW.name, NEW.status, datetime('now'));
    END;
    CREATE TRIGGER trg_customers_delete AFTER DELETE ON customers BEGIN
        INSERT INTO customers_changelog (op, id, name, status, changed_at)
        VALUES ('DELETE', OLD.id, OLD.name, OLD.status, datetime('now'));
    END;
""")

conn.execute("INSERT INTO customers VALUES (1, 'Alice', 'active')")
conn.execute("UPDATE customers SET status='inactive' WHERE id=1")
conn.execute("DELETE FROM customers WHERE id=1")
conn.commit()

for row in conn.execute("SELECT op, id, name, status FROM customers_changelog ORDER BY change_id"):
    print(row)
# ('INSERT', 1, 'Alice', 'active')
# ('UPDATE', 1, 'Alice', 'inactive')
# ('DELETE', 1, 'Alice', 'inactive')
```

Unlike query-based polling, every single change is captured — including the delete, and every intermediate update. The cost is real and lands directly on the source system: every write to `customers` now also performs a write to `customers_changelog`, inside the same transaction, adding latency and lock contention to the OLTP system's normal write path. Trigger-based CDC also needs its own maintenance — the changelog table grows forever unless something prunes rows the pipeline has already consumed, and a trigger must be written and kept in sync for every table that needs capturing.

## 4. Log-Based CDC: Reading the Transaction Log Directly

Every transactional database already keeps an internal, append-only log of every committed change for its own crash-recovery purposes — the write-ahead log (WAL) in Postgres, the binary log (binlog) in MySQL, redo logs in Oracle. Log-based CDC tools (Debezium, AWS DMS, Oracle GoldenGate) read that log directly and turn it into a stream of change events, without adding any triggers or extra writes to the source tables at all.

```python
# Simulating a decoded change-log stream (what a tool like Debezium hands you,
# already parsed from the database's internal WAL/binlog format)
change_log = [
    {"op": "INSERT", "id": 1, "data": {"name": "Alice", "status": "active"}},
    {"op": "UPDATE", "id": 1, "data": {"name": "Alice", "status": "inactive"}},
    {"op": "INSERT", "id": 2, "data": {"name": "Bob", "status": "active"}},
    {"op": "DELETE", "id": 2, "data": None},
]

def apply_cdc_stream(change_log):
    """Replay a CDC stream to reconstruct current state."""
    state = {}
    for event in change_log:
        op, eid = event["op"], event["id"]
        if op in ("INSERT", "UPDATE"):
            state[eid] = event["data"]
        elif op == "DELETE":
            state.pop(eid, None)   # tombstone: the row is gone, not just "unchanged"
    return state

print(apply_cdc_stream(change_log))
# {1: {'name': 'Alice', 'status': 'inactive'}}   -- id=2 correctly absent, not just stale
```

This is the lowest-impact, lowest-latency option: the source database does no extra work at all beyond what it was already doing (the WAL/binlog exists regardless of CDC), and changes are visible to the pipeline within roughly the log's own replication lag — typically sub-second to a few seconds, versus a polling interval that's usually minutes. It's also the highest-complexity option to operate: it needs a dedicated CDC connector/agent, direct (and usually privileged) access to the database's internal log format, and — because logs are eventually recycled/compacted by the database — a mechanism to track exactly how far the CDC process has read (its own kind of watermark, called an **offset** or **LSN/binlog position** depending on the database) so a restart resumes from the right place instead of re-reading everything or silently skipping a gap.

## 5. Handling Deletes, Ordering, and Schema Changes

**Deletes (tombstones).** A CDC delete event should be applied as an explicit removal downstream, not ignored — the naive mistake is to only handle `INSERT`/`UPDATE` events and let deleted rows linger forever in the target. Many warehouse targets implement this as a **soft delete** (flag the row `is_deleted = true`, keep it for audit) rather than a hard delete, exactly the same trade-off named for the "account deletion" curveball in `data_modeling/interview_questions/01_worked_scenarios.md`.

**Ordering.** Events for the *same key* must be applied in the order they happened — replaying an `UPDATE` before the `INSERT` it depends on (or a later update before an earlier one) produces a wrong final state. Log-based CDC preserves this ordering per-partition/per-key because the underlying transaction log is itself strictly ordered; a naive multi-consumer setup that processes events for the same key out of order across parallel workers is a real, common way to reintroduce a correctness bug that log-based CDC was supposed to eliminate.

**Schema changes.** If the source adds, removes, or retypes a column mid-stream, every downstream consumer of the CDC stream needs to handle both the old and new shape of the event during the transition — this is exactly the "transformation breaks when the source adds a column" bug in `interview_questions/03_critique_and_debug.md`, applied to a live stream instead of a batch extract, where there's no natural "next run" boundary to redeploy a fix before more bad data arrives.

## 6. Choosing an Approach

| Approach | Source impact | Latency | Detects deletes? | Sees every intermediate change? | Operational complexity |
|---|---|---|---|---|---|
| Query-based (polling) | Read load only | Minutes | No | No | Low |
| Trigger-based | Extra write per source write | Seconds–minutes | Yes | Yes | Medium |
| Log-based (WAL/binlog) | None beyond existing log | Sub-second–seconds | Yes | Yes | High |

Reach for query-based polling by default — it's what `concepts/04_incremental_vs_full.md` already covers, and it's sufficient whenever deletes don't matter and near-real-time isn't required. Reach for trigger-based CDC when deletes must be captured but standing up dedicated CDC infrastructure isn't justified yet. Reach for log-based CDC when latency needs to be low, deletes and every intermediate state must be captured, and the source-system impact of triggers (extra writes on the hot path) is unacceptable — which is also, not coincidentally, most large-scale production CDC in practice.

---

See `practice/coding_problems.md` for a full worked CDC system-design problem (replaying an ordered change stream into consistent target state), and `interview_questions/01_worked_scenarios.md` for a complete "design a CDC pipeline from an OLTP database" walkthrough.
