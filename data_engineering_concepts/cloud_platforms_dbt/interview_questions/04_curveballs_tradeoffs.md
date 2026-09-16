# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

A question type that doesn't fit a full scenario or a flash-card
definition — the interviewer takes whatever you just designed (in
[file 1](01_worked_scenarios.md)) and pushes on one assumption. There's
rarely one "correct" answer here; what's scored is whether you reason
through the trade-off out loud instead of freezing or giving a
one-word answer. Try answering each before expanding the model answer.

---

**Curveball: "Your dbt project only has one target — production. A new
hire keeps running `dbt run` and accidentally overwriting shared dev
tables other people are testing against. What's wrong here, and how do
you fix it structurally, not just by asking people to be careful?"**

<details>
<summary>Model answer</summary>

The structural fix is **`profiles.yml` targets and per-developer
schemas**, not a policy reminder. Every developer gets their own
`dev` target pointing at a schema namespaced to them (dbt's default
`generate_schema_name` macro does this automatically, prefixing the
configured schema with the developer's target name), so `dbt run`
against `dev` builds into `dev_alice` or `dev_bob`, never a shared
table. `prod` is a separate target, typically only ever invoked by the
scheduled CI/CD job, not run ad hoc by a person. The underlying
principle: environment isolation should be enforced by the project's
structure (separate schemas, separate connection profiles), not by
asking humans to remember which target they meant to type.

</details>

---

**Curveball: "Marketing wants to add a new column to a source table
that's already feeding a table-materialized mart. Does adding a column
upstream ever break anything downstream, and how would you catch it
before it ships?"**

<details>
<summary>Model answer</summary>

Adding a column rarely breaks a model that explicitly lists its select
columns (the standard, recommended practice — never `SELECT *` in a
staging model that feeds anything else), since an unlisted new column
is simply invisible to that model. It *can* break something if a
downstream model does use `SELECT *` or `{{ dbt_utils.star(...) }}`
without an `except` list, because a schema drift there can silently
change a mart's column set (and, worse, column *order*, which matters
to some BI tools' cached field mappings) without any dbt error at all.
The catch-before-ship mechanism is running `dbt build` (or at minimum
`dbt compile` plus a diff of the generated column list) against a
staging/CI environment before merging any change to a source's schema,
combined with the general practice of listing columns explicitly in
every staging model specifically to make a schema drift like this a
non-event.

</details>

---

**Curveball: "An incremental fact model's source table just got a
retroactive backfill — three months of historical rows were corrected
and re-sent with a `updated_at` newer than today, even though the data
itself represents last quarter. Does your incremental model pick this
up correctly?"**

<details>
<summary>Model answer</summary>

Only if the model is watermarked on `updated_at` (when the row was
last touched) rather than on the business event's own date column
(e.g. `order_date`). A model correctly built around `updated_at` picks
up the backfilled rows on the very next incremental run, since their
`updated_at` is newer than the current watermark — regardless of how
old the underlying business event is. This is precisely why the
watermark column should track "when did this row last change in the
source," not "when did the business event happen": a model
mistakenly filtered on the business-event date instead would silently
miss this backfill entirely, because the backfilled rows' `order_date`
values are all older than the current watermark. State this
distinction unprompted — it's the single most common way a candidate's
otherwise-correct incremental design quietly breaks under a real-world
backfill.

</details>

---

**Curveball: "Your CI pipeline runs a full `dbt build` — every model,
every test — on every single pull request, against a full clone of
production data. The team is now complaining CI takes 40 minutes and
the compute cost for CI alone is a meaningful line item. What do you
change?"**

<details>
<summary>Model answer</summary>

Several levers, and naming the trade-off of each rather than picking
one blindly: (1) **`--select state:modified+`** (dbt's state-based
selection) to run and test only models that actually changed in the
PR plus their downstream dependents, instead of the entire project,
which is usually the single biggest win. (2) A **smaller or sampled
dataset** for CI specifically (a fraction of production data, or a
fixed small fixture set), trading some fidelity (a test might miss a
data-shape issue only present in the full volume) for dramatically
lower cost and time — acceptable for most correctness tests, less
acceptable for anything checking a volume- or cost-sensitive property.
(3) Reserving the **full, unsampled `dbt build`** for a scheduled
nightly run or the actual merge-to-main event, rather than every draft
commit on every open PR. The point being scored is recognizing this as
a genuine trade-off (fast/cheap CI vs. maximum fidelity per-PR) with no
universally correct answer, not reciting one fix as if it were free.

</details>

---

**Curveball: "A model needs to join customer data that includes PII
(email, phone number) into a mart that several BI tool users, some of
whom shouldn't see raw PII, will query directly. How do you handle
this in the dbt project itself?"**

<details>
<summary>Model answer</summary>

Two complementary techniques, and naming why one alone usually isn't
enough: (1) a **masking/hashing macro** applied at the staging or
intermediate layer (e.g. `SHA256(email)` for a join key that needs to
remain joinable without exposing the raw value, or a `LEFT(phone, 3) ||
'****'` style partial mask for display purposes) — this addresses PII
that's genuinely never needed in raw form downstream. (2) **Warehouse-
level column-level security / dynamic data masking** (a native feature
in Snowflake and BigQuery) for cases where *some* roles legitimately
need the raw value and others don't — dbt can't enforce row/column-
level access control on its own, since dbt's job ends once the table is
built; the warehouse's own grant/masking-policy layer is what actually
restricts who sees what at query time. The tell here is recognizing dbt
transforms the data but does not replace the warehouse's own access
control — a masking macro that scrubs a column at build time is a
one-way transformation baked into every consumer, while a warehouse
masking policy can be role-aware and applied at query time to the same
underlying table.

</details>

---

**Curveball: "dbt Cloud vs. dbt Core — what's actually different, and
when would you push back on paying for Cloud?"**

<details>
<summary>Model answer</summary>

dbt Core is the open-source CLI and framework — the actual `ref()`/
`source()`/materialization/testing engine described throughout this
folder is identical either way. dbt Cloud is a managed service layered
on top: a hosted scheduler/orchestrator, a web IDE, built-in CI job
triggers, hosted documentation, and role-based access for a team — none
of which change what a model or test *does*, only how the project is
run, scheduled, and collaborated on. Pushing back on Cloud makes sense
when a team already has a capable orchestrator (Airflow, Dagster) that
can just as well trigger `dbt build` as a scheduled task, and doesn't
need the collaboration/UI features — at that point Cloud's cost is
paying again for scheduling infrastructure the team already owns. It
becomes clearly worth it for a smaller team without existing
orchestration, or one that values the hosted docs site and web IDE
enough to not want to stand up and maintain that infrastructure
themselves.

</details>

---

**Curveball: "You're told a new mart needs to combine data from a
Snowflake account and a BigQuery dataset that another team owns and
won't be migrating any time soon. Can dbt handle this, and what are the
real constraints?"**

<details>
<summary>Model answer</summary>

A single dbt project's models run against **one** configured warehouse
connection at a time — `ref()`/`source()` resolve within that one
target, and there's no native cross-warehouse join inside a model's
`SELECT`. The realistic options: (1) physically move the needed data
into one warehouse first (a scheduled export/load, or a connector like
Fivetran replicating the BigQuery dataset into Snowflake or vice versa)
and then build the mart as an ordinary single-warehouse dbt model on
top of the now-co-located data, or (2) a federated/external-table
approach specific to the target warehouse (e.g. Snowflake's external
tables, or BigQuery's federated queries to certain external sources) if
one exists for that specific pairing and the data volume is
manageable. State plainly that "two dbt projects, one per warehouse,
somehow synchronized" is not actually solving the problem — the join
still has to happen somewhere physically, and the honest answer is that
dbt's transformation model assumes single-warehouse data gravity; the
real engineering problem here is the data movement, not the SQL.

</details>

---

**Curveball: "Someone proposes switching every model in the project
from `table` to `incremental` by default, to save cost everywhere at
once. Good idea?"**

<details>
<summary>Model answer</summary>

No, and naming why is the actual answer: incremental models trade
simplicity and correctness-by-construction for cost savings, and that
trade only pays off when a model is large enough, and re-run often
enough, for the savings to matter — for a small dimension table
rebuilt in under a second as a `table`, converting it to `incremental`
adds real complexity (a watermark column, a `unique_key`, the failure
modes covered in `03_critique_and_debug.md`) for a savings that rounds
to zero. Blanket-converting every model also multiplies the number of
places a broken `is_incremental()` condition or missing `unique_key`
can silently produce wrong data, which is a correctness risk, not just
a wasted optimization. The right framing: convert specifically the
models where profiling actually shows meaningful runtime/cost tied to
processing unchanged historical data every run — the same "identify
the specific driver before applying a fix" discipline from
`concepts/05_cost_and_performance_optimization.md`, applied here to
resist an overcorrection instead of an under-reaction.

</details>
