# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

A question type that doesn't fit a full scenario or a flash-card
definition — the interviewer takes whatever you just designed (in
[file 1](01_worked_scenarios.md)) and pushes on one assumption. There's
rarely one "correct" answer here; what's scored is whether you reason
through the trade-off out loud instead of freezing or giving a one-word
answer. Try answering each before expanding the model answer.

---

**Curveball: "This dimension has an attribute that changes constantly —
thousands of times a day — for millions of rows. Is SCD Type 2 still
the right call?"**

<details>
<summary>Model answer</summary>

No — Type 2 on a huge, rapidly-changing dimension causes **dimension
explosion**: every change inserts a new row, and a dimension meant to
have a few million rows balloons into hundreds of millions, most of
which represent trivial, short-lived states nobody ever queries by
name. The standard fix is a **mini-dimension**: split the fast-changing,
low-cardinality attributes (say, a customer's current activity tier or
risk score) out of the main dimension into their own small dimension,
bucketed into ranges if needed, and reference it from the fact table
with its own foreign key alongside the main (stable) dimension's key.
The main dimension stays small and Type-2-able for the attributes that
genuinely need full history; the mini-dimension absorbs the churn
without threatening the row count of the customer dimension itself.

</details>

---

**Curveball: "Two source systems each have their own idea of
'customer.' Marketing's CRM and the billing system disagree on which
account is which. How does that affect your dimension design?"**

<details>
<summary>Model answer</summary>

This is a **conformed dimension** problem — before it's a modeling
problem, it's a matching/identity-resolution problem: you need a
deterministic or probabilistic process (matching on email, a shared
account ID, fuzzy name+address matching) to decide which CRM record and
which billing record refer to the same real-world customer, producing
one warehouse-owned surrogate key that both source systems map to.
Say explicitly that you would *not* model two separate customer
dimensions and try to reconcile them at query time — that pushes the
matching problem onto every analyst, forever. Get it right once, in the
dimension's load process, so `dim_customer` means the same thing no
matter which fact table joins to it — that consistency is what
"conformed" means, and it's what lets a business ask a cross-functional
question ("marketing-attributed revenue by billing risk tier") at all.

</details>

---

**Curveball: "Three more source systems need to start loading data
today, each with their own idea of 'customer,' and the business rules
for reconciling all of them haven't been agreed on yet. You can't wait —
how do you avoid blocking the loads on an agreement that isn't ready?"**

<details>
<summary>Model answer</summary>

This is the specific problem a **Data Vault** loading layer solves, and
naming it here — rather than in a vacuum — is exactly the right moment
to bring it up. Each source system writes its own hub rows (business
keys) and satellite rows (attributes, versioned by load date)
independently and in parallel, with no need to agree on a single
canonical customer definition first, because hubs and satellites never
mix descriptive attributes with business keys or relationships in a way
that could conflict across sources. Once the reconciliation rules
*are* finalized, a separate transformation step builds the conformed
`dim_customer` (the Kimball star-schema layer from the previous
curveball) on top of the vault — the loads were never blocked waiting
for that agreement. The tell here is recognizing this as a genuinely
different problem from the conformed-dimension curveball above: that one
assumes the business rule exists and asks how to centralize it; this one
is about what to do *before* it exists. See
`concepts/06_data_vault_modeling.md` for the full hub/link/satellite
mechanics.

</details>

---

**Curveball: "How would you physically partition or cluster this fact
table in a modern cloud warehouse, and why?"**

<details>
<summary>Model answer</summary>

Partition by date first, almost always — most analytical queries filter
by a date range, and date-based partitioning lets the warehouse skip
scanning irrelevant partitions entirely, which is usually the single
biggest performance lever available. Layer clustering (or a sort key,
depending on the warehouse) on top, choosing the column(s) most
frequently filtered *within* a date range and highest-cardinality
enough to be worth it — customer_id or product_key are common choices.
Explicitly avoid clustering on a very low-cardinality column (like a
three-value status flag) — it doesn't narrow the scan enough to earn
its cost. If asked "how do you know which column to cluster on,"
the honest answer is: look at actual query logs / access patterns
before guessing.

</details>

---

**Curveball: "Leadership now wants this dashboard updated in near
real-time instead of next-day batch. What changes about the model?"**

<details>
<summary>Model answer</summary>

