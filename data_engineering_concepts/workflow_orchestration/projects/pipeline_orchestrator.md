# Capstone Project: Build a PipelineOrchestrator

## Scenario

You're asked to build a small internal task-orchestration engine — not a full Airflow
clone, but the real core of one: a class that takes a set of tasks and dependencies,
executes them in a valid order, retries failures with backoff, respects trigger rules when
an upstream task fails, and — the part that separates this from a toy script — **persists
run state so a partially-failed run can be resumed without re-executing tasks that already
succeeded.** This is the same engine shape covered piece by piece in `concepts/01_dag_fundamentals.md`
through `concepts/04_error_handling_retries.md`, and the same three-part problem worked at
interview scope in `practice/coding_problems.md` — here, built out as one reusable class.

## Learning Goal

Implement `PipelineOrchestrator` against the interface specified below. This exercises
topological-sort execution order, cycle detection, a task state machine with retry/backoff,
trigger-rule evaluation with skip propagation, and — the project's actual centerpiece —
durable state that makes a rerun idempotent *at the pipeline level*, mirroring what
`concepts/05_backfills_and_catchup.md` requires of individual tasks, one level up.

This brief gives you the class interface, the expected behavior of each method, and a
worked scenario of what running (and then resuming) the finished tool should produce —
build the implementation yourself before checking your design against the notes at the end.

---

## The Interface

```python
from enum import Enum
from typing import Callable, Optional


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    UP_FOR_RETRY = "up_for_retry"


class PipelineOrchestrator:
    """
    A minimal, reusable DAG execution engine.

    Usage:
        pipe = PipelineOrchestrator("daily_sales", state_path="daily_sales_state.json")
        pipe.add_task("extract", extract_fn, retries=3, retry_delay=1.0)
        pipe.add_task("transform", transform_fn, retries=1)
        pipe.add_task("load", load_fn, retries=2, trigger_rule="all_success")
        pipe.set_dependency("extract", "transform")
        pipe.set_dependency("transform", "load")

        result = pipe.run(logical_date="2024-06-15")
        # ... if something failed, fix the underlying issue, then:
        result = pipe.run(logical_date="2024-06-15", resume=True)
    """

    def __init__(self, pipeline_id: str, state_path: Optional[str] = None):
        self.pipeline_id = pipeline_id
        self.state_path = state_path   # where run state is persisted between calls
        self.tasks = {}                # task_id -> task definition (dict or small class)
        self.graph = {}                # task_id -> [downstream_task_ids]
        self.reverse_graph = {}        # task_id -> [upstream_task_ids]
        # TODO: whatever else you need -- an XCom-style result store is optional,
        # not required for this project's scope.

    # -----------------------------------------------------------------
    # 1. DAG CONSTRUCTION
    # -----------------------------------------------------------------
    def add_task(self, task_id: str, callable_fn: Callable, *, retries: int = 0,
                 retry_delay: float = 1.0, backoff_factor: float = 2.0,
                 timeout: Optional[float] = None, trigger_rule: str = "all_success"):
        """
        Register a task.

        Requirements:
            - Raise ValueError on a duplicate task_id.
            - `trigger_rule` must be one of the rules from
              `concepts/03_scheduling_dependencies.md`, section 3
              (at minimum: all_success, all_failed, all_done, one_success,
              one_failed, none_failed) -- raise on anything else.
        """
        raise NotImplementedError

    def set_dependency(self, upstream_id: str, downstream_id: str):
        """
        Record upstream -> downstream.

        Requirements:
            - Raise ValueError if either task_id is unknown.
            - Raise ValueError if adding this edge would introduce a cycle --
              check BEFORE committing the edge, and leave the graph unchanged
              if it's rejected (see `concepts/01_dag_fundamentals.md`, section 2
              for the cycle-detection algorithm).
        """
        raise NotImplementedError

    def chain(self, *task_ids: str):
        """Convenience: chain('a', 'b', 'c') == set_dependency('a','b') + set_dependency('b','c')."""
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 2. EXECUTION
    # -----------------------------------------------------------------
    def run(self, logical_date: str, resume: bool = False) -> dict:
        """
        Execute the pipeline for a given logical date.

        Args:
            logical_date: an opaque string key identifying THIS run (e.g. "2024-06-15").
                          State is tracked per (pipeline_id, logical_date) pair --
                          running the same logical_date twice is how resume is exercised.
            resume:       if True, load any previously persisted state for this
                          logical_date and skip re-executing any task already
                          recorded as SUCCESS. If False, start this logical_date
                          fresh (ignore/overwrite any prior state for it).

        Returns:
            dict of {task_id: {"state": str, "attempts": int, "error": str | None}}

        Requirements:
            - Execute tasks in a valid topological order (raise if the graph
              somehow has a cycle at run time -- shouldn't happen given
              set_dependency's guard, but don't assume it can't).
            - A task only executes if its trigger rule is satisfied given its
              upstream tasks' CURRENT states (including states carried forward
              from a resumed run) -- otherwise mark it SKIPPED without running it.
            - A task retries up to `retries + 1` total attempts, sleeping
              `retry_delay * backoff_factor ** attempt` between attempts, before
              being marked FAILED.
            - After EVERY task (not just at the end of the whole run), persist
              state to `self.state_path` if one was given -- a crash mid-run
              should lose at most the currently-running task's progress, not
              everything since the run started.
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 3. STATE INSPECTION
    # -----------------------------------------------------------------
    def get_status(self, logical_date: str) -> dict:
        """Return the current persisted state for a given logical_date, loading
        from `state_path` if it's not already in memory. Return {} if there's no
        recorded run for that logical_date at all."""
        raise NotImplementedError

    def visualize_dag(self) -> str:
        """Return a human-readable, leveled ASCII rendering of the graph (see
        `concepts/01_dag_fundamentals.md` for the shape) -- not required to be
        exact, but should clearly show which tasks are at the same "wave" and
        therefore ran in parallel."""
        raise NotImplementedError
```

