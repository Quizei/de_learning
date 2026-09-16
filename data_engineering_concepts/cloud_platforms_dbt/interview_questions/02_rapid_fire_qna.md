# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design/diagnosis
conversations. This file is the other interview mode: **fast, direct
definitional questions** with no scenario attached — the kind asked in
a phone screen, or dropped mid-conversation to check you actually
understand a term you just used. Answer each one out loud in under 30
seconds before reading the model answer.

Every term used here is demonstrated somewhere in `concepts/` or in
file 1 — the cross-references point back to the concrete moment it
showed up.

---

## Cloud Warehouse Architecture

**Q: What's the one architectural idea that explains why virtual
warehouses, slots, and node clusters all exist?**
> Compute and storage are decoupled — data lives in cheap, durable
> object storage independent of whatever compute is provisioned to
> query it. Every vendor-specific feature (resizing a Snowflake
> warehouse in seconds, BigQuery serving an ad-hoc query with zero
> provisioning) follows from this one split.
> `concepts/01_cloud_data_warehouses.md`, section 1.

**Q: MPP, in one sentence.**
> Massively Parallel Processing: a query is split across many nodes/
> slots/partitions that each scan and aggregate their own slice
> concurrently, and a coordinator combines the partial results — this
> is why query time doesn't scale linearly with data size.
> `concepts/01_cloud_data_warehouses.md`, section 2.

**Q: Why does isolating ETL and analytics workloads onto separate
virtual warehouses matter?**
> They share the same underlying data but never compete for the same
> compute — a heavy nightly load job never slows down a live dashboard,
> because each has its own independently-sized, independently-billed
> compute allocation. `concepts/01_cloud_data_warehouses.md`, section 3.

**Q: What's Snowflake's zero-copy clone, and why is it notable?**
> `CREATE TABLE ... CLONE ... AT(...)` creates a full logical copy of a
> table (or schema/database) that shares underlying storage with the
> original until either side's data diverges — cloning a multi-TB
> production table for dev/test is instant and free at clone time,
> because no bytes are actually copied. `concepts/01_cloud_data_warehouses.md`,
> section 5.

**Q: Time travel vs. fail-safe — what's the difference?**
> Time travel is a user-queryable window (0–90 days depending on
> Snowflake edition) letting you query or restore data as it looked in
> the past. Fail-safe is a further 7-day window *after* time travel
> expires, accessible only by Snowflake support for disaster recovery —
> not something you query directly yourself.

---

## Platform-Specific SQL & Features

**Q: `VARIANT` vs. `STRUCT`/`ARRAY` — what's the modeling difference
between Snowflake's and BigQuery's approach to semi-structured data?**
> Snowflake stores semi-structured data in a single `VARIANT` column,
> queried with colon notation (`data:field::TYPE`) and exploded with
> `LATERAL FLATTEN`. BigQuery makes nested (`STRUCT`) and repeated
> (`ARRAY`) fields first-class parts of the table schema itself,
> queried with dot notation and exploded with `UNNEST`. Snowflake's
> approach is more flexible for genuinely variable/unknown shapes;
> BigQuery's is more efficient when the nested shape is known and
> stable. `concepts/02_snowflake_bigquery_redshift.md`, sections 2–3.

**Q: Redshift `DISTKEY` vs. `SORTKEY` — what does each control?**
> `DISTKEY` (or `DISTSTYLE`) controls which compute node a row is
> physically stored on — choosing the most-joined column co-locates
> matching rows and avoids a network shuffle during that join.
> `SORTKEY` controls the physical row order within each node's blocks —
> choosing the most range-filtered column (almost always a date) lets
> Redshift skip whole blocks during a scan. `concepts/02_snowflake_bigquery_redshift.md`,
> section 5.

**Q: Why doesn't Redshift have a native `MERGE`, and what's the
workaround?**
> Historically and in common configuration, Redshift lacks a native
> upsert statement — the standard workaround is stage the new/changed
> rows, `DELETE` any target rows matching the staged keys, then
> `INSERT` the staged rows. This is exactly the pattern dbt's
> `delete+insert` incremental strategy automates.
> `concepts/02_snowflake_bigquery_redshift.md`, section 5;
> `concepts/03_dbt_fundamentals_and_dag.md`, section 4.

