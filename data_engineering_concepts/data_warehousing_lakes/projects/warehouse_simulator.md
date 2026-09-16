# Capstone Project: Build a WarehouseSimulator

## Scenario

You're asked to build a small internal tool that demonstrates — and
lets a team measure — the core physical-design decisions covered in
`concepts/`: standing up a star schema, comparing partitioned vs.
full-scan query cost, running data through a bronze/silver/gold
medallion pipeline, and comparing file-format trade-offs. This is the
kind of tool a data platform team builds to make an architectural
decision concrete with actual numbers, rather than arguing about
partitioning strategy in the abstract — and building it forces you to
turn "I understand partition pruning and the medallion architecture"
into "I can express that understanding as reusable code that measures
its own claims."

## Learning Goal

Implement a `WarehouseSimulator` class against the interface specified
below, backed by an in-memory SQLite database plus in-memory Python
structures for the partition and medallion simulations. This exercises
star-schema construction, partition pruning mechanics, the small-file
cost model, and the bronze/silver/gold pipeline — the concepts from
`concepts/01_warehouse_architecture.md` through
`concepts/04_data_lake_and_lakehouse_architecture.md`, expressed as one
tool instead of five separate scripts.

This brief gives you the class interface, the expected behavior of each
method, and a worked example of what running the finished tool should
produce — build the implementation yourself before checking your
design against the notes at the end.

---

## The Interface

```python
import sqlite3
from collections import defaultdict


class WarehouseSimulator:
    """
    Simulates a data warehouse environment end to end:
    - A star schema in SQLite (fact_sales + dimensions)
    - Partitioned storage in memory (Python dicts), to measure the
      cost of partition pruning vs. a full scan
    - A bronze -> silver -> gold medallion pipeline over messy data
    - A file-format cost comparison (CSV vs. JSON Lines vs. simulated
      columnar), matching the trade-offs in concepts/03

    Usage:
        sim = WarehouseSimulator()
        sim.create_warehouse()
        sim.load_data(num_records=10_000)
        comparison = sim.query_with_partition_pruning()
        pipeline_stats = sim.run_medallion_pipeline()
        format_stats = sim.compare_formats()
        stats = sim.get_stats()
    """

    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row

        self.partitions = {}      # partition_key -> list of records (in-memory sim)
        self.raw_records = []     # the same records, unpartitioned (for full-scan comparison)

        self.bronze_data = []
        self.silver_data = []
        self.gold_tables = {}

        self._stats = {
            "warehouse_created": False,
            "records_loaded": 0,
            "partitions_created": 0,
            "bronze_count": 0,
            "silver_count": 0,
            "gold_tables": 0,
            "queries_run": 0,
        }

    def close(self):
        self.conn.close()

    # -----------------------------------------------------------------
    # 1. CREATE WAREHOUSE
    # -----------------------------------------------------------------
    def create_warehouse(self):
        """
        Build a star schema: dim_date, dim_product, dim_customer,
        dim_store, and fact_sales, with indexes on fact_sales' foreign
        keys.

        Requirements:
            - Every dimension gets a surrogate key primary key
              (see data_modeling/concepts/02_dimensional_modeling.md,
              section 4 -- never let fact_sales store a natural key
              directly).
            - fact_sales' grain is one row per sale: date_key,
              product_key, customer_key, store_key, quantity, revenue,
              discount.
            - Create indexes on fact_sales' foreign key columns --
              this is what lets you later contrast "an index helps a
              point lookup" against "partition pruning helps a range
              scan," a distinction worth being able to state out loud.
            - Set self._stats["warehouse_created"] = True when done.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 2. LOAD DATA
    # -----------------------------------------------------------------
    def load_data(self, num_records=10_000):
        """
        Generate and load realistic sales data: ~2 years of dim_date
        rows, ~100 dim_product rows across several categories, ~500
        dim_customer rows, ~15 dim_store rows, and num_records rows of
        fact_sales, referencing those dimensions by surrogate key.

        ALSO build the in-memory partition structure this simulator
        uses for the partition-pruning comparison in method 3: for each
        fact row generated, compute its (year, month) from its date,
        append it to self.raw_records (unpartitioned) AND to
        self.partitions[f"{year}-{month:02d}"] (partitioned by month).

        Requirements:
            - Use a fixed random seed so results are reproducible.
            - Update self._stats: records_loaded, partitions_created.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 3. QUERY WITH PARTITION PRUNING
    # -----------------------------------------------------------------
    def query_with_partition_pruning(self):
        """
        Run at least 3 aggregate queries (e.g. "revenue for a single
        month," "revenue for a quarter," "avg profit for a full year")
        BOTH as a full scan over self.raw_records AND as a partitioned
        scan that only touches the matching keys in self.partitions.

        Returns:
            A list of dicts, one per query, each containing at least:
            {"name", "rows_scanned_full", "rows_scanned_partitioned",
             "partitions_accessed", "partitions_total",
             "data_reduction_pct"}.

        Requirements:
            - The "partitioned" path must only ever touch
              self.partitions entries matching the query's filter --
              no cheating by filtering self.raw_records and calling it
              partitioned.
            - Increment self._stats["queries_run"] once per query.
            - Also run at least 2 real SQL queries against the star
              schema built in method 1 (a GROUP BY revenue-by-category
              style query and a top-N query), to show the same
              filter-then-aggregate shape working against real SQL,
              not just the in-memory simulation.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 4. RUN MEDALLION PIPELINE
    # -----------------------------------------------------------------
    def run_medallion_pipeline(self):
        """
        Simulate a bronze -> silver -> gold pipeline over deliberately
        messy raw event data (nulls, inconsistent casing, invalid
        values, duplicates) generated inside this method.

        Requirements:
            - BRONZE: generate ~500 raw event dicts with realistic data
              quality problems (missing user_id, inconsistent action
              casing, invalid/negative amounts, a handful of exact
              duplicates). Store in self.bronze_data.
            - SILVER: validate, deduplicate (by a record ID), and
              standardize (casing, types) into self.silver_data.
              Track WHY each rejected record was rejected -- return
              (or store) a breakdown by rejection reason, not just a
              total count.
            - GOLD: build at least 2 aggregate tables from silver data
              (e.g. daily action counts + revenue, and a per-platform
              or per-user breakdown). Store in self.gold_tables.
            - Update self._stats: bronze_count, silver_count,
              gold_tables.
            - Return a summary dict of bronze/silver/gold counts and
              the rejection-reason breakdown.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 5. COMPARE FORMATS
    # -----------------------------------------------------------------
    def compare_formats(self):
        """
        Using self.raw_records (or a subset, for speed), write the same
        records to a temp directory as CSV, JSON Lines, and a
        simulated columnar layout (one file per column), and compare:
        file size, write time, and time to read/aggregate ONE column
        (e.g. SUM(revenue)).

        Returns:
            A list of dicts, one per format: {"format", "size_bytes",
            "write_time_s", "read_one_column_time_s"}.

        Requirements:
            - Use a temp directory (tempfile.mkdtemp) and clean it up
              in a finally block -- don't leave files behind.
            - The simulated columnar format must demonstrate a REAL
              difference in bytes read for a single-column query, not
              just report a hypothetical ratio -- write one file per
              column, and have the "read one column" step open only
              that one file.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 6. GET STATS
    # -----------------------------------------------------------------
    def get_stats(self):
        """
        Return a dict of warehouse metrics: table row counts (query
        sqlite_master + COUNT(*) per table, don't hardcode), total
        revenue, total profit if tracked, active customer count, plus
        everything already tracked in self._stats.

        Requirements:
            - TODO: implement
        """
        raise NotImplementedError
```

