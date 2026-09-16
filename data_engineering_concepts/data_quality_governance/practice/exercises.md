# Data Quality & Governance — Practice Exercises

Twelve exercises covering: completeness, exact-match and near-duplicate uniqueness, a validity rules engine, statistical outlier detection, an expectation-suite build, a data contract definition, schema evolution classification, lineage graph traversal, cross-table consistency, a full weighted quality report, and — extending past dimension-level checks into ongoing monitoring — row-count anomaly detection and a freshness SLA check.

How to use this file: read the exercise, write down your own answer — genuinely commit to one before looking — and only then expand the reference solution to check yourself. Every solution includes working SQLite/Python code, exactly as it would run in a `python3` shell with the `sqlite3` module.

Shared setup used by most exercises:

```python
import sqlite3, statistics
from datetime import datetime, timedelta

def setup_exercise_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY, name TEXT, email TEXT, department TEXT,
            salary REAL, hire_date TEXT, manager_id INTEGER
        )
    """)
    conn.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?)", [
        (1, "Alice Johnson", "alice@company.com", "Engineering", 95000, "2020-03-15", None),
        (2, "Bob Smith",     "bob@company.com",   "Engineering", 88000, "2021-06-01", 1),
        (3, None,            "charlie@company.com","Marketing",  72000, "2022-01-10", 1),   # null name
        (4, "Diana Prince",  None,                 "Sales",      68000, "2022-05-20", 1),   # null email
        (5, "Eve Adams",     "eve@company.com",    "Engineering",-5000, "2023-03-01", 2),    # negative salary
        (6, "Frank Lee",     "frank@company",      "Marketing",  75000, "2024-08-15", 1),    # bad email
        (7, "Grace Kim",     "grace@company.com",  "HR",         82000, "2021-09-10", 1),
        (8, "Alice Johnson", "alice@company.com",  "Engineering",95000, "2020-03-15", None), # exact duplicate of 1
        (9, "Hank Brown",    "hank@company.com",   "ENGINEERING",91000, "2022-11-01", 2),    # inconsistent case
        (10,"Ivy Chen",      "ivy@company.com",    "Sales",      150000,"2023-06-15", 1),    # possible outlier
    ])
    conn.execute("CREATE TABLE departments (dept_name TEXT PRIMARY KEY, budget REAL, head_count INTEGER)")
    conn.executemany("INSERT INTO departments VALUES (?,?,?)", [
        ("Engineering", 500000, 4), ("Marketing", 200000, 2), ("Sales", 150000, 2), ("HR", 100000, 1),
    ])
    conn.commit()
    return conn
```

---

## Exercise 1: Completeness Check

Write a function that returns completeness percentage for every column in `employees`, as a dict `{column_name: pct}`.

<details>
<summary>Reference answer</summary>

```python
def check_completeness(conn, table):
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    result = {}
    for col in columns:
        nulls = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]
        result[col] = round((total - nulls) / total * 100, 1)
    return result

conn = setup_exercise_db()
print(check_completeness(conn, "employees"))
# {'id': 100.0, 'name': 90.0, 'email': 90.0, 'department': 100.0, 'salary': 100.0,
#  'hire_date': 100.0, 'manager_id': 80.0}
```

*(See `concepts/01_data_quality_dimensions.md`, section 2.)*

</details>

---

## Exercise 2: Exact-Match Duplicate Detector

Find all `(name, email)` groups appearing more than once. Return a list of dicts with `name`, `email`, `count`.

<details>
<summary>Reference answer</summary>

```python
def find_exact_duplicates(conn, table, columns):
    col_str = ", ".join(columns)
    rows = conn.execute(
        f"SELECT {col_str}, COUNT(*) as cnt FROM {table} "
        f"WHERE {' AND '.join(f'{c} IS NOT NULL' for c in columns)} "
        f"GROUP BY {col_str} HAVING COUNT(*) > 1"
    ).fetchall()
    return [dict(zip(columns + ["count"], r)) for r in rows]

conn = setup_exercise_db()
print(find_exact_duplicates(conn, "employees", ["name", "email"]))
# [{'name': 'Alice Johnson', 'email': 'alice@company.com', 'count': 2}]
```

