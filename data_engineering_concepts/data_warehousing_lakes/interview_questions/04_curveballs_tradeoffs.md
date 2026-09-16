# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

A question type that doesn't fit a full scenario or a flash-card
definition — the interviewer takes whatever you just designed (in
[file 1](01_worked_scenarios.md)) and pushes on one assumption. There's
rarely one "correct" answer here; what's scored is whether you reason
through the trade-off out loud instead of freezing or giving a
one-word answer. Try answering each before expanding the model answer.

---

**Curveball: "How do you actually know which column to bucket a table
on? Walk me through your reasoning, not just the answer."**

<details>
<summary>Model answer</summary>

Look at actual query/join logs before guessing — bucketing chosen from
an assumption about "the important join" rather than measured access
patterns is exactly how Case 4 in `03_critique_and_debug.md` happened.
The candidate column should be (a) genuinely high-cardinality (a
low-cardinality status flag doesn't spread rows evenly across buckets
and doesn't earn its cost), and (b) the column that dominates actual
join conditions against this table, not merely a column that seems
important conceptually (a customer ID feels like the "main" key, but if
90% of joins are actually against product, bucketing on customer buys
nothing for the workload that matters). If two different join patterns
are both genuinely common and roughly equally important, that's worth
naming as a real trade-off — a single physical table can only be
usefully bucketed one way at a time, and the honest answer may be a
second bucketed copy, a different join strategy for the secondary
pattern, or accepting a shuffle for whichever pattern is less frequent.

</details>

---

**Curveball: "Your team wants to repartition a 50 TB Hive-style Parquet
table from daily to hourly, because a new near-real-time dashboard
needs finer-grained pruning. What does that actually cost, and would
you recommend a different approach?"**

<details>
<summary>Model answer</summary>

On a plain Hive-style table, changing the partition scheme means
physically rewriting the entire table's file layout — a 50 TB
one-time migration, with real compute cost and a real window where two
layouts (old and new) may need to coexist during the cutover. Before
recommending that, I'd push back on the framing: does the new dashboard
actually need the *underlying table* repartitioned, or would a
separate, smaller, hourly-partitioned rollup table (fed by the existing
daily-partitioned raw table) serve it without touching 50 TB of
history at all? If a genuine repartition of the full table is
unavoidable, I'd name Iceberg's partition evolution
(`concepts/03_file_and_table_formats.md`, section 3) as the
architectural fix that prevents this exact costly rewrite from
recurring the *next* time query patterns shift — repartitioning becomes
a metadata change instead of a full data rewrite, which is precisely
the problem this curveball is describing.

</details>

---

**Curveball: "You've built the clickstream lake from scenario A in
`01_worked_scenarios.md`. Six months in, storage cost has become a
board-level concern. What do you look at first?"**

<details>
<summary>Model answer</summary>

Before touching partitioning or compression, I'd check whether data is
actually being retained past the point anyone queries it — a
write-only lake with no lifecycle policy (named explicitly as a data
swamp anti-pattern in `concepts/04_data_lake_and_lakehouse_architecture.md`,
section 4) is one of the most common, most fixable sources of runaway
storage cost, and it's a policy fix, not an engineering redesign. After
that: check for small-file bloat inflating both storage and per-file
metadata overhead (compaction fixes this without deleting anything);
check whether bronze is retaining full-resolution raw data far longer
than the replay-safety requirement actually needs (a shorter bronze
retention window, with silver/gold as the durable long-term record, is
often defensible); and only then look at compression codec choice
(zstd over snappy trades a little write-time CPU for meaningfully
smaller files at rest). The order matters: lifecycle/retention policy
is usually the biggest lever, and it's the one most likely to have been
skipped entirely rather than merely under-tuned.

</details>

---

**Curveball: "Leadership wants this warehouse/lakehouse to support
near-real-time dashboards instead of next-day batch. What changes about
the physical storage design?"**

<details>
<summary>Model answer</summary>

Say plainly that partitioning and file-format choices don't change just
because the load frequency does — a table is still best partitioned by
date, still best stored as Parquet under a table format for the
analytical layer. What changes is the **ingestion and compaction
cadence**: streaming ingestion naturally produces many small files per
partition far more often than a nightly batch job would, so the
compaction job that merges them into well-sized files needs to run far
more frequently too, or the small-file problem from
`concepts/02_partitioning_and_bucketing.md` reappears immediately at a
faster clock rate. This is also the moment to flag, the way the
equivalent curveball in `data_modeling/interview_questions/04_curveballs_tradeoffs.md`
does, that "near-real-time" is a genuine architectural shift (a
streaming ingestion and micro-batch compaction pipeline), not a
config tweak — worth naming as its own conversation rather than
silently redesigning the whole pipeline inside a storage-layout
question.

</details>

---

**Curveball: "You recommended Iceberg for a company's lakehouse. Six
months later, they're still running everything through Spark alone —
the multi-engine requirement you based the recommendation on hasn't
materialized. Was Iceberg still the right call?"**

<details>
<summary>Model answer</summary>

Answer honestly rather than defensively: if multi-engine support was
the deciding factor and it turned out not to be needed yet, that's
worth acknowledging as a real cost paid for a benefit not yet realized
— the same "don't build for anticipated needs" caution from
`01_worked_scenarios.md`, scenario B, applies to table-format choice
just as much as it does to warehouse-vs-lakehouse choice. That said,
Iceberg's other properties (safe deletes/merges, partition evolution,
time travel) are still real value independent of the multi-engine
story, so the choice isn't necessarily wrong — but if partition
evolution and time travel alone would have been equally well served by
Delta Lake, and Delta Lake would have meant less operational novelty
for a Spark-only shop, that's a fair, non-defensive thing to admit in
hindsight. The interview signal here is being willing to revisit a past
recommendation honestly rather than justifying it after the fact no
matter what.

