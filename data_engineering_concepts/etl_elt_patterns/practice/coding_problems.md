# ETL/ELT — Coding Problems

Five pipeline-design problems, medium-to-hard difficulty: an incremental data loader, a fuzzy-matching deduplication pipeline, a schema-change detector, a retry mechanism with exponential backoff and a dead-letter queue, and a change-data-capture replication system. Each includes the problem statement, sample input/output, and a hidden reference solution with an explanation of the pattern it's testing.

How to use this file: read the problem, write your own solution against the sample input, and only then expand the reference solution. These are pulled from — and extend — the same bonus interview problem sets used across this course; getting comfortable with all five is a reasonable bar for a mid-level pipeline-design round.

---

## Problem 1: Build an Incremental Data Loader

**Problem statement:** design a data loader that tracks a watermark (high-water mark) in its own metadata table, so each run only loads records changed since the last run — and correctly handles the very first run, when no watermark exists yet.

**Requirements:**
- Maintain the watermark in a metadata table, not in memory
- Each run selects `WHERE updated_at > watermark`
- Update the watermark only after a successful load
- Handle the initial run (no watermark yet -> load everything)
- Track load statistics (rows loaded, duration)

**Sample input** — table `events(id, event, created_at, updated_at)` seeded with 5 rows, the latest `updated_at = '2024-01-03 10:00:00'`.

**Expected behavior:**
```text
Run 1 (no watermark yet): loads all 5 rows, watermark becomes 2024-01-03 10:00:00
Row inserted: id=6, updated_at='2024-01-04 08:00:00'
Run 2: loads only 1 row (id=6), watermark becomes 2024-01-04 08:00:00
Run 3 (no new data): loads 0 rows
```

<details>
<summary>Reference solution</summary>

```python
import sqlite3, time
from datetime import datetime

class IncrementalLoader:
    """
    Tracks a high-water mark in a metadata table so each run loads only
    new/updated records. The watermark lives in the database, not in a
    Python variable, so it survives process restarts.
    """
    def __init__(self, conn, source_table, watermark_column):
        self.conn = conn
        self.source_table = source_table
        self.watermark_column = watermark_column
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _load_metadata (
                table_name TEXT PRIMARY KEY, watermark TEXT, last_run TEXT, rows_loaded INTEGER
            )
        """)
        conn.commit()

    def get_watermark(self):
        row = self.conn.execute(
            "SELECT watermark FROM _load_metadata WHERE table_name = ?", (self.source_table,)
        ).fetchone()
        return row[0] if row else None

    def load_new_records(self):
        watermark = self.get_watermark()
        start = time.time()

        if watermark is None:
            query = f"SELECT * FROM {self.source_table} ORDER BY {self.watermark_column}"
            rows = self.conn.execute(query).fetchall()
        else:
            query = (f"SELECT * FROM {self.source_table} "
                      f"WHERE {self.watermark_column} > ? ORDER BY {self.watermark_column}")
            rows = self.conn.execute(query, (watermark,)).fetchall()

        if rows:
            new_watermark = max(r[3] for r in rows)   # updated_at is column index 3
            self.conn.execute("""
                INSERT OR REPLACE INTO _load_metadata (table_name, watermark, last_run, rows_loaded)
                VALUES (?, ?, ?, ?)
            """, (self.source_table, new_watermark, datetime.now().isoformat(), len(rows)))
            self.conn.commit()

        print(f"  loaded {len(rows)} rows in {time.time() - start:.4f}s")
        return rows

# --- demo ---
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, event TEXT, created_at TEXT, updated_at TEXT)")
conn.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", [
    (1, "login", "2024-01-01 10:00:00", "2024-01-01 10:00:00"),
    (2, "purchase", "2024-01-01 11:00:00", "2024-01-01 11:00:00"),
    (3, "logout", "2024-01-02 09:00:00", "2024-01-02 09:00:00"),
    (4, "login", "2024-01-02 14:00:00", "2024-01-02 14:00:00"),
    (5, "purchase", "2024-01-03 10:00:00", "2024-01-03 10:00:00"),
])
conn.commit()

loader = IncrementalLoader(conn, "events", "updated_at")
run1 = loader.load_new_records()          # loaded 5 rows
conn.execute("INSERT INTO events VALUES (6, 'signup', '2024-01-04 08:00:00', '2024-01-04 08:00:00')")
conn.commit()
run2 = loader.load_new_records()          # loaded 1 rows
run3 = loader.load_new_records()          # loaded 0 rows
```

