# Concept 01: DAG Fundamentals

**Covers:**
- What a DAG is, and why "directed" and "acyclic" are both load-bearing words
- Cycle detection, and why a scheduler rejects a cyclic graph outright
- Topological sort — how an orchestrator turns a dependency graph into an execution order
- DAG Run vs. Task Instance vs. logical/execution date, and why "the date it runs" and "the date it's for" are different things
- The same vocabulary in Dagster, Prefect, and Mage, so the concept transfers off Airflow

*All code below is real, runnable, dependency-free Python — copy any block into a `python3` shell and it runs as shown. This course is Airflow-centric because Airflow is still the orchestrator most interviews ask about by name, but every concept here is named in orchestrator-agnostic terms first, Airflow-specific terms second.*

---

## 1. A DAG Is Just a Dependency Graph With Two Rules

A **DAG (Directed Acyclic Graph)** is the data structure every workflow orchestrator — Airflow, Dagster, Prefect, Mage, Luigi, dbt's own internal graph — uses to represent a pipeline. Two words in the name are both rules, not decoration:

- **Directed**: an edge `A -> B` means "A must finish before B starts," not just "A and B are related." Direction is what lets an engine derive an execution order at all.
- **Acyclic**: no path can loop back on itself. `A -> B -> C -> A` is not a pipeline, it's an infinite wait — A can never finish because it's downstream of something that needs it to finish first.

```text
  Valid DAG (ETL pipeline):

  extract_users  --> clean_users  --\
                                      --> join_data --> compute_metrics --> load_warehouse
  extract_orders --> clean_orders --/

  Invalid graph (cycle):

  extract --> transform --> load --> extract   <-- load depends on extract, which depends on load
```

Why orchestrators insist on this: a DAG is exactly the structure that guarantees **at least one valid execution order exists**, that order can be computed mechanically (not designed by hand), and independent branches can be safely run in parallel. Give up "acyclic" and none of those three guarantees hold anymore — which is why every orchestrator validates this at *parse* time, before a single task runs, and refuses to schedule a DAG that fails the check.

---

## 2. Cycle Detection: DFS With Three Colors

Detecting a cycle is a graph-coloring depth-first search: every node is WHITE (unvisited) until you start exploring it (GRAY, "in progress"), and BLACK once you're fully done with it and everything reachable from it. A cycle exists exactly when the search reaches a node that is currently GRAY — that's a **back edge**, an edge pointing at something still "in progress" further up the same call stack.

```python
def has_cycle(graph: dict) -> bool:
    """
    graph: {task_id: [downstream_task_ids]}
    WHITE = unvisited, GRAY = on the current DFS path, BLACK = fully explored.
    A cycle exists iff DFS reaches a GRAY node (a back edge).
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}

    def dfs(node):
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color.get(neighbor, WHITE) == GRAY:
                return True                      # back edge -> cycle
            if color.get(neighbor, WHITE) == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    return any(color[node] == WHITE and dfs(node) for node in graph)
```

```python
valid = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
print(has_cycle(valid))     # False

invalid = {"A": ["B"], "B": ["C"], "C": ["A"]}
print(has_cycle(invalid))   # True -- A -> B -> C -> A
```

This is exactly what Airflow's DAG parser (and every other orchestrator's graph validator) runs before it will schedule anything. If your DAG file defines a cycle, the DAG fails to *import* — it never reaches the scheduler, and you find out immediately rather than discovering it mid-run.

---

## 3. Topological Sort: Turning the Graph Into an Execution Order

**Topological sort** answers the question a scheduler actually needs answered every time it decides what to run next: *"of everything not yet done, what's now safe to start?"* Kahn's algorithm is the standard approach, and it maps directly onto how a real scheduler behaves:

```python
from collections import defaultdict, deque

def topological_sort(graph: dict) -> list:
    """
    Kahn's algorithm. Returns one valid execution order.
    This is mechanically what a scheduler does every tick:
      1. Find every task with no unmet dependency (in-degree 0)
      2. Run them (they can run in PARALLEL -- nothing orders them relative to each other)
      3. Remove their outgoing edges; anything that drops to in-degree 0 joins the queue
      4. Repeat until every task has run
    """
    in_degree = defaultdict(int)
    all_nodes = set(graph.keys())
    for node in graph:
        for neighbor in graph[node]:
            in_degree[neighbor] += 1
            all_nodes.add(neighbor)

    queue = deque(n for n in all_nodes if in_degree[n] == 0)
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(all_nodes):
        raise ValueError("Graph has a cycle -- cannot topologically sort")
    return order
```

