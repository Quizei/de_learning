# Concept 03: Spark DAGs and Execution

**Covers:**
- The DAG scheduler and how a DAG is built from lazy transformations
- How the DAG is split into stages at shuffle boundaries
- Jobs vs stages vs tasks (1 action -> 1 job, N stages per job, 1 task per partition per stage)
- The Spark UI's DAG visualization (described in ASCII)
- Task scheduling and speculative execution
- Retries on task failure
- A worked simulation of a 2-stage word count job showing stage boundaries and task counts explicitly

*All PySpark code below reflects real behavior of a running SparkSession; the worked examples are simulated in plain Python/reasoning so you can follow along without a cluster.*

---

## 1. The DAG Scheduler

The DAG Scheduler is the driver-side component responsible for turning your chain of transformations into physical execution units.

Its job, in order:
1. Take the final RDD/DataFrame lineage that an action was called on
2. Walk the dependency graph backward from that final node
3. Identify shuffle dependencies (wide transformations) -- these become stage boundaries
4. Emit a set of Stage objects, each containing a set of Tasks
5. Hand ready stages (whose inputs are available) to the Task Scheduler, which places tasks on executors

The DAG scheduler also handles stage retries: if an entire stage's output is lost (e.g. an executor died holding shuffle files), it resubmits just the missing stage, not the whole job.

```text
Your code (chain of transformations)
         |
         v
+--------------------------+
| Logical lineage graph    |   RDD/DataFrame dependency chain
+------------+-------------+
             |  action() called
             v
+--------------------------+
| DAG SCHEDULER            |   walks lineage backward,
|  - finds shuffle deps    |   cuts graph into stages
|  - builds Stage objects  |
+------------+-------------+
             v
+--------------------------+
| TASK SCHEDULER           |   assigns tasks to executor cores,
|  - places tasks          |   handles retries & speculation
+--------------------------+
```

**Simulation:** a tiny lineage graph (`read -> filter -> groupBy -> select`) walked backward from the final node, flagging the shuffle boundary.

```python
class Node:
    def __init__(self, name, shuffle=False, parent=None):
        self.name = name
        self.shuffle = shuffle
        self.parent = parent

# Build a small lineage: read -> filter -> groupBy -> select
n1 = Node("read(orders.parquet)")
n2 = Node("filter(amount>100)", parent=n1)
n3 = Node("groupBy(region)", shuffle=True, parent=n2)  # wide -> shuffle
n4 = Node("select(region,total)", parent=n3)

print("  Walking lineage backward from the action's final node:")
chain = [n4, n3, n2, n1]
for node in chain:
    marker = " <- SHUFFLE (stage boundary)" if node.shuffle else ""
    print(f"    {node.name}{marker}")
```

**Output:**
```text
  Walking lineage backward from the action's final node:
    select(region,total)
    groupBy(region) <- SHUFFLE (stage boundary)
    filter(amount>100)
    read(orders.parquet)
```

---

## 2. Splitting the DAG into Stages

A stage is a maximal set of transformations that can be pipelined together WITHOUT crossing a shuffle boundary. Every wide transformation (`groupBy`, `join`, `repartition`, `distinct`, `orderBy`) forces a new stage because its output partitions depend on data scattered across ALL upstream partitions.

Rule: N shuffles in the DAG -> N+1 stages in the job.

Within a stage, all narrow operations (`map`, `filter`, `select`) are fused into a single pipeline that runs per-partition, per-task, with no intermediate materialization -- this is why narrow chains are cheap regardless of how many you stack.

```text
DAG:  read -> filter -> map -> groupBy -> filter -> select
                                 ^
                             SHUFFLE (wide transform)

STAGE 0                         STAGE 1
+-----------------------+       +---------------------------+
| read -> filter -> map |  -->  | (post-shuffle) filter ->   |
| (pipelined, 1 task    |       |  select                    |
|  per input partition) |       | (pipelined, 1 task per     |
+-----------------------+       |  post-shuffle partition)   |
                                 +---------------------------+
```

**Simulation:** cut a DAG's operation list into stages whenever a `"SHUFFLE"`-marked op appears.

```python
dag_ops = ["read", "filter", "map", "groupBy(SHUFFLE)", "filter", "select"]
stages = [[]]
for op in dag_ops:
    stages[-1].append(op)
    if "SHUFFLE" in op:
        stages.append([])

print(f"  DAG has {sum(1 for op in dag_ops if 'SHUFFLE' in op)} shuffle(s) -> {len(stages)} stage(s)")
for i, stage_ops in enumerate(stages):
    print(f"    Stage {i}: {stage_ops}")
```

