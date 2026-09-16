# SQL Foundations — Predict-the-Output Exercises

12 exercises that test whether you actually understand a concept, or just
recognize it when you read it. Each gives you a small schema, sample data,
and a query — **predict the exact output yourself, on paper, before
expanding the answer.** Getting one wrong is the useful part: it tells you
exactly which concept file to re-read (each answer cross-references one).

How to use this file: read the setup and the query, write down your
prediction (row count, specific values, whichever the exercise asks for),
then expand `<details>` to check yourself.

Topics: exercises 1–2 joins, 3–4 window functions, 5–6 CTEs, 7–8
aggregations, 9–10 subqueries, 11 the NULL/`NOT IN` trap, 12 reading a plan.

---

## Exercise 1: LEFT JOIN with NULL

```sql
CREATE TABLE departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT);
CREATE TABLE employees (emp_id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER);

INSERT INTO departments VALUES (1, 'Engineering'), (2, 'Marketing'), (3, 'Sales');
INSERT INTO employees VALUES
    (1, 'Alice', 1), (2, 'Bob', 2), (3, 'Carol', 1),
    (4, 'Zara', NULL), (5, 'Yuki', 99);  -- dept_id 99 doesn't exist!

SELECT e.name, d.dept_name
FROM employees e
LEFT JOIN departments d ON e.dept_id = d.dept_id
ORDER BY e.name;
```

Predict: how many rows come back? What is Zara's `dept_name`? What is
Yuki's?

<details>
<summary>Answer</summary>

**5 rows.** `LEFT JOIN` keeps every row from `employees` regardless of
whether a match exists.

```text
name    dept_name
Alice   Engineering
Bob     Marketing
Carol   Engineering
Yuki    None    <- dept_id 99 has no matching row in departments -> NULL
Zara    None    <- dept_id is NULL, can't match anything -> NULL
```

