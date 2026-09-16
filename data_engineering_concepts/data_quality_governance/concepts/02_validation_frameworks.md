# Concept 02: Validation Frameworks

**Covers:**
- Assertion-based validation: the simplest possible check-and-raise pattern
- Data profiling as the step that comes *before* writing any checks at all
- The Great Expectations pattern — expectations, suites, checkpoints — built from scratch in plain Python
- Statistical validation: catching outliers a format rule can't see
- Schema validation: does the table's structure match what's expected

*All code below is real, runnable Python + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. Assertion-Based Validation: The Simplest Thing That Works

Before reaching for a framework, the simplest validation pattern is just: define rules per field, check each row, raise on the first failure.

```python
def validate_row(row, schema):
    for field, rules in schema.items():
        value = row.get(field)
        if rules.get("required") and value is None:
            raise ValueError(f"Field '{field}' is required but got None")
        if value is None:
            continue
        if "type" in rules and not isinstance(value, rules["type"]):
            raise ValueError(f"Field '{field}': expected {rules['type'].__name__}, got {type(value).__name__}")
        if "min" in rules and value < rules["min"]:
            raise ValueError(f"Field '{field}': {value} < min {rules['min']}")
        if "allowed" in rules and value not in rules["allowed"]:
            raise ValueError(f"Field '{field}': '{value}' not in allowed set {rules['allowed']}")
    return True

schema = {
    "name": {"required": True, "type": str},
    "age": {"required": True, "type": int, "min": 0},
    "status": {"required": False, "type": str, "allowed": ["active", "inactive"]},
}

print(validate_row({"name": "Alice", "age": 30, "status": "active"}, schema))  # True

for bad in [{"name": None, "age": 30}, {"name": "Bob", "age": -5}, {"name": "Dan", "age": 40, "status": "banned"}]:
    try:
        validate_row(bad, schema)
    except ValueError as e:
        print(e)
# Field 'name' is required but got None
# Field 'age': -5 < min 0
# Field 'status': 'banned' not in allowed set ['active', 'inactive']
```

This pattern is genuinely enough for a lot of real pipelines — it's cheap to write, easy to reason about, and every failure is a specific, readable message. Where it stops scaling is exactly where the next two sections pick up: it only checks *one row at a time* (no dataset-level checks like row count or uniqueness), and it has no notion of running the same suite of checks repeatably against a changing table and comparing results over time.

---

## 2. Profile First, Validate Second

Writing a check like `price BETWEEN 0 AND 500` before looking at the actual data is a guess. **Data profiling** — computing basic statistics for every column before writing a single rule — is what turns a guess into an informed threshold.

```python
import sqlite3, statistics

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, price REAL, category TEXT, stock INTEGER)")
conn.executemany("INSERT INTO products VALUES (?,?,?,?,?)", [
    (1, "Widget A", 9.99, "widgets", 100),
    (2, "Widget B", 19.99, "widgets", 50),
    (3, "Gadget X", 49.99, "gadgets", 25),
    (4, "Gadget Y", -5.00, "gadgets", 0),      # negative price
    (5, "Thing Z", 999.99, "things", 200),      # potential outlier
    (6, "Widget C", None, "widgets", 75),       # null price
])
conn.commit()

def profile_column(conn, table, col, col_type, total_rows):
    nulls = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]
    distinct = conn.execute(f"SELECT COUNT(DISTINCT {col}) FROM {table}").fetchone()[0]
    stats = {"null_pct": round(nulls / total_rows * 100, 1), "distinct_count": distinct}
    if col_type in ("INTEGER", "REAL"):
        row = conn.execute(f"SELECT MIN({col}), MAX({col}), AVG({col}) FROM {table} WHERE {col} IS NOT NULL").fetchone()
        if row[0] is not None:
            stats.update(min=row[0], max=row[1], mean=round(row[2], 2))
    return stats

total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
for cid, name, ctype, *_ in conn.execute("PRAGMA table_info(products)").fetchall():
    print(name, profile_column(conn, "products", name, ctype, total))
# price {'null_pct': 16.7, 'distinct_count': 5, 'min': -5.0, 'max': 999.99, 'mean': 214.99}
```

Seeing `min=-5.0` and `mean=214.99` *before* writing a validity rule is what tells you to write `price >= 0` (an obvious business rule) rather than guessing a max bound out of thin air — and it's what flags `999.99` as worth a statistical outlier check (Section 4) rather than a hard-coded range that would have been wrong for `Thing Z`'s legitimate price tier.