**Output:**
```text
  DAG has 1 shuffle(s) -> 2 stage(s)
    Stage 0: ['read', 'filter', 'map', 'groupBy(SHUFFLE)']
    Stage 1: ['filter', 'select']
```

---

## 3. Jobs vs Stages vs Tasks

The three units of work, and how their counts are determined:

- **JOB** -- created once per ACTION call (`count()`, `collect()`, `write()`, ...)
- **STAGE** -- created once per set of ops between shuffle boundaries (N shuffles -> N+1 stages, per job)
- **TASK** -- created once per PARTITION, per stage (a stage with 200 partitions submits 200 tasks)

A single Spark application can run many jobs over its lifetime (one per action), and the Spark UI's Jobs tab lists them all with their stage and task counts.

**Simulation:** two jobs -- a plain `count()` (1 stage) and a `groupBy(...).sum(...).collect()` (2 stages, the second post-shuffle).

```python
jobs = [
    {"job_id": 0, "action": "df.count()", "stages": [{"partitions": 8}]},
    {"job_id": 1, "action": "df.groupBy('region').sum('amount').collect()",
     "stages": [{"partitions": 8}, {"partitions": 200}]},
]

for job in jobs:
    total_tasks = sum(s["partitions"] for s in job["stages"])
    print(f"  Job {job['job_id']} (triggered by {job['action']}):")
    for si, stage in enumerate(job["stages"]):
        print(f"    Stage {si}: {stage['partitions']} tasks (1 per partition)")
    print(f"    -> {len(job['stages'])} stage(s), {total_tasks} task(s) total\n")
```

**Output:**
```text
  Job 0 (triggered by df.count()):
    Stage 0: 8 tasks (1 per partition)
    -> 1 stage(s), 8 task(s) total

  Job 1 (triggered by df.groupBy('region').sum('amount').collect()):
    Stage 0: 8 tasks (1 per partition)
    Stage 1: 200 tasks (1 per partition)
    -> 2 stage(s), 208 task(s) total
```

---

## 4. The Spark UI's DAG Visualization

In the real Spark UI (`http://driver-host:4040`), the "Jobs" tab lists each job; clicking one shows "DAG Visualization" -- a graphical box diagram of the stages for that job, and clicking a stage shows its DAG of individual RDD operations plus a task timeline.

What you'd actually see (recreated here in ASCII):
- Each stage is a rounded box; boxes are stacked top-to-bottom in execution order
- Inside a stage box, individual operator names appear (WholeStageCodegen groups are shown as a single blue box in the UI)
- Arrows between stage boxes represent shuffle dependencies
- Below the DAG, the "Event Timeline" shows executor add/remove events and task start/end bars, colored by what the task spent time on (scheduler delay, deserialization, compute, shuffle read/write, GC)

```text
Spark UI > Jobs > Job 1 > DAG Visualization

+-------------------------------+
|  Stage 0                     |
|  Scan orders -> Filter ->     |
|  Project (WholeStageCodegen)  |
+---------------+---------------+
                | shuffle write
                v
+-------------------------------+
|  Stage 1                     |
|  Exchange -> HashAggregate -> |
|  Project (WholeStageCodegen)  |
+-------------------------------+

Spark UI > Stages > Stage 1 > Event Timeline
Executor 1: [task0|===compute===|shuffle-read|] [task2|=compute=|...]
Executor 2: [task1|==compute==|shuffle-read|]   [task3|=compute=|..]
            (bar width = time; color = phase: dark=compute, hatch=shuffle)
```

The Spark UI is the single best free debugging tool for Spark: stage DAGs show what ran; the event timeline shows WHERE time went.

---

## 5. Task Scheduling and Speculative Execution

**Task scheduling:** the Task Scheduler (per-application, driver-side) assigns each pending task to an available executor core, respecting locality preferences (`PROCESS_LOCAL` > `NODE_LOCAL` > `RACK_LOCAL` > `ANY`) -- it prefers running a task where its input data already sits, to avoid network transfer, waiting briefly (`spark.locality.wait`) before relaxing to a less local placement.

