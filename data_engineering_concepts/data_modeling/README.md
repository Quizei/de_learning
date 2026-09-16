# Data Modeling & Schema Design

## Why This Matters

Data modeling is the single most-tested topic in mid-level data
engineering interviews. Every company that runs a warehouse asks some
version of "design a data model for X" — and unlike a lot of interview
trivia, the reasoning it tests (grain, dimensions vs. facts, when to
track history, when a schema shape is the wrong tool) is the same
reasoning you use on the job every time a new reporting requirement
lands on your desk. A bad schema means slow queries, silently wrong
aggregates, and migrations nobody wants to touch; a good one is a
blueprint everything else in the warehouse can build on safely.

This is one of two **flagship topics** in this course (the other is
system design & performance) — it goes deeper than a typical topic here:
more worked scenarios across more industries, more edge cases, and more
"why," not just "what."

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like
  notes, real runnable SQL wherever the topic needs it, an ASCII
  diagram where one helps
- `practice/` — schema-design and query exercises, with the answer
  hidden in a collapsible block so you can quiz yourself
- `interview_questions/` — a five-file, code-free drill covering every
  shape a data modeling interview question tends to take: worked design
  scenarios, rapid-fire definitions, critique-a-broken-schema, curveball
  trade-offs, and whiteboarding/stakeholder-communication mechanics
- `projects/` — one capstone project brief that forces you to
  implement most of the concepts as reusable code, not just recognize
  them

Every `concepts/*.md` file follows the same shape:
1. **Covers** — the bullet list of sub-topics in that file
2. One `##`/`###` section per sub-topic: prose explanation (the "why,"
   not just the "how") → an ASCII diagram where one helps → real,
   runnable SQL (SQLite, no external dependencies) → a worked example
   with its actual output shown in a separate block
3. Ends with a **Key Takeaways** summary

Every SQL block is plain, copy-pasteable SQLite — paste it into a
`python3` shell's `sqlite3` module, or any SQLite client, and it runs
exactly as shown. Nothing needs a real warehouse to follow along.

---

## How to Use This Folder

Work through it in this order:

1. **`concepts/`** (01 → 06) — the implementation vocabulary: what a
   fact table is, what a star schema is, what SCD Type 2 actually does
   to the rows in a table. Read these first; everything else assumes
   this vocabulary.
2. **`practice/exercises.md`** — apply the vocabulary directly:
   normalize a table, design a star schema, implement SCD Type 1/2,
   spot a non-additive measure bug, choose between a bridge table and a
   flattened column. Commit to an answer before expanding each solution.
3. **`interview_questions/`** — the conversation an interviewer actually
   scores, rehearsed end to end: clarifying questions → grain →
   schema → SCD choice → narrated queries → trade-offs, across nine
   industries, plus rapid-fire definitions, critique-the-broken-schema
   cases, curveball follow-ups, and the meta-skills of budgeting a
   live design round and explaining a decision to a non-technical
   stakeholder.
4. **`projects/schema_designer.md`** — a capstone that asks you to build
   a small, reusable tool implementing normalization, star-schema
   construction, and SCD Type 2 as general-purpose code, not one-off
   examples.

---

## Topics Covered

### Concepts

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Normalization | `concepts/01_normalization.md` | "Walk me through 1NF, 2NF, 3NF" / "When do you denormalize?" |
| 2 | Dimensional Modeling | `concepts/02_dimensional_modeling.md` | "What's a fact table vs. a dimension table?" / "What's grain, and why does it matter?" |
| 3 | Star & Snowflake Schema | `concepts/03_star_snowflake_schema.md` | "Star vs. snowflake — when do you actually pick snowflake?" |
| 4 | Slowly Changing Dimensions | `concepts/04_slowly_changing_dimensions.md` | "How do you handle a dimension attribute changing over time?" |
| 5 | One Big Table & Lakehouse Modeling | `concepts/05_one_big_table_and_lakehouse_modeling.md` | "What's OBT, and how does modeling work in a dbt project?" |
| 6 | Data Vault Modeling | `concepts/06_data_vault_modeling.md` | "Kimball vs. Inmon vs. Data Vault — what's the difference?" |

