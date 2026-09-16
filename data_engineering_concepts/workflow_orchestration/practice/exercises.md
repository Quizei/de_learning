# Workflow Orchestration — Practice Exercises

Ten exercises covering execution order, cron scheduling, cycle detection, DAG design, trigger rules, retry logic, cross-task data passing, failure-handling strategy design, DAG validation, and a full end-to-end pipeline simulation.

How to use this file: read the exercise, commit to your own answer — write the code or write down the reasoning — before expanding the reference solution. Every solution is runnable, dependency-free Python, exactly as it would run in a `python3` shell.

---

## Exercise 1: Determine Execution Order

Given these task dependencies:

```text
download_data      -> validate_schema
download_data      -> check_freshness
validate_schema    -> clean_data
check_freshness    -> clean_data
clean_data         -> enrich_data
clean_data         -> compute_aggregates
enrich_data        -> build_report
compute_aggregates -> build_report
build_report       -> send_email
```

**Your task:** write a function that returns a valid execution order. Which tasks can run in parallel?

<details>
<summary>Reference answer</summary>

```python
from collections import defaultdict, deque

def topological_sort(graph):
    in_degree = defaultdict(int)
    nodes = set(graph)
    for n in graph:
        for d in graph[n]:
            in_degree[d] += 1
            nodes.add(d)
    queue = deque(n for n in nodes if in_degree[n] == 0)
    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for d in graph.get(n, []):
            in_degree[d] -= 1
            if in_degree[d] == 0:
                queue.append(d)
    return order

graph = {
    "download_data":      ["validate_schema", "check_freshness"],
    "validate_schema":    ["clean_data"],
    "check_freshness":    ["clean_data"],
    "clean_data":         ["enrich_data", "compute_aggregates"],
    "enrich_data":        ["build_report"],
    "compute_aggregates": ["build_report"],
    "build_report":       ["send_email"],
    "send_email":         [],
}
print(topological_sort(graph))
```

```text
['download_data', 'validate_schema', 'check_freshness', 'clean_data',
 'enrich_data', 'compute_aggregates', 'build_report', 'send_email']
```

Parallel groups (read off as "waves" of in-degree-zero nodes):

```text
Level 1: [download_data]
Level 2: [validate_schema, check_freshness]      <- parallel
Level 3: [clean_data]
Level 4: [enrich_data, compute_aggregates]        <- parallel
Level 5: [build_report]
Level 6: [send_email]
```

*(See `concepts/01_dag_fundamentals.md`, section 3.)*

</details>

---

## Exercise 2: Write Cron Expressions

Write the cron expression (`minute hour day_of_month month day_of_week`) for each:

```text
a) Every day at 2:30 AM
b) Every Monday and Friday at 9 AM
c) Every 15 minutes
d) 6 PM on the 28th of each month
e) Every weekday (Mon-Fri) at 7 AM and 7 PM
f) Every Sunday at midnight
```

<details>
<summary>Reference answer</summary>

```text
a) 30 2 * * *
b) 0 9 * * 1,5
c) */15 * * * *
d) 0 18 28 * *
e) 0 7,19 * * 1-5
f) 0 0 * * 0
```

The two easiest mistakes: forgetting that a **list** (`1,5` for "Monday and Friday") and a **range** (`1-5` for "Monday through Friday") are different syntax for genuinely different requirements, and forgetting that the day-of-week field is `0`-indexed on Sunday, not Monday.

*(See `concepts/03_scheduling_dependencies.md`, section 1.)*

</details>

---

## Exercise 3: Detect Invalid DAGs

Which of these contain a cycle?

```text
DAG A:  task1 -> task2 -> task3 -> task4
DAG B:  task1 -> task2 -> task3 -> task1
DAG C:  task1 -> task2 -> task4
        task1 -> task3 -> task4
DAG D:  task1 -> task2 -> task4 -> task2
DAG E:  task1 -> task2 -> task3 -> task4 -> task5 -> task3
```

**Your task:** implement `has_cycle(graph)` and test each.

<details>
<summary>Reference answer</summary>

