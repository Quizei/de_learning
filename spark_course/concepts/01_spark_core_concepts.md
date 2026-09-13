# Concept 01: Spark Core Concepts

**Covers:**
- RDD vs DataFrame vs Dataset
- Transformations vs actions
- Lazy evaluation
- Driver vs executors
- Jobs, stages, and tasks hierarchy
- Partitions
- Narrow vs wide transformations
- SparkSession vs SparkContext
- DAG basics (a light preview -- see `03_dag_and_execution.md` for depth)
- Catalyst optimizer (a light preview -- see `02_query_plans_and_explain.md` for depth)
- spark-submit basics
- Local vs cluster mode

*All PySpark code below reflects real behavior of a running SparkSession; the worked examples are simulated in plain Python/reasoning so you can follow along without a cluster.*

---

## 1. RDD vs DataFrame vs Dataset

Spark has three core data abstractions, layered on top of each other:

**RDD (Resilient Distributed Dataset)**
- The original, lowest-level abstraction (Spark 1.0)
- A distributed collection of JVM/Python objects, partitioned across the cluster, with no schema
- You operate on it with functional transforms: `map`, `filter`, `reduce`
- No Catalyst optimization -- Spark can't see inside your lambdas

**DataFrame**
- A distributed collection of `Row` objects organized into named, typed columns (conceptually like a table / pandas DataFrame)
- Has a schema -- Catalyst and Tungsten can optimize and compile it
- The primary API for PySpark; RDDs are rarely used directly today

**Dataset**
- Typed DataFrame available in Scala/Java (compile-time type safety)
- Does NOT exist in PySpark -- Python is dynamically typed, so PySpark DataFrames are really `Dataset[Row]` under the hood

```text
+----------------------------------------------------------------+
| Feature          | RDD          | DataFrame      | Dataset      |
+----------------------------------------------------------------+
| Schema           | No           | Yes            | Yes          |
| Optimization     | None         | Catalyst+Tungsten | Catalyst+Tungsten |
| Type safety      | Compile-time | Runtime only   | Compile-time |
| Available in     | All langs    | All langs      | Scala/Java   |
| PySpark reality  | Rare use     | Standard API   | N/A (Dataset[Row]) |
+----------------------------------------------------------------+
```

```python
# RDD -- low level, no schema
rdd = sc.textFile("sales.txt")
parsed = rdd.map(lambda line: line.split(","))

# DataFrame -- schema-aware, optimized
df = spark.read.csv("sales.csv", header=True, inferSchema=True)
df.printSchema()
```

**Simulation:** the same raw data, treated RDD-style (untyped tuples) versus DataFrame-style (named, typed fields).

```python
raw_lines = ["alice,100,east", "bob,200,west", "carol,150,east"]

# RDD-style: untyped tuples, no schema
rdd_style = [tuple(line.split(",")) for line in raw_lines]
print(f"  [RDD-style]  no schema, just tuples: {rdd_style}")

# DataFrame-style: named fields with types
schema = ["name", "amount", "region"]
df_style = [dict(zip(schema, (r[0], int(r[1]), r[2]))) for r in rdd_style]
print(f"  [DF-style]   schema={schema}")
print(f"  [DF-style]   rows: {df_style}")
```

**Output:**
```text
  [RDD-style]  no schema, just tuples: [('alice', '100', 'east'), ('bob', '200', 'west'), ('carol', '150', 'east')]
  [DF-style]   schema=['name', 'amount', 'region']
  [DF-style]   rows: [{'name': 'alice', 'amount': 100, 'region': 'east'}, {'name': 'bob', 'amount': 200, 'region': 'west'}, {'name': 'carol', 'amount': 150, 'region': 'east'}]
```

---

## 2. Transformations vs Actions

Every Spark operation is either a **transformation** or an **action**.

Transformations return a new RDD/DataFrame and are lazy (not executed immediately). Examples: `select`, `filter`, `withColumn`, `groupBy`, `join`, `map`.