### Interview Questions

`interview_questions/` is a five-file, code-free drill:

1. [Worked Design Scenarios](interview_questions/01_worked_scenarios.md) — nine full "design a data model" walkthroughs (ride-sharing, food delivery, e-commerce, subscription retail, SaaS billing, social media, IoT telemetry, marketing attribution, healthcare) covering every schema-shape pattern from bridge tables to weighted attribution to snowflaked hierarchies
2. [Rapid-Fire Q&A](interview_questions/02_rapid_fire_qna.md) — fast definitional questions, no scenario attached
3. [Critique & Debug](interview_questions/03_critique_and_debug.md) — "what's wrong with this?" / "why is this number wrong?" diagnostic cases
4. [Curveballs & Trade-offs](interview_questions/04_curveballs_tradeoffs.md) — mid-conversation follow-ups: mini-dimensions, conformed dimensions, Data Vault onboarding, partitioning, real-time, testing, the bus matrix, schema evolution
5. [Whiteboarding & Stakeholder Communication](interview_questions/05_whiteboarding_and_stakeholder_communication.md) — budgeting a live design round under time pressure, and explaining a design decision to someone who's never seen a schema diagram

See `interview_questions/README.md` for how to use the set.

---

## Key Mental Models

### 1. Normalization = Eliminate Redundancy; Denormalization = Trade It Back for Speed

```
1NF: Atomic values, no repeating groups
2NF: 1NF + no partial dependencies (all non-key columns depend on the full PK)
3NF: 2NF + no transitive dependencies (non-key columns don't depend on each other)

OLTP (transactional) -> normalize to 3NF, for write consistency
OLAP (analytics)     -> denormalize (star schema, OBT) for read performance
```

### 2. Star Schema = Fast Queries, Easy to Understand

```
        dim_date
           |
dim_product -- fact_sales -- dim_customer
           |
        dim_store
```

### 3. SCD Type 2 = Full History Tracking

```
| customer_id | name    | city     | valid_from | valid_to   | is_current |
|-------------|---------|----------|------------|------------|------------|
| 101         | Alice   | NYC      | 2023-01-01 | 2024-06-15 | false      |
| 101         | Alice   | Chicago  | 2024-06-15 | 9999-12-31 | true       |
```

### 4. The One Question That Decides Type 1 vs. Type 2

```
Was the old value ever actually TRUE, or was it just WRONG?

  Was true at the time (a real move, a real re-categorization) -> Type 2
  Was simply wrong (a typo, a data-entry error)                -> Type 1
```

---

## Practice Goals

- [ ] Normalize a denormalized table through 3NF, identifying each anomaly it fixes
- [ ] Design a star schema for a given business scenario, stating the grain first
- [ ] Implement SCD Type 1, Type 2, and a hybrid dimension in SQL
- [ ] Identify fact vs. dimension tables, and additive/semi-additive/non-additive measures, in a real-world scenario
- [ ] Design a bridge table for a many-to-many relationship, and state its query consequence out loud
- [ ] Explain trade-offs between star, snowflake, and One Big Table for a given consumer
- [ ] Run a full "design a data model for X" conversation end to end, narrating queries against your own schema without writing SQL
- [ ] Explain a data modeling decision (SCD Type 2, a bridge table, a conformed dimension) to a non-technical stakeholder in under 60 seconds

---

## Prerequisites

None. Every concept file is self-contained Markdown with runnable SQLite
code blocks — no warehouse, no Spark cluster, no external service
required. If you want to run the SQL yourself: any `python3` with the
standard-library `sqlite3` module works, or paste the statements into
any SQLite client.
