# Concept 05: Anomaly Detection & Statistical Monitoring

**Covers:**
- Why "the job succeeded" and "the data is correct" are different claims, and how a pipeline breaks silently
- Row-count anomaly detection across pipeline runs (not within one snapshot)
- Freshness SLAs: is the table still being updated at all
- Null-rate drift alerting: a distribution shift that no single-run check catches
- Turning these into an alerting policy that doesn't cause fatigue or rot

*All code below is real, runnable Python + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. The Question the Other Concepts Don't Answer

`concepts/01_data_quality_dimensions.md` and `concepts/02_validation_frameworks.md` both answer: *given today's data, is it good?* That's a **point-in-time** question, answered against one snapshot. It leaves an entire failure mode uncovered: a pipeline that runs, succeeds, and writes a *plausible-looking but structurally wrong* result — half as many rows as usual, a column that's suddenly 40% null, a table that hasn't actually updated in three days while the job that's supposed to refresh it keeps reporting success.

None of that trips a single-snapshot validity or completeness check, because each individual value can be perfectly well-formed. What's wrong is the **shape of the metric over time** — and answering "did something change that shouldn't have" requires comparing today's run against a history of previous runs, not just inspecting today's rows in isolation. This is what "how do you know your pipeline silently broke" is actually asking.

```text
Point-in-time check (concepts/01, 02):  is TODAY's data internally consistent and well-formed?
Anomaly / monitoring check (this file): is TODAY's data consistent with how this table normally behaves?
```

---

## 2. Row-Count Anomaly Detection

The simplest and highest-signal monitoring check: track row count (or rows-added-this-run) per run, and compare each new run against the recent history rather than a hard-coded number.

```python
import sqlite3, statistics
from datetime import datetime, timedelta

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE run_history (run_date TEXT, table_name TEXT, row_count INTEGER)")

# 14 days of a normally-behaving daily load: roughly 1000 rows/day, noisy but stable
history = [
    ("2024-01-01", "orders", 1020), ("2024-01-02", "orders", 980),  ("2024-01-03", "orders", 1050),
    ("2024-01-04", "orders", 990),  ("2024-01-05", "orders", 1010), ("2024-01-06", "orders", 970),
    ("2024-01-07", "orders", 1030), ("2024-01-08", "orders", 1005), ("2024-01-09", "orders", 995),
    ("2024-01-10", "orders", 1015), ("2024-01-11", "orders", 985), ("2024-01-12", "orders", 1040),
    ("2024-01-13", "orders", 1000),
]
conn.executemany("INSERT INTO run_history VALUES (?,?,?)", history)
conn.commit()

def check_row_count_anomaly(conn, table_name, today_count, lookback_days=13, max_zscore=3.0):
    """Flag today's row count if it's an outlier relative to the table's own recent history."""
    rows = conn.execute(
        "SELECT row_count FROM run_history WHERE table_name = ? ORDER BY run_date DESC LIMIT ?",
        (table_name, lookback_days)
    ).fetchall()
    counts = [r[0] for r in rows]
    mean, stdev = statistics.mean(counts), statistics.stdev(counts)
    z = (today_count - mean) / stdev if stdev else 0
    return {
        "today_count": today_count, "recent_mean": round(mean, 1), "recent_stdev": round(stdev, 1),
        "zscore": round(z, 2), "anomaly": abs(z) > max_zscore,
    }

# A normal day
print(check_row_count_anomaly(conn, "orders", today_count=1005))
# {'today_count': 1005, 'recent_mean': 1006.9, 'recent_stdev': 23.8, 'zscore': -0.08, 'anomaly': False}

# A day where an upstream source silently failed and only 40 rows landed
print(check_row_count_anomaly(conn, "orders", today_count=40))
# {'today_count': 40, 'recent_mean': 1006.9, 'recent_stdev': 23.8, 'zscore': -40.69, 'anomaly': True}
```