Actions trigger actual computation and return a result to the driver (or write to storage). Examples: `collect`, `count`, `show`, `take`, `write`, `foreach`, `reduce`.

Only actions cause Spark to run anything. A chain of 50 transforms followed by zero actions does no work at all.

```text
TRANSFORMATIONS (lazy)          ACTIONS (eager, trigger execution)
-----------------------         -----------------------------------
select(), filter()               collect(), count(), show()
withColumn(), drop()             take(n), first(), head()
groupBy(), agg()                 write.parquet(...), write.csv(...)
join(), union()                  foreach(), reduce()
orderBy(), distinct()            toPandas()
```

```python
df2 = df.filter(F.col("amount") > 100)   # transformation -- lazy
df3 = df2.select("name", "amount")        # transformation -- lazy
df3.show()                                 # ACTION -- runs everything now
```

**Simulation:** track how many "operations" actually run, versus how many are merely queued.

```python
executed_ops = []

def transform(name):
    print(f"  [TRANSFORM] queued '{name}' -- 0 rows touched yet")

def action(name, work_units):
    executed_ops.append(name)
    print(f"  [ACTION]    '{name}' triggered execution -- {work_units} rows processed")

transform("filter(amount > 100)")
transform("select(name, amount)")
print("  (still nothing has run)")
action("show()", work_units=3)
```

**Output:**
```text
  [TRANSFORM] queued 'filter(amount > 100)' -- 0 rows touched yet
  [TRANSFORM] queued 'select(name, amount)' -- 0 rows touched yet
  (still nothing has run)
  [ACTION]    'show()' triggered execution -- 3 rows processed
```

---

## 3. Lazy Evaluation

Lazy evaluation means transformations only build up a logical plan (a recipe). Spark doesn't touch the data until an action forces it to.

Why this matters:
- Spark sees the FULL chain of operations before running any of it, so Catalyst can reorder, merge, or eliminate steps
- Filters can be pushed down close to the data source
- Unused columns can be pruned before any data is read

**Simulation:** a minimal stand-in for a lazy logical plan, which just records operation names until `.run()` is called.

```python
class LazyPlan:
    """Minimal simulation of a lazy logical plan."""

    def __init__(self, source):
        self.source = source
        self.ops = []

    def add(self, op_name):
        self.ops.append(op_name)
        print(f"  [LAZY] plan now: {' -> '.join([self.source] + self.ops)}")
        return self

    def run(self):
        print(f"  [LAZY] ACTION fired. Executing plan: {' -> '.join([self.source] + self.ops)}")

plan = LazyPlan("read(sales.csv)")
plan.add("filter(amount>100)")
plan.add("select(name,amount)")
print("  (no data has been read from disk yet)")
plan.run()
```

**Output:**
```text
  [LAZY] plan now: read(sales.csv) -> filter(amount>100)
  [LAZY] plan now: read(sales.csv) -> filter(amount>100) -> select(name,amount)
  (no data has been read from disk yet)
  [LAZY] ACTION fired. Executing plan: read(sales.csv) -> filter(amount>100) -> select(name,amount)
```

---

## 4. Driver vs Executors

**Driver:**
- Runs your main program, holds the SparkSession
- Builds the logical/physical plan and the DAG
- Schedules tasks and collects their results
- A single point -- if it dies, the application dies

**Executors:**
- JVM processes on worker nodes
- Run tasks assigned by the driver, in parallel, one thread per core
- Cache partitions in memory/disk when asked
- Report task status/results back to the driver

```text
+--------------------+          +------------------+  +------------------+
|      DRIVER        |          |   EXECUTOR 1     |  |   EXECUTOR 2     |
|  - SparkSession     |  tasks   |  - 4 cores       |  |  - 4 cores       |
|  - builds DAG      | -------> |  - runs 4 tasks   |  |  - runs 4 tasks   |
|  - schedules tasks |          |    in parallel    |  |    in parallel    |
|  - collects results| <------- |  - cached blocks  |  |  - cached blocks  |
+--------------------+  results +------------------+  +------------------+
```

