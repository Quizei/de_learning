# Concept 02: Window Functions

**Covers:**
- The window spec: `PARTITION BY`, `ORDER BY`, `ROWS`/`RANGE BETWEEN`
- Ranking: `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `NTILE` — and exactly how ties differ
- Offset functions: `LAG`, `LEAD`
- `FIRST_VALUE` / `LAST_VALUE` and the default-frame trap
- Running totals and moving averages with `SUM()`/`AVG() OVER (...)`
- Window vs `GROUP BY` — same aggregate function, very different result shape
- Worked example: top-N-per-group, the single most common window-function interview ask

> Every query runs against **SQLite 3.25+** (window function support landed
> there; `sqlite3` in a recent Python ships a new-enough version).

---

## 0. Setup — run this once

```python
import sqlite3
conn = sqlite3.connect(":memory:")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE employees (
        emp_id     INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        department TEXT NOT NULL,
        title      TEXT NOT NULL,
        salary     REAL NOT NULL,
        hire_date  TEXT NOT NULL
    )
""")
cur.executemany("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)", [
    (1,  "Alice", "Engineering", "Senior Engineer",    130000, "2019-03-15"),
    (2,  "Bob",   "Engineering", "Engineer",            95000, "2020-07-01"),
    (3,  "Carol", "Engineering", "Engineer",            95000, "2021-01-10"),
    (4,  "David", "Engineering", "Junior Engineer",     72000, "2022-06-20"),
    (5,  "Eve",   "Marketing",   "Marketing Director", 115000, "2018-11-05"),
    (6,  "Frank", "Marketing",   "Marketing Manager",   88000, "2020-04-18"),
    (7,  "Grace", "Marketing",   "Marketing Analyst",   65000, "2022-09-01"),
    (8,  "Hank",  "Sales",       "Sales Director",     120000, "2017-08-22"),
    (9,  "Ivy",   "Sales",       "Sales Manager",       92000, "2019-12-30"),
    (10, "Jack",  "Sales",       "Sales Rep",           58000, "2021-05-14"),
    (11, "Karen", "Sales",       "Sales Rep",           58000, "2022-02-28"),
    (12, "Leo",   "Sales",       "Sales Rep",           55000, "2023-01-09"),
])

cur.execute("""
    CREATE TABLE monthly_revenue (
        month    TEXT PRIMARY KEY,
        revenue  REAL NOT NULL,
        expenses REAL NOT NULL
    )
