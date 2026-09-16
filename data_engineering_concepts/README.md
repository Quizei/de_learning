# Data Engineering Interview Prep

Nine standalone, Markdown-only topic folders built for one goal: walking into a
**mid-level data engineering interview loop** and being ready for every round —
SQL, data modeling, pipeline design, warehousing, orchestration, streaming, the
modern cloud/dbt stack, data quality, and the closing system-design round.

This is a rewrite of the older `data_engineering_cource_claude/` folder in this
repo — that one was 11 `.py`-only "weeks" bundled together; this one splits
each topic into its own strong, self-contained unit with a much heavier
interview-question bank, since that's the actual differentiator for interview
prep. Two topics from the original course aren't repeated here on purpose:
Spark fundamentals and Pandas/Polars/PyArrow already have dedicated homes in
this repo — see [`spark_course/`](../spark_course/) and
[`python_course/`](../python_course/) (its `week_08_apis_databases_sql` and
general Python depth cover the DE-adjacent Python skills). Do those alongside
this one; there's no need to duplicate that ground here.

---

## Folder Structure

Every topic folder below follows the same shape:

```
<topic>/
├── README.md              # what it covers, why it's tested, how to use the folder
├── concepts/*.md           # one file per subtopic: the "why" in prose, an ASCII
│                           #   diagram where one helps, real runnable code
│                           #   (SQLite/Python/SQL/YAML), a worked example with
│                           #   its actual output shown
├── practice/               # exercises.md (predict-the-output drills) and, where
│                           #   relevant, coding_problems.md (timed interview-style
│                           #   coding problems with hidden solutions)
├── interview_questions/    # the differentiator — see below
└── projects/               # one capstone project brief (interface + requirements,
                            #   not a pre-built solution — you build it)
```

`interview_questions/` is a taxonomy, not a grab-bag, borrowed from a format
that already proved itself in this repo's original data-modeling notes:

| File | Question shape |
|---|---|
| `01_worked_scenarios.md` | Full mock-interview walkthroughs — clarifying questions → reasoning → a narrated answer, with the model answer hidden until you've tried it yourself |
| `02_rapid_fire_qna.md` | Fast definitional/conceptual drilling — a phone-screen-speed pass over vocabulary |
| `03_critique_and_debug.md` | "What's wrong with this?" — a flawed design, a wrong number, a bug, given as a plain-English description to diagnose |
| `04_curveballs_tradeoffs.md` | Mid-conversation follow-ups that push on one assumption of whatever you just designed |

Most topics add a **5th (sometimes 6th) file** where an important question
shape didn't fit those four cleanly — e.g. data modeling's whiteboarding/
stakeholder-communication drill, workflow orchestration's on-call incident
triage, or streaming's "does this actually need to be real-time" drill. Check
each topic's own `interview_questions/README.md` for its exact taxonomy.

---

## Topics

| # | Topic | Covers | Flagship? |
|---|---|---|---|
| 1 | [`sql_foundations/`](sql_foundations/) | Joins, subqueries, window functions, CTEs, aggregations, query optimization, reading EXPLAIN plans | |
| 2 | [`data_modeling/`](data_modeling/) | Normalization, dimensional modeling, star/snowflake, SCDs, one-big-table/lakehouse modeling, Data Vault | ⭐ Flagship |
| 3 | [`etl_elt_patterns/`](etl_elt_patterns/) | Extraction, transformation, loading strategies, incremental vs. full, CDC, idempotency & reliability | |
| 4 | [`data_warehousing_lakes/`](data_warehousing_lakes/) | Warehouse architecture, partitioning/bucketing, file & table formats (Parquet/Iceberg/Delta/Hudi), lakehouse, Kimball vs. Inmon vs. Data Vault | |
| 5 | [`workflow_orchestration/`](workflow_orchestration/) | DAG fundamentals, operators/sensors, scheduling, error handling & retries, backfills & catchup | |
| 6 | [`streaming_real_time/`](streaming_real_time/) | Streaming fundamentals, Kafka, windowing & watermarks, event-driven architecture, exactly-once semantics | |
| 7 | [`cloud_platforms_dbt/`](cloud_platforms_dbt/) | Snowflake/BigQuery/Redshift specifics, dbt models/tests/macros/incremental strategies, cost & performance optimization | |
| 8 | [`data_quality_governance/`](data_quality_governance/) | Data quality dimensions, validation frameworks, data contracts, lineage & cataloging, anomaly detection & monitoring | |
| 9 | [`system_design_performance/`](system_design_performance/) | Pipeline architecture, scalability patterns, optimization techniques, capacity planning & cost, full mock system-design interviews | ⭐ Flagship |

**Suggested order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. SQL and data modeling
are the foundation everything else leans on; system design comes last because
it deliberately combines all the others into one interview format.

---

## How to Use This

1. **Per topic:** `concepts/` → `practice/` → `interview_questions/` → `projects/`.
   Read concepts and run every code block yourself — don't just read the
   output, produce it. Practice exercises are hidden-answer format
   (`<details>`/`<summary>`): commit to an answer before expanding.
2. **`interview_questions/01_worked_scenarios.md` is the highest-leverage
   file in every folder** — read it once straight through per topic to see
   the reasoning modeled end to end, then come back and answer its "Now You
   Try" companions yourself before checking the hidden debrief.
3. **Week before an interview:** re-read every topic's
   `02_rapid_fire_qna.md` and `03_critique_and_debug.md` — that's the fast
   review pass across the whole course.
4. **Complements, doesn't replace:** for Spark internals and PySpark
   performance tuning, go to [`spark_course/`](../spark_course/); this
   folder assumes that ground is covered separately.

---

*Built for intermediate-to-mid-level data engineers preparing for interviews.*