```python
etl_graph = {
    "extract_users":     ["clean_users"],
    "extract_orders":    ["clean_orders"],
    "clean_users":       ["join_data"],
    "clean_orders":      ["join_data"],
    "join_data":         ["compute_metrics", "build_report"],
    "compute_metrics":   ["load_warehouse"],
    "build_report":      ["load_warehouse"],
    "load_warehouse":    ["notify_team"],
    "notify_team":       [],
}
print(topological_sort(etl_graph))
```

```text
['extract_users', 'extract_orders', 'clean_users', 'clean_orders',
 'join_data', 'compute_metrics', 'build_report', 'load_warehouse', 'notify_team']
```

The order isn't unique — `extract_orders` could just as validly come before `extract_users` — and that's the point: **`extract_users`/`extract_orders` share no dependency on each other, so they can run in parallel**, and so can `compute_metrics`/`build_report`. Spotting which tasks in a DAG are safe to parallelize (interview phrasing: "what's the critical path, and what can fan out?") is just reading in-degree-zero groups off this same computation, one "wave" at a time.

---

## 4. DAG Run, Task Instance, and the Logical-Date Trap

A **DAG** is a template — a definition of tasks and dependencies. A **DAG Run** is one concrete *execution* of that template, tied to a specific interval. A **Task Instance** is one task, inside one specific DAG Run. The distinction matters because the same DAG definition produces a new DAG Run every scheduled interval, and each DAG Run's task instances have completely independent state.

The single most common source of Airflow confusion for people new to it: **`execution_date` (Airflow ≥ 2.2 calls it `logical_date` / `data_interval_start`) is the START of the period the run is FOR, not the moment the run actually executes.** A `@daily` DAG's run stamped `2024-01-15` processes data *for* January 15th — but because Airflow only schedules a run once its full interval has elapsed, that run doesn't actually start until midnight on the **16th**.

```text
  A @daily DAG, start_date = 2024-01-01:

  logical_date   actually runs on     processes data for
  2024-01-01  -> 2024-01-02 00:00  -> all of 2024-01-01
  2024-01-02  -> 2024-01-03 00:00  -> all of 2024-01-02
  2024-01-03  -> 2024-01-04 00:00  -> all of 2024-01-03
```

```python
from datetime import datetime, timedelta

class DagRun:
    """One concrete execution of a DAG for a specific interval."""
    def __init__(self, dag_id, logical_date, run_id=None):
        self.dag_id = dag_id
        self.logical_date = logical_date
        self.run_id = run_id or f"{dag_id}__{logical_date.isoformat()}"
        self.state = "queued"          # queued, running, success, failed
        self.task_states = {}          # task_id -> state, independent per run

start_date = datetime(2024, 1, 1)
for day_offset in range(3):
    logical_date = start_date + timedelta(days=day_offset)
    actual_run_time = logical_date + timedelta(days=1)   # daily interval, runs the day after
    run = DagRun("daily_etl", logical_date)
    print(f"{run.run_id}: processes {logical_date.date()}, actually runs {actual_run_time.date()}")
```

```text
daily_etl__2024-01-01T00:00:00: processes 2024-01-01, actually runs 2024-01-02
daily_etl__2024-01-02T00:00:00: processes 2024-01-02, actually runs 2024-01-03
daily_etl__2024-01-03T00:00:00: processes 2024-01-03, actually runs 2024-01-04
```

This single fact is *why* backfilling and catch-up behave the way they do (`concepts/05_backfills_and_catchup.md`), and it's a favorite "do you actually understand this or just use `datetime.now()` everywhere" interview check — a task that reads `datetime.now()` instead of its DAG Run's logical date silently breaks the moment anyone reruns or backfills it, because "now" and "the date this run is for" are two different things by design.

---

## 5. A Minimal DAG Engine, End to End

Putting DAG + cycle check + topological sort + task execution together is most of what a toy orchestrator *is*:

