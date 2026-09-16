# Concept 04: dbt Testing, Macros & Project Structure

**Covers:**
- Staging, intermediate, and marts layers, and the naming/materialization conventions each one follows
- Generic (schema) tests: `unique`, `not_null`, `accepted_values`, `relationships`
- Singular (custom) data tests, and the "pass = zero rows returned" convention
- Macros — reusable Jinja SQL — and the `dbt_utils` package
- Sources, freshness checks, and `dbt docs generate`
- How this all fits into an ELT architecture and a CI/CD pipeline

This file builds directly on `03_dbt_fundamentals_and_dag.md` — read that first for `ref()`/`source()`, the DAG, and materializations. This one covers everything a real dbt project needs *around* the models themselves: how they're organized, how they're tested, and how logic gets shared instead of copy-pasted.

---

## 1. The Three Layers: Staging → Intermediate → Marts

A dbt project's `models/` directory is conventionally organized into three layers, each with a distinct job and a distinct default materialization:

```
models/
├── staging/          -- 1:1 with source tables: rename, cast, light cleaning. Views.
│   ├── stg_orders.sql
│   └── stg_customers.sql
├── intermediate/      -- business-logic joins between staging models. Tables (or ephemeral).
│   └── int_orders_enriched.sql
└── marts/             -- final, BI-facing entities. Tables.
    ├── fct_orders.sql
    └── dim_customers.sql
```

**Staging models** do exactly one job: make a raw source table trustworthy without adding any business logic — rename cryptic columns, cast types, lowercase/trim strings, convert cents to dollars. No joins. One staging model per source table, named `stg_{source}__{table}` (e.g. `stg_stripe__payments`).

```sql
-- models/staging/stg_stripe_payments.sql
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('stripe', 'payments') }}
),
renamed AS (
    SELECT
        id AS payment_id,
        order_id,
        CAST(amt AS FLOAT) / 100 AS amount_dollars,
        LOWER(TRIM(payment_method)) AS payment_method,
        LOWER(status) AS payment_status,
        created AS paid_at
    FROM source
)
SELECT * FROM renamed
```

**Intermediate models** join staging models together and apply business logic — the "why" a mart exists in the first place lives here, not scattered across marts. Named `int_{entity}__{verb}` (e.g. `int_orders__enriched`). Often materialized as a `table` (heavy joins get expensive to recompute per query) or `ephemeral` (thin, pure organizational logic).

```sql
-- models/intermediate/int_orders_enriched.sql
{{ config(materialized='table') }}

SELECT
    o.order_id, o.customer_id, c.customer_name, c.country,
    o.amount, o.order_status, o.ordered_at
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('stg_customers') }} c ON o.customer_id = c.customer_id
```

**Marts** are the final tables analysts and BI tools query directly — `fct_*` (fact tables, one row per business event) and `dim_*` (dimension tables), following the same vocabulary as `data_modeling/`. Almost always materialized as `table` or `incremental`.

```sql
-- models/marts/fct_orders.sql
{{ config(materialized='table') }}

SELECT order_id, customer_id, customer_name, country, amount, order_status, ordered_at
FROM {{ ref('int_orders_enriched') }}
WHERE order_status = 'completed'
```

This three-layer discipline is the direct dbt-flavored version of the medallion architecture (`data_warehousing_lakes/concepts/04_data_lake_and_lakehouse_architecture.md`): staging is silver, marts are gold. It's also the answer to the single most common practical dbt interview question — "walk me through how you'd structure a project" — see `interview_questions/01_worked_scenarios.md` for a full worked version.

---

## 2. Generic (Schema) Tests

A **generic test** is a reusable, parameterized assertion applied to a column via YAML — no SQL written per-test. dbt ships four built in:

```yaml
# models/marts/_marts.yml
version: 2
models:
  - name: fct_orders
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: order_status
        tests:
          - accepted_values:
              values: ['pending', 'completed', 'cancelled']
      - name: customer_id
        tests:
          - relationships:
              to: ref('dim_customers')
              field: customer_id
```

