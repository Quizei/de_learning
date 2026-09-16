# Concept 03: File Formats & Lakehouse Table Formats

**Covers:**
- Choosing a file format: CSV vs. JSON vs. Parquet vs. Avro vs. ORC, from the warehouse/lake architecture angle
- What a **table format** is and why file formats alone weren't enough — the problem Iceberg/Delta/Hudi exist to solve
- Schema evolution, ACID transactions on object storage, and time travel, each explained by the concrete failure they prevent
- Partition evolution and hidden partitioning — Iceberg's specific answer to the over-partitioning trap from `concepts/02_partitioning_and_bucketing.md`
- A decision framework: which file format, which table format, and why

> **Scope note:** this file is deliberately about *choosing and organizing* formats for warehouse/lake storage — which format for which workload, and what table formats add on top of files. It does not re-derive Parquet's internal row-group/column-chunk/page structure, predicate pushdown, or compression codec mechanics — that's already covered in depth in `spark_course/concepts/15_file_formats_columnar_storage.md`, and this file cross-links to it rather than repeating it. If you haven't read that file yet, it's worth reading section 2 (Parquet internals) and section 3 (pushdown) before this one — everything below about *why* Iceberg/Delta/Hudi need Parquet's footer statistics assumes that mechanism as background.

*The Python below simulates format trade-offs and table-format mechanics without needing pyarrow, delta-spark, or a JVM — the shapes shown mirror exactly what those libraries do.*

---

## 1. File Format Choice, From the Warehouse/Lake Angle

| Format | Layout | Schema | Human-readable | Compression | Schema evolution | Best for |
|---|---|---|---|---|---|---|
| CSV | Row | None | Yes | None | No | Simple exchange, small exports |
| JSON / JSON Lines | Row | Implicit | Yes | None | No (structurally) | APIs, nested/variable raw ingestion |
| Avro | Row | Embedded | No | Deflate/Snappy | **Excellent** | Streaming ingestion (Kafka), write-heavy |
| Parquet | Columnar | Embedded | No | Snappy/ZSTD/Gzip | Limited (additive only) | Analytics, curated lake/warehouse storage |
| ORC | Columnar | Embedded | No | ZLIB/Snappy | Limited | Hive-ecosystem warehouses |

The decision that actually matters in an interview is rarely "which format is best" in the abstract — it's **matching format to where data sits in the pipeline and how it gets read**:

- **Bronze/raw ingestion, write-heavy, schema still moving** → Avro or JSON Lines. A microservice emitting Kafka events adds a field every few weeks; Avro's writer/reader schema reconciliation (below) means every downstream consumer keeps working without a coordinated deploy.
- **Silver/gold, read-heavy, analytical** → Parquet, near-universally. A query that touches 3 of 50 columns only pays for those 3 columns' bytes — this is the payoff of columnar layout described in `concepts/01_warehouse_architecture.md`, section 3, and mechanically detailed in `spark_course/concepts/15_file_formats_columnar_storage.md`.
- **Already committed to Hive/Hadoop** → ORC is the ecosystem-native columnar choice, with built-in ACID support for Hive transactions specifically; outside that ecosystem, Parquet has won on tooling breadth (Spark, Trino, Athena, BigQuery, Snowflake, DuckDB all treat it as a first-class citizen).
- **Small exchange with a non-technical partner** → CSV, because "opens in Excel" is a real requirement, not a technical one.

### Avro's schema evolution, concretely

Avro's defining feature is that a **reader schema** and a **writer schema** don't need to match exactly — a reader can read data written under an older or newer schema, using field defaults to paper over the difference:

