# Concept 15: File Formats & Columnar Storage

**Covers:**
- Row-oriented (CSV/JSON) vs columnar (Parquet/ORC) storage layout
- Why columnar wins for analytics workloads
- Parquet internals: row groups, column chunks, pages, footer stats
- Predicate pushdown and projection pushdown, shown concretely
- Compression codecs: snappy, gzip, zstd
- The small-file problem and how to fix it
- spark.sql.files.maxPartitionBytes (input split sizing)
- Simulated read-time comparison: CSV vs well-sized Parquet vs small-files Parquet

> *Note: this topic isn't in the source YouTube playlist — added because it's essential and commonly asked about.*

*The PySpark snippets below reflect what you'd run against a real Spark session; the worked examples and their output are simulated here in pure Python so you can follow the mechanics without a cluster.*

---

## 1. Row-oriented vs columnar storage

Row-oriented formats (CSV, JSON, Avro) store a full record contiguously: all fields of row 1, then all fields of row 2, etc. Great for writing / streaming individual records, or reading whole records (OLTP-style).

Columnar formats (Parquet, ORC) store all values of COLUMN A together, then all values of COLUMN B together, etc. Great for analytics:

- Most analytical queries touch a FEW columns out of many (`SELECT revenue, region FROM sales_with_80_columns`) — columnar storage lets you read only those columns' bytes off disk, skipping the rest.
- Values within one column tend to be similar (same type, often repeated or a limited value set) — this compresses far better than mixing types/columns together (row-oriented).
- Column-specific ENCODINGS become possible: dictionary encoding (map repeated string values to small integer codes), run-length encoding (RLE — store "value X repeated N times" once), bit-packing for small-range integers, delta encoding for sorted/near-sorted numeric columns.

```text
ROW-ORIENTED (CSV/JSON):              COLUMNAR (Parquet/ORC):
physical layout on disk               physical layout on disk

Row1: [id, name, amt, region]         Col "id":     [1, 2, 3, 4]
Row2: [id, name, amt, region]         Col "name":   [a, b, c, d]
Row3: [id, name, amt, region]         Col "amt":    [100, 250, 90, 400]
Row4: [id, name, amt, region]         Col "region": [E, W, E, E]

Query: SELECT amt FROM t               Query: SELECT amt FROM t
-> must read every row fully           -> reads ONLY the "amt" column
   (id, name, region bytes wasted)        chunk -- other columns untouched
```

**Simulation:** bytes read for `SELECT amt FROM sales` (4 columns), 10M rows.

```python
row_bytes_per_record = {"id": 8, "name": 20, "amt": 8, "region": 10}
total_row_bytes = sum(row_bytes_per_record.values())
num_rows = 10_000_000

csv_bytes_read = total_row_bytes * num_rows                 # must scan whole row
parquet_bytes_read = row_bytes_per_record["amt"] * num_rows  # only "amt" column
```

**Output:**
```text
CSV (row-oriented) bytes read:         460.0 MB
Parquet (columnar) bytes read:          80.0 MB
Reduction: 5.8x less I/O
```

---

## 2. Parquet internals

A Parquet file has this hierarchy:

- File
  - Row Group(s) — a horizontal slice of rows (default target ~128MB-1GB depending on writer settings); the unit of parallelism for readers
    - Column Chunk — within a row group, all values of ONE column, stored contiguously
      - Page(s) — a column chunk is split into pages (the smallest unit of encoding/compression, typically ~1MB); each page has its own min/max/null-count statistics
- Footer (at the END of the file):
  - Schema (column names, types)
  - Per-row-group, per-column statistics: min, max, null count, distinct count estimates
  - Offsets of every row group / column chunk / page

Because the footer holds min/max stats PER ROW GROUP, a reader can open just the footer (cheap), decide "this row group's `amt` column ranges from 500-900, my filter wants `amt > 10000`, skip it entirely" — without ever reading the actual data pages. This is the basis for predicate pushdown / file & row-group skipping.

```text
sales.parquet
+------------------------------------------------------------+
| ROW GROUP 0  (rows 0 - 999,999)                              |
|   Column chunk "id"      [page][page][page]  stats: min/max |
|   Column chunk "amt"     [page][page][page]  stats: min/max |
|   Column chunk "region"  [page][page][page]  stats: min/max |
+------------------------------------------------------------+
| ROW GROUP 1  (rows 1,000,000 - 1,999,999)                    |
|   Column chunk "id"      [page][page][page]  stats: min/max |
|   Column chunk "amt"     [page][page][page]  stats: min/max |
|   Column chunk "region"  [page][page][page]  stats: min/max |
+------------------------------------------------------------+
| FOOTER: schema + per-row-group/column min/max/null stats     |
|         + byte offsets for every chunk/page                  |
+------------------------------------------------------------+
```

