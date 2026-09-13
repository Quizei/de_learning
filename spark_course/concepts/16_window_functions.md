# Concept 16: Window Functions

**Covers:**
- The Window spec: partitionBy, orderBy, rowsBetween/rangeBetween
- Ranking functions: row_number, rank, dense_rank (and tie behavior)
- Analytic/offset functions: lag, lead
- Aggregate-as-window: sum/avg/count OVER a window vs groupBy
- Worked example: running total of sales per customer
- Worked example: top-N-per-group (top 3 paid employees per dept)
- Performance notes: shuffle by partitionBy, unbounded window cost
- Pure-Python simulation of row_number/rank/running-sum

> *Note: this topic isn't in the source YouTube playlist — added because it's essential and commonly asked about.*

*The PySpark snippets below reflect what you'd run against a real Spark session; the worked examples and their output are simulated here in pure Python so you can follow the mechanics without a cluster.*

---

## 1. The window spec

A window function computes a value for each row using a FRAME of related rows — WITHOUT collapsing rows the way `groupBy` does. Every input row still produces exactly one output row.

A `WindowSpec` has three parts:

- `partitionBy(*cols)` — which rows belong "together" (like a `groupBy` key, but rows aren't collapsed)
- `orderBy(*cols)` — ordering within each partition (required for ranking/offset functions, and for meaningful running totals)
- `rowsBetween(start, end)` or `rangeBetween(start, end)` — which rows within the ordered partition are included in the frame for THIS row

`rowsBetween` counts physical rows (e.g. `Window.unboundedPreceding` to `Window.currentRow` = "all rows from the start of the partition up to and including me"). `rangeBetween` is logical: it looks at the VALUE of the order-by column and includes all rows whose value falls in a range (useful for e.g. "all rows within 7 days of this row's date").

```python
from pyspark.sql.window import Window
from pyspark.sql import functions as F

w = (
    Window
    .partitionBy("customer_id")     # rows grouped per customer
    .orderBy("order_date")          # ordered within each customer
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
    # frame = "from the first row of this partition through this row"
)

df.withColumn("running_total", F.sum("amount").over(w))
```

```text
Partition "cust_1" ordered by date:
  row1 (2024-01-01, 100)  <- frame for row1: [row1]
  row2 (2024-01-05, 200)  <- frame for row2: [row1, row2]
  row3 (2024-01-09, 50)   <- frame for row3: [row1, row2, row3]

rowsBetween(-1, 1) (physical): frame = "1 row before me, me, 1 row after"
rangeBetween(-7, 0) on a numeric/date order column: frame = "all rows
    whose order-by value is within 7 units before this row's value"
```

---

## 2. Ranking functions: row_number vs rank vs dense_rank

All three assign a rank within each partition based on `orderBy`, but they differ in how TIES (equal order-by values) are handled:

- `row_number()` — always unique, sequential: 1, 2, 3, 4, 5, ... Ties are broken arbitrarily (whatever order Spark encounters them in) — use this when you need exactly one row per rank (e.g. top-N-per-group).
- `rank()` — ties get the SAME rank, and the next rank SKIPS ahead by the number of tied rows: 1, 2, 2, 4, 5 (two rows tied for 2nd -> next is 4th, not 3rd).
- `dense_rank()` — ties get the SAME rank, but the next rank does NOT skip: 1, 2, 2, 3, 4 (no gaps).

```python
w = Window.partitionBy("dept").orderBy(F.desc("salary"))

df.select(
    "name", "dept", "salary",
    F.row_number().over(w).alias("row_number"),
    F.rank().over(w).alias("rank"),
    F.dense_rank().over(w).alias("dense_rank"),
)
```

**Simulation:** ranking functions on salaries, with a tie.

```python
salaries = [("alice", 90000), ("bob", 90000), ("carol", 85000), ("dave", 80000)]
salaries_sorted = sorted(salaries, key=lambda x: -x[1])

prev_salary = None
rank_val = 0
dense_rank_val = 0
for i, (name, salary) in enumerate(salaries_sorted, start=1):
    row_number = i
    if salary != prev_salary:
        rank_val = i
        dense_rank_val += 1
    prev_salary = salary
```

**Output:**
```text
name    salary    row_number  rank    dense_rank
alice   90000     1           1       1
bob     90000     2           1       1
carol   85000     3           3       2
dave    80000     4           4       3
```

Notice: alice/bob tie at 90000 -> both get `rank=1`, `dense_rank=1`, but `row_number` breaks the tie (1, 2). `rank()` then jumps to 3 for carol (skipping 2, because 2 rows occupied rank 1); `dense_rank()` doesn't skip and gives carol 2.

---

## 3. Analytic functions: lag and lead

`lag(col, n)` — value of `col` from n rows BEFORE the current row, within the same partition/order (default n=1). `lead(col, n)` — value of `col` from n rows AFTER the current row.

Both return NULL (or a supplied default) when there's no such row (e.g. `lag` on the first row of a partition). Extremely common for period-over-period comparisons: "sales this month vs last month", "time since previous event", etc.

```python
w = Window.partitionBy("customer_id").orderBy("order_date")

df.select(
    "customer_id", "order_date", "amount",
    F.lag("amount", 1).over(w).alias("prev_amount"),
    F.lead("amount", 1).over(w).alias("next_amount"),
    (F.col("amount") - F.lag("amount", 1).over(w)).alias("change_vs_prev"),
)
```

**Simulation:** lag/lead for one customer's ordered purchases.

```python
orders = [("2024-01-01", 100), ("2024-01-05", 250), ("2024-01-09", 80)]

for i, (date, amt) in enumerate(orders):
    prev_amt = orders[i - 1][1] if i - 1 >= 0 else None
    next_amt = orders[i + 1][1] if i + 1 < len(orders) else None
    change = amt - prev_amt if prev_amt is not None else None
```

**Output:**
```text
date        amount  prev_amount  next_amount  change_vs_prev
2024-01-01  100     None         250          None
2024-01-05  250     100          80           150
2024-01-09  80      250          None         -170
```

---

## 4. Aggregate-as-window vs groupBy

The same aggregate functions (`sum`, `avg`, `count`, `min`, `max`) can be used two ways, and they behave VERY differently:

- `groupBy("key").agg(F.sum("amt"))` -> COLLAPSES all rows per key into ONE output row. You lose the original row-level detail.
- `F.sum("amt").over(Window.partitionBy("key"))` -> Keeps EVERY original row, and adds a column with the aggregate computed over that row's window/frame. If the frame is the whole partition (default when no `orderBy`/`rowsBetween` is given, or an explicit `unboundedPreceding->unboundedFollowing`), every row in the partition gets the SAME total (like a "broadcast" of the group's aggregate back onto each row). If ordered with a running frame (`unboundedPreceding->currentRow`), each row gets a RUNNING total up to that row instead.