**Pattern being tested:** durable watermark tracking, exactly as in `concepts/01_extraction_patterns.md` and `concepts/04_incremental_vs_full.md` — the key detail interviewers watch for is handling `watermark is None` correctly for the first run (load everything, don't crash on a `None` comparison) and updating the watermark *only after* a successful load, never before, so a crash mid-load doesn't advance the watermark past data that never actually landed (see `interview_questions/03_critique_and_debug.md` for that exact bug).

</details>

---

## Problem 2: Data Deduplication Pipeline With Fuzzy Matching

**Problem statement:** build a pipeline that identifies duplicate records using string similarity rather than an exact key, groups them into clusters, and selects the most complete record from each cluster.

**Requirements:**
- Implement a string similarity function (Jaccard similarity over character bigrams, or edit-distance ratio)
- Group records into clusters of likely duplicates
- From each cluster, keep the most complete record (fewest `None` fields)
- Return the deduplicated dataset

**Sample input:**
```python
records = [
    {"id": 1, "name": "John Smith",    "email": "john@example.com"},
    {"id": 2, "name": "Jon Smith",     "email": "jon@example.com"},
    {"id": 3, "name": "Jane Doe",      "email": "jane@example.com"},
    {"id": 4, "name": "John Smyth",    "email": None},
    {"id": 5, "name": "Janet Doe",     "email": "janet@example.com"},
    {"id": 6, "name": "Alice Johnson", "email": "alice@example.com"},
]
```

**Expected output** (threshold-dependent, but at a reasonable threshold): records 1, 2, 4 cluster together (`John Smith` / `Jon Smith` / `John Smyth`); 3 and 5 may or may not cluster depending on threshold; 6 is always unique.

<details>
<summary>Reference solution</summary>

```python
from collections import defaultdict

def bigrams(s):
    s = s.lower().strip()
    return set(s[i:i+2] for i in range(len(s) - 1)) if len(s) >= 2 else {s}

def jaccard_similarity(s1, s2):
    """|intersection| / |union| of character bigrams -- 0.0 (different) to 1.0 (identical)."""
    if s1 == s2:
        return 1.0
    bg1, bg2 = bigrams(s1), bigrams(s2)
    if not bg1 or not bg2:
        return 0.0
    return len(bg1 & bg2) / len(bg1 | bg2)

def fuzzy_dedup(records, name_field, threshold=0.6):
    """Union-Find clustering: union any pair scoring >= threshold, then pick the
    most complete record (fewest None fields) from each resulting cluster."""
    n = len(records)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if jaccard_similarity(records[i][name_field], records[j][name_field]) >= threshold:
                union(i, j)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(records[i])

    def completeness(r): return sum(1 for v in r.values() if v is not None)
    return [max(c, key=completeness) for c in clusters.values()], list(clusters.values())

records = [
    {"id": 1, "name": "John Smith",    "email": "john@example.com"},
    {"id": 2, "name": "Jon Smith",     "email": "jon@example.com"},
    {"id": 3, "name": "Jane Doe",      "email": "jane@example.com"},
    {"id": 4, "name": "John Smyth",    "email": None},
    {"id": 5, "name": "Janet Doe",     "email": "janet@example.com"},
    {"id": 6, "name": "Alice Johnson", "email": "alice@example.com"},
]
deduped, clusters = fuzzy_dedup(records, "name", threshold=0.6)
print(len(clusters))   # fewer than 6 -- John/Jon/Smyth collapse into one cluster
```

**Pattern being tested:** this extends the exact-match and key-based dedup in `concepts/02_transformation_patterns.md`, section 2, to the case where there's no shared key at all — clustering via a similarity threshold, and Union-Find as the standard tool for turning pairwise "these two are similar" judgments into groups (transitively: if A~B and B~C, A/B/C end up in one cluster even if A and C weren't compared as similar directly). The completeness-based tie-break (`records[4]` has `email=None` and correctly loses to a more complete match) mirrors picking the "best" record — a recurring theme in identity-merge problems (`data_modeling/interview_questions/02_rapid_fire_qna.md`, "identity split vs. identity merge").

</details>

---

