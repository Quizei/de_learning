# Concept 12: Spark Executor Tuning

**Covers:**
- The three sizing knobs: --num-executors, --executor-cores, --executor-memory
- Fat vs thin executors — the tradeoff
- The "5 cores per executor" rule of thumb and why
- Reserving cores/memory per node for OS/YARN/NodeManager daemons
- A worked capacity-planning example with explicit arithmetic
- spark.executor.memoryOverhead (~7% default)
- Dynamic allocation (spark.dynamicAllocation.enabled)

*All PySpark/spark-submit configuration shown below is real and educational; the worked capacity-planning arithmetic and scaling behavior are simulated in plain Python so you can follow the numbers without a live cluster.*

---

## 1. The Three Sizing Knobs

Every Spark cluster deployment (YARN, Kubernetes, Standalone) is sized with three interacting knobs:

- **`--num-executors N`** — how many executor JVM processes to launch across the cluster. More executors means more parallel tasks cluster-wide, but each is a separate JVM with its own overhead and its own copy of broadcast data.

- **`--executor-cores C`** — how many concurrent tasks one executor JVM can run (1 core = 1 concurrent task slot, for CPU-bound work). Also determines how many tasks share that executor's memory pool at once.

- **`--executor-memory M`** — heap size per executor JVM. Divided (per Concept 11) into reserved / user / unified (execution + storage) memory, SHARED across all C concurrently running tasks in that executor.

These three interact:
```text
total_cluster_cores  = num_executors * executor_cores
total_cluster_memory = num_executors * executor_memory
memory_per_task      ~= executor_memory / executor_cores (contention)
```

Getting this wrong in either direction hurts:
- Too few, too-fat executors: poor I/O parallelism, huge GC pauses.
- Too many, too-thin executors: per-executor overhead dominates, and available memory per task shrinks.

```python
# spark-submit \
#     --num-executors 20 \
#     --executor-cores 5 \
#     --executor-memory 19g \
#     --conf spark.executor.memoryOverhead=2g \
#     my_job.py

total_cluster_cores  = 20 * 5   # = 100 concurrent task slots
total_cluster_memory = 20 * 19  # = 380 GB heap across all executors
```

---

## 2. Fat vs Thin Executors

Given a fixed total resource budget (say, one node with 16 cores/64GB), you can slice it into few "fat" executors or many "thin" executors.

**FAT executors (few, large — e.g. 2 executors x 8 cores x 32GB):**
- \+ Better memory sharing: broadcast variables, cached data, and the unified memory pool are shared across MORE concurrent tasks per JVM, so less total duplication.
- \+ Fewer JVMs means fewer copies of broadcast variables cluster-wide (each executor JVM holds its own copy).
- \- Worse HDFS I/O parallelism: HDFS client throughput per executor saturates around ~5 concurrent threads (see section 3) — an 8-core executor wastes cores beyond that for I/O-heavy stages.
- \- Bigger GC pauses: larger heaps mean the JVM garbage collector has more to scan per pause, so "stop-the-world" GC pauses get longer.
- \- A JVM crash/executor loss wastes more in-flight work (more tasks were running on it).

**THIN executors (many, small — e.g. 16 executors x 1 core x 4GB):**
- \+ Great I/O parallelism, small GC pauses.
- \- Each executor is its own JVM: fixed per-executor overhead (memoryOverhead, JVM startup cost, its own copy of every broadcast variable) is paid many more times over.
- \- Little room for the unified memory pool per task — 4GB minus reserved/user memory leaves very little for shuffle/join buffers.
- \- Only 1 core means no benefit from task-level parallelism sharing memory within the executor.

The practical sweet spot is almost always in between: moderate executors (commonly 4-6 cores each) that balance I/O parallelism against per-JVM overhead and memory sharing.

```text
Node budget: 16 cores, 64 GB RAM

FAT (2 executors):              THIN (16 executors):
+------------------------+      +---+ +---+ +---+ ... (x16)
| Executor 1             |      |1cr| |1cr| |1cr|
| 8 cores, 32 GB         |      |4GB| |4GB| |4GB|
| (shares mem/broadcast  |      +---+ +---+ +---+
|  across 8 task slots)  |      each: own JVM overhead,
+------------------------+      own broadcast copy,
| Executor 2             |      own tiny memory pool
| 8 cores, 32 GB         |
+------------------------+

Tradeoff table:
+----------------------+------------------+-------------------+
| Dimension            | Fat (few, large) | Thin (many, small)|
+----------------------+------------------+-------------------+
| Memory/broadcast reuse| Better           | Worse (duplicated)|
| HDFS I/O parallelism  | Worse (>5 cores  | Better (each stays|
|                        | wastes I/O)     |  near the sweet   |
|                        |                 |  spot)            |
| GC pause length       | Longer           | Shorter           |
| Per-executor overhead | Amortized well   | Paid many times   |
+----------------------+------------------+-------------------+
```

