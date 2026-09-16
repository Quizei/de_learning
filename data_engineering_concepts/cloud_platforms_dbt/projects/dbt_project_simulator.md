# Capstone Project: Build a Small Real dbt Project

## Scenario

You've been asked to stand up the first dbt project for a small
e-commerce analytics team. Raw order, customer, and product data
already lands nightly in a `raw` schema (via a managed connector — not
your concern). Your job is everything from there: a staging layer that
cleans the raw tables, an intermediate layer that joins them with
business logic, mart tables the BI team will query directly, and a test
suite that catches the classic failure modes covered in
`interview_questions/03_critique_and_debug.md` before they ever reach a
dashboard.

This brief is a **project spec, not a finished solution** — it gives
you the raw schema, the required models with their expected shape and
tests, and a couple of starter files to show the exact conventions to
follow. Build the rest yourself, in a real dbt project if you have one
set up (a free DuckDB or local Postgres target both work fine for this
size of exercise), or by reasoning through the SQL/YAML on paper if you
don't. This is deliberately the same underlying dataset shape used
throughout `concepts/` and `practice/exercises.md`, so anything you
learned there transfers directly.

## Learning Goal

Implement a complete three-layer dbt project (staging → intermediate →
marts) against the interface described below: generic and singular
tests wired to the right models, at least one genuinely incremental
model with a correct `unique_key` and `is_incremental()` condition, a
macro used in more than one model, and a `sources.yml` with freshness
configured. This exercises every concept from
`concepts/03_dbt_fundamentals_and_dag.md` and
`concepts/04_dbt_testing_macros_and_project_structure.md` as a single,
coherent project instead of isolated examples.

---

## The Raw Schema (already loaded, not yours to build)

```sql
-- raw.orders
CREATE TABLE raw.orders (
    id INTEGER, customer_id INTEGER, amount_cents INTEGER,
    status TEXT, channel TEXT, ordered_at TIMESTAMP, updated_at TIMESTAMP
);

-- raw.customers
CREATE TABLE raw.customers (
    id INTEGER, first_name TEXT, last_name TEXT, email TEXT,
    segment TEXT, country TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);

-- raw.products
CREATE TABLE raw.products (
    id INTEGER, name TEXT, category TEXT,
    price_cents INTEGER, cost_cents INTEGER, is_active BOOLEAN
);

-- raw.order_items
CREATE TABLE raw.order_items (
    id INTEGER, order_id INTEGER, product_id INTEGER,
    quantity INTEGER, unit_price_cents INTEGER
);

-- raw.events  (high volume -- this is the one that needs to be incremental)
CREATE TABLE raw.events (
    id INTEGER, user_id INTEGER, event_type TEXT,
    event_data TEXT, created_at TIMESTAMP
);
```

---

## Required Project Layout

```
ecommerce_analytics/
├── dbt_project.yml
├── packages.yml
├── macros/
│   └── cents_to_dollars.sql        -- STARTER PROVIDED BELOW
├── models/
│   ├── staging/
│   │   ├── _sources.yml            -- STARTER PROVIDED BELOW
│   │   ├── stg_orders.sql          -- YOUR TASK
│   │   ├── stg_customers.sql       -- YOUR TASK
│   │   ├── stg_products.sql        -- YOUR TASK
│   │   ├── stg_order_items.sql     -- YOUR TASK
│   │   └── stg_events.sql          -- YOUR TASK
│   ├── intermediate/
│   │   ├── int_order_items_enriched.sql   -- YOUR TASK
│   │   └── int_orders_enriched.sql        -- YOUR TASK
│   └── marts/
│       ├── _marts.yml              -- YOUR TASK (tests live here)
│       ├── fct_orders.sql          -- YOUR TASK
│       ├── fct_daily_revenue.sql   -- YOUR TASK
│       ├── fct_user_events.sql     -- YOUR TASK (must be incremental)
│       └── dim_customers.sql       -- YOUR TASK
└── tests/
    ├── assert_positive_order_amounts.sql   -- YOUR TASK
    └── assert_revenue_matches_line_items.sql -- YOUR TASK
```

---

## Starter Files (use these conventions throughout your own models)

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name, precision=2) %}
    ROUND(CAST({{ column_name }} AS FLOAT) / 100, {{ precision }})
{% endmacro %}
```

```yaml
# models/staging/_sources.yml
version: 2
sources:
  - name: raw
    schema: raw
    tables:
      - name: orders
        loaded_at_field: updated_at
        freshness:
          warn_after: {count: 12, period: hour}
          error_after: {count: 24, period: hour}
      - name: customers
        loaded_at_field: updated_at
        freshness:
          warn_after: {count: 24, period: hour}
          error_after: {count: 48, period: hour}
      - name: products
      - name: order_items
      - name: events
        loaded_at_field: created_at
        freshness:
          warn_after: {count: 6, period: hour}
          error_after: {count: 12, period: hour}
```

```sql
-- models/staging/stg_orders.sql  (example of the expected shape/convention --
-- your other staging models should follow this same pattern)
{{ config(materialized='view') }}

SELECT
    id AS order_id,
    customer_id,
    {{ cents_to_dollars('amount_cents') }} AS amount,
    LOWER(status) AS order_status,
    LOWER(channel) AS channel,
    ordered_at,
    updated_at