The reason this needs a *rolling* baseline instead of a fixed threshold (`row_count < 500 -> alert`) is that "normal" genuinely drifts — a table's typical daily volume grows over a year, or has a real weekly cycle (weekend volume legitimately lower). A fixed threshold either goes stale as the table grows, or has to be hand-tuned per table forever. A rolling z-score self-adjusts to whatever "normal" currently looks like for that specific table — the same core statistical idea as the value-level outlier check in `concepts/02_validation_frameworks.md`, section 4, just applied to one aggregate metric across runs instead of many raw values within one run.

---

## 3. Freshness SLAs: Is the Table Still Being Updated?

A row-count check answers "is this run's volume normal." It says nothing about whether there *was* a run at all today. **Freshness monitoring** checks the gap between now and the last time a table actually changed:

```python
def check_freshness(last_updated_str, max_age_hours, now=None):
    now = now or datetime.now()
    last_updated = datetime.fromisoformat(last_updated_str)
    age_hours = (now - last_updated).total_seconds() / 3600
    return {
        "last_updated": last_updated_str, "age_hours": round(age_hours, 1),
        "max_age_hours": max_age_hours, "fresh": age_hours <= max_age_hours,
    }

now = datetime(2024, 1, 15, 12, 0, 0)
print(check_freshness("2024-01-15T09:00:00", max_age_hours=6, now=now))
# {'last_updated': '2024-01-15T09:00:00', 'age_hours': 3.0, 'max_age_hours': 6, 'fresh': True}

print(check_freshness("2024-01-12T09:00:00", max_age_hours=6, now=now))
# {'last_updated': '2024-01-12T09:00:00', 'age_hours': 75.0, 'max_age_hours': 6, 'fresh': False}
```

This is deliberately the simplest possible check in this file, and that's the point: it needs no history, no statistics, just "when did this last change, and is that too long ago." It catches a specific and common real-world failure that row-count anomaly detection structurally *cannot*: an orchestrator that thinks a job is scheduled but silently stopped triggering it (a disabled DAG, a credentials expiry that fails the job before it ever touches the table) produces **zero runs**, not an anomalous run — there's no row count to even evaluate. Freshness is the check that catches "nothing happened," which is a different failure shape from "something happened, but wrong."

---

## 4. Null-Rate Drift Alerting

A one-time completeness check (`concepts/01`, section 2) says "97% of rows have a value in this column, right now." **Drift alerting** asks a sharper question: "has that percentage moved *meaningfully* since last week" — because a null rate creeping from 1% to 15% over ten runs is a real, often urgent signal (an upstream field silently stopped being populated) even though a single day's 15% might not breach any absolute SLA threshold on its own.

```python
conn.execute("CREATE TABLE null_rate_history (run_date TEXT, column_name TEXT, null_pct REAL)")
conn.executemany("INSERT INTO null_rate_history VALUES (?,?,?)", [
    ("2024-01-08", "phone", 1.2), ("2024-01-09", "phone", 1.5), ("2024-01-10", "phone", 1.1),
    ("2024-01-11", "phone", 1.8), ("2024-01-12", "phone", 1.3), ("2024-01-13", "phone", 1.6),
])
conn.commit()

def check_null_rate_drift(conn, column_name, today_null_pct, lookback_days=6, max_drift_pct=5.0):
    """Flag a null rate that has drifted meaningfully from its recent baseline, not just an absolute threshold."""
    rows = conn.execute(
        "SELECT null_pct FROM null_rate_history WHERE column_name = ? ORDER BY run_date DESC LIMIT ?",
        (column_name, lookback_days)
    ).fetchall()
    baseline = statistics.mean(r[0] for r in rows)
    drift = today_null_pct - baseline
    return {
        "today_null_pct": today_null_pct, "baseline_null_pct": round(baseline, 2),
        "drift_pct": round(drift, 2), "drifted": abs(drift) > max_drift_pct,
    }

print(check_null_rate_drift(conn, "phone", today_null_pct=1.9))
# {'today_null_pct': 1.9, 'baseline_null_pct': 1.42, 'drift_pct': 0.48, 'drifted': False}

print(check_null_rate_drift(conn, "phone", today_null_pct=22.0))
# {'today_null_pct': 22.0, 'baseline_null_pct': 1.42, 'drift_pct': 20.58, 'drifted': True}
```

