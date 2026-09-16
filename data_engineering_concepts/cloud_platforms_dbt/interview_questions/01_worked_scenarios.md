# 1. Worked Scenarios

Part of the [Interview Questions](README.md) series — see that index for
the full taxonomy of question types and how the files fit together.

This file is deliberately **code-free** — no `CREATE` statements, no
SQL, no Jinja. The point is to rehearse the *reasoning* an interviewer
is actually scoring: how you scope the problem, structure the answer,
and name trade-offs out loud. Once the reasoning is solid, the SQL/YAML
is easy — that's what `concepts/` and `practice/` are for.

Three scenarios, each a different question shape: structuring a dbt
project from scratch, choosing between two warehouses for a specific
workload, and diagnosing a real production problem from a description.

---

## Scenario A: Structure a dbt Project for a Mid-Size Company

**Interviewer prompt:**
> "Walk me through how you'd structure a dbt project for a company with
> a Postgres OLTP database, a Stripe billing integration, and a product
> events stream. Marketing, finance, and product all need different
> reporting."

### Step 1 — Ask clarifying questions before naming a single folder

- **How many source systems, and do any of them already have a
  well-known integration pattern?** → Confirmed three: Postgres (order/
  customer core data), Stripe (billing), product events (a
  clickstream-style event table). Stripe specifically has an existing
  package (`stripe` source conventions are well documented) worth
  reusing rather than reinventing.
- **Do the three consuming teams need the *same* customer/account
  definition, or can each have their own?** → Same underlying entity
  (a customer), but each team cares about different derived attributes
  (marketing: acquisition channel; finance: billing status; product:
  activation state). This is the signal for a single conformed
  `dim_customer`, extended by each mart layer rather than three
  separate customer tables.
- **Load frequency?** → Postgres and Stripe sync nightly via a managed
  connector (Fivetran-style); product events stream in near-real-time
  but are reported on with a next-day lag, so dbt itself runs on a
  nightly schedule against already-landed data — this is an ELT
  pattern, not a streaming-transformation problem (see
  `concepts/03_dbt_fundamentals_and_dag.md`, section 1).
- **Data volume?** → Product events are the highest-volume source by
  far (tens of millions of rows/day); orders and billing are orders of
  magnitude smaller. This flags exactly one place an incremental model
  will matter for cost, not the whole project.

### Step 2 — Name the layers before naming a single model

> "Staging: one model per raw source table, 1:1, renamed and cleaned,
> no joins, materialized as views. Intermediate: business-logic joins
> across staging models, one level up from any single source.
> Marts: final `fct_*`/`dim_*` tables, organized by *consuming team*,
> built from intermediate and staging models, materialized as tables
> (or incremental for the events-derived fact)."

Stating the three layers and *why* each one is materialized the way it
is — views for staging (thin, always-fresh), tables/incremental for
marts (heavier, queried directly by BI tools) — is worth more than
listing folder names, because it shows the materialization choice was
reasoned about per layer, not applied uniformly out of habit.

### Step 3 — Organize staging by source system

> "`models/staging/postgres/`, `models/staging/stripe/`,
> `models/staging/product_events/` — one subfolder per source, each
> with its own `_sources.yml` declaring that source's tables and
> freshness expectations, and one `stg_{source}__{table}.sql` per raw
> table."

This mirrors how the data actually arrives (per-connector, per-sync),
which keeps ownership and troubleshooting scoped: if Stripe's sync
breaks, only `stg_stripe__*` models and their `source freshness` checks
are affected, and that blast radius is visible in the folder structure
itself, not just in someone's memory.

### Step 4 — Name the intermediate models and what each one earns

> "`int_customers__unified` joins the Postgres customer record to
> Stripe's billing record on a shared account ID, producing one row per
> customer with both operational and billing attributes.
> `int_events__activity_daily` pre-aggregates the high-volume product
> events table down to one row per user per day — this is the
> *only* place the raw event volume is ever touched directly, and it's
> deliberately incremental, because re-scanning tens of millions of raw
> events every night for a project other models will `ref()` many times
> over is exactly the cost problem `concepts/05_cost_and_performance_optimization.md`
> is about."

Naming *which* intermediate model needs to be incremental, and why
(volume plus reuse), rather than defaulting every model to the same
materialization, is the concrete signal of someone who's actually run a
project like this before.

### Step 5 — Marts, grouped by consuming team

```
marts/
  finance/    fct_monthly_revenue, dim_subscriptions
  marketing/  fct_campaign_attribution, dim_customers (extended with acquisition_channel)
  product/    fct_daily_active_users, dim_users (extended with activation_state)
```

