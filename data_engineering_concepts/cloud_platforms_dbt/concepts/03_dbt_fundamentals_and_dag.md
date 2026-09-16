# Concept 03: dbt Fundamentals — the DAG, `ref()`/`source()`, and Materializations

**Covers:**
- Where dbt sits in a modern ELT stack, and why "T" is the only letter it owns
- `ref()` and `source()` — how a dbt project builds its dependency graph automatically
- The DAG: topological execution order, and what a circular dependency looks like
- The four materializations — view, table, incremental, ephemeral — and when to choose each
- Incremental strategies in depth: `append`, `merge`, `delete+insert`, and the `is_incremental()` macro
- The core dbt commands (`run`, `test`, `build`, `seed`, `snapshot`, `compile`, `docs generate`) and the flags you'll actually use

dbt is one of the most commonly *named* tools in modern data engineering job postings and interviews — "do you know dbt" is often asked before "what warehouse have you used." This file and `04_dbt_testing_macros_and_project_structure.md` together are the deepest two files in this folder for exactly that reason.

*A small "mini-dbt" engine below runs real Python against `sqlite3` to make the DAG resolution and materialization logic concrete — every function it's simulating is named in the docstring-equivalent comments alongside real dbt SQL/YAML. Nothing here needs a warehouse or a dbt install to follow along, but every dbt-specific SQL/Jinja block is exactly what you'd write in a real project.*

---

## 1. Where dbt Fits: ELT, Not ETL

dbt (**data build tool**) transforms data that already lives in your warehouse, using nothing but SQL `SELECT` statements — no `CREATE TABLE`, no manual DDL, no orchestration of extract/load. That's a deliberate scope boundary:

```
E (Extract)         L (Load)              T (Transform)
raw source system -> warehouse (raw)  ->  dbt turns raw into clean, tested,
(Fivetran, Airbyte,    (Snowflake/BigQuery/    documented models
 custom connectors)     Redshift)              (dbt's entire job)
```

This is the **ELT** pattern (load first, transform inside the warehouse after), which displaced classical **ETL** (transform *before* loading, usually on a separate compute cluster) once cloud warehouses got cheap and powerful enough to do the transforming themselves. dbt doesn't move data between systems and doesn't schedule extraction jobs — it assumes raw data is already sitting in a schema somewhere, and its entire job is turning that raw data into clean, tested, documented, versioned SQL models.

```
my_dbt_project/
├── dbt_project.yml
├── models/
│   ├── staging/
│   │   ├── stg_orders.sql
│   │   └── stg_customers.sql
│   ├── intermediate/
│   │   └── int_orders_enriched.sql
│   └── marts/
│       └── fct_daily_revenue.sql
├── tests/
│   └── assert_positive_revenue.sql
├── macros/
│   └── cents_to_dollars.sql
├── seeds/
│   └── country_codes.csv
└── snapshots/
    └── scd_customers.sql
```

A **model** is nothing more than a `.sql` file holding a `SELECT` statement. dbt reads it, wraps it in whatever DDL the chosen materialization needs (`CREATE VIEW`, `CREATE TABLE AS`, an `INSERT` for an incremental run), and executes it against the warehouse — you never write the `CREATE`/`INSERT` yourself.

---

## 2. `ref()` and `source()`: How the DAG Gets Built

Every model references its inputs through two Jinja functions instead of hardcoding schema-qualified table names:

- **`source('raw', 'orders')`** — points at a raw table dbt does not manage, declared once in a YAML file.
- **`ref('stg_orders')`** — points at another dbt model, resolved to that model's actual materialized name/schema at compile time.

```sql
-- models/staging/stg_orders.sql
{{ config(materialized='view') }}

SELECT
    id AS order_id,
    customer_id,
    CAST(amount_cents AS FLOAT) / 100 AS amount_dollars,
    status,
    created_at
FROM {{ source('raw', 'orders') }}
```

```yaml
# models/staging/_sources.yml
version: 2
sources:
  - name: raw
    database: analytics
    schema: raw_data
    tables:
      - name: orders
      - name: customers
```

Because every model declares its inputs this way instead of writing a literal table name, dbt can parse every `.sql` file in the project, extract every `ref()`/`source()` call, and build a full dependency graph — the **DAG** (directed acyclic graph) — without a human ever drawing it.