```python
from datetime import datetime

class Task:
    def __init__(self, task_id, callable_fn):
        self.task_id = task_id
        self.callable_fn = callable_fn
        self.state = "pending"     # pending, running, success, failed
        self.result = None
        self.error = None

    def execute(self):
        self.state = "running"
        try:
            self.result = self.callable_fn()
            self.state = "success"
        except Exception as e:
            self.state = "failed"
            self.error = str(e)
        return self.state


class SimpleDag:
    def __init__(self, dag_id):
        self.dag_id = dag_id
        self.tasks = {}
        self.graph = defaultdict(list)

    def add_task(self, task_id, callable_fn):
        self.tasks[task_id] = Task(task_id, callable_fn)
        self.graph.setdefault(task_id, [])
        return self

    def set_dependency(self, upstream_id, downstream_id):
        self.graph[upstream_id].append(downstream_id)
        if has_cycle(self.graph):
            self.graph[upstream_id].remove(downstream_id)
            raise ValueError(f"{upstream_id} -> {downstream_id} would create a cycle")
        return self

    def run(self):
        order = topological_sort(self.graph)
        results = {}
        for task_id in order:
            task = self.tasks[task_id]
            upstream_ok = all(
                self.tasks[u].state == "success"
                for u, downs in self.graph.items() if task_id in downs
            )
            if not upstream_ok:
                task.state = "skipped"
                results[task_id] = "skipped"
                continue
            results[task_id] = task.execute()
        return results


dag = SimpleDag("sales_etl")
dag.add_task("extract", lambda: {"rows": 1500})
dag.add_task("transform", lambda: {"rows": 1490})
dag.add_task("load", lambda: {"table": "fact_sales"})
dag.set_dependency("extract", "transform")
dag.set_dependency("transform", "load")

print(dag.run())
```

```text
{'extract': 'success', 'transform': 'success', 'load': 'success'}
```

This is deliberately the same shape covered end to end in `projects/pipeline_orchestrator.md` — a topological-sort execution loop, task state, and skip propagation — extended there with retries and persisted state.

---

## 6. The Same Concepts Outside Airflow

The words differ; the graph doesn't. An interviewer asking "have you used Dagster or Prefect" is checking whether you understand DAGs as a *concept* or only know one tool's API surface:

```text
Concept                    Airflow                  Dagster                 Prefect
------------------------   -----------------------  ----------------------  -----------------------
Pipeline definition        DAG                      Job (graph of ops)      Flow
Unit of work               Task / Operator          Op (or Asset)           Task
One execution              DAG Run                  Run                     Flow Run
Data-centric unit           (none, implicit)        Software-Defined Asset  (none, implicit)
Wait-for-condition          Sensor                   Sensor                 (custom / event trigger)
Logical/scheduled date      execution_date / logical_date   Partition key   scheduled_start_time
```

The detail worth naming out loud if asked: **Dagster's Software-Defined Assets** shift the primary mental model from "a graph of tasks that run" to "a graph of *data assets* that get materialized," with tasks as an implementation detail underneath. It's the same DAG and the same topological-sort execution underneath — the difference is what the graph's nodes are named after (a step vs. the dataset that step produces) — but it's a real conceptual shift, not just a rename, and is worth mentioning specifically if an interviewer asks "why would you pick Dagster over Airflow."

---

## Key Takeaways

- A DAG is directed (edges define order) and acyclic (no path loops back); both properties are required for a scheduler to guarantee a valid execution order exists at all.
- Cycle detection is DFS with WHITE/GRAY/BLACK coloring — a cycle is a back edge to a GRAY (in-progress) node. Orchestrators run this at parse time and refuse to schedule a cyclic DAG.
- Topological sort (Kahn's algorithm) turns the dependency graph into an execution order; nodes that become "ready" in the same pass can run in parallel — that's the mechanical definition of "what can fan out."
- A DAG is a template; a DAG Run is one concrete execution of it; a Task Instance is one task within one DAG Run. Each DAG Run's task states are independent of every other run's.
- `execution_date`/`logical_date` is the start of the interval a run is *for*, not the wall-clock time it actually executes — a daily DAG's Jan-15 run typically starts running after midnight on the 16th. A task that reads `datetime.now()` instead of its logical date breaks under backfill and rerun.
- The DAG/topological-sort/task-state vocabulary is identical across Airflow, Dagster, and Prefect even though the names differ — Dagster's asset-centric model is the one genuine conceptual variation worth calling out by name.
