# 3. Critique & Debug: "What's Wrong With This?"

Part of the [Interview Questions](README.md) series.

A different interview mode from [file 1](01_worked_scenarios.md):
instead of "design/diagnose something," you're handed a model, a
config, or a described symptom and asked **"what's wrong with this?"**
This tests whether you can *read* a dbt project or a warehouse setup
critically, not just produce one. Every case below is described in
plain prose or minimal SQL — because the skill being tested is spotting
the flaw the way it'd actually be described to you in an interview.

Read the symptom, form your diagnosis, then expand the debrief.

---

## Case 1: The Incremental Model That Duplicates Every Row It Reprocesses

**Setup:**

```sql
{{ config(materialized='incremental', incremental_strategy='merge') }}

SELECT id AS order_id, customer_id, status, updated_at
FROM {{ source('raw', 'orders') }}
{% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

An upstream system occasionally re-sends an order with a corrected
`status` (same `order_id`, newer `updated_at`). After that happens, a
`unique` test on `fct_orders.order_id` starts failing with duplicate
rows.

<details>
<summary>Debrief</summary>

**Diagnosis:** `incremental_strategy='merge'` is set, but there's no
`unique_key` configured. Without `unique_key`, dbt has no column to
match "this incoming row" against "an existing row" — a `merge`
strategy with no key to merge on silently behaves like `append`: every
reprocessed order lands as a brand-new row instead of updating the
existing one, even though the model is nominally an "upsert."

**Fix:** add `unique_key='order_id'` to the config:

```sql
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='order_id') }}
```

With the key present, the corrected row replaces the existing one
(delete-then-insert or a native `MERGE`, depending on the warehouse)
instead of duplicating it.

**The interview tell:** naming `unique_key` as *the* missing piece
immediately — rather than suspecting the `is_incremental()` filter or
the watermark column — is what separates someone who's actually
configured an incremental model in a real project from someone
reciting the concept.

</details>

---

## Case 2: The `is_incremental()` Model That's Never Actually Incremental

**Setup:**

```sql
{{ config(materialized='incremental', unique_key='event_id') }}

SELECT id AS event_id, user_id, event_type, created_at
FROM {{ source('raw', 'events') }}
WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
```

The model runs successfully every night, but a teammate notices its
runtime and cost never dropped after the "incremental" rewrite — every
run still scans and reprocesses the entire multi-year source table.

<details>
<summary>Debrief</summary>

**Diagnosis:** the `WHERE created_at > (SELECT MAX(created_at) FROM
{{ this }})` filter is missing the `{% if is_incremental() %}` guard.
On the very first run this is harmless (the table doesn't exist yet,
so this specific bug wouldn't even be visible), but on *every*
subsequent run, this filter is unconditionally present in the compiled
SQL — which sounds correct, except this model was very likely converted
from a `table` materialization by only changing the `config()` line and
never adding the conditional Jinja block. Depending on exactly what's
missing, this shows up two ways: either the filter is present but
unconditional (still technically "incremental behavior" every run
after the first, so this particular symptom wouldn't occur), or — the
actual bug here — the filter was never added and the model always
selects the *full* source table, appending or merging in the entirety
of `raw.events` every single night regardless of what already exists in
`{{ this }}`.

**Fix:** wrap the watermark filter in `{% if is_incremental() %}`, and
verify with `dbt compile` that the *compiled* SQL for a non-first run
actually contains the filter:

```sql
SELECT id AS event_id, user_id, event_type, created_at
FROM {{ source('raw', 'events') }}
{% if is_incremental() %}
    WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
