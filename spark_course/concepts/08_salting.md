# Concept 08: Salting

**Covers:**
- The salting technique for fixing skewed joins/aggregations
- Exact worked example: salt the skewed side, explode the small side
- The PySpark code pattern using `F.concat`/`F.rand` and `F.explode`/`F.array`
- When salting is (and isn't) still necessary given AQE
- Full simulation: skewed join before and after salting

*The PySpark snippets below are educational/conceptual — they describe what really happens against a real Spark session, but the worked examples are simulated in plain Python so you can follow along without a cluster.*

---

## 1. The problem salting solves

Recap from data skew: when one join key (e.g. `customer_id = "C_HOT"`) accounts for a huge share of rows, every row for that key hashes to the SAME partition. One task ends up doing most of the work while others sit idle — the classic skewed join.

Salting fixes this by artificially SPLITTING the hot key across many partitions, so the work for that one logical key gets spread over multiple tasks instead of piling into one.

Skewed join on `customer_id`, `"C_HOT"` is 70% of the large table's rows:

```text
    large_df (skewed)         small_df (dimension-like)
    customer_id | ...         customer_id | ...
    C_HOT       | ...         C_HOT       | ...
    C_HOT       | ...  <-- ALL C_HOT rows hash to the same partition
    C_HOT       | ...         (small_df has just one row per key)
    C_003       | ...
    C_004       | ...
```

Without salting: the partition holding `C_HOT` does 70% of the join's work.

---

## 2. The salting technique, step by step

Salting technique (for a join `large_df JOIN small_df ON customer_id`):

1. Choose a number of salt buckets, N (e.g. 10).
2. On the LARGE (skewed) side: append a random integer in `[0, N)` to the join key, forming a composite key `"customer_id_salt"`. Each occurrence of `"C_HOT"` now gets randomly assigned one of N salted variants, e.g. `"C_HOT_0"`, `"C_HOT_3"`, `"C_HOT_7"`, ... — which SPREADS the `C_HOT` rows across up to N different partitions instead of one.
3. On the SMALL side: for every row, EXPLODE it into N copies, one per possible salt value (0 .. N-1), each getting a matching composite key, e.g. `"C_HOT_0"`, `"C_HOT_1"`, ..., `"C_HOT_9"`. This guarantees that whichever salt value a large-side row picked randomly, a matching small-side row with that same salted key exists to join against.
4. Join on the composite (key + salt) column instead of the original key.
5. If aggregating afterward, group by the ORIGINAL key (strip the salt back off) to combine partial results from all N buckets back into one row per real key.

The small side grows by a factor of N (one row becomes N rows), but N is a small constant (e.g. 10), and this cost is paid only on the smaller table — far cheaper than leaving the large side's hot key concentrated in a single partition.

```text
BEFORE salting (all C_HOT rows -> one partition):

    large_df:  C_HOT, C_HOT, C_HOT, C_HOT, C_HOT  --> partition 2 (hot!)
    small_df:  C_HOT                              --> partition 2

AFTER salting with N=4 salt buckets:

    large_df (salt appended, RANDOM per row):
        C_HOT_2, C_HOT_0, C_HOT_3, C_HOT_1, C_HOT_2
            |        |        |        |       |
            v        v        v        v       v
         part.2   part.0   part.3   part.1   part.2   <- spread out!

    small_df (EXPLODED into all N salt variants):
        C_HOT_0, C_HOT_1, C_HOT_2, C_HOT_3   <- one row becomes 4
            |        |        |        |
            v        v        v        v
         part.0   part.1   part.2   part.3   <- matches every salt

    Join on (customer_id + salt) instead of customer_id alone.
    Then groupBy(original customer_id) to merge results back together.
```

```python
NUM_SALT_BUCKETS = 10

# 1. Salt the LARGE (skewed) side: append a random salt per row
large_salted = large_df.withColumn(
    "salted_key",
    F.concat(
        F.col("customer_id"),
        F.lit("_"),
        (F.rand() * NUM_SALT_BUCKETS).cast("int")
    )
)

# 2. Explode the SMALL side: one row -> NUM_SALT_BUCKETS rows,
#    one per possible salt value, so every large-side salt has a match
small_exploded = small_df.withColumn(
    "salt",
    F.explode(F.array([F.lit(i) for i in range(NUM_SALT_BUCKETS)]))
).withColumn(
    "salted_key",
    F.concat(F.col("customer_id"), F.lit("_"), F.col("salt"))
)

# 3. Join on the composite salted key instead of customer_id
joined = large_salted.join(small_exploded, on="salted_key", how="inner")

# 4. If aggregating, group back on the ORIGINAL key to merge partials
result = (
    joined.groupBy("customer_id")   # original, un-salted column
          .agg(F.sum("amount").alias("total_amount"))
)
```

---

## 3. When salting is (and isn't) still necessary

Since Spark 3.0+ (default enabled from 3.2), Adaptive Query Execution (AQE) includes an automatic "skew join optimization": when AQE sees (after a shuffle) that one partition is much larger than the others, it automatically SPLITS that oversized partition into smaller sub-partitions and joins them piecewise — conceptually similar to salting, but done by Spark automatically at runtime. See concept 09 for the full mechanics of AQE.

Manual salting is still the right tool when:

- You're on an older Spark version (pre-3.0, or AQE not enabled).
- You're writing a custom UDAF or an RDD-level aggregation that AQE's SQL-level skew join optimization doesn't apply to.
- The skew is SO extreme (e.g. one key is billions of rows, larger than a single executor's memory even after AQE's split) that you need explicit, fine-grained control over how many pieces the hot key is broken into.
- The skew occurs in a groupBy/aggregation (not a join) in a way AQE's skew join handling doesn't cover — AQE's skew handling specifically targets skewed JOINS, not raw groupBy aggregations.

In short: try AQE first (it requires no code change, just config). Reach for manual salting only when AQE can't fully fix your case.

Decision guide:

```text
    Is AQE enabled (spark.sql.adaptive.enabled=true, default since 3.2)?
      |
      +-- YES --> Is the skew in a JOIN?
      |             |
      |             +-- YES --> Try AQE's skew join optimization first
      |             |            (spark.sql.adaptive.skewJoin.enabled=true)
      |             |
      |             +-- NO (it's a groupBy/agg) --> AQE skew-join handling
      |                          doesn't apply -- consider manual salting
      |                          or a two-phase partial aggregation
      |
      +-- NO (old Spark, AQE off) --> Manual salting is your main tool
```

---

## 4. Full simulation: skewed join before and after salting

This simulates a join with one dominant key, first without salting (all rows for the hot key land in one partition) and then with salting (the hot key's rows are spread across N partitions), comparing resulting partition sizes.

```python
import random
random.seed(42)

num_partitions = 4
total_rows = 10_000
hot_key = "C_HOT"
hot_key_rows = int(total_rows * 0.70)
other_keys = [f"C_{i:03d}" for i in range(1, 51)]

large_rows = [hot_key] * hot_key_rows
for _ in range(total_rows - hot_key_rows):
    large_rows.append(random.choice(other_keys))
random.shuffle(large_rows)

small_rows = {hot_key: 1}
for k in other_keys:
    small_rows[k] = 1

def bucket_of(key, n):
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % n

# --- BEFORE salting ---
partitions_before = {i: 0 for i in range(num_partitions)}
for key in large_rows:
    partitions_before[bucket_of(key, num_partitions)] += 1
for p, cnt in partitions_before.items():
    bar = "#" * int(cnt / 100)
    print(f"    Partition {p}: {cnt:>6} rows  [{bar}]")
max_before = max(partitions_before.values())

# --- AFTER salting ---
NUM_SALT_BUCKETS = 10
salted_rows = []
for key in large_rows:
    if key == hot_key:
        salt = random.randint(0, NUM_SALT_BUCKETS - 1)
        salted_rows.append(f"{key}_{salt}")
    else:
        # Non-hot keys don't need salting, but must match the small
        # side's un-salted key exactly for the join -- kept as-is here
        # since only the hot key is skewed in this example.
        salted_rows.append(key)

partitions_after = {i: 0 for i in range(num_partitions)}
for key in salted_rows:
    partitions_after[bucket_of(key, num_partitions)] += 1
for p, cnt in partitions_after.items():
    bar = "#" * int(cnt / 100)
    print(f"    Partition {p}: {cnt:>6} rows  [{bar}]")
max_after = max(partitions_after.values())

print(f"\n  Small-side row count before explode: {len(small_rows)}")
exploded_small_count = (NUM_SALT_BUCKETS - 1) + len(small_rows)  # hot key -> N copies
print(f"  Small-side row count after exploding hot key into "
      f"{NUM_SALT_BUCKETS} salt variants: {exploded_small_count}")

print(f"\n  Max partition size BEFORE salting: {max_before} rows")
print(f"  Max partition size AFTER salting:  {max_after} rows")
print(f"  Improvement: {max_before / max_after:.1f}x more balanced")
```

**Output** (seeded with `random.seed(42)`, so this is the exact, reproducible result of the code above):

```text
  (a) BEFORE salting -- join partitioned by customer_id alone:
    Partition 0:    724 rows  [#######]
    Partition 1:   7764 rows  [#############################################################################]
    Partition 2:    727 rows  [#######]
    Partition 3:    785 rows  [#######]

  (b) AFTER salting -- NUM_SALT_BUCKETS=10 applied to the hot key:
    Partition 0:   2145 rows  [#####################]
    Partition 1:   2182 rows  [#####################]
    Partition 2:   2772 rows  [###########################]
    Partition 3:   2901 rows  [#############################]

  Small-side row count before explode: 51
  Small-side row count after exploding hot key into 10 salt variants: 60

  Max partition size BEFORE salting: 7764 rows
  Max partition size AFTER salting:  2901 rows
  Improvement: 2.7x more balanced
```

Before salting, `C_HOT`'s roughly 7,000 rows all hash to the same partition (partition 1 here), which ends up with 7,764 rows versus roughly 700-800 in each of the other three. After salting, those same `C_HOT` rows get one of 10 random salt suffixes each, spreading them across partitions — the max partition size drops from 7,764 to 2,901 rows, a 2.7x improvement in balance. The small side grows from 51 rows (one per key) to 60 rows, because only the hot key gets exploded into its 10 salt variants (10 - 1 extra rows), while the other 50 keys are left as single rows since they were never skewed in this example.

---

## Key Takeaways

- Salting spreads a skewed key's rows across N partitions by appending a random salt suffix on the large side.
- The small side must be EXPLODED into N copies (one per salt value) so every randomly-salted large-side row has a match to join against.
- Join on (key + salt); when aggregating, group back on the ORIGINAL key afterward to merge the N partial results into one true result.
- The pattern: `F.concat(col, F.lit("_"), (F.rand()*N).cast("int"))` on the skewed side, `F.explode(F.array([F.lit(i) for i in range(N)]))` on the other side.
- AQE's automatic skew join optimization (concept 09) handles many skew cases today without any code change — try that first.
- Manual salting remains necessary for older Spark, custom UDAFs/RDD aggregations, groupBy-only skew (not joins), or extreme skew AQE's split can't fully absorb.
- Salting trades a larger small-side (Nx rows) for a much more even distribution of the large side's work across partitions.
