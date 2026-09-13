# Concept 02: Spark Query Plans

**Covers:**
- The four plan stages: Parsed -> Analyzed -> Optimized Logical -> Physical
- What `.explain()` / `.explain(True)` / `.explain("formatted")` / `.explain("cost")` show
- Reading a physical plan bottom-up
- Common physical operators: Scan, Filter, Project, HashAggregate, Exchange, BroadcastHashJoin, SortMergeJoin, Sort
- Exchange = a shuffle boundary, and why counting Exchanges predicts shuffle cost
- Predicate pushdown and column pruning shown as a before/after plan diff
- A worked example: reading a realistic `explain()` output line by line

*All PySpark code below reflects real behavior of a running SparkSession; the worked examples are simulated in plain Python/reasoning so you can follow along without a cluster.*

---

## 1. The Four Query Plans

Every DataFrame/SQL query passes through four plan representations before Spark runs it:

1. **Parsed Logical Plan** -- a direct, unresolved translation of your code/SQL into a tree. Column and table names are NOT yet verified to exist.
2. **Analyzed Logical Plan** -- the Analyzer resolves every column/table reference against the Catalog (schema, types, function signatures). Unresolved references raise `AnalysisException` here.
3. **Optimized Logical Plan** -- Catalyst's rule-based optimizer rewrites the analyzed plan: predicate pushdown, column pruning, constant folding, boolean simplification, redundant filter/cast removal, etc.
4. **Physical Plan(s)** -- the Spark Planner turns the optimized logical plan into one or more candidate physical plans (concrete execution strategies, e.g. which join algorithm to use), then the Cost-Based Optimizer (if enabled) picks the cheapest one.

```text
Your DataFrame code / SQL string
         |
         v
+-----------------------+
| 1. PARSED LOGICAL     |  <- syntax only, nothing resolved
+-----------+-----------+
            | Analyzer (resolves columns/tables via Catalog)
            v
+-----------------------+
| 2. ANALYZED LOGICAL   |  <- AnalysisException raised here if invalid
+-----------+-----------+
            | Catalyst rule-based optimizer
            v
+-----------------------+
| 3. OPTIMIZED LOGICAL  |  <- pushdown, pruning, folding applied
+-----------+-----------+
            | Spark Planner (+ Cost-Based Optimizer)
            v
+-----------------------+
| 4. PHYSICAL PLAN(S)   |  <- concrete operators, chosen join strategy
+-----------------------+
            |
            v
    Tungsten codegen -> RDDs -> tasks on executors
```

```python
df = spark.read.parquet("orders.parquet")
result = df.filter(F.col("amount") > 100).select("customer_id", "amount")
result.explain(True)   # prints all four plans
```

**Simulation:** the four-stage rewrite of a trivial `filter` + `select` query on an `orders` table.

```python
parsed = "Project[*] -> Filter[amount > 100] -> Scan[orders]"
analyzed = "Project[customer_id#1,amount#2] -> Filter[amount#2 > 100] -> Scan[orders: customer_id,amount,region,ts]"
optimized = "Project[customer_id#1,amount#2] -> Filter[amount#2 > 100] -> Scan[orders: customer_id,amount]  (region,ts pruned)"
physical = "*(1) Project [customer_id#1, amount#2]\n+- *(1) Filter (isnotnull(amount#2) AND (amount#2 > 100))\n   +- *(1) FileScan parquet orders[customer_id,amount] PushedFilters:[amount>100]"

print(f"  [1] Parsed:    {parsed}")
print(f"  [2] Analyzed:  {analyzed}")
print(f"  [3] Optimized: {optimized}")
print(f"  [4] Physical:\n{physical}")
```

**Output:**
```text
  [1] Parsed:    Project[*] -> Filter[amount > 100] -> Scan[orders]
  [2] Analyzed:  Project[customer_id#1,amount#2] -> Filter[amount#2 > 100] -> Scan[orders: customer_id,amount,region,ts]
  [3] Optimized: Project[customer_id#1,amount#2] -> Filter[amount#2 > 100] -> Scan[orders: customer_id,amount]  (region,ts pruned)
  [4] Physical:
*(1) Project [customer_id#1, amount#2]
+- *(1) Filter (isnotnull(amount#2) AND (amount#2 > 100))
   +- *(1) FileScan parquet orders[customer_id,amount] PushedFilters:[amount>100]
```

---

## 2. The .explain() Variants