> "Every mart in every team's folder still traces back to the same
> conformed `int_customers__unified` — marketing's `dim_customers` and
> product's `dim_users` share the same `customer_id` lineage and the
> same underlying join logic, they just select and expose different
> columns for their own team's use. That's deliberate: if the two teams
> independently re-derived 'customer' inside their own marts, their
> dashboards could quietly drift out of agreement the moment either
> team's logic changed — the exact bug in
> `data_modeling/interview_questions/03_critique_and_debug.md`, Case 8,
> just expressed as separate dbt marts instead of separate OBTs."

### Step 6 — Tests, named per layer

> "Staging models get lightweight `not_null`/`unique` checks on natural
> keys — catching a broken source sync as early as possible in the DAG.
> Marts get the full set: `unique`/`not_null` on every surrogate key,
> `relationships` from every `fct_*` back to its `dim_*`, `accepted_values`
> on every status/tier column, plus singular tests for cross-table
> business rules like 'billing revenue reconciles to Stripe's own
> reported total.' `dbt build`, not bare `dbt run`, is what's wired into
> CI, specifically so a broken model is caught by its own tests before
> it reaches a table anyone downstream queries."

### Step 7 — Trade-offs, stated unprompted

> "I made `int_events__activity_daily` incremental because it's by far
> the highest-volume source and gets reused by multiple marts — that's
> the one place a full nightly rebuild would actually be expensive.
> Everything else in this project is small enough that a full nightly
> rebuild costs nothing meaningful, and I'd rather keep those models
> simple `table` rebuilds than add incremental complexity (and its
> failure modes — see
> `interview_questions/03_critique_and_debug.md`) anywhere it isn't
> earning its cost."

---

### Now You Try: A Three-Region Retailer Onboarding a New Warehouse

**Interviewer prompt:**
> "A retail company is migrating from a legacy on-prem warehouse to
> Snowflake, with point-of-sale data from three regions (each currently
> in its own schema, with slightly different column names for the same
> concepts) and a single new dbt project to unify them. Walk me through
> the project structure and the biggest risk in this specific migration."

Work through Steps 1–7 yourself, out loud, before reading the debrief.

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **Clarifying questions:** are the three regions' schemas genuinely
  the same entity with cosmetic naming differences (a "conforming"
  problem), or are there real business-logic differences (different
  tax rules, different currencies) that shouldn't be silently
  flattened together? → Assume mostly cosmetic (column naming), with a
  few real differences (currency) that need explicit handling, not
  hiding.
- **Structure:** one staging subfolder per region
  (`staging/region_us/`, `staging/region_eu/`, `staging/region_apac/`),
  each producing a *conformed* output shape (same column names, same
  types, currency converted to a common reporting currency) even
  though each region's raw source differs — the staging layer's whole
  job here is absorbing exactly this kind of naming/shape
  inconsistency before anything downstream ever sees it.
- **Intermediate:** a `int_sales__unified` model that simply
  `UNION ALL`s the three now-conformed staging outputs — because
  staging already did the hard work of making them shape-identical,
  the union itself is close to trivial, which is the entire point of
  putting the conforming logic in staging rather than in this model.
- **Marts:** built once, on top of the unified intermediate model — a
  single `fct_pos_sales` and `dim_stores`, not three regional copies.
- **The biggest risk, named explicitly:** silently getting the
  cosmetic-vs-real distinction wrong — flattening a *real* regional
  business-logic difference (e.g. EU includes VAT in `unit_price`
  where US doesn't) into a single unified model as if it were just a
  naming difference produces a schema that looks unified but is
  quietly wrong the moment someone sums revenue across regions. The
  fix isn't a dbt feature — it's insisting on a business-rule review of
  every column being conformed, region by region, before writing the
  staging SQL, not after a stakeholder notices EU revenue looks
  inflated.

</details>

---

## Scenario B: Choose Between Snowflake and BigQuery for a Specific Company

**Interviewer prompt:**
> "A mid-size ad-tech company is entirely on GCP already (BigQuery for
> logging, Google Ads/Analytics data feeding in natively), has a small
> data team of two engineers, and needs to support both scheduled
> reporting and unpredictable, very large ad-hoc queries during
> incident investigations. Which warehouse, and why?"

### Step 1 — Resist a generic feature-checklist answer

A weak answer recites "Snowflake has time travel, BigQuery is
serverless" without connecting either fact to *this* company. A strong
answer starts by naming which details in the prompt are actually
load-bearing:

- **Already fully on GCP, with native GCP data sources feeding in.**
  BigQuery has first-party integration with Google Ads/Analytics data
  exports — choosing Snowflake here means either an extra ETL hop or a
  third-party connector that GCP-native tooling wouldn't need at all.
- **A team of two engineers.** This is a strong signal against any
  platform choice that adds *operational* burden — cluster sizing,
  warehouse count planning, credit monitoring — that a small team has
  to actively manage day to day.
- **Unpredictable, very large ad-hoc queries during incidents.** This
  is the scenario BigQuery's serverless, pay-per-query model is
  specifically good at: a huge one-off incident-investigation query
  doesn't require anyone to have pre-provisioned a bigger warehouse for
  it, and it doesn't compete with the scheduled reporting workload for
  a shared, fixed compute pool.