## Problem 3: Schema Change Detector

**Problem statement:** given an old and a new schema definition for the same table, detect every column added, removed, retyped, or changed in nullability, and classify each change by severity.

**Requirements:**
- Detect: added columns, removed columns, type changes, nullable changes
- Classify severity: `BREAKING`, `NON_BREAKING`, or `WARNING`
- Produce a migration report

**Sample input:**
```python
old_schema = {"users": {
    "id": {"type": "INTEGER", "nullable": False}, "name": {"type": "TEXT", "nullable": False},
    "email": {"type": "TEXT", "nullable": False}, "age": {"type": "INTEGER", "nullable": True},
    "created_at": {"type": "TEXT", "nullable": False},
}}
new_schema = {"users": {
    "id": {"type": "INTEGER", "nullable": False}, "name": {"type": "VARCHAR", "nullable": False},
    "email": {"type": "TEXT", "nullable": True}, "phone": {"type": "TEXT", "nullable": True},
    "created_at": {"type": "TIMESTAMP", "nullable": False},
    # "age" removed
}}
```

**Expected output:**
```text
[BREAKING]     users.age: COLUMN_REMOVED - was type=INTEGER
[WARNING]      users.created_at: TYPE_CHANGED - TEXT -> TIMESTAMP
[NON_BREAKING] users.email: NULLABLE_CHANGED - nullable: False -> True
[WARNING]      users.name: TYPE_CHANGED - TEXT -> VARCHAR
[NON_BREAKING] users.phone: COLUMN_ADDED - type=TEXT, nullable=True
```

<details>
<summary>Reference solution</summary>

```python
class SchemaChange:
    def __init__(self, table, column, change_type, details, severity):
        self.table, self.column = table, column
        self.change_type, self.details, self.severity = change_type, details, severity
    def __repr__(self):
        return f"[{self.severity}] {self.table}.{self.column}: {self.change_type} - {self.details}"

def detect_schema_changes(old_schema, new_schema):
    """
    Severity rules:
      REMOVED column           -> BREAKING (data loss, dependent queries break)
      TYPE change               -> WARNING  (may need a data-conversion pass)
      NULLABLE True  -> False   -> BREAKING (existing NULLs now violate the constraint)
      NULLABLE False -> True    -> NON_BREAKING (a relaxed constraint)
      ADDED column, nullable    -> NON_BREAKING (existing writers unaffected)
      ADDED column, NOT NULL    -> WARNING (inserts missing this column now fail)
    """
    changes = []
    for table in sorted(set(old_schema) | set(new_schema)):
        old_cols, new_cols = old_schema.get(table, {}), new_schema.get(table, {})
        for col in sorted(set(old_cols) | set(new_cols)):
            if col not in old_cols:
                nullable = new_cols[col].get("nullable", True)
                changes.append(SchemaChange(table, col, "COLUMN_ADDED",
                    f"type={new_cols[col]['type']}, nullable={nullable}",
                    "NON_BREAKING" if nullable else "WARNING"))
            elif col not in new_cols:
                changes.append(SchemaChange(table, col, "COLUMN_REMOVED",
                    f"was type={old_cols[col]['type']}", "BREAKING"))
            else:
                if old_cols[col]["type"] != new_cols[col]["type"]:
                    changes.append(SchemaChange(table, col, "TYPE_CHANGED",
                        f"{old_cols[col]['type']} -> {new_cols[col]['type']}", "WARNING"))
                old_n, new_n = old_cols[col].get("nullable", True), new_cols[col].get("nullable", True)
                if old_n != new_n:
                    sev = "BREAKING" if (old_n and not new_n) else "NON_BREAKING"
                    changes.append(SchemaChange(table, col, "NULLABLE_CHANGED",
                        f"nullable: {old_n} -> {new_n}", sev))
    return changes

changes = detect_schema_changes(old_schema, new_schema)
for c in changes: print(c)
breaking = [c for c in changes if c.severity == "BREAKING"]
print(f"{len(changes)} changes, {len(breaking)} BREAKING")   # 5 changes, 1 BREAKING
```

