# Concept 04: Aggregations & Grouping

**Covers:**
- `GROUP BY` basics, grouping by multiple columns and by expressions
- `WHERE` vs `HAVING` — filter rows before aggregation vs filter groups after
- The five core aggregates: `COUNT(*)` vs `COUNT(col)`, `SUM`, `AVG`, `MIN`, `MAX`, and how NULLs interact with each
- `GROUP_CONCAT`/`STRING_AGG` — string aggregation
- Conditional aggregation: `CASE` inside an aggregate, and pivot-style queries
- `COALESCE` with aggregates for "include zero-activity groups"
- `GROUPING SETS`, `ROLLUP`, `CUBE` — multiple grouping levels in one query (and the SQLite workaround, since SQLite has none of the three)
- The full logical order of operations, and why it explains every `HAVING`/`WHERE`/alias gotcha

> Queries run against **SQLite**. `GROUPING SETS`/`ROLLUP`/`CUBE` are **not**
> supported by SQLite — section 7 shows the standard syntax (Postgres/
> SQL Server/BigQuery/Snowflake all support it) alongside the portable
> `UNION ALL` workaround, because "what if your engine doesn't have this"
> is itself a fair follow-up question.

---

## 0. Setup — run this once

```python
import sqlite3
conn = sqlite3.connect(":memory:")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE products (
        product_id   INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category     TEXT NOT NULL,
        unit_price   REAL NOT NULL
    )
""")
cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", [
    (1, "Laptop Pro",     "Electronics", 1299.99),
    (2, "Wireless Mouse", "Electronics",   29.99),
    (3, "USB-C Hub",      "Electronics",   49.99),
    (4, "Desk Chair",     "Furniture",    399.99),
    (5, "Standing Desk",  "Furniture",    599.99),
    (6, "Monitor Arm",    "Furniture",     89.99),
    (7, "Python Book",    "Books",         39.99),
    (8, "SQL Cookbook",   "Books",         44.99),
    (9, "Data Eng Guide", "Books",         54.99),
])

cur.execute("CREATE TABLE regions (region_id INTEGER PRIMARY KEY, region_name TEXT NOT NULL)")
cur.executemany("INSERT INTO regions VALUES (?, ?)", [
    (1, "North"), (2, "South"), (3, "East"), (4, "West"),
])

cur.execute("""
    CREATE TABLE sales (
        sale_id    INTEGER PRIMARY KEY,
        product_id INTEGER NOT NULL,
        region_id  INTEGER NOT NULL,
        quantity   INTEGER NOT NULL,
        sale_date  TEXT NOT NULL,
        discount   REAL DEFAULT 0
    )
""")
cur.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)", [
    (1,  1, 1, 2,  "2023-01-15", 0.0),  (2,  2, 1, 10, "2023-01-20", 0.1),
    (3,  4, 2, 3,  "2023-02-05", 0.0),  (4,  7, 3, 15, "2023-02-12", 0.05),
    (5,  1, 2, 1,  "2023-03-01", 0.15), (6,  5, 1, 2,  "2023-03-18", 0.0),
    (7,  3, 4, 8,  "2023-04-02", 0.1),  (8,  8, 3, 12, "2023-04-20", 0.0),
    (9,  6, 2, 5,  "2023-05-10", 0.0),  (10, 2, 3, 20, "2023-05-25", 0.2),
    (11, 9, 4, 7,  "2023-06-08", 0.0),  (12, 1, 1, 3,  "2023-06-15", 0.1),
    (13, 5, 3, 1,  "2023-07-01", 0.0),  (14, 4, 4, 2,  "2023-07-12", 0.05),
    (15, 3, 1, 5,  "2023-08-03", 0.0),  (16, 7, 2, 10, "2023-08-22", 0.1),
    (17, 8, 1, 6,  "2023-09-10", 0.0),  (18, 2, 4, 15, "2023-09-28", 0.15),
    (19, 6, 3, 3,  "2023-10-05", 0.0),  (20, 1, 4, 1,  "2023-10-18", 0.2),
    (21, 9, 1, 4,  "2023-11-02", 0.0),  (22, 5, 2, 2,  "2023-11-15", 0.1),
    (23, 4, 1, 1,  "2023-12-01", 0.0),  (24, 7, 4, 8,  "2023-12-10", 0.0),
    (25, 2, 2, 25, "2023-12-20", 0.0),
])
conn.commit()
```

