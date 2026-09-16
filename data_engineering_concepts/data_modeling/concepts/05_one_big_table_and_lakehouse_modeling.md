# Concept 05: One Big Table (OBT), Lakehouse Layering, and Modeling for dbt

> **Added — not from a single canonical source.** Kimball's dimensional modeling (concepts 01-04) assumes a warehouse where storage is relatively expensive and joins are relatively cheap. Modern cloud/lakehouse platforms (Snowflake, BigQuery, Databricks) and columnar storage invert that trade-off — storage is cheap, and joins, while still not free, matter less than they did in the 1990s. This file covers the modeling patterns that trade-off produces, and how they map onto a typical dbt project, both increasingly common in mid-level DE interviews.

**Covers:**
- One Big Table (OBT): what it is, why it exists, and its real costs
- Medallion/multi-hop layering (bronze/silver/gold, or staging/intermediate/marts) as the modern packaging for "normalize then denormalize"
- How dbt's layer conventions map directly onto Kimball concepts you already know
- Wide/flattened tables for ML feature pipelines — a close cousin of OBT with a different consumer
- A decision framework: star schema vs. OBT vs. wide ML table

---

## 1. One Big Table (OBT): Pre-Joining Everything

**OBT** takes a fact table and *all* of its dimensions and pre-joins them into a single, wide, heavily denormalized table — no joins needed at query time, at all.

```text
Star schema (query-time joins):              One Big Table (pre-joined at load time):

dim_date                                     fact_sales_obt
   |                                           order_id, order_date, day_of_week, month,
dim_product -- fact_sales -- dim_customer      product_id, product_name, category, brand,
   |                                           customer_id, customer_name, segment, region,
dim_store                                      store_id, store_name, store_type,
                                                quantity, unit_price, line_total
```

Building it is literally the query that reconstructs a denormalized view, materialized instead of run live:

```sql
CREATE TABLE fact_sales_obt AS
SELECT
    f.sale_key, f.invoice_number,
    d.full_date, d.day_of_week, d.month, d.quarter,
    p.product_name, p.category, p.subcategory,
    c.customer_name, c.segment, c.region,
    s.store_name, s.store_type,
    f.quantity_sold, f.unit_price, f.discount_amount, f.line_total
FROM fact_sales f
JOIN dim_date d     ON f.date_key     = d.date_key
JOIN dim_product p  ON f.product_key  = p.product_key
JOIN dim_customer c ON f.customer_key = c.customer_key
JOIN dim_store s     ON f.store_key    = s.store_key;
```

**What it costs:** every dimension attribute is now repeated on every fact row that references it — `customer_name`, `segment`, and `region` are duplicated across every order a customer ever placed, instead of living once in `dim_customer`. If a customer's segment changes, that's now a bulk `UPDATE` (or a full rebuild) across every historical row referencing them, rather than one row in one dimension table — the exact update-anomaly cost that normalization exists to avoid (`concepts/01_normalization.md`), reintroduced deliberately.

**What it buys:** zero joins at query time, which matters enormously for two specific consumers:
1. **BI tools and end users who can't or shouldn't write joins** — a self-service dashboard tool pointed at one flat table is far more approachable than one pointed at a schema with a dozen tables and a join graph.
2. **Feature tables feeding an ML model**, covered in section 4 below, where "one flat row per training example" isn't a nice-to-have, it's the required input shape.

**When OBT is the wrong call:** the moment more than one fact table needs to share the same dimension — a `fact_orders` and a `fact_returns` that both need `dim_customer` to mean exactly the same thing. A star schema centralizes that dimension once, as a conformed dimension (`interview_questions/04_curveballs_tradeoffs.md` covers this in depth); OBT duplicates the dimension's logic separately inside every wide table that needs it, so two OBTs can quietly drift into disagreeing about what "customer segment" means.

---

## 2. Medallion Layering: Bronze / Silver / Gold

