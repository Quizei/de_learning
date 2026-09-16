# Capstone Project: Build a QualityChecker Tool

## Scenario

You're asked to build a small internal tool that a data platform team could actually reuse across many tables: a rule-based quality checker that profiles a table, runs checks across the standard dimensions, validates it against a data contract, and rolls everything into one scored, alerting-aware report. This is deliberately not a one-off validation script for one table — it's the general-purpose shape from `concepts/01_data_quality_dimensions.md` through `concepts/03_data_contracts.md`, expressed as reusable code that has to handle a table it's never seen before, not just the one it was tested against.

## Learning Goal

Implement a `QualityChecker` class against the interface specified below, backed by a live SQLite connection. This exercises dimension-level checks (completeness, uniqueness, validity, consistency), a weighted scoring model, contract validation, and severity-aware reporting, all working together against an arbitrary table and an arbitrary contract spec — not hand-tuned to one demo dataset.

This brief gives you the class interface, the expected behavior of each method, and a worked example of what running the finished tool should produce against a deliberately messy sample database — build the implementation yourself before checking your design against the notes at the end.

---

## The Interface

```python
import sqlite3


class QualityChecker:
    """
    A reusable, rule-based data quality checker for a SQLite table.

    Usage:
        qc = QualityChecker(conn, "customers")
        qc.profile()
        qc.check_completeness(["name", "email"])
        qc.check_uniqueness(["email"])
        qc.check_validity(rules)
        qc.check_consistency(checks)
        qc.validate_contract(contract_spec)
        report = qc.generate_report()
    """

    def __init__(self, conn, table):
        self.conn = conn
        self.table = table
        self._row_count = self._get_row_count()
        self._scores = {}     # dimension_name -> score (0-100)
        self._issues = []     # list of human-readable issue strings, accumulated across all checks
        # TODO: whatever else you need to accumulate detail across check calls
        # for generate_report() to assemble into one structured output

    def _get_row_count(self):
        return self.conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]

    def _get_columns(self):
        """Returns [(column_name, column_type), ...] via PRAGMA table_info."""
        return [(r[1], r[2]) for r in self.conn.execute(f"PRAGMA table_info({self.table})")]

    # -----------------------------------------------------------------
    # 1. PROFILE
    # -----------------------------------------------------------------
    def profile(self):
        """
        Profile every column: type, null count/pct, distinct count, and for
        numeric columns, min/max/mean/stdev.

        Returns:
            Dict: {"table": ..., "row_count": ..., "columns": {col_name: {...stats...}}}

        Requirements:
            - Must not crash on a table with zero rows (guard every division).
            - Numeric stats (min/max/mean/stdev) only apply to INTEGER/REAL columns,
              and only when at least 2 non-null values exist (statistics.stdev needs >= 2).
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 2. CHECK COMPLETENESS
    # -----------------------------------------------------------------
    def check_completeness(self, required_columns=None):
        """
        Check completeness for the given columns (or every column, if None).

        Args:
            required_columns: list of column names, or None for all columns.

        Returns:
            Dict: {col_name: {"missing": int, "total": int, "completeness_pct": float}}

        Requirements:
            - Records the average completeness_pct into self._scores["completeness"].
            - Appends a human-readable string to self._issues for any column below 100%
              (e.g. "Completeness: email has 3 missing values (91.7% complete)").
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 3. CHECK UNIQUENESS
    # -----------------------------------------------------------------
    def check_uniqueness(self, key_columns):
        """
        Check for duplicate rows on the given key columns (exact-match grouping).

        Returns:
            Dict: {"key_columns": [...], "total_rows": int, "distinct_rows": int,
                   "duplicate_rows": int, "uniqueness_pct": float, "duplicate_groups": [...]}

        Requirements:
            - "duplicate_groups" is a list of dicts, one per group with count > 1,
              containing the key column values plus a "count" field.
            - Records uniqueness_pct into self._scores["uniqueness"].
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 4. CHECK VALIDITY
    # -----------------------------------------------------------------
    def check_validity(self, rules):
        """
        Check validity against a dict of rules.

        Args:
            rules: {column_name: (description, sql_condition_true_for_valid_rows)}

        Returns:
            Dict: {col_name: {"rule": desc, "valid": int, "invalid": int, "validity_pct": float}}

        Requirements:
            - Records the average validity_pct into self._scores["validity"].
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 5. CHECK CONSISTENCY
    # -----------------------------------------------------------------
    def check_consistency(self, checks):
        """
        Run cross-field or cross-table consistency checks.

        Args:
            checks: list of (description, sql_returning_count_of_inconsistent_rows)

        Returns:
            List of dicts: [{"check": desc, "inconsistent_rows": int, "passed": bool}, ...]

        Requirements:
            - Records the pass-rate (percentage of checks that passed, NOT rows) into
              self._scores["consistency"].
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 6. VALIDATE CONTRACT
    # -----------------------------------------------------------------
    def validate_contract(self, contract_spec):
        """
        Validate this table against a data contract specification.

        Args:
            contract_spec: {
                "contract_name": str, "version": str,
                "schema": {"columns": [{"name", "type", "required", "unique"?,
                                         "min_value"?, "max_value"?, "allowed_values"?}, ...]},
                "quality_slas": {"completeness_threshold": float, "uniqueness_threshold": float,
                                  "min_row_count": int, "max_row_count": int},
            }

        Returns:
            Dict: {"contract": name, "version": version, "compliant": bool,
                   "failures": [str, ...], "failure_count": int}

        Requirements:
            - Schema check: every declared column exists, with a matching type.
            - Completeness SLA: every REQUIRED column must clear completeness_threshold.
            - Uniqueness SLA: every column marked "unique" must clear uniqueness_threshold.
            - Value constraints: min_value / max_value / allowed_values, where declared.
            - Row count bounds from quality_slas.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 7. GENERATE REPORT
    # -----------------------------------------------------------------
    def generate_report(self, weights=None):
        """
        Roll every check that's been run so far into one structured report.

        Args:
            weights: optional dict of {dimension: weight} for the overall score.
                     Default: equal weight across whichever dimensions have been scored.

        Returns:
            Dict: {"table": ..., "row_count": ..., "overall_score": float, "grade": "A".."F",
                   "dimension_scores": {...}, "issues": [...], "issue_count": int,
                   "recommendations": [str, ...]}

        Requirements:
            - overall_score is a weighted average across whatever's in self._scores --
              it must not assume all six dimensions were checked (a caller may only have
              run check_completeness and check_validity, for instance).
            - Grade: A >= 95, B >= 85, C >= 70, D >= 50, else F.
            - "recommendations" is a short, generated list of actionable next steps based
              on which dimensions scored below a reasonable bar (your call what "reasonable"
              means per dimension, document your choice).
            - TODO: implement
        """
        raise NotImplementedError
```