- `.explain()` -- physical plan only (default, most common)
- `.explain(True)` -- all four plans: parsed, analyzed, optimized, and physical
- `.explain("formatted")` -- physical plan in a readable, numbered, two-section format (plan tree + per-node detail), the modern default for humans
- `.explain("cost")` -- logical plan annotated with estimated statistics (row counts, sizes) used by the cost-based optimizer -- requires `spark.sql.cbo.enabled` / table stats to be meaningful, otherwise shows `sizeInBytes` only

```python
df.explain()               # physical plan only
df.explain(True)           # parsed + analyzed + optimized + physical
df.explain("formatted")    # numbered, structured physical plan
df.explain("cost")         # logical plan + estimated statistics
df.explain("extended")     # same as explain(True), string form
```

Simulated `explain("formatted")`-style output:

```text
== Physical Plan ==
* Project (3)
+- * Filter (2)
   +- * Scan parquet orders (1)

(1) Scan parquet orders
Output: [customer_id#1, amount#2]
PushedFilters: [IsNotNull(amount), GreaterThan(amount,100)]

(2) Filter
Input: [customer_id#1, amount#2]
Condition: (isnotnull(amount#2) AND (amount#2 > 100))

(3) Project
Output: [customer_id#1, amount#2]
```

Simulated `explain("cost")`-style output:

```text
== Optimized Logical Plan ==
Project [customer_id#1, amount#2], Statistics(sizeInBytes=2.1 MiB, rowCount=50000)
+- Filter (amount#2 > 100), Statistics(sizeInBytes=4.2 MiB, rowCount=100000)
   +- Relation orders[customer_id,amount] parquet, Statistics(sizeInBytes=8.4 MiB, rowCount=200000)
```

---

## 3. Reading a Physical Plan Bottom-Up

Physical plans print top-down on the page, but data actually FLOWS bottom-up: the bottommost operator reads/produces the first rows, and each operator above it consumes the output of the one below.

Read a plan by starting at the deepest indentation (the leaves -- usually Scans) and walking upward, tracking how row count and shape change at each step.

```text
*(2) HashAggregate(keys=[region#3], functions=[sum(amount#2)])
+- Exchange hashpartitioning(region#3, 200)
   +- *(1) HashAggregate(keys=[region#3], functions=[partial_sum(amount#2)])
      +- *(1) Filter (isnotnull(amount#2) AND (amount#2 > 100))
         +- *(1) FileScan parquet orders[region,amount]
```

**Simulation:** narrate this plan bottom-up, one step at a time.

```python
steps = [
    ("FileScan parquet orders", "read raw rows from disk (region, amount only -- pruned)"),
    ("Filter", "drop rows where amount is null or <= 100"),
    ("HashAggregate (partial_sum)", "pre-aggregate WITHIN each partition (map-side combine)"),
    ("Exchange hashpartitioning(region,200)", "SHUFFLE: redistribute partial sums by region key"),
    ("HashAggregate (sum)", "combine partial sums per region into the final total"),
]
for i, (op, meaning) in enumerate(steps, start=1):
    print(f"    step {i}: {op:<38} -> {meaning}")
```

**Output:**
```text
    step 1: FileScan parquet orders               -> read raw rows from disk (region, amount only -- pruned)
    step 2: Filter                                -> drop rows where amount is null or <= 100
    step 3: HashAggregate (partial_sum)            -> pre-aggregate WITHIN each partition (map-side combine)
    step 4: Exchange hashpartitioning(region,200)  -> SHUFFLE: redistribute partial sums by region key
    step 5: HashAggregate (sum)                    -> combine partial sums per region into the final total
```

---

## 4. Common Physical Operators

A cheat-sheet of physical operators you'll see constantly:

- **Scan** -- reads data from a source (`FileScan`, `InMemoryTableScan`)
- **Filter** -- row-level predicate evaluation (the WHERE clause)
- **Project** -- selects/computes a subset of columns
- **HashAggregate** -- group-by aggregation via an in-memory hash table (appears twice per shuffle: partial + final)
- **Sort** -- orders rows; required before `SortMergeJoin`
- **Exchange** -- a SHUFFLE boundary: repartitions data across the cluster (`hashpartitioning`, `roundrobin`, or `rangepartitioning`)
- **BroadcastHashJoin** -- one side is small enough to broadcast whole to every executor; NO shuffle of the big side
- **SortMergeJoin** -- both sides are shuffled and sorted on the join key, then merged; used for large-large joins

