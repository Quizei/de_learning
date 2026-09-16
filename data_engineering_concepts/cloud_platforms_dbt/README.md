# Cloud Platforms & dbt

## Why This Matters

Almost every mid-level data engineering job posting names two things
explicitly: a cloud warehouse (Snowflake, BigQuery, or Redshift) and
dbt. dbt in particular has become one of the few tools interviewers ask
about *by name*, often before they've even asked which warehouse you've
used — "have you used dbt," "walk me through a dbt project you built,"
"what's your incremental strategy" show up constantly, because dbt has
become the default way SQL-based transformation actually gets written,
tested, and shipped in a modern data team.

This folder is about the two things together: the platform-specific
features and SQL dialect of the three big warehouses, and dbt as the
transformation layer that sits on top of all three. It deliberately
does **not** re-cover general warehouse architecture, table formats, or
lakehouse concepts — those live in `data_warehousing_lakes/`, and this
folder cross-references that material rather than duplicating it. What
this folder covers instead: Snowflake's `VARIANT`/`FLATTEN`/streams,
BigQuery's `STRUCT`/`ARRAY`/partitioning-and-clustering, Redshift's
`DISTKEY`/`SORTKEY`, the credits/slots/node-hours pricing models each
platform bills on — and, at real depth, dbt's DAG, materializations,
incremental strategies, testing, and project structure.

---

## Prerequisites

- **Required:** `sql_foundations` — every concept and exercise here
  assumes comfortable SQL (joins, aggregation, window functions) and
  doesn't re-teach it.
- **Helpful:** `data_warehousing_lakes` — this folder assumes the
  underlying storage-architecture vocabulary (partitioning, file/table
  formats, OLTP vs. OLAP, medallion architecture) as background and
  builds the platform-specific and dbt-specific layer on top of it.
  Where a concept file here would otherwise re-explain that ground, it
  links to the corresponding `data_warehousing_lakes/concepts/*.md`
  file instead.
- **Helpful:** `data_modeling` — dbt marts are exactly the `fct_*`/
  `dim_*` vocabulary from that folder; this folder assumes it rather
  than re-deriving grain, star schemas, or SCDs from scratch.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like
  notes, real runnable Python/SQLite wherever the topic needs a working
  simulation, real dbt SQL/YAML wherever the topic is dbt-native (dbt
  itself isn't installed — the SQL/YAML shown is exactly what a real
  project would contain), and an ASCII diagram where one helps.
- `practice/` — `exercises.md`: platform-selection, SQL-dialect,
  staging/intermediate/mart model design, testing, incremental-model,
  and cost-diagnosis drills, with the answer hidden in a collapsible
  block. No `coding_problems.md` in this folder — the practice format
  here is modeling/configuration decisions and dbt SQL/YAML, not
  from-scratch data-structure implementation.
- `interview_questions/` — a five-file, code-free drill covering every
  shape a cloud-platform-or-dbt interview question tends to take:
  worked design/diagnosis scenarios, rapid-fire definitions,
  critique-a-broken-model-or-config, curveball trade-offs, and a
  dedicated project-structure-and-testing-strategy drill.
- `projects/` — one capstone brief (`dbt_project_simulator.md`) that
  specifies a small, realistic dbt project (staging → intermediate →
  marts, generic + singular tests, one genuinely incremental model) for
  you to actually build, in a real dbt project if you have one set up.

Every `concepts/*.md` file follows the same shape: a **Covers** list,
one `##`/`###` section per sub-topic with a prose "why," an ASCII
diagram where one helps, real runnable code or real dbt SQL/YAML, and a
worked example with its actual output shown — ending in **Key
Takeaways**.

---

## How to Use This Folder

Work through it in this order:

1. **`concepts/`** (01 → 05) — the platform and dbt vocabulary: cloud
   warehouse architecture, Snowflake/BigQuery/Redshift specifics, dbt's
   DAG and materializations, dbt testing/macros/project structure, and
   cost/performance optimization. Read these first; everything else
   assumes this vocabulary.
2. **`practice/exercises.md`** — apply it directly: choose a platform
   for a use case, fix a query defeating partition pruning, write
   staging/intermediate/mart models, write generic and singular tests,
   diagnose a broken incremental model and a slow nightly run. Commit
   to an answer before expanding each solution.
3. **`interview_questions/`** — the conversation an interviewer
   actually scores, rehearsed end to end: structuring a real dbt
   project, choosing between warehouses for a specific workload,
   diagnosing a slow/expensive run, plus rapid-fire definitions,
   critique-the-broken-model/config cases, curveball follow-ups, and a
   dedicated project-structure-and-testing drill.
4. **`projects/dbt_project_simulator.md`** — a capstone that asks you
   to build a small, complete dbt project (or reason through it fully
   on paper) implementing everything above as one coherent thing, not
   isolated examples.

---

## Topics Covered

