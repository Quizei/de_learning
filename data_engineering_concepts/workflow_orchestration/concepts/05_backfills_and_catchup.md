# Concept 05: Backfills and Catchup

**Covers:**
- `catchup` — what it actually does, and why `catchup=True` is one of the most common real production incidents in this whole topic
- Backfilling: rerunning a DAG for a historical date range on purpose
- The one property that makes any of this safe: idempotency
- Running a backfill *safely* alongside a DAG that's also running live, incrementally, today
- `max_active_runs`, `depends_on_past`, and pool/concurrency limits as the actual safety levers
- Why this is a favorite mid-level "have you actually operated this" interview question

*Code below is runnable, dependency-free Python simulating the scheduling decision, not the workers themselves.*

---

## 1. Why This Gets Its Own File

The four Airflow-specific concept files in this folder cover DAGs, operators, scheduling, and error handling — the vocabulary of building a pipeline. **Backfilling** is different: it's an *operational* skill, not a design skill, and it's disproportionately common as an interview question because it's one of the few things that's very hard to fake having actually done. "How would you backfill six months of history for a DAG that's also running incrementally today, without doubling up compute or breaking downstream consumers?" tests real production experience in a way "what's a DAG" doesn't.

---

## 2. `catchup`: What It Actually Does

Every DAG has a `start_date` and a schedule. The moment you deploy (or un-pause) that DAG, Airflow has to decide what to do about every scheduled interval *between* `start_date` and now that never ran. `catchup` is the switch that decides:

```text
catchup=True   (Airflow's historical default) Schedule a DAG Run for EVERY interval between
               start_date and now, immediately, back to back, as fast as the scheduler and
               available worker slots allow.

catchup=False  Only schedule the MOST RECENT interval going forward. Every earlier interval
               between start_date and now is simply never run.
```

```python
from datetime import datetime, timedelta

def scheduled_intervals(start_date, now, schedule_days=1):
    """What catchup=True would queue up as DAG Runs, right now, all at once."""
    runs = []
    current = start_date
    while current < now:
        runs.append(current)
        current += timedelta(days=schedule_days)
    return runs

start = datetime(2022, 1, 1)     # a DAG someone wrote two years ago
now = datetime(2024, 1, 1)
runs = scheduled_intervals(start, now)
print(f"catchup=True would immediately queue {len(runs)} DAG Runs")
```

```text
catchup=True would immediately queue 731 DAG Runs
```

**This is the incident.** Someone sets `start_date=datetime(2022, 1, 1)` on a brand-new DAG, deploys it today with the (very common, unstated) default of `catchup=True`, and the scheduler responds by queuing 731 daily runs *simultaneously* — each one hitting the same source APIs, the same warehouse, the same downstream tables, all at once, for a pipeline nobody intended to backfill at all. The fix people reach for after being burned once is making `catchup=False` the default on every new DAG and treating an intentional backfill as a deliberate, separate action — never something that happens as a side effect of a normal deploy.

---

## 3. Backfilling: The Same Mechanism, Done on Purpose

A **backfill** is choosing to run a DAG for a historical date range deliberately — a new metric was added and needs computing for the last year, a bug in `transform_data` corrupted three months of a table and it needs reprocessing, a brand-new pipeline needs to be seeded with history before it goes live.

```python
def backfill_runs(dag_start, backfill_start, backfill_end, schedule_days=1):
    """Which logical dates a deliberate backfill would (re)run."""
    if backfill_start < dag_start:
        raise ValueError("backfill_start is before the DAG's start_date")
    runs, current = [], backfill_start
    while current <= backfill_end:
        runs.append(current)
        current += timedelta(days=schedule_days)
    return runs

runs = backfill_runs(
    dag_start=datetime(2023, 1, 1),
    backfill_start=datetime(2023, 6, 1),
    backfill_end=datetime(2023, 6, 5),
)
print([r.date() for r in runs])
```

```text
[datetime.date(2023, 6, 1), datetime.date(2023, 6, 2), datetime.date(2023, 6, 3),
 datetime.date(2023, 6, 4), datetime.date(2023, 6, 5)]
```