**Simulation:** footer stats enabling row-group skip decisions, for the query `WHERE amt > 2000`.

```python
row_groups = [
    {"id": 0, "amt_min": 10, "amt_max": 500},
    {"id": 1, "amt_min": 480, "amt_max": 1200},
    {"id": 2, "amt_min": 1150, "amt_max": 3000},
    {"id": 3, "amt_min": 2900, "amt_max": 9000},
]
query_filter_min = 2000  # WHERE amt > 2000

for rg in row_groups:
    can_skip = rg["amt_max"] <= query_filter_min
    verdict = "SKIP (max <= filter)" if can_skip else "READ (may contain matches)"
```

**Output:**
```text
Query filter: amt > 2000
Row group 0: amt range [10, 500] -> SKIP (max <= filter)
Row group 1: amt range [480, 1200] -> SKIP (max <= filter)
Row group 2: amt range [1150, 3000] -> READ (may contain matches)
Row group 3: amt range [2900, 9000] -> READ (may contain matches)
```

---

## 3. Predicate and projection pushdown

Projection pushdown: only the COLUMNS actually referenced by the query are read from disk (columnar layout makes this cheap/possible).

Predicate pushdown: filter conditions (WHERE clauses) are pushed down to the file-reading layer, so entire row groups (or whole files, when combined with partitioning) can be skipped using footer statistics — without decompressing/deserializing a single data page.

Both are visible in `df.explain()` physical plans as:
- `"PushedFilters: [IsNotNull(amt), GreaterThan(amt,2000)]"`
- The Scan node listing only the needed columns, not all of them

```python
df = spark.read.parquet("sales.parquet")
result = df.select("region", "amt").filter(df.amt > 2000)
result.explain()

# == Physical Plan ==
# *(1) Project [region#5, amt#3]                     <- projection pushdown:
# +- *(1) Filter (isnotnull(amt#3) AND (amt#3 > 2000))    only these 2 cols read
#    +- *(1) FileScan parquet [region#5,amt#3] Batched: true,
#            PushedFilters: [IsNotNull(amt), GreaterThan(amt,2000)],  <- pushdown
#            ReadSchema: struct<region:string,amt:int>
```

Without pushdown: read all columns for all rows, filter in Spark's own execution engine after full deserialization. With pushdown: skip whole row groups via stats, and never even decode columns you didn't select. Both reduce I/O and CPU.

---

## 4. Compression codecs

Compression is applied per-page within a column chunk (on top of any encoding like dictionary/RLE). The codec is a speed/size tradeoff:

- **snappy** (default in Spark): fast compression/decompression, moderate compression ratio. Good default for most ETL: CPU stays cheap, I/O drops a lot.
- **gzip** (zlib): higher compression ratio (smaller files) than snappy. Notably slower to compress AND decompress — more CPU per byte. Good when storage cost or network transfer dominates and you can afford the CPU (e.g. cold/archival data read rarely).
- **zstd**: tunable compression level; at moderate levels, beats snappy's ratio while staying close to snappy's speed — often the best all-around choice on modern Spark/Parquet versions. Requires a reasonably recent Parquet/Spark version for full support.

```text
+----------+-------------------+-------------------+------------------+
| Codec    | Compression ratio | Compress speed     | Decompress speed |
+----------+-------------------+-------------------+------------------+
| snappy   | Moderate           | Fast                | Fast             |
| gzip     | High               | Slow                | Slower           |
| zstd     | High (tunable)     | Fast-Moderate       | Fast             |
+----------+-------------------+-------------------+------------------+
```

```python
df.write.option("compression", "zstd").parquet("out/")
df.write.option("compression", "snappy").parquet("out/")   # default
df.write.option("compression", "gzip").parquet("out/")
```

**Simulation:** relative file sizes for the same 1GB raw dataset.

```python
raw_mb = 1024
ratios = {"none": 1.0, "snappy": 0.35, "zstd": 0.28, "gzip": 0.22}
for codec, ratio in ratios.items():
    print(f"{codec:<8}: ~{raw_mb * ratio:>7.0f} MB on disk")
```