```python
# groupBy: collapses rows
df.groupBy("customer_id").agg(F.sum("amount").alias("total"))
# -> 1 row per customer_id

# window, whole-partition frame: keeps rows, repeats the total
w_total = Window.partitionBy("customer_id")
df.withColumn("customer_total", F.sum("amount").over(w_total))
# -> every row for a customer shows the SAME customer_total

# window, running frame: keeps rows, running total up to this row
w_running = Window.partitionBy("customer_id").orderBy("order_date") \
                   .rowsBetween(Window.unboundedPreceding, Window.currentRow)
df.withColumn("running_total", F.sum("amount").over(w_running))
```

**Simulation:** groupBy total vs window total vs running total.

```python
orders = [
    ("cust_1", "2024-01-01", 100),
    ("cust_1", "2024-01-05", 200),
    ("cust_1", "2024-01-09", 50),
    ("cust_2", "2024-01-02", 300),
]

# groupBy-style total
totals = {}
for cust, _, amt in orders:
    totals[cust] = totals.get(cust, 0) + amt

# window totals (whole-partition) vs running total
running = {}
for cust, date, amt in orders:
    running[cust] = running.get(cust, 0) + amt
```

**Output:**
```text
groupBy result: {'cust_1': 350, 'cust_2': 300}

customer  date        amount  window_total  running_total
cust_1    2024-01-01  100     350           100
cust_1    2024-01-05  200     350           300
cust_1    2024-01-09  50      350           350
cust_2    2024-01-02  300     300           300
```

