# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design conversations.
This file is the other interview mode: **fast, direct definitional
questions** with no scenario attached — the kind asked in a phone
screen, or dropped mid-conversation to check you actually understand a
term you just used. Answer each one out loud in under 30 seconds before
reading the model answer.

Every term used here is demonstrated somewhere in file 1 or in
`concepts/` — the cross-references point back to the concrete moment it
showed up, so a shaky answer has somewhere to go for the worked version.

---

## Foundational

**Q: What's the difference between OLTP and OLAP?**
> OLTP (Online Transaction Processing) systems run the application
> itself — fast, small, single-row reads and writes, normalized to keep
> writes consistent (an order-processing database). OLAP (Online
> Analytical Processing) systems answer analytical questions across
> millions of rows — optimized for large scans and aggregation, usually
> denormalized. Data modeling for interviews is almost always about the
> OLAP side; the source systems it pulls from are OLTP.

**Q: What is "grain," and why declare it first?**
> Grain is the answer to "what does one row in this table represent?"
> Every dimension, measure, and query correctness question traces back
> to it. Declaring it first (Step 2 in every scenario in
> [file 1](01_worked_scenarios.md)) prevents a design where half the
> columns implicitly assume a different grain than the other half — the
> most common source of silently wrong aggregates.

**Q: Normalize or denormalize — how do you decide?**
> Normalize (reduce redundancy, enforce via foreign keys) when the
> priority is write consistency and storage efficiency — the OLTP side.
> Denormalize (flatten, accept redundancy) when the priority is read
> speed and simplicity for analytics — the OLAP side. Most warehouse
> interviews expect you to default toward denormalized star schemas
> and justify any normalization you keep, not the other way around.

**Q: Walk through 1NF, 2NF, 3NF in one sentence each.**
> 1NF: every column holds a single atomic value, no repeating groups
> (no comma-separated lists in a cell). 2NF: 1NF, plus every non-key
> column depends on the *whole* primary key, not just part of it
> (relevant only when the key is composite). 3NF: 2NF, plus no non-key
> column depends on another non-key column (no transitive dependency) —
> e.g. storing both `zip_code` and `city` when city is fully determined
> by zip is a 3NF violation.

**Q: What does BCNF add on top of 3NF?**
> For every functional dependency `A -> B`, `A` must be a superkey — even
> if `A` is a non-key attribute. It closes a rare loophole where a table
> is technically 3NF but still has a non-key column determining another
> column (a professor determining the subject they teach, in a table
> keyed on student+subject). Worked example:
> `concepts/01_normalization.md`, section 5. Rarely the center of an
> interview question on its own; naming it correctly when asked is
> usually enough.

---

## Schema Shapes