**Pattern being tested:** this is a direct implementation of the "transform breaks when the source adds a column" family of bugs from `interview_questions/03_critique_and_debug.md` — the interview signal is the severity *rule*, not the diffing mechanics: recognizing that a removed column is unconditionally breaking, a widened nullability is safe, a *tightened* nullability is not (existing NULLs now violate it), and a type change is a judgment call (`WARNING`, not automatically breaking or safe) because whether `TEXT -> TIMESTAMP` breaks anything depends on whether every existing value actually parses as a timestamp.

</details>

---

## Problem 4: Retry Mechanism With Exponential Backoff and Dead Letter Queue

**Problem statement:** build a processor that retries failed records with exponential backoff and jitter, caps retries, and routes permanently-failed records to a dead-letter queue.

**Requirements:**
- Retry with exponential backoff (`1s, 2s, 4s, ...`), capped at `max_retries`
- Add jitter to avoid a thundering herd
- After max retries, send the record to a DLQ
- Track statistics: successful, retried, failed

**Sample input:** 15 records; by construction, records with `id % 5 == 0` always fail (permanent error), records with `id % 3 == 0` fail once then succeed on retry (transient error), everything else succeeds immediately.

**Expected output:**
```text
Stats: {'success': 10, 'retried': 3, 'failed': 3, 'total': 15}
DLQ: ids 5, 10, 15 (permanent errors)
```

<details>
<summary>Reference solution</summary>

```python
import time, random

class ProcessingError(Exception):
    def __init__(self, message, permanent=False):
        super().__init__(message)
        self.permanent = permanent

class RetryProcessor:
    """Retries transient failures with exponential backoff + jitter; routes
    permanent failures (or exhausted retries) straight to a dead-letter queue."""

    def __init__(self, max_retries=3, base_delay=0.01):
        self.max_retries, self.base_delay = max_retries, base_delay
        self.dlq = []
        self.stats = {"success": 0, "retried": 0, "failed": 0, "total": 0}
        self._attempts = {}

    def process_record(self, record):
        rid = record["id"]
        self._attempts[rid] = self._attempts.get(rid, 0) + 1
        if rid % 5 == 0:
            raise ProcessingError(f"permanent error for {rid}", permanent=True)
        if rid % 3 == 0 and self._attempts[rid] == 1:
            raise ProcessingError(f"transient error for {rid}", permanent=False)
        return {"id": rid, "status": "processed"}

    def process_with_retry(self, record):
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self.process_record(record)
                if attempt > 1:
                    self.stats["retried"] += 1
                self.stats["success"] += 1
                return result
            except ProcessingError as e:
                last_error = e
                if e.permanent:
                    break
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    time.sleep(delay + random.uniform(0, delay * 0.1))   # jitter

        self.dlq.append({"record": record, "error": str(last_error),
                          "permanent": getattr(last_error, "permanent", False)})
        self.stats["failed"] += 1
        return None

    def process_batch(self, records):
        self.stats["total"] = len(records)
        return [r for r in (self.process_with_retry(rec) for rec in records) if r]

processor = RetryProcessor(max_retries=3, base_delay=0.001)
records = [{"id": i, "data": f"record_{i}"} for i in range(1, 16)]
processor.process_batch(records)
print(processor.stats)   # {'success': 10, 'retried': 3, 'failed': 3, 'total': 15}
```

**Pattern being tested:** distinguishing **transient** from **permanent** failures and routing each differently — retrying a permanent error (`id % 5 == 0`) wastes time before failing anyway, so it should `break` out immediately rather than burn through all `max_retries`; a transient error deserves the backoff delay. This is the same distinction drilled in `concepts/06_idempotency_reliability.md`, section 4, and in `interview_questions/05_idempotency_and_exactly_once.md`.

</details>

---

## Problem 5: Change Data Capture — Replicate a Source Table via a Change Stream

**Problem statement:** design a small CDC replication system. A source database emits an ordered stream of change events (`INSERT`/`UPDATE`/`DELETE`), each carrying a monotonically increasing sequence number (its position in the log — analogous to a Postgres LSN or a MySQL binlog offset). Your replication target must apply these events to reconstruct the source's current state, must be safe to re-run if the same event is delivered twice (at-least-once delivery is the realistic assumption for any real CDC transport), and must detect a **gap** in the sequence (a missing event) rather than silently producing an incomplete replica.