---

## 3. The "5 Cores per Executor" Rule of Thumb

A widely cited Spark tuning heuristic (originally from Cloudera's Spark tuning guidance): keep `executor-cores` around 5.

Why 5, specifically?
- HDFS client throughput per executor was empirically observed to saturate at roughly 5 concurrent reader/writer threads. Beyond that, the HDFS NameNode/DataNode-side lock contention and the HDFS client's own internal throughput ceiling mean additional threads add diminishing (or negative) returns for HDFS-bound stages.
- This isn't a CPU limit — modern nodes have far more than 5 cores. It's an I/O-contention limit specific to the HDFS client library.
- Going much higher (say, 12-16 cores per executor) also worsens GC pause times (more concurrent tasks means more heap churn per executor) and increases the blast radius of a single executor failure.

This is a STARTING heuristic, not a law:
- Non-HDFS-bound workloads (e.g. reading from object storage like S3, or CPU-bound UDF-heavy stages) may tolerate more cores per executor.
- Always validate against your actual workload's Spark UI metrics (task time, GC time, shuffle read/write time) rather than treating 5 as gospel.

```text
HDFS throughput per executor vs concurrent threads (illustrative):

Throughput
   ^
   |        ____------------  (plateaus / contention past ~5)
   |    ___/
   |  _/
   | /
   +---------------------------------> concurrent threads per executor
   1   2   3   4   5   6   7   8

Rule of thumb: executor-cores <= 5 for HDFS-heavy jobs.
Re-validate for object-storage-backed or CPU-bound workloads.
```

---

## 4. Reserving Resources for OS / YARN / NodeManager Daemons

A worker node's cores and RAM aren't 100% available to Spark executors. You must leave headroom for:
- The operating system itself
- The YARN NodeManager daemon (manages containers on that node)
- HDFS DataNode daemon (if co-located, common in on-prem clusters)
- Other cluster agents (monitoring, log shipping, etc.)

Common convention: reserve 1 core and ~1GB RAM per node for these daemons before computing how many executor slots fit. Some shops reserve more (e.g. 1-2 cores, 2GB) if DataNode/NodeManager are memory-hungry, but 1 core / 1GB is the standard baseline assumption in most tuning guides.

Also reserve 1 executor-equivalent of cores/memory on ONE node for the Application Master (AM) in YARN client/cluster mode — the AM negotiates containers and needs its own small allocation (typically 1 core, 1-2GB), separate from your `num-executors` count.

```text
Per node (before Spark gets anything):
  available_cores = node_total_cores - 1   (OS/NodeManager/DataNode)
  available_memory = node_total_memory - 1GB

Additionally, in YARN mode, reserve one small container elsewhere for
the Application Master (~1 core, ~1-2GB) -- it doesn't run your tasks,
it just manages the application's containers.
```

---

## 5. Worked Capacity-Planning Example

Full worked example: given a cluster of N nodes with C cores and M GB RAM each, derive a recommended `--num-executors` / `--executor-cores` / `--executor-memory`, showing every step of arithmetic.

**Simulation:**
```python
def worked_capacity_planning_example(num_nodes, cores_per_node, ram_gb_per_node,
                                      target_cores_per_executor=5,
                                      overhead_fraction=0.07):
    # Step 1: reserve for OS/daemons
    usable_cores_per_node = cores_per_node - 1
    usable_ram_per_node = ram_gb_per_node - 1

    # Step 2: executor-cores from the 5-cores rule
    executor_cores = min(target_cores_per_executor, usable_cores_per_node)
    executors_per_node = usable_cores_per_node // executor_cores

    # Step 3: memory per executor before overhead
    raw_mem_per_executor = usable_ram_per_node / executors_per_node

    # Step 4: account for memoryOverhead (~7%, min 384MB)
    # executor_memory + overhead = raw_mem_per_executor
    # overhead = max(384MB, executor_memory * overhead_fraction)
    # Solve: executor_memory * (1 + overhead_fraction) ~= raw_mem_per_executor
    executor_memory = raw_mem_per_executor / (1 + overhead_fraction)
    overhead_gb = raw_mem_per_executor - executor_memory
    overhead_gb = max(overhead_gb, 0.375)  # ~384MB floor
    executor_memory = raw_mem_per_executor - overhead_gb

    # Step 5: total executors across cluster, minus 1 for AM
    total_executors = executors_per_node * num_nodes
    recommended_executors = total_executors - 1  # reserve one slot for the AM

    return {
        "num_executors": recommended_executors,
        "executor_cores": executor_cores,
        "executor_memory_gb": round(executor_memory, 1),
        "memory_overhead_gb": round(overhead_gb, 1),
    }

worked_capacity_planning_example(num_nodes=10, cores_per_node=16, ram_gb_per_node=64)
```

Walking through the arithmetic for a cluster of **10 nodes x 16 cores x 64GB RAM each**:

```text
Cluster: 10 nodes x 16 cores x 64GB RAM each

Step 1 -- Reserve 1 core + 1GB per node for OS/YARN/NodeManager:
  usable cores/node = 16 - 1 = 15
  usable RAM/node   = 64 - 1 = 63 GB

Step 2 -- Pick executor-cores near the 5-cores-per-executor rule:
  executor-cores = 5
  executors/node = usable_cores_per_node // executor_cores = 15 // 5 = 3

Step 3 -- Split usable RAM across executors on the node:
  raw memory/executor = 63 / 3 = 21.00 GB

Step 4 -- Reserve spark.executor.memoryOverhead (~7%, min 384MB):
  memoryOverhead   ~= 1.37 GB
  executor-memory  = raw - overhead = 21.00 - 1.37 = 19.63 GB

Step 5 -- Total executors across the cluster, minus 1 for the AM:
  total executor slots = 3 * 10 = 30
  reserve 1 for YARN Application Master -> --num-executors = 29

RECOMMENDATION:
  --num-executors 29
  --executor-cores 5
  --executor-memory 19.6g
  --conf spark.executor.memoryOverhead=1.4g
  Total cluster parallelism: 145 concurrent tasks
```

**Output** (the returned summary dict):
```text
{'num_executors': 29, 'executor_cores': 5, 'executor_memory_gb': 19.6, 'memory_overhead_gb': 1.4}
```

---

## 6. Dynamic Allocation

```text
spark.dynamicAllocation.enabled = true
```

Instead of a fixed `--num-executors` for the whole application lifetime, dynamic allocation lets Spark request MORE executors when there's a backlog of pending tasks, and RELEASE idle executors back to the cluster manager when they've been idle past a timeout.

Key configs:
- `spark.dynamicAllocation.enabled = true`
- `spark.dynamicAllocation.minExecutors = 2`
- `spark.dynamicAllocation.maxExecutors = 50`
- `spark.dynamicAllocation.initialExecutors = <minExecutors by default>`
- `spark.dynamicAllocation.executorIdleTimeout = 60s` (release after idle)
- `spark.dynamicAllocation.schedulerBacklogTimeout = 1s` (request more if tasks queue this long)
- `spark.shuffle.service.enabled = true` (required in most setups — lets shuffle data outlive the executor that produced it, since that executor may be reclaimed while a later stage still needs to fetch its shuffle output)

Why it's usually better than fixed sizing for varying workloads:
- Multi-tenant clusters: a job that requests a fixed 50 executors but only needs that much during a heavy join stage wastes resources (and blocks other jobs) during its light read/write phases.
- Ad hoc / notebook workloads have bursty, unpredictable resource needs.
- Fixed sizing forces you to size for PEAK demand for the ENTIRE job duration, even if peak only lasts 10% of the runtime.

When fixed sizing is still preferred:
- Tight SLA batch jobs where you want predictable, reproducible performance and don't want allocation latency (waiting for new executors to spin up) mid-job.
- Clusters without a shuffle service configured.

```python
# spark-submit \
#     --conf spark.dynamicAllocation.enabled=true \
#     --conf spark.dynamicAllocation.minExecutors=2 \
#     --conf spark.dynamicAllocation.maxExecutors=50 \
#     --conf spark.dynamicAllocation.executorIdleTimeout=60s \
#     --conf spark.shuffle.service.enabled=true \
#     my_job.py
```

**Simulation:**

Simulating scaling behavior across a job's phases (a pending-tasks signal driving the target executor count, clamped to `[minExecutors, maxExecutors]`):

```python
phases = [
    ("Startup / small read", 3),
    ("Heavy shuffle join", 40),
    ("Light post-join filter", 8),
    ("Final small aggregation write", 2),
]

current = 2  # minExecutors
for phase, needed in phases:
    target = max(2, min(50, needed))
    direction = "scale UP" if target > current else ("scale DOWN" if target < current else "steady")
    print(f"    Phase: {phase:<32} pending_tasks_signal={needed:<3} "
          f"-> {direction} to {target} executors")
    current = target
```

**Output:**
```text
    Phase: Startup / small read             pending_tasks_signal=3   -> scale UP to 3 executors
    Phase: Heavy shuffle join                pending_tasks_signal=40  -> scale UP to 40 executors
    Phase: Light post-join filter            pending_tasks_signal=8   -> scale DOWN to 8 executors
    Phase: Final small aggregation write     pending_tasks_signal=2   -> scale DOWN to 2 executors
```

---

## 7. Simulation: Recommend a Config from Cluster Specs

A thin wrapper that runs the capacity planner (section 5) and prints a summary card for a given set of cluster specs — the same formula, applied to a different cluster shape to show it generalizes.

**Simulation:**
```python
def simulate_recommendation(num_nodes, cores_per_node, ram_gb_per_node):
    """Runs the capacity planner and prints a summary card."""
    result = worked_capacity_planning_example(num_nodes, cores_per_node, ram_gb_per_node)
    print(f"\n  Summary: {result}")
    return result

simulate_recommendation(num_nodes=6, cores_per_node=32, ram_gb_per_node=128)
```

Tracing the arithmetic for **6 nodes x 32 cores x 128GB RAM each**:

```text
Cluster: 6 nodes x 32 cores x 128GB RAM each

Step 1 -- Reserve 1 core + 1GB per node for OS/YARN/NodeManager:
  usable cores/node = 32 - 1 = 31
  usable RAM/node   = 128 - 1 = 127 GB

Step 2 -- Pick executor-cores near the 5-cores-per-executor rule:
  executor-cores = 5
  executors/node = usable_cores_per_node // executor_cores = 31 // 5 = 6

Step 3 -- Split usable RAM across executors on the node:
  raw memory/executor = 127 / 6 = 21.17 GB

Step 4 -- Reserve spark.executor.memoryOverhead (~7%, min 384MB):
  memoryOverhead   ~= 1.38 GB
  executor-memory  = raw - overhead = 21.17 - 1.38 = 19.78 GB

Step 5 -- Total executors across the cluster, minus 1 for the AM:
  total executor slots = 6 * 6 = 36
  reserve 1 for YARN Application Master -> --num-executors = 35

RECOMMENDATION:
  --num-executors 35
  --executor-cores 5
  --executor-memory 19.8g
  --conf spark.executor.memoryOverhead=1.4g
  Total cluster parallelism: 175 concurrent tasks
```

**Output:**
```text
  Summary: {'num_executors': 35, 'executor_cores': 5, 'executor_memory_gb': 19.8, 'memory_overhead_gb': 1.4}
```

---

## Key Takeaways

- `num-executors`, `executor-cores`, and `executor-memory` interact — tune them together, not independently.
- Fat executors share memory/broadcasts better; thin executors give better I/O parallelism and shorter GC pauses — the sweet spot is usually moderate (commonly ~4-6 cores per executor).
- The "5 cores per executor" rule comes from HDFS client throughput saturating around 5 concurrent threads, not a CPU limit.
- Reserve 1 core + ~1GB per node for OS/YARN/NodeManager daemons, and one small container for the YARN Application Master.
- `spark.executor.memoryOverhead` (~7%, minimum 384MB) must be subtracted from the memory budget per executor — it's off-heap JVM overhead, not extra memory on top of `--executor-memory`.
- Dynamic allocation scales executors up/down with workload, and usually beats fixed sizing for bursty or multi-tenant workloads — but requires the external shuffle service.
- Always validate any sizing formula against real Spark UI metrics (task time, GC time, shuffle read/write) for your actual workload.
