# Data Warehousing & Data Lakes

## Why This Matters

Warehouses and lakes are where all the data physically lives, and
almost every mid-level data engineering interview eventually asks
something that lives in this folder: "Parquet or Avro, and why," "walk
me through how you'd partition this table," "warehouse, lake, or
lakehouse for this company," or "here's a slow query — what's wrong
with the physical layout." Unlike data-modeling questions, which test
whether you can shape a schema, these questions test whether you
understand what happens physically when a query runs — how many bytes
actually get read off disk, and why.

The reasoning here is also exactly what you use on the job the first
time a warehouse bill spikes, a dashboard slows down for no obvious
reason, or a team proposes migrating to a lakehouse and someone has to
say whether that's actually warranted. A good storage layout is
invisible — queries are just fast and cheap. A bad one means scanning
10x more data than necessary, millions of tiny files nobody remembers
creating, and a bill nobody can explain.

**Relationship to `spark_course/`:** this folder and `spark_course/`
cover two different angles of the same underlying topics, and each
deliberately avoids duplicating the other. `spark_course/concepts/15_file_formats_columnar_storage.md`
covers file formats and partitioning from the **execution-engine
internals** angle — Parquet's row-group/column-chunk/page structure,
predicate pushdown mechanics, `spark.sql.files.maxPartitionBytes`, how
Spark's own task scheduling reacts to file count. This folder's
`concepts/02_partitioning_and_bucketing.md` and
`concepts/03_file_and_table_formats.md` cover the same physical
building blocks from the **storage-architecture** angle — how you lay
data out on object storage in the first place, which table format
solves which reliability problem, and how to choose a partition/bucket
scheme for a given workload. If a concept file here cross-references
`spark_course/concepts/15`, that's deliberate — read both when you want
the full picture, but expect each to go deep on its own angle rather
than repeat the other's.

**Relationship to `data_modeling/`:** that folder is about *shaping* a
schema (grain, star vs. snowflake, SCDs); this folder is about
*physically storing and organizing* whatever schema you've designed
(partitioning, file format, table format, lake zones). `data_modeling/`
is listed as a helpful prerequisite below for exactly this reason — the
mini star-schema build in `concepts/01_warehouse_architecture.md` and
the ETL/OLAP capstone in `projects/warehouse_simulator.md` both assume
the fact/dimension vocabulary that folder builds.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like
  notes, real runnable Python/SQLite wherever the topic needs it, an
  ASCII diagram where one helps.
- `practice/` — `exercises.md` (design/classification/calculation
  drills with the answer hidden in a collapsible block) and
  `coding_problems.md` (a data partitioner, a hash join, and a mini
  data warehouse — full problem statement, sample I/O, and a hidden
  solution with explanation).
- `interview_questions/` — a five-file, code-free drill covering every
  shape a warehousing/lake interview question tends to take: worked
  storage-design scenarios, rapid-fire definitions, critique-a-broken-
  layout, curveball trade-offs, and a dedicated lakehouse table-format
  drill.
- `projects/` — one capstone project brief (`warehouse_simulator.md`)
  that forces you to implement star-schema construction, partition
  pruning, and the medallion pipeline as reusable, measurable code.

Every `concepts/*.md` file follows the same shape: a **Covers** list,
one `##`/`###` section per sub-topic with a prose "why," an ASCII
diagram where one helps, real runnable code, and a worked example with
its actual output shown — ending in **Key Takeaways**. Code blocks run
against Python's standard library (plus `sqlite3`) — nothing needs a
real cluster, cloud account, or `pyarrow`/`delta-spark` install to
follow along; where the concept is genuinely about a real
library/engine (Parquet metadata, Spark's `explain()` output, Delta's
transaction log), the code simulates its shape in plain Python and says
so explicitly.

---

## How to Use This Folder

Work through it in this order:

1. **`concepts/`** (01 → 05) — the physical vocabulary: OLTP vs. OLAP
   and MPP, partitioning and bucketing, file and table formats, lake
   zones and lakehouse architecture, and Kimball/Inmon/Data Vault as an
   *architectural* (not modeling) choice. Read these first; everything
   else assumes this vocabulary.
2. **`practice/exercises.md`** — apply the vocabulary directly:
   classify workloads, design a partition strategy, choose a file
   format, diagnose a data swamp, calculate a partition-pruning or
   small-file cost. Commit to an answer before expanding each solution.
3. **`practice/coding_problems.md`** — implement the mechanisms
   underneath the vocabulary: a date-based partitioner, a hash join,
   and a full mini warehouse (schema + ETL + OLAP queries).
4. **`interview_questions/`** — the conversation an interviewer
   actually scores, rehearsed end to end: clarifying questions →
   storage layout → format/table-format choice → trade-offs, across
   four full scenarios, plus rapid-fire definitions, critique-the-
   broken-layout cases, curveball follow-ups, and a dedicated Iceberg/
   Delta/Hudi trade-off drill.
5. **`projects/warehouse_simulator.md`** — a capstone that asks you to
   build a small, measurable tool implementing star-schema
   construction, partition-pruning comparison, and the medallion
   pipeline as general-purpose code, not one-off examples.

---

## Topics Covered

