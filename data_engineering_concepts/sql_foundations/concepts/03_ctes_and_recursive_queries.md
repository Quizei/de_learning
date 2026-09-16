# Concept 03: CTEs & Recursive Queries

**Covers:**
- Basic CTEs (`WITH ... AS (...)`) and why they beat nested subqueries for readability
- Multiple CTEs, and CTEs referencing earlier CTEs
- CTE vs subquery, side by side, same query
- Recursive CTEs: anatomy (anchor + recursive step + termination)
- Worked example: org-chart traversal (depth, path, report counts)
- Worked example: bill-of-materials explosion (multiply quantities down a tree)
- Worked example: generating number/date series to fill gaps in a report

> All queries run against **SQLite**, which supports `WITH RECURSIVE`.
> The recursion mechanics shown here are close to standard SQL — Postgres,
> SQL Server, and MySQL 8+ all use the same `WITH RECURSIVE` shape.

---

## 0. Setup — run this once

```python
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE employees (
        emp_id     INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        title      TEXT NOT NULL,
        manager_id INTEGER,
        dept       TEXT NOT NULL,
        salary     REAL NOT NULL,
        hire_date  TEXT NOT NULL,
        FOREIGN KEY (manager_id) REFERENCES employees(emp_id)
    )
""")
cur.executemany("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?)", [
    (1,  "Sarah CEO",     "Chief Executive Officer", None, "Executive",   250000, "2015-01-01"),
    (2,  "Mike VP Eng",   "VP Engineering",          1,    "Engineering", 180000, "2016-03-15"),
    (3,  "Lisa VP Sales", "VP Sales",                1,    "Sales",       175000, "2016-06-01"),
    (4,  "Tom Director",  "Engineering Director",    2,    "Engineering", 155000, "2017-02-20"),
    (5,  "Amy Director",  "Sales Director",          3,    "Sales",       145000, "2017-08-10"),
    (6,  "John Manager",  "Engineering Manager",     4,    "Engineering", 130000, "2018-04-05"),
    (7,  "Kate Manager",  "Sales Manager",           5,    "Sales",       125000, "2018-09-22"),
    (8,  "Bob Engineer",  "Senior Engineer",         6,    "Engineering", 110000, "2019-01-14"),
    (9,  "Eve Engineer",  "Senior Engineer",         6,    "Engineering", 108000, "2019-06-30"),
    (10, "Dan Sales",     "Sales Rep",               7,    "Sales",       72000,  "2020-03-18"),
    (11, "Fay Sales",     "Sales Rep",               7,    "Sales",       68000,  "2020-11-05"),
    (12, "Gil Engineer",  "Junior Engineer",         8,    "Engineering", 78000,  "2021-07-12"),
    (13, "Hal Engineer",  "Junior Engineer",         9,    "Engineering", 75000,  "2022-01-20"),
])

cur.execute("""
    CREATE TABLE sales (
        sale_id   INTEGER PRIMARY KEY,
        rep_id    INTEGER,
        product   TEXT,
        amount    REAL,
        sale_date TEXT,
        region    TEXT,
        FOREIGN KEY (rep_id) REFERENCES employees(emp_id)
    )
""")
cur.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)", [
    (1, 10, "Widget A", 15000, "2023-01-15", "East"),
    (2, 10, "Widget B", 22000, "2023-02-20", "East"),
    (3, 11, "Widget A", 18000, "2023-01-28", "West"),
    (4, 11, "Widget C", 31000, "2023-03-10", "West"),
    (5, 10, "Widget B", 25000, "2023-04-05", "East"),
    (6, 10, "Widget A", 19000, "2023-05-12", "East"),
    (7, 11, "Widget B", 27000, "2023-06-18", "West"),
    (8, 11, "Widget A", 14000, "2023-07-22", "West"),
    (9, 10, "Widget C", 35000, "2023-08-30", "East"),
    (10, 11, "Widget B", 21000, "2023-09-15", "West"),
])

cur.execute("""
    CREATE TABLE bom (
        component_id   INTEGER PRIMARY KEY,
        component_name TEXT NOT NULL,
        parent_id      INTEGER,
        quantity       INTEGER DEFAULT 1,
        unit_cost      REAL DEFAULT 0,
        FOREIGN KEY (parent_id) REFERENCES bom(component_id)
    )
""")
cur.executemany("INSERT INTO bom VALUES (?, ?, ?, ?, ?)", [
    (1,  "Bicycle",        None, 1,  0),
    (2,  "Frame Assembly", 1,    1,  0),
    (3,  "Wheel Assembly", 1,    2,  0),      # 2 wheels per bicycle
    (4,  "Drivetrain",     1,    1,  0),
    (5,  "Main Frame",     2,    1,  45.00),
    (6,  "Seat Post",      2,    1,  12.00),
    (7,  "Handlebars",     2,    1,  18.00),
    (8,  "Rim",            3,    1,  22.00),
    (9,  "Tire",           3,    1,  15.00),
    (10, "Spokes",         3,    36, 0.50),   # 36 spokes per wheel
    (11, "Hub",            3,    1,  8.00),
    (12, "Chain",          4,    1,  14.00),
    (13, "Pedals",         4,    2,  9.00),   # 2 pedals
    (14, "Gears",          4,    1,  25.00),
    (15, "Brake Pads",     3,    2,  5.00),   # 2 pads per wheel
])
conn.commit()
```

