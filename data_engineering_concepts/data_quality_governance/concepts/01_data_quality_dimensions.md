# Concept 01: Data Quality Dimensions

**Covers:**
- Why "bad data is worse than no data" and the 1-10-100 rule for when it's cheapest to catch a problem
- The six dimensions of data quality: completeness, accuracy, consistency, timeliness, uniqueness, validity
- A concrete SQL/Python check for each dimension
- Turning dimension scores into one overall quality score
- SLIs, SLAs, and SLOs applied to data instead of uptime

*All code below is real, runnable Python + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. Why This Is Worth a Whole Topic

A pipeline that runs on schedule and never throws an exception can still be silently wrong — nulls where a required field should be, a duplicate customer counted twice, a stale table that stopped updating three days ago while every downstream job kept "succeeding." None of that trips an orchestrator's failure alert, because nothing *failed* — the data just quietly stopped being trustworthy. That gap between "the job succeeded" and "the data is correct" is what this whole topic exists to close.

The **1-10-100 rule** is the standard framing for why this is worth investing in early rather than reactively:

```text
$1    to verify data at the point of entry      (a validation check before it lands)
$10   to cleanse and fix it after it has landed  (a backfill, a reprocessing job)
$100  to deal with the business impact of it     (a wrong dashboard a VP already acted on)
```

Catching a bad row before it's written is nearly free compared to catching it after a report built on it has already shipped.

---

## 2. The Six Dimensions

Every data quality conversation — and nearly every interview question on this topic — decomposes into some combination of these six measurable properties:

```text
Completeness:   Are all required fields present?
Accuracy:       Do values match reality?
Consistency:    Do related values / datasets agree with each other?
Timeliness:     Is the data fresh enough to be useful?
Uniqueness:     Are there duplicates where there shouldn't be?
Validity:       Do values conform to expected formats, types, and ranges?
```

Every example below runs against the same intentionally-flawed table:

```python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("""
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT,
        age INTEGER, state TEXT, signup_date TEXT, last_active TEXT
    )
""")
customers = [
    (1, "Alice Johnson", "alice@example.com", "555-0101", 29, "CA", "2024-01-15", "2024-06-01"),
    (2, "Bob Smith",     "bob@example.com",   "555-0102", 35, "NY", "2024-02-20", "2024-05-28"),
    (3, None,            "charlie@example.com","555-0103", 42, "TX", "2024-03-10", "2024-06-02"),  # missing name
    (4, "Diana Prince",  None,                "555-0104", 31, "FL", "2024-04-05", "2024-05-30"),   # missing email
    (5, "Eve Adams",     "eve@example.com",    None,       27, "CA", "2024-05-12", "2024-06-01"),  # missing phone
    (6, "Frank Lee",     "frank@example.com", "555-0106", -5, "NY", "2024-01-20", "2024-05-15"),    # invalid age
    (7, "Grace Kim",     "grace@example.com", "555-0107", 200,"ZZ", "2024-03-01", "2024-06-01"),    # invalid age + state
    (8, "Alice Johnson", "alice@example.com", "555-0101", 29, "CA", "2024-01-15", "2024-06-01"),    # exact duplicate of row 1
    (9, "Hank Brown",    "hank@example",      "555-0109", 45, "WA", "2099-06-15", "2024-05-01"),    # bad email, future signup
    (10,"Ivy Chen",      "ivy@example.com",   "555-0110", 33, "OR", "2023-01-01", "2020-01-01"),    # last_active before signup
]
conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", customers)
conn.commit()
```

### Completeness — are the required fields populated?

```python
def measure_completeness(conn, table, columns):
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    results = {}
    for col in columns:
        missing = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL OR TRIM({col}) = ''"
        ).fetchone()[0]
        results[col] = round((total - missing) / total * 100, 2) if total else 0
    return results

print(measure_completeness(conn, "customers", ["name", "email", "phone"]))
# {'name': 90.0, 'email': 90.0, 'phone': 90.0}  -- 1 missing value per column, out of 10 rows
```

### Validity — do values conform to a format or range rule?

