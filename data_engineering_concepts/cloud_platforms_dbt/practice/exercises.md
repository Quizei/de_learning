# Cloud Platforms & dbt — Practice Exercises

Twelve exercises covering platform selection and SQL dialect (1–3), dbt staging/intermediate/mart model design (4–6), dbt testing strategy (7–8), incremental models and project structure (9–10), and cost/performance diagnosis (11–12).

How to use this file: read the exercise, write down your own answer — genuinely commit to one before looking — and only then expand the reference solution. Solutions include real, runnable SQLite where the exercise is testable code, and real dbt SQL/YAML where the exercise is a modeling or configuration decision (dbt itself isn't installed here — the SQL/YAML is exactly what a real project would contain).

---

## Exercise 1: Choose the Right Cloud Platform

For each use case, decide which platform — Snowflake, BigQuery, or Redshift — is the best fit and state why.

1. A startup already on GCP needs ad-hoc analytics with no dedicated data team to manage infrastructure, and wants to pay only for queries actually run.
2. An enterprise needs to securely share live data with several external partners without exporting or copying it.
3. A heavy AWS shop has years of data already in S3 and runs complex, scheduled ETL jobs.
4. A company needs fully isolated compute for ETL, BI, and a data science team, so a heavy ETL job never slows down an executive's dashboard.
5. A team wants zero cluster or node management of any kind, with automatic scaling to any query size.

<details>
<summary>Reference answer</summary>

1. **BigQuery** — GCP-native, serverless, on-demand (pay-per-byte-scanned) pricing needs no dedicated infrastructure team and fits ad-hoc, spiky usage well.
2. **Snowflake** — secure data sharing (Snowflake Marketplace / secure shares) is a first-class, mature feature; partners query shared data directly without a copy ever leaving the provider's account.
3. **Redshift** — AWS-native, and Redshift Spectrum queries S3 directly without loading it in, which matters when a lot of data already lives there and ETL is heavy and scheduled rather than ad-hoc.
4. **Snowflake** — multiple independent virtual warehouses against the same underlying data is exactly this isolation pattern (see `concepts/01_cloud_data_warehouses.md`, section 3).
5. **BigQuery** — fully serverless; there is no cluster or warehouse object to size, suspend, or resume at all.

</details>

---

## Exercise 2: Fix a Query That's Silently Defeating Partition Pruning

A BigQuery table `sales` is `PARTITION BY DATE(sale_date)`. This query is supposed to scan only March 2024, but the billing dashboard shows it scanned the entire multi-year table:

```sql
SELECT SUM(revenue)
FROM sales
WHERE FORMAT_DATE('%Y-%m', sale_date) = '2024-03';
```

**Your task:** explain why pruning fails here, and rewrite the query so it prunes correctly.

<details>
<summary>Reference answer</summary>

**Why it fails:** wrapping the partitioned column (`sale_date`) inside a function (`FORMAT_DATE(...)`) before comparing it means the warehouse would have to evaluate that function against every row just to know whether it matches — it can no longer reason "which partitions could possibly satisfy this filter" from the raw column value alone, so it falls back to a full scan.

**Fix:** filter on `sale_date` directly, as a range:

```sql
SELECT SUM(revenue)
FROM sales
WHERE sale_date BETWEEN '2024-03-01' AND '2024-03-31';
```

This is the same failure mode named in `concepts/05_cost_and_performance_optimization.md`, section 2, and it's one of the most common causes of "the partitioned table isn't actually saving us anything" tickets in practice.

</details>

---

## Exercise 3: Choose a Redshift Distribution and Sort Key

You're designing `fact_sales` in Redshift: 500M rows, joined constantly to `dim_customer` (2M rows) on `customer_id`, and almost every analytical query filters by a date range on `sale_date`.

**Your task:** choose a `DISTSTYLE`/`DISTKEY` and a `SORTKEY` for `fact_sales`, and a `DISTSTYLE` for `dim_customer`, with reasoning.

<details>
<summary>Reference answer</summary>

```sql
CREATE TABLE fact_sales (
    sale_id INT, customer_id INT, sale_date DATE, revenue DECIMAL(10,2)
) DISTSTYLE KEY DISTKEY(customer_id) SORTKEY(sale_date);

CREATE TABLE dim_customer (
    customer_id INT, name VARCHAR, segment VARCHAR
) DISTSTYLE ALL;
```

- `fact_sales` gets `DISTKEY(customer_id)` because it's joined to `dim_customer` constantly on that column — co-locating matching rows on the same node avoids a network shuffle during the join.
- `SORTKEY(sale_date)` because nearly every query filters by date range — sorted blocks let Redshift skip blocks outside the filtered range.
- `dim_customer` gets `DISTSTYLE ALL` (copied to every node) because it's small (2M rows) and joined constantly — every node already has a local copy, so the join never needs to shuffle it either. `DISTSTYLE ALL` would be the wrong call on `fact_sales` itself — copying 500M rows to every node multiplies storage by the node count for no benefit.

*(See `concepts/02_snowflake_bigquery_redshift.md`, section 5.)*

</details>

---

## Exercise 4: Write Staging Models

Given these raw source tables, write staging models for all four:

```
raw_orders(id, customer_id, amount_cents, status, channel, ordered_at)
raw_customers(id, first_name, last_name, email, segment, country, created_at)
raw_products(id, name, category, price_cents, is_active)
raw_order_items(id, order_id, product_id, quantity, unit_price_cents)
```

Requirements: `stg_orders` converts cents to dollars and lowercases status; `stg_customers` combines first/last name and lowercases email; `stg_products` filters to active only and converts cents to dollars; `stg_order_items` converts cents to dollars.

<details>
<summary>Reference answer</summary>

```sql
-- models/staging/stg_orders.sql
{{ config(materialized='view') }}
SELECT
    id AS order_id, customer_id,
    CAST(amount_cents AS FLOAT) / 100 AS amount,
    LOWER(status) AS order_status,
    LOWER(channel) AS channel,
    ordered_at
FROM {{ source('raw', 'orders') }}

-- models/staging/stg_customers.sql
{{ config(materialized='view') }}
SELECT
    id AS customer_id,
    first_name || ' ' || last_name AS customer_name,
    LOWER(email) AS email,
    segment, UPPER(country) AS country,
    created_at AS registered_at
FROM {{ source('raw', 'customers') }}

-- models/staging/stg_products.sql
{{ config(materialized='view') }}
SELECT
    id AS product_id, name AS product_name,
    LOWER(category) AS category,
    CAST(price_cents AS FLOAT) / 100 AS price
FROM {{ source('raw', 'products') }}
WHERE is_active = 1

-- models/staging/stg_order_items.sql
{{ config(materialized='view') }}
SELECT
    id AS order_item_id, order_id, product_id, quantity,
    CAST(unit_price_cents AS FLOAT) / 100 AS unit_price
FROM {{ source('raw', 'order_items') }}
```

Runnable verification against sqlite (standing in for the four views above):

```python
import sqlite3
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("CREATE TABLE raw_orders (id INT, customer_id INT, amount_cents INT, status TEXT, channel TEXT, ordered_at TEXT)")
cur.execute("INSERT INTO raw_orders VALUES (1, 10, 5000, 'COMPLETED', 'Web', '2024-06-01')")
cur.execute("""CREATE VIEW stg_orders AS
    SELECT id AS order_id, customer_id, CAST(amount_cents AS REAL)/100 AS amount,
           LOWER(status) AS order_status, LOWER(channel) AS channel, ordered_at
    FROM raw_orders""")
cur.execute("SELECT * FROM stg_orders")
print(cur.fetchall())
```

```
[(1, 10, 50.0, 'completed', 'web', '2024-06-01')]
```

</details>

---

## Exercise 5: Build an Intermediate Model

Using the staging models from Exercise 4, build `int_orders_detailed`: join orders to customers, order items, and products; compute `line_total = quantity * unit_price`; include `customer_name`, `country`, `product_name`, `category`. Then write the query that reports total revenue by category for completed orders only.

<details>
<summary>Reference answer</summary>

```sql
-- models/intermediate/int_orders_detailed.sql
{{ config(materialized='table') }}
SELECT
    o.order_id, o.customer_id, c.customer_name, c.country,
    o.channel, o.order_status, o.ordered_at,
    oi.product_id, p.product_name, p.category,
    oi.quantity, oi.unit_price,
    oi.quantity * oi.unit_price AS line_total
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('stg_customers') }} c ON o.customer_id = c.customer_id
JOIN {{ ref('stg_order_items') }} oi ON o.order_id = oi.order_id
JOIN {{ ref('stg_products') }} p ON oi.product_id = p.product_id
```

```sql
SELECT category, ROUND(SUM(line_total), 2) AS revenue
FROM {{ ref('int_orders_detailed') }}
WHERE order_status = 'completed'
GROUP BY category
ORDER BY revenue DESC
```

Notice this model is materialized as a `table`, not a `view` — it's a four-way join, and it's about to be `ref()`'d by more than one downstream mart, so recomputing it live on every query would be wasteful (see `concepts/03_dbt_fundamentals_and_dag.md`, section 3).

</details>

---

## Exercise 6: Build Mart Models

Build two marts from `int_orders_detailed`:

1. `fct_daily_sales` — one row per `(sale_date, channel)`: `order_count`, `total_revenue`, `avg_order_value`.
2. `dim_customers` — one row per customer: `total_orders`, `total_spent`, `avg_order_value`, `first_order_date`, `last_order_date`.

<details>
<summary>Reference answer</summary>

```sql
-- models/marts/fct_daily_sales.sql
{{ config(materialized='table') }}
SELECT
    ordered_at AS sale_date, channel,
    COUNT(DISTINCT order_id) AS order_count,
    ROUND(SUM(line_total), 2) AS total_revenue,
    ROUND(SUM(line_total) / COUNT(DISTINCT order_id), 2) AS avg_order_value
FROM {{ ref('int_orders_detailed') }}
WHERE order_status = 'completed'
GROUP BY ordered_at, channel

-- models/marts/dim_customers.sql
{{ config(materialized='table') }}
SELECT
    customer_id, customer_name, country,
    COUNT(DISTINCT order_id) AS total_orders,
    COALESCE(ROUND(SUM(line_total), 2), 0) AS total_spent,
    COALESCE(ROUND(SUM(line_total) / NULLIF(COUNT(DISTINCT order_id), 0), 2), 0) AS avg_order_value,
    MIN(ordered_at) AS first_order_date,
    MAX(ordered_at) AS last_order_date
FROM {{ ref('int_orders_detailed') }}
WHERE order_status = 'completed'
GROUP BY customer_id, customer_name, country
```

Notice `order_count` and the customer aggregates use `COUNT(DISTINCT order_id)`, not `COUNT(*)` — `int_orders_detailed` is at the line-item grain (one row per order item), so a naive `COUNT(*)` would count line items, not orders, exactly the double-counting failure named in `data_modeling/interview_questions/03_critique_and_debug.md`, Case 1.

</details>

---

## Exercise 7: Write Generic (Schema) Tests

For `fct_daily_sales` and `dim_customers`, write the YAML schema tests that check:

1. `customer_id` in `dim_customers` is unique and not null.
2. `channel` in `fct_daily_sales` only takes values `web`, `mobile`, `api`.
3. Every `customer_id` referenced elsewhere exists in `dim_customers` (relationship/orphan check).

<details>
<summary>Reference answer</summary>

```yaml
# models/marts/_marts.yml
version: 2
models:
  - name: dim_customers
    columns:
      - name: customer_id
        tests:
          - unique
          - not_null

  - name: fct_daily_sales
    columns:
      - name: channel
        tests:
          - accepted_values:
              values: ['web', 'mobile', 'api']

  - name: fct_orders
    columns:
      - name: customer_id
        tests:
          - relationships:
              to: ref('dim_customers')
              field: customer_id
```

Runnable equivalent, to see the pass/fail mechanics directly:

```python
import sqlite3
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("CREATE TABLE dim_customers (customer_id INT)")
cur.executemany("INSERT INTO dim_customers VALUES (?)", [(1,), (2,), (2,)])  # duplicate on purpose
conn.commit()

cur.execute("SELECT customer_id, COUNT(*) c FROM dim_customers GROUP BY customer_id HAVING c > 1")
failures = cur.fetchall()
print("unique(dim_customers.customer_id):", "PASS" if not failures else f"FAIL {failures}")
```

```
unique(dim_customers.customer_id): FAIL [(2, 2)]
```

</details>

---

## Exercise 8: Write Singular (Custom) Tests

Write three singular tests as SQL files, each following the "pass = 0 rows" convention:

1. `assert_revenue_matches_line_items` — an order's total should equal the sum of its line items.
2. `assert_no_orphan_order_items` — every order item's `order_id` must exist in orders.
3. `assert_customer_ltv_non_negative` — `dim_customers.total_spent` must never be negative.

<details>
<summary>Reference answer</summary>

```sql
-- tests/assert_revenue_matches_line_items.sql
SELECT o.order_id, o.amount, SUM(oi.quantity * oi.unit_price) AS calculated_total
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('stg_order_items') }} oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.amount
HAVING ABS(o.amount - calculated_total) > 0.01

-- tests/assert_no_orphan_order_items.sql
SELECT oi.order_item_id
FROM {{ ref('stg_order_items') }} oi
LEFT JOIN {{ ref('stg_orders') }} o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL

-- tests/assert_customer_ltv_non_negative.sql
SELECT customer_id, total_spent
FROM {{ ref('dim_customers') }}
WHERE total_spent < 0
```

</details>

---

## Exercise 9: Implement and Diagnose an Incremental Model

Part A: implement an incremental model for `fct_events` that loads only new rows, using `is_incremental()` and a `created_at` watermark. Part B: this incremental model was configured as `incremental_strategy='merge'` with `unique_key='event_id'` — an upstream backfill re-sends 200 already-loaded events with corrected `event_type` values. What happens on the next `dbt run`, and would the result differ under `append` instead of `merge`?

<details>
<summary>Reference answer</summary>

**Part A:**

```sql
{{ config(materialized='incremental', unique_key='event_id', incremental_strategy='merge') }}

SELECT id AS event_id, user_id, event_type, created_at
FROM {{ source('raw', 'events') }}
{% if is_incremental() %}
    WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
```

```python
def run_incremental(cur, exists, unique_key="event_id"):
    sql = "SELECT * FROM raw_events WHERE created_at > (SELECT MAX(created_at) FROM fct_events)"
    if not exists:
        cur.execute("CREATE TABLE fct_events AS SELECT * FROM raw_events")
    else:
        cur.execute(f"DELETE FROM fct_events WHERE {unique_key} IN (SELECT {unique_key} FROM ({sql}))")
        cur.execute(f"INSERT INTO fct_events {sql}")
```

**Part B:** under `merge` with a correct `unique_key`, the 200 re-sent events are recognized by their `event_id` and their rows are updated in place (delete-then-reinsert or a native `MERGE`, depending on the warehouse) — the corrected `event_type` values land cleanly, with no duplicates.

Under `append` instead, dbt has no concept of "this row already exists" — it blindly inserts the 200 re-sent rows *in addition to* the 200 already there, producing 200 duplicate `event_id`s. This is exactly why `append` is only appropriate for genuinely immutable, never-updated event data — the moment an upstream system might resend or correct a row, `merge` (or `delete+insert`) with a correct `unique_key` is required, or a `unique` schema test on `event_id` will start failing (which is precisely the mechanism that should catch this in CI before it's discovered manually).

</details>

---

## Exercise 10: Design a Complete dbt Project Structure

You're building an analytics platform for a SaaS company with four source systems: Stripe (payments), Salesforce (CRM), a product/events database, and marketing ad-platform exports. Design the full project: staging models per source, intermediate models with their join logic, mart models grouped by consuming team (finance, sales, product, marketing), tests for each mart, and any macros worth creating.

<details>
<summary>Reference answer</summary>

```
my_saas_analytics/
├── dbt_project.yml
├── packages.yml                          -- dbt-utils, dbt-expectations
├── macros/
│   ├── cents_to_dollars.sql              -- reusable currency conversion
│   └── is_active_record.sql              -- shared soft-delete filter
├── models/
│   ├── staging/
│   │   ├── stripe/
│   │   │   ├── _stripe__sources.yml
│   │   │   ├── stg_stripe__payments.sql
│   │   │   └── stg_stripe__invoices.sql
│   │   ├── salesforce/
│   │   │   ├── _salesforce__sources.yml
│   │   │   ├── stg_sf__accounts.sql
│   │   │   └── stg_sf__opportunities.sql
│   │   ├── product/
│   │   │   ├── stg_product__users.sql
│   │   │   └── stg_product__events.sql
│   │   └── marketing/
│   │       └── stg_ads__campaign_spend.sql
│   ├── intermediate/
│   │   ├── int_payments__enriched.sql    -- payments + account info
│   │   ├── int_users__activity.sql       -- per-user event rollups
│   │   └── int_revenue__by_account.sql   -- revenue attributed to SF accounts
│   └── marts/
│       ├── finance/
│       │   ├── fct_monthly_revenue.sql
│       │   └── dim_subscriptions.sql
│       ├── sales/
│       │   ├── fct_pipeline.sql
│       │   └── dim_accounts.sql
│       ├── product/
│       │   ├── fct_daily_active_users.sql
│       │   └── dim_users.sql
│       └── marketing/
│           └── fct_campaign_roi.sql       -- joins ad spend to attributed revenue
└── tests/
    ├── assert_mrr_non_negative.sql
    └── assert_no_orphan_payments.sql
```

Each mart's tests live alongside its YAML (`unique`/`not_null` on every primary key, `relationships` from `fct_*` back to its `dim_*`, `accepted_values` on any status/tier column) — omitted above for brevity but expected in a real project, per `concepts/04_dbt_testing_macros_and_project_structure.md`.

</details>

---

## Exercise 11: Diagnose a Slow, Expensive Nightly Run

A nightly `dbt build` used to finish in 20 minutes and now takes 3 hours, with a proportional jump in warehouse cost. Nothing in the model SQL changed recently, but the source `raw.events` table (feeding an `incremental` model, `fct_user_events`) grew from 2M to 400M rows over the last few months as usage scaled.

**Your task:** name the most likely root cause and the fix, and one thing you'd check to confirm the diagnosis before acting on it.

<details>
<summary>Reference answer</summary>

**Most likely cause:** `fct_user_events`'s `is_incremental()` watermark filter isn't actually narrowing the scan the way it should — either the filter column isn't indexed/clustered on the source table, or (more likely, given "nothing in the model SQL changed") the model was always doing a small delta correctly, and the *real* culprit is a different, non-incremental `table`-materialized model downstream that re-joins the full (now 200x larger) `fct_user_events` on every run. A `table` materialization has no concept of "new rows only" — it always processes everything the query selects, so as the base table grew 200x, that model's per-run cost grew proportionally.

**Fix:** find which specific model(s) grew in runtime (dbt's run results/logs show per-model timing) rather than assuming it's the incremental model itself. If it's a downstream `table` model doing a full join against the now-huge `fct_user_events` every night, either convert it to `incremental` as well (if its own logic supports a watermark), or narrow what it selects from `fct_user_events` (e.g. only the last N days, if that's all the model's business logic actually needs).

**What to check first:** the dbt run's per-model timing output (or `target/run_results.json`) to confirm *which* model's runtime grew, rather than guessing — this is the same "check what changed, don't guess" discipline from `concepts/05_cost_and_performance_optimization.md`, section 6. Fixing the wrong model wastes an engineering cycle and leaves the actual cost driver untouched.

</details>

---

## Exercise 12: Choose Between Snowflake and BigQuery for a Given Workload

A retail analytics company: 80% of workload is a fixed set of scheduled dashboards refreshed every morning at 6am; the remaining 20% is unpredictable ad-hoc analyst queries throughout the day, with occasional very large one-off queries during quarterly planning. The company is not tied to a specific cloud provider.

**Your task:** pick a platform and justify it against this specific workload shape, not a generic feature list.

<details>
<summary>Reference answer</summary>

**Either can work, but the reasoning should be workload-shaped, not a coin flip.** A strong answer names the actual trade-off: Snowflake lets you run the predictable 80% (the 6am dashboard refresh) on a small, fixed-size, scheduled-resume warehouse — cost is capped and predictable because you control warehouse size and auto-suspend directly — while giving the unpredictable 20% (ad-hoc analyst queries, occasional huge quarterly queries) its own separately-sized, auto-scaling warehouse, so a huge one-off query doesn't force the whole account onto a permanently bigger (and pricier) footprint.

BigQuery's on-demand pricing is arguably simpler for the unpredictable 20% (no warehouse to size at all — it just scales to the query), but becomes harder to *forecast and cap* for the predictable, recurring 80% unless flat-rate slot reservations are purchased specifically for that scheduled workload — which reintroduces a capacity-planning decision similar to sizing a Snowflake warehouse anyway.

The stronger interview answer isn't "Snowflake" or "BigQuery" in isolation — it's naming that this workload has two distinct shapes (predictable/scheduled vs. unpredictable/bursty) and that the platform choice should let each shape be isolated and cost-controlled independently, which both platforms can do, through different mechanisms (multiple warehouses vs. slot reservations + on-demand).

</details>