**Simulation:** distribute 8 tasks across 2 executors, 4 cores each, round-robin.

```python
tasks = list(range(8))
executors = {"executor_1": [], "executor_2": []}
exec_names = list(executors.keys())
for t in tasks:
    executors[exec_names[t % 2]].append(t)

print("  Driver schedules 8 tasks across 2 executors (4 cores each):")
for name, assigned in executors.items():
    print(f"    {name}: tasks {assigned}")
```

**Output:**
```text
  Driver schedules 8 tasks across 2 executors (4 cores each):
    executor_1: tasks [0, 2, 4, 6]
    executor_2: tasks [1, 3, 5, 7]
```

---

## 5. Jobs, Stages, and Tasks

Spark's execution hierarchy, top to bottom:

```
Application
  -> Job        one job per ACTION
       -> Stage  one stage per set of transforms between shuffle boundaries
            -> Task   one task per partition, within a stage
```

Rule of thumb: 1 action triggers 1 job. A job has N stages (N-1 shuffles + 1). Each stage has as many tasks as the RDD/DataFrame has partitions at that point in the plan.

```text
APPLICATION
  +-- JOB 0 (triggered by df.count())
         +-- STAGE 0 (read + filter, 4 partitions)
         |      +-- Task 0, Task 1, Task 2, Task 3
         +-- [SHUFFLE BOUNDARY: groupBy]
         +-- STAGE 1 (aggregate, 200 partitions)
                +-- Task 0 ... Task 199
```

**Simulation:** an action creates a job made of 2 stages.

```python
job_id = 0
stage_0_partitions = 4
stage_1_partitions = 200  # default spark.sql.shuffle.partitions

print(f"  Action fired -> Job {job_id} created")
print(f"    Stage 0: narrow transforms, {stage_0_partitions} tasks (1 per partition)")
print(f"    -- shuffle boundary --")
print(f"    Stage 1: post-shuffle aggregation, {stage_1_partitions} tasks")
total_tasks = stage_0_partitions + stage_1_partitions
print(f"    Total tasks for this job: {total_tasks}")
```

**Output:**
```text
  Action fired -> Job 0 created
    Stage 0: narrow transforms, 4 tasks (1 per partition)
    -- shuffle boundary --
    Stage 1: post-shuffle aggregation, 200 tasks
    Total tasks for this job: 204
```

---

## 6. Partitions

A partition is a chunk of the dataset that lives on one executor and is processed by exactly one task at a time. Partitioning is what makes parallelism possible -- more partitions (up to core count) means more concurrent tasks.

Partition count is influenced by:
- Input file splits (e.g. HDFS block size, number of files)
- `spark.sql.shuffle.partitions` (default 200, used after a shuffle)
- Explicit `repartition(n)` / `coalesce(n)` calls

```text
Dataset (12 rows) split into 3 partitions:
+------------------+  +------------------+  +------------------+
| Partition 0      |  | Partition 1      |  | Partition 2      |
| rows 0-3         |  | rows 4-7         |  | rows 8-11        |
| -> Task on Exec A|  | -> Task on Exec B|  | -> Task on Exec A|
+------------------+  +------------------+  +------------------+
```

**Simulation:** distribute 12 rows into 3 partitions round-robin (`row % num_partitions`).

```python
data = list(range(12))
num_partitions = 3
partitions = {i: [] for i in range(num_partitions)}
for row in data:
    partitions[row % num_partitions].append(row)

print(f"  Distributing {len(data)} rows into {num_partitions} partitions (round-robin):")
for pid, rows in partitions.items():
    print(f"    Partition {pid}: {rows} ({len(rows)} rows -> 1 task)")
```

