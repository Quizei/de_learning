# Concept 10: Dynamic Partition Pruning (DPP)

**Covers:**
- Static partition pruning recap: filtering directly on a partition column
- The problem static pruning can't solve: filter on a joined DIMENSION table, fact table partitioned on the join column
- How DPP works: dimension side evaluated first, its keys injected as a dynamic filter to prune fact-table partitions before scanning
- Requirements for DPP to trigger
- Simulation: fact table partitioned by region, joined to a filtered dimension table, partitions scanned WITH vs WITHOUT DPP

*The PySpark snippets below are educational/conceptual — they describe what really happens against a real Spark session, but the worked examples are simulated in plain Python so you can follow along without a cluster.*

---

## 1. Static partition pruning recap

A partitioned table stores its data in separate directories, one per distinct value (or value combination) of the partition column(s), e.g.:

```text
    /warehouse/fact_sales/region=US/...
    /warehouse/fact_sales/region=EU/...
    /warehouse/fact_sales/region=APAC/...
```

STATIC partition pruning happens when a filter DIRECTLY references the partition column with a literal value known at plan time:

```python
spark.table("fact_sales").filter("region = 'EU'")
```

Spark's Catalyst optimizer can push this filter down to the FILE SCAN itself: it only lists and reads the `region=EU/` directory, skipping every other region's files entirely — no data from other partitions is ever touched. This is cheap and effective, but it only works because the filter literally names the partition column with a known value at planning time.

```text
    fact_sales table, partitioned by region:

    /fact_sales/region=US/    (4,000,000 rows)
    /fact_sales/region=EU/    (1,200,000 rows)
    /fact_sales/region=APAC/  (2,500,000 rows)
    /fact_sales/region=LATAM/   (600,000 rows)
    ... (6 more regions)

    Query:  SELECT * FROM fact_sales WHERE region = 'EU'

    Static pruning: Spark reads ONLY region=EU/ -- 9 of 10 partition
    directories are never listed or scanned.
```

```python
df = spark.table("fact_sales").filter(F.col("region") == "EU")
df.explain()
# == Physical Plan ==
# *(1) FileScan parquet fact_sales
#      PartitionFilters: [isnotnull(region), (region = EU)]   <- pruned here
#      ... only region=EU files are opened
```

---

## 2. The problem: filter on the other side of a join

Static pruning breaks down as soon as the filter is on a DIMENSION table, and the fact table is only related to it through a JOIN:

```sql
SELECT f.*
FROM fact_sales f
JOIN dim_region d ON f.region = d.region
WHERE d.region_group = 'EU'
```

Here, `fact_sales` is partitioned by `region` — but the WHERE clause filters on `dim_region.region_group`, a column that doesn't exist in `fact_sales` at all. The static optimizer cannot push `"region_group = 'EU'"` down into `fact_sales`'s partition filter, because at PLAN time it doesn't know which region values satisfy `dim_region`'s filter — that requires actually evaluating `dim_region` first.

Without any special handling, Spark would have to scan ALL of `fact_sales`'s partitions (every region), then join, then filter — even though logically most of that data could never survive the join.

```text
    dim_region (small)              fact_sales (large, partitioned by region)
    +-----------+--------------+    /region=US/    (4.0M rows)
    | region    | region_group |    /region=EU/    (1.2M rows)  <-- only this
    +-----------+--------------+    /region=APAC/  (2.5M rows)      is needed
    | EU        | EU           |    /region=LATAM/ (0.6M rows)
    | DE        | EU           |    ... 6 more regions
    | FR        | EU           |
    | US        | AMERICAS     |
    +-----------+--------------+

    Query: WHERE d.region_group = 'EU'  -- filters dim_region, not fact_sales!

    Without DPP: fact_sales's partition column ("region") is never
    literally compared to a filter constant, so the static optimizer
    can't prune anything -- ALL 10 region partitions get scanned, then
    the join discards most of the rows AFTER reading them. Wasted I/O.
```

---

## 3. How DPP works

Dynamic Partition Pruning solves this by evaluating the FILTERED DIMENSION side FIRST (as part of building the broadcast/hash side of the join), and using the actual set of join keys it produces as a dynamically-generated filter on the fact table's partition column — injected into the fact table's scan BEFORE most of it is read.

Step by step:

1. Spark recognizes the join is on the fact table's partition column (`region`) and that the dimension side has a selective filter (`region_group = 'EU'`).
2. Spark builds a small "reused" broadcast/hash-join subquery from the FILTERED dimension side: `SELECT DISTINCT region FROM dim_region WHERE region_group = 'EU'` &rarr; `{EU, DE, FR}`.
3. That small set of region values becomes a DYNAMIC filter, injected as an additional partition filter on `fact_sales`'s scan: effectively `"AND region IN ({EU, DE, FR})"` — computed at RUNTIME, not known when the query was first planned.
4. `fact_sales`'s file listing now skips every partition directory whose region is not in that dynamically-computed set — the same directory-skipping benefit as static pruning, but driven by a join instead of a literal filter.

The key insight: DPP reuses the broadcast side that the join was ALREADY going to build (for a broadcast hash join) as the source of the dynamic filter — it doesn't do genuinely extra work to compute the set of needed keys.

```text
    Step 1: Evaluate filtered dimension side first
        dim_region WHERE region_group = 'EU'  -->  {EU, DE, FR}

    Step 2: Reuse that broadcast result as a dynamic filter
        fact_sales partition filter becomes:
            region IN ({EU, DE, FR})     <- computed at RUNTIME

    Step 3: Prune fact_sales scan using the dynamic filter
        /region=US/    SKIPPED  (not in {EU, DE, FR})
        /region=EU/    SCANNED  (1.2M rows)
        /region=APAC/  SKIPPED
        /region=LATAM/ SKIPPED
        /region=DE/    SCANNED  (0.9M rows)
        /region=FR/    SCANNED  (0.7M rows)
        ... other regions SKIPPED
```

```python
result = (
    spark.table("fact_sales").alias("f")
    .join(
        spark.table("dim_region").filter("region_group = 'EU'").alias("d"),
        on="region"
    )
)
result.explain()
# == Physical Plan ==
# *(2) BroadcastHashJoin [region], [region], Inner, BuildRight
# :- *(2) FileScan parquet fact_sales
# :       PartitionFilters: [dynamicpruningexpression(region IN dynamicpruning#12)]
# :       (the "dynamicpruning" filter is populated at runtime from
# :        the broadcast subquery below)
# +- BroadcastExchange HashedRelationBroadcastMode
#    +- *(1) FileScan parquet dim_region
#            PushedFilters: [(region_group = EU)]
```

---

## 4. Requirements for DPP to trigger

DPP requires ALL of the following:

1. The join predicate must be directly on the fact table's PARTITION column (e.g. `fact_sales` partitioned by `region`, joined `ON f.region = d.region`). If the join key is a different, derived, or unpartitioned column, DPP cannot map dimension keys back to fact table partitions.
2. One side (typically the filtered dimension table) must be small enough to be used as a broadcast/hash side — DPP is built on REUSING the broadcast join's build side as the dynamic filter source, so a broadcast hash join must actually be chosen for that join (or Spark must determine it's cheap enough to build the filter subquery separately).
3. `spark.sql.optimizer.dynamicPartitionPruning.enabled = true` (this is the DEFAULT since Spark 3.0).
4. The fact table must actually BE a partitioned table (directory layout by the join column) — DPP prunes partitions, it doesn't invent indexes on unpartitioned data.

If the dimension side is too large to broadcast, Spark may still apply DPP using a reusable subquery filter computed once, but the classic and most reliable trigger is a broadcastable dimension side.

Checklist for DPP to trigger:

- [ ] Join predicate is directly on the fact table's partition column
- [ ] Filtered/dimension side is broadcastable (small enough)
- [ ] `spark.sql.optimizer.dynamicPartitionPruning.enabled = true` (default)
- [ ] Fact table is actually partitioned (directory layout) on that column

---

## 5. Simulation: partitions scanned with vs without DPP

This simulates a fact table partitioned by region (10 regions, uneven sizes) joined to a small dimension table filtered down to 3 matching regions, and compares how many partitions (and rows) get scanned with DPP enabled vs disabled.