```python
import re
from collections import defaultdict

def build_dag(models: dict[str, str]) -> list[str]:
    """models: {model_name: sql_text}. Returns execution order via Kahn's algorithm."""
    in_degree = defaultdict(int)
    graph = defaultdict(list)
    for name, sql in models.items():
        in_degree.setdefault(name, 0)
        for dep in re.findall(r"ref\('(\w+)'\)", sql):
            if dep in models:
                graph[dep].append(name)
                in_degree[name] += 1

    queue = [n for n in models if in_degree[n] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(models):
        missing = set(models) - set(order)
        raise ValueError(f"Circular dependency detected: {missing}")
    return order

models = {
    "stg_orders": "SELECT * FROM source('raw','orders')",
    "stg_customers": "SELECT * FROM source('raw','customers')",
    "int_orders_enriched": "SELECT * FROM ref('stg_orders') JOIN ref('stg_customers')",
    "fct_daily_revenue": "SELECT * FROM ref('int_orders_enriched')",
}
print(" -> ".join(build_dag(models)))
```

```
stg_orders -> stg_customers -> int_orders_enriched -> fct_daily_revenue
```

```
              stg_orders  ----\
                                >-- int_orders_enriched --> fct_daily_revenue
              stg_customers ---/
```

If two models mutually `ref()` each other (or a longer cycle forms across three or more models), `_topological_sort` above raises exactly the error a real `dbt run` raises at compile time — dbt refuses to guess an order and fails the whole run before executing a single model, which is the correct behavior: a cycle means the dependency itself is contradictory, not just ambiguous.

---

## 3. Materializations: View, Table, Incremental, Ephemeral

`{{ config(materialized=...) }}` at the top of a model controls how dbt persists it. This single choice is one of the most common "explain the trade-off" interview questions in this whole topic.

| Materialization | Stored? | Rebuild behavior | Best for |
|---|---|---|---|
| `view` | No | `CREATE VIEW` — recomputed on every query | Lightweight staging models, rarely-queried models, always-fresh reads |
| `table` | Yes | `CREATE TABLE AS` — full rebuild every run | Heavier transforms queried often; marts that BI tools hit directly |
| `incremental` | Yes | Only new/changed rows processed after the first run | Large fact tables where a full rebuild is too slow/expensive |
| `ephemeral` | No | Never persisted — inlined as a CTE into whatever refs it | Small reusable logic you don't want cluttering the warehouse's schema browser |

```sql
{{ config(materialized='view') }}        -- CREATE VIEW AS ...
{{ config(materialized='table') }}       -- CREATE TABLE AS ...  (full rebuild)
{{ config(materialized='incremental') }} -- INSERT/MERGE new rows only, after the first run
{{ config(materialized='ephemeral') }}   -- becomes a WITH ... AS (...) CTE wherever ref()'d
```

**View** is the right default for staging models: they're thin (rename/cast/clean, no heavy joins), so recomputing on every query is cheap, and always-fresh is exactly what you want one layer above raw source data.

**Table** earns its keep once a model does real aggregation or joins that would be wasteful to re-run on every single downstream query — most marts (`fct_*`/`dim_*`) are tables for this reason.

**Ephemeral** is a code-organization tool, not a performance one: it lets you factor out repeated logic into its own file for readability without adding a permanent object to the warehouse. It has a real cost, though — an ephemeral model can't be queried directly (only through whatever refs it), and if the *same* ephemeral model is ref'd by five downstream models, its SQL gets **inlined five separate times**, once per CTE, rather than computed once and reused — for anything non-trivial in cost, that's a reason to promote it to a view instead.

**Incremental** is the one worth a full section of its own.

---

## 4. Incremental Models: Strategies and `is_incremental()`

An incremental model's first run behaves like a `table` — a full `CREATE TABLE AS SELECT`. Every subsequent run instead filters the model's own `SELECT` down to only new or changed rows, using the `is_incremental()` macro, which evaluates `true` only when the target table already exists and `--full-refresh` wasn't passed:

```sql
-- models/marts/fct_events.sql
{{ config(materialized='incremental', unique_key='event_id') }}

SELECT
    id AS event_id,
    user_id,
    event_type,
    created_at
FROM {{ source('raw', 'events') }}

{% if is_incremental() %}
    -- this filter only applies on runs AFTER the first --
    -- on the very first run, is_incremental() is false and
    -- the whole source table is selected
    WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
```

`{{ this }}` refers to the model's own already-materialized table — reading `MAX(created_at)` from a table the same query is about to insert into is the standard incremental watermark pattern.

Once dbt has the filtered set of new/changed rows, the **incremental strategy** controls exactly how they get merged into the existing table:

| Strategy | Behavior | When to use |
|---|---|---|
| `append` | `INSERT` the new rows, no dedup | Pure event/log data that's never updated after landing (e.g. clickstream) |
| `merge` | `MERGE ... WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT`, keyed on `unique_key` | Warehouses with native `MERGE` (Snowflake, BigQuery) and rows that can be updated after first appearing (e.g. an order whose status changes) |
| `delete+insert` | `DELETE` rows matching the new batch's keys, then `INSERT` the new batch | Warehouses without a native `MERGE` (Redshift, historically), or a partition-level "delete and reload" pattern |