**Now extend it:** this only catches byte-for-byte identical values. Add a normalized pass that would also catch `"alice@company.com"` vs. `"ALICE@COMPANY.COM "` as the same duplicate.

```python
def find_duplicates_normalized(conn, table, columns):
    col_expr = ", ".join(f"LOWER(TRIM({c}))" for c in columns)
    rows = conn.execute(
        f"SELECT {col_expr}, COUNT(*) as cnt FROM {table} "
        f"WHERE {' AND '.join(f'{c} IS NOT NULL' for c in columns)} "
        f"GROUP BY {col_expr} HAVING COUNT(*) > 1"
    ).fetchall()
    return rows

print(find_duplicates_normalized(conn, "employees", ["name", "email"]))
# [('alice johnson', 'alice@company.com', 2)]
```

Normalizing case and whitespace before grouping is cheap and catches a real class of near-duplicate; it still can't catch a genuine typo or nickname — that needs similarity-based matching, which is `practice/coding_problems.md`'s dedicated fuzzy-deduplication problem.

*(See `concepts/01_data_quality_dimensions.md`, section 2, and `interview_questions/03_critique_and_debug.md`, Case 2.)*

</details>

---

## Exercise 3: Validity Rules Engine

Implement rules: salary must be positive; email must contain `@` and `.`; department must be in a known set; hire_date must not be in the future. Return `{rule_name: [failing_ids]}`.

<details>
<summary>Reference answer</summary>

```python
def run_validity_rules(conn, table, rules):
    failures = {}
    for rule_name, sql in rules.items():
        failures[rule_name] = [r[0] for r in conn.execute(sql).fetchall()]
    return failures

conn = setup_exercise_db()
rules = {
    "salary_positive": "SELECT id FROM employees WHERE salary <= 0",
    "email_valid": "SELECT id FROM employees WHERE email IS NOT NULL AND email NOT LIKE '%@%.%'",
    "department_valid": "SELECT id FROM employees WHERE UPPER(department) NOT IN ('ENGINEERING','MARKETING','SALES','HR')",
    "hire_date_not_future": "SELECT id FROM employees WHERE hire_date > date('now')",
}
print(run_validity_rules(conn, "employees", rules))
# {'salary_positive': [5], 'email_valid': [6], 'department_valid': [], 'hire_date_not_future': []}
```

*(See `concepts/01_data_quality_dimensions.md`, section 2, and `concepts/02_validation_frameworks.md`, section 1.)*

</details>

---

## Exercise 4: Statistical Outlier Detection

Detect salary outliers using z-scores; flag anything more than 2 standard deviations from the mean.

<details>
<summary>Reference answer</summary>

```python
def detect_salary_outliers(conn, max_zscore=2.0):
    rows = conn.execute("SELECT id, name, salary FROM employees WHERE salary IS NOT NULL").fetchall()
    salaries = [r[2] for r in rows]
    mean, stdev = statistics.mean(salaries), statistics.stdev(salaries)
    return [{"id": r[0], "name": r[1], "salary": r[2], "zscore": round((r[2] - mean) / stdev, 2)}
            for r in rows if stdev and abs((r[2] - mean) / stdev) > max_zscore]

conn = setup_exercise_db()
print(detect_salary_outliers(conn))
# [{'id': 5, 'name': 'Eve Adams', 'salary': -5000, 'zscore': -2.27}]
```

Note that Eve's outlier salary is *also* a validity failure (negative) from Exercise 3 — the two checks catch it for different reasons (validity: violates a hard business rule; statistical: is far from the rest of the distribution), and a real value can trip one without the other (Ivy Chen's $150,000 is perfectly valid but may or may not register as a statistical outlier depending on the threshold — worth checking both).

*(See `concepts/02_validation_frameworks.md`, section 4.)*

</details>

---

## Exercise 5: Expectation Suite Builder

Build a mini expectation suite for `employees` with at least 5 expectations, and run it.

<details>
<summary>Reference answer</summary>