```python
operators = [
    ("Scan / FileScan",     "reads rows from a data source"),
    ("Filter",              "evaluates a row-level predicate (WHERE)"),
    ("Project",             "selects / computes a subset of columns"),
    ("HashAggregate",       "group-by aggregation via hash table (partial + final)"),
    ("Sort",                "orders rows -- often precedes SortMergeJoin"),
    ("Exchange",            "SHUFFLE boundary -- redistributes data across the cluster"),
    ("BroadcastHashJoin",   "small side broadcast to all executors, no shuffle of big side"),
    ("SortMergeJoin",       "both sides shuffled + sorted on join key, then merged"),
]
for name, desc in operators:
    print(f"    {name:<20} {desc}")
```

**Output:**
```text
    Scan / FileScan      reads rows from a data source
    Filter               evaluates a row-level predicate (WHERE)
    Project              selects / computes a subset of columns
    HashAggregate        group-by aggregation via hash table (partial + final)
    Sort                 orders rows -- often precedes SortMergeJoin
    Exchange             SHUFFLE boundary -- redistributes data across the cluster
    BroadcastHashJoin    small side broadcast to all executors, no shuffle of big side
    SortMergeJoin        both sides shuffled + sorted on join key, then merged
```

Rule of thumb when scanning a plan:
- Scan/Filter/Project = usually cheap, per-partition work
- HashAggregate = cheap if partial (pre-shuffle), moderate if final
- Sort/Exchange = expensive: disk + network I/O
- BroadcastHashJoin = cheap (no shuffle of the large table)
- SortMergeJoin = expensive (shuffles + sorts BOTH sides)

---

## 5. Exchange = Shuffle Boundary

"Exchange" in a physical plan always means a shuffle: data is written out, redistributed across the network by partitioning key (or randomly, or by range), and read back in on the other side.

A very practical trick: count the Exchange nodes in a plan. Each one is a stage boundary and a shuffle Spark will actually perform at runtime. A plan with 4 Exchanges will do 4 shuffles -- if that number looks too high for the query you wrote, it's a signal to look for unnecessary repartitions, joins on differently-partitioned columns, or aggregations that could be combined.

```text
*(5) SortMergeJoin [customer_id#1], [customer_id#9], Inner
:- *(2) Sort [customer_id#1 ASC], false, 0
:  +- Exchange hashpartitioning(customer_id#1, 200)      <- Exchange #1
:     +- *(1) HashAggregate(keys=[customer_id#1])
:        +- Exchange hashpartitioning(customer_id#1, 200) <- Exchange #2
:           +- *(0) HashAggregate(partial)
+- *(4) Sort [customer_id#9 ASC], false, 0
   +- Exchange hashpartitioning(customer_id#9, 200)       <- Exchange #3
      +- *(3) FileScan parquet customers
```

**Simulation:** count the literal `"Exchange "` occurrences in the plan text above.

```python
exchange_count = plan_text.count("Exchange ")
print(f"  Exchange nodes found in this plan: {exchange_count}")
print(f"  -> Expect {exchange_count} shuffles at runtime, each with its own stage boundary.")
```

**Output:**
```text
  Exchange nodes found in this plan: 3
  -> Expect 3 shuffles at runtime, each with its own stage boundary.
```

---

## 6. Predicate Pushdown and Column Pruning (Before/After)

**Predicate pushdown:** Catalyst moves filter conditions as close to the data source as possible, so the source (Parquet, ORC, JDBC) can skip reading rows/row-groups that can't match, using file-level statistics (min/max per column chunk).

**Column pruning:** Catalyst detects which columns are actually needed by the final query, and rewrites the scan to only read those columns from a columnar format -- other columns are never touched on disk.

