# 3. Critique & Debug: "What's Wrong With This?"

Part of the [Interview Questions](README.md) series.

A different interview mode from [file 1](01_worked_scenarios.md):
instead of "design something from scratch," you're handed a schema or a
report and asked **"what's wrong with this?"** or **"why does this
number look wrong?"** This tests whether you can *read* a data model
critically, not just produce one. Every case below is described in
plain prose — no DDL — because the skill being tested is spotting the
flaw from a description, the same way it'd be described to you out loud
in an interview.

Read the symptom, form your diagnosis, then expand the debrief.

---

## Case 1: The Double-Counted Revenue Report

**Setup:** A single `fact_orders` table has one row per order, with
columns for `order_total`, `customer_id`, `order_date` — *and* also a
`product_id`, `product_quantity`, `product_line_total` for whatever
happens to be the order's line items, with one row per line item.
Someone runs `SUM(order_total)` grouped by month and gets a number 3x
higher than finance's reported revenue.

<details>
<summary>Debrief</summary>

**Diagnosis:** the table mixes two grains in one place — "one row per
order" (which is where `order_total` conceptually lives) and "one row
per order line item" (which is where `product_line_total` lives). Since
the table is actually stored at the line-item grain, `order_total` gets
repeated on every line-item row of the same order, and summing it counts
the same order total once per line item instead of once per order.