```python
schema_v1_fields = ["name", "email"]
schema_v2_fields = ["name", "email", "phone"]
schema_v2_defaults = {"phone": "N/A"}

data_v1 = [{"name": "Alice", "email": "alice@example.com"}]
data_v2 = [{"name": "Carol", "email": "carol@example.com", "phone": "555-0100"}]

# A v2 reader reading v1 data: missing field gets its default
for record in data_v1:
    evolved = {**record}
    for field in schema_v2_fields:
        evolved.setdefault(field, schema_v2_defaults.get(field))
    print("v2 reader on v1 data:", evolved)

# A v1 reader reading v2 data: extra field is simply ignored
for record in data_v2:
    projected = {k: v for k, v in record.items() if k in schema_v1_fields}
    print("v1 reader on v2 data:", projected)
```

**Output:**
```text
v2 reader on v1 data: {'name': 'Alice', 'email': 'alice@example.com', 'phone': 'N/A'}
v1 reader on v2 data: {'name': 'Carol', 'email': 'carol@example.com'}
```

This is why Avro (or Protobuf with a schema registry) is the standard choice for a Kafka topic feeding several independent downstream consumers: no single deploy has to touch every consumer simultaneously when a producer adds a field.

---

## 2. Why File Formats Alone Weren't Enough

Parquet (or ORC) solves the *read* problem — columnar layout, compression, pushdown. It does **not** solve a cluster of problems that show up the moment multiple writers and readers share the same lake table:

- **No atomicity.** A writer replacing a set of Parquet files isn't a single operation. A reader can see a half-written state — some old files deleted, new ones not yet all present — and get an inconsistent or outright wrong result.
- **No schema enforcement.** Nothing stops a new job from writing a `price` column as a string into a table where every other file has it as a float, silently corrupting downstream reads.
- **No safe way to `UPDATE`/`DELETE`/`MERGE`.** Parquet files are immutable; "update one row" means rewriting an entire file (or worse, hoping no reader touches it mid-rewrite).
- **No history.** Once a bad write lands, there's no built-in way to ask "what did this table look like an hour ago?" or to roll back.
- **No safe way to evolve partitioning.** Changing a Hive-style table's partition scheme (say, from daily to hourly) generally means rewriting the entire table's physical layout.

A **table format** — Apache Iceberg, Delta Lake, or Apache Hudi — is a metadata layer sitting *on top of* plain Parquet (or ORC/Avro) files that adds exactly these missing guarantees, without giving up the "cheap, open files on object storage" property that makes a lake a lake in the first place. This is the concrete mechanism behind the "lakehouse" architecture introduced at a high level in `concepts/04_data_lake_and_lakehouse_architecture.md` — this section is where that phrase gets made concrete.

```text
                     BEFORE (files only)              AFTER (table format)

   Reader sees:      whatever files currently         a consistent SNAPSHOT --
                      exist in the directory --        an atomic pointer to an
                      no guarantee of consistency       exact set of files

   Schema:           whatever the last writer          enforced + versioned;
                      happened to write                additive changes tracked

   UPDATE/DELETE:    rewrite entire files by hand,      MERGE/UPDATE/DELETE as a
                      hope nobody reads mid-rewrite      first-class, atomic operation

   History:          none                               time travel: query any
                                                          past snapshot/version
```

### How this works mechanically: a transaction log / metadata tree

Every table format's core trick is the same shape, even though the three implementations differ in the details: **never mutate a file in place; instead, write new files, then atomically swap in a new pointer (a manifest, a log entry, a metadata JSON) that says which files currently make up the table.** A reader always resolves "what are this table's current files?" through that pointer, so it either sees the whole old state or the whole new state — never a half-written mix.