The distinction worth stating plainly in an interview: an **absolute SLA** ("completeness must stay above 95%") and **drift detection** ("completeness must not move more than N points from its own recent baseline") catch different bugs. A column that's always been 40% null (maybe legitimately — an optional field most users skip) will never trip an absolute 95% threshold set for a different, mostly-required column, but a sudden jump from 40% to 70% null is still a real regression that only drift detection catches. Mature monitoring runs both: an absolute floor for fields that must always be well-populated, and drift detection layered on top for everything, including fields whose "normal" is something other than "always full."

---

## 5. Turning Checks Into an Alerting Policy

Row-count anomalies, freshness breaches, and null-rate drift are all, mechanically, the same shape: measure something, compare it to a rolling baseline or a fixed bound, decide pass/fail. What separates a *useful* monitoring system from a noisy one is the policy layered on top of that pass/fail signal:

```python
def evaluate_monitoring_checks(checks):
    """
    checks: list of {"name", "failed" (bool), "severity"}
    Routes each result to the right response instead of treating every failure identically.
    """
    routed = {"page": [], "ticket": [], "dashboard_only": []}
    for c in checks:
        if not c["failed"]:
            continue
        if c["severity"] == "critical":
            routed["page"].append(c["name"])
        elif c["severity"] == "warning":
            routed["ticket"].append(c["name"])
        else:
            routed["dashboard_only"].append(c["name"])
    return routed

checks = [
    {"name": "orders.row_count_anomaly", "failed": True,  "severity": "critical"},   # volume collapsed -- page someone
    {"name": "phone.null_rate_drift",    "failed": True,  "severity": "warning"},     # worth investigating, not urgent
    {"name": "orders.freshness",         "failed": False, "severity": "critical"},
]
print(evaluate_monitoring_checks(checks))
# {'page': ['orders.row_count_anomaly'], 'ticket': ['phone.null_rate_drift'], 'dashboard_only': []}
```

The two failure modes this exists to prevent, both fatal to whether anyone still trusts the monitoring a year from now:

```text
Alert fatigue: every anomaly (including tiny, harmless ones) pages someone at 2am.
               People start ignoring pages, then miss the one that mattered.

Silent rot:    nothing is wired to page at all, or thresholds are set so loose
               they never fire. The dashboard exists; nobody looks at it until
               a stakeholder notices the number is wrong three weeks later.
```

Getting this right is a design decision, not an afterthought: decide up front which checks are truly "wake someone up" critical (a core revenue table's row count collapsing) versus "worth a ticket, not a page" (a rarely-used optional field's null rate drifting) versus "log it, review weekly" — and revisit the severity assignments periodically as what "normal" and "critical" mean for a table changes over time.

---

## Key Takeaways

- Point-in-time checks (`concepts/01`, `concepts/02`) answer "is today's data internally well-formed"; anomaly/monitoring checks answer "is today's data consistent with how this table normally behaves over time" — a pipeline can pass every point-in-time check and still be silently broken by this second measure.
- Row-count anomaly detection compares each run's volume against a *rolling* baseline (mean/stdev of recent runs), not a fixed threshold — this is what lets it stay correct as a table's normal volume genuinely grows or has a weekly cycle.
- Freshness monitoring checks the time since a table last actually changed, independent of row count — it's the check that catches "nothing happened at all" (a silently disabled job), a failure row-count anomaly detection can't see because there's no run to evaluate.
- Null-rate (or any column-statistic) drift alerting compares today's value against its own recent baseline, catching a meaningful shift even in a column whose "normal" null rate is nowhere near 0% — a case an absolute SLA threshold, tuned for a different kind of column, would miss entirely.
- All three checks are mechanically the same pattern (measure, compare to baseline/bound, flag) but need a severity-routing policy layered on top — critical failures page, lesser ones ticket or just log — or the system fails through alert fatigue (too sensitive) or silent rot (not sensitive enough, or unwired) regardless of how good the underlying statistics are.