FROM {{ source('raw', 'orders') }}
```

---

## Your Tasks, With Required Behavior

### 1. Remaining staging models

- `stg_customers`: combine `first_name`/`last_name` into `customer_name`, lowercase `email`, uppercase `country`.
- `stg_products`: filter to `is_active = true` only, convert both `price_cents` and `cost_cents` to dollars using the shared macro.
- `stg_order_items`: rename `id` to `order_item_id`, convert `unit_price_cents` to dollars.
- `stg_events`: rename `id` to `event_id`; no other transformation needed.

### 2. Intermediate models

- `int_order_items_enriched`: join order items to products; compute `line_total = quantity * unit_price` and `line_profit = quantity * (unit_price - cost)`.
- `int_orders_enriched`: join orders to customers, bringing in `customer_name` and `country`.

### 3. Mart models

- `fct_orders`: from `int_orders_enriched`, left-joined to an aggregation of `int_order_items_enriched` (total items, total profit per order).
- `fct_daily_revenue`: one row per `(date, channel)` from `int_orders_enriched` — `order_count`, `total_revenue`, `completed_revenue` (revenue only where `order_status = 'completed'`).
- `fct_user_events`: **must be `materialized='incremental'`**, `unique_key='event_id'`, `incremental_strategy='merge'`, watermarked on `created_at`, reading from `stg_events`. This is the one high-volume source (per the raw schema comment) — build it incremental deliberately, not by habit, and be ready to explain why the *other* models in this project are not incremental (they're small enough that a full rebuild costs nothing meaningful — see `concepts/05_cost_and_performance_optimization.md`).
- `dim_customers`: from `stg_customers` left-joined to `fct_orders`, computing `total_orders`, `lifetime_value`, `first_order_date`, `last_order_date`.

### 4. Tests

In `models/marts/_marts.yml`:
- `unique` + `not_null` on `fct_orders.order_id` and `dim_customers.customer_id`.
- `accepted_values` on `fct_orders.order_status` (`completed`, `pending`, `cancelled`) and `fct_daily_revenue.channel` (`web`, `mobile`, `api`).
- `relationships` from `fct_orders.customer_id` to `dim_customers.customer_id`.

Two singular tests in `tests/`:
- `assert_positive_order_amounts.sql` — fails if any `fct_orders.amount < 0`.
- `assert_revenue_matches_line_items.sql` — fails if an order's `amount` doesn't reconcile against the sum of its `int_order_items_enriched.line_total` rows.

---

## Worked Example: What a Correct `fct_orders` Should Produce

Given this raw data:

```
raw.orders:       (1, 10, 5998, 'completed', 'web', '2024-06-01', '2024-06-01')
                  (2, 11, 4999, 'completed', 'mobile', '2024-06-02', '2024-06-02')
raw.customers:    (10, 'Alice', 'Johnson', 'alice@x.com', 'premium', 'US', ..., ...)
                  (11, 'Bob', 'Smith', 'bob@x.com', 'standard', 'UK', ..., ...)
raw.order_items:  (1, 1, 101, 2, 2999), (2, 2, 102, 1, 4999)
raw.products:     (101, 'Widget', 'electronics', 2999, 1200, true)
                  (102, 'Gadget', 'electronics', 4999, 2000, true)
```

Running `dbt build` should produce a `fct_orders` table shaped like:

| order_id | customer_id | customer_name | country | amount | order_status | total_items | total_profit |
|---|---|---|---|---|---|---|---|
| 1 | 10 | Alice Johnson | US | 59.98 | completed | 2 | 35.98 |
| 2 | 11 | Bob Smith | UK | 49.99 | completed | 1 | 29.99 |

(`total_profit` for order 1: `2 * (29.99 - 12.00) = 35.98`; order 2: `1 * (49.99 - 20.00) = 29.99`.)

And `dbt test` should report every configured test passing:

```
1 of 8  PASS  unique_fct_orders_order_id ................ [PASS]
2 of 8  PASS  not_null_fct_orders_order_id .............. [PASS]
3 of 8  PASS  accepted_values_fct_orders_order_status ... [PASS]
4 of 8  PASS  relationships_fct_orders_customer_id ...... [PASS]
5 of 8  PASS  unique_dim_customers_customer_id .......... [PASS]
6 of 8  PASS  not_null_dim_customers_customer_id ........ [PASS]
7 of 8  PASS  assert_positive_order_amounts ............. [PASS]
8 of 8  PASS  assert_revenue_matches_line_items .......... [PASS]

Done. PASS=8 WARN=0 ERROR=0
```

---

## Stretch Goals (once the core project builds and tests pass)

1. **Break your own incremental model on purpose.** Remove `unique_key`
   from `fct_user_events`, re-run it twice against overlapping data, and
   confirm you get duplicate rows — then add `unique_key` back and
   confirm the duplicates stop. This is the exact bug in
   `interview_questions/03_critique_and_debug.md`, Case 1, reproduced
   in your own project rather than read about.
2. **Add a `dbt snapshot`** over `raw.customers` to track `segment`
   changes as SCD Type 2, and explain in a comment why this is a
   different tool from `fct_user_events`'s incremental materialization
   even though both process "only what changed."
3. **Simulate a cost regression.** Convert `fct_user_events` from
   `incremental` to `table`, note (or estimate, if not running against
   a real warehouse) how much more it would scan on a full rebuild once
   `raw.events` is large, and write down the fix as if this were a
   real "why did the bill triple" investigation from
   `interview_questions/01_worked_scenarios.md`, Scenario C.