---

## Worked Example: What the Finished Tool Should Do

This is the acceptance test for your implementation — build toward producing exactly this behavior.

```python
conn = sqlite3.connect(":memory:")
conn.execute("""
    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY, name TEXT, email TEXT, age INTEGER, country TEXT
    )
""")
conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
    (1, "Alice Johnson", "alice@shop.com", 29, "US"),
    (2, "Bob Smith",     "bob@shop.com",   35, "US"),
    (3, None,            "charlie@shop.com", 42, "UK"),        # null name
    (4, "Diana Prince",  None,             31, "US"),           # null email
    (5, "Eve Adams",     "eve@shop",       -3, "XX"),           # bad email, negative age, bad country
    (6, "Alice Johnson", "alice@shop.com", 29, "US"),           # duplicate of row 1
])
conn.commit()

qc = QualityChecker(conn, "customers")

profile = qc.profile()
# profile["columns"]["age"] should include min=-3, max=42, mean=..., stdev=...

comp = qc.check_completeness(["name", "email", "age", "country"])
# comp["name"] == {"missing": 1, "total": 6, "completeness_pct": 83.33}

uniq = qc.check_uniqueness(["name", "email"])
# uniq["duplicate_rows"] == 1, uniq["duplicate_groups"] == [{"name": "Alice Johnson", "email": "alice@shop.com", "count": 2}]

val = qc.check_validity({
    "age": ("age between 0 and 120", "age BETWEEN 0 AND 120"),
    "email": ("email contains @ and .", "email LIKE '%@%.%'"),
    "country": ("country is a known 2-letter code", "country IN ('US','UK','CA','DE','FR')"),
})
# val["age"]["invalid"] == 1, val["email"]["invalid"] == 2 (one null, one malformed -- decide how you treat nulls
#   in a validity rule and document it: this brief expects nulls to be excluded from the denominator, not
#   counted as automatic failures, since completeness already owns "is it missing")

report = qc.generate_report()
print(report["overall_score"], report["grade"])
# A score well below 95 given the injected issues above; grade should NOT be "A"
print(report["issues"])
# Should include something for the missing name, missing email, the duplicate pair,
# the invalid age, and the invalid country -- one readable string per finding, not just a number.
```