**Output:**
```text
  Distributing 12 rows into 3 partitions (round-robin):
    Partition 0: [0, 3, 6, 9] (4 rows -> 1 task)
    Partition 1: [1, 4, 7, 10] (4 rows -> 1 task)
    Partition 2: [2, 5, 8, 11] (4 rows -> 1 task)
```

---

## 7. Narrow vs Wide Transformations

**Narrow transformations:** each output partition depends on exactly one input partition. No network shuffle. Examples: `map`, `filter`, `select`, `union`, `mapPartitions`.

**Wide transformations:** an output partition may depend on data from MANY input partitions, requiring a shuffle (data movement across the network, keyed by hash or range). Examples: `groupBy`, `join`, `distinct`, `repartition`, `orderBy`.

Wide transformations are the main cost driver in Spark jobs -- they involve disk writes, network I/O, and a new stage.

```text
NARROW (map/filter):              WIDE (groupBy/join):
+----------+   +----------+       +----------+   +----------+
| Part. 0  |-->| Part. 0  |       | Part. 0  |-+>| Part. 0  |
+----------+   +----------+       +----------+ X +----------+
| Part. 1  |-->| Part. 1  |       | Part. 1  |-+>| Part. 1  |
+----------+   +----------+       +----------+   +----------+
   no shuffle                        shuffle (network)
```

**Simulation:** a narrow `filter` applied independently per partition, versus a wide `groupBy` that must collect matching keys from across all partitions.

```python
partitions = {
    0: [("east", 100), ("west", 200)],
    1: [("east", 50), ("south", 300)],
}

print("  NARROW -- filter(amount > 60), each partition independent:")
for pid, rows in partitions.items():
    filtered = [r for r in rows if r[1] > 60]
    print(f"    Partition {pid}: {rows} -> {filtered}")

print("\n  WIDE -- groupBy(region), needs shuffle to co-locate same keys:")
all_rows = [r for rows in partitions.values() for r in rows]
grouped = {}
for region, amt in all_rows:
    grouped.setdefault(region, []).append(amt)
for region, amounts in grouped.items():
    print(f"    region='{region}' collected from multiple partitions -> {amounts}")
```

**Output:**
```text
  NARROW -- filter(amount > 60), each partition independent:
    Partition 0: [('east', 100), ('west', 200)] -> [('east', 100), ('west', 200)]
    Partition 1: [('east', 50), ('south', 300)] -> [('south', 300)]

  WIDE -- groupBy(region), needs shuffle to co-locate same keys:
    region='east' collected from multiple partitions -> [100, 50]
    region='west' collected from multiple partitions -> [200]
    region='south' collected from multiple partitions -> [300]
```

---

## 8. SparkSession vs SparkContext

`SparkContext` (`sc`) is the original, lower-level entry point -- it talks to the cluster manager and manages RDDs. It has existed since Spark 1.0.

`SparkSession` (`spark`), introduced in Spark 2.0, wraps `SparkContext` and unifies `SQLContext`, `HiveContext`, and `StreamingContext` into one object. Nearly all modern code uses `SparkSession`; you reach the underlying `SparkContext` via `spark.sparkContext` if you ever need RDD-level APIs.

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("demo").master("local[*]").getOrCreate()
sc = spark.sparkContext          # underlying SparkContext, if needed for RDD APIs

df = spark.read.csv("data.csv")  # DataFrame API (SparkSession)
rdd = sc.textFile("data.csv")    # RDD API (SparkContext)
```

**Simulation:** a small stand-in class hierarchy showing that a `SparkSession` wraps a `SparkContext`.

```python
class SimSparkContext:
    def __init__(self, master):
        self.master = master
        print(f"  [SIM] SparkContext connected to master='{master}'")

class SimSparkSession:
    def __init__(self, app_name, master):
        self.sparkContext = SimSparkContext(master)
        print(f"  [SIM] SparkSession '{app_name}' ready (wraps SparkContext, SQLContext, HiveContext)")