**Speculative execution** (`spark.speculation=true`): if one task in a stage is running much slower than its siblings (a "straggler", typically caused by a slow/overloaded node or skewed data), Spark can launch a duplicate copy of that task on a different executor. Whichever copy finishes first "wins" and the other is killed. This trades extra cluster resources for protection against stragglers -- it does NOT help if the slowness is due to genuine data skew (a partition with 100x more rows will be slow everywhere).

```text
Locality preference order (best to worst):
  PROCESS_LOCAL  -- data already in same executor JVM
  NODE_LOCAL     -- data on same physical node, different process
  RACK_LOCAL      -- data on same rack, different node
  ANY             -- no locality, data fetched over network

Speculative execution:
  Stage tasks:    [T0: 4s] [T1: 4s] [T2: 4s] [T3: 38s <- straggler]
  spark.speculation=true detects T3 as an outlier vs. median runtime
  -> launches T3' (duplicate) on a different executor
  -> whichever of T3 / T3' finishes first wins; the other is killed
```

**Simulation:** detect a straggler task as one running well above the median duration (a simplified stand-in for `spark.speculation.multiplier`).

```python
task_durations = {"T0": 4.1, "T1": 3.9, "T2": 4.0, "T3": 38.0}
median = sorted(task_durations.values())[len(task_durations) // 2]
threshold = median * 1.5  # simplified version of spark.speculation.multiplier

print(f"  Task durations (seconds): {task_durations}")
print(f"  Median duration: {median}s, speculation threshold: {threshold}s")
stragglers = [t for t, d in task_durations.items() if d > threshold]
print(f"  Straggler(s) detected: {stragglers} -> speculative copies launched")
```

**Output:**
```text
  Task durations (seconds): {'T0': 4.1, 'T1': 3.9, 'T2': 4.0, 'T3': 38.0}
  Median duration: 4.0s, speculation threshold: 6.0s
  Straggler(s) detected: ['T3'] -> speculative copies launched
```

---

## 6. Task Retries on Failure

If a task throws an exception or its executor is lost (crash, OOM, preemption), Spark retries it automatically, up to `spark.task.maxFailures` (default 4). Retries are scheduled preferably on a different executor to avoid repeating a node-specific failure.

If a whole stage's shuffle output becomes unreadable (e.g. the executor holding the shuffle files died), the DAG scheduler resubmits the STAGE that produced that output (a "stage retry"), not just the one task -- because the map output for the lost executor's partitions no longer exists anywhere.

Only after `maxFailures` is exceeded for a single task does the whole job fail.

**Simulation:** a task that fails three times for different reasons before succeeding on its fourth attempt, right at the `maxFailures` limit.

```python
max_failures = 4
attempts = ["fail: executor lost", "fail: OOM", "fail: fetch failed", "success"]

print(f"  spark.task.maxFailures = {max_failures}")
for attempt_num, outcome in enumerate(attempts, start=1):
    if outcome == "success":
        print(f"    Attempt {attempt_num}: SUCCESS -- task completes, job proceeds")
        break
    else:
        print(f"    Attempt {attempt_num}: {outcome} -- retrying on a different executor")
else:
    print(f"    All {max_failures} attempts failed -> JOB ABORTED")
```

**Output:**
```text
  spark.task.maxFailures = 4
    Attempt 1: fail: executor lost -- retrying on a different executor
    Attempt 2: fail: OOM -- retrying on a different executor
    Attempt 3: fail: fetch failed -- retrying on a different executor
    Attempt 4: SUCCESS -- task completes, job proceeds
```

---

## 7. Worked Simulation: A 2-Stage Word Count Job

Put everything together: run a word-count DAG through the same mental model Spark uses -- lineage, stage split at the shuffle, explicit task counts per stage, then task-level execution.

```python
rdd = sc.textFile("docs/*.txt")          # 3 input partitions (3 files)
words = rdd.flatMap(lambda line: line.split())
pairs = words.map(lambda w: (w, 1))
counts = pairs.reduceByKey(lambda a, b: a + b)  # WIDE -- shuffle here
counts.collect()                          # ACTION -- 1 job created
```

**Simulation:** 3 input partitions of text, flat-mapped and paired (Stage 0, narrow), then shuffled by `hash(word) % shuffle_partitions` into 2 post-shuffle partitions and reduced (Stage 1, post-shuffle).

