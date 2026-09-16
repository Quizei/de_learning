# Data Quality & Governance — Coding Problems

Four harder, mid-to-senior-level problems: a full data quality monitoring system (checks, alerting, and scoring combined into one engine — the "hard" tier problem this course's bonus problem set only ever described, never wrote out, since its `hard/` directory shipped empty), a schema contract enforcer with a version registry, a lineage impact analyzer that handles a diamond dependency and a cycle, and a multi-metric anomaly detection engine with severity routing. Each includes a problem statement, sample input/output, and a hidden reference solution with an explanation of the pattern it's testing.

How to use this file: read the problem, write your own solution against the sample input, and only then expand the reference solution. A fuzzy-matching deduplication pipeline — the other classic "hard" data quality problem — is already worked in full in `etl_elt_patterns/practice/coding_problems.md`, Problem 2; it's not repeated here, but it's worth doing if you haven't, since Exercise 2 in this folder's `exercises.md` only goes as far as normalized exact-match.

---

## Problem 1: Data Quality Monitoring System

**Problem statement:** build a monitoring engine that runs a set of named checks against a table, scores the results into an overall quality score, and routes any failure to the right alerting channel based on its configured severity — the combined "checks, alerting, scoring" system this course's bonus problem set names but never implements.

**Requirements:**
- Register named checks, each with a SQL predicate (returns a count of *bad* rows), a dimension it belongs to, and a severity (`critical`, `warning`, `info`)
- Run all registered checks against a live table and record pass/fail plus the bad-row count for each
- Compute a per-dimension score and one overall weighted score
- Route failures: `critical` -> page, `warning` -> ticket, `info` -> log-only — never treat every failure identically
- Produce one structured report combining all of the above

**Sample input** — a `shipments` table:

```python
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE shipments (id INTEGER PRIMARY KEY, order_id INTEGER, weight_kg REAL, carrier TEXT, ship_date TEXT)")
conn.executemany("INSERT INTO shipments VALUES (?,?,?,?,?)", [
    (1, 101, 2.5, "UPS", "2024-06-01"),
    (2, 102, -1.0, "FedEx", "2024-06-01"),      # negative weight
    (3, 103, 3.2, None, "2024-06-02"),           # null carrier
    (4, 104, 1.8, "UPS", "2024-06-02"),
    (5, 105, 0.0, "DHL", "2024-06-03"),          # zero weight
    (6, None, 2.1, "UPS", "2024-06-03"),         # null order_id
])
conn.commit()
```

**Expected behavior:**
```text
[critical] weight_positive:  2 bad rows  -> FAIL -> routed to PAGE
[critical] order_id_present: 1 bad row   -> FAIL -> routed to PAGE
[warning]  carrier_present:  1 bad row   -> FAIL -> routed to TICKET
overall quality score: well below 100, weighted toward the critical dimension failures
```

<details>
<summary>Reference solution</summary>

```python
import sqlite3

class QualityCheck:
    def __init__(self, name, dimension, sql_bad_row_count, severity, weight=1.0):
        self.name = name
        self.dimension = dimension
        self.sql = sql_bad_row_count   # SQL returning COUNT(*) of BAD rows
        self.severity = severity       # 'critical' | 'warning' | 'info'
        self.weight = weight


class QualityMonitor:
    """
    Registers named checks, runs them against a table, scores the results,
    and routes each failure to an alerting channel based on severity.
    """
    SEVERITY_ROUTE = {"critical": "PAGE", "warning": "TICKET", "info": "LOG"}

    def __init__(self, conn, table):
        self.conn = conn
        self.table = table
        self.checks = []

    def register(self, name, dimension, sql_bad_row_count, severity="warning", weight=1.0):
        self.checks.append(QualityCheck(name, dimension, sql_bad_row_count, severity, weight))

    def run(self):
        total_rows = self.conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]
        results = []
        for check in self.checks:
            bad = self.conn.execute(check.sql).fetchone()[0]
            passed = bad == 0
            pct_good = round((total_rows - bad) / total_rows * 100, 2) if total_rows else 100
            results.append({
                "name": check.name, "dimension": check.dimension, "severity": check.severity,
                "bad_rows": bad, "passed": passed, "score": pct_good,
                "routed_to": None if passed else self.SEVERITY_ROUTE[check.severity],
            })
        return results

    def score_by_dimension(self, results):
        dims = {}
        for r in results:
            dims.setdefault(r["dimension"], []).append(r["score"])
        return {dim: round(sum(scores) / len(scores), 2) for dim, scores in dims.items()}

    def overall_score(self, results):
        if not results:
            return 100.0
        weighted = sum(r["score"] * next(c.weight for c in self.checks if c.name == r["name"]) for r in results)
        total_weight = sum(c.weight for c in self.checks)
        return round(weighted / total_weight, 2)

    def report(self):
        results = self.run()
        return {
            "table": self.table,
            "checks": results,
            "dimension_scores": self.score_by_dimension(results),
            "overall_score": self.overall_score(results),
            "alerts": {
                "page": [r["name"] for r in results if r["routed_to"] == "PAGE"],
                "ticket": [r["name"] for r in results if r["routed_to"] == "TICKET"],
                "log": [r["name"] for r in results if r["routed_to"] == "LOG"],
            },
        }


conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE shipments (id INTEGER PRIMARY KEY, order_id INTEGER, weight_kg REAL, carrier TEXT, ship_date TEXT)")
conn.executemany("INSERT INTO shipments VALUES (?,?,?,?,?)", [
    (1, 101, 2.5, "UPS", "2024-06-01"),
    (2, 102, -1.0, "FedEx", "2024-06-01"),
    (3, 103, 3.2, None, "2024-06-02"),
    (4, 104, 1.8, "UPS", "2024-06-02"),
    (5, 105, 0.0, "DHL", "2024-06-03"),
    (6, None, 2.1, "UPS", "2024-06-03"),
])
conn.commit()

monitor = QualityMonitor(conn, "shipments")
monitor.register("weight_positive", "validity",
                  "SELECT COUNT(*) FROM shipments WHERE weight_kg <= 0", severity="critical", weight=2.0)
monitor.register("order_id_present", "completeness",
                  "SELECT COUNT(*) FROM shipments WHERE order_id IS NULL", severity="critical", weight=2.0)
monitor.register("carrier_present", "completeness",
                  "SELECT COUNT(*) FROM shipments WHERE carrier IS NULL", severity="warning", weight=1.0)

report = monitor.report()
for c in report["checks"]:
    status = "PASS" if c["passed"] else f"FAIL -> {c['routed_to']}"
    print(f"  [{c['severity']}] {c['name']}: {c['bad_rows']} bad rows ({status})")
print("Dimension scores:", report["dimension_scores"])
print("Overall score:", report["overall_score"])
print("Alerts:", report["alerts"])
# [critical] weight_positive: 2 bad rows (FAIL -> PAGE)
# [critical] order_id_present: 1 bad rows (FAIL -> PAGE)
# [warning] carrier_present: 1 bad rows (FAIL -> TICKET)
# Dimension scores: {'validity': 66.67, 'completeness': 83.33}
# Overall score: 76.67
# Alerts: {'page': ['weight_positive', 'order_id_present'], 'ticket': ['carrier_present'], 'log': []}
```

**Pattern being tested:** this is `concepts/01_data_quality_dimensions.md`'s scoring model and `concepts/05_anomaly_detection_and_monitoring.md`'s severity-routing policy combined into one engine, exactly the shape a "design a data quality monitoring system" interview question is probing for — the interviewer wants to see all three pieces (a registered, extensible set of checks; a scoring model that rolls them up without hiding a critical failure inside a healthy average; a routing policy so a failure's severity determines the response) working together, not any one piece in isolation. The weighting in `overall_score` matters concretely here: without it, three roughly-equal-weight checks would average to a score that looks "mostly fine" even though two of the three failures are `critical` — weighting critical checks higher is what keeps the single overall number honest about what's actually wrong, the same concern raised about a single warehouse-wide quality score in `interview_questions/04_curveballs_tradeoffs.md`.

</details>

---

## Problem 2: Schema Contract Enforcer With Version History

**Problem statement:** build a contract registry that accepts or rejects a proposed schema version based on its declared compatibility policy against the immediately preceding version, and can explain *why* it rejected one.

**Requirements:**
- Classify every column-level change between two schemas as breaking or non-breaking (add/remove/retype/required-optional/allowed-values changes)
- Reject a new version outright if it breaks the registered `backward` compatibility policy, returning the specific breaking changes
- Accept and store a version if it's compatible, or if the policy is explicitly `none`
- Support querying the full version history and the current version

**Sample input:**
```python
v1 = {"version": "1.0.0", "compatibility": "backward", "columns": [
    {"name": "id", "type": "INTEGER", "required": True},
    {"name": "email", "type": "TEXT", "required": True},
]}
v1_1 = {"version": "1.1.0", "compatibility": "backward", "columns": [
    {"name": "id", "type": "INTEGER", "required": True},
    {"name": "email", "type": "TEXT", "required": True},
    {"name": "phone", "type": "TEXT", "required": False},   # additive
]}
v2_bad = {"version": "2.0.0", "compatibility": "backward", "columns": [
    {"name": "id", "type": "INTEGER", "required": True},
    # email removed entirely
]}
```

**Expected output:**
```text
register(v1):     accepted, version 1.0.0
register(v1_1):   accepted, version 1.1.0
register(v2_bad): rejected -- "email" removed while required, violates backward compatibility
current version:  1.1.0
```

<details>
<summary>Reference solution</summary>

```python
class ContractRegistry:
    def __init__(self):
        self.history = []

    def _diff(self, old_cols, new_cols):
        old_map = {c["name"]: c for c in old_cols}
        new_map = {c["name"]: c for c in new_cols}
        changes = []
        for name, col in old_map.items():
            if name not in new_map:
                changes.append({"column": name, "breaking": col.get("required", False),
                                 "detail": f"'{name}' removed" + (" while required" if col.get("required") else "")})
        for name, col in new_map.items():
            if name not in old_map:
                breaking = col.get("required", False) and "default" not in col
                changes.append({"column": name, "breaking": breaking, "detail": f"'{name}' added"})
        for name in old_map:
            if name in new_map:
                if not old_map[name].get("required") and new_map[name].get("required"):
                    changes.append({"column": name, "breaking": True, "detail": f"'{name}' optional -> required"})
                if old_map[name].get("type") != new_map[name].get("type"):
                    changes.append({"column": name, "breaking": True,
                                     "detail": f"'{name}' type changed {old_map[name].get('type')} -> {new_map[name].get('type')}"})
        return changes

    def register(self, spec):
        if self.history:
            prev = self.history[-1]
            changes = self._diff(prev["columns"], spec["columns"])
            breaking = [c for c in changes if c["breaking"]]
            if prev["compatibility"] == "backward" and breaking:
                return {"accepted": False, "reason": "violates backward compatibility", "breaking_changes": breaking}
        self.history.append(spec)
        return {"accepted": True, "version": spec["version"]}

    def current(self):
        return self.history[-1] if self.history else None

    def get_history(self):
        return [s["version"] for s in self.history]


registry = ContractRegistry()
v1 = {"version": "1.0.0", "compatibility": "backward",
      "columns": [{"name": "id", "type": "INTEGER", "required": True}, {"name": "email", "type": "TEXT", "required": True}]}
v1_1 = {"version": "1.1.0", "compatibility": "backward",
        "columns": v1["columns"] + [{"name": "phone", "type": "TEXT", "required": False}]}
v2_bad = {"version": "2.0.0", "compatibility": "backward",
          "columns": [{"name": "id", "type": "INTEGER", "required": True}]}

print(registry.register(v1))     # {'accepted': True, 'version': '1.0.0'}
print(registry.register(v1_1))   # {'accepted': True, 'version': '1.1.0'}
result = registry.register(v2_bad)
print(result["accepted"], result["breaking_changes"])
# False [{'column': 'email', 'breaking': True, "detail": "'email' removed while required"}]
print(registry.get_history())    # ['1.0.0', '1.1.0']
print(registry.current()["version"])  # 1.1.0
```

**Pattern being tested:** this is the mechanical enforcement layer behind `concepts/03_data_contracts.md`'s claim that a contract registry rejects a breaking version rather than silently accepting it — the interview signal is building the rejection to be *specific* (which columns, why) rather than a bare boolean, because a registry that only says "rejected" with no detail forces whoever hit the rejection to re-derive the diff by hand. Note that `v2_bad` is never appended to `self.history` on rejection — `current()` still correctly returns `1.1.0` afterward, which is the detail that would be easy to get wrong (accidentally storing a rejected version anyway) and is worth testing explicitly.

</details>

---

## Problem 3: Lineage Impact Analyzer

**Problem statement:** build a lineage graph traversal that correctly handles a **diamond dependency** (two different paths converging on the same downstream dataset) without double-counting it, and detects a **cycle** if one is accidentally introduced, rather than looping forever.

**Requirements:**
- `add_edge(source, target)` records a lineage edge
- `downstream(dataset)` returns every dataset transitively affected, each exactly once, even if reachable via more than one path
- `has_cycle()` detects whether the graph contains a cycle at all
- `downstream` must terminate (not infinite-loop) even if called on a graph that contains a cycle

**Sample input:**
```text
edges:
  raw_orders -> staging_orders
  raw_customers -> staging_customers
  staging_orders -> mart_revenue
  staging_customers -> mart_revenue      <- diamond: mart_revenue has two parents
  mart_revenue -> report_dashboard
```

**Expected output:**
```text
downstream("raw_orders") = ['staging_orders', 'mart_revenue', 'report_dashboard']
   -- mart_revenue appears exactly once, even though it's also reachable via staging_customers
has_cycle() = False
```

<details>
<summary>Reference solution</summary>

```python
class LineageGraph:
    def __init__(self):
        self.edges = {}  # source -> set of targets

    def add_edge(self, source, target):
        self.edges.setdefault(source, set()).add(target)

    def downstream(self, dataset):
        """BFS forward, tracking visited so a diamond-shaped path never double-counts a node."""
        visited = set()
        queue = [dataset]
        result = []
        while queue:
            current = queue.pop(0)
            for neighbor in self.edges.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    result.append(neighbor)
                    queue.append(neighbor)
        return result

    def has_cycle(self):
        """DFS with a recursion-stack set: a node reachable from itself, via the CURRENT path, is a cycle."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in set(self.edges) | {t for targets in self.edges.values() for t in targets}}

        def visit(node):
            color[node] = GRAY
            for neighbor in self.edges.get(node, []):
                if color[neighbor] == GRAY:
                    return True             # back edge to a node on the current path -> cycle
                if color[neighbor] == WHITE and visit(neighbor):
                    return True
            color[node] = BLACK
            return False

        return any(color[node] == WHITE and visit(node) for node in list(color))


graph = LineageGraph()
for src, tgt in [
    ("raw_orders", "staging_orders"), ("raw_customers", "staging_customers"),
    ("staging_orders", "mart_revenue"), ("staging_customers", "mart_revenue"),
    ("mart_revenue", "report_dashboard"),
]:
    graph.add_edge(src, tgt)

print(graph.downstream("raw_orders"))
# ['staging_orders', 'mart_revenue', 'report_dashboard']
print(graph.has_cycle())
# False

# Introduce a cycle: report_dashboard incorrectly feeds back into raw_orders
graph.add_edge("report_dashboard", "raw_orders")
print(graph.has_cycle())
# True
print(graph.downstream("raw_orders"))
# still terminates and returns every node reachable, each exactly once, despite the cycle
```

**Pattern being tested:** two correctness properties that are easy to get wrong under time pressure. First, the `visited` set in `downstream` has to be checked *before* a node is enqueued (not just before it's processed) — otherwise a diamond dependency like `mart_revenue` above gets added to the queue twice and, depending on implementation, can appear twice in the result or even be processed twice. Second, `has_cycle` needs a proper three-color (white/gray/black) DFS, not just a single global `visited` set — a single visited set alone cannot distinguish "this node is an ancestor on my current path" (a real cycle) from "this node was already fully explored via a different, unrelated path" (a diamond, not a cycle) — conflating the two would make `has_cycle` wrongly report every diamond-shaped lineage graph as cyclic. This distinction is exactly why a real lineage tool needs cycle detection as a distinct check from a plain reachability walk, and why a naive "have I seen this node before" check is the wrong tool for it.

</details>

---

## Problem 4: Multi-Metric Anomaly Detection Engine

**Problem statement:** build an engine that tracks a rolling history for multiple named metrics (row count, null rate, average value — anything numeric), flags an anomaly per metric using a z-score against that metric's own history, and produces one combined alert routing everything by severity.

**Requirements:**
- `record(metric_name, value, timestamp)` appends an observation to that metric's history
- `check(metric_name, today_value, max_zscore, severity)` compares today's value against the metric's rolling history (excluding today's own value) and returns whether it's anomalous
- Handle a metric with fewer than 2 historical observations gracefully (no crash, clearly marked as "insufficient history")
- Combine several metrics' check results into one routed alert summary

**Sample input:**
```python
history = {
    "orders.row_count": [1020, 980, 1050, 990, 1010, 970, 1030],
    "customers.null_rate_email": [1.2, 1.5, 1.1, 1.8, 1.3],
}
todays_values = {"orders.row_count": 145, "customers.null_rate_email": 1.6}
```

**Expected output:**
```text
orders.row_count:            ANOMALY (z far below normal -- volume collapsed)      -> critical -> PAGE
customers.null_rate_email:   normal (within expected range)                       -> no alert
```

<details>
<summary>Reference solution</summary>

```python
import statistics

class AnomalyEngine:
    def __init__(self):
        self.history = {}  # metric_name -> list of past values, oldest to newest

    def record(self, metric_name, value):
        self.history.setdefault(metric_name, []).append(value)

    def check(self, metric_name, today_value, max_zscore=3.0, severity="warning"):
        past = self.history.get(metric_name, [])
        if len(past) < 2:
            return {"metric": metric_name, "anomaly": False, "note": "insufficient history", "severity": severity}
        mean, stdev = statistics.mean(past), statistics.stdev(past)
        if stdev == 0:
            return {"metric": metric_name, "anomaly": today_value != mean, "zscore": None, "severity": severity}
        z = (today_value - mean) / stdev
        return {"metric": metric_name, "mean": round(mean, 2), "stdev": round(stdev, 2),
                "zscore": round(z, 2), "anomaly": abs(z) > max_zscore, "severity": severity}

    def evaluate_all(self, checks):
        """checks: list of (metric_name, today_value, max_zscore, severity)"""
        results = [self.check(*c) for c in checks]
        route = {"PAGE": [], "TICKET": [], "LOG": []}
        severity_map = {"critical": "PAGE", "warning": "TICKET", "info": "LOG"}
        for r in results:
            if r["anomaly"]:
                route[severity_map[r["severity"]]].append(r["metric"])
        return {"results": results, "alerts": route}


engine = AnomalyEngine()
for v in [1020, 980, 1050, 990, 1010, 970, 1030]:
    engine.record("orders.row_count", v)
for v in [1.2, 1.5, 1.1, 1.8, 1.3]:
    engine.record("customers.null_rate_email", v)

summary = engine.evaluate_all([
    ("orders.row_count", 145, 3.0, "critical"),
    ("customers.null_rate_email", 1.6, 3.0, "warning"),
])
for r in summary["results"]:
    print(f"  {r['metric']}: anomaly={r['anomaly']}")
print("Alerts:", summary["alerts"])
# orders.row_count: anomaly=True
# customers.null_rate_email: anomaly=False
# Alerts: {'PAGE': ['orders.row_count'], 'TICKET': [], 'LOG': []}
```

**Pattern being tested:** this generalizes the single-metric row-count and null-rate-drift checks in `concepts/05_anomaly_detection_and_monitoring.md` into one reusable engine that can watch any number of named metrics side by side, which is closer to what a real monitoring system actually looks like — dozens of metrics, not one. The `len(past) < 2` guard matters more than it looks: a metric that's brand new (a table added last week) has no meaningful history yet, and `statistics.stdev` on fewer than 2 points raises an exception outright — silently crashing the whole `evaluate_all` batch over one new metric would be a worse failure than any individual anomaly this engine is trying to catch, so a monitoring system has to be at least as defensive about its own inputs as the checks it runs.

</details>
