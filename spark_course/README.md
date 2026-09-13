# Spark Performance & Internals Course

## Source

Based on the topic list of **"Afaque Ahmad"**'s Spark YouTube playlist
(playlist ID `PLWAuYt0wgRcLCtWzUxNg4BjnYlCZNEVth`, starting video *"Master Reading
Spark Query Plans"*) and its companion repo,
[`afaqueahmad7117/spark-experiments`](https://github.com/afaqueahmad7117/spark-experiments)
— "the ultimate guide for mastering Spark Performance Tuning and Optimization,
for Data Engineering interviews." Afaque Ahmad is a Solutions Architect at Databricks.

> **Note on provenance:** YouTube blocks transcript scraping, so this folder is
> **not** a transcript of the videos. It's original explanation + runnable code
> written from the same 13-topic outline the playlist and repo advertise, plus
> 6 extra topics (marked below) that a senior DE should know but that this
> particular playlist doesn't cover. Treat this as study notes *inspired by*
> the playlist, not a copy of it — watch the actual videos for Afaque's
> walkthroughs of real Spark UI screenshots and query plans.

This is the **advanced / performance-tuning** Spark track. If you want
fundamentals first (architecture, RDDs, basic DataFrame ops, basic joins),
do [`data_engineering_cource_claude/week_05_spark_pyspark`](../data_engineering_cource_claude/week_05_spark_pyspark)
before this one.

---

## Why This Matters

Anyone can write a PySpark job that works on a laptop with 1,000 rows. The
interview bar (and the on-call bar) is: **can you explain why a job that
should take 2 minutes is taking 2 hours, and fix it?** That's entirely a
question of internals — query plans, shuffle, partitioning, skew, memory,
and executor sizing. This folder is about that.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like notes,
  code blocks inline wherever the topic needs a diagram or a snippet
- `practice/` — tuning scenarios and "diagnose this slow job" exercises,
  with the answer hidden in a collapsible block so you can quiz yourself
- `projects/` — one end-to-end capstone that forces you to apply most topics

Every `concepts/*.md` file follows the same shape:
1. **Covers** — the bullet list of sub-topics in that file
2. One `##` section per sub-topic: prose explanation (the "why", not just the
   "how") → an ASCII diagram where one helps → the real PySpark API/config →
   a worked example with its actual output shown in a separate code block
3. Ends with a **Key Takeaways** summary

Every code block is plain Markdown — copy-paste it into a `python3` shell with
`pyspark` installed and it runs (`pip install pyspark`, Java 8/11/17 required).
Nothing needs a real cluster to *follow along*; the worked examples are traced
by hand so the shown output is exactly what you'd see.

Start with `concepts/00_pyspark_basics_and_syntax.md` if `select`/`filter`/
`join`/`groupBy`/renaming a column aren't already muscle memory — everything
from 01 onward assumes that vocabulary and jumps straight into internals.

---

## Topics Covered

### Prerequisite — added, not from the playlist

| # | Topic | File | Why it's here |
|---|-------|------|----------------|
| 0 | PySpark Basics & Syntax | `concepts/00_pyspark_basics_and_syntax.md` | Starting a session, `select`/`filter`/`join`/`groupBy`/rename, nulls, writing data, SQL, a pandas cheat-sheet. Everything else in this course assumes this vocabulary and never explains it. |

### From the playlist (in the order the repo lists them)

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Spark Core Concepts (foundations) | `concepts/01_spark_core_concepts.md` | "Walk me through what happens when you run a Spark job." |
| 2 | Spark Query Plans | `concepts/02_query_plans_and_explain.md` | "How do you read `explain()` output?" |
| 3 | Spark DAGs | `concepts/03_dag_and_execution.md` | "What's the difference between a job, a stage, and a task?" |
| 4 | Caching | `concepts/04_caching_and_persistence.md` | "When would `.cache()` make a job slower?" |
| 5 | Data Partitioning | `concepts/05_data_partitioning.md` | "repartition vs coalesce — when do you use each?" |
| 6 | Bucketing | `concepts/06_bucketing.md` | "How do you avoid a shuffle on a repeated join?" |
| 7 | Data Skew | `concepts/07_data_skew.md` | "One task runs 100x longer than the rest — why?" |
| 8 | Salting | `concepts/08_salting.md` | "How do you fix a skewed join key?" |
| 9 | AQE & Broadcast Joins | `concepts/09_aqe_and_broadcast_joins.md` | "What does Adaptive Query Execution actually change at runtime?" |
| 10 | Dynamic Partition Pruning | `concepts/10_dynamic_partition_pruning.md` | "How does Spark avoid scanning a whole partitioned table on a join?" |
| 11 | Spark Memory Management | `concepts/11_memory_management.md` | "Explain unified memory / execution vs storage memory." |
| 12 | Spark Executor Tuning | `concepts/12_executor_tuning.md` | "How many executors / cores / memory would you give this job?" |
| 13 | Shuffle Partitions | `concepts/13_shuffle_partitions.md` | "Why is `spark.sql.shuffle.partitions=200` a bad default?" |

### Added — what the playlist doesn't cover, but you need

A performance-tuning playlist assumes you already know these; a "senior DE
interview" doesn't assume that. Added for completeness:

| # | Topic | File | Why it's here |
|---|-------|------|----------------|
| 14 | Join Strategies Deep Dive | `concepts/14_join_strategies.md` | The playlist mentions broadcast joins but not the full decision tree (BHJ vs SMJ vs SHJ vs cartesian) or how to force one with hints. |
| 15 | File Formats & Columnar Storage | `concepts/15_file_formats_columnar_storage.md` | Parquet/ORC internals, predicate & projection pushdown, the small-file problem — the #1 real-world perf killer, never mentioned in tuning talks that assume good input files. |
| 16 | Window Functions | `concepts/16_window_functions.md` | Extremely common in interviews and production SQL, but tuning-focused content skips it entirely. |
| 17 | Structured Streaming Basics | `concepts/17_structured_streaming_basics.md` | The playlist is 100% batch. Watermarks, triggers, checkpointing, and micro-batch vs continuous are core Spark knowledge. |
| 18 | Delta Lake / Lakehouse Concepts | `concepts/18_delta_lake_lakehouse.md` | Most production Spark today runs on a lakehouse (Delta/Iceberg/Hudi) — ACID, time travel, `MERGE`, Z-ordering. Pure-OSS-Spark tuning content usually skips the table format layer. |
| 19 | Testing & Debugging PySpark Jobs | `concepts/19_pyspark_testing_and_debugging.md` | Nobody in a tuning-focused playlist covers *how to unit-test a transformation* or *how to read a `java.lang.OutOfMemoryError` stack* — both come up constantly in real jobs. |

---

## Key Mental Models

### 1. The Four Plans Behind Every `explain()`

```
SQL / DataFrame code
      |
      v
Parsed Logical Plan      <- syntax check only, unresolved column/table names
      |
      v
Analyzed Logical Plan    <- names resolved against the catalog/schema
      |
      v
Optimized Logical Plan   <- Catalyst rules: predicate pushdown, constant
      |                     folding, column pruning
      v
Physical Plan(s)         <- one or more candidate execution strategies,
      |                     costed, cheapest one selected
      v
   RDDs / Tasks           <- what actually runs on executors
```

### 2. Where Time Actually Goes

```
Slow Spark job?  Check in this order:
  1. Data skew          -> one partition way bigger than others
  2. Too much shuffle    -> wide transforms, bad join strategy, too many
                            shuffle partitions for the data size
  3. Small files         -> thousands of tiny tasks, scheduling overhead
  4. Spill to disk       -> not enough executor memory for the partition size
  5. Serialization       -> UDFs / Python overhead instead of native
                            functions or Pandas UDFs (Arrow)
```

### 3. Executor Sizing Cheat Sheet

```
Total cluster cores = num_executors x executor_cores
Rule of thumb:        executor_cores <= 5   (HDFS throughput saturates above ~5)
                       leave 1 core + ~1GB per node for the OS/YARN daemon
                       executor_memory: split between execution + storage
                       (unified memory, controlled by spark.memory.fraction)
```

---

## Practice Goals

- [ ] Read a physical plan and identify the join strategy Spark chose, and why
- [ ] Reproduce a data-skew scenario and fix it with salting
- [ ] Explain, with numbers, why `spark.sql.shuffle.partitions` shouldn't stay at 200 for a 10GB or a 10TB job
- [ ] Design bucketing for two tables that are joined repeatedly on the same key
- [ ] Size executors (cores/memory/count) for a given cluster + workload
- [ ] Diagnose an OOM from a stack trace and know which config to change first
- [ ] Write a unit test for a PySpark transformation without spinning up a real cluster job

---

## Prerequisites

None strictly required to *read* the files — they're Markdown, open them in
any editor/viewer. To run the code blocks yourself: `pip install pyspark`
(Java 8/11/17 required). If `select`/`filter`/`join`/`groupBy` aren't already
familiar, start at `concepts/00_pyspark_basics_and_syntax.md`.