Lakehouse platforms formalize a multi-hop pattern for getting from raw data to something query-ready, usually named **bronze → silver → gold** (Databricks' terms; other platforms use different names for the same idea):

```text
BRONZE                    SILVER                        GOLD
Raw, as-landed             Cleaned, conformed,            Business-level aggregates,
source data.                deduplicated, typed.           dimensional models, OBTs.
Append-only, often          Roughly 3NF/normalized          Star schemas, wide tables —
schema-on-read.             shape, validated.               whatever the actual
                                                             consumers need.
```

This is not a new idea competing with normalization and dimensional modeling — it's the **same** normalize-then-denormalize trade-off from `concepts/01_normalization.md`, section 6, repackaged as physical pipeline stages instead of a single-database design choice. Bronze is intentionally messy and unopinionated (you can always re-derive silver/gold from it, which is the whole point of keeping it around). Silver is where 1NF/2NF/3NF-style cleanup happens — deduplication, type enforcement, conformance to a stable natural key. Gold is where Kimball dimensional modeling (or OBT) actually gets applied, and it's typically the *only* layer most analysts and BI tools ever query directly.

---

## 3. Mapping This Onto dbt

A dbt project's folder convention is the medallion pattern's most common concrete implementation, and interviewers who ask "how would you organize this in dbt" are really asking whether you know where dimensional-modeling concepts live inside dbt's layers:

```text
models/
  staging/       <- one model per source table, light cleanup only
                    (renaming, casting, deduplication) — this IS "silver"
                 -- staging models are 1:1 with a source table, materialized
                    as views (cheap, always fresh)

  intermediate/  <- reusable business logic that doesn't belong in a final
                    mart on its own (e.g. "sessionize raw events", "resolve
                    the current SCD Type 2 row per customer")

  marts/         <- THIS is where dim_* and fact_* tables live — "gold"
                    marts/core/dim_customer.sql
                    marts/core/fact_orders.sql
                 -- materialized as tables (or incremental models for
                    large fact tables), because they're queried repeatedly
```

Two dbt-specific patterns worth naming explicitly, because they're common "have you actually used dbt" screening questions:

- **`dbt snapshot`** is dbt's built-in mechanism for implementing **SCD Type 2** against a source that only ever gives you the *current* state (a normal operational table with no history of its own) — dbt periodically diffs the source against the last snapshot and appends new Type 2 rows automatically, so you don't hand-write the expire-then-insert logic from `concepts/04_slowly_changing_dimensions.md` yourself.
- **Incremental models** (`materialized='incremental'`) are how a `fact_*` table in `marts/` stays a transaction fact without a full rebuild on every run — each run inserts only the new rows since the last run (typically filtered by a load timestamp), rather than reprocessing the entire history, which matters once a fact table is large enough that a full rebuild is too slow or too expensive to run on every schedule.

The underlying vocabulary never changes — grain, dimensions, facts, SCD types — only *where* in the pipeline and *in what tool* it gets implemented.

---

## 4. Wide Tables for ML Feature Pipelines

A close cousin of OBT with a different consumer: an ML training pipeline typically wants **one flat row per training example**, with every feature as a column — not a star schema the model has to join itself.

```text
customer_key | total_orders_90d | avg_order_value_90d | days_since_last_order |
              region | segment | is_churned (label)
```

This looks structurally identical to OBT, and the reasoning for building it is the same trade-off (denormalize for the read pattern a specific consumer needs), but the *consumer* is different in a way that matters for design: a BI OBT is read by humans clicking through a dashboard and tolerates some staleness; a feature table is read by a training job that needs **point-in-time correctness** — the feature values as they were *at the time of the labeled event*, not as of today. That's the machine-learning-specific version of the SCD Type 2 "as of" query from `concepts/04_slowly_changing_dimensions.md`: if `avg_order_value_90d` is computed using today's data for a training example labeled six months ago, the model trains on information that wouldn't have been available at prediction time — a subtle and common cause of a model that looks great offline and fails in production (feature leakage). Building a wide feature table correctly generally means it's built from the same Type-2-aware, point-in-time joins as any other historical report, not a live view of current state.

---

## 5. Decision Framework: Star vs. OBT vs. Wide ML Table

```text
Multiple fact tables need to share the same dimension consistently?
  -> Star schema (or snowflake, per concepts/03). Centralize the dimension once.

One dashboard/BI tool needs a single flat, joinless table, and it's fed by
exactly one fact's worth of data?
  -> OBT. Accept the update-cost and redundancy trade-off deliberately.

The consumer is a model training job that needs one row per example with
point-in-time-correct feature values?
  -> Wide ML feature table, built with the same point-in-time discipline
     as any Type-2-aware historical report.
```

None of these replace Kimball dimensional modeling — they're all downstream shapes built *from* a well-modeled gold layer, chosen based on who's actually going to query the result.

---

## Key Takeaways

- OBT pre-joins a fact and all its dimensions into one wide table, trading update cost and storage redundancy for zero-join reads — the right call for a single BI tool/consumer, the wrong call the moment a second fact table needs the same dimension to mean the same thing.
- Bronze/silver/gold (or staging/intermediate/marts) is the lakehouse-native packaging of the same normalize-then-denormalize trade-off from `concepts/01_normalization.md` — it's a pipeline shape, not a competing theory.
- In dbt specifically: staging models are "silver" (light cleanup, 1:1 with sources), marts are "gold" (this is where `dim_*`/`fact_*` actually live), `dbt snapshot` implements SCD Type 2 automatically, and incremental models keep large fact tables from needing a full rebuild every run.
- ML feature tables are structurally an OBT variant, but they need point-in-time-correct values (the training-time analog of a Type 2 "as of" query) — using today's data for a historical label is a common, subtle cause of feature leakage.
- Choose the shape based on who's actually querying the result: multiple facts sharing a dimension → star; one BI tool, one flat read → OBT; a training job needing point-in-time rows → a wide feature table.