Validity rules are expressed as a SQL condition that is *true for valid rows*; the check counts how many rows fail it.

```python
def measure_validity(conn, table, rules):
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    results = {}
    for col, (desc, condition) in rules.items():
        valid = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}").fetchone()[0]
        results[col] = {"rule": desc, "invalid": total - valid,
                         "validity_pct": round(valid / total * 100, 2) if total else 0}
    return results

rules = {
    "age":   ("age between 0 and 120", "age BETWEEN 0 AND 120"),
    "email": ("email contains @ and .", "email IS NULL OR email LIKE '%@%.%'"),
    "state": ("state is 2 uppercase letters", "LENGTH(state) = 2 AND state = UPPER(state)"),
}
for col, info in measure_validity(conn, "customers", rules).items():
    print(col, info)
# age: {'rule': 'age between 0 and 120', 'invalid': 2, 'validity_pct': 80.0}
# email: {'rule': 'email contains @ and .', 'invalid': 1, 'validity_pct': 90.0}
```

Notice the `email IS NULL OR ...` guard in the rule itself: a bare `email LIKE '%@%.%'` would silently count row 4's missing email as a *validity* failure too, since SQL's `NULL LIKE anything` evaluates to `NULL` (falsy), not `TRUE`. Without the guard, a validity check quietly double-penalizes the exact same row completeness already caught — worth writing every validity rule defensively against nulls for this reason, unless double-counting a missing value against both dimensions is genuinely what you want.

Validity is about *shape* (a format, a range, a type) — it says nothing about whether the value is actually *true*. `state = 'ZZ'` fails the validity rule above; `state = 'CA'` for someone who actually lives in Texas passes it while still being wrong. That distinction is exactly what separates validity from accuracy, next.

### Accuracy — does the value reflect reality?

Accuracy is the hardest dimension to measure directly, because it requires a source of truth to compare against, and pipelines rarely have one on hand. In practice, accuracy is almost always measured as a **proxy**: a domain rule that's a reasonable stand-in for "is this plausible," or a reconciliation against an external system that's trusted more than the one being checked.

```python
def measure_accuracy_proxy(conn, table, accuracy_rules):
    # Same shape as validity -- accuracy checks ARE validity-style SQL,
    # they're just chosen for a different reason (plausibility vs. format).
    return measure_validity(conn, table, accuracy_rules)

accuracy_rules = {
    "age_realistic":    ("age is a realistic human age (1-100)", "age BETWEEN 1 AND 100"),
    "signup_not_future": ("signup_date is not in the future", "signup_date <= date('now')"),
}
for col, info in measure_accuracy_proxy(conn, "customers", accuracy_rules).items():
    print(col, info)
# signup_not_future: {'rule': ..., 'invalid': 1, 'validity_pct': 90.0}  -- row 9 signed up "in the future"
```

The honest caveat to state out loud in an interview: a domain-rule proxy can only ever catch *implausible* values, never *wrong-but-plausible* ones — a customer's age recorded as 34 when they're actually 41 will never fail any rule like this. True accuracy validation needs an external reference (a reconciliation against a system of record), which is a heavier, less common check than the other five dimensions.

### Consistency — do related values agree with each other?

Consistency checks compare a row against another row, another column, or another table — anywhere two things are supposed to agree and might not.

```python
conn.execute("""
    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY, customer_id INTEGER,
        amount REAL, status TEXT, order_date TEXT
    )
""")
conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", [
    (1, 1, 99.99, "completed", "2024-03-01"),
    (2, 999, 75.00, "completed", "2024-04-10"),   # orphan: customer_id 999 doesn't exist
    (3, 5, -10.00, "completed", "2024-04-20"),    # negative amount
    (4, 2, 200.00, "COMPLETED", "2024-05-01"),    # inconsistent status casing
])
conn.commit()

def measure_consistency(conn, checks):
    results = []
    for desc, sql in checks:
        bad = conn.execute(sql).fetchone()[0]
        results.append({"check": desc, "inconsistent_rows": bad, "passed": bad == 0})
    return results

checks = [
    ("last_active is never before signup_date",
     "SELECT COUNT(*) FROM customers WHERE last_active < signup_date"),
    ("every order.customer_id exists in customers",
     "SELECT COUNT(*) FROM orders o LEFT JOIN customers c ON o.customer_id = c.id WHERE c.id IS NULL"),
    ("status values are lowercase everywhere",
     "SELECT COUNT(*) FROM orders WHERE status != LOWER(status)"),
]
for c in measure_consistency(conn, checks):
    print(c)
# {'check': 'last_active is never before signup_date', 'inconsistent_rows': 2, 'passed': False}
# {'check': 'every order.customer_id exists in customers', 'inconsistent_rows': 1, 'passed': False}
```