```python
def run_expectation_suite(conn, table):
    results = []
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    results.append({"expectation": "row_count_5_to_100", "passed": 5 <= total <= 100})

    nulls = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE name IS NULL").fetchone()[0]
    results.append({"expectation": "name_not_null", "passed": nulls == 0, "detail": f"{nulls} nulls"})

    bad_salary = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE salary < 0 OR salary > 200000").fetchone()[0]
    results.append({"expectation": "salary_in_range", "passed": bad_salary == 0})

    distinct_emails = conn.execute(f"SELECT COUNT(DISTINCT email) FROM {table} WHERE email IS NOT NULL").fetchone()[0]
    non_null_emails = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE email IS NOT NULL").fetchone()[0]
    results.append({"expectation": "email_unique", "passed": distinct_emails == non_null_emails})

    bad_dept = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE UPPER(department) NOT IN ('ENGINEERING','MARKETING','SALES','HR')"
    ).fetchone()[0]
    results.append({"expectation": "department_in_set", "passed": bad_dept == 0})
    return results

conn = setup_exercise_db()
for r in run_expectation_suite(conn, "employees"):
    print(("PASS" if r["passed"] else "FAIL"), r["expectation"])
# PASS row_count_5_to_100
# FAIL name_not_null
# FAIL salary_in_range
# FAIL email_unique
# PASS department_in_set
```

*(See `concepts/02_validation_frameworks.md`, section 3.)*

</details>

---

## Exercise 6: Data Contract Definition

Define a contract for `employees` as a Python dict (schema + completeness/uniqueness SLAs + row-count bounds), and validate the table against it.

<details>
<summary>Reference answer</summary>

```python
CONTRACT = {
    "schema": [
        {"name": "id", "type": "INTEGER", "required": True},
        {"name": "name", "type": "TEXT", "required": True},
        {"name": "email", "type": "TEXT", "required": True},
        {"name": "salary", "type": "REAL", "required": True},
    ],
    "slas": {"completeness_threshold": 95.0, "uniqueness_threshold": 95.0},
    "row_count": {"min": 5, "max": 1000},
}

def validate_contract(conn, table, contract):
    failures = []
    actual = {r[1]: r[2] for r in conn.execute(f"PRAGMA table_info({table})")}
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    for col in contract["schema"]:
        if col["name"] not in actual:
            failures.append(f"Missing column: {col['name']}")
            continue
        if col["required"]:
            nulls = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col['name']} IS NULL").fetchone()[0]
            pct = (total - nulls) / total * 100 if total else 0
            if pct < contract["slas"]["completeness_threshold"]:
                failures.append(f"Completeness SLA failed for {col['name']}: {pct:.1f}%")

    if not (contract["row_count"]["min"] <= total <= contract["row_count"]["max"]):
        failures.append(f"Row count {total} out of bounds")

    return {"compliant": len(failures) == 0, "failures": failures}

conn = setup_exercise_db()
print(validate_contract(conn, "employees", CONTRACT))
# {'compliant': False, 'failures': ["Completeness SLA failed for name: 90.0%", "Completeness SLA failed for email: 90.0%"]}
```

*(See `concepts/03_data_contracts.md`, sections 1 and 4.)*

</details>

---

## Exercise 7: Schema Evolution Checker

Old schema: `id (INTEGER)`, `name (TEXT, required)`, `email (TEXT, required)`. New schema: same `id`/`name`, `email` now optional, plus a new optional `phone`. Classify each change as breaking or not.

<details>
<summary>Reference answer</summary>

```python
def compare_schemas(old_cols, new_cols):
    old_map, new_map = {c["name"]: c for c in old_cols}, {c["name"]: c for c in new_cols}
    changes = []
    for name, col in old_map.items():
        if name not in new_map:
            changes.append({"change": f"removed {name}", "breaking": col.get("required", False)})
        elif col.get("required") and not new_map[name].get("required"):
            changes.append({"change": f"made_optional {name}", "breaking": False})
    for name, col in new_map.items():
        if name not in old_map:
            changes.append({"change": f"added {name}", "breaking": col.get("required", False)})
    return changes

old_cols = [{"name": "id", "type": "INTEGER", "required": True},
            {"name": "name", "type": "TEXT", "required": True},
            {"name": "email", "type": "TEXT", "required": True}]
new_cols = [{"name": "id", "type": "INTEGER", "required": True},
            {"name": "name", "type": "TEXT", "required": True},
            {"name": "email", "type": "TEXT", "required": False},
            {"name": "phone", "type": "TEXT", "required": False}]

for c in compare_schemas(old_cols, new_cols):
    print(("BREAKING" if c["breaking"] else "safe"), c["change"])
# safe made_optional email
# safe added phone
```