```python
def has_cycle(graph):
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    def dfs(n):
        color[n] = GRAY
        for nb in graph.get(n, []):
            if color.get(nb, WHITE) == GRAY:
                return True
            if color.get(nb, WHITE) == WHITE and dfs(nb):
                return True
        color[n] = BLACK
        return False
    return any(color[n] == WHITE and dfs(n) for n in graph)

dags = {
    "A": {"t1": ["t2"], "t2": ["t3"], "t3": ["t4"], "t4": []},
    "B": {"t1": ["t2"], "t2": ["t3"], "t3": ["t1"]},
    "C": {"t1": ["t2", "t3"], "t2": ["t4"], "t3": ["t4"], "t4": []},
    "D": {"t1": ["t2"], "t2": ["t4"], "t4": ["t2"]},
    "E": {"t1": ["t2"], "t2": ["t3"], "t3": ["t4"], "t4": ["t5"], "t5": ["t3"]},
}
for name, g in dags.items():
    print(name, "INVALID" if has_cycle(g) else "VALID")
```

```text
A VALID
B INVALID
C VALID
D INVALID
E INVALID
```

D and E are both cycles that don't loop all the way back to the *start* — D's cycle is `t2 -> t4 -> t2`, entirely downstream of `t1`; E's is `t3 -> t4 -> t5 -> t3`, downstream of `t1 -> t2`. A cycle anywhere in the graph invalidates the whole DAG, not just the portion that loops.

*(See `concepts/01_dag_fundamentals.md`, section 2.)*

</details>

---

## Exercise 4: Design an ETL DAG

Design a DAG for this e-commerce analytics pipeline:

```text
1. Extract from 3 sources (orders API, products DB, users DB)
2. Validate each extracted dataset
3. Join orders with products and users
4. Compute daily revenue metrics
5. Compute user segmentation
6. Load metrics to the warehouse
7. Load segments to the warehouse
8. Generate a daily report combining both
9. Email the report
```

**Your task:** define the graph, and state which tasks can run in parallel, the critical path, and the number of levels.

<details>
<summary>Reference answer</summary>

```python
ecom_dag = {
    "extract_orders":    ["validate_orders"],
    "extract_products":  ["validate_products"],
    "extract_users":     ["validate_users"],
    "validate_orders":   ["join_data"],
    "validate_products": ["join_data"],
    "validate_users":    ["join_data"],
    "join_data":         ["compute_revenue", "compute_segments"],
    "compute_revenue":   ["load_metrics"],
    "compute_segments":  ["load_segments"],
    "load_metrics":      ["generate_report"],
    "load_segments":     ["generate_report"],
    "generate_report":   ["send_email"],
    "send_email":        [],
}
```

- **Parallel:** the three `extract_*` tasks (level 1), the three `validate_*` tasks (level 2), `compute_revenue`/`compute_segments` (level 4), `load_metrics`/`load_segments` (level 5).
- **Critical path:** `extract_* -> validate_* -> join_data -> compute_* -> load_* -> generate_report -> send_email` — 7 sequential levels regardless of which branch you follow, since both branches are the same length.
- **Levels:** 7.

*(See `concepts/01_dag_fundamentals.md`, section 3.)*

</details>

---

## Exercise 5: Trigger Rules

```text
extract_api  (SUCCESS)   \
                          -> validate (trigger_rule='one_success')
extract_db   (FAILED)    /
                           \
                            -> load (trigger_rule='all_success')
validate -> transform (trigger_rule='all_success')
validate -> alert_on_fail (trigger_rule='one_failed')
transform -> load
load -> notify (trigger_rule='none_failed')
extract_db -> cleanup (trigger_rule='all_done')
```

**Your task:** for each task, decide RUNS or SKIPPED.

<details>
<summary>Reference answer</summary>

```text
a) validate       RUNS     one_success: extract_api=SUCCESS is enough, extract_db's FAILED doesn't matter
b) alert_on_fail  SKIPPED  one_failed: validate=SUCCESS -- no upstream failure to react to
c) transform      RUNS     all_success: validate=SUCCESS
d) load           SKIPPED  all_success needs BOTH transform AND extract_db to succeed; extract_db=FAILED
e) cleanup        RUNS     all_done: extract_db reached a terminal state (FAILED counts as "done")
f) notify         SKIPPED  load never ran (it was SKIPPED) -- none_failed treats "not failed" loosely,
                           but a SKIPPED upstream still means notify's own upstream state is SKIPPED,
                           which propagates rather than satisfying none_failed's parent
```

The tell in (f): `none_failed` is easy to misread as "runs as long as nothing *failed*," but a task whose only upstream was itself `SKIPPED` inherits that skip rather than being evaluated as "no failure, therefore proceed" — skip propagation (`concepts/03_scheduling_dependencies.md`, section 3) overrides the trigger-rule table for a task whose entire upstream chain never ran at all.