---

## Worked Example: What the Finished Tool Should Do

This is the acceptance test for your implementation — build toward
producing behavior like this.

### 1. Create the warehouse and load data

```python
sim = WarehouseSimulator()
sim.create_warehouse()
sim.load_data(num_records=10_000)
```

**Expected result:** `dim_date` holds roughly 2 years of daily rows,
`dim_product` roughly 100 rows across several categories, `dim_customer`
roughly 500 rows, `dim_store` roughly 15 rows, and `fact_sales` exactly
10,000 rows, each referencing the dimensions by surrogate key only.
`self.partitions` has one entry per `year-month` combination present in
the generated date range (roughly 24 entries for 2 years), and
`self.raw_records` has all 10,000 rows unpartitioned.

### 2. Compare partitioned vs. full-scan queries

```python
results = sim.query_with_partition_pruning()
for r in results:
    print(f"{r['name']}: {r['rows_scanned_full']:,} full-scan rows vs "
          f"{r['rows_scanned_partitioned']:,} partitioned rows "
          f"({r['data_reduction_pct']:.1f}% reduction, "
          f"{r['partitions_accessed']}/{r['partitions_total']} partitions touched)")
```

**Expected result:** for a single-month query, the partitioned path
should touch roughly `1/24` of the rows the full scan touches (for 2
years of roughly evenly distributed data), with a data-reduction
percentage in the 90%+ range — the same order of magnitude as the
worked simulation in `concepts/02_partitioning_and_bucketing.md`,
section 1. A full-year query should show a much smaller reduction
(since it still needs ~12 of the ~24 partitions) — if your two query
results don't show meaningfully different reduction percentages
depending on how wide the query's date range is, something in the
partition-matching logic is wrong.

### 3. Run the medallion pipeline

```python
pipeline_result = sim.run_medallion_pipeline()
print(pipeline_result)
```

