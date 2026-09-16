# Concept 06: Idempotency and Reliability

**Covers:**
- What "idempotent" actually means for a pipeline, precisely
- Idempotency patterns: delete-then-insert, partition overwrite, merge/upsert
- Checkpointing: resuming from failure instead of restarting from scratch
- Retry with exponential backoff and jitter
- Dead-letter queues for records that fail processing
- Putting it all together: a small idempotent pipeline class

*All Python below is real, runnable stdlib + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. What Makes a Pipeline Idempotent

A pipeline is **idempotent** if running it again, with the same input, from the same starting state, always produces the same end result — whether it's run once or ten times.

```python
import sqlite3
data = [(1, "Alice", 100), (2, "Bob", 200)]

# Non-idempotent: plain append
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE t (id INT, name TEXT, amount REAL)")
for run in range(1, 4):
    conn.executemany("INSERT INTO t VALUES (?, ?, ?)", data)
    conn.commit()
    print(f"non-idempotent run {run}: {conn.execute('SELECT COUNT(*) FROM t').fetchone()[0]} rows")
# 2, 4, 6 -- duplicates accumulate

# Idempotent: upsert on a primary key
conn2 = sqlite3.connect(":memory:")
conn2.execute("CREATE TABLE t (id INT PRIMARY KEY, name TEXT, amount REAL)")
for run in range(1, 4):
    conn2.executemany("INSERT OR REPLACE INTO t VALUES (?, ?, ?)", data)
    conn2.commit()
    print(f"idempotent run {run}: {conn2.execute('SELECT COUNT(*) FROM t').fetchone()[0]} rows")
# 2, 2, 2 -- safe to re-run
```

This matters because batch jobs *will* fail partway through and get retried — that isn't a hypothetical edge case, it's the normal operating condition of any pipeline that runs often enough for long enough. A pipeline whose correctness depends on "this never fails mid-run" is a pipeline that will eventually double-count revenue, exactly the bug in `interview_questions/03_critique_and_debug.md`, Case 1.

## 2. Idempotency Patterns, by Load Strategy

These are the same patterns from `concepts/03_loading_strategies.md`, viewed specifically through "does re-running this change the answer":

**Delete-then-insert**, scoped to exactly what this run is responsible for:

```python
conn.execute("CREATE TABLE daily_metrics (metric_date TEXT, metric_name TEXT, value REAL, PRIMARY KEY (metric_date, metric_name))")

def load_daily_metrics(conn, date, metrics):
    conn.execute("DELETE FROM daily_metrics WHERE metric_date = ?", (date,))
    conn.executemany("INSERT INTO daily_metrics VALUES (?, ?, ?)", [(date, k, v) for k, v in metrics.items()])
    conn.commit()

for run in range(1, 4):
    load_daily_metrics(conn, "2024-01-01", {"revenue": 10000, "orders": 150})
    print(conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0])
# 2, 2, 2 -- always the same row count, regardless of how many times this runs
```

**Partition overwrite** — the same idea at the granularity of a whole physical partition, common in lake/warehouse tables partitioned by date.