**Q: How does BigQuery partition pruning actually reduce cost?**
> BigQuery bills (in on-demand mode) by bytes scanned. A query filtered
> on the partitioned column (usually a date) skips entire partitions
> outside the filter, so fewer bytes are read and billed for. Wrapping
> the partitioned column in a function before filtering usually defeats
> this — the engine can no longer prove which partitions could match
> without evaluating the function row by row.
> `concepts/02_snowflake_bigquery_redshift.md`, section 4;
> `concepts/05_cost_and_performance_optimization.md`, section 2.

---

## dbt Fundamentals

**Q: What does dbt actually do, in one sentence, and what does it
explicitly *not* do?**
> dbt transforms data that's already been loaded into a warehouse,
> using pure SQL `SELECT` statements — it's the "T" in ELT. It does not
> extract data from source systems and does not load raw data into the
> warehouse; those are separate tools' jobs.
> `concepts/03_dbt_fundamentals_and_dag.md`, section 1.

**Q: How does dbt build its DAG, mechanically?**
> By parsing every model's SQL for `ref()` and `source()` calls, then
> topologically sorting the resulting dependency graph (Kahn's
> algorithm) into an execution order — no one draws the DAG by hand,
> and a cycle causes `dbt run`/`dbt build` to fail before executing any
> model. `concepts/03_dbt_fundamentals_and_dag.md`, section 2.

**Q: `ref()` vs. `source()` — what's the difference?**
> `source()` points at a raw table dbt doesn't manage, declared once in
> a `sources.yml` file (which is also where freshness rules attach).
> `ref()` points at another dbt model, resolved at compile time to that
> model's actual materialized name — using `ref()` instead of a literal
> table name is what lets dbt discover the dependency automatically.
> `concepts/03_dbt_fundamentals_and_dag.md`, section 2.

**Q: Name the four materializations and when to choose each.**
> **View** — not stored, recomputed every query; default for thin
> staging models. **Table** — full rebuild every run; for heavier
> marts queried often. **Incremental** — only new/changed rows
> processed after the first run; for large fact tables where a full
> rebuild is too slow/expensive. **Ephemeral** — never persisted,
> inlined as a CTE wherever it's `ref()`'d; for small, reusable logic
> that doesn't need its own warehouse object — but its SQL is
> duplicated once per downstream reference, so it's a poor choice for
> anything non-trivial that's `ref()`'d many times.
> `concepts/03_dbt_fundamentals_and_dag.md`, section 3.

**Q: What does `is_incremental()` actually evaluate to, and when?**
> It's `true` only when the target table already exists *and*
> `--full-refresh` wasn't passed — i.e., on every run after the first.
> On the very first run (or any `--full-refresh` run), it's `false` and
> the model's full, unfiltered `SELECT` runs, exactly like a `table`
> materialization. `concepts/03_dbt_fundamentals_and_dag.md`, section 4.

**Q: Name the three incremental strategies and the failure mode of
picking the wrong one.**
> `append` (no dedup — only correct for genuinely immutable event
> data), `merge` (upsert on `unique_key` — for warehouses with native
> `MERGE`, when rows can be updated after landing), `delete+insert`
> (delete rows matching the new batch's keys, then insert — for
> warehouses without native `MERGE`, or partition-level reloads).
> Configuring `merge`/`delete+insert` without a correct `unique_key`
> silently degrades to `append`-like duplicate-producing behavior — the
> single most common incremental-model bug.
> `concepts/03_dbt_fundamentals_and_dag.md`, section 4;
> `interview_questions/03_critique_and_debug.md`, Case 1.

**Q: `dbt run` vs. `dbt build` — why is `build` the one that belongs in
CI/CD?**
> `dbt run` only executes models. `dbt build` runs models, tests,
> snapshots, and seeds together in DAG order, so a model that produces
> bad data can be caught by a downstream test in the *same* run before
> it ever reaches a table anyone queries.
> `concepts/03_dbt_fundamentals_and_dag.md`, section 5;
> `concepts/04_dbt_testing_macros_and_project_structure.md`, section 6.

**Q: What's `dbt snapshot`, and how is it different from an
incremental model?**
> `dbt snapshot` specifically implements SCD Type 2 against a source
> that only exposes current state — it diffs the source against the
> last snapshot each run and inserts a new Type 2 row when it detects a
> change. An incremental model is a general materialization strategy
> for any model (usually a large fact table) that processes only new/
> changed rows — it has nothing to do with tracking dimension history
> by itself. `concepts/03_dbt_fundamentals_and_dag.md`, section 5.

---

## dbt Testing, Macros & Structure

