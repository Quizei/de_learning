# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design conversations.
This file is fast, direct, definitional — the kind of question asked in
a phone screen, or dropped mid-conversation to check you actually
understand a term you just used. Answer each one out loud in under 30
seconds before reading the model answer.

Every term used here is demonstrated somewhere in `concepts/` or file 1
— the cross-references point back to the concrete moment it showed up.

---

## Warehouse Architecture

**Q: OLTP vs. OLAP — one line each.**
> OLTP runs the application itself: many short, normalized, single-row
> reads/writes optimized for consistency and latency. OLAP answers
> analytical questions: fewer, larger, denormalized scans/aggregations
> optimized for throughput. A warehouse is built for OLAP; the systems
> that feed it are OLTP. (`concepts/01_warehouse_architecture.md`,
> section 1.)

**Q: What does MPP stand for, and what problem does it solve?**
> Massively Parallel Processing — a query is split into fragments that
> run in parallel across many compute nodes, each scanning its own data
> slice, with partial results merged (shuffled) at the end. It's the
> execution model that partitioning and bucketing exist to optimize
> for: less data per node to scan, less data to reshuffle during joins.
> (`concepts/01_warehouse_architecture.md`, section 2.)

**Q: Why does separating compute from storage matter?**
> It lets a warehouse scale and bill each independently — cheap object
> storage holds the data at rest, elastic compute clusters spin up only
> while a query runs, instead of provisioning always-on nodes sized for
> peak load. It's also the architectural precondition for a lakehouse:
> without decoupled storage, there's no cheap object store to layer a
> table format on top of. (`concepts/01_warehouse_architecture.md`,
> section 4.)

---

## Partitioning & Bucketing

**Q: What's partition pruning, and at what level does it happen?**
> Skipping entire partitions (directories/files) that can't match a
> query's filter, decided from partition metadata/listing — before any
> data file is opened. It's a coarser, cheaper cousin of the row-group
> statistics pruning that happens *within* a single Parquet file.
> (`concepts/02_partitioning_and_bucketing.md`, section 3.)

**Q: Partitioning vs. bucketing — what problem does each solve?**
> Partitioning organizes data for *filtering*: skip whole
> directories/files that don't match a `WHERE` clause. Bucketing
> organizes data for *joining*: hash-distribute rows by a key so
> matching keys always land in the same bucket, avoiding a full shuffle
> during a join. They're commonly combined — partition by date,
> bucket within each partition by the most frequent join key.
> (`concepts/02_partitioning_and_bucketing.md`, sections 1 and 4.)

**Q: Why shouldn't you partition on a high-cardinality column like
`customer_id`?**
> Because partition count scales with the number of distinct values —
> a million customers means a million directories, most holding tiny
> amounts of data, which turns per-partition fixed overhead
> (metadata lookups, file-open cost, query-planning time to enumerate
> candidates) into the dominant cost. Bucket on a high-cardinality
> column instead; reserve partitioning for low-cardinality, frequently
> filtered columns like date. (`concepts/02_partitioning_and_bucketing.md`,
> section 5.)

**Q: What's the target size for a single partition/file, roughly?**
> 128 MB to 1 GB. Below roughly 10 MB, per-partition/per-file fixed
> overhead starts to dominate actual work done — this is the small-file
> problem, covered from the storage-layout side in
> `concepts/02_partitioning_and_bucketing.md`, section 5, and from the
> read-task-scheduling side in
> `spark_course/concepts/15_file_formats_columnar_storage.md`, section 5.

---

## File Formats & Table Formats

**Q: When would you choose Avro over Parquet?**
> When the workload is write-heavy ingestion with a schema that's still
> evolving — a Kafka topic where producers add fields over time — and
> row-based access (whole-record reads/writes) rather than analytical
> scans. Avro's reader/writer schema reconciliation lets old and new
> schema versions coexist without breaking consumers.
> (`concepts/03_file_and_table_formats.md`, section 1.)

**Q: What problem does a table format (Iceberg/Delta/Hudi) solve that
plain Parquet files don't?**
> Atomicity (no reader ever sees a half-written state), enforced and
> versioned schema, safe row-level `UPDATE`/`DELETE`/`MERGE` against
> immutable files, and time travel — none of which Parquet's columnar
> layout and compression provide on their own, no matter how well the
> files are organized. (`concepts/03_file_and_table_formats.md`,
> section 2.)

**Q: How does a table format make time travel possible?**
> Every commit is a new, versioned entry in a metadata log/manifest
> that defines exactly which files make up the table at that version —
> never mutating a file in place. Querying an old version means
> resolving the file set as of an earlier log entry instead of the
> latest one. (`concepts/03_file_and_table_formats.md`, section 2.)

