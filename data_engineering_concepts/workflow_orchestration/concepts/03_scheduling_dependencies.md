# Concept 03: Scheduling & Dependencies

**Covers:**
- Cron expressions, and Airflow's schedule presets
- Task dependency syntax (`>>`/`<<`), fan-out/fan-in, and TaskGroups
- Trigger rules — what decides whether a downstream task runs, fails, or is skipped
- Branching (conditional execution paths)
- `max_active_runs` and `depends_on_past`, the two knobs that shape *concurrent* schedule behavior

*Code below is runnable, dependency-free Python. Catchup/backfill specifically — the scheduling topic asked about most often at the mid-level — gets its own file: `concepts/05_backfills_and_catchup.md`.*

---

## 1. Cron Expressions and Schedule Presets

A cron expression is five fields — minute, hour, day-of-month, month, day-of-week — and every orchestrator's "run this on a schedule" feature is either a thin wrapper around cron syntax or offers it as one option alongside a fixed interval:

```text
 * * * * *
 | | | | |
 | | | | +-- day of week (0-6, Sun=0)
 | | | +---- month (1-12)
 | | +------ day of month (1-31)
 | +-------- hour (0-23)
 +---------- minute (0-59)
```

```text
Airflow presets    Cron equivalent      Meaning
@hourly            0 * * * *            top of every hour
@daily             0 0 * * *            midnight every day
@weekly            0 0 * * 0            midnight every Sunday
@monthly           0 0 1 * *            midnight, 1st of the month
@once              (none)               run exactly once, never again
None                (none)               no schedule -- manual/API trigger only
```

```text
Custom patterns you should be able to write cold in an interview:
0 6 * * 1-5     every weekday at 6 AM
0 */2 * * *     every 2 hours
30 9 * * 1      every Monday at 9:30 AM
0 0 1,15 * *    1st and 15th of the month at midnight
```

```python
class CronExpression:
    """A minimal cron matcher -- enough to check whether a given datetime fires."""
    PRESETS = {
        "@hourly": "0 * * * *", "@daily": "0 0 * * *",
        "@weekly": "0 0 * * 0", "@monthly": "0 0 1 * *",
    }

    def __init__(self, expression):
        self.original = expression
        expression = self.PRESETS.get(expression, expression)
        self.parts = expression.split()

    def _field_matches(self, field_expr, value, min_val):
        for part in field_expr.split(","):
            step = 1
            if "/" in part:
                part, step = part.split("/")
                step = int(step)
            if part == "*":
                if (value - min_val) % step == 0:
                    return True
            elif "-" in part:
                start, end = map(int, part.split("-"))
                if start <= value <= end and (value - start) % step == 0:
                    return True
            elif int(part) == value:
                return True
        return False

    def matches(self, dt):
        minute, hour, dom, month, dow = self.parts
        return (self._field_matches(minute, dt.minute, 0)
                and self._field_matches(hour, dt.hour, 0)
                and self._field_matches(dom, dt.day, 1)
                and self._field_matches(month, dt.month, 1)
                and self._field_matches(dow, dt.isoweekday() % 7, 0))


from datetime import datetime
monday_6am = datetime(2024, 6, 17, 6, 0)     # a Monday
for expr in ["@hourly", "@daily", "0 6 * * 1-5"]:
    print(expr, "->", CronExpression(expr).matches(monday_6am))
```

```text
@hourly -> True
@daily -> False
0 6 * * 1-5 -> True
```

---

## 2. Dependency Syntax: `>>`, `<<`, Fan-Out, Fan-In

Airflow overloads `>>`/`<<` as "set downstream"/"set upstream." Any orchestrator's dependency API is doing the same underlying thing: recording an edge in the graph from `concepts/01_dag_fundamentals.md`.

```python
class TaskNode:
    def __init__(self, task_id, trigger_rule="all_success"):
        self.task_id = task_id
        self.trigger_rule = trigger_rule
        self.upstream, self.downstream = [], []

    def set_downstream(self, other):
        self.downstream.append(other)
        other.upstream.append(self)
        return other

    def __rshift__(self, other):
        if isinstance(other, list):
            for t in other:
                self.set_downstream(t)
            return other
        return self.set_downstream(other)

    def __lshift__(self, other):
        if isinstance(other, list):
            for t in other:
                t.set_downstream(self)
            return other
        other.set_downstream(self)
        return other


extract, transform, load, notify = (TaskNode(n) for n in
                                     ["extract", "transform", "load", "notify"])
extract >> transform >> load >> notify

start, a, b, c, merge = (TaskNode(n) for n in ["start", "a", "b", "c", "merge"])
start >> [a, b, c] >> merge          # fan-out then fan-in

print("start.downstream:", [t.task_id for t in start.downstream])
print("merge.upstream:  ", [t.task_id for t in merge.upstream])
```

```text
start.downstream: ['a', 'b', 'c']
merge.upstream:   ['a', 'b', 'c']
```

**TaskGroups** are a pure UI/organizational feature layered on top of this — they visually bundle related tasks (e.g., a set of data-quality checks) under one collapsible node in the graph view. They change nothing about execution: every task inside a TaskGroup still has its own independent state and still participates in the same topological sort as if it weren't grouped at all.

---

## 3. Trigger Rules: What Decides If a Downstream Task Runs

By default, a task only runs if **every** upstream task succeeded (`all_success`). That default is wrong for a meaningful fraction of real pipelines — a cleanup task that should run *regardless* of whether the main path succeeded, an alert task that should run *only if* something upstream failed. **Trigger rules** are how you override the default per task:

```text
all_success   (default) every parent succeeded
all_failed    every parent failed
all_done      every parent reached a terminal state (success, failed, OR skipped) -- doesn't care which
one_success   at least one parent succeeded
one_failed    at least one parent failed
none_failed   no parent failed (success or skipped both count as "not failed")
none_skipped  no parent was skipped
```

```python
def should_task_run(trigger_rule, parent_states: list) -> bool:
    if not parent_states:
        return True
    successes = parent_states.count("success")
    failures = parent_states.count("failed")
    skips = parent_states.count("skipped")
    total = len(parent_states)
    return {
        "all_success": successes == total,
        "all_failed":  failures == total,
        "all_done":    True,
        "one_success": successes >= 1,
        "one_failed":  failures >= 1,
        "none_failed": failures == 0,
        "none_skipped": skips == 0,
    }.get(trigger_rule, False)


scenarios = [
    ("all_success", ["success", "failed", "success"]),
    ("one_success", ["failed", "failed", "success"]),
    ("none_failed", ["success", "skipped"]),
    ("all_done",    ["success", "failed", "skipped"]),
]
for rule, states in scenarios:
    print(f"{rule:12s} {states} -> {should_task_run(rule, states)}")
```

```text
all_success  ['success', 'failed', 'success'] -> False
one_success  ['failed', 'failed', 'success'] -> True
none_failed  ['success', 'skipped'] -> True
all_done     ['success', 'failed', 'skipped'] -> True
```

**Skip propagation is the part that trips people up in a live trigger-rule question.** A task's `all_success`-by-default downstream doesn't just fail when an upstream task fails — it gets marked **`skipped`**, and that `skipped` state then propagates forward through every subsequent `all_success` task, all the way to the end of the DAG, unless something downstream has a trigger rule (`all_done`, `none_failed`) specifically designed to catch it. A cleanup or notification task that needs to run "no matter what happened" has to opt out of the default explicitly — it will not run on its own.

---

## 4. Branching: Choosing a Path at Runtime

A `BranchPythonOperator` (or its equivalent elsewhere) picks which of several downstream paths actually runs, and marks every path *not* chosen as `skipped` rather than running them and discarding the result:

```python
class BranchOperator:
    def __init__(self, task_id, branch_fn):
        self.task_id, self.branch_fn = task_id, branch_fn
        self.branches = {}

    def add_branch(self, branch_id, fn):
        self.branches[branch_id] = fn

    def execute(self, context=None):
        chosen = self.branch_fn(context)
        results = {}
        for branch_id, fn in self.branches.items():
            results[branch_id] = {"state": "success", "result": fn()} if branch_id == chosen \
                                  else {"state": "skipped", "result": None}
        return results


def choose_engine(context=None):
    row_count = 150_000
    return "heavy_processing" if row_count > 100_000 else "light_processing"

branch = BranchOperator("decide_path", choose_engine)
branch.add_branch("heavy_processing", lambda: "used Spark for 150K rows")
branch.add_branch("light_processing", lambda: "used pandas for a small dataset")
print(branch.execute())
```

```text
{'heavy_processing': {'state': 'success', 'result': 'used Spark for 150K rows'},
 'light_processing': {'state': 'skipped', 'result': None}}
```

Note the overlap with trigger rules: a task placed downstream of *both* branches needs `none_failed` or `one_success` (not the default `all_success`) to run at all — otherwise the `skipped` branch drags it into `skipped` too, the same skip-propagation behavior from section 3.

---

## 5. `max_active_runs` and `depends_on_past`: Concurrency Across Runs, Not Within One

Everything above governs dependency order **within a single DAG Run**. Two separate settings govern how multiple DAG Runs of the *same* DAG interact with each other — and this is exactly where backfill safety lives:

```text
max_active_runs=N     Caps how many DAG Runs of THIS DAG can be RUNNING concurrently.
                       max_active_runs=1 means run #2 physically cannot start until
                       run #1 finishes -- the standard guard against an expensive daily
                       job's runs piling up and overlapping if one runs long.

depends_on_past=True  A task in run N will not start until the SAME task in run N-1
                       reached success. Forces strict sequential order across runs,
                       task by task -- appropriate for an accumulating computation
                       (e.g. a running balance) where run order genuinely matters;
                       actively wrong for stateless, idempotent tasks, where it just
                       adds needless serialization.
```

Both are the two levers that make a **backfill** of many historical runs behave safely (or unsafely) when it overlaps a live schedule — the full treatment, including exactly why `catchup=True` is a frequent production incident on its own, is `concepts/05_backfills_and_catchup.md`.

---

## Key Takeaways

- Cron expressions (or Airflow's `@daily`/`@hourly`/etc. presets) define *when* a DAG is scheduled; `>>`/`<<` (or the equivalent dependency API) define the *order* tasks run in within one DAG Run.
- Fan-out (`start >> [a, b, c]`) and fan-in (`[a, b, c] >> merge`) are the two dependency shapes that let independent work run in parallel and then converge; TaskGroups are a visual grouping only — they change nothing about execution.
- Trigger rules override the default `all_success` gate per task. `all_done`/`none_failed` are how a cleanup or alert task is made to run regardless of upstream failure — without one of those, it inherits the default and gets silently skipped.
- A failed task's `all_success` downstream is marked `skipped`, not left `pending` — and that `skipped` state propagates forward through the rest of the DAG unless a trigger rule downstream is specifically designed to catch it.
- `BranchPythonOperator` marks every non-chosen path `skipped`; anything meant to run regardless of which branch fired needs a non-default trigger rule.
- `max_active_runs` and `depends_on_past` govern concurrency *across* DAG Runs of the same DAG, not dependency order within one run — they're the levers that make backfilling a live DAG safe or unsafe.