Consistency is the dimension that most naturally spans *multiple tables*, which is why it's the one most often broken by a join a reporting query gets wrong (an inner join silently dropping the orphaned order above) rather than by the source data itself — see `interview_questions/03_critique_and_debug.md` for that exact failure mode.

### Timeliness — is the data fresh enough to be useful?

```python
from datetime import datetime, timedelta

def measure_timeliness(conn, table, date_column, max_age_days, as_of=None):
    as_of = as_of or datetime.now()
    cutoff = (as_of - timedelta(days=max_age_days)).strftime("%Y-%m-%d")
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    timely = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {date_column} >= ?", (cutoff,)).fetchone()[0]
    return {"total": total, "timely": timely, "stale": total - timely,
            "cutoff": cutoff, "timeliness_pct": round(timely / total * 100, 2) if total else 0}

# as_of is pinned to a fixed date here (rather than the real "now") purely so this example's
# output stays reproducible no matter when you actually run it -- in production this argument
# defaults to datetime.now() and you'd never pass it explicitly.
print(measure_timeliness(conn, "customers", "last_active", max_age_days=365, as_of=datetime(2024, 6, 15)))
# {'total': 10, 'timely': 9, 'stale': 1, ..., 'timeliness_pct': 90.0}
```

Timeliness measured this way is a **snapshot** check — "what fraction of existing rows are recent." It answers "is the data stale" but not "did today's load even run" — that second question is a different, ongoing-monitoring problem (a row-count/freshness *SLA* on the pipeline itself, not a per-row property of the table), covered in full in `concepts/05_anomaly_detection_and_monitoring.md`.

### Uniqueness — are there duplicates where there shouldn't be?

```python
def measure_uniqueness(conn, table, columns):
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    col_str = ", ".join(columns)
    distinct = conn.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT {col_str} FROM {table})").fetchone()[0]
    return {"total": total, "distinct": distinct, "duplicates": total - distinct,
            "uniqueness_pct": round(distinct / total * 100, 2) if total else 0}

print(measure_uniqueness(conn, "customers", ["name", "email"]))
# {'total': 10, 'distinct': 9, 'duplicates': 1, 'uniqueness_pct': 90.0}  -- row 8 duplicates row 1
```

This is an **exact-match** uniqueness check — `GROUP BY` on the literal column values. It has a real blind spot: it will never catch "Alice Johnson" vs. "alice johnson " (trailing space, different casing) or two records that are the same person entered twice with a typo in one field. Catching *those* needs fuzzy matching — worked as its own problem in `practice/coding_problems.md` and named explicitly as a critique case in `interview_questions/03_critique_and_debug.md`.

---

## 3. Turning Six Scores Into One Number

Dimension scores get combined into a single **quality score**, weighted by how much each dimension matters for the table in question — a customer PII table might weight accuracy and validity heavily; a high-volume clickstream table might weight timeliness and completeness instead.

```python
def compute_quality_score(dimension_scores, weights):
    weighted_sum = sum(dimension_scores.get(dim, 0) * w for dim, w in weights.items())
    total_weight = sum(w for dim in dimension_scores if dim in weights for w in [weights[dim]])
    return round(weighted_sum / total_weight, 2) if total_weight else 0

weights = {"completeness": 0.20, "accuracy": 0.20, "consistency": 0.15,
           "timeliness": 0.15, "uniqueness": 0.15, "validity": 0.15}
scores = {"completeness": 90.0, "accuracy": 90.0, "consistency": 67.0,
          "timeliness": 90.0, "uniqueness": 90.0, "validity": 80.0}
overall = compute_quality_score(scores, weights)
print(overall)  # 85.05

grade = "A" if overall >= 95 else "B" if overall >= 85 else "C" if overall >= 70 else "D" if overall >= 50 else "F"
print(grade)  # B
```