*(See `concepts/03_data_contracts.md`, section 2.)*

</details>

---

## Exercise 8: Lineage Graph Builder

Build lineage for `raw_employees -> staging_employees -> mart_headcount -> report_dashboard`. Answer: what feeds `report_dashboard` (upstream), and what's impacted if `raw_employees` changes (downstream)?

<details>
<summary>Reference answer</summary>

```python
forward = {
    "raw_employees": ["staging_employees"],
    "staging_employees": ["mart_headcount"],
    "mart_headcount": ["report_dashboard"],
    "report_dashboard": [],
}
backward = {}
for src, targets in forward.items():
    for tgt in targets:
        backward.setdefault(tgt, []).append(src)

def walk(node, graph):
    visited, queue, result = set(), [node], []
    while queue:
        current = queue.pop(0)
        for neighbor in graph.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor); result.append(neighbor); queue.append(neighbor)
    return result

print("Upstream of report_dashboard:", walk("report_dashboard", backward))
# ['mart_headcount', 'staging_employees', 'raw_employees']
print("Impact of raw_employees change:", walk("raw_employees", forward))
# ['staging_employees', 'mart_headcount', 'report_dashboard']
```

*(See `concepts/04_lineage_and_cataloging.md`, section 2.)*

</details>

---

## Exercise 9: Cross-Table Consistency Check

Validate: every employee's department exists in `departments`; each department's `head_count` matches the actual employee count; total salaries per department don't exceed budget.

<details>
<summary>Reference answer</summary>

```python
def check_consistency(conn):
    checks = []

    orphans = conn.execute("""
        SELECT COUNT(*) FROM employees e
        LEFT JOIN departments d ON LOWER(e.department) = LOWER(d.dept_name)
        WHERE d.dept_name IS NULL
    """).fetchone()[0]
    checks.append({"check": "dept_referential_integrity", "passed": orphans == 0, "detail": f"{orphans} orphans"})

    mismatches = []
    for dept_name, head_count in conn.execute("SELECT dept_name, head_count FROM departments").fetchall():
        actual = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE LOWER(department) = LOWER(?)", (dept_name,)
        ).fetchone()[0]
        if actual != head_count:
            mismatches.append(f"{dept_name}: expected={head_count}, actual={actual}")
    checks.append({"check": "head_count_matches", "passed": not mismatches, "detail": "; ".join(mismatches)})

    over_budget = []
    for dept_name, budget in conn.execute("SELECT dept_name, budget FROM departments").fetchall():
        total_salary = conn.execute(
            "SELECT COALESCE(SUM(salary), 0) FROM employees WHERE LOWER(department) = LOWER(?)", (dept_name,)
        ).fetchone()[0]
        if total_salary > budget:
            over_budget.append(f"{dept_name}: budget={budget}, salaries={total_salary}")
    checks.append({"check": "salary_within_budget", "passed": not over_budget, "detail": "; ".join(over_budget)})
    return checks

conn = setup_exercise_db()
for c in check_consistency(conn):
    print(("PASS" if c["passed"] else "FAIL"), c["check"], c["detail"])
# PASS dept_referential_integrity 0 orphans
# FAIL head_count_matches Engineering: expected=4, actual=5
# FAIL salary_within_budget Sales: budget=150000.0, salaries=218000.0
```

*(See `concepts/01_data_quality_dimensions.md`, section 2.)*

</details>

---

## Exercise 10: Quality Report Generator

Generate a report with completeness, uniqueness, validity scores, a weighted overall score, a grade, and a list of issues.

<details>
<summary>Reference answer</summary>