**Q: Name the four generic tests dbt ships out of the box.**
> `unique`, `not_null`, `accepted_values` (an allow-list of valid
> values), `relationships` (referential integrity — every value exists
> in the referenced model's column, i.e. no orphan rows).
> `concepts/04_dbt_testing_macros_and_project_structure.md`, section 2.

**Q: Generic test vs. singular test — what's the actual distinction?**
> A generic test is reusable and parameterized via YAML, applied to any
> column via config, no SQL written per instance. A singular test is
> hand-written SQL in its own file, for cross-row/cross-table business
> rules a generic test can't express. Both follow the identical
> convention: the test query returns zero rows on pass, one row per
> failure on fail. `concepts/04_dbt_testing_macros_and_project_structure.md`,
> sections 2–3.

**Q: What's a dbt macro, and what does `dbt_utils` add on top of the
built-in ones?**
> A macro is a Jinja function that expands into SQL at compile time —
> dbt's mechanism for not repeating the same SQL pattern across models.
> `dbt_utils` is the most widely-installed community package, adding
> macros for problems nearly every project hits: `generate_surrogate_key`,
> `date_spine`, `star` (select-all-except), and more.
> `concepts/04_dbt_testing_macros_and_project_structure.md`, section 4.

**Q: What does `dbt source freshness` catch that no schema test can?**
> Data that's technically correct in every row but too *stale* to
> trust — a source table whose most recent load is older than an
> acceptable threshold. A schema test only checks rows that did load;
> it can't detect a silently-stalled upstream extraction job, since
> every row that made it in is perfectly valid.
> `concepts/04_dbt_testing_macros_and_project_structure.md`, section 5.

**Q: Staging, intermediate, marts — one line each on what belongs
where.**
> Staging: 1:1 with a source table, rename/cast/clean only, no joins,
> materialized as views. Intermediate: joins and business logic across
> staging models. Marts: final `fct_*`/`dim_*` tables that BI tools and
> analysts query directly, organized by consuming team or domain.
> `concepts/04_dbt_testing_macros_and_project_structure.md`, section 1.

---

## Cost & Performance

**Q: Name the two axes cloud warehouse cost breaks into, and why does
it matter which one is driving a bill?**
> Bytes scanned (per-TB pricing, e.g. BigQuery on-demand) and idle
> compute time (per-second/per-node billing that accrues whether or not
> a warehouse is doing useful work, e.g. Snowflake credits, Redshift
> node-hours). The fix for one does almost nothing for the other — a
> bytes-scanned problem needs partition pruning/clustering; an idle-
> compute problem needs auto-suspend/right-sizing.
> `concepts/05_cost_and_performance_optimization.md`, section 1.

**Q: What's the single most common way partition pruning silently
fails?**
> Filtering on a derived/wrapped expression of the partitioned column
> (`EXTRACT(YEAR FROM sale_date) = 2024`) instead of the raw column
> directly (`sale_date BETWEEN ... AND ...`) — the engine can't prove
> which partitions could match without evaluating the function against
> every row first. `concepts/05_cost_and_performance_optimization.md`,
> section 2.

**Q: Why does query result caching sometimes silently stop helping?**
> The cache only hits on a byte-for-byte identical query against
> unchanged underlying data. A per-user literal value in a `WHERE`
> clause (instead of a shared, parameterized, or unfiltered query)
> makes every user's query technically different, defeating the cache
> for what looks like "the same dashboard" from the outside.
> `concepts/05_cost_and_performance_optimization.md`, section 4.

**Q: How is a dbt materialization choice also a cost decision, not just
a correctness one?**
> `table` re-scans and recomputes its entire source every single run;
> `incremental` only touches what changed. Flipping a large, frequently
> `ref()`'d fact model from `incremental` to `table` (deliberately or by
> a config mistake) is one of the most common single causes of a sudden
> warehouse-bill spike. `concepts/05_cost_and_performance_optimization.md`,
> section 5.

**Q: Someone asks "the warehouse bill tripled this quarter, what do you
do" — what's the structure of a strong answer, not the content?**
> A decision tree, not a list of tips: (1) which axis moved — bytes
> scanned or compute time; (2) which specific query/warehouse/model is
> responsible, checked from actual query history or dbt run metadata,
> not guessed; (3) what changed recently that correlates with the cost
> inflection point; (4) fix the specific cause; (5) add a monitor so the
> next regression is caught quickly instead of discovered a quarter
> later. `concepts/05_cost_and_performance_optimization.md`, section 6.

---

**Next:** [03 — Critique & Debug](03_critique_and_debug.md)