- **`unique`** — no duplicate values in the column.
- **`not_null`** — no `NULL`s.
- **`accepted_values`** — every value falls inside an explicit allow-list (a lightweight enum check).
- **`relationships`** — every value in this column exists in the referenced column of another model (referential integrity, the classic orphan-row check).

Each compiles down to a `SELECT` that returns **zero rows on pass, one row per failure on fail** — the same convention every dbt test (generic or singular) follows:

```python
def run_schema_test(cur, model, column, test_type, **kwargs):
    if test_type == "unique":
        cur.execute(f"SELECT {column}, COUNT(*) c FROM {model} GROUP BY {column} HAVING c > 1")
    elif test_type == "not_null":
        cur.execute(f"SELECT * FROM {model} WHERE {column} IS NULL")
    elif test_type == "accepted_values":
        values = kwargs["values"]
        ph = ",".join("?" for _ in values)
        cur.execute(f"SELECT DISTINCT {column} FROM {model} WHERE {column} NOT IN ({ph})", values)
    elif test_type == "relationships":
        cur.execute(f"""SELECT * FROM {model}
                         WHERE {column} NOT IN (SELECT {kwargs['field']} FROM {kwargs['to']})""")
    failures = cur.fetchall()
    return len(failures) == 0, len(failures)

passed, n = run_schema_test(cur, "fct_orders", "order_id", "unique")
print("PASS" if passed else f"FAIL ({n} duplicates)")
```

```
PASS
```

---

## 3. Singular (Custom) Tests

A **singular test** is arbitrary SQL you write yourself, one `.sql` file per test in `tests/`, following the identical "zero rows = pass" convention — for business rules generic tests can't express:

```sql
-- tests/assert_positive_revenue.sql
-- Passes when this query returns 0 rows.
SELECT order_id, amount
FROM {{ ref('fct_orders') }}
WHERE amount < 0
```

```sql
-- tests/assert_revenue_matches_line_items.sql
SELECT o.order_id, o.amount, SUM(oi.quantity * oi.unit_price) AS calculated_total
FROM {{ ref('fct_orders') }} o
JOIN {{ ref('fct_order_items') }} oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.amount
HAVING o.amount != calculated_total
```

Generic tests check a *column property*; singular tests check a *cross-row or cross-table business invariant* — reach for a singular test the moment the assertion needs a join, an aggregation, or logic specific to one model rather than a reusable column-level rule.

---

## 4. Macros and `dbt_utils`

A **macro** is a Jinja function that expands into SQL at compile time — dbt's mechanism for not repeating yourself across models.

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name, precision=2) %}
    ROUND(CAST({{ column_name }} AS FLOAT) / 100, {{ precision }})
{% endmacro %}
```

```sql
-- used in a model:
SELECT {{ cents_to_dollars('amount_cents') }} AS amount
FROM {{ source('raw', 'orders') }}
```

```python
def expand_macro(sql: str, name: str, template: str) -> str:
    """Simplified simulation of Jinja macro expansion: cents_to_dollars('amount_cents')
    -> ROUND(CAST(amount_cents AS FLOAT) / 100, 2)"""
    import re
    for match in re.finditer(rf"{name}\(([^)]*)\)", sql):
        args = [a.strip().strip("'\"") for a in match.group(1).split(",")]
        expanded = template.replace("${0}", args[0])
        sql = sql.replace(match.group(0), expanded)
    return sql

sql = "SELECT cents_to_dollars('amount_cents') AS amount FROM raw_orders"
print(expand_macro(sql, "cents_to_dollars", "ROUND(CAST(${0} AS FLOAT) / 100, 2)"))
```

```
SELECT ROUND(CAST(amount_cents AS FLOAT) / 100, 2) AS amount FROM raw_orders
```

**`dbt_utils`** is the most widely installed community package, adding macros for problems every project eventually hits:

```yaml
# packages.yml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
```

```sql
-- generate a stable surrogate key by hashing a set of columns
{{ dbt_utils.generate_surrogate_key(['customer_id', 'order_date']) }}