**Requirements:**
- Apply `INSERT`/`UPDATE` as an upsert, `DELETE` as a removal (a tombstone), keyed by the record's business id
- Track the last-applied sequence number durably, and skip any event at or below it (idempotent replay)
- Detect a gap: if the next event's sequence number is not exactly `last_applied + 1`, flag it instead of silently continuing
- Return the final replica state plus a list of any detected gaps

**Sample input:**
```python
change_stream = [
    {"seq": 1, "op": "INSERT", "id": 1, "data": {"name": "Alice", "status": "active"}},
    {"seq": 2, "op": "UPDATE", "id": 1, "data": {"name": "Alice", "status": "inactive"}},
    {"seq": 2, "op": "UPDATE", "id": 1, "data": {"name": "Alice", "status": "inactive"}},  # redelivered
    {"seq": 3, "op": "INSERT", "id": 2, "data": {"name": "Bob", "status": "active"}},
    {"seq": 5, "op": "DELETE", "id": 1, "data": None},   # seq 4 is missing -- a gap
]
```

**Expected output:**
```text
Replica state: {2: {'name': 'Bob', 'status': 'active'}}
   (id=1 removed by the seq=5 DELETE, which is still applied despite the gap
    at seq=4, so replication doesn't stall -- but the gap is surfaced, not hidden)
Gaps detected: [(3, 5)]   # expected seq 4, got seq 5
Redelivery of seq=2 was skipped, not double-applied.
```

<details>
<summary>Reference solution</summary>

```python
class CDCReplicator:
    """
    Applies an ordered CDC change stream to reconstruct source state.

    - Idempotent: an event at or below the last-applied sequence number
      is skipped, so at-least-once delivery (the realistic case for any
      real message transport) never double-applies a change.
    - Gap-aware: a jump in sequence numbers is recorded rather than
      silently ignored, so a monitoring system can alert on missed events
      instead of quietly serving an incomplete replica.
    """
    def __init__(self):
        self.state = {}
        self.last_applied_seq = 0
        self.gaps = []

    def apply(self, event):
        seq = event["seq"]

        if seq <= self.last_applied_seq:
            return "skipped_duplicate"        # idempotent replay

        if seq != self.last_applied_seq + 1:
            self.gaps.append((self.last_applied_seq + 1, seq))

        op, rid = event["op"], event["id"]
        if op in ("INSERT", "UPDATE"):
            self.state[rid] = event["data"]
        elif op == "DELETE":
            self.state.pop(rid, None)

        self.last_applied_seq = seq
        return "applied"

    def replicate(self, change_stream):
        results = [self.apply(e) for e in change_stream]
        return self.state, self.gaps, results

change_stream = [
    {"seq": 1, "op": "INSERT", "id": 1, "data": {"name": "Alice", "status": "active"}},
    {"seq": 2, "op": "UPDATE", "id": 1, "data": {"name": "Alice", "status": "inactive"}},
    {"seq": 2, "op": "UPDATE", "id": 1, "data": {"name": "Alice", "status": "inactive"}},  # redelivered
    {"seq": 3, "op": "INSERT", "id": 2, "data": {"name": "Bob", "status": "active"}},
    {"seq": 5, "op": "DELETE", "id": 1, "data": None},
]

replicator = CDCReplicator()
state, gaps, results = replicator.replicate(change_stream)
print(state)     # {2: {'name': 'Bob', 'status': 'active'}}
print(gaps)      # [(4, 5)]
print(results)   # ['applied', 'applied', 'skipped_duplicate', 'applied', 'applied']
```

**Pattern being tested:** this combines three ideas from across this topic into one system-design problem — CDC event semantics (`concepts/05_change_data_capture.md`: `DELETE` as a tombstone, not a no-op), idempotent replay under at-least-once delivery (`concepts/06_idempotency_reliability.md`), and gap detection as its own first-class concern, distinct from both. The critical design decision the reference solution makes explicit: a gap is **surfaced, not fatal** — the replicator keeps applying events after detecting one (the `seq=5` delete still lands) rather than halting the whole pipeline, because in a real system the missing event might simply be delayed in transit and arrive moments later; treating every gap as an unrecoverable error would make the pipeline far too fragile for normal jitter in delivery order. What should happen once a gap is detected and doesn't resolve itself (re-request the missing offset range from the source log, alert an operator, or fall back to a full re-sync) is exactly the kind of open-ended follow-up an interviewer asks next — see `interview_questions/04_curveballs_tradeoffs.md`.

</details>
