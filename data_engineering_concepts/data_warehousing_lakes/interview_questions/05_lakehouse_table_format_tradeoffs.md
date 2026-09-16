# 5. Lakehouse Table Format Trade-offs

Part of the [Interview Questions](README.md) series.

Iceberg, Delta Lake, and Hudi have become common enough in interviews
that "which table format, and why" is now frequently asked as its own
dedicated question — not just embedded inside a broader lakehouse
design scenario the way it appears in
[`01_worked_scenarios.md`](01_worked_scenarios.md). This file is a
focused, rapid drill on exactly that comparison. It assumes you've
already read `concepts/03_file_and_table_formats.md` — this is
practice applying that comparison, not a re-explanation of it.

For each requirement below, name which table format (or formats) best
serve it, and why — then expand the model answer.

---

**Requirement: "We ingest via Kafka Connect at roughly 100,000 events
per second, and need to upsert (not just append) into the target
table continuously as records get updated downstream."**

<details>
<summary>Model answer</summary>

**Hudi**, specifically its Merge-on-Read (MoR) table type — this is the
workload Hudi was purpose-built for at Uber: extremely high-throughput,
continuous streaming upserts, where MoR defers the cost of merging
updates into base files until read time (or a background compaction),
keeping write-path latency low even under heavy update volume. Delta
Lake and Iceberg both support upserts via `MERGE`, but neither is as
specifically optimized for this throughput profile as Hudi's MoR design.

</details>

---

**Requirement: "Our partitioning strategy is very likely to need to
change as data volume grows over the next year or two, and we don't
want to repeat a costly full-table rewrite every time it does."**

<details>
<summary>Model answer</summary>

**Iceberg.** Partition evolution is Iceberg's standout, purpose-built
feature: new data can be written under a new partition spec while old
data stays physically untouched, and Iceberg's metadata layer tracks
which spec applies to which files — a query transparently reads across
both correctly. Delta Lake and Hudi both require a genuine rewrite of
existing data to change partitioning; this is the single clearest
differentiator among the three formats for this specific requirement.

</details>

---

**Requirement: "We need Spark for nightly batch ETL, Trino for ad-hoc
analyst SQL, and Flink for a streaming enrichment job — all reading and
writing the same tables."**

<details>
<summary>Model answer</summary>

**Iceberg.** Multi-engine support is Iceberg's other standout feature —
it's an open specification designed from the outset to be a first-class
citizen across Spark, Trino, Flink, Snowflake, Athena, and more, rather
than being most mature on one vendor's engine. Delta Lake has
historically been strongest on Databricks/Spark specifically (though its
open-sourcing has broadened engine support over time); Hudi has strong
Spark/Flink support but is less universally adopted across query
engines like Trino. When "several different engines must share the
exact same tables" is a stated, current requirement (not a hypothetical
one — see the curveball on exactly this in
`04_curveballs_tradeoffs.md`), Iceberg is the most defensible default.

</details>

---

**Requirement: "We need to answer 'what did this table look like 90
days ago' for compliance/audit purposes."**

<details>
<summary>Model answer</summary>

All three support time travel — this requirement alone doesn't
differentiate them. Iceberg's snapshot-based model, Delta Lake's
versioned `_delta_log`, and Hudi's timeline of instants all provide a
mechanism to query a prior state. The deciding factor for which format
to use should come from a *different* requirement in the same system
(engine diversity, partition stability, streaming-upsert intensity) —
naming "time travel" itself as the reason to prefer one format over
another is a tell of reciting the feature checklist rather than
reasoning about what's actually different between them.

</details>

---

**Requirement: "We want to avoid vendor lock-in and keep our options
open for which cloud data platform we adopt next."**

<details>
<summary>Model answer</summary>

**Iceberg**, as the fully open, vendor-neutral specification with the
broadest cross-vendor adoption (Snowflake, AWS/Athena, Google BigQuery,
Databricks, and more all support reading/writing Iceberg tables
natively or via connectors). Delta Lake originated at, and has
historically been most tightly coupled to, Databricks specifically —
its open-sourcing has reduced but not eliminated that association.
Hudi is fully open and Apache-governed but has a narrower ecosystem of
native integrations than Iceberg does today. If lock-in avoidance is
the primary stated driver, Iceberg is the strongest default answer.

</details>

---

**Requirement: "Given all of the above, which one format would you
recommend if this system needed to satisfy every requirement listed in
this file simultaneously?"**

<details>
<summary>Model answer</summary>

**Iceberg**, with the honest caveat spoken out loud: it wins on
partition evolution, multi-engine support, and vendor neutrality
outright, and is fully competitive (not a weakness) on time travel and
ACID guarantees — but for the very first requirement (100K events/sec
continuous upserts), Iceberg is "good and growing," not the strongest
purpose-built answer the way Hudi's Merge-on-Read specifically is. The
strongest interview answer names Iceberg as the overall recommendation
*and* explicitly flags that a genuinely upsert-throughput-dominated
workload might still argue for pairing Iceberg's table format with a
Flink+Hudi-style ingestion path, or accepting Iceberg with a tuned
Merge-on-Read-equivalent write pattern, rather than pretending one
format is unambiguously best at everything. Trade-off questions like
this are scored on recognizing that a single system can have competing
requirements at all, not on picking a single winner and stopping there.

</details>