```

**The interview tell:** reaching for `dbt compile` (not `dbt run`) as
the diagnostic step — it renders the Jinja into raw SQL without
executing anything, which is the fastest way to confirm what a model
*actually* sends to the warehouse rather than guessing from the source
file. See `concepts/03_dbt_fundamentals_and_dag.md`, section 5.

</details>

---

## Case 3: The Warehouse Bill That Never Goes Down Overnight

**Setup:** A Snowflake warehouse dedicated to ad-hoc analyst queries
runs from 9am to 6pm on weekdays. Analysts confirm nobody queries it
outside those hours. The monthly credit usage report shows the
warehouse accruing roughly the same cost at 2am as it does at 2pm.

<details>
<summary>Debrief</summary>

**Diagnosis:** `AUTO_SUSPEND` either isn't configured or is set to an
impractically long interval — the warehouse is staying `RUNNING`
(billing credits) indefinitely once resumed, regardless of whether any
query is actually executing against it.

**Fix:**

```sql
ALTER WAREHOUSE analytics_wh SET AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
```

A short `AUTO_SUSPEND` (60 seconds is a common aggressive default) means
the warehouse stops accruing cost within a minute of its last query,
and `AUTO_RESUME` means the very next query still starts it back up
transparently, with only a few seconds of resume latency — the
trade-off strongly favors suspending aggressively for an ad-hoc/
analyst-facing warehouse, since resume time is nearly free.

**The interview tell:** naming `AUTO_SUSPEND` immediately, rather than
suggesting a smaller warehouse size — the symptom (identical cost at
2am and 2pm, when nobody's querying at 2am) specifically points at idle
compute time, not at warehouse *size* being wrong for the workload. See
`concepts/05_cost_and_performance_optimization.md`, section 3.

</details>

---

## Case 4: The BigQuery Table That's Still Scanning Everything

**Setup:**

```sql
CREATE TABLE `project.dataset.sales`
PARTITION BY DATE(sale_date)
AS SELECT * FROM `project.dataset.raw_sales`;
```

```sql
SELECT SUM(revenue)
FROM `project.dataset.sales`
WHERE FORMAT_DATE('%Y-%m', sale_date) = '2024-06';
```

The billing dashboard shows this query scanning the entire multi-year
table, not just June 2024.

<details>
<summary>Debrief</summary>

**Diagnosis:** the table is correctly partitioned, but the query wraps
the partitioned column (`sale_date`) inside `FORMAT_DATE(...)` before
comparing it. BigQuery can't determine which partitions could possibly
satisfy `FORMAT_DATE(sale_date, ...) = '2024-06'` without evaluating
that function against every row first — the filter defeats pruning
even though partitioning itself is configured correctly.

**Fix:** filter on the raw partitioned column, as a literal range:

```sql
SELECT SUM(revenue)
FROM `project.dataset.sales`
WHERE sale_date BETWEEN '2024-06-01' AND '2024-06-30';
```

**The interview tell:** recognizing that this is a *query-writing* bug,
not a *table-design* bug — the `PARTITION BY` clause is entirely
correct, so the fix is teaching the team the raw-column-filter
convention (and possibly adding it as a code-review checklist item),
not touching the DDL at all. See
`concepts/05_cost_and_performance_optimization.md`, section 2, and
`concepts/02_snowflake_bigquery_redshift.md`, section 4.

</details>

---

## Case 5: The Redshift Table Clustered for the Wrong Query

**Setup:** `fact_sales` in Redshift is defined as:

```sql
CREATE TABLE fact_sales (
    sale_id INT, customer_id INT, region VARCHAR(20), sale_date DATE, revenue DECIMAL(10,2)
) DISTKEY(customer_id) SORTKEY(region);
```

Every dashboard query filters on a date range (`WHERE sale_date BETWEEN
...`); almost none filter on `region` alone. Query performance is
noticeably worse than expected for a table this size.

<details>
<summary>Debrief</summary>

**Diagnosis:** the `SORTKEY` was chosen for a column (`region`) that
the actual query workload rarely filters on, instead of the column
(`sale_date`) that nearly every real query filters by. Sorting the
table's blocks by `region` gives zero benefit to a date-range filter,
because rows for any given date range are scattered across
region-sorted blocks rather than co-located — so a date-filtered query
still has to scan nearly every block, just as it would with no sort key
at all.

**Fix:** re-create the table (or use `ALTER TABLE ... ALTER SORTKEY`,
where supported) with the sort key matching actual usage:

```sql
CREATE TABLE fact_sales (
    sale_id INT, customer_id INT, region VARCHAR(20), sale_date DATE, revenue DECIMAL(10,2)
) DISTKEY(customer_id) SORTKEY(sale_date);
```

**The interview tell:** naming explicitly that a sort/cluster key
should be chosen from *actual query patterns*, not assumed from the
schema alone — `region` looks like a reasonable filter column in the
abstract, but the fix requires checking what analysts actually filter
on, the same discipline named in
`concepts/02_snowflake_bigquery_redshift.md`, section 5, and
`concepts/05_cost_and_performance_optimization.md`, section 2.

</details>

---

## Case 6: The Test Suite That Passes While the Data Is Silently Stale

**Setup:** A dbt project has thorough schema tests on every mart —
`unique`, `not_null`, `relationships` everywhere they belong — and
`dbt build` passes green every night. A stakeholder discovers the
"active users" dashboard hasn't reflected any new signups in eleven
days, even though every test in the project is passing.

<details>
<summary>Debrief</summary>

**Diagnosis:** schema and singular tests only check the rows that
*did* make it into a model — they say nothing about whether the
upstream source itself is still being refreshed. If the raw events
sync silently stopped eleven days ago, every row already in the
warehouse is perfectly `not_null`/`unique`/well-formed; there's simply
nothing new to fail a test against. This is exactly why `dbt test`
passing is not the same claim as "our data is current."

**Fix:** add a `freshness` block to the relevant `sources.yml` entry
and run `dbt source freshness` as part of the scheduled job (ideally
failing the pipeline, or at minimum alerting, when a source exceeds
`error_after`):

```yaml
sources:
  - name: raw
    loaded_at_field: _etl_loaded_at
    freshness:
      warn_after: {count: 12, period: hour}
      error_after: {count: 24, period: hour}
    tables:
      - name: events