*(See `concepts/03_scheduling_dependencies.md`, section 3.)*

</details>

---

## Exercise 6: Implement Retry with Exponential Backoff

Implement a `retry_with_backoff` decorator that takes `max_retries` and `base_delay`, retries with `delay = base_delay * 2^attempt`, and re-raises the final exception on exhaustion.

<details>
<summary>Reference answer</summary>

```python
import functools, time, random

def retry_with_backoff(max_retries=3, base_delay=0.1):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    delay = base_delay * (2 ** attempt)
                    print(f"attempt {attempt + 1} failed: {e}, retrying in {delay:.2f}s")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3, base_delay=0.01)
def unreliable():
    if random.random() < 0.7:
        raise ConnectionError("server unavailable")
    return {"status": "ok"}

print(unreliable())
```

*(See `concepts/04_error_handling_retries.md`, section 1.)*

</details>

---

## Exercise 7: Cross-Task Data Passing

Wire a 4-task pipeline where each task pulls the previous task's output:

```text
extract_task  -> {"file_path": "/data/sales.csv", "rows": 1000}
validate_task -> pulls extract's result, checks rows > 0, returns {"valid": True, "rows": 1000}
transform_task -> pulls validate's result, returns {"transformed_rows": 950, "dropped": 50}
load_task     -> pulls transform's result, returns {"loaded": 950, "table": "analytics.sales"}
```

<details>
<summary>Reference answer</summary>

```python
class XCom:
    def __init__(self):
        self.store = {}
    def push(self, task_id, value, key="return_value"):
        self.store[(task_id, key)] = value
    def pull(self, task_id, key="return_value"):
        return self.store.get((task_id, key))

xcom = XCom()

xcom.push("extract", {"file_path": "/data/sales.csv", "rows": 1000})

data = xcom.pull("extract")
xcom.push("validate", {"valid": data["rows"] > 0, "rows": data["rows"]})

data = xcom.pull("validate")
xcom.push("transform", {"transformed_rows": data["rows"] - 50, "dropped": 50})

data = xcom.pull("transform")
xcom.push("load", {"loaded": data["transformed_rows"], "table": "analytics.sales"})

print(xcom.pull("load"))
```

```text
{'loaded': 950, 'table': 'analytics.sales'}
```

*(See `concepts/02_operators_sensors.md`, section 3.)*

</details>

---

## Exercise 8: Design a Failure-Handling Strategy

A pipeline processes 1 million records daily: extract from 3 APIs, transform (some records have bad data), load to a warehouse, send a Slack notification.

**Your task:** for each task, specify retries, retry delay strategy, timeout, what happens on final failure, and an SLA. Also: should you use a dead letter queue, and where? What monitoring would you set up? How do you handle 50% of records failing?

<details>
<summary>Reference answer</summary>

```text
extract_api (x3)   retries=5   exponential backoff (1s,2s,4s,8s,16s)   timeout=10min
                    on final failure: alert Slack + PagerDuty, skip downstream    sla=30min

transform          retries=2   fixed 30s (a data problem won't fix itself by waiting longer)
                    timeout=2h  on final failure: route bad records to DLQ, continue    sla=1h

load_warehouse      retries=5   exponential backoff + jitter   timeout=30min
                    on final failure: write to a local/staging fallback file, alert team   sla=45min

send_notification   retries=3   fixed 10s   timeout=1min
                    on final failure: log a warning only (non-critical, doesn't block the pipeline) sla=5min
```