---

## Worked Scenario: A Failing Run, Fixed, and Resumed

```python
def extract(): return {"rows": 1500}

def flaky_transform():
    import random
    if random.random() < 1.0:      # deterministic failure for this demo
        raise ValueError("schema mismatch in upstream field 'region'")

def load(): return {"loaded": 1500}

pipe = PipelineOrchestrator("sales_pipeline", state_path="sales_pipeline_state.json")
pipe.add_task("extract", extract, retries=1)
pipe.add_task("transform", flaky_transform, retries=1, retry_delay=0.01)
pipe.add_task("load", load, retries=0, trigger_rule="all_success")
pipe.chain("extract", "transform", "load")

result_1 = pipe.run(logical_date="2024-06-15")
```

**Expected result (`result_1`):** `extract` is `SUCCESS`; `transform` is `FAILED` after 2
total attempts (`retries=1` means 2 attempts); `load` is `SKIPPED`, because its
`all_success` trigger rule isn't satisfied by an upstream `FAILED` state.

```python
# ... an engineer fixes the actual bug in the transform logic ...

def fixed_transform():
    return {"transformed": 1490}

pipe.tasks["transform"].callable_fn = fixed_transform  # (however your design exposes this)

result_2 = pipe.run(logical_date="2024-06-15", resume=True)
```

**Expected result (`result_2`):** `extract` shows `SUCCESS` **without having been
re-invoked** — its state was carried forward from `result_1` rather than re-executed;
`transform` now runs (it wasn't `SUCCESS` before) and succeeds; `load`, previously
`SKIPPED`, is now re-evaluated against `transform`'s new `SUCCESS` state and runs
successfully. The whole run's final state has no task showing `FAILED` or `SKIPPED`.

```python
print(pipe.get_status("2024-06-15"))
# {'extract': {'state': 'success', 'attempts': 1, 'error': None},
#  'transform': {'state': 'success', 'attempts': 1, 'error': None},
#  'load': {'state': 'success', 'attempts': 1, 'error': None}}
```

---

## Design Notes and Judgment Calls to Make Yourself

- **State persistence format:** a flat JSON file keyed by `logical_date` is enough for this
  project's scope (`{"2024-06-15": {"extract": {...}, ...}}`) — don't over-build a real
  database layer; the point is proving you understand *that* state needs to survive between
  `run()` calls, not building Airflow's actual metadata schema.
- **`resume=True` re-evaluation, not just re-execution:** the trickiest correctness
  requirement is that `load` in the worked scenario above needs to be **re-evaluated**
  against `transform`'s new state on the resumed run, not just skipped again because it was
  `SKIPPED` last time — a resumed run has to re-run trigger-rule evaluation for every
  non-`SUCCESS` task, not merely retry tasks that were `FAILED`.
- **Cycle detection on every `set_dependency` call, not just at `run()` time:** rejecting a
  cycle-introducing edge immediately, with a clear error, is far more useful than
  discovering the DAG is broken only when someone tries to run it — this mirrors how a real
  orchestrator's DAG parser behaves (`concepts/01_dag_fundamentals.md`, section 2).
- **Retry sleep during tests:** make `retry_delay` small (or monkeypatchable) in your own
  test calls — nothing about the design requires real multi-second sleeps to verify
  correctness.

## Stretch Goals

- Add a `pool` concept: a named, capacity-limited resource each task can optionally declare
  (`add_task(..., pool="api_calls", pool_slots=1)`), and enforce that no more than a pool's
  declared capacity of tasks run "concurrently" (simulated, since this project doesn't need
  real threading) — the mechanism behind `concepts/05_backfills_and_catchup.md`'s
  backfill-isolation pattern.
- Add `max_active_runs` semantics: track whether a `logical_date`'s run is still `RUNNING`
  and reject (or queue) a second concurrent `run()` call for a *different* `logical_date` if
  a cap is configured — this is the mechanism, not just the concept, behind
  `concepts/03_scheduling_dependencies.md`, section 5.
- Add a `dry_run()` method that returns the execution order and which tasks WOULD be
  skipped given a hypothetical set of upstream states, without executing anything — useful
  for validating a trigger-rule design before ever running the pipeline for real.

## Evaluation Criteria

- `set_dependency` rejects a cycle-introducing edge and leaves the graph unchanged when it
  does.
- `run` executes tasks in a valid topological order, retries each task independently up to
  its own configured limit, and marks a task `SKIPPED` (not `FAILED` or left `PENDING`)
  when its trigger rule isn't satisfied.
- A crash or forced stop mid-run, followed by a fresh `PipelineOrchestrator` instance
  loading the same `state_path`, correctly reports which tasks had already succeeded.
- `run(..., resume=True)` never re-invokes a task callable whose state is already
  `SUCCESS` for that `logical_date`, and correctly re-evaluates (not just re-runs) every
  task that was previously `SKIPPED` or `FAILED` against the current state of its
  dependencies.
- The worked scenario above reproduces the stated expected results exactly when run against
  your implementation.