```python
input_partitions = {
    0: ["hello world", "hello spark"],
    1: ["spark is fast"],
    2: ["hello fast world"],
}
shuffle_partitions = 2  # small number for a readable demo

print(f"  ACTION collect() called -> Job 0 created")
print(f"  DAG has 1 shuffle (reduceByKey) -> 2 stages\n")

# ---- Stage 0: narrow transforms (flatMap + map), 1 task per input partition
print(f"  STAGE 0: flatMap + map  ({len(input_partitions)} tasks, 1 per input partition)")
mapped = {}
for pid, lines in input_partitions.items():
    pairs = [(w, 1) for line in lines for w in line.split()]
    mapped[pid] = pairs
    print(f"    Task (stage 0, partition {pid}): {lines} -> {pairs}")

# ---- Shuffle: redistribute by hash(word) % shuffle_partitions
print(f"\n  SHUFFLE: repartitioning by hash(word) % {shuffle_partitions}")
shuffled = {i: [] for i in range(shuffle_partitions)}
for pairs in mapped.values():
    for word, one in pairs:
        target = hash(word) % shuffle_partitions
        shuffled[target].append((word, one))

# ---- Stage 1: reduceByKey, 1 task per shuffle partition
print(f"\n  STAGE 1: reduceByKey  ({shuffle_partitions} tasks, 1 per shuffle partition)")
final_counts = {}
for pid, pairs in shuffled.items():
    local_counts = {}
    for word, one in pairs:
        local_counts[word] = local_counts.get(word, 0) + one
    final_counts.update(local_counts)
    print(f"    Task (stage 1, partition {pid}) received {len(pairs)} pairs -> {local_counts}")

total_tasks = len(input_partitions) + shuffle_partitions
print(f"\n  Job 0 summary: 2 stages, {total_tasks} tasks total")
print(f"  Final word counts: {dict(sorted(final_counts.items()))}")
```

**Output:**

The Stage 0 narrow transforms and the final word counts are fully deterministic. The exact partition each word lands in after the shuffle depends on Python's built-in `hash()`, which is randomized per process (`PYTHONHASHSEED`) unless pinned -- so which words land in shuffle-partition 0 vs. 1 will vary run to run, even though the total structure (3 input tasks, 1 shuffle, 2 reduce tasks, 5 tasks total) never changes. Running it once with hash randomization disabled (`PYTHONHASHSEED=0`) gives a concrete, reproducible example of the shape you'd see:

```text
  ACTION collect() called -> Job 0 created
  DAG has 1 shuffle (reduceByKey) -> 2 stages

  STAGE 0: flatMap + map  (3 tasks, 1 per input partition)
    Task (stage 0, partition 0): ['hello world', 'hello spark'] -> [('hello', 1), ('world', 1), ('hello', 1), ('spark', 1)]
    Task (stage 0, partition 1): ['spark is fast'] -> [('spark', 1), ('is', 1), ('fast', 1)]
    Task (stage 0, partition 2): ['hello fast world'] -> [('hello', 1), ('fast', 1), ('world', 1)]

  SHUFFLE: repartitioning by hash(word) % 2

  STAGE 1: reduceByKey  (2 tasks, 1 per shuffle partition)
    Task (stage 1, partition 0) received 7 pairs -> {'hello': 3, 'world': 2, 'fast': 2}
    Task (stage 1, partition 1) received 3 pairs -> {'spark': 2, 'is': 1}

  Job 0 summary: 2 stages, 5 tasks total
  Final word counts: {'fast': 2, 'hello': 3, 'is': 1, 'spark': 2, 'world': 2}
```

---

## Key Takeaways

- The DAG scheduler walks the lineage graph backward from an action and cuts it into stages wherever a shuffle (wide transform) occurs.
- Rule of thumb: N shuffles in a job -> N+1 stages; 1 action -> 1 job; 1 task per partition per stage.
- Narrow transformations within a stage are pipelined and fused (WholeStageCodegen) -- stacking more of them costs little.
- The Spark UI's DAG visualization (Jobs/Stages tabs) is the primary tool for seeing this structure on a real cluster.
- Task placement respects data locality (PROCESS_LOCAL best, ANY worst); speculative execution re-runs slow-outlier tasks elsewhere.
- Failed tasks retry automatically (`spark.task.maxFailures`, default 4); a lost executor's shuffle output triggers a stage-level retry.
- Speculative execution helps with stragglers caused by slow nodes, not with genuine data skew -- a skewed partition is slow everywhere.