- **DLQ:** yes, in the `transform` step, for individually malformed records — not for whole-task failures.
- **Monitoring:** a failure-rate dashboard per task, SLA-violation alerts, and DLQ-ratio as its own tracked metric (not just a silent bucket).
- **50% of records failing:** this should **not** just fill the DLQ and continue — a failure rate that high is a signal the *source* data is broken, not that a normal fraction of records are individually malformed (see `interview_questions/03_critique_and_debug.md`'s DLQ-threshold case). The pipeline should halt and alert once the failure ratio crosses a threshold (a low single-digit percentage is typical), rather than silently proceeding with half the day's data missing.

*(See `concepts/04_error_handling_retries.md`, sections 2 and 4.)*

</details>

---

## Exercise 9: Build a DAG Validator

Implement `validate_dag(tasks, dependencies)` checking: no cycles, no dependency referencing an undefined task, no duplicate task IDs, no orphan tasks (unless the DAG has exactly one task), and every task has a callable.

<details>
<summary>Reference answer</summary>

```python
from collections import defaultdict

def validate_dag(tasks, dependencies):
    errors = []
    all_ids = set(tasks)

    for up, down in dependencies:
        if up not in all_ids:
            errors.append(f"unknown task referenced: '{up}'")
        if down not in all_ids:
            errors.append(f"unknown task referenced: '{down}'")

    for tid, fn in tasks.items():
        if fn is None:
            errors.append(f"task '{tid}' has no callable")

    graph = defaultdict(list)
    for up, down in dependencies:
        graph[up].append(down)
    for tid in tasks:
        graph.setdefault(tid, [])
    if has_cycle(graph):
        errors.append("DAG contains a cycle")

    if len(tasks) > 1:
        connected = set()
        for up, down in dependencies:
            connected.update([up, down])
        for orphan in all_ids - connected:
            errors.append(f"orphan task (no connections): '{orphan}'")

    return (len(errors) == 0, errors)

valid_tasks = {"a": lambda: 1, "b": lambda: 2, "c": lambda: 3}
print(validate_dag(valid_tasks, [("a", "b"), ("b", "c")]))

invalid_tasks = {"x": lambda: 1, "y": lambda: 2}
print(validate_dag(invalid_tasks, [("x", "y"), ("y", "x"), ("x", "z")]))
```

```text
(True, [])
(False, ["unknown task referenced: 'z'", 'DAG contains a cycle'])
```

*(`has_cycle` is defined in Exercise 3. See also `concepts/01_dag_fundamentals.md`, section 2.)*

</details>

---

## Exercise 10: End-to-End Pipeline Simulation

Build a full simulation of "Daily User Activity Report":

```text
1. extract_clickstream, 2. extract_signups, 3. extract_purchases   (parallel)
4. validate_all             (waits for all 3 extracts)
5. build_user_profiles, 6. compute_metrics                          (parallel, depend on 4)
7. generate_report          (waits for both 5 and 6)
8. send_to_stakeholders     (waits for 7)
```

**Requirements:** realistic XCom metadata per task, 3 retries with exponential backoff, a 5s timeout per task, tracked execution times, a final summary.

<details>
<summary>Reference answer</summary>

```python
import time

class XCom:
    def __init__(self):
        self.store = {}
    def push(self, task_id, value, key="return_value"):
        self.store[(task_id, key)] = value
    def pull(self, task_id, key="return_value"):
        return self.store.get((task_id, key))

xcom = XCom()
timings = {}

def run_task(task_id, fn, depends_on=None):
    for dep in (depends_on or []):
        xcom.pull(dep)          # a real task would use the pulled value
    start = time.time()
    result = fn()
    timings[task_id] = round(time.time() - start, 4)
    xcom.push(task_id, result)
    print(f"{task_id:22s} -> {result}")
    return result

run_task("extract_clickstream", lambda: {"clicks": 50000, "source": "kafka"})
run_task("extract_signups", lambda: {"signups": 320, "source": "postgres"})
run_task("extract_purchases", lambda: {"purchases": 1200, "source": "api"})

run_task("validate_all", lambda: {"valid": True, "total_records": 51520},
         depends_on=["extract_clickstream", "extract_signups", "extract_purchases"])

run_task("build_user_profiles", lambda: {"profiles_built": 12400}, depends_on=["validate_all"])
run_task("compute_metrics", lambda: {"dau": 8500, "retention": 0.73, "revenue": 45000},
         depends_on=["validate_all"])

run_task("generate_report", lambda: {"report_path": "/reports/daily.pdf"},
         depends_on=["build_user_profiles", "compute_metrics"])
run_task("send_to_stakeholders", lambda: {"sent_to": ["ceo@co.com", "product@co.com"]},
         depends_on=["generate_report"])

print(f"\ntimings: {timings}")
print(f"xcom entries stored: {len(xcom.store)}")
```

The retry-with-backoff and per-task timeout requirements aren't shown wired into `run_task` above for brevity — they compose directly with the `TaskRunner` from `concepts/04_error_handling_retries.md`, section 2: wrap each `fn` passed to `run_task` in a `TaskRunner(..., retry_policy=RetryPolicy(max_retries=3), timeout_seconds=5).run` call instead of invoking it directly. This is also the same shape `projects/pipeline_orchestrator.md` builds as a reusable class rather than one-off script code.

*(See `concepts/01_dag_fundamentals.md` and `concepts/04_error_handling_retries.md` throughout.)*

</details>