</details>

---

**Curveball: "A new source system needs to start loading into the
warehouse today, and it has its own conflicting definition of
'customer' compared to two systems already loading. The business rules
for reconciling all three haven't been agreed yet. What do you do?"**

<details>
<summary>Model answer</summary>

Name this as the specific scenario Data Vault exists to solve
(`concepts/05_kimball_inmon_data_vault_architecture.md`, section 3):
don't block the new source's ingestion waiting for an agreement that
isn't ready, and don't have it silently write into the same conformed
`dim_customer` the other two sources feed, papering over a conflict
that hasn't actually been resolved. Instead, load all three sources'
business keys and attributes independently, in parallel, tagged by
source — the vault pattern — and build (or extend) the conformed
Kimball-style `dim_customer` as a separate transformation step once the
reconciliation rules are actually agreed. The tell here is recognizing
this as an architecture-level decoupling problem, not a schema-design
problem to solve by cleverly merging three definitions on the spot.

</details>

---

**Curveball: "Someone on the team says 'we should just partition
everything by the highest-cardinality column so each partition is as
small as possible — smaller partitions are always faster to scan.'
What's wrong with that reasoning?"**

<details>
<summary>Model answer</summary>

Smaller *individual* scans aren't the same thing as a faster *query*
once fixed per-partition overhead is accounted for — this inverts the
actual guidance from `concepts/02_partitioning_and_bucketing.md`,
section 5. Partitioning too finely multiplies the number of
directories/files/metastore entries, and past a point, the fixed cost
of opening and planning around each one dominates the shrinking amount
of real data each one holds — this is precisely the mechanism behind
Case 1 in `03_critique_and_debug.md`. The correct instinct is the
opposite of "smaller is always faster": aim for a partition size in the
128 MB–1 GB range, and reach for **bucketing**, not finer partitioning,
when a high-cardinality column needs to speed up joins or lookups
without multiplying the partition count.

</details>

---

**Next:** [05 — Lakehouse Table Format Trade-offs](05_lakehouse_table_format_tradeoffs.md)
