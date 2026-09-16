# Concept 02: Operators, Sensors & Cross-Task Communication

**Covers:**
- Operators — the "what" a task does, as distinct from the DAG's "when" and "order"
- Sensors — waiting for a condition, poke mode vs. reschedule mode vs. deferrable/event-driven
- Cross-task data passing (XCom in Airflow terms), and why it's for metadata, not payloads
- Writing a custom operator, and why teams end up doing it
- The same ideas as Dagster/Prefect ops, sensors, and assets

*Code below is runnable, dependency-free Python simulating operator/sensor behavior — the same shape real Airflow operators implement, minus the scheduler and metadata database around them.*

---

## 1. Operators Are the "What"; the DAG Is the "When" and "Order"

A DAG (`concepts/01_dag_fundamentals.md`) defines dependency order. An **operator** defines what a single task actually *does* when it runs. Splitting these two concerns is deliberate: the same operator type gets reused across dozens of DAGs, and the same DAG's shape is unaffected by swapping what one node inside it runs.

Every real Airflow operator inherits from a common base that provides retry bookkeeping, state, and a `.execute()` hook subclasses fill in:

```python
import time
from abc import ABC, abstractmethod

class BaseOperator(ABC):
    """Every operator type in this file inherits from this."""
    def __init__(self, task_id, retries=0, retry_delay=1):
        self.task_id = task_id
        self.retries = retries
        self.retry_delay = retry_delay
        self.state = "pending"
        self.result = None

    @abstractmethod
    def execute(self, context=None):
        """Subclasses implement the actual work here."""
        raise NotImplementedError

    def run(self, context=None):
        context = context or {}
        for attempt in range(self.retries + 1):
            try:
                self.state = "running"
                self.result = self.execute(context)
                self.state = "success"
                return self.result
            except Exception as e:
                if attempt < self.retries:
                    time.sleep(self.retry_delay)
                else:
                    self.state = "failed"
                    raise
```

### The three operator families

```text
Action operators    Do something directly           PythonOperator, BashOperator, SQL operators
Transfer operators   Move data between two systems    S3ToRedshiftOperator, PostgresToGCSOperator
Sensors              WAIT for a condition, then let    FileSensor, ExternalTaskSensor, PartitionSensor
                     downstream tasks proceed
```

### PythonOperator and BashOperator

```python
class PythonOperator(BaseOperator):
    """Runs any Python callable. The most common operator by far."""
    def __init__(self, task_id, python_callable, op_args=None, op_kwargs=None, **kwargs):
        super().__init__(task_id, **kwargs)
        self.python_callable = python_callable
        self.op_args = op_args or []
        self.op_kwargs = op_kwargs or {}

    def execute(self, context=None):
        return self.python_callable(*self.op_args, **self.op_kwargs)


class BashOperator(BaseOperator):
    """Runs a shell command -- a script, a CLI tool (dbt, spark-submit), etc."""
    def __init__(self, task_id, bash_command, **kwargs):
        super().__init__(task_id, **kwargs)
        self.bash_command = bash_command

    def execute(self, context=None):
        print(f"    would execute: {self.bash_command}")
        return {"command": self.bash_command, "status": "ok"}


calc = PythonOperator(
    task_id="calc_revenue",
    python_callable=lambda region, multiplier=1.0: {"region": region, "revenue": 50000 * multiplier},
    op_args=["US"], op_kwargs={"multiplier": 1.15},
)
print(calc.run())
```

```text
{'region': 'US', 'revenue': 57500.0}
```

The real Airflow equivalent is written declaratively inside a `with DAG(...)` block:

```python
# Real Airflow -- not runnable standalone, shown for the API shape
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

extract = PythonOperator(task_id="extract", python_callable=extract_fn)
cleanup = BashOperator(task_id="cleanup", bash_command="rm -rf /tmp/staging/*")
```

---

## 2. Sensors: Waiting for a Condition, Three Different Ways