---

## 1. Basic CTEs

A CTE is a named, temporary result set scoped to a single statement:
`WITH name AS (SELECT ...) SELECT ... FROM name`. It doesn't do anything a
subquery in `FROM` couldn't do — the entire value is readability: you name
each step of the computation instead of nesting parentheses.

```sql
WITH high_earners AS (
    SELECT name, title, salary, dept
    FROM employees
    WHERE salary > 120000
)
SELECT name, title, salary
FROM high_earners
ORDER BY salary DESC;
```
**Output (excerpt):** Sarah CEO ($250,000), Mike VP Eng ($180,000), Lisa VP
Sales ($175,000), Tom Director ($155,000), Amy Director ($145,000), John
Manager ($130,000), Kate Manager ($125,000).

CTEs compose naturally with aggregation too:
```sql
WITH dept_stats AS (
    SELECT dept, COUNT(*) AS emp_count,
           ROUND(AVG(salary), 0) AS avg_salary,
           MIN(salary) AS min_salary, MAX(salary) AS max_salary,
           SUM(salary) AS total_salary
    FROM employees
    GROUP BY dept
)
SELECT * FROM dept_stats ORDER BY total_salary DESC;
```
**Output:**
```text
dept          emp_count   avg_salary   min       max       total
Engineering   7           119429.0     75000.0   180000.0  836000.0
Sales         5           117000.0     68000.0   175000.0  585000.0
Executive     1           250000.0     250000.0  250000.0  250000.0
```

---

## 2. Multiple CTEs, and CTEs referencing earlier CTEs

Separate multiple CTEs with commas inside one `WITH` block. Each one can
reference **any CTE defined earlier** in the same block (not later ones —
see the ordering rule in section 8) — this is how you build a multi-step
transformation without nesting subqueries five levels deep.

```sql
WITH
rep_totals AS (
    SELECT rep_id, COUNT(*) AS sale_count, SUM(amount) AS total_sales,
           ROUND(AVG(amount), 0) AS avg_sale
    FROM sales
    GROUP BY rep_id
),
rep_summary AS (
    SELECT e.name, rt.sale_count, rt.total_sales, rt.avg_sale,
           RANK() OVER (ORDER BY rt.total_sales DESC) AS sales_rank
    FROM rep_totals rt
    JOIN employees e ON rt.rep_id = e.emp_id
)
SELECT * FROM rep_summary ORDER BY sales_rank;
```
**Output:**
```text
name         sale_count   total_sales   avg_sale   sales_rank
Dan Sales    5            116000.0      23200.0    1
Fay Sales    5            111000.0      22200.0    2
```

`rep_summary` references `rep_totals` — that's the "nested CTE" pattern:
each step reads only from steps already defined, which keeps the whole
pipeline linear and readable top to bottom, unlike nested subqueries which
read inside-out.

---

## 3. CTE vs subquery: same query, two ways

The exact same result, written both ways, to make the readability argument
concrete rather than abstract:

```sql
-- Subquery version
SELECT e.name, e.dept, e.salary, dept_avg.avg_salary
FROM employees e
INNER JOIN (
    SELECT dept, ROUND(AVG(salary), 0) AS avg_salary
    FROM employees
    GROUP BY dept
) dept_avg ON e.dept = dept_avg.dept
WHERE e.salary > dept_avg.avg_salary
ORDER BY e.salary DESC;

-- CTE version -- identical result, reads top to bottom
WITH dept_averages AS (
    SELECT dept, ROUND(AVG(salary), 0) AS avg_salary
    FROM employees
    GROUP BY dept
)
SELECT e.name, e.dept, e.salary, da.avg_salary
FROM employees e
JOIN dept_averages da ON e.dept = da.dept
WHERE e.salary > da.avg_salary
ORDER BY e.salary DESC;
```

