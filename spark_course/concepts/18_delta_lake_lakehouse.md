# Concept 18: Delta Lake / Lakehouse Concepts

**Covers:**
- The problem with plain Parquet-on-a-data-lake
- What Delta Lake adds: the transaction log (_delta_log/)
- Key operations: MERGE INTO, UPDATE/DELETE, time travel
- Schema enforcement vs schema evolution (mergeSchema)
- OPTIMIZE (compaction) and Z-ORDER BY (data skipping)
- VACUUM (removing old unreferenced files)
- The "lakehouse" pitch: one copy of data for BI and ML
- Brief note on Iceberg and Hudi as alternative designs
- Simulation: a transaction log with commits and time travel

> *Note: this topic isn't in the source YouTube playlist — added because it's essential and commonly asked about.*

*The PySpark/SQL snippets below reflect what you'd run against a real Spark session; the worked examples and their output are simulated here in pure Python so you can follow the mechanics without a cluster.*

---

## 1. The problem with plain Parquet on a data lake

A "data lake" of plain Parquet files (e.g. a directory tree on S3/HDFS/ADLS) has real limitations for anything beyond append-only, read-only analytics:

- NO ACID transactions: if a write job crashes halfway through writing 500 files, readers can see a PARTIAL, inconsistent result (some new files present, some not) — there's no atomic "commit" concept at the storage layer.
- NO schema enforcement: nothing stops a new job from writing files with a different, incompatible schema into the same directory, silently corrupting downstream reads.
- Can't safely UPDATE or DELETE individual rows: Parquet files are immutable. "Updating a row" means finding which file(s) contain it, rewriting those files without the old value and with the new one, and atomically swapping them in — painful and unsafe to do by hand, especially concurrently with readers.
- NO built-in history/versioning: once old files are overwritten or deleted, there's no way to see "what did this table look like yesterday" or reproduce a report from last month.
- Concurrent writers can conflict/corrupt data with no locking or conflict-detection mechanism built in.

```text
plain_lake/sales/
  part-00000.parquet
  part-00001.parquet
  part-00002.parquet   <- job crashes mid-write here
  part-00003.parquet   <- never gets written
```

A concurrent reader might see part-00002 as a truncated/corrupt file, or see 2 of 4 expected files and silently under-count — there's no atomic "this write either fully happened or didn't happen" guarantee.

No log of past states means: "show me this table as of last Tuesday" is simply not answerable once files have been overwritten.

---

## 2. What Delta Lake adds: the transaction log

Delta Lake stores data as Parquet files (same format!) PLUS a `_delta_log/` directory containing an ordered sequence of JSON commit files: `000...0.json`, `000...1.json`, `000...2.json`, etc.

Each commit file records the ACTIONS that happened in that transaction: which files were added, which were removed (logically — not necessarily deleted from disk yet), schema info, metadata changes, etc.