**Q: Star vs. snowflake — when do you actually pick snowflake?**
> Star by default. Snowflake earns its keep when a dimension's
> hierarchy is large, deep, and frequently queried at an intermediate
> level on its own (e.g. a 50,000-SKU product catalog, or the ~70,000-code
> ICD-10 diagnosis hierarchy in
> [file 1's healthcare scenario](01_worked_scenarios.md)) — the storage
> savings and update simplicity outweigh the extra joins. Worked
> comparison: `concepts/03_star_snowflake_schema.md`.

**Q: What's a fact table vs. a dimension table, in one line each?**
> A fact table holds the numeric measurements of a business event/state
> at a declared grain, plus foreign keys to describe it. A dimension
> table holds the descriptive attributes (who/what/when/where) that
> give those measurements context and are used to filter and group them.

**Q: What's "One Big Table" (OBT), and when would you use it instead of
a star schema?**
> OBT pre-joins a fact and all its dimensions into a single wide,
> heavily denormalized table — no joins needed at query time at all.
> It trades storage and update cost (every dimension attribute is
> repeated on every fact row) for query simplicity and speed, which
> matters most for BI tools/end users who can't or shouldn't write
> joins, or for a wide feature table feeding an ML model. A star schema
> stays the better default when multiple fact tables need to share
> conformed dimensions consistently — OBT duplicates that logic per
> table instead of centralizing it. Full decision framework:
> `concepts/05_one_big_table_and_lakehouse_modeling.md`.

**Q: Kimball vs. Inmon vs. Data Vault — what's the one-sentence
distinction?**
> Kimball builds bottom-up from business-process-specific star schemas
> (dimensional, what this whole course focuses on). Inmon builds
> top-down from a single normalized enterprise data warehouse, with
> dimensional data marts derived from it afterward. Data Vault sits
> between the two for very large, fast-changing enterprises — it splits
> entities into hubs (business keys), links (relationships), and
> satellites (attributes/history) specifically to make the *loading*
> process itself insertable-only and highly parallel; it's rarely the
> right answer for an analytics-facing interview question but is worth
> naming if asked "what else is out there." Full treatment:
> `concepts/06_data_vault_modeling.md`.

**Q: How does a medallion (bronze/silver/gold) lakehouse layering relate
to Kimball dimensional modeling?**
> It's not a competing methodology — it's the same normalize-then-
> denormalize trade-off packaged as physical pipeline stages. Bronze is
> raw, as-landed data; silver is cleaned/conformed (roughly the 3NF-style
> cleanup from `concepts/01_normalization.md`); gold is where star
> schemas or OBTs actually get built, and it's the only layer most
> analysts query directly. In a dbt project, staging models are "silver"
> and marts (`dim_*`/`fact_*`) are "gold." See
> `concepts/05_one_big_table_and_lakehouse_modeling.md`, sections 2-3.

---

## Fact Table Types & Measures

**Q: Name the three classic fact table types.**
> **Transaction fact** — one row per discrete event, append-only, never
> updated (`fact_order_lines`,
> [file 1's e-commerce scenario](01_worked_scenarios.md)).
> **Periodic snapshot** — one row per entity per fixed time interval, a
> frozen point-in-time measurement (`fact_mrr_snapshot`,
> [file 1's SaaS billing scenario](01_worked_scenarios.md)).
> **Accumulating snapshot** — one row per entity that gets *updated in
> place* as it passes milestones over its lifecycle
> (`fact_account_lifecycle`, same scenario).

**Q: What's a factless fact table? Give an example.**
> A fact table with no numeric measure column at all — the existence of
> the row *is* the fact, and you answer questions by counting or
> filtering rows rather than summing a column. Examples: browsing/page-
> view events, likes, follows, and the sensor-fault event table in
> [file 1's IoT scenario](01_worked_scenarios.md).

**Q: Additive, semi-additive, non-additive — define each with an
example.**
> **Additive**: safe to sum across every dimension (`line_total`,
> `fare_amount`). **Semi-additive**: safe to sum across some dimensions
> but not others — classically, a snapshot balance like `mrr` sums
> correctly across accounts but not across time. **Non-additive**: never
> safe to sum, only to average or evaluate per-row — a ratio or
> multiplier like `surge_multiplier`, or a rollup's `avg_temperature`
> (see the IoT scenario in file 1 for why re-averaging an average is
> its own distinct trap, worse than a plain non-additive column, since
> naively `AVG()`-ing pre-aggregated averages can silently produce a
> wrong number rather than an obviously meaningless one). The interview
> tell is catching this *before* someone builds a wrong report on top of
> it.

**Q: Why store `discount_amount` instead of `discount_percent`?**
> A dollar amount is additive; a percentage is not. Storing the rate
> forces every consumer to either avoid summing it (easy to forget) or
> recompute it from the underlying amounts anyway — so store the
> additive form and derive the rate at query/report time if needed.
> Same reasoning that argues for storing `sum_temperature` and
> `reading_count` instead of a bare `avg_temperature` in a rollup table.

---

## Dimension Design Patterns

**Q: What's a role-playing dimension?**
> One physical dimension table joined into a fact table more than once
> under different aliases, each representing a different role — pickup
> vs. dropoff location, trial/activated/converted/churned dates all
> pointing at the same `dim_date` table, or admit/discharge dates in the
> healthcare scenario. One table, multiple meanings depending on which
> foreign key you're looking through.

**Q: What's a degenerate dimension?**
> A dimension-like attribute that lives directly on the fact table with
> no dimension table behind it, because it has no further attributes to
> describe — an order number or invoice number. You group and filter by
> it like a dimension, but a whole table for it would hold nothing but
> the key itself.

**Q: What's a junk dimension?**
> A single dimension table that bundles together several low-
> cardinality flags/indicators that don't deserve their own tables and
> don't belong on any single existing dimension — e.g. a combination of
> `is_gift_wrapped`, `payment_method`, `is_first_order` flags, or the
> clinical `is_emergency`/`is_telehealth`/`is_readmission_flagged`
> bundle in file 1's healthcare scenario — folded into one small
> dimension, keeping the fact table's foreign-key list from ballooning
> with one column per flag.

**Q: What's a bridge table, and when do you need one?**
> A table resolving a many-to-many relationship between a fact (or a
> dimension) and a dimension — one row per pairing. Needed whenever a
> single fact row (or dimension row) legitimately maps to *multiple*
> rows of another dimension, like a product belonging to several
> categories at once. The alternative — repeating rows or packing values
> into a delimited string — breaks either the grain or the ability to
> join/filter cleanly. A bridge table can also carry a payload beyond
> just the relationship itself — the marketing-attribution bridge in
> file 1 adds a `credit_weight` column per attribution model, so the
> *business logic* for splitting credit lives in data rather than being
> hard-coded into the schema.

**Q: What's a ragged (or unbalanced) hierarchy, and how do you model
one?**
> A hierarchy whose depth varies by branch — not every leaf is the same
> number of levels down (a comment-reply thread, an org chart with
> uneven management layers). Don't flatten it into fixed
> `level_1, level_2, ...` columns the way you would a known, fixed-depth
> hierarchy (category → subcategory); instead use a self-referencing
> parent-key column and walk it recursively at query time, or precompute
> a `depth` at load time if that's what's actually asked for repeatedly.

**Q: How do you handle a dimension attribute changing — walk through
all the SCD types you know.**
> **Type 0**: never changes, or changes are ignored (a birthdate) —
> though a genuine data-entry *error* in a Type 0 column should still be
> corrected in place; Type 0 means the business value doesn't change
> over time, not that a bug in it is permanent.
> **Type 1**: overwrite in place, no history kept — use when the old
> value was simply *wrong* (a data-entry correction).
> **Type 2**: insert a new row with `valid_from`/`valid_to`/`is_current`,
> preserving full history — use when the old value was *genuinely true
> at the time* and historical reports must reflect it.
> **Type 3**: keep the previous value in a separate `previous_x` column
> alongside the current one — only tracks *one* prior state, used
> rarely, when you specifically need "current vs. immediately prior"
> and nothing further back.
> **Type 4**: keep a full history table separate from the current-value
> dimension table, so most queries hit the small "current" table and
> only history-aware queries pay the cost of the larger table.
> **Type 6** (a hybrid, "1+2+3"): a Type 2 row structure that *also*
> keeps a current-value column updated across all historical rows for
> that entity, so you can ask both "what was true then" and "what's
> true now, joined to that historical row" without a second lookup.
> The interview signal isn't reciting all six — it's picking the right
> one by asking *why* the value changed, every time.

**Q: What's an "unknown member" row, and why use one instead of NULL?**
> A placeholder row inserted into a dimension table (surrogate key like
> `-1` or `0`) specifically to represent "not applicable / not yet
> known / late-arriving," so foreign keys on the fact table are never
> NULL. This keeps every join an inner join with predictable behavior,
> rather than requiring every consumer to remember to use a LEFT JOIN
> and handle NULLs specially — used in file 1's SaaS scenario for
> milestones (`converted_date_key`, `churned_date_key`) not yet reached.

---

## Keys & Practical Loading Concerns

**Q: Surrogate key vs. natural key — why bother with surrogates?**
> A natural key (an order number, a SKU) comes from the source system
> and can change, get reused, or differ in format across source
> systems. A surrogate key is a warehouse-generated, meaningless integer
> assigned on load, which (a) insulates the warehouse from source-system
> key changes, (b) is required for SCD Type 2 — the same natural key
> needs multiple surrogate rows over time, one per historical version,
> and (c) joins faster as a small integer than a wide text natural key.

**Q: What's a late-arriving dimension (vs. a late-arriving fact)?**
> A late-arriving dimension is when a fact row shows up before its
> dimension row exists yet (a sale for a customer whose profile hasn't
> loaded yet) — handled by inserting a placeholder dimension row
> immediately (not the generic unknown-member row, but a specific
> "placeholder for this natural key," backfilled with real attributes
> once they arrive) so the fact can still be loaded without waiting. A
> late-arriving fact is the opposite: a fact row shows up describing an
> event that happened in the past, after later periods have already
> been loaded and reported on — this requires the load process to
> correctly re-open and adjust any already-published periodic snapshots
> or aggregates, not just append the row.

**Q: What makes a fact table load idempotent, and why does it matter?**
> Idempotent means re-running the same load (after a failure and retry,
> for instance) produces the same end state, not duplicated rows.
> Typically achieved by keying the fact table's insert on a natural
> business key plus load-batch logic (upsert / merge on that key, or
> delete-then-insert for the affected partition) rather than a blind
> append. It matters because batch jobs *will* fail partway through and
> get retried — without idempotency, a retry silently double-counts
> revenue.

**Q: What's the difference between an identity split and an identity
merge, and why is the merge case harder?**
> An identity split is when one natural key wrongly refers to two
> different real-world entities over time — e.g. a source system reuses
> a deleted customer's ID for a brand-new customer
> (`03_critique_and_debug.md`, Case 6). An identity merge is the
> opposite: two different natural keys are discovered to refer to the
> *same* real-world entity (two duplicate patient registrations, worked
> in [file 1's healthcare scenario](01_worked_scenarios.md)). The merge
> case is structurally harder because fixing a split just means
> assigning new surrogate keys correctly going forward, while fixing a
> merge requires rewriting historical fact-table foreign keys to point
> at one canonical surrogate key, typically tracked through an auditable
> mapping table rather than a silent rewrite.

**Q: What's the difference between dbt's `snapshot` feature and a
regular incremental model?**
> `dbt snapshot` specifically implements SCD Type 2 against a source
> that only exposes current state — it diffs the source against the
> last snapshot on each run and appends new Type 2 rows when it detects
> a change, automating the expire-then-insert pattern from
> `concepts/04_slowly_changing_dimensions.md`. An incremental model is a
> more general materialization strategy for a `fact_*` (or any) model —
> it only processes new/changed rows since the last run instead of a
> full rebuild, which is what keeps a large transaction fact table
> affordable to refresh on every run. See
> `concepts/05_one_big_table_and_lakehouse_modeling.md`, section 3.

---

**Next:** [03 — Critique & Debug](03_critique_and_debug.md)