---

## 5. Worked example: running total of sales per customer

Full worked example: running total of sales per customer, ordered by order date, using an unbounded-preceding-to-current-row frame.

```python
from pyspark.sql.window import Window
from pyspark.sql import functions as F

w = (
    Window.partitionBy("customer_id")
          .orderBy("order_date")
          .rowsBetween(Window.unboundedPreceding, Window.currentRow)
)

result = sales_df.withColumn("running_total", F.sum("amount").over(w))
result.orderBy("customer_id", "order_date").show()
```

**Simulation:**

```python
sales = [
    ("cust_A", "2024-01-01", 120),
    ("cust_A", "2024-01-03", 80),
    ("cust_A", "2024-01-10", 200),
    ("cust_B", "2024-01-02", 50),
    ("cust_B", "2024-01-06", 150),
]

running_totals = {}
for cust, date, amt in sales:
    running_totals[cust] = running_totals.get(cust, 0) + amt
```

**Output:**
```text
customer  date        amount  running_total
cust_A    2024-01-01  120     120
cust_A    2024-01-03  80      200
cust_A    2024-01-10  200     400
cust_B    2024-01-02  50      50
cust_B    2024-01-06  150     200
```

---

## 6. Worked example: top-N-per-group

Top-N-per-group is one of the most common interview questions: "top 3 highest-paid employees per department." Pattern:

1. `row_number()` over a window partitioned by group, ordered by the ranking column descending
2. filter `WHERE row_number <= N`

Use `row_number` (not `rank`) when you want EXACTLY N rows per group even in the presence of ties — `rank()` could return more than N rows if there's a tie at the Nth position.

```python
w = Window.partitionBy("department").orderBy(F.desc("salary"))

top_3_per_dept = (
    employees_df
    .withColumn("rn", F.row_number().over(w))
    .filter(F.col("rn") <= 3)
    .drop("rn")
)
```

**Simulation:** top-2-per-department.

```python
employees = [
    ("eng", "alice", 150000),
    ("eng", "bob", 140000),
    ("eng", "carol", 130000),
    ("eng", "dave", 120000),
    ("sales", "erin", 110000),
    ("sales", "frank", 105000),
    ("sales", "gina", 95000),
]

by_dept = {}
for dept, name, salary in employees:
    by_dept.setdefault(dept, []).append((name, salary))

top_n = 2
for dept, people in by_dept.items():
    ranked = sorted(people, key=lambda x: -x[1])
    top = ranked[:top_n]
```

**Output:**
```text
eng: top 2 -> [('alice', 150000), ('bob', 140000)]
sales: top 2 -> [('erin', 110000), ('frank', 105000)]
```

---

## 7. Performance notes

Window functions are convenient but not free:

- `partitionBy(key)` causes a SHUFFLE, exactly like `groupBy(key)` — Spark must move rows so all rows sharing a partition key end up together (and, with `orderBy`, sorted) on the same task. If your partition key is skewed, one task gets a disproportionate share of rows — same skew problem as a skewed join/groupBy (see `concepts/07_data_skew.py` and `concepts/08_salting.py`).
- UNBOUNDED frames (e.g. `unboundedPreceding` to `unboundedFollowing`, or omitting `rowsBetween` entirely, which often defaults to the whole partition for aggregate functions) require materializing the whole partition's relevant data before producing any output row's result — this can be expensive/memory-heavy for very large partitions (e.g. one customer with 50 million rows).
- Multiple window functions with DIFFERENT `partitionBy`/`orderBy` specs in the same query each trigger their OWN shuffle+sort — consolidate to a shared window spec where the logic allows it, to avoid paying for redundant shuffles.

