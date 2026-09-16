# SQL Foundations

## Why This Matters

SQL is the single most universally-tested skill in data engineering
interviews — every DE interview loop has a SQL round, whether or not it
also has a systems-design or coding round. It's also the one skill that
transfers unchanged across every tool you'll touch on the job: the same
`JOIN`/`GROUP BY`/window-function vocabulary answers a question in
Postgres, Snowflake, BigQuery, Spark SQL, or a spreadsheet-adjacent BI
tool. Master this folder and you've covered the one interview round that's
never optional.

The bar isn't "can you write a `SELECT`" — it's **can you write correct,
reasonably efficient SQL live, while talking, including catching your own
mistakes out loud**, because that's exactly the format almost every SQL
round actually takes.

---

## Folder Structure

- `concepts/` — one Markdown file per topic, following a fixed shape:
  a **Covers** list, one `##` section per sub-topic with a prose "why" →
  an ASCII diagram where one clarifies the mechanism → a real, runnable
  SQLite code block → a worked example with its actual output shown →
  ending in **Key Takeaways**. Every code block is copy-paste runnable
  against `sqlite3` (Python's standard library `sqlite3` module, or the
  `sqlite3` CLI) — nothing needs a server or a cloud account to follow
  along.
- `practice/` — `exercises.md` (12 predict-the-output drills with the
  answer hidden behind `<details>`, so you can quiz yourself honestly) and
  `coding_problems.md` (6 classic pattern-recognition/optimization
  problems with schema, expected output, and a hidden solution +
  explanation).
- `interview_questions/` — the four shapes a real SQL round actually
  takes: worked live-coding scenarios, rapid-fire conceptual Q&A,
  critique-and-debug of someone else's query, and mid-conversation
  curveballs/trade-offs. See its own
  [README](interview_questions/README.md) for the full breakdown.
- `projects/` — one capstone: build a small analytics query engine over a
  generated e-commerce dataset and answer 12 real analytics questions
  against it, then tune the two slowest ones.

---

## Topics Covered

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Joins & Subqueries | `concepts/01_joins_and_subqueries.md` | "Write all the join types from memory, and simulate a FULL OUTER JOIN on an engine that doesn't support one." |
| 2 | Window Functions | `concepts/02_window_functions.md` | "Find the top 3 highest-paid employees per department." |
| 3 | CTEs & Recursive Queries | `concepts/03_ctes_and_recursive_queries.md` | "Write a query that walks an org chart / bill of materials to arbitrary depth." |
| 4 | Aggregations & Grouping | `concepts/04_aggregations_and_grouping.md` | "What's the difference between WHERE and HAVING, and why does AVG() surprise people with NULLs?" |
| 5 | Query Optimization & Indexing | `concepts/05_query_optimization_and_indexing.md` | "This query is slow — what do you check, in what order?" |
| 6 | Reading EXPLAIN Plans | `concepts/06_reading_explain_plans.md` | "Walk me through this EXPLAIN ANALYZE output." |

---

## Key Mental Models

### 1. The Real Order of Operations

SQL clauses do **not** execute in the order you type them:

```sql
FROM      -- which tables (and joins) are involved
WHERE     -- filter individual rows
GROUP BY  -- partition rows into groups
HAVING    -- filter groups
-- window functions are evaluated here, after HAVING, before SELECT
SELECT    -- choose/compute output columns (aliases are born HERE)
DISTINCT  -- de-duplicate SELECTed rows
ORDER BY  -- sort (CAN reference SELECT aliases)
LIMIT     -- cap the output
```

This single fact resolves nearly every "why can't I filter on a window
function in WHERE" or "why can I use this alias in ORDER BY but not WHERE"
confusion — see
[Concept 04, section 8](concepts/04_aggregations_and_grouping.md#8-the-full-logical-order-of-operations)
for the full walkthrough.

### 2. Window Functions = Aggregation Without Collapsing Rows

```sql
-- GROUP BY: collapses rows -- one row per department
SELECT department, AVG(salary) FROM employees GROUP BY department;

-- Window function: keeps every row, adds a computed column
SELECT name, department, salary,
       AVG(salary) OVER (PARTITION BY department) AS dept_avg
FROM employees;
```

Same aggregate function, completely different output shape — this is the
single most-tested distinction in the whole folder.

### 3. NULL Is Not a Value, It's "Unknown" — and That Breaks Intuition Twice

```sql
NULL = NULL        -- NULL (not TRUE!) -- use IS NULL / IS NOT NULL
x NOT IN (1, NULL)  -- NULL for every row -- silently returns ZERO rows, no error
AVG(rating)         -- divides by the NON-NULL count, not the total row count
```

Three-valued logic (`TRUE`/`FALSE`/`NULL`) is the root cause of the single
most common silent SQL bug — a `NOT IN` subquery that can ever produce a
`NULL` returns an empty result forever, with no error at all. `NOT EXISTS`
is immune to it; that's why it's the recommended default for anti-joins.

### 4. SCAN vs SEARCH, and Sargability

```text
EXPLAIN QUERY PLAN SELECT * FROM orders WHERE status = 'pending';
  SCAN TABLE orders                              -- no usable index: reads everything
  SEARCH TABLE orders USING INDEX ... (status=?)  -- after CREATE INDEX: jumps to matches
```

A predicate that wraps an indexed column in a function
(`WHERE SUBSTR(date_col, 1, 4) = '2024'`) can't use an index no matter how
well it's built — rewritten as a sargable range
(`WHERE date_col >= '2024-01-01' AND date_col < '2025-01-01'`), it can.

---

## Practice Goals

- [ ] Write all the join types from memory, including simulating RIGHT JOIN
      and FULL OUTER JOIN on an engine without them
- [ ] Use window functions for ranking, running totals, moving averages,
      and top-N-per-group — and explain the `LAST_VALUE` default-frame trap
      without looking it up
- [ ] Write a recursive CTE for a hierarchy and for a gap-filling date/
      number series, and know what stops the recursion
- [ ] State the WHERE-vs-HAVING rule and the AVG-ignores-NULLs rule without
      hesitating
- [ ] Read an `EXPLAIN QUERY PLAN` (SQLite) and an `EXPLAIN ANALYZE`
      (Postgres-style) plan and name the join algorithm/scan type at each
      node
- [ ] Diagnose a slow query from its plan and propose the specific index
      or rewrite that fixes it — not just "add an index"
- [ ] Solve all 12 practice exercises and all 6 coding problems without
      looking at the hidden solutions first
- [ ] Complete the capstone project end to end, including the tuning pass

---

## Prerequisites

None. This is the entry point of the interview-prep course — if `SELECT`/
`WHERE`/`JOIN`/`GROUP BY` are already comfortable, start directly at
[`concepts/02_window_functions.md`](concepts/02_window_functions.md);
otherwise start at
[`concepts/01_joins_and_subqueries.md`](concepts/01_joins_and_subqueries.md)
and go in order. Every code block runs against SQLite — `python3` with the
standard library is enough (`sqlite3` ships with Python), no server, account,
or install required.