Say plainly that the *dimensional* shape usually survives — dimensions,
grain, and star-schema structure don't change just because the load
frequency does. What changes is the **loading pattern**: periodic
snapshot facts stop being viable at the same interval (you can't
re-snapshot every account every few seconds), so the design shifts
toward streaming the transaction-level events continuously and
computing anything snapshot-like as a materialized, incrementally-
updated view instead of a batch job. Flag that this is a real
architectural shift (Lambda/Kappa-style batch+streaming or streaming-
only), not a tweak — and that it's worth naming as a separate
conversation ("that's a streaming architecture question — want me to go
there, or stay on the data model?") rather than trying to redesign the
whole pipeline inside a data-modeling question. Streaming/real-time
architecture itself is a separate topic in this course — the discipline
here is recognizing the boundary between the two questions.

</details>

---

**Curveball: "How do you know your fact table is actually correct once
it's loaded?"**

<details>
<summary>Model answer</summary>

Name concrete, checkable properties rather than "I'd test it": (1)
**grain uniqueness** — the declared grain columns should have no
duplicate combinations, checkable with a count-distinct-vs-count-star
comparison; (2) **referential integrity** — every foreign key on the
fact table should resolve to a real dimension row (or an explicit
unknown-member placeholder), never a dangling reference; (3)
**reconciliation totals** — a sum of a key measure (like total revenue)
should match a trusted source-of-truth total (finance's ledger, the
source system's own report) within an explainable tolerance; (4) **row-
count sanity** — the count of fact rows loaded for a period shouldn't
swing wildly day to day without a real business reason. Mentioning that
these checks belong in the pipeline itself, run automatically on every
load, not as a one-time manual spot-check, is the difference between an
answer about testing and an answer about production data quality
practice.

</details>

---

**Curveball: "Two different teams are each building their own star
schema off the same raw data. How do you keep their numbers from
disagreeing?"**

<details>
<summary>Model answer</summary>

Name the **bus matrix**: a planning artifact (rows = business processes
like "orders," "shipments," "support tickets"; columns = shared
dimensions like customer, date, product) that's filled in *before*
either team builds anything, marking which dimensions each process's
fact table will use. Any dimension used by more than one process must
be built once, centrally, as a conformed dimension (same keys, same
attribute definitions, same SCD handling) and shared — not
independently rebuilt by each team with their own idea of what a
"customer" row looks like. Without this upfront agreement, two
teams' "revenue by customer segment" numbers can disagree for months
before anyone notices the two `dim_customer` tables quietly define
"segment" differently. The same failure mode shows up one layer further
downstream if teams skip the shared dimension and go straight to their
own One Big Tables — see Case 8 in `03_critique_and_debug.md` for that
exact scenario.

</details>

---

**Curveball: "This attribute only ever has three possible values and
never changes. Do you really need a whole dimension table for it, or
can it just live on the fact table?"**

<details>
<summary>Model answer</summary>

For a genuinely fixed, tiny, static set of values with no further
attributes and no need for translation/lookup (e.g. an
`order_channel` of exactly `web` / `mobile` / `phone`, never
changing) it's reasonable to keep it directly on the fact table as a
low-cardinality attribute rather than a full dimension — the overhead
of a join buys you nothing when there's no additional descriptive data
to look up and no history to track. This becomes a real dimension the
moment any of that changes: if the value set will grow, if it needs
extra descriptive attributes beyond the code, or if a junk dimension
(bundling several such small flags together, see
[file 2](02_rapid_fire_qna.md#dimension-design-patterns))
is a better fit than several loose columns. The point being scored is
recognizing this as a genuine judgment call with a real criterion
(cardinality + need for extra attributes + need for history), not a
rule to apply blindly in either direction.

</details>

---

**Curveball: "Marketing wants a self-service tool where non-engineers
build their own charts against this data, with zero joins. Does that
mean you should have designed this as One Big Table from the start?"**

<details>
<summary>Model answer</summary>

Not necessarily — push back gently on the framing. A star schema and a
"zero-join, self-service-friendly" experience aren't mutually exclusive:
most BI tools (and semantic-layer tools sitting in front of a
warehouse) can present a pre-defined join path across a star schema as
if it were one flat table to the end user, without the warehouse itself
needing to physically materialize an OBT. The real question is whether
*more than one* fact table needs to share the same dimensions
consistently — if so, keep the star schema as the source of truth and
let the BI layer (or a materialized OBT built *from* that star schema,
refreshed on a schedule) handle the flattened experience for end users,
rather than hand-building and maintaining a separate OBT ETL pipeline
that can drift from the conformed dimensions over time. If it's truly
one fact table, one dashboard tool, and no other consumer will ever need
the same dimensions elsewhere, a direct OBT is a perfectly reasonable,
simpler choice — the judgment call is exactly the one in
`concepts/05_one_big_table_and_lakehouse_modeling.md`, section 5.

</details>

---

**Curveball: "You shipped this schema, and six months later the
business asks for a report your grain fundamentally can't answer. What
do you do?"**

<details>
<summary>Model answer</summary>

Don't pretend a schema can be future-proofed against every possible
future question — the honest, senior answer is that this is expected
and normal, not a design failure. Diagnose *why* the grain can't answer
it: either the question needs finer grain than currently captured (fix:
a new or additional fact table at the required grain, sourced going
forward — historical backfill may or may not be possible depending on
whether the source system retained the detail), or it needs a
derived/aggregate table built *on top of* the existing fact table
rather than a grain change at all. Explicitly reject "just add more
columns to the existing fact table to shoehorn this in" as the wrong
instinct — that's the same mistake as Case 1 in
`03_critique_and_debug.md`, mixing grains in one table to avoid
building a second one.

</details>

---

**Next:** [05 — Whiteboarding & Stakeholder Communication](05_whiteboarding_and_stakeholder_communication.md)