```python
def materialize_incremental(cur, name, sql, exists, unique_key=None, strategy="merge"):
    if not exists:
        cur.execute(f"CREATE TABLE {name} AS {sql}")          # first run: full refresh
    elif strategy == "append":
        cur.execute(f"INSERT INTO {name} {sql}")               # no dedup at all
    elif strategy == "merge" and unique_key:
        cur.execute(f"""
            DELETE FROM {name} WHERE {unique_key} IN (SELECT {unique_key} FROM ({sql}))
        """)                                                     # simulate MERGE's "matched" branch
        cur.execute(f"INSERT INTO {name} {sql}")                # simulate MERGE's "not matched" branch
    elif strategy == "delete+insert":
        cur.execute(f"DELETE FROM {name} WHERE {unique_key} IN (SELECT {unique_key} FROM ({sql}))")
        cur.execute(f"INSERT INTO {name} {sql}")
```

Note that a correct `merge`/`delete+insert` simulation and a naive `append` differ in exactly one dangerous way: **without a `unique_key`, dbt cannot deduplicate**, and an incremental model configured as `merge` but never given `unique_key` silently behaves like `append` — every re-run of the same source row inserts a brand new duplicate row instead of updating the existing one. This exact bug is worked through end to end in `interview_questions/03_critique_and_debug.md`.

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge'
) }}

SELECT id AS order_id, customer_id, status, updated_at
FROM {{ source('raw', 'orders') }}
{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

`--full-refresh` forces a complete rebuild, ignoring all prior incremental state — the standard fix when the model's logic itself changed (a new column, a corrected join) and the existing incrementally-built table no longer reflects what a from-scratch build would produce:

```bash
dbt run --select fct_events --full-refresh
```

---

## 5. dbt Commands and Flags

| Command | What it does |
|---|---|
| `dbt run` | Executes all models in DAG order, creating/updating views and tables |
| `dbt test` | Runs all schema + data tests (see `04_dbt_testing_macros_and_project_structure.md`) |
| `dbt build` | Runs models, tests, snapshots, and seeds together, in dependency order — the standard CI/CD command |
| `dbt seed` | Loads CSV files from `seeds/` into warehouse tables — good for small static lookup data |
| `dbt snapshot` | Captures SCD Type 2 history of a source table (see the cross-reference below) |
| `dbt compile` | Renders Jinja into raw SQL without executing — the fastest way to debug what a model *actually* sends to the warehouse |
| `dbt docs generate` | Builds a static documentation site with a DAG visualization and column-level docs |
| `dbt source freshness` | Checks whether a source table's most recent load is within an acceptable age |

```bash
dbt run --select stg_orders          # run only this model
dbt run --select +stg_orders         # run this model and everything upstream of it
dbt run --select stg_orders+         # run this model and everything downstream of it
dbt run --full-refresh                # force a full rebuild of incremental models
dbt run --target prod                 # run against the production connection profile
dbt run --vars '{lookback_days: 7}'   # pass variables into Jinja templates
```

`dbt snapshot` deserves one explicit distinction, since it's a frequent follow-up: it implements SCD Type 2 against a source that only exposes *current* state, by diffing the source against the last snapshot on every run and inserting a new Type 2 row whenever it detects a change — automating exactly the expire-then-insert pattern covered in `data_modeling/concepts/04_slowly_changing_dimensions.md`. An incremental *model* is a more general-purpose materialization strategy for any model (usually a large fact table) and has nothing to do with tracking dimension history by itself.

---

## Key Takeaways

- dbt owns only the "T" in ELT — it transforms data already sitting in a warehouse using pure SQL `SELECT` statements, with extraction/loading handled by separate tools upstream.
- `ref()` and `source()` are how a project's dependency graph gets built automatically — every model declares its own inputs, and dbt topologically sorts the whole project into a DAG before running anything; a cycle fails the run before a single model executes.
- Materializations, in order of increasing persistence cost and decreasing per-query cost: ephemeral (CTE, never stored) → view (recomputed every query) → table (full rebuild every run) → incremental (only new/changed rows processed after the first run).
- Incremental models rely on `is_incremental()` to conditionally filter to new/changed rows, and on an incremental strategy (`append`, `merge`, `delete+insert`) to decide how those rows land — `merge`/`delete+insert` without a correct `unique_key` silently degrades into duplicate-producing `append` behavior.
- `dbt build` (run + test + snapshot + seed, in DAG order) is the standard single command wired into CI/CD; `dbt compile` is the fastest way to see the exact SQL Jinja produced when a model isn't behaving as expected.