### Concepts

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Cloud Data Warehouse Architecture | `concepts/01_cloud_data_warehouses.md` | "Compare Snowflake, BigQuery, and Redshift" / "What's a virtual warehouse?" |
| 2 | Snowflake, BigQuery & Redshift Deep Dive | `concepts/02_snowflake_bigquery_redshift.md` | "How do you query semi-structured data in Snowflake vs. BigQuery?" / "DISTKEY vs. SORTKEY?" |
| 3 | dbt Fundamentals & the DAG | `concepts/03_dbt_fundamentals_and_dag.md` | "What is dbt?" / "Explain dbt materializations" / "How do incremental models work?" |
| 4 | dbt Testing, Macros & Project Structure | `concepts/04_dbt_testing_macros_and_project_structure.md` | "How do you test data transformations in dbt?" / "Design a dbt project structure" |
| 5 | Cost & Performance Optimization | `concepts/05_cost_and_performance_optimization.md` | "The warehouse bill is too high — what do you do?" |

### Interview Questions

`interview_questions/` is a five-file, code-free drill:

1. [Worked Scenarios](interview_questions/01_worked_scenarios.md) —
   structuring a dbt project for a real company (plus a "Now You Try"),
   choosing between Snowflake and BigQuery for a specific workload, and
   diagnosing a slow, expensive nightly `dbt build`
2. [Rapid-Fire Q&A](interview_questions/02_rapid_fire_qna.md) — fast
   definitional questions, no scenario attached
3. [Critique & Debug](interview_questions/03_critique_and_debug.md) —
   classic bugs: a `merge` strategy with no `unique_key`, a missing
   `is_incremental()` guard, unconfigured auto-suspend, a Redshift sort
   key chosen for the wrong query, tests passing while data goes stale,
   an ephemeral model multiplying its own cost
4. [Curveballs & Trade-offs](interview_questions/04_curveballs_tradeoffs.md)
   — environments/targets, schema drift, backfills vs. incremental
   watermarks, CI cost, PII handling, dbt Cloud vs. Core, cross-
   warehouse joins
5. [dbt Project Structure & Testing Strategy](interview_questions/05_dbt_project_structure_and_testing.md)
   — a dedicated drill on the single most common practical dbt
   question

See `interview_questions/README.md` for how to use the set.

---

## Key Mental Models

### 1. Compute/Storage Separation Explains (Almost) Everything

```
Snowflake:  credits, virtual warehouses, time travel, zero-copy clone
BigQuery:   slots, serverless, per-byte-scanned pricing, partition pruning
Redshift:   node-hours, DISTKEY/SORTKEY, Spectrum over S3
```

### 2. dbt = SQL Transformations as Code, ELT's "T"

```
E (extract) -> L (load) -> T (transform, dbt's entire job)

models/
├── staging/          <- 1:1 with source tables (clean, rename), views
│   ├── stg_orders.sql
│   └── stg_customers.sql
├── intermediate/      <- business logic joins, tables/ephemeral
│   └── int_orders_enriched.sql
└── marts/             <- final fct_*/dim_* tables, tables/incremental
    ├── fct_orders.sql
    └── dim_customers.sql
```

### 3. dbt Materializations

```
View:         CREATE VIEW           -- lightweight, always fresh, recomputed every query
Table:        CREATE TABLE AS       -- fast to query, full rebuild every run
Incremental:  INSERT/MERGE new rows -- only new/changed rows processed after run 1
Ephemeral:    CTE, never persisted  -- inlined once per ref(); no cost if reused rarely
```

### 4. Two Cost Axes, Two Different Fixes

```
Bytes scanned (BigQuery on-demand):   fix = partition pruning, clustering, column pruning
Idle compute time (Snowflake credits, fix = AUTO_SUSPEND, right-sizing, result caching
Redshift node-hours):
```

---

## Practice Goals

- [ ] Compare Snowflake, BigQuery, and Redshift by pricing model,
      isolation model, and platform-native SQL, and justify a platform
      choice against a specific company's workload rather than a
      feature checklist
- [ ] Explain and simulate MPP, time travel, zero-copy clone, and
      result caching well enough to answer "why is this feature there"
- [ ] Write correct staging, intermediate, and mart dbt models
      following the standard layer conventions
- [ ] Explain all four dbt materializations and choose correctly among
      them for a given model's size, reuse, and freshness needs
- [ ] Configure a correct incremental model — `is_incremental()`,
      `unique_key`, and the right incremental strategy — and diagnose
      one that's silently producing duplicates or not actually
      incremental
- [ ] Write generic and singular dbt tests, and explain what source
      freshness checks catch that no test can
- [ ] Diagnose a warehouse cost spike or a slow query from its physical
      layout (partitioning, clustering, sort keys) before assuming it's
      a compute-sizing problem
- [ ] Structure a complete dbt project for a multi-source company and
      defend the folder/layer/materialization choices out loud
- [ ] Complete the `dbt_project_simulator.md` capstone, including at
      least one genuinely incremental, correctly-tested model

---

## A Note on Scope

`data_warehousing_lakes/` already covers Iceberg/Delta Lake/Hudi table
formats, the medallion (bronze/silver/gold) lakehouse architecture, and
Snowflake/BigQuery-style MPP query execution in real depth — this
folder does not re-teach any of that. Where this folder needs that
vocabulary (e.g. dbt's staging/marts layers mapping to silver/gold), it
links to the specific `data_warehousing_lakes/concepts/*.md` section
rather than repeating it. Read that folder's `concepts/03_file_and_table_formats.md`
and `concepts/04_data_lake_and_lakehouse_architecture.md` first if
those terms are unfamiliar.