```python
def generate_quality_report(conn, table):
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    comp_scores = []
    for col in columns:
        nulls = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]
        comp_scores.append((total - nulls) / total * 100)
    completeness = round(statistics.mean(comp_scores), 1)

    distinct = conn.execute(
        f"SELECT COUNT(DISTINCT name || '|' || email) FROM {table} WHERE name IS NOT NULL AND email IS NOT NULL"
    ).fetchone()[0]
    uniqueness = round(distinct / total * 100, 1)

    val_checks = [
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE salary > 0").fetchone()[0] / total * 100,
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE email LIKE '%@%.%'").fetchone()[0] / total * 100,
    ]
    validity = round(statistics.mean(val_checks), 1)

    overall = round(completeness * 0.35 + uniqueness * 0.30 + validity * 0.35, 1)
    grade = "A" if overall >= 95 else "B" if overall >= 85 else "C" if overall >= 70 else "D" if overall >= 50 else "F"

    issues = []
    if completeness < 100: issues.append(f"Missing values (completeness: {completeness}%)")
    if uniqueness < 100: issues.append(f"Duplicate rows (uniqueness: {uniqueness}%)")
    if validity < 100: issues.append(f"Invalid values (validity: {validity}%)")

    return {"completeness": completeness, "uniqueness": uniqueness, "validity": validity,
            "overall": overall, "grade": grade, "issues": issues}

conn = setup_exercise_db()
print(generate_quality_report(conn, "employees"))
# {'completeness': 94.3, 'uniqueness': 70.0, 'validity': 85.0, 'overall': 83.8, 'grade': 'C', 'issues': [...]}
```

*(See `concepts/01_data_quality_dimensions.md`, section 3.)*

</details>

---

## Exercise 11: Row-Count Anomaly Detection

Given 10 days of a table's daily row counts (roughly 1000/day, noisy), flag whether an 11th day's count of 150 is an anomaly using a z-score threshold of 3.0.

<details>
<summary>Reference answer</summary>

```python
def check_row_count_anomaly(history_counts, today_count, max_zscore=3.0):
    mean, stdev = statistics.mean(history_counts), statistics.stdev(history_counts)
    z = (today_count - mean) / stdev if stdev else 0
    return {"mean": round(mean, 1), "stdev": round(stdev, 1), "zscore": round(z, 2), "anomaly": abs(z) > max_zscore}

history = [1020, 980, 1050, 990, 1010, 970, 1030, 1005, 995, 1015]
print(check_row_count_anomaly(history, today_count=150))
# {'mean': 1006.5, 'stdev': 23.9, 'zscore': -35.8, 'anomaly': True}

print(check_row_count_anomaly(history, today_count=1002))
# {'mean': 1006.5, 'stdev': 23.9, 'zscore': -0.19, 'anomaly': False}
```

**Extend it:** what would change if the table has a strong day-of-week pattern (weekends run at 30% of weekday volume)? A single rolling baseline across all days would flag every normal weekend as an anomaly. The fix: compute a separate baseline per day-of-week bucket (weekday history vs. weekend history), and compare each day only against its own bucket's baseline — the same principle as choosing the right comparison group for any statistical check, not just this one.

*(See `concepts/05_anomaly_detection_and_monitoring.md`, section 2.)*

</details>

---

## Exercise 12: Freshness SLA Check

Write a function that checks whether a table's last-updated timestamp is within a maximum allowed age, and returns enough detail to act on a failure (not just true/false).

<details>
<summary>Reference answer</summary>

```python
from datetime import datetime

def check_freshness(last_updated_str, max_age_hours, now=None):
    now = now or datetime.now()
    last_updated = datetime.fromisoformat(last_updated_str)
    age_hours = (now - last_updated).total_seconds() / 3600
    return {"last_updated": last_updated_str, "age_hours": round(age_hours, 1),
            "max_age_hours": max_age_hours, "fresh": age_hours <= max_age_hours}

now = datetime(2024, 6, 2, 9, 0, 0)
print(check_freshness("2024-06-02T04:00:00", max_age_hours=6, now=now))
# {'last_updated': '2024-06-02T04:00:00', 'age_hours': 5.0, 'max_age_hours': 6, 'fresh': True}

print(check_freshness("2024-05-30T04:00:00", max_age_hours=6, now=now))
# {'last_updated': '2024-05-30T04:00:00', 'age_hours': 77.0, 'max_age_hours': 6, 'fresh': False}
```

*(See `concepts/05_anomaly_detection_and_monitoring.md`, section 3.)*

</details>