**Fix:** split into two fact tables at two honest grains —
`fact_order_headers` (one row per order, holding `order_total`) and
`fact_order_lines` (one row per line item, holding `product_line_total`)
— exactly the grain discipline from
[file 1's e-commerce scenario](01_worked_scenarios.md). If someone needs
`order_total`, either derive it as `SUM(product_line_total)` from the
lines table, or keep it on the header table and never repeat it onto the
lines.

**The interview tell:** naming this instantly as "two grains stuffed
into one table" — rather than groping toward a JOIN fix — is what
separates someone who internalized "grain" as a concept from someone
who memorized the word.

</details>

---

## Case 2: The Category Rename That Rewrote History

**Setup:** `dim_product.category` is a plain column, overwritten in
place whenever a product's category changes (Type 1). Last week,
"Electronics" got renamed to "Consumer Tech" platform-wide. This
morning, the VP asks why last year's "revenue by category" dashboard —
which hasn't been touched — now shows $0 for "Electronics" and a
sudden spike for "Consumer Tech" in January of *last* year, a month
before the rename even happened.

<details>
<summary>Debrief</summary>

**Diagnosis:** category was modeled as Type 1 (overwrite), but a
category rename is exactly the case that calls for Type 2 (preserve
history) — unlike a genuine data-entry correction, "Electronics" wasn't
ever *wrong*, it was renamed. Because the dimension row was overwritten
in place, every historical fact row that joins to that product now
joins to the *renamed* category, retroactively reattributing all past
revenue.

**Fix:** category should be Type 2 with `valid_from`/`valid_to` — the
rename inserts a *new* dimension row effective from the rename date,
and historical fact rows keep pointing at the surrogate key of the old
("Electronics") row, since that's the value that was true when those
sales happened.

**The interview tell:** this is the mirror image of the "cuisine_type
miscategorization" curveball in
[file 1's food delivery scenario](01_worked_scenarios.md) — there,
Type 1 was *correct* because the old value was wrong; here, Type 1
is the *bug* because the old value was true at the time. Both cases are
solved by asking the same one question — "was the old value ever true,
or was it always wrong?" — and answering it in opposite directions.

</details>

---

## Case 3: The Missing 12% of Orders

**Setup:** `fact_orders` has a `customer_key` foreign key, joined with
an **inner join** to `dim_customer` in every report. Someone notices the
"orders per month" count from the raw fact table (`SELECT COUNT(*) FROM
fact_orders`) is consistently about 12% higher than the same count run
through the standard reporting view (which joins to `dim_customer`).

<details>
<summary>Debrief</summary>

**Diagnosis:** roughly 12% of orders are arriving with a `customer_key`
that doesn't (yet) have a matching row in `dim_customer` — a classic
**late-arriving dimension**: the order lands before the customer
profile has been loaded, or a guest-checkout order was never assigned a
real customer profile at all. An inner join silently drops every one of
those rows from any report built on it.

**Fix:** either (a) load a placeholder `dim_customer` row for any
unrecognized `customer_key` at fact-load time, backfilled with real
attributes once the profile arrives, or (b) point unresolved orders at
a generic "unknown member" `dim_customer` row so they're never simply
dropped — and switch the reporting join to account for it explicitly
rather than relying on an inner join to hide the gap. Either way, the
report should show "12% unknown customer" as a visible bucket, not
silently vanish 12% of orders.

**The interview tell:** recognizing that an inner join is doing quiet,
invisible damage — and that the fix belongs in the *load process*
(handling late arrivals), not just in changing INNER to LEFT in the
report — is the deeper answer here.

</details>

---

## Case 4: Revenue That Doesn't Add Up to Itself

**Setup:** Products can belong to multiple categories, modeled with a
`bridge_product_category` table (see
[file 1's e-commerce scenario](01_worked_scenarios.md)).
A stakeholder sums "revenue by category" across every category in the
report and gets a number 40% higher than total company revenue reported
elsewhere, and is convinced the schema is broken.

<details>
<summary>Debrief</summary>

**Diagnosis:** this isn't a bug — it's the expected, correct behavior
of a many-to-many rollup. A product in both "Footwear" and "Sale Items"
contributes its full revenue to *both* categories' totals when you
group by category through the bridge table, so summing across all
categories double-(or triple-)counts any order line whose product sits
in more than one category. Total company revenue and "sum of revenue
by category" are simply answering different questions once a
many-to-many relationship is in play.

**Fix:** there's no schema fix needed — the fix is communication.
Either add an explicit note on the report that category totals aren't
mutually exclusive, or, if the stakeholder specifically needs a
mutually-exclusive breakdown, they need a business rule to assign each
product exactly one "primary category" for that purpose (a separate,
simpler attribute directly on `dim_product`, alongside — not replacing —
the bridge table for full multi-category reporting).

**The interview tell:** exactly the caveat flagged proactively in
[file 1's e-commerce scenario, Step 6, Q1](01_worked_scenarios.md) —
this case rewards whoever warned the stakeholder about the fan-out
*before* it caused a panic, versus whoever has to explain it after
the fact.

</details>

---

## Case 5: "Annual Revenue" That's Off by 12x

**Setup:** `fact_mrr_snapshot` holds one row per account per month, with
an `mrr` column (see
[file 1's SaaS billing scenario](01_worked_scenarios.md)).
An analyst reports "annual revenue" for a customer segment by summing
`mrr` across all 12 months of the year for every account in the
segment. Finance says the number is roughly 12x too high compared to
their own figure (which they compute as December's MRR × 12, or
properly, actual invoiced revenue for the year).

<details>
<summary>Debrief</summary>

**Diagnosis:** `mrr` is semi-additive — safe to sum *across accounts*
within a single month, never safe to sum *across months* for the same
account, because each month's row is a snapshot balance, not a
transaction. Summing 12 monthly balances doesn't produce "annual
revenue," it produces a number with no coherent business meaning (it's
closer to "the sum of 12 different point-in-time measurements" than to
any revenue figure).

**Fix:** for a run-rate view, take a single month's `mrr` (usually the
latest) and multiply by 12 — that's what "annualized" actually means for
a subscription metric. For *actual* revenue recognized over the year,
that's a different fact table entirely — a transaction fact of actual
billing/invoice events — not a rollup of the snapshot at all.

**The interview tell:** this is precisely the caution named in
[file 1's SaaS billing scenario, Step 3](01_worked_scenarios.md) and
generalized in
[file 2's additive/semi-additive/non-additive answer](02_rapid_fire_qna.md#fact-table-types--measures) —
if you flagged `mrr` as semi-additive when you first designed the
schema, this bug should never have shipped. That's the entire reason
this classification gets asked about at all.

</details>

---

## Case 6: The Customer Whose History Doesn't Belong to Them

**Setup:** `fact_orders.customer_key` stores the source system's
customer ID directly (a natural key, no surrogate key generated by the
warehouse). Six months after a customer named "Alice" closes her
account, the source system reissues her old customer ID to a brand new
customer, "Frank." The warehouse's "customer lifetime value" report now
shows Frank with two years of order history that isn't his.

<details>
<summary>Debrief</summary>

**Diagnosis:** the fact table's foreign key is a **natural key**
straight from the source system, with no surrogate key layer in
between. When the source system reuses an ID after deletion — a real
and common failure mode, not a hypothetical — the warehouse has no way
to distinguish "the entity that used to hold this ID" from "the entity
that holds it now," because it never assigned its own independent
identity to either one.

**Fix:** generate a warehouse-owned surrogate key for `dim_customer` at
load time, and have `fact_orders` reference *that*, not the source
system's ID directly. When a new customer shows up reusing an old
natural key, the load process assigns them a brand new surrogate key —
a new dimension row — rather than reusing the old surrogate. Alice and
Frank end up as two distinct dimension rows even though the source
system briefly gave them the same natural key.

**The interview tell:** this is the concrete failure scenario behind
[file 2's surrogate-vs-natural-key answer](02_rapid_fire_qna.md#keys--practical-loading-concerns) —
a candidate who can only recite "surrogates insulate you from source
key changes" as a slogan will struggle here; naming *this specific*
failure mode (ID reuse after deletion) shows the reasoning is actually
understood, not memorized. It's also the mirror image of the identity-
*merge* problem in [file 1's healthcare scenario](01_worked_scenarios.md) —
this case is one key wrongly representing two different people over
time; that one is two different keys that turn out to represent one
person.

</details>

---

## Case 7: The Dashboard's Average Doesn't Match the Raw Data

**Setup:** `fact_sensor_readings_1min` stores one row per sensor per
minute, with a pre-computed `avg_temperature` column for that minute
(see [file 1's IoT scenario](01_worked_scenarios.md)). A dashboard
computes "average temperature by equipment type, last 7 days" as
`AVG(avg_temperature)` grouped by equipment type. An engineer
spot-checks the raw sensor readings for one piece of equipment and gets
a noticeably different number than the dashboard shows for that same
equipment and time range.

<details>
<summary>Debrief</summary>

**Diagnosis:** `AVG(avg_temperature)` is an **average of averages**, and
it is only mathematically equal to the true average if every minute
being averaged had exactly the same number of underlying readings. In
practice, minutes don't all have equal reading counts — a sensor
occasionally drops a reading, a minute at the start/end of the 7-day
window is partial, a sensor briefly goes offline — so naively averaging
the pre-aggregated per-minute averages silently gives a *different*
number than the true average of all raw readings, weighted correctly by
how many readings actually happened each minute.

**Fix:** the rollup table needs to store `sum_temperature` and
`reading_count` (both genuinely additive) alongside — or instead of —
`avg_temperature`. The correct query is
`SUM(sum_temperature) / SUM(reading_count)`, not `AVG(avg_temperature)`.
This is a schema-design fix, not just a query fix: if only
`avg_temperature` was ever stored and the raw sums are gone, the true
average can no longer be reconstructed at all.

**The interview tell:** this is a sharper, easier-to-miss version of the
semi-additive caution in Case 5 — an `mrr` bug produces an obviously
absurd number (12x too high), but a rollup-of-rollup averaging bug can
produce a *plausible-looking but quietly wrong* number, which is why it
survives in production dashboards far longer before anyone notices. See
`concepts/02_dimensional_modeling.md` and
[file 1's IoT scenario, Step 3](01_worked_scenarios.md) for the full
worked version, including why the fix has to happen at schema-design
time (storing sums, not just averages), not just at query time.

</details>

---

## Case 8: Two Teams' Dashboards Disagree on "Customer Segment"

**Setup:** The BI team built a wide, single-table OBT
(`orders_wide_obt`) that flattens `fact_orders` with all its dimensions,
including a `customer_segment` column, for their self-service dashboard
tool. Separately, the support-ops team built their own OBT
(`support_tickets_wide_obt`) flattening `fact_support_tickets` with a
`customer_segment` column of its own. Someone notices the two teams'
dashboards report meaningfully different customer counts per segment,
even after accounting for orders vs. tickets being different events.

<details>
<summary>Debrief</summary>

**Diagnosis:** each OBT independently pre-joined its own copy of
customer-segment logic at build time, rather than referencing one
centralized, conformed `dim_customer`. If the two teams' ETL jobs
compute or refresh `customer_segment` even slightly differently — a
different snapshot cutoff, a slightly different business rule for what
counts as "Corporate" vs. "Consumer," one team's job running before a
segment change lands and the other's after — the two OBTs quietly drift
out of agreement, and there's no single source of truth to reconcile
against because the segment logic was never centralized in the first
place.

**Fix:** this is precisely the trade-off named in
`concepts/05_one_big_table_and_lakehouse_modeling.md`, section 1 and
section 5: OBT is a fine choice for a single fact table feeding a single
consumer, but the moment a *second* fact table needs the same dimension
to mean the same thing, that dimension needs to be centralized and
conformed — built once, referenced by both OBTs' build processes (or,
better, by a shared star schema that both OBTs are derived from) —
rather than each team independently re-deriving "customer segment"
inside their own wide table.

**The interview tell:** this is the OBT-specific version of the
conformed-dimension curveball in
[file 4](04_curveballs_tradeoffs.md) — recognizing that OBT doesn't
just cost storage and update overhead, it can actively reintroduce the
"two teams silently disagree" failure mode that a conformed dimension
exists to prevent, unless the dimension logic feeding each OBT is
centralized before the flattening happens.

</details>

---

**Next:** [04 — Curveballs & Trade-offs](04_curveballs_tradeoffs.md)
