# SQL Foundations — Coding Problems

Six classic SQL interview problems: five "easy" pattern-recognition problems
that come up constantly, plus one "medium" query-optimization problem where
you're handed something slow and asked to fix it. Every problem gives you a
runnable SQLite schema + sample data and the exact expected output — write
your query against it before expanding the hidden solution.

How to use this file: create the schema, write your query, run it, compare
row-for-row against "Expected Output" — then expand the solution to check
your approach and read the explanation, even if your output matched
(there's often more than one valid shape, and the explanation covers the
trade-offs between them).

---

## Problem 1: Find Duplicate Records

Given a table of email addresses, find every email that appears more than
once, along with how many times it appears.

```sql
CREATE TABLE contacts (id INTEGER PRIMARY KEY, email TEXT);
INSERT INTO contacts VALUES
    (1, 'alice@example.com'), (2, 'bob@example.com'), (3, 'alice@example.com'),
    (4, 'carol@example.com'), (5, 'bob@example.com'), (6, 'bob@example.com');
```

**Constraints:** return both the email and its count; only duplicates
(count > 1); order by count descending.

**Expected Output:**
```text
email               count
bob@example.com      3
alice@example.com    2
```

<details>
<summary>Solution</summary>

```sql
SELECT email, COUNT(*) AS cnt
FROM contacts
GROUP BY email
HAVING COUNT(*) > 1
ORDER BY cnt DESC;
```