A **sensor** is a special operator whose entire job is to **wait** — it repeatedly checks ("pokes") a condition and only lets its downstream tasks proceed once that condition is true. The condition is almost always something outside the DAG's own control: a file landing in a bucket, an upstream system's table partition finishing, a fixed wall-clock time being reached.

```python
class BaseSensor(BaseOperator):
    """poke_interval: seconds between checks. timeout: give up after this long."""
    def __init__(self, task_id, poke_interval=1, timeout=10, **kwargs):
        super().__init__(task_id, **kwargs)
        self.poke_interval = poke_interval
        self.timeout = timeout

    @abstractmethod
    def poke(self, context=None):
        """Return True once the condition is met."""
        raise NotImplementedError

    def execute(self, context=None):
        start = time.time()
        attempt = 0
        while True:
            attempt += 1
            if time.time() - start > self.timeout:
                raise TimeoutError(f"'{self.task_id}' timed out after {self.timeout}s")
            if self.poke(context):
                return True
            time.sleep(self.poke_interval)


class ConditionalSensor(BaseSensor):
    def __init__(self, task_id, condition_fn, **kwargs):
        super().__init__(task_id, **kwargs)
        self.condition_fn = condition_fn

    def poke(self, context=None):
        return self.condition_fn()


calls = {"n": 0}
def upstream_partition_ready():
    calls["n"] += 1
    return calls["n"] >= 3          # ready on the 3rd check

sensor = ConditionalSensor("wait_for_partition", upstream_partition_ready,
                           poke_interval=0.1, timeout=5)
print(sensor.run())
```

```text
True
```

### Poke mode vs. reschedule mode vs. deferrable — this is the part interviewers actually probe

A sensor's `mode` parameter decides *how* it waits, and picking the wrong one is a classic operational mistake:

```text
mode='poke'        Holds a full worker slot for the ENTIRE wait, sleeping between checks.
                    Cheapest to write, most expensive to run: a sensor waiting 4 hours for
                    a file blocks one worker slot for 4 hours doing nothing.

mode='reschedule'  Releases the worker slot between pokes and re-queues itself for the
                    next check. Costs a bit of scheduler overhead per poke, but frees the
                    slot for other tasks in between -- the standard fix for a long-running
                    sensor eating capacity.

deferrable         (Airflow 2.2+) Doesn't occupy a worker AT ALL while waiting -- it hands
operator/trigger   off to a lightweight async "triggerer" process and the worker slot is
                    fully free until the condition fires, which then re-queues the task.
                    The most efficient option, but requires the sensor/operator to have a
                    deferrable (async-aware) implementation, and not everything does.
```

`mode='poke'` left on its default for a sensor that can realistically wait hours is one of the most common real production incidents this topic produces (see `interview_questions/03_critique_and_debug.md` and `interview_questions/05_oncall_incident_triage.md`) — a handful of long-poking sensors can silently exhaust a worker pool and stall every *other* DAG that needs a slot, with no error anywhere until someone notices nothing else is running.

### Orchestrator-agnostic framing

Every orchestrator has some version of this same choice — "wait by holding a worker" vs. "wait without holding a worker" — because it's a structural tradeoff (poll cost vs. resource cost), not an Airflow implementation detail:

```text
Airflow:   Sensor, mode='poke' | mode='reschedule' | deferrable operator (async, no worker held)
Dagster:   Sensor (polls at a defined interval; runs as a lightweight daemon process, not a worker)
Prefect:   An event trigger / webhook is generally preferred outright over a busy-poll task
```

---

## 3. Cross-Task Communication: Small Metadata, Not Payloads

Tasks in a DAG need to hand small pieces of information downstream — a row count, a file path, a partition key — without going through a shared database each time. Airflow calls this mechanism **XCom** ("cross-communication"); the concept exists under other names everywhere else.