```python
# Simulated Delta Lake-style transaction log: each entry is one atomic commit
delta_log = [
    {"version": 0, "op": "CREATE TABLE",  "files_added": 0,  "files_removed": 0},
    {"version": 1, "op": "INSERT",        "files_added": 5,  "files_removed": 0},
    {"version": 2, "op": "INSERT",        "files_added": 3,  "files_removed": 0},
    {"version": 3, "op": "MERGE (upsert)","files_added": 2,  "files_removed": 2},
    {"version": 4, "op": "DELETE",        "files_added": 1,  "files_removed": 1},
]

# "Current" table state = replay the log and track the live file set
live_files = set()
next_file_id = 0
for entry in delta_log:
    added = {f"file_{next_file_id + i}.parquet" for i in range(entry["files_added"])}
    next_file_id += entry["files_added"]
    live_files |= added
    # (a real log also records exactly which file IDs were removed; simplified here)
    print(f"v{entry['version']}: {entry['op']:<16} "
          f"+{entry['files_added']} files, -{entry['files_removed']} files "
          f"-> {len(live_files)} live files tracked")
```

**Output:**
```text
v0: CREATE TABLE      +0 files, -0 files -> 0 live files tracked
v1: INSERT             +5 files, -0 files -> 5 live files tracked
v2: INSERT             +3 files, -0 files -> 8 live files tracked
v3: MERGE (upsert)     +2 files, -2 files -> 10 live files tracked
v4: DELETE             +1 files, -1 files -> 11 live files tracked
```

**Time travel** falls directly out of this design: since every version is just "replay the log up to entry N," querying an old version means resolving the file set as of that entry instead of the latest one — no separate backup system required:

```sql
-- Delta Lake / Iceberg-style time travel (illustrative syntax)
SELECT * FROM sales VERSION AS OF 2;
SELECT * FROM sales TIMESTAMP AS OF '2025-01-02';
```

**Schema evolution** works the same way: a schema change is itself a logged, versioned event (add a column, widen a type), so old files written under the old schema and new files written under the new schema can coexist and be read consistently — readers reconcile using the schema recorded for whichever files they're reading, the same principle as Avro's reader/writer schema reconciliation in section 1, but implemented at the table-metadata level instead of per-record.

---

## 3. Iceberg vs. Delta Lake vs. Hudi: The Actual Differences

All three give you ACID transactions, schema evolution, and time travel. Where they genuinely differ is worth knowing precisely, because "just pick Iceberg" is a slogan, not a reasoned answer:

| | Delta Lake | Apache Iceberg | Apache Hudi |
|---|---|---|---|
| Created by | Databricks | Netflix | Uber |
| Metadata structure | `_delta_log/` (JSON commit log) | Snapshot → manifest list → manifest → data files | Timeline of instants (commits) |
| Partition evolution | No — changing partitioning means rewriting data | **Yes** — change partitioning without rewriting existing data | No — rewrite required |
| Hidden partitioning | No — queries must know the physical partition columns | **Yes** — queries filter on logical columns; Iceberg maps to physical layout itself | No |
| Streaming upserts | Good | Growing | **Excellent** — purpose-built for this (Copy-on-Write and Merge-on-Read table types) |
| Multi-engine support | Strong on Databricks/Spark; growing elsewhere | **Strongest** — Spark, Trino, Flink, Snowflake, Athena all treat it as first-class | Strong with Spark/Flink |
| Vendor neutrality | Historically tied to Databricks (now more open) | Fully open specification, vendor-neutral by design | Open, Apache-governed |

**Why partition evolution matters concretely:** without it, "we partitioned this table by month, but query patterns have shifted and daily partitions would prune better now" means rewriting the entire table's file layout — potentially terabytes — as a one-time, disruptive migration. Iceberg tracks partition specs as versioned metadata alongside the data, so *new* data can be written under a new partition scheme while old data stays exactly where it is, and a query transparently reads both correctly. This directly defuses the over-partitioning trap from `concepts/02_partitioning_and_bucketing.md` — a wrong initial partitioning choice on an Iceberg table is a metadata change, not a data rewrite.

**Why hidden partitioning matters:** in a plain Hive-style table, a query has to know the exact physical partition columns (`WHERE year=2025 AND month=1`, not `WHERE order_date = '2025-01-15'`) to get pruning at all — get the predicate shape wrong and pruning silently doesn't happen (this exact failure is drilled in `interview_questions/03_critique_and_debug.md`). Iceberg's engine derives the physical partition from a logical column transform (`day(order_date)`) automatically, so a query written the "natural" way still prunes correctly.

