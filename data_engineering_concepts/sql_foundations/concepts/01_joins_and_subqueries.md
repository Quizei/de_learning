# Concept 01: Joins & Subqueries

**Covers:**
- INNER JOIN, LEFT JOIN, RIGHT JOIN (simulated), FULL OUTER JOIN (simulated), CROSS JOIN, self join
- Non-correlated subqueries (in WHERE, in FROM as a derived table, in SELECT)
- Correlated subqueries
- EXISTS vs IN vs JOIN — behavior, NULL pitfalls, when to reach for which
- Scalar subqueries
- Worked example: employees, their departments, and their orders, queried every way

> All queries in this file run against **SQLite** (`sqlite3` in Python or the
> `sqlite3` CLI). SQLite has no native `RIGHT JOIN` or `FULL OUTER JOIN` —
> both are shown simulated, which is itself a common interview question
> ("how would you write a full outer join on a database that doesn't support
> it?").

---

## 0. Setup — run this once

Every query below assumes this schema and data. Paste it into a `python3` shell (or adapt to the `sqlite3` CLI) and keep the connection open.

```python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE departments (
        dept_id   INTEGER PRIMARY KEY,
        dept_name TEXT NOT NULL,
        location  TEXT
    )
""")
cur.executemany("INSERT INTO departments VALUES (?, ?, ?)", [
    (1, "Engineering", "San Francisco"),
    (2, "Marketing",   "New York"),
    (3, "Sales",       "Chicago"),
    (4, "HR",          "San Francisco"),
    (5, "Research",    "Boston"),   # no employees assigned
])

cur.execute("""
    CREATE TABLE employees (
        emp_id     INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        dept_id    INTEGER,
        manager_id INTEGER,
        salary     REAL,
        hire_date  TEXT,
        FOREIGN KEY (dept_id) REFERENCES departments(dept_id),
        FOREIGN KEY (manager_id) REFERENCES employees(emp_id)
    )
""")
cur.executemany("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)", [
    (1,  "Alice", 1,    None, 120000, "2020-01-15"),
    (2,  "Bob",   1,    1,    95000,  "2020-06-01"),
    (3,  "Carol", 2,    1,    88000,  "2021-03-10"),
    (4,  "David", 2,    3,    72000,  "2021-08-22"),
    (5,  "Eve",   3,    1,    98000,  "2019-11-05"),
    (6,  "Frank", 3,    5,    67000,  "2022-01-18"),
    (7,  "Grace", 1,    2,    105000, "2020-09-30"),
    (8,  "Hank",  None, 1,    55000,  "2023-02-14"),  # no department
    (9,  "Ivy",   4,    1,    78000,  "2021-07-07"),
    (10, "Jack",  3,    5,    71000,  "2022-05-25"),
])

cur.execute("""
    CREATE TABLE orders (
        order_id   INTEGER PRIMARY KEY,
        emp_id     INTEGER,
        customer   TEXT,
        amount     REAL,
        order_date TEXT,
        FOREIGN KEY (emp_id) REFERENCES employees(emp_id)
    )
""")
cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", [
    (101, 5,  "Acme Corp", 15000, "2023-01-10"),
    (102, 5,  "Globex",    22000, "2023-02-15"),
    (103, 6,  "Initech",   8500,  "2023-03-20"),
    (104, 10, "Acme Corp", 12000, "2023-04-05"),
    (105, 5,  "Umbrella",  30000, "2023-05-12"),
    (106, 6,  "Globex",    9500,  "2023-06-18"),
    (107, 10, "Initech",   11000, "2023-07-22"),
    (108, 3,  "Acme Corp", 5000,  "2023-08-30"),
])
conn.commit()
```

Note the deliberate landmines baked into the data: **Hank** has no department
(`dept_id IS NULL`), **Research** has no employees, and several employees
(Alice, Bob, David, Grace, Ivy) have never placed an order. Every join type
below treats those landmines differently — that difference *is* the concept.

---

## 1. INNER JOIN

An `INNER JOIN` returns only the rows where the join condition finds a match
on **both** sides. Anything unmatched — Hank (no department), Research (no
employees) — is silently dropped. That's the right choice when a mismatch is
meaningless for the question you're asking, and a bug when it isn't.

```sql
SELECT e.name, d.dept_name, e.salary
FROM employees e
INNER JOIN departments d ON e.dept_id = d.dept_id
ORDER BY e.name;
```

**Output:**
```text
name    dept_name     salary
Alice   Engineering   120000.0
Bob     Engineering   95000.0
Carol   Marketing     88000.0
David   Marketing     72000.0
Eve     Sales         98000.0
Frank   Sales         67000.0
Grace   Engineering   105000.0
Ivy     HR            78000.0
Jack    Sales         71000.0
```

Hank is gone (no department to match), and Research never shows up (no
employee to match). Chaining a third table works the same way — each `JOIN`
only keeps rows that match at that step:

```sql
SELECT e.name, d.dept_name, o.customer, o.amount
FROM employees e
INNER JOIN departments d ON e.dept_id = d.dept_id
INNER JOIN orders o ON e.emp_id = o.emp_id
ORDER BY o.amount DESC;
```

**Output:**
```text
name   dept_name  customer    amount
Eve    Sales      Umbrella    30000.0
Eve    Sales      Globex      22000.0
Eve    Sales      Acme Corp   15000.0
Jack   Sales      Initech     12000.0
Jack   Sales      Initech     11000.0
Frank  Sales      Globex      9500.0
Frank  Sales      Initech     8500.0
Carol  Marketing  Acme Corp   5000.0
```

Only 5 of the 10 employees ever placed an order, so the three-table inner
join drops the other 5 entirely — worth saying out loud in an interview,
because it's exactly the kind of silent row loss that produces a "why is my
report missing people" bug report.

---

## 2. LEFT JOIN

`LEFT JOIN` keeps **every** row from the left table, filling right-side
columns with `NULL` when there's no match. This is the workhorse for "give
me everything, plus whatever extra info exists" and for the classic
"find rows with no match" pattern.

```sql
SELECT e.name, d.dept_name
FROM employees e
LEFT JOIN departments d ON e.dept_id = d.dept_id
ORDER BY e.name;
```

**Output (excerpt):**
```text
...
Hank    None          <- Hank has no department, but he's still in the result
Ivy     HR
Jack    Sales
```

The classic anti-join pattern — find employees who've never placed an
order — is a `LEFT JOIN` plus a `WHERE ... IS NULL` filter on the right
side's key:

```sql
SELECT e.name, e.dept_id, o.order_id
FROM employees e
LEFT JOIN orders o ON e.emp_id = o.emp_id
WHERE o.order_id IS NULL
ORDER BY e.name;
```

**Output:**
```text
name    dept_id  order_id
Alice   1        None
Bob     1        None
David   2        None
Grace   1        None
Hank    None     None
Ivy     4        None
```

Filter on a column that's **guaranteed non-NULL on the right side when a
match exists** (a primary key, like `o.order_id`) — filtering on a nullable
business column instead is a common source of subtly wrong "missing rows"
queries.

---

## 3. RIGHT JOIN (simulated)

SQLite has no `RIGHT JOIN` keyword. The fix: a `RIGHT JOIN B ON ...` is
always logically identical to swapping the table order and writing a
`LEFT JOIN` instead — "all rows from the right table + matches from the
left" is exactly "all rows from the (now left) table + matches from the
(now right) table."

```sql
-- Instead of: employees RIGHT JOIN departments
-- Write:      departments LEFT JOIN employees
SELECT d.dept_name, e.name
FROM departments d
LEFT JOIN employees e ON e.dept_id = d.dept_id
ORDER BY d.dept_name, e.name;
```

**Output (excerpt):**
```text
dept_name     name
Engineering   Alice
Engineering   Bob
Engineering   Grace
HR            Ivy
Marketing     Carol
Marketing     David
Research      None    <- Research has no employees, but it's still here
Sales         Eve
Sales         Frank
Sales         Jack
```

Being able to say "swap the table order and use LEFT JOIN" instantly, without
hesitating, is itself the signal an interviewer is checking for when they ask
"does SQLite/does this engine support RIGHT JOIN?"

---

## 4. FULL OUTER JOIN (simulated)

Some engines (older MySQL, SQLite) lack `FULL OUTER JOIN` too. Simulate it as
a `UNION` of a `LEFT JOIN` and the reversed `LEFT JOIN` — `UNION` (not
`UNION ALL`) also de-duplicates the rows that matched on both sides, since
those would otherwise appear twice.

```sql
SELECT e.name, d.dept_name
FROM employees e
LEFT JOIN departments d ON e.dept_id = d.dept_id

UNION

SELECT e.name, d.dept_name
FROM departments d
LEFT JOIN employees e ON e.dept_id = d.dept_id

ORDER BY dept_name, name;
```

**Output (excerpt):**
```text
name    dept_name
Hank    None            <- employee with no department
Alice   Engineering
Bob     Engineering
Grace   Engineering
Ivy     HR
Carol   Marketing
David   Marketing
None    Research        <- department with no employees
Eve     Sales
Frank   Sales
Jack    Sales
```

```text
     employees                    departments
   +-----------+                +-------------+
   |   Hank    |\              /|  Research   |
   |           | \            / |             |
   |  Alice -- Engineering -- ..              |
   |  Bob   -- Marketing   -- ..               |
   +-----------+                +-------------+
   FULL OUTER = everything on the left, everything on the right,
                matched where possible, NULL where not.
```

---

## 5. CROSS JOIN

`CROSS JOIN` produces the Cartesian product — every row of the left table
paired with every row of the right table, `M x N` rows total, with no join
condition at all. It's rarely what you want on real fact tables (accidental
cross joins are the #1 cause of a query that "returns way too many rows"),
but it's the right tool for generating combinations: dimension scaffolding,
date x region grids, test data.

```sql
CREATE TEMP TABLE sizes (size TEXT);
CREATE TEMP TABLE colors (color TEXT);
INSERT INTO sizes VALUES ('S'), ('M'), ('L');
INSERT INTO colors VALUES ('Red'), ('Blue'), ('Green');

SELECT s.size, c.color
FROM sizes s
CROSS JOIN colors c
ORDER BY s.size, c.color;
```

**Output:** 9 rows (3 sizes x 3 colors) — `('L','Blue')`, `('L','Green')`,
`('L','Red')`, `('M','Blue')`, ... `('S','Red')`.

Writing `FROM a, b` (comma-join, no `WHERE`) is the same thing as
`CROSS JOIN` — if you ever see a comma-join in a review and there's no
filter tying the tables together, that's either an intentional cross join or
a missing join condition, and it's worth asking out loud which one it is.

---

## 6. Self Join

A self join joins a table to itself under two aliases — the standard pattern
for any "compare a row to a related row in the same table" question:
employee/manager, previous/next version of a record, parent/child hierarchy.

```sql
SELECT e.name AS employee, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.emp_id
ORDER BY m.name, e.name;
```

**Output (excerpt):**
```text
employee   manager
Alice      None      <- top of the org, no manager
Bob        Alice
Carol      Alice
Eve        Alice
Hank       Alice
Ivy        Alice
Grace      Bob
David      Carol
Frank      Eve
Jack       Eve
```

Use `LEFT JOIN` (not `INNER JOIN`) so the top of the hierarchy (Alice, no
manager) doesn't get dropped. A very common follow-up — "who earns more
than their manager" — is the same self join with a `WHERE` comparing the two
salary columns:

```sql
SELECT e.name AS employee, e.salary AS emp_salary,
       m.name AS manager,  m.salary AS mgr_salary
FROM employees e
INNER JOIN employees m ON e.manager_id = m.emp_id
WHERE e.salary > m.salary
ORDER BY (e.salary - m.salary) DESC;
```

**Output:**
```text
employee   emp_salary   manager   mgr_salary
Grace      105000.0     Bob       95000.0
```

`INNER JOIN` is correct here — an employee with no manager (Alice) can't be
"earning more than their manager" at all, so dropping unmatched rows is the
desired behavior, not a bug.

---

## 7. Non-correlated subqueries

A non-correlated subquery is self-contained — it doesn't reference anything
from the outer query, so the engine can evaluate it **once** and reuse the
result. Three places they show up:

**In `WHERE`**, as a value to compare against:
```sql
SELECT name, salary
FROM employees
WHERE salary > (SELECT AVG(salary) FROM employees)
ORDER BY salary DESC;
```
**Output:** average salary is `$84,900`; Alice ($120k), Grace ($105k), Eve
($98k), Bob ($95k), and Carol ($88k) clear it.

**In `FROM`**, as a derived table — build an intermediate result, then query
it like any other table:
```sql
SELECT dept_stats.dept_name, dept_stats.emp_count, dept_stats.avg_salary
FROM (
    SELECT d.dept_name,
           COUNT(e.emp_id)        AS emp_count,
           ROUND(AVG(e.salary), 0) AS avg_salary
    FROM departments d
    LEFT JOIN employees e ON d.dept_id = e.dept_id
    GROUP BY d.dept_id, d.dept_name
) dept_stats
WHERE dept_stats.emp_count > 0
ORDER BY dept_stats.avg_salary DESC;
```
**Output:**
```text
dept_name     emp_count   avg_salary
Engineering   3           106667.0
Sales         3           78667.0
Marketing     2           80000.0
HR            1           78000.0
```

**In `SELECT`**, as a computed column — but watch out: the moment it
references an outer-query column (`e.dept_id` below), it's technically
**correlated**, even sitting in the `SELECT` list:
```sql
SELECT e.name, e.salary,
       (SELECT ROUND(AVG(e2.salary), 0)
        FROM employees e2
        WHERE e2.dept_id = e.dept_id) AS dept_avg
FROM employees e
WHERE e.dept_id IS NOT NULL
ORDER BY e.dept_id, e.salary DESC;
```
A truly non-correlated version of "salary vs department average" would join
against the derived table from the `FROM`-subquery example above instead.

---

## 8. Correlated subqueries

A correlated subquery references a column from the outer query
(`e2.dept_id = e.dept_id` below) — conceptually, it re-runs **once per
outer row**. More expensive, but often the most readable way to express
"compare this row to an aggregate of its own group."

```sql
SELECT e.name, d.dept_name, e.salary
FROM employees e
JOIN departments d ON e.dept_id = d.dept_id
WHERE e.salary = (
    SELECT MAX(e2.salary)
    FROM employees e2
    WHERE e2.dept_id = e.dept_id   -- references the outer row
)
ORDER BY e.salary DESC;
```

**Output:**
```text
name    dept_name     salary
Alice   Engineering   120000.0
Eve     Sales         98000.0
Carol   Marketing     88000.0
Ivy     HR            78000.0
```

This "highest earner per department" result is exactly what `RANK() OVER
(PARTITION BY dept ...)` computes in one pass instead (see
[Concept 02](02_window_functions.md)) — correlated subqueries and window
functions frequently solve the same problem, and knowing both lets you
default to the window function for anything per-group (usually cheaper,
one pass over the data) while still recognizing the correlated-subquery
shape when you see it in someone else's query.

```text
Correlated subquery, conceptually:

for each outer row e:
    run: SELECT MAX(salary) FROM employees WHERE dept_id = e.dept_id
    keep e if e.salary equals that result

-- real engines optimize this (e.g. rewrite into a join/window plan),
-- but the NAIVE mental model is "runs once per outer row" -- and it's
-- literally true for some optimizers/versions, which is why a correlated
-- subquery inside a big table scan can be a real performance problem.
```

---

## 9. EXISTS vs IN vs JOIN

Three ways to answer "does a related row exist," with real behavioral
differences — not just style preference.

```sql
-- Using IN
SELECT dept_name FROM departments
WHERE dept_id IN (SELECT dept_id FROM employees WHERE dept_id IS NOT NULL)
ORDER BY dept_name;

-- Using EXISTS
SELECT d.dept_name FROM departments d
WHERE EXISTS (SELECT 1 FROM employees e WHERE e.dept_id = d.dept_id)
ORDER BY d.dept_name;
```
Both return `Engineering, HR, Marketing, Sales` — same result, different
mechanism. `IN` materializes the subquery's result list once, then checks
membership; `EXISTS` short-circuits per outer row, stopping at the first
match, and is untouched by `NULL`s in the subquery's result.

**The NULL trap** is the interview-favorite gotcha:
```sql
SELECT d.dept_name
FROM departments d
WHERE d.dept_id NOT IN (SELECT dept_id FROM employees);
-- Hank has dept_id = NULL, so this subquery returns
-- (1, 1, 2, 2, 3, 3, 3, NULL, 4, 3)
```
**Output:** **0 rows** — not "Research", which is what you'd expect.
`NOT IN` is `x <> a AND x <> b AND x <> NULL ...` under the hood, and
`x <> NULL` evaluates to `NULL` (not `TRUE` or `FALSE`), which poisons the
entire `AND` chain to `NULL` for every row — a `NULL` result is treated as
"not true," so every row is filtered out.

```sql
-- Fix: filter NULLs out of the subquery first
SELECT d.dept_name
FROM departments d
WHERE d.dept_id NOT IN (
    SELECT dept_id FROM employees WHERE dept_id IS NOT NULL
);
```
**Output:** `Research` (correct).

`NOT EXISTS` has no such trap — it never falls into this hole, which is why
many style guides recommend `NOT EXISTS` over `NOT IN` unconditionally for
anti-joins. Rule of thumb for the three:
- **`JOIN`** when you need columns from both tables in the output.
- **`EXISTS`/`NOT EXISTS`** for existence checks, especially anti-joins —
  safe with NULLs, short-circuits.
- **`IN`** is fine for small, NULL-free, known-clean lists; avoid `NOT IN`
  against any subquery that might produce a `NULL`.

---

## 10. Scalar subqueries

A scalar subquery returns exactly one row and one column — a single value —
usable anywhere an expression is legal: `SELECT`, `WHERE`, `HAVING`. If it
ever returns more than one row at runtime, the engine raises an error.

```sql
SELECT name, salary,
       ROUND(salary * 100.0 / (SELECT SUM(salary) FROM employees), 1) AS pct_of_total
FROM employees
ORDER BY salary DESC;
```
**Output (excerpt):** Alice `$120,000 (14.1%)`, Grace `$105,000 (12.4%)`,
Eve `$98,000 (11.5%)`, ...

```sql
SELECT d.dept_name,
       ROUND(AVG(e.salary), 0) AS dept_avg,
       (SELECT ROUND(AVG(salary), 0) FROM employees) AS company_avg
FROM departments d
JOIN employees e ON d.dept_id = e.dept_id
GROUP BY d.dept_id, d.dept_name
HAVING AVG(e.salary) > (SELECT AVG(salary) FROM employees)
ORDER BY dept_avg DESC;
```
**Output:**
```text
dept_name     dept_avg   company_avg
Engineering   106667.0   84900.0
```

---

## Key Takeaways

- `INNER JOIN` drops unmatched rows on *either* side; `LEFT JOIN` keeps every
  left row and NULLs out the right side on no match — picking the wrong one
  is the single most common cause of a report silently missing rows.
- SQLite (and older MySQL) have no `RIGHT JOIN`/`FULL OUTER JOIN` — simulate
  `RIGHT JOIN` by swapping table order into a `LEFT JOIN`, and `FULL OUTER
  JOIN` as a `UNION` of a `LEFT JOIN` and its reverse.
- `LEFT JOIN ... WHERE right.pk IS NULL` is the standard anti-join pattern —
  filter on a column guaranteed non-NULL on a match (a PK), never a nullable
  business column.
- `CROSS JOIN` (or a comma-join with no filter) produces `M x N` rows —
  correct for dimension scaffolding, almost always a bug on fact tables.
- A self join is one table, two aliases — the pattern for manager
  hierarchies and any "compare this row to a related row in the same table"
  question.
- Non-correlated subqueries run once and are reusable in `WHERE`, `FROM`
  (derived tables), or `SELECT`; correlated subqueries reference an outer
  column and conceptually re-run per outer row.
- `NOT IN` against a subquery that can return `NULL` silently returns zero
  rows for everything — always filter `IS NOT NULL` in that subquery, or
  use `NOT EXISTS` instead, which is immune to the trap.
- A scalar subquery must return exactly one row, one column — usable
  anywhere a single value is expected, and errors at runtime if that
  contract is violated.