**Expected result:** something like
`{"bronze_count": 500, "silver_count": 340, "rejected": {"null_user": 90,
"invalid_amount": 45, "duplicate": 25}, "gold_tables": 2}` — the exact
numbers depend on your random data generation, but the shape (bronze >
silver, a rejection breakdown that sums to `bronze_count - silver_count`,
and at least 2 named gold tables) should hold.

### 4. Compare file formats

```python
format_stats = sim.compare_formats()
for f in format_stats:
    print(f"{f['format']:<16} {f['size_bytes']:>10,} bytes  "
          f"read-1-col: {f['read_one_column_time_s']:.5f}s")
```

**Expected result:** the simulated columnar format's "read one column"
time should be meaningfully faster than CSV's or JSON Lines' — since it
only opens one file instead of parsing every field of every row — even
though this is a simulation without real compression, the *shape* of
the result (columnar wins on single-column reads) should be unmistakable
and reproduce the pattern from
`spark_course/concepts/15_file_formats_columnar_storage.md`, section 1.

### 5. Get final stats

```python
stats = sim.get_stats()
print(stats)
```

**Expected result:** a dict including `records_loaded`, table row
counts for all 5 tables, `partitions_created`, `bronze_count`,
`silver_count`, `gold_tables`, and `queries_run` — everything the
simulator has done so far, in one place.

---

## Design Notes and Judgment Calls to Make Yourself

- **`load_data`**: decide how granular your date range needs to be for
  the partition-pruning comparison to be meaningful — too few months
  and the reduction percentages won't be interesting; too many and the
  in-memory simulation gets slow for no added learning value. 2 years
  at daily grain, partitioned by month, is a reasonable target.
- **`query_with_partition_pruning`**: resist the temptation to compute
  the "partitioned" result by filtering `self.raw_records` with the
  same predicate — that would make the comparison meaningless. The
  partitioned path must only ever look at the specific
  `self.partitions[...]` entries that match, the way a real partition
  pruning decision only ever consults matching partition metadata.
- **`run_medallion_pipeline`**: decide how you represent a rejection
  reason (a `Counter`, a plain dict, an enum) — what matters is that a
  caller can see *why* records were dropped, not just how many, mirroring
  the real diagnostic value of a silver-layer rejection report.
- **`compare_formats`**: the simulated columnar layout is one file per
  column (a list of that column's values, e.g. as JSON) — this is a
  deliberate simplification of real Parquet, and it's fine to say so in
  a comment; what must be real is that reading "one column" only opens
  that one file, not all of them.
- **`get_stats`**: pull table row counts by querying `sqlite_master`/
  `COUNT(*)` live, rather than hardcoding the 5 table names in two
  places — this is the same principle as `generate_ddl` in the
  `data_modeling` capstone's `SchemaDesigner`: read the live state,
  don't reconstruct it from separate bookkeeping that can drift out of
  sync.

## Stretch Goals

- Extend `compare_formats` to also simulate a **small-files** scenario
  (write the same data as many tiny files instead of one file per
  format) and report the read-time penalty, reproducing the
  small-file-vs-well-sized-file comparison from
  `spark_course/concepts/15_file_formats_columnar_storage.md`, section 7.
- Add a `simulate_table_format_compaction(files_before, avg_size_before_mb,
  target_size_mb)` method that models the read-task-count reduction from
  compacting many small files into fewer well-sized ones, the way
  `concepts/03_file_and_table_formats.md`, section 4, illustrates.
- Add a `simulate_bucketed_join(left_size, right_size, num_buckets)`
  method returning the comparison-count reduction versus a naive
  cross-join, generalizing the bucketing simulation in
  `concepts/02_partitioning_and_bucketing.md`, section 4.
- Add an `apply_lifecycle_policy(zone, older_than_days)` method that
  removes bronze records older than a cutoff from `self.bronze_data`
  and reports how much was reclaimed — a mechanical version of the
  retention-policy reasoning in `concepts/04_data_lake_and_lakehouse_architecture.md`.

## Evaluation Criteria

- `create_warehouse` never lets `fact_sales` store a natural key
  directly — every dimension reference is a surrogate key.
- `load_data` produces internally consistent `raw_records` and
  `partitions` (every record in `raw_records` appears in exactly one
  partition, and vice versa).
- `query_with_partition_pruning`'s partitioned path only ever touches
  matching partition entries — verify this yourself by checking that a
  narrower date-range query shows a *larger* reduction percentage than
  a wider one, not a suspiciously identical number every time.
- `run_medallion_pipeline` rejects records for real, distinguishable
  reasons, and `bronze_count - silver_count` equals the sum of the
  rejection breakdown.
- `compare_formats` demonstrates a genuine difference in bytes/time
  read for a single-column query across formats, not a hardcoded ratio.
- The worked example above reproduces results of the stated shape
  (not necessarily exact numbers, since data is randomly generated)
  when run against your implementation.