```

**The interview tell:** distinguishing "tests passing" from "data is
current" explicitly, and naming `dbt source freshness` as the specific
mechanism that closes this gap — a candidate who only says "add more
tests" hasn't identified that no *test*, however well-written, can
detect an absence of new rows on its own.
`concepts/04_dbt_testing_macros_and_project_structure.md`, section 5.

</details>

---

## Case 7: The Ephemeral Model That Made Everything Slower

**Setup:** `int_orders_enriched` is configured `materialized='ephemeral'`
and does a moderately expensive three-table join. It's `ref()`'d by
six different downstream marts. After converting a previously-`table`
model to `ephemeral` (to "reduce clutter" in the warehouse's schema
browser), the full `dbt build` runtime increased noticeably.

<details>
<summary>Debrief</summary>

**Diagnosis:** an ephemeral model has no persisted table or view behind
it — its SQL is inlined as a CTE into *every* model that `ref()`s it.
With six downstream marts each referencing it, the same three-table
join now gets recompiled and re-executed six separate times per
`dbt build` run instead of once, multiplying its actual compute cost by
the number of references, in exchange for a purely cosmetic benefit
(one fewer object visible in the schema browser).

**Fix:** materialize it as a `view` (recomputed on read, but only once
per query rather than once per reference within the same query, and
queryable directly for debugging) or, if it's genuinely expensive and
reused often, as a `table`.

**The interview tell:** knowing the concrete cost mechanism of
`ephemeral` — SQL duplicated once per reference — rather than treating
"ephemeral" as simply "the lightweight option." It's a code-
organization tool, not a performance one; the moment a model is reused
more than once or twice and isn't trivial, ephemeral is very often the
wrong choice. `concepts/03_dbt_fundamentals_and_dag.md`, section 3.

</details>

---

**Next:** [04 — Curveballs & Trade-offs](04_curveballs_tradeoffs.md)