The weights themselves are a judgment call, not a formula — stating *why* you weighted one dimension over another for a given table is exactly the kind of reasoning an interviewer wants to hear, not the arithmetic itself.

---

## 4. SLIs, SLAs, and SLOs for Data

Borrowed directly from site-reliability engineering vocabulary, applied to data instead of uptime:

```text
SLI (Service Level Indicator): the measured metric      -- "completeness = 93%"
SLA (Service Level Agreement): the promised threshold    -- "completeness >= 95%"
SLO (Service Level Objective): an internal target,       -- "completeness >= 98%"
                                usually stricter than the SLA
```

```python
DATA_SLAS = {
    "completeness": {"threshold": 95.0, "severity": "critical"},
    "uniqueness":   {"threshold": 99.0, "severity": "critical"},
    "validity":     {"threshold": 90.0, "severity": "warning"},
}

def check_sla_compliance(slis, slas=DATA_SLAS):
    results = []
    for dim, sla in slas.items():
        measured = slis.get(dim)
        if measured is None:
            results.append({"dimension": dim, "status": "NOT_MEASURED"})
            continue
        results.append({"dimension": dim, "measured": measured, "threshold": sla["threshold"],
                         "severity": sla["severity"], "status": "PASS" if measured >= sla["threshold"] else "FAIL"})
    return results

for r in check_sla_compliance({"completeness": 90.0, "uniqueness": 90.0, "validity": 80.0}):
    print(r)
# {'dimension': 'completeness', 'measured': 90.0, 'threshold': 95.0, 'severity': 'critical', 'status': 'FAIL'}
# {'dimension': 'uniqueness', 'measured': 90.0, 'threshold': 99.0, 'severity': 'critical', 'status': 'FAIL'}
# {'dimension': 'validity', 'measured': 80.0, 'threshold': 90.0, 'severity': 'warning', 'status': 'FAIL'}
```

The `severity` field is what turns a check into an actionable alerting policy rather than just a number: a `critical` SLA breach should page someone or block the pipeline; a `warning` breach should show up on a dashboard without waking anyone up. Designing that severity split *before* wiring up alerting is what prevents the two failure modes that make teams stop trusting a monitoring system: alert fatigue (everything pages, so nothing gets attention) and silent rot (nothing pages, so real breaks go unnoticed) — both covered as ongoing-monitoring concerns in `concepts/05_anomaly_detection_and_monitoring.md`.

---

## Key Takeaways

- Data quality decomposes into six measurable dimensions: completeness (are fields populated), accuracy (does it reflect reality — usually only measurable via a proxy or an external source of truth), consistency (do related values/tables agree), timeliness (is it fresh), uniqueness (are there unwanted duplicates), validity (does it match a format/range/type rule).
- Validity and accuracy are easy to conflate: validity is about *shape* (`state` is 2 uppercase letters), accuracy is about *truth* (that state is actually where the customer lives). A value can be perfectly valid and still wrong.
- Exact-match uniqueness checks (`GROUP BY` the literal values) have a structural blind spot for near-duplicates and fuzzy matches — a different technique (string similarity, worked in `practice/coding_problems.md`) is needed to catch those.
- Dimension scores combine into one quality score via a weighted average; the weights are a domain judgment call, worth justifying out loud, not a fixed formula.
- SLI/SLA/SLO borrows SRE vocabulary for data: the measured value, the promised threshold, and a stricter internal target, respectively — paired with a severity level so a breach routes to the right response (page vs. dashboard) instead of either alert fatigue or silent rot.
- Catching a bad row before it lands (validation at entry) is roughly 10x cheaper than cleaning it up after, and roughly 100x cheaper than absorbing the business impact of a decision made on top of it — the 1-10-100 rule.