```python
class XComBackend:
    """
    Simulates Airflow's XCom store: a (task_id, key) -> value map, backed in
    real Airflow by the metadata database.
    """
    def __init__(self):
        self.store = {}

    def push(self, task_id, value, key="return_value"):
        self.store[(task_id, key)] = value

    def pull(self, task_id, key="return_value"):
        return self.store.get((task_id, key))


xcom = XComBackend()

extract_result = {"file_path": "/data/sales_2024.csv", "row_count": 15000}
xcom.push("extract_sales", extract_result)

extracted = xcom.pull("extract_sales")
print(f"validating {extracted['row_count']} rows from {extracted['file_path']}")
xcom.push("validate_sales", {"valid_count": 14850, "invalid_count": 150})
```

```text
validating 15000 rows from /data/sales_2024.csv
```

In real Airflow, a task's **return value is pushed automatically**; a downstream task pulls it via `context['ti'].xcom_pull(task_ids='extract_sales')`:

```python
# Real Airflow -- shown for the API shape, not runnable standalone
def extract(**context):
    return {"file_path": "/data/sales.csv", "row_count": 15000}   # auto-pushed

def transform(**context):
    data = context["ti"].xcom_pull(task_ids="extract")
    ...
```

**The rule that matters far more than the API:** XComs (and their equivalents everywhere else) are for **small metadata** — counts, paths, flags, IDs — never for passing an actual DataFrame or a large payload between tasks. The metadata database isn't built to hold megabytes-per-row, and every orchestrator either silently bloats its own backing store or outright caps XCom size for exactly this reason. The correct pattern for real data handoff is: write the data to a shared location (S3, a staging table) in the upstream task, and pass only the *path or table name* through XCom for the downstream task to read.

---

## 4. Writing a Custom Operator

Teams write custom operators once a `PythonOperator` wrapping the same 15 lines of boilerplate shows up in enough DAGs that it's worth naming and reusing:

```python
class ApiToFileOperator(BaseOperator):
    """Fetch from an API, land the response as a file. A real reusable operator
    would take a connection ID and use a Hook rather than hardcoding a client."""
    def __init__(self, task_id, api_url, output_path, **kwargs):
        super().__init__(task_id, **kwargs)
        self.api_url = api_url
        self.output_path = output_path

    def execute(self, context=None):
        # data = requests.get(self.api_url).json()  -- the real call
        data = {"records": [{"id": 1}, {"id": 2}, {"id": 3}]}
        return {"records_fetched": len(data["records"]), "path": self.output_path}


op = ApiToFileOperator(task_id="fetch_weather", api_url="https://api.weather.example/v1/forecast",
                        output_path="/data/staging/weather.json")
print(op.run())
```

```text
{'records_fetched': 3, 'path': '/data/staging/weather.json'}
```

The reasons a real team reaches for a custom operator instead of another copy-pasted `PythonOperator`: (1) the same connection/auth/retry logic needs to be consistent across many DAGs, (2) the operator should show up cleanly in the UI/lineage with its own name rather than as an anonymous Python function, (3) parameters should be validated once, at DAG-parse time, instead of failing deep inside a function body at runtime.

---

## Key Takeaways

- Operators define *what* a task does; the DAG defines *when* and in what *order* — the same operator type is reused across many DAGs precisely because that split holds.
- The three operator families: action (do something), transfer (move data between systems), sensor (wait for a condition).
- A sensor's `mode` is an operational decision, not a style choice: `poke` holds a worker slot for the entire wait, `reschedule` frees it between checks, and a deferrable/async operator (or an event trigger in Dagster/Prefect) frees it entirely. A poke-mode sensor left waiting for hours is a classic way to silently starve a worker pool.
- Cross-task data passing (XCom in Airflow) is for small metadata — counts, paths, flags — never for actual data payloads; large data is written to shared storage and only its location passed through.
- Custom operators earn their keep once shared connection/retry/validation logic would otherwise be copy-pasted across many `PythonOperator` tasks.
- The "wait without burning a worker" problem is universal across orchestrators — Airflow's deferrable operators, Dagster's sensor daemon, and Prefect's event triggers are three different answers to the same structural question.