**Output:**
```text
none    : ~   1024 MB on disk
snappy  : ~    358 MB on disk
zstd    : ~    287 MB on disk
gzip    : ~    225 MB on disk
```

(Illustrative ratios — actual results vary heavily by data shape/cardinality. Benchmark on your real data before deciding.)

---

## 5. The small-file problem

The small-file problem: writing many tiny output files instead of a few well-sized ones. Common causes:

- Too many shuffle/output partitions relative to data size (e.g. default `spark.sql.shuffle.partitions=200` on a job whose final result is only a few hundred MB -> 200 tiny files).
- Many small streaming micro-batch writes, each batch producing its own small file(s) per partition, never compacted.
- Over-partitioned table layout (partitioning by a very high-cardinality column, or too many partition columns).

Why it hurts: each file becomes (roughly) one task to read. Thousands of tiny files means thousands of tasks, and PER-TASK OVERHEAD (scheduling, JVM/Python startup for UDFs, file open/close, metadata lookups on cloud storage like S3) dominates over actual work done — you pay fixed overhead thousands of times for almost no data each time. It also bloats the driver/metastore with file-listing metadata.

Fixes:
- `coalesce(n)` before write to reduce output partition count (no shuffle, just merges partitions — see `concepts/05_data_partitioning.py`)
- `spark.sql.files.maxRecordsPerFile` to cap rows per output file
- Periodic COMPACTION jobs that rewrite many small files into fewer larger ones
- Lakehouse table formats' auto-optimize / auto-compaction (e.g. Delta Lake's `OPTIMIZE`, see `concepts/18_delta_lake_lakehouse.py`)

```text
BAD: 1 GB of data written as 2,000 files of ~500KB each
  -> 2,000 tasks on read, each paying ~fixed overhead for ~500KB of work

GOOD: 1 GB of data written as 8 files of ~128MB each
  -> 8 tasks on read, each doing substantial work relative to overhead
```

```python
df.coalesce(8).write.parquet("out/")                         # reduce file count
spark.conf.set("spark.sql.files.maxRecordsPerFile", 1000000)  # cap rows/file
# + periodic compaction job: read many small files, rewrite as few large ones
```

**Simulation:** total job time, overhead-per-task vs data size.

```python
total_data_mb = 1024
per_task_overhead_ms = 50   # scheduling + open/close + metadata, illustrative
throughput_mb_per_ms = 2.0  # once running, how fast a task processes data

for num_files in [8, 50, 500, 2000]:
    mb_per_file = total_data_mb / num_files
    work_time_ms = mb_per_file / throughput_mb_per_ms
    time_per_task = per_task_overhead_ms + work_time_ms
```

**Output:**
```text
   8 files (128.00 MB/file): overhead=50ms + work= 64.00ms = 114.00ms per task
  50 files ( 20.48 MB/file): overhead=50ms + work= 10.24ms =  60.24ms per task
 500 files (  2.05 MB/file): overhead=50ms + work=  1.02ms =  51.02ms per task
2000 files (  0.51 MB/file): overhead=50ms + work=  0.26ms =  50.26ms per task
```

Notice: as file count grows, overhead dominates total per-task time — at 2000 files you're paying ~50ms of overhead to move ~0.26ms worth of actual data. Worse, with limited executor slots, thousands of tasks means many more SCHEDULING ROUNDS overall, multiplying this overhead across the whole job — not just per task.

---

## 6. spark.sql.files.maxPartitionBytes

`spark.sql.files.maxPartitionBytes` (default 128MB) controls the maximum size of a single INPUT partition/split when Spark reads files — i.e. how large a chunk of a file (or how many small files combined) becomes one read task.

- If a single file is bigger than `maxPartitionBytes`, Spark splits it into multiple read tasks (e.g. a 1GB Parquet file with `maxPartitionBytes=128MB` -> ~8 read tasks).
- If files are SMALLER than `maxPartitionBytes`, Spark can PACK several small files into one partition/task (governed together with `spark.sql.files.openCostInBytes`, which models the fixed cost of opening a file) — this is Spark's own partial mitigation for the small-file problem on READ, though writing well-sized files up front is still the better fix.

```python
spark.conf.set("spark.sql.files.maxPartitionBytes", 128 * 1024 * 1024)  # 128MB default
spark.conf.set("spark.sql.files.openCostInBytes", 4 * 1024 * 1024)      # ~4MB default
```