Mechanically this is identical to what `catchup=True` does — schedule a batch of historical DAG Runs. The difference is entirely about *intent and control*: a backfill is triggered deliberately (Airflow's `airflow dags backfill` CLI, or re-running specific DAG Runs from the UI), for a chosen range, at a chosen concurrency — not as an unbounded side effect of un-pausing a DAG.

---

## 4. The Property That Makes Any of This Safe: Idempotency

None of this is safe unless every task in the DAG is **idempotent** — running the same logical date twice produces the exact same end state as running it once, with no duplicated rows, no double-counted revenue, no doubled email sends.

```text
NOT idempotent (backfill-unsafe):
  INSERT INTO fact_sales SELECT * FROM staging WHERE date = :ds;
    -- rerun the same date -> every row inserted a second time -> doubled revenue

  fact_daily_totals.amount += new_batch_total
    -- rerun -> the running total is now wrong for every day after it, permanently

IDEMPOTENT (backfill-safe):
  DELETE FROM fact_sales WHERE date = :ds;
  INSERT INTO fact_sales SELECT * FROM staging WHERE date = :ds;
    -- rerun any number of times -> same date, same final rows, every time

  INSERT INTO fact_sales (...) VALUES (...)
    ON CONFLICT (order_id) DO UPDATE SET ...;
    -- upsert keyed on a stable natural id -> rerun-safe by construction
```

**The single question that determines whether a DAG can be safely backfilled at all: does every task key its writes off the logical date (or another stable key), in a way where "delete-then-insert" or "upsert" replaces exactly the same rows every time — or does it append/accumulate in a way where a second run changes the answer?** This is the same idempotency property that makes retries safe (`concepts/04_error_handling_retries.md`, section 2b) — backfilling is really just "retrying," deliberately, for dates instead of failures, and it inherits the exact same requirement.

---

## 5. Backfilling Safely *While* the DAG Is Also Running Live

This is the actual hard version of the question, and the part a canned "just run `airflow dags backfill`" answer misses: how do you backfill six months of history for a DAG that's also running its normal daily schedule today, without the backfill's runs competing with production runs for the same worker slots, hammering the same source APIs concurrently, or racing a live run for the same table.

```text
1. Idempotency first, always. Confirm every task is safe to rerun (section 4) before
   touching anything else -- if it isn't, fix that before scheduling any backfill runs.

2. Isolate the backfill's concurrency from production's.
   - A dedicated Airflow "pool" (a named, capacity-limited slot pool) for the backfill's
     task instances keeps it from consuming the SAME worker slots the live daily run needs.
   - `airflow dags backfill --pool backfill_pool ...` -- the live DAG's normal runs keep
     their own pool/capacity untouched.

3. Throttle the backfill's OWN concurrency deliberately.
   - `max_active_runs` (or `--max-active-runs` / `-j` on the backfill command) caps how
     many of the BACKFILL's historical runs execute at once -- running 180 days of history
     16-at-a-time instead of all 180 simultaneously is what actually protects a rate-limited
     source API or a warehouse's concurrent-query limit.

4. Never let the backfill write into a table a live run is concurrently writing to for a
   DIFFERENT date range in a way that could race. Per-partition writes (one partition per
   logical date, per section 4's delete-then-insert pattern) sidestep this by construction:
   the backfill's June 2023 write and today's live write touch entirely different partitions.

5. Downstream consumers (a BI dashboard, a scheduled export) should not silently see PARTIAL
   backfilled history mid-run. Backfill into a staging table/partition and cut consumers over
   only once the full historical range is complete and validated -- not row-by-row as the
   backfill progresses.
```

```python
class BackfillPlan:
    """A backfill's own worker/schedule config, kept explicitly separate from
    the production DAG's normal concurrency."""
    def __init__(self, dates, pool="backfill_pool", max_active_runs=8):
        self.dates = dates
        self.pool = pool                      # isolated from the live DAG's pool
        self.max_active_runs = max_active_runs  # throttles the backfill, not production

    def batches(self):
        for i in range(0, len(self.dates), self.max_active_runs):
            yield self.dates[i:i + self.max_active_runs]

plan = BackfillPlan(dates=backfill_runs(datetime(2023, 1, 1),
                                        datetime(2023, 6, 1), datetime(2023, 6, 20)),
                     max_active_runs=5)
for i, batch in enumerate(plan.batches(), 1):
    print(f"wave {i}: {[d.date() for d in batch]}")
```

```text
wave 1: [2023-06-01, 2023-06-02, 2023-06-03, 2023-06-04, 2023-06-05]
wave 2: [2023-06-06, 2023-06-07, 2023-06-08, 2023-06-09, 2023-06-10]
wave 3: [2023-06-11, 2023-06-12, 2023-06-13, 2023-06-14, 2023-06-15]
wave 4: [2023-06-16, 2023-06-17, 2023-06-18, 2023-06-19, 2023-06-20]
```

---

## 6. `depends_on_past`: When Backfill Order Actually Matters

Section 3-5 assumed each historical date is independent and can run in any order, or even in parallel. That's not always true: a DAG computing a **running/accumulating value** (a cumulative balance, a rolling 30-day retention metric) genuinely needs date N-1 to have finished correctly before date N runs. `depends_on_past=True` enforces exactly that — task `X` in today's run will not start until task `X` in *yesterday's* run reached `success`.

```text
depends_on_past=False (default)   Each logical date's tasks are independent. Safe to backfill
                                   many dates in parallel -- this is the common case, and the
                                   reason section 5's wave-based parallelism works at all.

depends_on_past=True              Strictly serializes runs, one logical date at a time, in
                                   order. Correct for genuinely sequential/accumulating state;
                                   turns a 180-day backfill into 180 forced-sequential runs if
                                   left on for a DAG that didn't actually need it -- naming that
                                   cost explicitly is the interview-level answer, not just
                                   knowing the flag exists.
```

---

## Key Takeaways

- `catchup=True` (Airflow's historical default) schedules every missed interval between `start_date` and now immediately, all at once — deploying a new DAG with a `start_date` set months or years in the past is the single most common way this becomes an unplanned, accidental backfill on day one.
- A backfill is the exact same mechanism, done deliberately: rerunning a chosen historical date range, on purpose, at a chosen concurrency.
- None of this is safe unless every task is idempotent — reruns must replace exactly the same rows (delete-then-insert on a partition/logical-date key, or an upsert on a stable natural key), never append or accumulate on top of what's already there.
- Backfilling safely alongside a live, currently-running DAG means isolating the backfill's worker capacity from production's (a dedicated pool), throttling the backfill's own concurrency (`max_active_runs` / `-j`) so it doesn't overwhelm a rate-limited source or warehouse, writing to distinct per-date partitions so backfill and live writes can't race each other, and not exposing downstream consumers to partial backfilled history mid-run.
- `depends_on_past=True` strictly serializes runs across dates and is correct only for genuinely accumulating computations — left on by default, it silently turns an otherwise-parallelizable backfill into a slow, forced-sequential one.
- This is a disproportionately common interview question specifically because it's hard to answer well without having actually operated a production DAG through a real backfill.