### Step 2 — State the recommendation and justify it against those specific details, not a generic list

> "BigQuery. Three of the four details in the prompt point the same
> direction: GCP-native data sources avoid an extra integration hop,
> a two-person team benefits from not managing warehouse sizing at
> all, and serverless on-demand pricing handles an unpredictable huge
> query without anyone needing to provision for it in advance. The one
> detail that could argue against BigQuery — cost predictability for
> the scheduled reporting half of the workload — is solved by BigQuery
> flat-rate slot reservations for exactly that portion, while leaving
> the unpredictable incident-query half on the flexible on-demand
> model."

### Step 3 — Name what you'd give up, unprompted

> "Snowflake's data-sharing features and multi-cloud portability
> aren't relevant here — this company isn't sharing data externally and
> has no stated multi-cloud requirement, so that's not a cost worth
> naming as a real trade-off. The genuine trade-off is Snowflake's more
> mature workload-isolation model (separate virtual warehouses per
> team) versus BigQuery's reservation/on-demand split doing something
> similar but less granular — for a two-person team with two workload
> shapes, that's an acceptable simplification, not a real gap."

### Step 4 — Anticipate the natural follow-up

**Q: "What would change your answer?"**
> "If this company later needed to securely share query-able data with
> external partners (a common ad-tech need — sharing attribution data
> with advertisers), Snowflake's secure data sharing is a materially
> stronger fit than BigQuery's authorized views/Analytics Hub
> equivalent for a team this size to stand up and maintain. That's the
> point at which I'd revisit this recommendation rather than treat it
> as settled forever."

---

## Scenario C: Diagnose a Slow, Expensive Nightly dbt Run

**Interviewer prompt:**
> "Our nightly `dbt build` used to take 45 minutes. Over the last two
> months it crept up to 4 hours, and our Snowflake bill for that
> warehouse roughly quadrupled in the same period. Nothing in the dbt
> project's SQL has been touched recently. Walk me through how you'd
> find and fix the cause."

### Step 1 — Refuse to guess before gathering evidence

> "Before touching any model, I'd pull dbt's own run metadata —
> `target/run_results.json` from recent runs, or whatever the
> orchestrator (Airflow, dbt Cloud) logs per-model timing as — to see
> *which specific models* got slower, rather than assuming it's
> whichever model looks most complex. A 4-hour run is very rarely
> uniformly slower across every model; it's usually one or a handful of
> models that degraded sharply, dragging the total up."

This mirrors the diagnostic discipline in
`concepts/05_cost_and_performance_optimization.md`, section 6: identify
which axis and which specific object moved before proposing a fix.

### Step 2 — Correlate the timing data with "what changed"

> "'Nothing in the SQL changed' rules out a model-logic regression, but
> it doesn't rule out the *data* changing shape underneath unchanged
> SQL. The two most likely categories, given that framing:
>
> 1. **A table a model reads from grew substantially in row count**
>    (e.g. a source table doubled or tripled as the business scaled),
>    and a `table`-materialized model downstream is now doing a full
>    rebuild over a much larger input every night, even though its own
>    SQL is untouched.
> 2. **An incremental model's `is_incremental()` filter quietly stopped
>    narrowing anything** — for instance if the source's watermark
>    column (`updated_at`) started arriving with nulls or out-of-order
>    timestamps for a subset of rows, silently causing the model to
>    reprocess far more than the intended delta every run, without
>    erroring."

### Step 3 — Confirm before fixing

> "I'd check the row counts and query profiles for whichever specific
> model(s) the timing data flagged, comparing today's actual scanned-
> bytes/row-count against two months ago — Snowflake's query history
> and `INFORMATION_SCHEMA` give this directly. If it's case 1 (organic
> growth under a `table` model), the fix is converting that specific
> model to `incremental`, if its logic supports a clean watermark, or
> narrowing what it selects if the business logic allows. If it's case
> 2 (a broken incremental filter), the fix is auditing the watermark
> column's data quality upstream and adding a test that would have
> caught it — `dbt source freshness` or a singular test asserting the
> watermark column has no unexpected nulls, so this class of silent
> regression can't recur invisibly."

### Step 4 — Close with the monitor, not just the fix

> "Whichever specific cause it turns out to be, I'd also add a
> lightweight per-model runtime alert (many teams do this by parsing
> `run_results.json` after every scheduled run and flagging any model
> whose runtime jumped materially versus its trailing average) —
> otherwise the *next* regression like this one again goes unnoticed
> for two months instead of being caught within a few days."

**The interview tell across this whole scenario:** never proposing a
fix ("just make everything incremental," "just resize the warehouse")
before naming how you'd first identify *which specific model* is
responsible — a diagnosis-first answer is what's actually being scored
here, not a list of generically plausible causes.