```python
# fact_sales partitioned by region, 10 regions, uneven sizes
fact_partitions = {
    "US":    4_000_000,
    "EU":    1_200_000,
    "APAC":  2_500_000,
    "LATAM":   600_000,
    "DE":      900_000,
    "FR":      700_000,
    "UK":      850_000,
    "CA":      450_000,
    "JP":    1_100_000,
    "AU":      300_000,
}
total_rows = sum(fact_partitions.values())

# dim_region, filtered to region_group = 'EU'
dim_region = {
    "US": "AMERICAS", "CA": "AMERICAS", "LATAM": "AMERICAS",
    "EU": "EU", "DE": "EU", "FR": "EU", "UK": "EU",
    "APAC": "APAC", "JP": "APAC", "AU": "APAC",
}
matching_regions = {r for r, grp in dim_region.items() if grp == "EU"}

print(f"  fact_sales partitions (by region): {len(fact_partitions)} total, "
      f"{total_rows:,} rows")
print(f"  dim_region filter 'region_group = EU' matches: {sorted(matching_regions)}")

# --- WITHOUT DPP ---
scanned_without = list(fact_partitions.keys())
rows_scanned_without = sum(fact_partitions.values())
print(f"    Partitions scanned: {len(scanned_without)} of {len(fact_partitions)} "
      f"-> {scanned_without}")
print(f"    Rows read from disk: {rows_scanned_without:,}")
print(f"    (rows surviving the join, after filtering, still only: "
      f"{sum(fact_partitions[r] for r in matching_regions):,})")

# --- WITH DPP ---
scanned_with = [r for r in fact_partitions if r in matching_regions]
rows_scanned_with = sum(fact_partitions[r] for r in scanned_with)
print(f"    Partitions scanned: {len(scanned_with)} of {len(fact_partitions)} "
      f"-> {scanned_with}")
print(f"    Rows read from disk: {rows_scanned_with:,}")

reduction_pct = 100 * (1 - rows_scanned_with / rows_scanned_without)
print(f"\n  I/O reduction from DPP: {reduction_pct:.1f}% fewer rows read from disk")
print(f"  Partitions skipped: {len(fact_partitions) - len(scanned_with)} "
      f"of {len(fact_partitions)}")
```

**Output:**

```text
  fact_sales partitions (by region): 10 total, 12,600,000 rows
  dim_region filter 'region_group = EU' matches: ['DE', 'EU', 'FR', 'UK']

  (a) WITHOUT DPP -- fact table scan can't use the dimension filter:
    Partitions scanned: 10 of 10 -> ['US', 'EU', 'APAC', 'LATAM', 'DE', 'FR', 'UK', 'CA', 'JP', 'AU']
    Rows read from disk: 12,600,000
    (rows surviving the join, after filtering, still only: 3,650,000)

  (b) WITH DPP -- dynamic filter from dim_region prunes fact_sales:
    Partitions scanned: 4 of 10 -> ['EU', 'DE', 'FR', 'UK']
    Rows read from disk: 3,650,000

  I/O reduction from DPP: 71.0% fewer rows read from disk
  Partitions skipped: 6 of 10
```

Without DPP, Spark reads all 12.6 million rows across all 10 region partitions, even though only the 3,650,000 rows belonging to `EU`, `DE`, `FR`, and `UK` (the four regions whose `region_group` is `'EU'`) can ever survive the join — the other 8.95 million rows read are wasted I/O, discarded only after being read. With DPP, the dynamic filter derived from `dim_region`'s `region_group = 'EU'` filter prunes the fact table scan down to exactly those 4 matching partitions, reading only the 3,650,000 rows that matter — a 71% reduction in rows read from disk, and 6 of 10 partitions skipped entirely.

---

## Key Takeaways

- Static partition pruning works when a filter directly names the partition column with a known literal — Spark then reads only the matching directories.
- Static pruning FAILS when the filter is on a joined DIMENSION table and the fact table's partition column is only related via the join key — the fact table scan has no literal to prune with.
- DPP fixes this by evaluating the filtered dimension side first and injecting the resulting join keys as a dynamic runtime filter on the fact table's partition scan.
- DPP reuses the broadcast side that a broadcast hash join was already going to build — it's not meaningfully extra work.
- DPP requires: join on the partition column, a broadcastable dimension side, and `dynamicPartitionPruning.enabled=true` (default since Spark 3.0).
- DPP can produce dramatic I/O reduction on large partitioned fact tables joined to small, selectively-filtered dimension tables — exactly the star-schema pattern common in data warehouses.
- DPP is a scan-time (I/O) optimization, distinct from AQE (runtime plan re-optimization) and broadcast joins (shuffle avoidance) — though all three often work together in the same query.