Effect on a 1GB file: `1024MB file / 128MB per partition -> ~8 read tasks`.

Effect on 100 files of 2MB each (200MB total), `maxPartitionBytes=128MB`: Spark packs multiple small files into each partition until it would exceed ~128MB -> far fewer than 100 tasks are created, partially absorbing the small-file penalty on the READ side.

---

## 7. Simulation: CSV vs well-sized Parquet vs small-files Parquet

A combined simulation putting it all together: same total logical data volume, three physical layouts, comparing a rough simulated read time for a query that selects 2 of 20 columns with a filter.

```python
total_logical_gb = 10  # same underlying data in all 3 cases
num_columns = 20
columns_needed = 2

scenarios = [
    {
        "name": "1 big CSV file",
        "num_files": 1,
        "columnar": False,
        "compression_ratio": 1.0,   # CSV here assumed uncompressed
        "per_task_overhead_ms": 50,
    },
    {
        "name": "Well-sized Parquet (~10 files, 1GB each)",
        "num_files": 10,
        "columnar": True,
        "compression_ratio": 0.30,
        "per_task_overhead_ms": 50,
    },
    {
        "name": "Small-files Parquet (~10,000 files, ~1MB each)",
        "num_files": 10_000,
        "columnar": True,
        "compression_ratio": 0.30,
        "per_task_overhead_ms": 50,
    },
]

throughput_mb_per_ms = 3.0  # per-task effective throughput once reading, illustrative

for s in scenarios:
    on_disk_mb = total_logical_gb * 1024 * s["compression_ratio"]
    # columnar formats only pay for the needed columns' share of bytes
    col_fraction = (columns_needed / num_columns) if s["columnar"] else 1.0
    bytes_to_read_mb = on_disk_mb * col_fraction

    mb_per_file = bytes_to_read_mb / s["num_files"]
    work_ms_per_task = mb_per_file / throughput_mb_per_ms
    # Assume enough parallelism that overhead is paid once per task, but many
    # small files also mean many scheduling waves -- approximate total wall
    # time as num_files worth of overhead+work divided by a fixed parallelism
    # of 20 slots, to make the "too many tasks" penalty visible.
    parallel_slots = 20
    waves = max(1, -(-s["num_files"] // parallel_slots))  # ceil division
    total_ms = waves * (s["per_task_overhead_ms"] + work_ms_per_task)
```

**Output:**
```text
Query: SELECT 2 of 20 columns WHERE filter, over 10 GB logical data

1 big CSV file
    on-disk size:      10240.0 MB
    bytes actually read: 10240.0 MB (columnar=False)
    files:      1  scheduling waves:    1
    simulated total read time:   3463.3 ms

Well-sized Parquet (~10 files, 1GB each)
    on-disk size:       3072.0 MB
    bytes actually read:  307.2 MB (columnar=True)
    files:     10  scheduling waves:    1
    simulated total read time:     60.2 ms

Small-files Parquet (~10,000 files, ~1MB each)
    on-disk size:       3072.0 MB
    bytes actually read:  307.2 MB (columnar=True)
    files:  10000  scheduling waves:  500
    simulated total read time:  25005.1 ms
```

Takeaway: columnar format + reasonable file sizing wins decisively over row-oriented CSV. But columnar format with THOUSANDS of tiny files can be even worse than the naive CSV case, because scheduling overhead across many waves of tasks swamps the I/O savings from columnar pruning. File SIZE matters as much as file FORMAT.

---

## Key Takeaways

- Columnar formats (Parquet/ORC) read only needed columns and compress better than row-oriented formats (CSV/JSON).
- Parquet's hierarchy is File -> Row Group -> Column Chunk -> Page, with min/max/null stats stored per row group in the footer.
- Predicate pushdown uses those footer stats to skip whole row groups (or files) without decoding data; projection pushdown reads only the referenced columns' bytes.
- Pick a compression codec by tradeoff: snappy (fast, default), gzip (smallest, slowest), zstd (good middle ground, often best).
- The small-file problem (too many tiny output files) makes per-task scheduling overhead dominate actual work — fix with `coalesce()`, `maxRecordsPerFile`, or periodic compaction.
- `spark.sql.files.maxPartitionBytes` controls input split size on read and can partially absorb small files by packing them together.
- File SIZE matters as much as file FORMAT — a columnar dataset split into thousands of tiny files can be slower than one big CSV.