`GROUP BY` collapses rows sharing the same email; `HAVING COUNT(*) > 1`
keeps only groups where more than one row landed together — the standard
"find duplicates" shape, and the reason `HAVING` exists as a clause
distinct from `WHERE` (you can't write `WHERE COUNT(*) > 1`, because
`WHERE` runs before aggregation happens — see
[Concept 04, section 8](../concepts/04_aggregations_and_grouping.md#8-the-full-logical-order-of-operations)).

</details>

---

## Problem 2: Second Highest Salary

Given an employees table, find the second-highest **distinct** salary. If
there is no second-highest (e.g. everyone earns the same), return `NULL`.

```sql
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, salary INTEGER);
INSERT INTO employees VALUES
    (1, 'Alice', 90000), (2, 'Bob', 85000), (3, 'Carol', 90000),
    (4, 'Dave', 70000), (5, 'Eve', 85000);
```

**Constraints:** ties count once (Alice and Carol both earning 90000 is one
distinct salary, not two); handle the "no second value" edge case cleanly.

**Expected Output:** `85000`

<details>
<summary>Solution</summary>

```sql
-- Approach 1: DISTINCT + LIMIT/OFFSET
SELECT DISTINCT salary FROM employees
ORDER BY salary DESC
LIMIT 1 OFFSET 1;

-- Approach 2: subquery, no DISTINCT needed
SELECT MAX(salary) FROM employees
WHERE salary < (SELECT MAX(salary) FROM employees);
```

Both return `85000`. Approach 1 de-duplicates first, then skips the top
row (`OFFSET 1`) — if there's no second distinct value, `LIMIT 1 OFFSET 1`
simply returns zero rows, i.e. `NULL` when read with `fetchone()`. Approach
2 needs no explicit `DISTINCT`: it directly asks for "the largest salary
that is strictly less than the largest salary," which automatically skips
over duplicates of the top value and returns `NULL` on its own if no salary
is below the max. Generalizing either approach to "Nth highest" is a
natural interview follow-up — Approach 1 generalizes cleanly
(`LIMIT 1 OFFSET N-1`); Approach 2 does not (it only generalizes to N=2)
and would need `DENSE_RANK()` instead for arbitrary N — see the curveball
in [`interview_questions/04_curveballs_tradeoffs.md`](../interview_questions/04_curveballs_tradeoffs.md).

</details>

---

## Problem 3: Employees Earning More Than Their Manager

Given a self-referencing employees table, find every employee who earns
more than their own manager.

```sql
CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT, salary INTEGER, manager_id INTEGER);
INSERT INTO staff VALUES
    (1, 'Alice', 95000, NULL), (2, 'Bob', 80000, 1), (3, 'Carol', 100000, 1),
    (4, 'Dave', 60000, 2), (5, 'Eve', 85000, 2), (6, 'Frank', 70000, 3);
```

**Constraints:** use a self-join; only employees who *have* a manager
(`manager_id IS NOT NULL`); include both names and both salaries in the
output for clarity.

**Expected Output:**
```text
name    employee_salary   manager   manager_salary
Carol   100000             Alice     95000
Eve     85000              Bob       80000
```

<details>
<summary>Solution</summary>

```sql
SELECT
    e.name AS employee, e.salary AS employee_salary,
    m.name AS manager,  m.salary AS manager_salary
FROM staff e
JOIN staff m ON e.manager_id = m.id
WHERE e.salary > m.salary
ORDER BY e.salary DESC;
```

`staff` is aliased twice — `e` for "the employee row," `m` for "that
employee's manager row" — with the join condition `e.manager_id = m.id`
walking exactly one level up the hierarchy. Using a plain `JOIN` (not
`LEFT JOIN`) is correct and deliberate here: an employee with `manager_id
IS NULL` (Alice, the top of the hierarchy) can't be "earning more than
their manager" in any meaningful sense, so dropping unmatched rows is the
desired behavior, not a bug to work around. See
[Concept 01, section 6](../concepts/01_joins_and_subqueries.md#6-self-join).

</details>

---

## Problem 4: Customers Who Never Placed an Order

Given `customers` and `orders`, find every customer with zero orders.

```sql
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
INSERT INTO customers VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Carol'), (4, 'Dave'), (5, 'Eve');

CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL);
INSERT INTO orders VALUES (1, 1, 150.00), (2, 1, 200.00), (3, 3, 75.00), (4, 5, 300.00);
```

**Constraints:** show at least one approach using `LEFT JOIN` + `IS NULL`
(the standard, NULL-safe pattern); order by name.

**Expected Output:**
```text
name
Bob
Dave
```

<details>
<summary>Solution</summary>

```sql
-- Approach 1: LEFT JOIN + IS NULL (preferred -- NULL-safe, reads clearly)
SELECT c.name
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE o.id IS NULL
ORDER BY c.name;

-- Approach 2: NOT EXISTS (equally NULL-safe, often the fastest plan)
SELECT c.name FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
ORDER BY c.name;

-- Approach 3: NOT IN -- WORKS here only because orders.customer_id has no NULLs.
-- If it could ever be NULL, this silently returns ZERO rows -- see Exercise 11
-- in practice/exercises.md and Concept 01, section 9.
SELECT name FROM customers
WHERE id NOT IN (SELECT customer_id FROM orders)
ORDER BY name;
```

All three return `Bob, Dave` on this data. Approaches 1 and 2 are safe
regardless of whether `orders.customer_id` could ever be `NULL`; Approach 3
is a live landmine the moment that column can contain `NULL` — worth saying
explicitly in an interview even when asked to "just use `NOT IN`," since
flagging the risk unprompted is exactly the kind of detail that
distinguishes a strong answer.

</details>

---

## Problem 5: Running Total of Sales

Given a `sales` table with dates and amounts, compute the running
(cumulative) total ordered by date.

```sql
CREATE TABLE sales (id INTEGER PRIMARY KEY, sale_date TEXT, amount INTEGER);
INSERT INTO sales VALUES
    (1, '2024-01-01', 100), (2, '2024-01-02', 200), (3, '2024-01-03', 150),
    (4, '2024-01-04', 300), (5, '2024-01-05', 250);
```

**Expected Output:**
```text
sale_date    amount   running_total
2024-01-01   100      100
2024-01-02   200      300
2024-01-03   150      450
2024-01-04   300      750
2024-01-05   250      1000
```

<details>
<summary>Solution</summary>

```sql
-- Approach 1: window function (preferred -- one pass, O(n))
SELECT sale_date, amount,
       SUM(amount) OVER (ORDER BY sale_date) AS running_total
FROM sales
ORDER BY sale_date;

-- Approach 2: correlated subquery (portable to engines without window
-- functions, but O(n^2) -- for every row, re-sum every row on or before it)
SELECT
    s1.sale_date, s1.amount,
    (SELECT SUM(s2.amount) FROM sales s2 WHERE s2.sale_date <= s1.sale_date) AS running_total
FROM sales s1
ORDER BY s1.sale_date;
```

Approach 1 relies on `SUM() OVER (ORDER BY ...)` defaulting to the frame
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` whenever `ORDER BY` is
present with no explicit frame (see
[Concept 02, section 6](../concepts/02_window_functions.md#6-running-totals-and-moving-averages))
— that default *is* a running total, for free. Approach 2 is the fallback
worth knowing for any engine (or any SQLite build) without window function
support, but be ready to say out loud that it's quadratic: every one of
the `n` output rows re-scans up to `n` rows in the subquery, versus one
linear pass for the window-function version.

</details>

---

## Problem 6 (Optimization): Fix a Slow Query

You're handed a slow query against a 50,000-row `transactions` table and
asked to make it fast — this is the "optimize this" interview format,
distinct from the five pattern-recognition problems above.

**Scenario:** for each customer, find their total 2024 spend and their most
recent transaction date overall — but only for customers who spent more
than $1,000 in 2024.

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    amount REAL,
    transaction_date TEXT   -- 'YYYY-MM-DD', ~50,000 rows, ~500 distinct customers
);
```

**The slow query you're given:**
```sql
SELECT customer_id,
       (SELECT SUM(amount) FROM transactions t2
        WHERE t2.customer_id = t1.customer_id
          AND strftime('%Y', t2.transaction_date) = '2024') AS total_spend,
       (SELECT MAX(transaction_date) FROM transactions t3
        WHERE t3.customer_id = t1.customer_id) AS last_date
FROM transactions t1
WHERE strftime('%Y', t1.transaction_date) = '2024'
GROUP BY customer_id
HAVING total_spend > 1000;
```

**What's wrong with it (name these before looking at the fix):**
1. Two separate **correlated subqueries** — for every group, the engine
   re-scans `transactions` twice more, once per subquery.
2. `strftime('%Y', transaction_date) = '2024'` wraps the filtered column in
   a function — this is not sargable (see
   [Concept 05, section 7](../concepts/05_query_optimization_and_indexing.md#7-query-rewriting-strategies))
   and defeats any index on `transaction_date` even if one existed.
3. No indexes at all on `customer_id` or `transaction_date`.
4. `last_date` is scoped across **all years**, but `total_spend` is scoped
   to 2024 only — worth double-checking this is actually the intended
   business rule (it is, per the scenario: "most recent transaction date
   *overall*") rather than an inconsistency to silently "fix."

<details>
<summary>Solution</summary>

```sql
-- Step 1: index the columns actually filtered/grouped/joined on
CREATE INDEX idx_transactions_customer_date ON transactions(customer_id, transaction_date);

-- Step 2: single pass, sargable date range, no correlated subqueries
SELECT
    customer_id,
    SUM(CASE WHEN transaction_date >= '2024-01-01' AND transaction_date < '2025-01-01'
             THEN amount ELSE 0 END) AS total_spend,
    MAX(transaction_date) AS last_date
FROM transactions
GROUP BY customer_id
HAVING total_spend > 1000;
```

What changed and why each change matters:
- **One pass over `transactions`, not three.** Both subqueries are folded
  into conditional aggregation (`SUM(CASE WHEN ...)`) in the *same*
  `GROUP BY customer_id` that already has to scan the table once anyway —
  the two extra correlated re-scans are simply gone.
- **A sargable range (`>= ... AND < ...`) instead of `strftime(...) = '2024'`.**
  A range comparison against a raw column can use a B-tree index directly;
  wrapping the column in `strftime()` cannot, on essentially any engine.
- **A composite index on `(customer_id, transaction_date)`** supports both
  the `GROUP BY customer_id` and a range scan on `transaction_date` for
  rows within a customer, and even makes this closer to an index-only
  computation depending on the engine.
- **`HAVING total_spend > 1000`** still runs after grouping — this part of
  the original query's logic was already correct and didn't need to change,
  which is worth saying explicitly rather than rewriting things that
  weren't broken.

On 50,000 rows the difference is milliseconds either way — the reason this
is still an interview staple is that the *pattern* (correlated subqueries
doing redundant re-scans, a function wrapped around an indexed column)
is exactly what turns into a multi-minute query at 50 million rows instead
of 50 thousand, and being able to name each problem instantly, not just
"try rewriting it and see," is what's being scored.

</details>