### Concepts

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Warehouse Architecture | `concepts/01_warehouse_architecture.md` | "OLTP vs. OLAP?" / "How does an MPP warehouse actually run a query?" |
| 2 | Partitioning & Bucketing | `concepts/02_partitioning_and_bucketing.md` | "Design a partition strategy for this table" / "Partitioning vs. bucketing — what's the difference?" |
| 3 | File & Table Formats | `concepts/03_file_and_table_formats.md` | "Parquet vs. Avro — when do you use each?" / "Iceberg vs. Delta Lake vs. Hudi?" |
| 4 | Data Lake & Lakehouse Architecture | `concepts/04_data_lake_and_lakehouse_architecture.md` | "What's a lakehouse?" / "Warehouse, lake, or lakehouse for this company?" |
| 5 | Kimball vs. Inmon vs. Data Vault (Architecture) | `concepts/05_kimball_inmon_data_vault_architecture.md` | "Kimball vs. Inmon vs. Data Vault — as an organizational choice, not a schema" |

### Interview Questions

`interview_questions/` is a five-file, code-free drill:

1. [Worked Scenarios](interview_questions/01_worked_scenarios.md) —
   four full walkthroughs: a multi-TB clickstream lake storage design,
   a warehouse-vs-lakehouse decision for a mid-size company, live
   diagnosis of a slow query from its physical layout, and a multi-year
   IoT retention/table-format design
2. [Rapid-Fire Q&A](interview_questions/02_rapid_fire_qna.md) — fast
   definitional questions, no scenario attached
3. [Critique & Debug](interview_questions/03_critique_and_debug.md) —
   classic warehousing bugs: over-partitioning, partitioning on the
   wrong column, bucketing chosen for the wrong join, a lakehouse table
   that's still a small-file mess
4. [Curveballs & Trade-offs](interview_questions/04_curveballs_tradeoffs.md)
   — mid-conversation follow-ups: bucketing-column choice, a costly
   repartition, storage-cost triage, real-time, Data Vault onboarding
5. [Lakehouse Table Format Trade-offs](interview_questions/05_lakehouse_table_format_tradeoffs.md)
   — a dedicated Iceberg/Delta Lake/Hudi drill, requirement by
   requirement

See `interview_questions/README.md` for how to use the set.

---

## Key Mental Models

### 1. Warehouse vs. Lake vs. Lakehouse

```
Data Warehouse:  structured, schema-on-write, fast queries, higher storage cost
Data Lake:       any format, schema-on-read, cheap storage, no built-in guarantees
Lakehouse:       lake storage cost + warehouse reliability (ACID, schema, time travel)
                 via a table format (Iceberg/Delta Lake/Hudi) layered on open files
```

### 2. Partitioning Skips Directories; Bucketing Avoids Shuffles

```
Table: events/
├── year=2024/
│   ├── month=01/
│   │   ├── day=01/  <- query only reads this partition
│   │   └── day=02/
│   └── month=02/
└── year=2023/        <- entire year skipped by pruning

Bucketing (within a partition): hash rows by a join key into N buckets
so a join only ever compares matching buckets -- no shuffle needed.
```

### 3. File Format Selection

```
Parquet:  Columnar -- great for analytics (SELECT few columns from many)
Avro:     Row-based -- great for streaming ingestion and schema evolution
ORC:      Columnar, Hive-optimized -- similar benefits to Parquet
CSV/JSON: Simple/flexible -- fine for exchange, bad for analytics at scale
```

### 4. A Table Format Adds What Files Alone Can't

```
Plain Parquet files:    no atomicity, no enforced schema, no safe
                        UPDATE/DELETE, no history
+ Iceberg/Delta/Hudi:   atomic commits (versioned manifest/log),
                        schema evolution, MERGE/UPDATE/DELETE, time travel
```

### 5. Small Files Are Expensive Regardless of Format

```
1 GB as 8 files (~128 MB each):    8 read tasks, overhead negligible
1 GB as 2,000 files (~500 KB each): 2,000 read tasks, overhead dominates
```

---

## Practice Goals

- [ ] Explain OLTP vs. OLAP and MPP query execution well enough to
      justify why a warehouse's schema and physical layout look the
      way they do
- [ ] Design a partition and bucketing strategy for a given dataset and
      query pattern, and calculate the expected partition size
- [ ] Choose a file format (CSV/JSON/Avro/Parquet/ORC) and a table
      format (Iceberg/Delta Lake/Hudi) for a given workload, with the
      reasoning tied to the actual requirement, not a feature checklist
- [ ] Diagnose a slow query from its physical layout: confirm whether
      partition pruning is happening, check partition/file sizing,
      before assuming it's a compute-tuning problem
- [ ] Explain the bronze/silver/gold medallion architecture and what
      turns an ungoverned lake into a data swamp
- [ ] Argue for Kimball, Inmon, or Data Vault as an organizational
      choice, tied to team size, timeline, and number of disagreeing
      source systems — not a memorized preference
- [ ] Solve all 13 practice exercises and all 3 coding problems without
      looking at the hidden solutions first
- [ ] Complete the `WarehouseSimulator` capstone, including the
      partition-pruning and file-format comparisons

---

## Prerequisites

None strictly required — every concept file is self-contained Markdown
with runnable Python/SQLite code, no warehouse, Spark cluster, or cloud
account needed. `data_modeling/` (fact/dimension vocabulary, star
schemas) is genuinely helpful background for
`concepts/01_warehouse_architecture.md`'s mini warehouse build and the
`projects/warehouse_simulator.md` capstone, but this folder introduces
what it needs as it goes.