Both are visible as a before/after diff between the ANALYZED plan (naive, reads everything) and the OPTIMIZED plan (reads only what's needed, with filters pushed into the scan itself).

```text
ANALYZED LOGICAL PLAN (naive, before optimization)
Project [customer_id#1, amount#2]
+- Filter (amount#2 > 100)
   +- Relation orders[customer_id,amount,region,ts,notes,discount_code] parquet
      (all 6 columns would be read; filter applied AFTER reading)
```

```text
OPTIMIZED LOGICAL PLAN / PHYSICAL PLAN (after Catalyst)
Project [customer_id#1, amount#2]
+- Filter (isnotnull(amount#2) AND (amount#2 > 100))
   +- FileScan parquet orders[customer_id,amount]      <- only 2 of 6 columns read
      PushedFilters: [IsNotNull(amount), GreaterThan(amount,100)]  <- filter pushed to scan
```

**Simulation:** estimate the I/O savings from column pruning on a 200,000-row, 6-column table.

```python
total_columns = 6
columns_needed = 2
total_rows = 200_000
rows_matching_filter = 40_000

bytes_per_col_per_row = 8
naive_bytes = total_columns * total_rows * bytes_per_col_per_row
optimized_bytes = columns_needed * total_rows * bytes_per_col_per_row  # pruning still scans all rows' 2 cols

print(f"  Naive scan (no pruning):      {total_columns} cols x {total_rows} rows = {naive_bytes:,} bytes read")
print(f"  Pruned scan (2 cols needed):  {columns_needed} cols x {total_rows} rows = {optimized_bytes:,} bytes read")
print(f"  Reduction from column pruning: {100 * (1 - optimized_bytes / naive_bytes):.1f}%")
print(f"  Rows actually matching filter: {rows_matching_filter:,} of {total_rows:,} "
      f"(pushdown lets the source skip whole row-groups that can't match)")
```

**Output:**
```text
  Naive scan (no pruning):      6 cols x 200000 rows = 9,600,000 bytes read
  Pruned scan (2 cols needed):  2 cols x 200000 rows = 3,200,000 bytes read
  Reduction from column pruning: 66.7%
  Rows actually matching filter: 40,000 of 200,000 (pushdown lets the source skip whole row-groups that can't match)
```

---

## 7. Worked Example: Reading a Real explain() Output Line by Line

Put it all together: a realistic `explain()` output for a join + aggregation query, read line by line.

```python
orders.join(customers, "customer_id") \
      .groupBy("region") \
      .agg(F.sum("amount").alias("total"))
      .explain()
```

```text
== Physical Plan ==
*(6) HashAggregate(keys=[region#9], functions=[sum(amount#2)])
+- Exchange hashpartitioning(region#9, 200)
   +- *(5) HashAggregate(keys=[region#9], functions=[partial_sum(amount#2)])
      +- *(5) Project [amount#2, region#9]
         +- *(5) BroadcastHashJoin [customer_id#1], [customer_id#8], Inner, BuildRight
            :- *(5) FileScan parquet orders[customer_id,amount] PushedFilters:[IsNotNull(customer_id)]
            +- BroadcastExchange HashedRelationBroadcastMode
               +- *(4) FileScan parquet customers[customer_id,region]
```

**Simulation:** narrate the plan bottom-up, line by line.

```python
narration = [
    "FileScan customers[customer_id,region]  -- small dim table, only needed cols read",
    "BroadcastExchange                        -- customers table is broadcast to every executor",
    "FileScan orders[customer_id,amount]      -- fact table scanned, non-null customer_id pushed down",
    "BroadcastHashJoin (BuildRight)            -- orders joined locally against broadcast customers; NO shuffle of orders",
    "Project [amount, region]                  -- only the columns the aggregation needs survive",
    "HashAggregate (partial_sum)                -- each partition pre-sums amount per region locally",
    "Exchange hashpartitioning(region,200)      -- ONE shuffle: partial sums redistributed by region",
    "HashAggregate (sum)                        -- final per-region totals combined",
]
for i, line in enumerate(narration, start=1):
    print(f"    {i}. {line}")
```

**Output:**
```text
    1. FileScan customers[customer_id,region]  -- small dim table, only needed cols read
    2. BroadcastExchange                        -- customers table is broadcast to every executor
    3. FileScan orders[customer_id,amount]      -- fact table scanned, non-null customer_id pushed down
    4. BroadcastHashJoin (BuildRight)            -- orders joined locally against broadcast customers; NO shuffle of orders
    5. Project [amount, region]                  -- only the columns the aggregation needs survive
    6. HashAggregate (partial_sum)                -- each partition pre-sums amount per region locally
    7. Exchange hashpartitioning(region,200)      -- ONE shuffle: partial sums redistributed by region
    8. HashAggregate (sum)                        -- final per-region totals combined
```

Takeaway from this plan: only ONE Exchange appears, even though there's a join AND a group-by. That's because the join used `BroadcastHashJoin` (no shuffle) -- only the final aggregation required a real shuffle.

---

## Key Takeaways

- Every query passes through Parsed -> Analyzed -> Optimized Logical -> Physical plans; `explain(True)` shows all four.
- `explain("formatted")` is the most human-readable form; `explain("cost")` shows the row/size statistics the optimizer used to make decisions.
- Physical plans print top-down but data flows bottom-up -- always read from the deepest indentation (the Scan) upward.
- Exchange = a shuffle boundary. Count the Exchange nodes in a plan to know exactly how many shuffles the job will perform.
- BroadcastHashJoin avoids shuffling the large side entirely; SortMergeJoin shuffles and sorts both sides -- far more expensive.
- Predicate pushdown and column pruning happen during logical plan optimization, before any physical execution strategy is chosen.
- Reading `explain()` output is the single most useful debugging skill for diagnosing why a Spark job is slow.