**Q: What's Iceberg's standout feature relative to Delta Lake and Hudi?**
> Partition evolution — changing a table's partitioning scheme without
> rewriting existing data — plus hidden partitioning, where queries
> filter on logical columns and Iceberg maps to the physical layout
> itself. Delta Lake's strength is Databricks/Spark-ecosystem maturity;
> Hudi's is streaming-upsert performance (Merge-on-Read).
> (`concepts/03_file_and_table_formats.md`, section 3, and
> `05_lakehouse_table_format_tradeoffs.md` for the full drill.)

**Q: Do table formats solve the small-file problem?**
> Not automatically — they still store Parquet (or ORC/Avro) files
> underneath, and thousands of tiny files are exactly as expensive to
> read regardless of which table format manages their metadata. What
> they add is automated compaction (Delta's `OPTIMIZE`, Iceberg's
> `rewrite_data_files`, Hudi's clustering) as a maintenance operation —
> a fix for files that already went small, not a substitute for
> choosing a sane layout up front. (`concepts/03_file_and_table_formats.md`,
> section 4.)

---

## Data Lakes & Lakehouse Architecture

**Q: Warehouse vs. lake vs. lakehouse — one line each.**
> Warehouse: structured, schema-on-write, reliable, historically
> proprietary/costlier storage. Lake: any format, schema-on-read, cheap
> storage, no built-in reliability guarantees. Lakehouse: lake storage
> economics plus warehouse reliability (ACID, schema, time travel), via
> a table format layered on top of open files.
> (`concepts/04_data_lake_and_lakehouse_architecture.md`, section 1.)

**Q: What are the bronze/silver/gold zones, in one line each?**
> Bronze: raw, as-landed, immutable, append-only — the replay source.
> Silver: validated, deduplicated, standardized, still record-level.
> Gold: business aggregates, pre-joined and curated for the exact
> dashboards/reports that consume them.
> (`concepts/04_data_lake_and_lakehouse_architecture.md`, section 2.)

**Q: What's a "data swamp," precisely — not just "a messy lake"?**
> A lake where discovery, schema enforcement, quality checks,
> ownership, and lineage have broken down badly enough that nobody can
> find, trust, or safely build on the data anymore. Bronze being raw
> and messy is expected and fine on its own — a swamp is what happens
> when that same lack of discipline has also spread into silver and
> gold. (`concepts/04_data_lake_and_lakehouse_architecture.md`,
> section 4.)

**Q: How do you decide between a managed warehouse and a lakehouse for
a given company?**
> By the actual workload and team's operational appetite, not a
> universal ranking: a purely SQL/BI-shaped workload with a small team
> and no lakehouse experience usually favors a managed warehouse for
> its lower operational overhead; a workload with real (not just
> anticipated) ML/multi-engine needs favors a lakehouse's open-format
> flexibility, at the cost of owning the table format, catalog, and
> compaction as new operational responsibilities.
> (`concepts/04_data_lake_and_lakehouse_architecture.md`, section 5, and
> `01_worked_scenarios.md`, scenario B.)

---

## Warehouse Architecture Philosophy

**Q: Kimball vs. Inmon — the one-sentence distinction.**
> Kimball builds bottom-up, dimensional data marts first, for fast
> delivery; Inmon builds top-down, a single normalized enterprise
> warehouse first, for enterprise-wide consistency, with marts derived
> from it afterward. (`concepts/05_kimball_inmon_data_vault_architecture.md`,
> sections 1-2.)

**Q: What's Kimball's real risk, and what's the actual fix for it —
not just "be careful"?**
> Marts built independently can silently define shared dimensions
> (customer, product category) differently, with no single place that
> agreement was supposed to live. The fix is a **bus matrix** — business
> processes as rows, shared dimensions as columns, filled in *before*
> any mart is built — so any dimension used by more than one process
> gets built once, centrally, as a conformed dimension.
> (`concepts/05_kimball_inmon_data_vault_architecture.md`, section 1.)

**Q: Where does Data Vault fit relative to Kimball and Inmon — as an
architecture choice, not a table design?**
> It solves a different problem than either: what to do when several
> source systems need to start loading today, but the business rules
> for reconciling their conflicting definitions of an entity aren't
> finalized yet. Hubs/links/satellites let ingestion proceed in
> parallel per source, with no reconciliation required to load; a
> Kimball-style conformed dimensional layer gets built on top once the
> rules are agreed. It's not a competitor to Kimball — it's usually a
> loading layer that *feeds* a Kimball layer.
> (`concepts/05_kimball_inmon_data_vault_architecture.md`, section 3.
> For the hub/link/satellite table mechanics themselves, see
> `data_modeling/concepts/06_data_vault_modeling.md`.)

---

**Next:** [03 — Critique & Debug](03_critique_and_debug.md)