-- a complete calendar spine, useful anywhere a report needs every date
-- represented even on days with zero underlying activity
{{ dbt_utils.date_spine(datepart='day', start_date="'2024-01-01'", end_date="'2024-12-31'") }}

-- select every column except a few, without hand-listing the rest
{{ dbt_utils.star(from=ref('stg_orders'), except=['_loaded_at']) }}
```

Other packages worth naming if asked "what packages have you used": **`dbt_expectations`** (statistical/range-based tests, e.g. `expect_column_values_to_be_between`), **`codegen`** (scaffolds source/staging-model YAML and SQL so it isn't hand-typed for every new table), and **`dbt_audit_helper`** (diffs two relations row-by-row — useful when refactoring a model and needing to prove the output didn't change).

---

## 5. Sources, Freshness, and Documentation

**Sources** are declared once in YAML and referenced everywhere via `source()`, giving dbt a place to attach freshness rules and descriptions to raw tables it doesn't build itself:

```yaml
# models/staging/_sources.yml
version: 2
sources:
  - name: raw
    database: analytics
    schema: raw_data
    loaded_at_field: _etl_loaded_at
    freshness:
      warn_after: {count: 12, period: hour}
      error_after: {count: 24, period: hour}
    tables:
      - name: orders
        description: "Raw orders from the OLTP system"
      - name: customers
```

```bash
dbt source freshness
```

```
raw.orders      last loaded: 3h ago   [PASS]
raw.customers   last loaded: 26h ago  [ERROR]
```

`dbt source freshness` answers a question no schema test can: not "is this data correct," but "is this data *current enough to trust*" — a silently-stalled upstream extraction job is one of the most common real-world causes of a stakeholder-visible bad number, and it produces zero test failures, since every row that did load is perfectly valid.

`dbt docs generate` builds a static site from all of this — every model's SQL, every test, every source, and a rendered DAG diagram — the practical answer to "how do you document a warehouse" that doesn't involve a separate wiki nobody keeps updated, because the documentation is generated directly from the same YAML and SQL that defines the pipeline.

---

## 6. Where This Sits in a CI/CD Pipeline

```
pull request opened
        |
        v
  dbt build --target ci   (run + test + snapshot + seed, against an
        |                   isolated schema, usually on a small sample
        |                   or a full dev warehouse clone)
        v
  tests fail?  --> block the merge, surface which test failed and why
        |
        v
  merge to main
        |
        v
  dbt build --target prod   (scheduled, e.g. via dbt Cloud, Airflow,
                              or a cron-triggered container)
```

Because `dbt build` runs models and tests together in DAG order, a broken model that produces bad data can be caught by tests immediately downstream in the same run, before it ever reaches a table analysts query — this is the concrete mechanism behind "we test our data pipeline like we test our code," and it's why `dbt build`, not a bare `dbt run`, is the command that actually belongs in CI.

---

## Key Takeaways

- Staging (1:1 source mapping, views), intermediate (joins + business logic, tables/ephemeral), and marts (final `fct_*`/`dim_*` tables analysts query) is the standard three-layer project structure — it's the concrete, practical answer to "how do you structure a dbt project."
- Generic tests (`unique`, `not_null`, `accepted_values`, `relationships`) are reusable, YAML-declared, column-level assertions; singular tests are hand-written SQL for cross-row/cross-table business rules. Both follow the same convention: the underlying query passes when it returns zero rows.
- Macros are reusable Jinja-templated SQL; `dbt_utils` is the standard community package for problems (surrogate keys, date spines, pivoting) that come up in nearly every project.
- Sources plus freshness checks catch a class of bug tests can't: data that's technically correct but too stale to trust, typically caused by a silently-broken upstream extraction job.
- `dbt build` — not `dbt run` alone — is the command that belongs in CI/CD, because it runs models and tests together in DAG order, catching a bad model before it reaches a table anyone queries.