SimSparkSession("demo", "local[*]")
```

**Output:**
```text
  [SIM] SparkContext connected to master='local[*]'
  [SIM] SparkSession 'demo' ready (wraps SparkContext, SQLContext, HiveContext)
```

---

## 9. DAG Basics and the Catalyst Optimizer (Light Preview)

**DAG (Directed Acyclic Graph):** every time you call an action, Spark walks the chain of transformations you built and represents it as a graph of dependencies with no cycles -- hence "directed acyclic". The DAG scheduler then cuts this graph into stages at shuffle boundaries. (Full depth on DAGs and execution is in `03_dag_and_execution.md`.)

**Catalyst optimizer:** for DataFrame/SQL code, Spark doesn't run your plan as literally written. It parses it into a logical plan, resolves column/table references against the catalog, then applies rule-based and cost-based optimizations (predicate pushdown, column pruning, constant folding, join reordering) before generating a physical plan and, via Tungsten, compiled JVM bytecode. This is why DataFrame code is almost always faster than equivalent hand-written RDD code -- the RDD API is opaque to Catalyst, but DataFrame operations are not. (Full depth on plans and `.explain()` is in `02_query_plans_and_explain.md`.)

```text
Your code                DAG (dependency graph)         Stages (cut at shuffles)
----------                ----------------------         -------------------------
read -> filter            [read]->[filter]->[groupBy]     Stage 0: read, filter
   -> groupBy                                              Stage 1: groupBy (post-shuffle)

DataFrame code  --Catalyst-->  optimized plan  --Tungsten-->  compiled bytecode
```

This section is a pointer rather than a full simulation: see `03_dag_and_execution.md` for stage-splitting depth, and `02_query_plans_and_explain.md` for reading real `explain()` output.

---

## 10. spark-submit and Deployment Modes

`spark-submit` launches a Spark application against a cluster manager (Standalone, YARN, Kubernetes) or locally.

**Local mode:** driver and "executors" are threads in a single JVM on one machine. Great for development/testing; no real distributed execution.

**Cluster mode:** driver and executors run as separate processes across multiple machines, coordinated by a cluster manager. This is how production workloads run.

Within cluster deployments, `--deploy-mode` further chooses whether the driver itself runs on your submitting machine (`client`) or on the cluster (`cluster`).

```text
spark-submit \
    --master yarn \              # or local[*], spark://host:7077, k8s://...
    --deploy-mode cluster \      # driver location: client | cluster
    --num-executors 10 \
    --executor-memory 8g \
    --executor-cores 4 \
    my_job.py

LOCAL MODE                         CLUSTER MODE
-----------------------------      -----------------------------
master = "local[*]"                master = "yarn" / "spark://..." / "k8s://..."
driver + executors = 1 JVM         driver + executors = separate processes/nodes
good for dev/test                  good for production workloads
no real network shuffle cost       real network + disk shuffle cost
```

**Simulation:** the master string associated with each mode.

```python
configs = {"local": "local[*]", "cluster": "yarn"}
for mode, master in configs.items():
    print(f"  [SIM] mode='{mode}': master='{master}'")
```

**Output:**
```text
  [SIM] mode='local': master='local[*]'
  [SIM] mode='cluster': master='yarn'
```

---

## Key Takeaways

- DataFrames (schema + Catalyst optimization) are the standard API; RDDs are the low-level, unoptimized foundation underneath them.
- Transformations are lazy and build a plan; only actions execute it.
- The driver plans and schedules; executors do the actual data work.
- 1 action = 1 job; a job is split into stages at shuffle boundaries; each stage runs 1 task per partition.
- Partitions are the unit of parallelism -- one task processes one partition on one executor core at a time.
- Narrow transforms (map/filter) need no shuffle; wide transforms (groupBy/join) do, and shuffles are usually the biggest cost.
- SparkSession is the modern unified entry point; SparkContext is the lower-level object it wraps for RDD access.
- Local mode runs everything in one JVM for development; cluster mode distributes driver and executors across real machines.