Zara and Yuki land on `NULL` for two *different* reasons — Zara because her
`dept_id` itself is `NULL`, Yuki because her `dept_id` is a real value that
just doesn't exist in `departments`. Both produce the same visible result,
which is exactly why "why is this NULL" needs a follow-up question in real
debugging, not an assumption. See
[Concept 01, section 2](../concepts/01_joins_and_subqueries.md#2-left-join).

</details>

---

## Exercise 2: INNER JOIN with duplicate matches

```sql
CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE projects (proj_id INTEGER, staff_id INTEGER, proj_name TEXT);

INSERT INTO staff VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Carol');
INSERT INTO projects VALUES
    (10, 1, 'Alpha'), (20, 1, 'Beta'), (30, 2, 'Alpha'), (40, 1, 'Gamma');

SELECT s.name, p.proj_name
FROM staff s
INNER JOIN projects p ON s.id = p.staff_id
ORDER BY s.name, p.proj_name;
```

Predict: total row count. How many rows for Alice? Does Carol appear at all?

<details>
<summary>Answer</summary>

**4 rows total.** Alice appears **3 times** (Alpha, Beta, Gamma — she's on
3 projects). Bob appears once. **Carol does not appear** — she has zero
matching project rows, and `INNER JOIN` drops unmatched rows entirely.

Key insight: `INNER JOIN` produces one output row per **matching pair**,
not one row per input row — a staff member on 3 projects contributes 3
rows, a staff member on 0 projects contributes 0. See
[Concept 01, section 1](../concepts/01_joins_and_subqueries.md#1-inner-join).

</details>

---

## Exercise 3: ROW_NUMBER vs RANK vs DENSE_RANK with ties

```sql
CREATE TABLE emp_salaries (name TEXT, salary INTEGER);
INSERT INTO emp_salaries VALUES
    ('Alice', 100), ('Bob', 100), ('Carol', 90), ('David', 90), ('Eve', 80);

SELECT name, salary,
       ROW_NUMBER() OVER (ORDER BY salary DESC) AS row_num,
       RANK()       OVER (ORDER BY salary DESC) AS rank_val,
       DENSE_RANK() OVER (ORDER BY salary DESC) AS dense_rank
FROM emp_salaries;
```

Predict: Carol's `ROW_NUMBER`. Carol's `RANK`. Eve's `RANK`. Eve's
`DENSE_RANK`.

<details>
<summary>Answer</summary>

```text
name    salary   row_num   rank_val   dense_rank
Alice   100      1         1          1
Bob     100      2         1          1
Carol   90       3         3          2
David   90       4         3          2
Eve     80       5         5          3
```

Carol's `ROW_NUMBER` is **3** (or 4 — ties break arbitrarily between Carol
and David, so either is defensible, but she and David split 3/4 between
them). Carol's `RANK` is **3** — two rows (Alice, Bob) occupy rank 1 before
her, so the next distinct rank is 3, not 2. Eve's `RANK` is **5** — ranks
1,1,3,3 are already used, so the next rank skips to 5. Eve's `DENSE_RANK`
is **3** — dense ranks 1,2 are used, so the next one is 3, no skipping.
See [Concept 02, section 2](../concepts/02_window_functions.md#2-ranking-row_number-rank-dense_rank).

</details>

---

## Exercise 4: LAG with no previous row

```sql
CREATE TABLE monthly (month TEXT, revenue INTEGER);
INSERT INTO monthly VALUES ('Jan', 100), ('Feb', 150), ('Mar', 120);

SELECT month, revenue,
       LAG(revenue) OVER (ORDER BY month) AS prev_revenue,
       revenue - LAG(revenue) OVER (ORDER BY month) AS change
FROM monthly;
```

Predict: Jan's `prev_revenue` and `change`. Mar's `change`.

<details>
<summary>Answer</summary>

```text
month   revenue   prev_revenue   change
Jan     100       None           None
Feb     150       100            +50
Mar     120       150            -30
```

Jan's `prev_revenue` is `NULL` (no row before the first row in the
partition) — and critically, `change` is **also `NULL`**, not `100`,
because `100 - NULL` evaluates to `NULL` in SQL, not `100`. Any arithmetic
involving a `NULL` operand produces `NULL`. Use `LAG(revenue, 1, 0)` if you
want a `0` default instead of `NULL` for the first row. See
[Concept 02, section 4](../concepts/02_window_functions.md#4-lag-and-lead).

</details>

---

## Exercise 5: CTE scope and visibility

```sql
CREATE TABLE nums (n INTEGER);
-- INSERT 1 through 10

WITH
evens AS (
    SELECT n FROM nums WHERE n % 2 = 0
),
even_stats AS (
    SELECT COUNT(*) AS cnt, SUM(n) AS total FROM evens
)
SELECT (SELECT cnt FROM even_stats)   AS even_count,
       (SELECT total FROM even_stats) AS even_sum;
```

Predict: `even_count` and `even_sum`.

<details>
<summary>Answer</summary>

`even_count = 5`, `even_sum = 30` (the even numbers 1–10 are 2, 4, 6, 8, 10;
they sum to 30).

This works because `even_stats` is defined **after** `evens` in the same
`WITH` block, so it's allowed to reference it — and the final `SELECT` can
reference *any* CTE from the block, not just the last one defined. A CTE
referencing one defined **after** it would be a compile error. See
[Concept 03, section 8](../concepts/03_ctes_and_recursive_queries.md#8-cte-scope-rule-a-common-trick-question).

</details>

---

## Exercise 6: Recursive CTE termination — off-by-one

```sql
WITH RECURSIVE countdown AS (
    SELECT 5 AS val
    UNION ALL
    SELECT val - 1 FROM countdown WHERE val > 1
)
SELECT val FROM countdown;
```

Predict: the full list of values produced. Does it include `1`?

<details>
<summary>Answer</summary>

**`[5, 4, 3, 2, 1]`** — yes, it includes 1.

Trace it: anchor produces `5`. Recursive step checks `5 > 1`? Yes -> emits
`4`. Checks `4 > 1`? Yes -> emits `3`. ... Checks `2 > 1`? Yes -> emits `1`.
Checks `1 > 1`? **No** -> stop. The row `val=1` was already emitted in the
*previous* iteration (triggered by `val=2 > 1`) before the condition that
finally fails is even evaluated on `val=1` itself.

The gotcha: the `WHERE` condition on the recursive step controls whether
**another row gets generated**, not whether the **current** row is included
— the current row was already produced by the prior iteration. To stop
*before* producing `1`, the condition would need to be `WHERE val > 2`. See
[Concept 03, section 4](../concepts/03_ctes_and_recursive_queries.md#4-recursive-ctes-anatomy).

</details>

---

## Exercise 7: GROUP BY with HAVING

```sql
CREATE TABLE orders (id INTEGER, customer TEXT, amount REAL);
INSERT INTO orders VALUES
    (1, 'Alice', 50), (2, 'Alice', 75), (3, 'Alice', 100),
    (4, 'Bob', 200),
    (5, 'Carol', 30), (6, 'Carol', 20),
    (7, 'David', 150), (8, 'David', 250), (9, 'David', 100);

SELECT customer, COUNT(*) AS order_count, SUM(amount) AS total_spent
FROM orders
GROUP BY customer
HAVING COUNT(*) >= 2
ORDER BY total_spent DESC;
```

Predict: which customers appear? Does Bob appear? David's `total_spent`?

<details>
<summary>Answer</summary>

```text
customer   order_count   total_spent
David      3             500
Alice      3             225
Carol      2             50
```

**Bob does not appear** — he has exactly 1 order, and `HAVING COUNT(*) >= 2`
filters his group out *after* it was formed. This is the tell: `HAVING`
runs after grouping, so Bob's single row was grouped and counted (`count=1`)
before being excluded — it's not that Bob was filtered out of the raw
rows, his entire group was dropped once it existed. See
[Concept 04, section 2](../concepts/04_aggregations_and_grouping.md#2-where-vs-having).

</details>

---

## Exercise 8: COUNT(*) vs COUNT(column) vs AVG with NULLs

```sql
CREATE TABLE feedback (id INTEGER, rating INTEGER, comment TEXT);
INSERT INTO feedback VALUES
    (1, 5, 'Great'), (2, 4, NULL), (3, NULL, 'OK'), (4, 3, NULL), (5, NULL, NULL);

SELECT COUNT(*)       AS count_all,
       COUNT(rating)  AS count_rating,
       COUNT(comment) AS count_comment,
       AVG(rating)    AS avg_rating
FROM feedback;
```

Predict all four values. Does `AVG(rating)` divide by 5 or by 3?

<details>
<summary>Answer</summary>

```text
count_all = 5   (every row, NULLs included)
count_rating = 3    (rows 1, 2, 4 have a non-NULL rating)
count_comment = 2   (rows 1, 3 have a non-NULL comment)
avg_rating = 4.0    (5 + 4 + 3) / 3 -- divides by the NON-NULL count, i.e. 3, not 5
```

If you expected `avg_rating = 2.4` (treating the two `NULL` ratings as `0`
and dividing by 5), that's the trap: `AVG` — like every aggregate except
`COUNT(*)` — silently skips `NULL`s entirely, both from the sum and from
the divisor. To force NULL-as-zero behavior: `AVG(COALESCE(rating, 0))`.
See [Concept 04, section 3](../concepts/04_aggregations_and_grouping.md#3-the-five-core-aggregates-and-how-null-breaks-intuition).

</details>

---

## Exercise 9: Correlated subquery — strict inequality

```sql
CREATE TABLE team (name TEXT, dept TEXT, salary INTEGER);
INSERT INTO team VALUES
    ('Alice', 'Eng', 100), ('Bob', 'Eng', 80), ('Carol', 'Eng', 90),
    ('David', 'Sales', 70), ('Eve', 'Sales', 95);

SELECT name, dept, salary
FROM team t1
WHERE salary > (SELECT AVG(salary) FROM team t2 WHERE t2.dept = t1.dept)
ORDER BY dept, salary DESC;
```

Predict: which names appear in the result? (Eng average = 90, Sales
average = 82.5.)

<details>
<summary>Answer</summary>

**Alice** (Eng, $100 > $90 average) and **Eve** (Sales, $95 > $82.5
average).

Carol earns exactly the Eng average ($90) and is **excluded** — the
condition is strict `>`, not `>=`. This is the same shape as
"employees earning more than their manager" from
[Concept 01, section 6](../concepts/01_joins_and_subqueries.md#6-self-join),
generalized from "manager's salary" to "this row's group average," computed
freshly for each outer row via the correlated subquery
(`t2.dept = t1.dept` references the outer table `t1`). See
[Concept 01, section 8](../concepts/01_joins_and_subqueries.md#8-correlated-subqueries).

</details>

---

## Exercise 10: Window function with PARTITION BY — running balance

```sql
CREATE TABLE transactions (id INTEGER, account TEXT, amount INTEGER);
INSERT INTO transactions VALUES
    (1, 'A', 100), (2, 'A', 50), (3, 'A', -30),
    (4, 'B', 200), (5, 'B', -50);

SELECT account, amount,
       SUM(amount) OVER (PARTITION BY account ORDER BY id) AS running_balance
FROM transactions
ORDER BY account, id;
```

Predict: account A's final running balance. Account B's final balance.

<details>
<summary>Answer</summary>

```text
account   amount   running_balance
A         +100     100
A         +50      150
A         -30      120
B         +200     200
B         -50      150
```

A ends at **120** (`100 + 50 - 30`), B ends at **150** (`200 - 50`).
`PARTITION BY account` resets the running total independently per account —
without it, the running total would run across *all* rows regardless of
account (`100, 150, 120, 320, 270`), which is a common accidental bug when
someone forgets the `PARTITION BY` on a running-total query. See
[Concept 02, section 6](../concepts/02_window_functions.md#6-running-totals-and-moving-averages).

</details>

---

## Exercise 11: The NOT IN + NULL trap

```sql
CREATE TABLE departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT);
CREATE TABLE employees (emp_id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER);

INSERT INTO departments VALUES (1, 'Engineering'), (2, 'Research');  -- Research has no employees
INSERT INTO employees VALUES (1, 'Alice', 1), (2, 'Hank', NULL);      -- Hank has no department

SELECT dept_name FROM departments
WHERE dept_id NOT IN (SELECT dept_id FROM employees);
```

Predict: how many rows come back. (Trick question — think about what the
subquery actually returns before answering.)

<details>
<summary>Answer</summary>

**Zero rows** — even though "Research" is intuitively the right answer.

The subquery `SELECT dept_id FROM employees` returns `(1, NULL)`. Then
`dept_id NOT IN (1, NULL)` expands to `dept_id <> 1 AND dept_id <> NULL`.
`dept_id <> NULL` evaluates to `NULL` for *every* row (comparing anything
to `NULL` with `<>` or `=` yields `NULL`, never `TRUE`/`FALSE`), which
poisons the whole `AND` to `NULL` — and a `WHERE` clause only keeps rows
where the condition is `TRUE`, so a `NULL` result is treated the same as
`FALSE`. Every row is filtered out, silently, with no error.

**Fix:** filter the subquery's `NULL`s first —
`WHERE dept_id NOT IN (SELECT dept_id FROM employees WHERE dept_id IS NOT NULL)`
— or sidestep the whole class of bug by using `NOT EXISTS` instead, which
is immune to it. See
[Concept 01, section 9](../concepts/01_joins_and_subqueries.md#9-exists-vs-in-vs-join).

</details>

---

## Exercise 12: Reading a plan — SCAN or SEARCH?

```sql
CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER, status TEXT);
-- 100,000 rows, no index on status or customer_id besides the primary key

EXPLAIN QUERY PLAN
SELECT * FROM orders WHERE customer_id = 42;
```

Predict: does this show `SCAN` or `SEARCH`? What would change it? Then:
predict the plan shape for
`SELECT * FROM orders o JOIN orders o2 ON o.customer_id = o2.customer_id WHERE o.status = 'pending'`
(a self-join with no index on either `status` or `customer_id`).

<details>
<summary>Answer</summary>

**First query: `SCAN TABLE orders`.** There's a primary key on `order_id`,
but the filter is on `customer_id`, which has no index — SQLite must read
every row to find matches. `CREATE INDEX idx_orders_customer ON
orders(customer_id)` would flip this to
`SEARCH TABLE orders USING INDEX idx_orders_customer (customer_id=?)`.

**Second query: two `SCAN`s**, one per side of the self-join — the
`status = 'pending'` filter has no index to use, and the join itself
(`customer_id = customer_id`) also has no index to use, so both the outer
scan and the inner probe for each match fall back to full scans. On a
100,000-row table joined to itself with no indexes, this is the shape of a
genuinely slow query — the fix is indexing `status` (to shrink the outer
side first) and `customer_id` (so the join itself can use `SEARCH` instead
of a nested full scan). See
[Concept 05, sections 1–2](../concepts/05_query_optimization_and_indexing.md#1-explain-query-plan-scan-vs-search).

</details>