Both produce the same rows. The CTE version separates "compute the
averages" from "filter employees against them" into two named, readable
steps — that separation is exactly what an interviewer is listening for
when they ask you to "clean up" a deeply nested query.

---

## 4. Recursive CTEs: anatomy

A recursive CTE has exactly two parts, joined by `UNION ALL`:

```sql
WITH RECURSIVE cte_name AS (
    SELECT ...              -- 1. ANCHOR (base case): the starting row(s)
    UNION ALL
    SELECT ...               -- 2. RECURSIVE STEP: references cte_name itself
    FROM base_table
    JOIN cte_name ON ...      --    joins the table to the CTE's own output
    WHERE <termination cond>  --    stops the recursion
)
SELECT ... FROM cte_name;
```

```text
Iteration 0 (anchor):    produces the base row(s)
Iteration 1:             recursive step runs against iteration 0's output
Iteration 2:             recursive step runs against iteration 1's output
...
Iteration N:             recursive step produces ZERO new rows -> STOP
Final result = UNION ALL of every iteration's output
```

The termination condition lives in the recursive step's `WHERE`/`JOIN`
condition — get it wrong and you get an infinite loop (most engines cap
recursion depth and error out; SQLite's default limit is very high, so a
mistake here can hang a session).

---

## 5. Worked example: org-chart traversal

The canonical recursive-CTE use case: walk a self-referencing hierarchy,
tracking depth and a human-readable path.

```sql
WITH RECURSIVE org_chart AS (
    -- Anchor: the CEO (no manager)
    SELECT emp_id, name, title, manager_id, 0 AS level, name AS path
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    -- Recursive step: employees reporting to the CURRENT level
    SELECT e.emp_id, e.name, e.title, e.manager_id,
           oc.level + 1, oc.path || ' > ' || e.name
    FROM employees e
    INNER JOIN org_chart oc ON e.manager_id = oc.emp_id
)
SELECT level, name, title, path
FROM org_chart
ORDER BY path;
```

**Output (indented by level):**
```text
Sarah CEO (Chief Executive Officer)
  Lisa VP Sales (VP Sales)
    Amy Director (Sales Director)
      Kate Manager (Sales Manager)
        Dan Sales (Sales Rep)
        Fay Sales (Sales Rep)
  Mike VP Eng (VP Engineering)
    Tom Director (Engineering Director)
      John Manager (Engineering Manager)
        Bob Engineer (Senior Engineer)
          Gil Engineer (Junior Engineer)
        Eve Engineer (Senior Engineer)
          Hal Engineer (Junior Engineer)
```

The same shape answers "all reports (direct + indirect) under Tom
Director" — anchor on Tom instead of the root, and the recursive step is
identical:

```sql
WITH RECURSIVE reports AS (
    SELECT emp_id, name, title, 0 AS depth
    FROM employees WHERE name = 'Tom Director'

    UNION ALL

    SELECT e.emp_id, e.name, e.title, r.depth + 1
    FROM employees e
    JOIN reports r ON e.manager_id = r.emp_id
)
SELECT depth, name, title FROM reports WHERE depth > 0 ORDER BY depth, name;
```
**Output:** John Manager (1 level down) -> Bob Engineer, Eve Engineer (2
levels down) -> Gil Engineer, Hal Engineer (3 levels down).

---

## 6. Worked example: bill-of-materials explosion

The other classic recursive shape: a parts hierarchy where quantities
**multiply down the tree** (2 wheels x 36 spokes = 72 spokes for the whole
bicycle, not 36).

```sql
WITH RECURSIVE bom_tree AS (
    SELECT component_id, component_name, parent_id, quantity, unit_cost,
           0 AS level, component_name AS path,
           1 AS total_qty                       -- root quantity is 1
    FROM bom
    WHERE parent_id IS NULL

    UNION ALL

    SELECT b.component_id, b.component_name, b.parent_id, b.quantity, b.unit_cost,
           bt.level + 1, bt.path || ' > ' || b.component_name,
           bt.total_qty * b.quantity             -- MULTIPLY quantities down the tree
    FROM bom b
    JOIN bom_tree bt ON b.parent_id = bt.component_id
)
SELECT level, component_name, total_qty, unit_cost,
       ROUND(total_qty * unit_cost, 2) AS line_cost
FROM bom_tree
ORDER BY path;
```

The running product `bt.total_qty * b.quantity` (not a running sum) is
what makes this a BOM explosion rather than a flat tree walk — every level
multiplies by its own local quantity, so a part nested three levels under
"2 wheels per bike" and "36 spokes per wheel" correctly reports 72 total
spokes needed.

