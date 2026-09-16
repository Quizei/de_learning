# Workflow Orchestration — Coding Problem: Pipeline Orchestrator

A single "hard, senior-level" problem (target time: 45-60 minutes) that combines the three
mechanisms a real orchestrator is built from: **topological-sort execution**, a **task
state machine with retries**, and **run state you can inspect and resume from**. This is
the same shape `projects/pipeline_orchestrator.md` builds out fully as a reusable engine
with XCom, callbacks, and visualization — this file is the tighter, interview-length
version of the same core problem, done in three parts.

How to use this file: implement each part yourself against the given interface before
expanding the reference solution. Everything is dependency-free Python.

---

## Setup: The Task Graph

Every part below operates on the same input shape — a dict of task definitions, each with
an id, a callable, and its upstream dependencies:

```python
tasks = {
    "extract_orders":   {"fn": lambda: {"rows": 1500}, "deps": []},
    "extract_products": {"fn": lambda: {"rows": 300},  "deps": []},
    "validate":         {"fn": lambda: {"ok": True},   "deps": ["extract_orders", "extract_products"]},
    "load":             {"fn": lambda: {"loaded": 1500}, "deps": ["validate"]},
}
```

---

## Part A: Execute a DAG in Dependency Order

**Problem:** implement `run_pipeline(tasks: dict) -> dict[str, str]` that executes every
task in a valid topological order and returns each task's final state
(`"success"` or `"failed"`). If a task's dependency failed, the task itself must be marked
`"skipped"` rather than run at all — and that skip must propagate to *its* downstream tasks
in turn.

**Expected output**, given the `tasks` graph above with all four functions succeeding:

```text
{'extract_orders': 'success', 'extract_products': 'success',
 'validate': 'success', 'load': 'success'}
```

And if `extract_products`'s callable raised instead:

```text
{'extract_orders': 'success', 'extract_products': 'failed',
 'validate': 'skipped', 'load': 'skipped'}
```

<details>
<summary>Solution</summary>

```python
from collections import defaultdict, deque

def topological_sort(tasks):
    in_degree = defaultdict(int)
    for tid, spec in tasks.items():
        in_degree.setdefault(tid, 0)
        for dep in spec["deps"]:
            in_degree[tid] += 1
    queue = deque(tid for tid in tasks if in_degree[tid] == 0)
    order = []
    graph = defaultdict(list)
    for tid, spec in tasks.items():
        for dep in spec["deps"]:
            graph[dep].append(tid)
    while queue:
        tid = queue.popleft()
        order.append(tid)
        for downstream in graph[tid]:
            in_degree[downstream] -= 1
            if in_degree[downstream] == 0:
                queue.append(downstream)
    if len(order) != len(tasks):
        raise ValueError("cycle detected")
    return order


def run_pipeline(tasks):
    order = topological_sort(tasks)
    states = {}
    for tid in order:
        deps = tasks[tid]["deps"]
        if any(states[d] != "success" for d in deps):
            states[tid] = "skipped"
            continue
        try:
            tasks[tid]["fn"]()
            states[tid] = "success"
        except Exception:
            states[tid] = "failed"
    return states
```

**The pattern:** this is Kahn's algorithm (`concepts/01_dag_fundamentals.md`, section 3)
plus one extra rule layered on top of plain topological order — a task only actually
*executes* if every dependency's recorded state is `"success"`; otherwise it's marked
`"skipped"` without running, and because the loop processes tasks in topological order,
that `"skipped"` state is already visible by the time any of *its* downstream tasks are
checked, so the propagation is free — no separate pass is needed.

</details>

---

## Part B: Add Retries With Backoff

**Problem:** extend the interface so each task can specify `retries` and `base_delay`,
and a task is only marked `"failed"` after exhausting all attempts. Track the number of
attempts each task actually took.

```python
tasks = {
    "flaky_extract": {"fn": make_flaky(fail_times=2), "deps": [], "retries": 3, "base_delay": 0.01},
    "load":          {"fn": lambda: {"ok": True}, "deps": ["flaky_extract"], "retries": 0, "base_delay": 0},
}
```

**Expected output** (`make_flaky(fail_times=2)` raises on its first two calls, then succeeds):

```text
{'flaky_extract': {'state': 'success', 'attempts': 3},
 'load':          {'state': 'success', 'attempts': 1}}
```