Reading a Delta table = read the transaction log to figure out exactly which set of underlying Parquet files currently constitutes "the table" (the net effect of all commits so far), then read those files. Writing = write new Parquet file(s), then atomically append a new commit JSON to the log (using the underlying storage's atomic "put-if-absent"/rename semantics to guarantee only one writer wins a given commit number — this is how Delta gets ACID guarantees on top of storage that itself has no transactions).

Periodically, Delta writes a CHECKPOINT (a Parquet snapshot of the log state) so readers don't have to replay thousands of tiny JSON commits from the beginning every time.

```text
delta_table/
  part-00000-....parquet     <- actual data files (still Parquet!)
  part-00001-....parquet
  part-00002-....parquet
  _delta_log/
    00000000000000000000.json   <- commit 0: initial write (ADD file1, file2)
    00000000000000000001.json   <- commit 1: MERGE (ADD file3, REMOVE file1)
    00000000000000000002.json   <- commit 2: DELETE (REMOVE file2, ADD file2b)
    00000000000000000010.checkpoint.parquet  <- periodic snapshot for fast reads

Reader logic (simplified):
  1. Read the latest checkpoint (or start from commit 0 if none)
  2. Replay subsequent JSON commits to get the CURRENT set of
     "live" files
  3. Read only those Parquet files
```

---

## 3. Key operations: MERGE, UPDATE/DELETE, time travel

MERGE INTO (upsert): match incoming rows against existing rows on a key; update matched rows, insert unmatched ones, optionally delete. This is the standard pattern for "apply a batch of CDC changes" or "daily snapshot upsert" without hand-rolling file rewrites.

UPDATE / DELETE: modify or remove rows matching a condition directly via SQL, without you figuring out which physical files are affected — Delta handles rewriting only the affected files under the hood (copy-on-write: files containing matched rows get rewritten with the change applied; a new commit marks old files removed, new ones added).

Time travel: query the table as it existed at a PAST version or timestamp, using the transaction log's history — useful for auditing, reproducing a report, or recovering from a bad write.

```sql
-- MERGE INTO: apply a batch of CDC upserts
MERGE INTO sales_target AS t
USING sales_updates AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *

-- UPDATE / DELETE directly on a table
UPDATE sales_target SET status = 'cancelled' WHERE order_id = 42
DELETE FROM sales_target WHERE order_date < '2020-01-01'

-- Time travel: by version number
SELECT * FROM sales_target VERSION AS OF 12

-- Time travel: by timestamp
SELECT * FROM sales_target TIMESTAMP AS OF '2024-01-15 00:00:00'
```

```python
# PySpark equivalents
df_v12 = spark.read.format("delta").option("versionAsOf", 12).load("/path/sales_target")
df_asof = spark.read.format("delta").option("timestampAsOf", "2024-01-15").load("/path/sales_target")
```

---

## 4. Schema enforcement vs schema evolution

Schema ENFORCEMENT (the default): a write whose schema doesn't match the table's existing schema (missing column, extra column, type mismatch) is REJECTED with an error, protecting the table from silent corruption — exactly what plain Parquet-on-a-lake doesn't give you.

Schema EVOLUTION: when a schema change is intentional (e.g. upstream added a new column), you opt in explicitly with `mergeSchema` (or `overwriteSchema` for more drastic changes), and Delta updates the table's schema going forward, back-filling old rows' new columns as NULL.

```python
# Enforcement (default): this FAILS if incoming_df has a schema
# mismatch against the existing Delta table
incoming_df.write.format("delta").mode("append").save("/path/sales_target")

# Evolution: explicitly allow the new column(s) to be added
incoming_df.write.format("delta").mode("append") \
    .option("mergeSchema", "true") \
    .save("/path/sales_target")
```

---

## 5. OPTIMIZE and Z-ORDER BY

OPTIMIZE: compacts many small files into fewer, larger ones (see `concepts/15_file_formats_columnar_storage.py` for why small files hurt). It's Delta's built-in fix for the exact problem that plain Parquet lakes have no automated answer for.

Z-ORDER BY (col1, col2, ...): while compacting, additionally CO-LOCATES rows with similar values of the given columns into the same files, using a space-filling curve (Z-order curve) so that multi-column range/equality filters skip more files/row-groups via min/max stats (see concept 15 for predicate pushdown). Regular partitioning only helps for ONE column's equality filters well; Z-ordering helps multiple columns at once without needing separate partition directories for each.

```sql
-- Compact small files into fewer larger ones
OPTIMIZE sales_target

-- Compact AND co-locate data by these columns for better skipping
OPTIMIZE sales_target ZORDER BY (customer_id, order_date)
```

```python
# PySpark (Delta) equivalent:
from delta.tables import DeltaTable
delta_table = DeltaTable.forPath(spark, "/path/sales_target")
delta_table.optimize().executeZOrderBy("customer_id", "order_date")
```

Effect: a query filtering `WHERE customer_id = X AND order_date BETWEEN a AND b` can skip far more files after Z-ordering on both columns, versus a layout only optimized for one dimension.

---

## 6. VACUUM

Every UPDATE/DELETE/MERGE/OPTIMIZE that "removes" a file from the table's logical view doesn't delete it from disk immediately — Delta just marks it removed in the transaction log, which is what makes TIME TRAVEL possible (old versions can still find their files).

VACUUM physically deletes files that are no longer referenced by any version of the table WITHIN THE RETENTION WINDOW (default 7 days). This reclaims storage, but it also means: after VACUUM, you can no longer time-travel to a version older than the retention window that depended on those files.

Running VACUUM with too short a retention (or the dangerous `VACUUM ... RETAIN 0 HOURS`) risks deleting files a long-running concurrent reader is still using — so retention exists specifically to protect both time travel and in-flight reads.

```sql
-- Remove files no longer referenced by any version, older than the
-- default 7-day retention window
VACUUM sales_target

-- Dry run: see what WOULD be deleted without deleting
VACUUM sales_target DRY RUN

-- Shorter retention (dangerous -- can break time travel / in-flight reads)
VACUUM sales_target RETAIN 24 HOURS
```

---

## 7. The lakehouse pitch

"Lakehouse" = data LAKE storage (cheap object storage, open file formats, huge scale) + data WAREHOUSE-like guarantees (ACID transactions, schema enforcement, fast metadata operations, time travel) layered on top via a table format like Delta Lake.

The pitch: you don't need to maintain two separate copies of your data — one in a warehouse for BI/SQL analytics, another in a lake for ML/data-science workloads reading raw files directly. One Delta table can serve both: BI tools query it like a warehouse table (via Spark SQL or increasingly native connectors), while ML pipelines read the same underlying Parquet files directly for training data. This avoids the cost, staleness, and duplication of maintaining a separate ETL pipeline into a walled-garden warehouse.

Iceberg and Hudi solve the same core problem (ACID + time travel + upserts on top of a data lake) with different internal designs:

- **Apache Iceberg:** a different metadata layout (manifest lists + manifests tracking data files, with hidden partitioning), strong multi-engine support (Spark, Trino, Flink, etc.) as a first-class goal.
- **Apache Hudi:** originally optimized around fast upserts/incremental pipelines (Copy-on-Write and Merge-on-Read table types), popular in CDC-heavy ingestion pipelines.

All three (Delta, Iceberg, Hudi) are converging toward similar feature sets; the choice is often driven by your existing ecosystem/engine support rather than a fundamental capability gap.

```text
DATA WAREHOUSE               DATA LAKE                LAKEHOUSE
(Snowflake, BigQuery)         (raw files on S3/HDFS)   (Delta/Iceberg/Hudi + lake storage)
- ACID, fast metadata         - Cheap, scalable         - Cheap, scalable storage
- Structured, governed        - Open formats            - ACID + schema enforcement
- Expensive at huge scale     - No transactions/ACID    - Time travel, upserts
- Poor fit for raw ML data    - Great for ML/raw data   - One copy for BI AND ML

Delta Lake / Iceberg / Hudi: same core problem, different internal
metadata designs -- pick based on ecosystem fit (engines, cloud
provider support) more than raw capability differences today.
```

---

## 8. Simulation: transaction log + time travel

Simulate a small transaction log: a sequence of commits (insert, merge/upsert, delete), each recording added/removed files and a resulting logical row-set snapshot. Then "time travel" by replaying commits up to a chosen version number. (In real Delta, this is done by replaying the log's add/remove file actions up to that version, not by storing full snapshots — simplified here for clarity.)

```python
commits = []
table_state = {}  # id -> row dict, mutated to build up history snapshots

def commit(version, op, apply_fn, description):
    apply_fn(table_state)
    commits.append({
        "version": version,
        "op": op,
        "description": description,
        "snapshot": dict(table_state),  # copy of state AFTER this commit
    })

# Commit 0: initial insert
commit(0, "WRITE", lambda s: s.update({
    1: {"id": 1, "name": "alice", "amount": 100},
    2: {"id": 2, "name": "bob", "amount": 200},
}), "INSERT 2 rows (alice, bob)")

# Commit 1: merge/upsert -- update bob, insert carol
def apply_merge(s):
    s[2] = {"id": 2, "name": "bob", "amount": 250}       # updated
    s[3] = {"id": 3, "name": "carol", "amount": 300}     # inserted
commit(1, "MERGE", apply_merge, "MERGE upsert: update bob's amount, insert carol")

# Commit 2: delete alice
def apply_delete(s):
    del s[1]
commit(2, "DELETE", apply_delete, "DELETE WHERE name = 'alice'")

# Commit 3: another insert
def apply_insert(s):
    s[4] = {"id": 4, "name": "dave", "amount": 150}
commit(3, "WRITE", apply_insert, "INSERT dave")

# Time travel: reconstruct table state "AS OF" a given version by using
# the snapshot recorded at that commit
version_1_state = next(c["snapshot"] for c in commits if c["version"] == 1)
version_0_state = next(c["snapshot"] for c in commits if c["version"] == 0)
```

**Output:**
```text
Commit 0 [WRITE]: INSERT 2 rows (alice, bob)
  Table state after commit: {1: {'id': 1, 'name': 'alice', 'amount': 100}, 2: {'id': 2, 'name': 'bob', 'amount': 200}}
Commit 1 [MERGE]: MERGE upsert: update bob's amount, insert carol
  Table state after commit: {1: {'id': 1, 'name': 'alice', 'amount': 100}, 2: {'id': 2, 'name': 'bob', 'amount': 250}, 3: {'id': 3, 'name': 'carol', 'amount': 300}}
Commit 2 [DELETE]: DELETE WHERE name = 'alice'
  Table state after commit: {2: {'id': 2, 'name': 'bob', 'amount': 250}, 3: {'id': 3, 'name': 'carol', 'amount': 300}}
Commit 3 [WRITE]: INSERT dave
  Table state after commit: {2: {'id': 2, 'name': 'bob', 'amount': 250}, 3: {'id': 3, 'name': 'carol', 'amount': 300}, 4: {'id': 4, 'name': 'dave', 'amount': 150}}

--- Current table (latest version) ---
  {2: {'id': 2, 'name': 'bob', 'amount': 250}, 3: {'id': 3, 'name': 'carol', 'amount': 300}, 4: {'id': 4, 'name': 'dave', 'amount': 150}}

--- Time travel: table AS OF version 1 ---
  {1: {'id': 1, 'name': 'alice', 'amount': 100}, 2: {'id': 2, 'name': 'bob', 'amount': 250}, 3: {'id': 3, 'name': 'carol', 'amount': 300}}
  (alice still present -- her DELETE happened in commit 2, which
   is AFTER version 1, so time travel to v1 still sees her)

--- Time travel: table AS OF version 0 ---
  {1: {'id': 1, 'name': 'alice', 'amount': 100}, 2: {'id': 2, 'name': 'bob', 'amount': 200}}
  (original amounts, before the MERGE updated bob to 250)
```

---

## Key Takeaways

- Plain Parquet on a data lake has no ACID guarantees, no schema enforcement, no safe row-level update/delete, and no history.
- Delta Lake adds a `_delta_log/` of ordered JSON commits on top of ordinary Parquet files, giving ACID transactions via atomic commit-file writes.
- MERGE INTO handles upserts; UPDATE/DELETE modify rows directly; VERSION AS OF / TIMESTAMP AS OF give time travel via the log.
- Schema enforcement rejects mismatched writes by default; `mergeSchema` opts into intentional schema evolution.
- OPTIMIZE compacts small files (fixing the problem from concept 15); ZORDER BY additionally co-locates data for multi-column data skipping.
- VACUUM physically deletes unreferenced old files after a retention window — but doing so trades away time travel to versions that depended on those files.
- The lakehouse pitch: one copy of data, on cheap lake storage, serving both BI (warehouse-like guarantees) and ML (raw file access).
- Iceberg and Hudi solve the same ACID-on-a-lake problem with different metadata designs — the ecosystem fit matters more than raw capability differences today.