---

## 3. The Great Expectations Pattern: Expectations, Suites, Checkpoints

[Great Expectations](https://greatexpectations.io/) is the most widely used validation framework in the data engineering ecosystem, and its vocabulary shows up in interviews independent of whether the actual library is installed. The pattern has three pieces:

```text
Expectation:       a single, named, parameterized check
                    ("expect_column_values_to_not_be_null", column='price')

ExpectationSuite:   a named collection of expectations for one dataset
                    (all the rules that define "products looks healthy")

Checkpoint:         runs a suite against a batch of actual data,
                    returns pass/fail per expectation plus a summary
```

The three map directly onto three responsibilities: *what* to check (Expectation), *what a healthy dataset means, as a group of checks* (Suite), *the execution engine that runs the group against real data* (Checkpoint). Building a miniature version from scratch makes that separation concrete:

```python
class Expectation:
    def __init__(self, etype, **kwargs):
        self.etype = etype
        self.kwargs = kwargs

class ExpectationSuite:
    def __init__(self, name):
        self.name = name
        self.expectations = []

    def expect_column_values_to_not_be_null(self, column):
        self.expectations.append(Expectation("not_null", column=column))

    def expect_column_values_to_be_between(self, column, min_value, max_value):
        self.expectations.append(Expectation("between", column=column, min_value=min_value, max_value=max_value))

    def expect_column_values_to_be_unique(self, column):
        self.expectations.append(Expectation("unique", column=column))

    def expect_table_row_count_to_be_between(self, min_value, max_value):
        self.expectations.append(Expectation("row_count", min_value=min_value, max_value=max_value))


class Checkpoint:
    def __init__(self, conn, table):
        self.conn = conn
        self.table = table

    def run(self, suite):
        results = [self._evaluate(e) for e in suite.expectations]
        passed = sum(1 for r in results if r["success"])
        return {"suite": suite.name, "total": len(results), "passed": passed,
                "failed": len(results) - passed, "results": results}

    def _evaluate(self, exp):
        kw, c = exp.kwargs, self.conn
        if exp.etype == "not_null":
            n = c.execute(f"SELECT COUNT(*) FROM {self.table} WHERE {kw['column']} IS NULL").fetchone()[0]
            return {"expectation": exp.etype, "column": kw["column"], "success": n == 0, "observed": f"{n} nulls"}
        if exp.etype == "between":
            col, lo, hi = kw["column"], kw["min_value"], kw["max_value"]
            n = c.execute(f"SELECT COUNT(*) FROM {self.table} WHERE {col} IS NOT NULL AND ({col} < ? OR {col} > ?)",
                          (lo, hi)).fetchone()[0]
            return {"expectation": exp.etype, "column": col, "success": n == 0, "observed": f"{n} out of range"}
        if exp.etype == "unique":
            col = kw["column"]
            total = c.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]
            distinct = c.execute(f"SELECT COUNT(DISTINCT {col}) FROM {self.table}").fetchone()[0]
            return {"expectation": exp.etype, "column": col, "success": total == distinct,
                    "observed": f"{total - distinct} duplicates"}
        if exp.etype == "row_count":
            n = c.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]
            return {"expectation": exp.etype, "success": kw["min_value"] <= n <= kw["max_value"], "observed": f"row_count={n}"}

suite = ExpectationSuite("products_quality_suite")
suite.expect_table_row_count_to_be_between(min_value=1, max_value=1000)
suite.expect_column_values_to_not_be_null(column="price")
suite.expect_column_values_to_be_between(column="price", min_value=0, max_value=500)
suite.expect_column_values_to_be_unique(column="name")

result = Checkpoint(conn, "products").run(suite)
print(f"{result['passed']}/{result['total']} passed")
for r in result["results"]:
    print(f"  [{'PASS' if r['success'] else 'FAIL'}] {r['expectation']} -> {r['observed']}")
# 2/4 passed
#   [PASS] row_count -> row_count=6
#   [FAIL] not_null -> 1 nulls
#   [FAIL] between -> 2 out of range
#   [PASS] unique -> 0 duplicates
```

The reason this three-layer split earns its complexity over the assertion function in Section 1: a `Suite` is a portable, inspectable *artifact* — it can be version-controlled, diffed between two commits, and rerun against a completely different table (a staging copy, last month's snapshot) without touching the check logic itself. That portability is what makes "did our data quality rules change, and when" an answerable question, the same way a data contract (`concepts/03_data_contracts.md`) makes "did our schema change" answerable.

---

## 4. Statistical Validation: Catching What a Range Rule Can't

A fixed range rule (`price BETWEEN 0 AND 500`) has to be re-guessed by hand for every column and breaks the moment the underlying distribution shifts. **Z-score based outlier detection** instead flags any value unusually far from the *current* data's own mean:

```python
def detect_outliers(conn, table, column, max_zscore=2.0):
    values = [r[0] for r in conn.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL").fetchall()]
    if len(values) < 2:
        return {"outliers": [], "note": "not enough data"}
    mean, stdev = statistics.mean(values), statistics.stdev(values)
    if stdev == 0:
        return {"outliers": [], "mean": mean, "stdev": 0}
    outliers = [{"value": v, "zscore": round((v - mean) / stdev, 2)} for v in values if abs((v - mean) / stdev) > max_zscore]
    return {"mean": round(mean, 2), "stdev": round(stdev, 2), "outliers": outliers}

print(detect_outliers(conn, "products", "price", max_zscore=1.5))
# {'mean': 214.99, 'stdev': ..., 'outliers': [{'value': 999.99, 'zscore': ...}]}
```

Z-score checks trade a hard-coded guess for a threshold expressed in units of "how unusual is this relative to everything else right now" — which is also exactly the mechanism behind ongoing anomaly detection on metrics like daily row counts, covered in `concepts/05_anomaly_detection_and_monitoring.md`. The difference between the two is *what's being scored*: here it's individual row values within one snapshot; there it's a single aggregate metric (like row count) across successive pipeline runs over time.

---

## 5. Schema Validation

Every check so far assumes the table's *shape* is correct and looks at its *values*. Schema validation checks the shape itself — the right columns exist, with the right types, with the right nullability — before any value-level check runs at all.

```python
def validate_schema(conn, table, expected_columns):
    actual = {row[1]: {"type": row[2], "notnull": bool(row[3])} for row in conn.execute(f"PRAGMA table_info({table})")}
    issues = []
    for exp in expected_columns:
        name = exp["name"]
        if name not in actual:
            issues.append(f"Missing column: {name}")
            continue
        if exp.get("type") and actual[name]["type"].upper() != exp["type"].upper():
            issues.append(f"Column '{name}': expected {exp['type']}, got {actual[name]['type']}")
        if exp.get("nullable") is False and not actual[name]["notnull"]:
            issues.append(f"Column '{name}': should be NOT NULL but is nullable")
    return {"valid": len(issues) == 0, "issues": issues}

expected = [
    {"name": "id", "type": "INTEGER"},
    {"name": "name", "type": "TEXT", "nullable": False},
    {"name": "price", "type": "REAL"},
    {"name": "updated_at", "type": "TEXT"},  # doesn't exist in this table
]
print(validate_schema(conn, "products", expected))
# {'valid': False, 'issues': ["Missing column: updated_at"]}
```

Schema validation is the value-level checks' prerequisite, not a substitute for them — a table can pass every schema check (right columns, right types) and still be full of nulls, duplicates, and out-of-range values. It's also the check that belongs *earliest* in a pipeline: if the schema itself is wrong, running expensive value-level checks against columns that may not even mean what they used to is wasted work. This is precisely the mechanical check behind enforcing a data contract in CI, which is the next concept.

---

## Key Takeaways

- Assertion-based, row-at-a-time validation (check + raise) is legitimately sufficient for a lot of pipelines — it only becomes limiting once dataset-level checks (row count, uniqueness) or repeatable, version-controlled rule sets are needed.
- Profile before you validate: a column's actual min/max/null-rate/distinct-count tells you what threshold to write, rather than guessing one and hoping it doesn't produce false positives on legitimate data.
- The Great Expectations pattern splits into three concerns — Expectation (one check), Suite (a named, portable collection of checks for one dataset), Checkpoint (the engine that runs a suite against real data and reports pass/fail) — and that separation is what makes a rule set version-controllable and reusable across environments, not just a bigger validation function.
- Z-score-based statistical validation catches outliers relative to the data's own current distribution, avoiding hard-coded thresholds that go stale as the data legitimately shifts.
- Schema validation checks structure (columns, types, nullability) and belongs before value-level checks — a table can be perfectly well-typed and still be full of bad values, but a schema mismatch invalidates the assumptions every downstream value check depends on.
- See `concepts/03_data_contracts.md` for how schema validation becomes an enforced, versioned agreement between a producer and its consumers, rather than a one-off check run by hand.