### Contract validation example

```python
CUSTOMER_CONTRACT = {
    "contract_name": "customers", "version": "1.0.0",
    "schema": {"columns": [
        {"name": "customer_id", "type": "INTEGER", "required": True, "unique": True},
        {"name": "name", "type": "TEXT", "required": True},
        {"name": "email", "type": "TEXT", "required": True, "unique": True},
        {"name": "age", "type": "INTEGER", "required": True, "min_value": 0, "max_value": 120},
        {"name": "country", "type": "TEXT", "required": True, "allowed_values": ["US", "UK", "CA", "DE", "FR"]},
    ]},
    "quality_slas": {"completeness_threshold": 95.0, "uniqueness_threshold": 98.0,
                      "min_row_count": 5, "max_row_count": 100000},
}

result = qc.validate_contract(CUSTOMER_CONTRACT)
print(result["compliant"])  # False
for f in result["failures"]:
    print(" -", f)
# Expect failures naming: name/email completeness below threshold, email uniqueness below
# threshold, age below min_value in at least one row, country not in allowed_values in at
# least one row -- five distinct, specific failure strings, not one generic "contract failed."
```

---

## Design Notes and Judgment Calls to Make Yourself

- **How validity treats nulls:** decide once, document it, and apply it consistently — this brief's worked example expects a validity rule to only evaluate *non-null* values (nulls are completeness's job to catch, not validity's), but "nulls count as automatically invalid" is a defensible alternative choice as long as you're explicit about which one your `check_validity` implements.
- **`check_uniqueness`'s duplicate_groups:** build this from a single `GROUP BY ... HAVING COUNT(*) > 1` query, not by re-scanning the whole table row by row in Python — the SQL engine is the right tool for this, and it's the same reasoning as preferring `PRAGMA table_info` over hand-parsing DDL in the sibling `SchemaDesigner` project.
- **`generate_report`'s weighting:** decide what "equal weight across whatever's been checked" means precisely when, say, only 3 of 6 possible dimensions were run — the report should not silently treat unscored dimensions as either 100% (too generous) or 0% (too harsh); they should simply not enter the weighted average at all.
- **`validate_contract`'s failure messages:** make every failure string specific enough to act on without re-running the check (name the column, the actual value, the threshold) — a report full of "SLA failed" with no further detail forces whoever reads it to go re-derive what actually broke, exactly the trap named in `interview_questions/03_critique_and_debug.md`, Case 3.

## Stretch Goals

- Add a `check_freshness(date_column, max_age_days)` method using the pattern from `concepts/01_data_quality_dimensions.md`, section 2, and fold its score into `generate_report` as a sixth dimension.
- Add a `check_row_count_anomaly(history_counts, max_zscore)` method implementing the rolling-baseline pattern from `concepts/05_anomaly_detection_and_monitoring.md`, and route any anomaly it finds through a `severity` argument the same way `practice/coding_problems.md`'s monitoring engine does — this turns the project from a point-in-time checker into something closer to real ongoing monitoring.
- Add a `track_lineage(lineage_table)` method that reads a `(source, target, transformation)` edge table and exposes upstream/downstream traversal for whichever table this checker is currently pointed at, using the BFS pattern from `concepts/04_lineage_and_cataloging.md`.
- Make `validate_contract` return not just pass/fail but a *diff* against the previous time it was run (requires persisting prior results somewhere) — the mechanical basis of noticing a contract compliance regression between two runs, not just a single point-in-time snapshot.

## Evaluation Criteria

- `profile`, `check_completeness`, `check_uniqueness`, `check_validity`, and `check_consistency` all work correctly against a table they were never specifically tuned for, not just the worked example above — test your implementation against a second, different sample table before considering it done.
- `check_uniqueness`'s `duplicate_groups` and `check_validity`'s per-column results are specific enough to act on, not just aggregate percentages.
- `validate_contract` correctly fails on every category of violation named in its docstring (missing column, type mismatch, completeness SLA, uniqueness SLA, min/max/allowed_values, row count bounds) against a contract you construct yourself with at least one violation in each category.
- `generate_report` never crashes when only a subset of dimensions have been checked, and its `issues` list is specific enough that someone who never saw the raw data could understand what's wrong from reading it alone.
- The worked example above reproduces the stated expected results when run against your implementation.