---

## 1. GROUP BY basics

`GROUP BY` partitions rows into groups; each group collapses into exactly
one output row. Every column in `SELECT` must be either in `GROUP BY` or
wrapped in an aggregate — anything else is ambiguous ("which row's value do
you mean, out of the whole group?") and most engines reject it outright.

```sql
SELECT p.category, COUNT(*) AS num_sales
FROM sales s
JOIN products p ON s.product_id = p.product_id
GROUP BY p.category
ORDER BY num_sales DESC;
```
**Output:** `Electronics` (11 sales), `Furniture` (8), `Books` (6).

Group by multiple columns for a finer grain, or by an expression (a common
one: truncating a date down to month):
```sql
SELECT SUBSTR(sale_date, 1, 7) AS month, COUNT(*) AS num_sales, SUM(quantity) AS total_units
FROM sales
GROUP BY SUBSTR(sale_date, 1, 7)
ORDER BY month;
```

---

## 2. WHERE vs HAVING

`WHERE` filters individual rows **before** grouping happens; `HAVING`
filters groups **after** aggregation. This is the most-tested single fact
in this file — mixing them up either throws an error (using an aggregate in
`WHERE`) or silently computes the wrong thing (filtering pre-aggregate rows
with `HAVING` when `WHERE` would be cheaper and clearer).

```sql
SELECT p.product_name, COUNT(*) AS times_sold, SUM(s.quantity) AS total_units
FROM sales s
JOIN products p ON s.product_id = p.product_id
GROUP BY p.product_id, p.product_name
HAVING COUNT(*) > 3          -- filters GROUPS, after aggregation
ORDER BY times_sold DESC;
```
**Output:** Wireless Mouse (sold 4 times, 70 units), Laptop Pro (sold 4
times, 7 units).

Combine both — `WHERE` narrows rows cheaply first, `HAVING` filters the
resulting aggregates:
```sql
SELECT r.region_name,
       SUM(s.quantity * p.unit_price * (1 - s.discount)) AS revenue,
       COUNT(*) AS num_sales
FROM sales s
JOIN products p ON s.product_id = p.product_id
JOIN regions r  ON s.region_id  = r.region_id
WHERE s.sale_date >= '2023-07-01'                                   -- WHERE: rows first
GROUP BY r.region_name
HAVING SUM(s.quantity * p.unit_price * (1 - s.discount)) > 1000      -- HAVING: groups after
ORDER BY revenue DESC;
```

```text
FROM/JOIN -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY -> LIMIT
              ^                     ^
        filters ROWS         filters GROUPS
        (pre-aggregate)      (post-aggregate)
```

---

## 3. The five core aggregates, and how NULL breaks intuition

`COUNT(*)`, `COUNT(col)`, `SUM`, `AVG`, `MIN`/`MAX` — the fundamentals. The
one that trips people up: **every aggregate except `COUNT(*)` silently
ignores `NULL`s.**

```sql
SELECT
    COUNT(*)                    AS total,
    COUNT(NULLIF(discount, 0))  AS sales_with_discount   -- NULLIF turns 0 into NULL, so COUNT skips it
FROM sales;
```

The `AVG` trap specifically: `AVG(rating)` divides by the count of
**non-NULL** rows, not the total row count. Given `[5, 4, NULL, 3, NULL]`,
`AVG(rating)` is `(5+4+3)/3 = 4.0`, **not** `(5+4+0+3+0)/5 = 2.4` — if you
actually want NULLs treated as zero in the average, you must say so
explicitly: `AVG(COALESCE(rating, 0))`. This single gotcha (assuming
`AVG` averages over all rows including NULLs) produces real, silent
reporting bugs.

```sql
SELECT p.product_name, p.category,
       COUNT(*) AS times_sold,
       SUM(s.quantity) AS units_sold,
       ROUND(SUM(s.quantity * p.unit_price * (1 - s.discount)), 2) AS total_revenue,
       ROUND(AVG(s.quantity * p.unit_price * (1 - s.discount)), 2) AS avg_per_sale
FROM sales s
JOIN products p ON s.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY total_revenue DESC;
```

---

## 4. GROUP_CONCAT / STRING_AGG

String aggregation collapses a group's text values into one delimited
string — SQLite calls it `GROUP_CONCAT(col, separator)`; Postgres/SQL
Server call the same idea `STRING_AGG(col, separator)`.

```sql
SELECT category, GROUP_CONCAT(product_name, ', ') AS products, COUNT(*) AS count
FROM products
GROUP BY category
ORDER BY category;
```
**Output:**
```text
Books          (3 products): Python Book, SQL Cookbook, Data Eng Guide
Electronics    (3 products): Laptop Pro, Wireless Mouse, USB-C Hub
Furniture      (3 products): Desk Chair, Standing Desk, Monitor Arm
```
Add `DISTINCT` inside the aggregate the same way you would for `COUNT`:
`GROUP_CONCAT(DISTINCT r.region_name, ', ')` de-duplicates repeated values
in the concatenated string.

---

## 5. CASE inside an aggregate — conditional counting, pivots

`CASE` inside `SUM`/`COUNT` is the foundation of conditional aggregation and
pivot-style reporting — turning row-wise categories into columns.

```sql
-- Conditional counting
SELECT
    COUNT(*) AS total_sales,
    COUNT(CASE WHEN discount = 0                     THEN 1 END) AS no_discount,
    COUNT(CASE WHEN discount > 0 AND discount <= 0.1 THEN 1 END) AS small_discount,
    COUNT(CASE WHEN discount > 0.1                    THEN 1 END) AS large_discount
FROM sales;
```
**Output:** `total=25, no_discount=14, small_discount=7, large_discount=4`.

`COUNT(CASE WHEN ... THEN 1 END)` works because the implicit `ELSE` is
`NULL`, and `COUNT` ignores `NULL`s — this is the same NULL-skipping
behavior from section 3, used deliberately here as a filtering trick.

```sql
-- Pivot: units sold per product, one column per region
SELECT p.product_name,
       SUM(CASE WHEN r.region_name = 'North' THEN s.quantity ELSE 0 END) AS north,
       SUM(CASE WHEN r.region_name = 'South' THEN s.quantity ELSE 0 END) AS south,
       SUM(CASE WHEN r.region_name = 'East'  THEN s.quantity ELSE 0 END) AS east,
       SUM(CASE WHEN r.region_name = 'West'  THEN s.quantity ELSE 0 END) AS west,
       SUM(s.quantity) AS total
FROM sales s
JOIN products p ON s.product_id = p.product_id
JOIN regions r  ON s.region_id  = r.region_id
GROUP BY p.product_id, p.product_name
ORDER BY total DESC;
```
Here `SUM(CASE ... ELSE 0 END)` (not `ELSE NULL`) is deliberate — `SUM` of
an all-`NULL` group returns `NULL`, not `0`, and a pivot column should read
`0` for "no sales in this region," not blank.

---

## 6. COALESCE with aggregates — including zero-activity groups

`LEFT JOIN` + `COALESCE` is how you make sure a group with **zero** matching
rows still shows up with a `0`, instead of vanishing from the report
entirely — the aggregation analogue of the anti-join pattern from
[Concept 01](01_joins_and_subqueries.md).

```sql
SELECT p.product_name, p.category,
       COALESCE(COUNT(s.sale_id), 0) AS times_sold,
       COALESCE(SUM(s.quantity), 0)  AS units_sold
FROM products p
LEFT JOIN sales s ON p.product_id = s.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY units_sold DESC;
```
All 9 products appear, including any never sold — `COUNT(s.sale_id)` is
already `0` for them (COUNT of all-NULL rows is 0, unlike SUM/AVG which
return NULL), but `SUM`/`AVG` on an unsold product's `quantity` would be
`NULL` without the `COALESCE` wrapping it.

---

## 7. GROUPING SETS, ROLLUP, CUBE

A report that needs subtotals **and** a grand total — "revenue by category,
by region, by category+region, AND overall" — is one query with multiple
grouping levels, not four separate queries unioned by hand. Standard SQL
gives you three shorthands for this. **SQLite does not implement any of
them** — the syntax below is Postgres/SQL Server/BigQuery/Snowflake, shown
alongside the portable workaround.

```sql
-- ROLLUP: hierarchical subtotals -- (category, region), (category), () grand total
SELECT category, region, SUM(revenue) AS revenue
FROM sales_fact
GROUP BY ROLLUP (category, region);

-- CUBE: every combination -- (category, region), (category), (region), () grand total
SELECT category, region, SUM(revenue) AS revenue
FROM sales_fact
GROUP BY CUBE (category, region);

-- GROUPING SETS: exactly the combinations you list, nothing implied
SELECT category, region, SUM(revenue) AS revenue
FROM sales_fact
GROUP BY GROUPING SETS ((category, region), (category), ());
```

```text
ROLLUP(category, region) produces, in order:
  (category, region)  <- most granular
  (category)           <- category subtotal, region = NULL
  ()                    <- grand total, both = NULL

CUBE(category, region) produces ALL FOUR:
  (category, region), (category), (region), ()
  -- CUBE = every possible subset; ROLLUP = only the hierarchical prefixes
```

The output rows for a subtotal have `NULL` in the columns that were rolled
up — e.g. the category-subtotal row has `region = NULL`. Distinguishing
"this NULL means rolled-up subtotal" from "this NULL means the actual data
was NULL" is exactly what the standard's `GROUPING(col)` function is for —
it returns `1` for a rolled-up NULL and `0` for a real one.

**SQLite workaround** — `UNION ALL` of each grouping level explicitly, with
a literal marking which level each row belongs to:
```sql
SELECT category, region, SUM(revenue) AS revenue, 'detail' AS level
FROM sales_fact GROUP BY category, region
UNION ALL
SELECT category, NULL, SUM(revenue), 'category_subtotal'
FROM sales_fact GROUP BY category
UNION ALL
SELECT NULL, NULL, SUM(revenue), 'grand_total'
FROM sales_fact;
```
This is more verbose but portable, and it's a fair follow-up in an
interview: *"what would you do if your engine didn't have `ROLLUP`?"* —
the `UNION ALL` shape, with an explicit `level` marker column instead of
relying on positional `NULL`s, is the answer.

---

## 8. The full logical order of operations

Every `WHERE`-vs-`HAVING` confusion, every "why can't I use a `SELECT`
alias in `WHERE`" question, and every window-function-in-`WHERE` error
traces back to one fact: SQL clauses do **not** execute in the order
they're written.

```text
1. FROM        -- which tables (and joins) are involved
2. WHERE       -- filter individual rows
3. GROUP BY    -- partition rows into groups
4. HAVING      -- filter groups
5. WINDOW      -- window functions evaluated here (after HAVING, before SELECT)
6. SELECT      -- choose/compute output columns (aliases are born HERE)
7. DISTINCT    -- de-duplicate SELECTed rows
8. ORDER BY    -- sort (CAN reference SELECT aliases, since SELECT already ran)
9. LIMIT/OFFSET -- cap and page the output
```

This explains three gotchas at once: you can't put a window function's
result in `WHERE` (window functions run in step 5, `WHERE` is step 2 — the
value doesn't exist yet, hence needing the subquery-then-filter pattern
from [Concept 02, section 8](02_window_functions.md)); you *can* reference
a `SELECT` alias in `ORDER BY` (step 8, after step 6) but generally *can't*
in `WHERE` (step 2, before step 6); and `HAVING` can reference aggregates
that aren't even in `SELECT`, because it runs at step 4, independent of
step 6 entirely.

---

## Key Takeaways

- `WHERE` filters rows before grouping; `HAVING` filters groups after
  aggregation — this single distinction resolves nearly every "why doesn't
  my filter work" question involving `GROUP BY`.
- Every aggregate except `COUNT(*)` ignores `NULL`s — `AVG` in particular
  divides by the non-NULL count, not the total row count; wrap with
  `COALESCE` if NULLs should count as zero.
- `CASE` inside an aggregate is the whole mechanism behind conditional
  counting and pivot-style reports — `COUNT` skips the implicit `NULL`
  `ELSE`, `SUM` needs an explicit `ELSE 0` to avoid an all-NULL-group `NULL`.
- `LEFT JOIN` + `COALESCE` is how a zero-activity group still appears in a
  report instead of silently vanishing — the aggregation-side twin of the
  anti-join pattern.
- `ROLLUP`/`CUBE`/`GROUPING SETS` compute multiple grouping levels (subtotals
  + grand total) in one query — none of the three exist in SQLite; the
  portable fallback is `UNION ALL` of each grouping level with an explicit
  marker column.
- The real clause execution order is `FROM -> WHERE -> GROUP BY -> HAVING
  -> WINDOW -> SELECT -> DISTINCT -> ORDER BY -> LIMIT`, not top-to-bottom
  as written — this is the root cause of every "can I use this alias here"
  or "why can't I filter a window function in WHERE" question.