```text
- partitionBy(key) -> shuffle by key (same cost profile as groupBy/join)
- Skewed partition key -> one task does far more work (see 07/08)
- Unbounded window frames over huge partitions -> memory pressure
- Multiple differently-specified windows in one query -> multiple
  separate shuffles; reuse one window spec where possible
```

---

## 8. Simulation: window mechanics implemented by hand

Ties everything together: implement `partitionBy` + `orderBy` + `row_number` + `rank` + running sum completely by hand, over a small partitioned/ordered dataset, to make the underlying mechanics concrete (this is conceptually close to what Spark does per-partition after the shuffle+sort).

```python
data = [
    ("east", "2024-01-03", 90),
    ("east", "2024-01-01", 120),
    ("west", "2024-01-02", 200),
    ("east", "2024-01-02", 120),   # tie with the row above on amount
    ("west", "2024-01-01", 150),
]

# Step 1: partitionBy region
partitions = {}
for region, date, amt in data:
    partitions.setdefault(region, []).append((date, amt))

# Step 2: orderBy date within each partition
for region in partitions:
    partitions[region].sort(key=lambda x: x[0])

# Step 3: row_number, rank (by amount desc within partition), running sum (by date)
for region, rows in partitions.items():
    # running sum in date order
    running = 0
    running_sums = []
    for date, amt in rows:
        running += amt
        running_sums.append(running)

    # rank by amount desc (recompute order for ranking purposes)
    rank_order = sorted(rows, key=lambda x: -x[1])
    rank_lookup = {}
    prev_amt = None
    current_rank = 0
    for i, (date, amt) in enumerate(rank_order, start=1):
        if amt != prev_amt:
            current_rank = i
        rank_lookup[(date, amt)] = current_rank
        prev_amt = amt

    for i, (date, amt) in enumerate(rows):
        row_number = i + 1
        rank = rank_lookup[(date, amt)]
```

**Output:**
```text
Step 1 -- partitionBy('region'):
  east: [('2024-01-03', 90), ('2024-01-01', 120), ('2024-01-02', 120)]
  west: [('2024-01-02', 200), ('2024-01-01', 150)]

Step 2 -- orderBy('date') within each partition:
  east: [('2024-01-01', 120), ('2024-01-02', 120), ('2024-01-03', 90)]
  west: [('2024-01-01', 150), ('2024-01-02', 200)]

Step 3 -- row_number / rank (by amount desc) / running_sum (by date):
  region  date        amount  row_number  rank  running_sum
  east    2024-01-01  120     1           1     120
  east    2024-01-02  120     2           1     240
  east    2024-01-03  90      3           3     330
  west    2024-01-01  150     1           2     150
  west    2024-01-02  200     2           1     350
```

Notice 'east' has a tie (120, 120) — both get rank 1 (dense/rank behavior for ties), while `row_number` still assigns 1, 2 in whatever order they appear after sorting. This is exactly the per-partition, per-order-key logic Spark runs after shuffling rows to group by `partitionBy` and sorting by `orderBy` within each task.

---

## Key Takeaways

- Window functions compute a value per row using a frame of related rows, WITHOUT collapsing rows the way `groupBy` does.
- A `WindowSpec` = `partitionBy` (grouping) + `orderBy` (ordering) + `rowsBetween`/`rangeBetween` (which rows are in the frame).
- `row_number` is always unique per partition; `rank` skips after ties; `dense_rank` doesn't skip after ties — pick based on what you need.
- `lag`/`lead` pull values from neighboring rows for period-over-period comparisons; they return null with no default when there's no such row (e.g. first/last row of a partition).
- The same aggregate function behaves differently as a window (keeps all rows, can produce running totals) vs a `groupBy` (collapses to one row per key).
- Top-N-per-group = `row_number().over(window)` + `filter(rn <= N)`; use `row_number`, not `rank`, to guarantee exactly N rows.
- `partitionBy` triggers a shuffle just like `groupBy`/`join` — skewed partition keys and unbounded frames over huge partitions both hurt performance.