**Practical decision guide:**
- Multiple engines (Spark **and** Trino **and** Flink), avoiding vendor lock-in, or partition scheme likely to change → **Iceberg**.
- Heavy streaming upsert workload (CDC feeds, frequent row-level updates at high throughput) → **Hudi**'s Merge-on-Read is purpose-built for this.
- Already deep in the Databricks/Spark ecosystem, want the most mature single-vendor tooling → **Delta Lake**.
- All three are legitimate answers to "does this handle ACID/schema evolution/time travel" — the differentiator that should actually drive a choice is partition evolution, streaming-upsert intensity, and engine diversity, not the ACID/evolution/time-travel checklist itself.

---

## 4. Where This Leaves File-Size Guidance

None of the above changes the small-file guidance from `concepts/02_partitioning_and_bucketing.md` and `spark_course/concepts/15_file_formats_columnar_storage.md` — a table format still stores Parquet files underneath, and thousands of tiny Parquet files are exactly as expensive to read whether or not Iceberg or Delta Lake is managing their metadata. What table formats add on top is **automated compaction**: Delta Lake's `OPTIMIZE`, Iceberg's `rewrite_data_files` procedure, and Hudi's clustering all exist specifically to periodically merge small files into well-sized ones as a background maintenance operation, rather than requiring a human to notice and run a manual compaction job.

```python
# Same simulation shape as the small-file cost model, framed as what
# a table format's OPTIMIZE/compaction job is trying to fix
files_before = 2000       # many small commits over time, e.g. streaming upserts
avg_size_before_mb = 0.5
files_after = 8            # after a compaction/OPTIMIZE pass
avg_size_after_mb = 128

print(f"Before compaction: {files_before:,} files x {avg_size_before_mb} MB "
      f"= {files_before * avg_size_before_mb:,.0f} MB total, "
      f"{files_before:,} read tasks")
print(f"After compaction:  {files_after} files x {avg_size_after_mb} MB "
      f"= {files_after * avg_size_after_mb:,.0f} MB total, "
      f"{files_after} read tasks")
```

**Output:**
```text
Before compaction: 2,000 files x 0.5 MB = 1,000 MB total, 2,000 read tasks
After compaction:  8 files x 128 MB = 1,024 MB total, 8 read tasks
```

Same logical data, 250x fewer read tasks — table-format compaction is a maintenance job, not a substitute for choosing a sane initial partition/file-size strategy.

---

## Key Takeaways

- File format choice should follow the pipeline stage and access pattern: Avro/JSON for write-heavy, schema-shifting raw ingestion; Parquet (or ORC in a Hive shop) for read-heavy analytical storage.
- A table format (Iceberg/Delta Lake/Hudi) is a metadata layer on top of files that adds atomic commits, enforced/versioned schema, safe `UPDATE`/`DELETE`/`MERGE`, and time travel — solving problems plain Parquet files never could, regardless of how well-compressed or well-partitioned they are.
- The mechanism underneath all three is the same: never mutate a file in place, write new files, then atomically swap a pointer (log entry/manifest/snapshot) that defines the table's current file set — this is what makes ACID and time travel possible on ordinary object storage.
- Iceberg's standout features are partition evolution (repartition without rewriting existing data) and hidden partitioning (queries don't need to know the physical layout); Hudi's is streaming-upsert performance; Delta Lake's is Databricks/Spark-ecosystem maturity — pick based on which of those actually matches the workload, not by reciting the shared ACID/schema/time-travel feature list.
- Table formats add automated compaction on top of files, but don't eliminate the small-file problem on their own — see `concepts/02_partitioning_and_bucketing.md` and `spark_course/concepts/15_file_formats_columnar_storage.md` for why file size still matters as much as format.