<details>
<summary>Solution</summary>

```python
import time

def run_pipeline_with_retries(tasks):
    order = topological_sort(tasks)
    states = {}
    for tid in order:
        spec = tasks[tid]
        deps = spec["deps"]
        if any(states[d]["state"] != "success" for d in deps):
            states[tid] = {"state": "skipped", "attempts": 0}
            continue

        max_attempts = spec.get("retries", 0) + 1
        base_delay = spec.get("base_delay", 0)
        for attempt in range(1, max_attempts + 1):
            try:
                spec["fn"]()
                states[tid] = {"state": "success", "attempts": attempt}
                break
            except Exception:
                if attempt == max_attempts:
                    states[tid] = {"state": "failed", "attempts": attempt}
                else:
                    time.sleep(base_delay * (2 ** (attempt - 1)))   # exponential backoff
    return states
```

**The pattern:** a retry loop nested *inside* the topological-sort loop, not a separate
phase — each task gets its own bounded attempt budget (`retries + 1` total attempts) before
the outer loop moves on. This is `TaskRunner` from `concepts/04_error_handling_retries.md`,
section 2, applied once per node in execution order rather than to a single isolated task.
The state dict grows from a bare string to a small record (`state` + `attempts`) because
"how many tries did this take" is exactly the kind of operational detail a real run history
needs to answer an on-call question like "did this actually retry, or fail outright?"
(see `interview_questions/05_oncall_incident_triage.md`).

</details>

---

## Part C: Persist State So a Failed Run Can Resume

**Problem:** a pipeline that failed partway through should not have to re-run tasks that
already succeeded. Implement `run_pipeline_resumable(tasks, prior_state=None)` that accepts
a previous run's state dict and skips re-executing any task already recorded as
`"success"` — while still re-evaluating tasks that were `"failed"` or never ran.

```python
first_run = run_pipeline_with_retries(tasks)   # load fails because flaky_extract exhausted retries
# ... operator fixes the underlying issue, e.g. bumps flaky_extract's retries ...
second_run = run_pipeline_resumable(tasks, prior_state=first_run)
```

**Expected behavior:** `extract_orders`/`extract_products`-style tasks that already
succeeded in `first_run` are **not** re-invoked at all on the second call; only tasks that
were `"failed"` or `"skipped"` actually run again.

<details>
<summary>Solution</summary>

```python
def run_pipeline_resumable(tasks, prior_state=None):
    prior_state = prior_state or {}
    order = topological_sort(tasks)
    states = dict(prior_state)   # carry forward anything already recorded

    for tid in order:
        if states.get(tid, {}).get("state") == "success":
            continue   # already done -- do NOT re-run a task that already succeeded

        spec = tasks[tid]
        deps = spec["deps"]
        if any(states.get(d, {}).get("state") != "success" for d in deps):
            states[tid] = {"state": "skipped", "attempts": states.get(tid, {}).get("attempts", 0)}
            continue

        max_attempts = spec.get("retries", 0) + 1
        base_delay = spec.get("base_delay", 0)
        for attempt in range(1, max_attempts + 1):
            try:
                spec["fn"]()
                states[tid] = {"state": "success", "attempts": attempt}
                break
            except Exception:
                if attempt == max_attempts:
                    states[tid] = {"state": "failed", "attempts": attempt}
                else:
                    time.sleep(base_delay * (2 ** (attempt - 1)))
    return states
```

**The pattern:** state becomes an input to the run, not just an output of it — the
function is now idempotent at the *pipeline* level (rerunning it with the same
`prior_state` and the same tasks converges rather than redoing completed work), which is
the exact same property `concepts/05_backfills_and_catchup.md` requires of individual tasks,
just applied one level up, to the whole run. A real orchestrator persists this state dict to
a metadata database (Airflow's task-instance table) rather than an in-memory dict, precisely
so a scheduler restart or a manual "clear and rerun" doesn't lose track of what already
succeeded.

**Why this is the senior-level version of the problem:** Part A is "can you implement
topological sort," which is a standard exercise. Part C is "do you understand that an
orchestration engine's job is fundamentally about *durable state*, not just execution order"
— the difference between a script that runs a DAG once and an actual orchestrator that can
be safely stopped, restarted, and resumed without re-doing work or silently skipping work
that never actually happened.

</details>