**Merge/upsert** — keyed on a natural business key, so re-applying the same batch lands on exactly the same rows it landed on before (section 1's example).

The common thread across all three: the operation is defined in terms of "replace what should exist for this scope" rather than "add this to whatever is already there" — that reframing is what idempotency actually is, mechanically.

## 3. Checkpointing: Resume, Don't Restart

For a multi-step or multi-batch pipeline, checkpointing persists *how far the run got* so a retry after failure can skip already-completed work instead of redoing it from the beginning.

```python
import json

conn.execute("CREATE TABLE checkpoints (pipeline_id TEXT PRIMARY KEY, state TEXT)")
conn.execute("CREATE TABLE processed (id INTEGER PRIMARY KEY, value TEXT)")

def save_checkpoint(conn, pid, state):
    conn.execute("INSERT INTO checkpoints VALUES (?, ?) ON CONFLICT(pipeline_id) DO UPDATE SET state=excluded.state",
                 (pid, json.dumps(state)))
    conn.commit()

def get_checkpoint(conn, pid):
    row = conn.execute("SELECT state FROM checkpoints WHERE pipeline_id=?", (pid,)).fetchone()
    return json.loads(row[0]) if row else {"completed": []}

def run_pipeline(conn, pid, batches, fail_at=None):
    state = get_checkpoint(conn, pid)
    completed = set(state["completed"])
    for name, rows in batches.items():
        if name in completed:
            continue
        if name == fail_at:
            save_checkpoint(conn, pid, {"completed": list(completed)})
            return False   # simulated crash
        conn.executemany("INSERT OR REPLACE INTO processed VALUES (?, ?)", rows)
        completed.add(name)
        save_checkpoint(conn, pid, {"completed": list(completed)})
    return True

batches = {"b1": [(1, "a"), (2, "b")], "b2": [(3, "c"), (4, "d")], "b3": [(5, "e")]}
run_pipeline(conn, "job1", batches, fail_at="b2")     # crashes partway through b2
print(conn.execute("SELECT COUNT(*) FROM processed").fetchone()[0])   # 2 (only b1 landed)

run_pipeline(conn, "job1", batches)                    # resumes -- skips b1, redoes from b2
print(conn.execute("SELECT COUNT(*) FROM processed").fetchone()[0])   # 5 (all batches now landed)
```

Checkpointing and idempotent loading solve *different* problems and are usually used together: idempotency guarantees that re-applying a batch is harmless; checkpointing means you don't have to re-apply *everything* just to redo the one batch that failed.

## 4. Retry With Exponential Backoff and Jitter

Retrying immediately after a transient failure (a dropped connection, a `429 Too Many Requests`) tends to hit the same overloaded resource again immediately. Exponential backoff waits longer between each successive retry; jitter adds a small random offset so many clients retrying at once don't all retry in lockstep.

```python
import time, random

def retry_with_backoff(func, max_retries=5, base_delay=0.01, max_delay=1.0):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)
            time.sleep(delay + jitter)

call_count = 0
def flaky():
    global call_count
    call_count += 1
    if call_count < 4:
        raise ConnectionError(f"transient failure #{call_count}")
    return "SUCCESS"

print(retry_with_backoff(flaky), call_count)   # SUCCESS 4
```

Retry logic should only ever wrap **transient** failures (a network blip, a rate limit, a lock timeout) — retrying a **permanent** failure (malformed data, a `404` for a resource that doesn't exist) just wastes time before failing anyway, and should route straight to the dead-letter queue instead (section 5). Distinguishing the two is itself a design decision worth stating explicitly in an interview, not an afterthought — `practice/coding_problems.md`'s retry-mechanism problem builds exactly this distinction into one class.

## 5. Dead-Letter Queues: Bad Records Shouldn't Crash the Batch

A record that fails validation or processing should be captured — with its raw content and the error that caused the failure — and routed aside, so 1 bad row out of 100,000 doesn't take down the other 99,999.

```python
conn.execute("CREATE TABLE results (id INTEGER PRIMARY KEY, value REAL)")
conn.execute("CREATE TABLE dead_letters (id INTEGER, raw_data TEXT, error TEXT)")

records = [{"id": 1, "value": "100.50"}, {"id": 2, "value": "not_a_number"}, {"id": 3, "value": "200.75"}]
for r in records:
    try:
        conn.execute("INSERT INTO results VALUES (?, ?)", (r["id"], float(r["value"])))
    except ValueError as e:
        conn.execute("INSERT INTO dead_letters VALUES (?, ?, ?)", (r["id"], json.dumps(r), str(e)))
conn.commit()

print(conn.execute("SELECT COUNT(*) FROM results").fetchone()[0])       # 2
print(conn.execute("SELECT COUNT(*) FROM dead_letters").fetchone()[0])  # 1
```

A dead-lettered record isn't gone — it's held for inspection and, once the underlying issue is understood or fixed, **reprocessing**. That reprocessing step should go through the same idempotent load path as everything else, precisely so replaying a dead letter can never produce a duplicate if it happens to have partially landed already.

## 6. Putting It Together

A production-grade pipeline layers all of the above rather than picking one: staging + merge for idempotent loads (`concepts/03_loading_strategies.md`), checkpoints so a crash resumes instead of restarting, retries with backoff around anything that talks to a flaky external system, and a dead-letter table for anything that fails validation outright. `projects/mini_etl_pipeline.md` builds a small version of exactly this combination as one class, and `practice/coding_problems.md` includes a from-scratch version of the retry+DLQ piece as its own problem.

One caution belongs here explicitly: idempotency at the *database* layer (an upsert, a partition overwrite) does not automatically make an entire pipeline safe to retry if any step has a **non-idempotent side effect outside the database** — calling a payment API, sending a notification email, incrementing an external counter. Retrying a batch that already succeeded in charging a customer, purely because the pipeline's own bookkeeping failed to record that success before crashing, duplicates a real-world effect that no database upsert can undo. This distinction — and how to reason about it under "exactly-once" language — gets a full, dedicated drill in `interview_questions/05_idempotency_and_exactly_once.md`.

---

This closes out the concepts folder. From here, `practice/exercises.md` and `practice/coding_problems.md` apply everything above hands-on, and `interview_questions/` drills the reasoning an interviewer actually scores.