```sql
-- Total build cost, one query
WITH RECURSIVE bom_tree AS (
    SELECT component_id, component_name, parent_id, quantity, unit_cost,
           1 AS total_qty
    FROM bom WHERE parent_id IS NULL
    UNION ALL
    SELECT b.component_id, b.component_name, b.parent_id, b.quantity, b.unit_cost,
           bt.total_qty * b.quantity
    FROM bom b JOIN bom_tree bt ON b.parent_id = bt.component_id
)
SELECT ROUND(SUM(total_qty * unit_cost), 2) AS total_cost,
       COUNT(*) AS total_components
FROM bom_tree
WHERE unit_cost > 0;   -- only leaf/cost-bearing nodes
```

---

## 7. Worked example: generating a series to fill report gaps

Recursive CTEs also generate synthetic sequences — numbers, dates — which
is exactly what you need to make a report show a zero instead of a missing
row for a month/day with no activity.

```sql
-- Numbers 1..10
WITH RECURSIVE numbers AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM numbers WHERE n < 10
)
SELECT n FROM numbers;
-- Output: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
```

```sql
-- Gap-fill: every month of 2023, even ones with zero sales
WITH RECURSIVE months(month) AS (
    SELECT '2023-01'
    UNION ALL
    SELECT CASE WHEN CAST(SUBSTR(month, 6, 2) AS INTEGER) < 12
                THEN SUBSTR(month, 1, 5) ||
                     PRINTF('%02d', CAST(SUBSTR(month, 6, 2) AS INTEGER) + 1)
           END
    FROM months
    WHERE CAST(SUBSTR(month, 6, 2) AS INTEGER) < 12
),
monthly_sales AS (
    SELECT SUBSTR(sale_date, 1, 7) AS month,
           SUM(amount) AS total_sales, COUNT(*) AS num_sales
    FROM sales
    GROUP BY SUBSTR(sale_date, 1, 7)
)
SELECT m.month,
       COALESCE(ms.total_sales, 0) AS total_sales,
       COALESCE(ms.num_sales, 0)   AS num_sales
FROM months m
LEFT JOIN monthly_sales ms ON m.month = ms.month
ORDER BY m.month;
```

**Output (excerpt):**
```text
month     total_sales   num_sales
2023-09   21000         1
2023-10   0             0   <- gap filled: no sales that month
2023-11   0             0   <- gap filled
2023-12   0             0   <- gap filled
```

Without the generated `months` CTE and the `LEFT JOIN`, October/November/
December would simply be **absent** from the result — not zero, just
missing — which silently breaks any downstream chart expecting one row per
month. Postgres/BigQuery users would more often reach for
`generate_series()`, but the `WITH RECURSIVE` version works everywhere and
is worth knowing cold for engines without a series-generating builtin.

---

## 8. CTE scope rule (a common trick question)

A CTE can reference any CTE defined **before** it in the same `WITH` block,
and the final query can reference **all** of them — but a CTE cannot
reference one defined *after* it (no forward references), and by default a
CTE isn't visible outside the statement it's attached to (it isn't a view
or a temp table).

```sql
WITH
evens AS (
    SELECT n FROM nums WHERE n % 2 = 0
),
even_stats AS (
    SELECT COUNT(*) AS cnt, SUM(n) AS total FROM evens   -- OK: evens defined above
)
SELECT (SELECT cnt FROM even_stats) AS even_count,
       (SELECT total FROM even_stats) AS even_sum;
```

---

## Key Takeaways

- A CTE (`WITH name AS (...)`) is a named, single-statement-scoped result
  set — functionally identical to a `FROM`-subquery, but readable top to
  bottom instead of nested inside-out.
- Multiple CTEs in one `WITH` block can each reference any CTE defined
  **before** them (not after) — this is how multi-step pipelines stay linear.
- A recursive CTE is exactly `anchor UNION ALL recursive-step`; the
  recursive step's `JOIN`/`WHERE` condition is both what advances the
  traversal and what terminates it — get the termination condition wrong
  and it runs away.
- Org-chart traversal accumulates depth/path with a running concatenation;
  BOM explosion accumulates a running **product** (quantities multiply down
  the tree) — recognize which pattern a hierarchy problem needs before
  writing the recursive step.
- Recursive CTEs also generate synthetic number/date series — the standard
  fix for a report that's silently missing rows for periods with zero
  activity (gap-fill with `LEFT JOIN` against the generated series).
- Recursion terminates when the recursive step produces zero new rows for
  an iteration — the `WHERE` clause on the recursive step controls this
  directly, and a row can already be "produced" one iteration before the
  condition that stops the *next* one is even evaluated.