""")
cur.executemany("INSERT INTO monthly_revenue VALUES (?, ?, ?)", [
    ("2023-01", 120000, 95000), ("2023-02", 135000, 98000),
    ("2023-03", 128000, 92000), ("2023-04", 142000, 101000),
    ("2023-05", 155000, 105000), ("2023-06", 148000, 110000),
    ("2023-07", 162000, 108000), ("2023-08", 158000, 112000),
    ("2023-09", 171000, 115000), ("2023-10", 180000, 118000),
    ("2023-11", 175000, 120000), ("2023-12", 195000, 125000),
])
conn.commit()
```

---

## 1. The window spec: PARTITION BY, ORDER BY, frame

A window function computes a value **per row**, using a frame of related
rows, without collapsing anything — the row count in equals the row count
out. That's the entire conceptual difference from `GROUP BY`.

```text
function_name(...) OVER (
    [PARTITION BY col1, col2, ...]   -- which rows belong "together"
    [ORDER BY col3, col4, ...]       -- order within each partition
    [ROWS|RANGE BETWEEN start AND end]  -- which rows THIS row's frame includes
)
```

- **`PARTITION BY`** — like a `GROUP BY` key, but rows aren't collapsed.
- **`ORDER BY`** — required for ranking/offset functions, and it changes
  the *default* frame (see the running-total gotcha in section 6).
- **`ROWS BETWEEN`** counts physical rows (`1 PRECEDING` = the literal row
  before this one). **`RANGE BETWEEN`** is logical — it looks at the
  *value* of the order-by column (e.g. "all rows within 7 days of this
  row's date"), which matters when there are ties in the order-by column.

```text
Partition "Engineering", ordered by hire_date:
  Alice (2019-03-15)  <- frame for Alice, ROWS UNBOUNDED PRECEDING..CURRENT: [Alice]
  Bob   (2020-07-01)  <- frame for Bob:                                     [Alice, Bob]
  Carol (2021-01-10)  <- frame for Carol:                                   [Alice, Bob, Carol]
  David (2022-06-20)  <- frame for David:                                   [Alice, Bob, Carol, David]
```

---

## 2. Ranking: ROW_NUMBER, RANK, DENSE_RANK

All three number rows within a partition by `ORDER BY` — they differ **only**
in how ties are handled, and that difference is asked about in nearly every
SQL round.

```sql
SELECT name, salary,
       ROW_NUMBER() OVER (ORDER BY salary DESC) AS row_num,
       RANK()       OVER (ORDER BY salary DESC) AS rank_val,
       DENSE_RANK() OVER (ORDER BY salary DESC) AS dense_rank_val
FROM employees
WHERE department = 'Sales';
```

**Output:**
```text
name    salary    row_num   rank_val   dense_rank_val
Hank    120000     1         1          1
Ivy      92000     2         2          2
Jack     58000     3         3          3
Karen    58000     4         3          3   <- tie with Jack
Leo      55000     5         5          4   <- RANK skips to 5, DENSE_RANK doesn't
```

- `ROW_NUMBER()` — always unique (1,2,3,4,5); ties broken arbitrarily. Use
  when you need **exactly one row per rank** (top-N-per-group, dedup).
- `RANK()` — ties share a rank, next rank **skips** by the tie count
  (1,2,3,3,5 — two rows share 3rd, so the next is 5th, not 4th).
- `DENSE_RANK()` — ties share a rank, **no skip** (1,2,3,3,4).

---

## 3. NTILE

`NTILE(n)` divides the ordered partition into `n` roughly-equal buckets,
numbering each row 1..n — the tool for quartile/percentile-style bucketing.

```sql
SELECT NTILE(4) OVER (ORDER BY salary) AS quartile, name, salary
FROM employees
ORDER BY salary;
```
Q1 is the lowest quarter of earners, Q4 the highest. Within a department:
```sql
SELECT department,
       NTILE(2) OVER (PARTITION BY department ORDER BY salary DESC) AS tier,
       name, salary
FROM employees
ORDER BY department, tier, salary DESC;
```
`tier = 1` is each department's upper half, `tier = 2` its lower half.

---

## 4. LAG and LEAD

`LAG(col, n, default)` reads a value from `n` rows **before** the current
row in partition/order; `LEAD` reads `n` rows **after**. `n` defaults to 1;
`default` (returned when no such row exists) defaults to `NULL`. This is the
standard pattern for period-over-period comparisons.

```sql
SELECT month, revenue,
       LAG(revenue, 1) OVER (ORDER BY month) AS prev_month_rev,
       revenue - LAG(revenue, 1) OVER (ORDER BY month) AS change,
       ROUND((revenue - LAG(revenue, 1) OVER (ORDER BY month)) * 100.0
             / LAG(revenue, 1) OVER (ORDER BY month), 1) AS pct_change
FROM monthly_revenue
ORDER BY month;
```

**Output (excerpt):**
```text
month     revenue   prev_month_rev   change    pct_change
2023-01   120000    None             None      None      <- no previous month
2023-02   135000    120000           +15000    +12.5
2023-03   128000    135000           -7000     -5.2
```

`change` and `pct_change` are `NULL` for January because arithmetic with
`NULL` produces `NULL` — supply a default explicitly if you'd rather have 0:
`LAG(revenue, 1, 0) OVER (...)`.

---

## 5. FIRST_VALUE and LAST_VALUE — the default-frame trap

`FIRST_VALUE`/`LAST_VALUE` return the first/last value in the **frame**.
The trap: the *default* frame when `ORDER BY` is present is
`RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` — which means
`LAST_VALUE` just returns **the current row**, not the partition's actual
last row. This single gotcha is a favorite "predict the output" interview
question.

```sql
-- WRONG (implicit default frame): LAST_VALUE just echoes the current row
SELECT name, department, salary,
       LAST_VALUE(salary) OVER (PARTITION BY department ORDER BY salary DESC) AS dept_lowest
FROM employees;
-- dept_lowest here is just each row's own salary, NOT the department minimum!

-- CORRECT: explicitly widen the frame to the whole partition
SELECT name, department, salary,
       FIRST_VALUE(salary) OVER (
           PARTITION BY department ORDER BY salary DESC
           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
       ) AS dept_highest,
       LAST_VALUE(salary) OVER (
           PARTITION BY department ORDER BY salary DESC
           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
       ) AS dept_lowest
FROM employees
ORDER BY department, salary DESC;
```

Every employee in a department now correctly sees that department's
highest and lowest salary. Say this rule out loud whenever you use
`LAST_VALUE`: *"I need to widen the frame to `UNBOUNDED FOLLOWING`, or
`LAST_VALUE` is a no-op."*

---

## 6. Running totals and moving averages

`SUM() OVER (ORDER BY ...)` with no explicit frame defaults to
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` — which is exactly a
running total, "for free":

```sql
SELECT month, revenue,
       SUM(revenue) OVER (ORDER BY month) AS cumulative_revenue
FROM monthly_revenue
ORDER BY month;
```
**Output (excerpt):** `2023-01 -> 120,000`, `2023-02 -> 255,000`,
`2023-03 -> 383,000`, growing every month.

A **moving average** uses an explicit bounded frame instead of the
unbounded default:

```sql
-- 3-month trailing moving average
SELECT month, revenue,
       ROUND(AVG(revenue) OVER (
           ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
       ), 0) AS moving_avg_3m
FROM monthly_revenue
ORDER BY month;
```
**Output (excerpt):** January `120,000` (only 1 row available), February
`127,500` (2 rows), March `127,667` (full 3-row window), April `135,000`, ...

```text
- ROWS BETWEEN 2 PRECEDING AND CURRENT ROW  -> 3-point TRAILING average
- ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING  -> 3-point CENTERED average
- omitting ROWS/RANGE with an ORDER BY      -> defaults to UNBOUNDED
  PRECEDING..CURRENT ROW for aggregate functions -- i.e. a running total,
  not the whole-partition total. This default is exactly why the same
  SUM()/AVG() OVER (...) behaves so differently depending on whether an
  ORDER BY is present (see section 7).
```

---

## 7. Window aggregate vs GROUP BY — same function, different shape

The exact same aggregate function (`SUM`, `AVG`, `COUNT`, ...) behaves
completely differently depending on whether it's a `GROUP BY` or a window:

```sql
-- GROUP BY: COLLAPSES rows -- one row per customer
SELECT customer_id, SUM(amount) AS total
FROM orders
GROUP BY customer_id;

-- Window, whole-partition frame (no ORDER BY): KEEPS every row,
-- repeats the SAME total onto every row of the partition
SELECT customer_id, order_date, amount,
       SUM(amount) OVER (PARTITION BY customer_id) AS customer_total
FROM orders;

-- Window, running frame (ORDER BY present): KEEPS every row,
-- each gets a RUNNING total up to that row
SELECT customer_id, order_date, amount,
       SUM(amount) OVER (
           PARTITION BY customer_id ORDER BY order_date
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS running_total
FROM orders;
```

```text
groupBy-style result:      {'cust_1': 350, 'cust_2': 300}

customer  date        amount  window_total  running_total
cust_1    2024-01-01  100     350           100
cust_1    2024-01-05  200     350           300
cust_1    2024-01-09  50      350           350
cust_2    2024-01-02  300     300           300
```

This is the single sentence to have ready for "what's the difference
between a window function and GROUP BY": *"GROUP BY collapses rows to one
per group; a window function keeps every row and adds a computed column,
using the same-shaped aggregate."*

Also true, and worth a warning: `PARTITION BY` triggers a shuffle/sort on a
distributed engine exactly like `GROUP BY`/`JOIN` does — a skewed partition
key hurts a window function the same way it hurts a `GROUP BY` (see
[`spark_course/concepts/07_data_skew.md`](../../../spark_course/concepts/07_data_skew.md)
if that's unfamiliar) — and an unbounded frame over a huge partition can be
expensive to materialize.

---

## 8. Worked example: top-N-per-group

The single most common window-function interview question: *"top 3
highest-paid employees per department."* The pattern is always the same —
rank, then filter:

```sql
SELECT dept_rank, name, department, salary
FROM (
    SELECT ROW_NUMBER() OVER (
               PARTITION BY department ORDER BY salary DESC
           ) AS dept_rank,
           name, department, salary
    FROM employees
)
WHERE dept_rank <= 2
ORDER BY department, dept_rank;
```

**Output:**
```text
dept_rank   name    department    salary
1           Alice   Engineering   130000.0
2           Bob     Engineering   95000.0
1           Eve     Marketing     115000.0
2           Frank   Marketing     88000.0
1           Hank    Sales         120000.0
2           Ivy     Sales         92000.0
```

Use `ROW_NUMBER()`, **not** `RANK()`, for this pattern. If two employees
tie for the 2nd-highest salary in a department, `RANK()` would let *both*
through `WHERE dept_rank <= 2` (producing 3 rows for that department) —
`ROW_NUMBER()` guarantees exactly N rows per group regardless of ties,
because it never repeats a rank. A window function must always live in a
subquery/CTE before you can filter on it — `WHERE dept_rank <= 2` directly
in the same `SELECT` is illegal, because `WHERE` runs before window
functions are computed (see the logical order-of-operations diagram in
[Concept 04](04_aggregations_and_grouping.md)).

---

## Key Takeaways

- A window function computes a value per row over a frame of related rows
  **without** collapsing rows — row count in equals row count out.
- `ROW_NUMBER` is always unique per partition; `RANK` skips after ties;
  `DENSE_RANK` doesn't skip — the tie behavior is the entire distinction.
- `LAG`/`LEAD` pull neighboring-row values for period-over-period
  comparisons and return `NULL` (or a supplied default) with no such row.
- `LAST_VALUE` with the *default* frame just echoes the current row — you
  must explicitly widen the frame to `UNBOUNDED FOLLOWING` to get the
  partition's real last value. This is a classic gotcha question.
- `SUM()/AVG() OVER (ORDER BY ...)` with no explicit frame defaults to a
  running total (`UNBOUNDED PRECEDING .. CURRENT ROW`), not a whole-partition
  total — add `ROWS BETWEEN ... PRECEDING AND ... FOLLOWING` for a moving
  average, or drop `ORDER BY` for a whole-partition total.
- The same aggregate function behaves differently as a window (keeps rows,
  can run cumulative) vs `GROUP BY` (collapses to one row per key).
- Top-N-per-group = `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` in a
  subquery, then `WHERE rn <= N` in the outer query — use `ROW_NUMBER`, not
  `RANK`, to guarantee exactly N rows regardless of ties.
