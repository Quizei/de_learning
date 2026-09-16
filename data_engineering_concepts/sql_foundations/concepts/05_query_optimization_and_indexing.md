# Concept 05: Query Optimization & Indexing

**Covers:**
- `EXPLAIN QUERY PLAN` basics: SCAN vs SEARCH
- Index creation, composite indexes, and why leftmost-column order matters
- Covering indexes
- `EXISTS` vs `IN` vs `JOIN` performance, and how an index changes the answer
- Avoiding `SELECT *` (projection optimization)
- Pagination: `OFFSET/LIMIT` vs keyset pagination
- Query rewriting strategies (OR -> UNION, avoiding functions on indexed columns, EXISTS over COUNT)
- Common anti-patterns: N+1 queries, DISTINCT as a band-aid, implicit type conversion, deep nesting

> Queries run against **SQLite**. The concepts (index usage, covering
> indexes, pagination strategy) transfer directly to Postgres/MySQL — see
> [Concept 06](06_reading_explain_plans.md) for how the *plan output itself*
> differs on those engines.

---

## 0. Setup — run this once

```python
import sqlite3, time
conn = sqlite3.connect(":memory:")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE orders (
        order_id    INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        product_id  INTEGER NOT NULL,
        quantity    INTEGER NOT NULL,
        total_price REAL NOT NULL,
        status      TEXT NOT NULL,
        order_date  TEXT NOT NULL,
        region      TEXT NOT NULL
    )
""")
# 10,000 rows, generated with a recursive CTE so the file stays self-contained
cur.execute("""
    WITH RECURSIVE gen AS (
        SELECT 1 AS n UNION ALL SELECT n + 1 FROM gen WHERE n < 10000
    )
    INSERT INTO orders (order_id, customer_id, product_id, quantity, total_price, status, order_date, region)
    SELECT n,
           (ABS(RANDOM()) % 500) + 1,
           (ABS(RANDOM()) % 100) + 1,
           (ABS(RANDOM()) % 10) + 1,
           ROUND((ABS(RANDOM()) % 10000) / 100.0 + 10, 2),
           CASE ABS(RANDOM()) % 5
               WHEN 0 THEN 'pending' WHEN 1 THEN 'shipped' WHEN 2 THEN 'delivered'
               WHEN 3 THEN 'cancelled' ELSE 'returned' END,
           DATE('2022-01-01', '+' || (ABS(RANDOM()) % 730) || ' days'),
           CASE ABS(RANDOM()) % 4
               WHEN 0 THEN 'North' WHEN 1 THEN 'South' WHEN 2 THEN 'East' ELSE 'West' END
    FROM gen
""")

cur.execute("""
    CREATE TABLE customers (
        customer_id   INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        tier          TEXT NOT NULL,
        created_date  TEXT NOT NULL
    )
""")
cur.execute("""
    WITH RECURSIVE gen AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM gen WHERE n < 500)
    INSERT INTO customers
    SELECT n, 'Customer_' || n,
           CASE ABS(RANDOM()) % 3 WHEN 0 THEN 'Gold' WHEN 1 THEN 'Silver' ELSE 'Bronze' END,
           DATE('2020-01-01', '+' || (ABS(RANDOM()) % 1095) || ' days')
    FROM gen
""")
conn.commit()

def plan(query):
    return "\n".join(f"  {'  '*row[1]}{row[-1]}" for row in cur.execute(f"EXPLAIN QUERY PLAN {query}").fetchall())

def timeit(query, iters=10):
    start = time.perf_counter()
    for _ in range(iters):
        cur.execute(query).fetchall()
    return (time.perf_counter() - start) * 1000 / iters
```

---

## 1. EXPLAIN QUERY PLAN: SCAN vs SEARCH

Prefix any `SELECT` with `EXPLAIN QUERY PLAN` and SQLite tells you *how* it
intends to execute it — the two words to look for are the whole story at
this level:

- **`SCAN TABLE`** — reads every row, a full table scan. Fine for a small
  table or a query that legitimately needs most rows; a red flag on a large
  table with a selective filter.
- **`SEARCH TABLE ... USING INDEX`** — uses an index (or the primary key)
  to jump straight to matching rows, without reading the whole table.

```sql
EXPLAIN QUERY PLAN SELECT * FROM orders WHERE status = 'pending';
```
**Output:** `SCAN TABLE orders` — full scan of all 10,000 rows; there's no
index on `status` yet.

```sql
EXPLAIN QUERY PLAN SELECT * FROM orders WHERE order_id = 5000;
```
**Output:** `SEARCH TABLE orders USING INTEGER PRIMARY KEY (rowid=?)` — fast,
because the primary key is automatically indexed.

```sql
EXPLAIN QUERY PLAN
SELECT o.order_id, c.customer_name
FROM orders o JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status = 'pending';
```
**Output:** `SCAN TABLE orders ...` then `SEARCH TABLE customers USING
INTEGER PRIMARY KEY (rowid=?)` — `orders` is scanned fully (no index on
`status`), but each matching row's join into `customers` uses `customers`'
primary key.

---

## 2. Index creation, and why column order matters

```sql
CREATE INDEX idx_orders_status ON orders(status);
```
After this, the exact same `status = 'pending'` query flips from `SCAN` to
`SEARCH TABLE orders USING INDEX idx_orders_status (status=?)` — measurably
faster on 10,000 rows, and the gap only widens as table size grows.

A **composite index** `(status, region)` speeds up queries filtering on
`status` alone, or on `status AND region` together — but **not** a query
filtering on `region` alone:

```sql
CREATE INDEX idx_orders_status_region ON orders(status, region);

EXPLAIN QUERY PLAN SELECT * FROM orders WHERE status = 'pending' AND region = 'North';
-- SEARCH TABLE orders USING INDEX idx_orders_status_region (status=? AND region=?)

EXPLAIN QUERY PLAN SELECT * FROM orders WHERE region = 'North';
-- Still SCAN TABLE orders -- the composite index is USELESS here!
```

```text
Index on (status, region) is like a phone book sorted by (last_name,
first_name): great for "find Smith" or "find Smith, John," useless for
"find everyone named John" -- you'd have to scan the whole book.

Rule: a composite index only helps a query that filters on its LEFTMOST
column(s), in order. Filtering on a non-leading column alone needs its
own index.
```

The fix, if `region`-only queries are common too: add a separate
`CREATE INDEX idx_orders_region ON orders(region)`. This leftmost-prefix
rule is one of the most reliably-asked index questions in an interview —
have the phone-book analogy ready.

---

## 3. Covering indexes

A **covering index** contains every column a query needs — the engine
answers the query entirely from the index's own B-tree, never touching the
underlying table rows at all. Look for `COVERING INDEX` in the plan output.

```sql
CREATE INDEX idx_orders_covering ON orders(status, total_price);

EXPLAIN QUERY PLAN
SELECT status, SUM(total_price) AS total
FROM orders
WHERE status IN ('pending', 'shipped')
GROUP BY status;
-- SEARCH TABLE orders USING COVERING INDEX idx_orders_covering (status=?)
```

This is also *why* "avoid `SELECT *`" (section 5) is more than a style
preference: `SELECT *` needs every column, so it can never be satisfied by
a covering index no matter how well-designed the index is — it always
forces a trip back to the table's actual rows.

---

## 4. EXISTS vs IN vs JOIN performance

Three ways to filter by a related table's condition — behaviorally similar
in result, but their performance profile depends heavily on whether the
right index exists.

```sql
-- IN: materializes the subquery's result set, then checks membership
SELECT COUNT(*) FROM orders
WHERE customer_id IN (SELECT customer_id FROM customers WHERE tier = 'Gold');

-- EXISTS: short-circuits per outer row on first match
SELECT COUNT(*) FROM orders o
WHERE EXISTS (SELECT 1 FROM customers c WHERE c.customer_id = o.customer_id AND c.tier = 'Gold');

-- JOIN: joins first, filters after
SELECT COUNT(*) FROM orders o
INNER JOIN customers c ON o.customer_id = c.customer_id
WHERE c.tier = 'Gold';
```

All three return the same count. Before any custom index besides the
primary keys, timings are close and dominated by scanning `orders`. Add
`CREATE INDEX idx_orders_customer ON orders(customer_id)` and all three
speed up together, because the bottleneck (locating matching
`orders.customer_id` rows) is now index-assisted regardless of which SQL
shape you used — the takeaway isn't "always use X," it's **the index
matters more than the syntax choice**, and you should check the plan
rather than guess.

---

## 5. Avoiding SELECT *

```sql
SELECT * FROM orders WHERE status = 'pending' LIMIT 1000;                  -- transfers ALL columns
SELECT order_id, total_price FROM orders WHERE status = 'pending' LIMIT 1000;  -- transfers 2
```

Costs of `SELECT *`, beyond raw bandwidth: it defeats covering-index
optimization (section 3), it silently changes behavior if the table gains
columns later, and it obscures what a query actually depends on for anyone
reading it later. Rule: **name the columns you need**, especially inside a
subquery/CTE that's about to be joined or filtered further — the earlier a
narrow projection happens, the less data every downstream step has to move.

---

## 6. Pagination: OFFSET/LIMIT vs keyset

```sql
-- OFFSET/LIMIT: SQLite must generate and discard `offset` rows before
-- it can return the next page -- cost grows with how deep you page.
SELECT order_id, customer_id, total_price
FROM orders ORDER BY order_id LIMIT 10 OFFSET 9000;

-- Keyset (a.k.a. seek) pagination: jump straight to rows after the last
-- ID you saw, using an index -- cost is roughly constant at any depth.
SELECT order_id, customer_id, total_price
FROM orders WHERE order_id > 9000 ORDER BY order_id LIMIT 10;
```

```text
OFFSET/LIMIT timing pattern (10,000-row table, page_size=10):
  offset     0:  fast
  offset   100:  fast
  offset  1000:  slower
  offset  5000:  slower still
  offset  9000:  slowest -- had to walk past 9000 rows first

Keyset pagination timing pattern:
  after id     0:  fast
  after id   100:  fast
  after id  1000:  fast
  after id  5000:  fast
  after id  9000:  fast -- SAME cost, because it SEARCHes via index, not SCANs
```

Trade-off: keyset pagination requires a unique, ordered column (or tuple)
to seek on, and it doesn't support jumping to an arbitrary page number
directly (only "next page after X") — the right trade for infinite-scroll
UIs and API pagination, the wrong one for a UI that needs a literal page-7
link.

---

## 7. Query rewriting strategies

**OR across two different columns can defeat a single index** — an index
can typically only be used efficiently for one branch of an `OR` at a time.
Rewriting as `UNION` lets each half use its own index:
```sql
-- May not use indexes on both columns efficiently
SELECT order_id, customer_id, total_price FROM orders
WHERE status = 'pending' OR order_date > '2023-06-01';

-- Each half can use its own index, then de-duplicated by UNION
SELECT order_id, customer_id, total_price FROM orders WHERE status = 'pending'
UNION
SELECT order_id, customer_id, total_price FROM orders WHERE order_date > '2023-06-01';
```

**Never wrap an indexed column in a function** — it forces the engine to
compute the function for every row, which defeats the index entirely:
```sql
-- BAD: SUBSTR(created_date, ...) must run on every row -- no index use
SELECT COUNT(*) FROM customers WHERE SUBSTR(created_date, 1, 4) = '2022';

-- GOOD: a sargable range condition can use an index on created_date
SELECT COUNT(*) FROM customers
WHERE created_date >= '2022-01-01' AND created_date < '2023-01-01';
```
("Sargable" — **S**earch **ARG**ument **ABLE** — is the term for a
predicate an index can actually be used to evaluate; it's worth knowing the
word, since interviewers use it directly.)

**Existence checks: `EXISTS` beats `COUNT(*) > 0`** — `COUNT(*)` must scan
every matching row to produce an exact count before the comparison can even
happen; `EXISTS` stops at the very first match:
```sql
SELECT CASE WHEN (SELECT COUNT(*) FROM orders WHERE customer_id = 1) > 0 THEN 1 ELSE 0 END; -- scans all matches
SELECT CASE WHEN EXISTS (SELECT 1 FROM orders WHERE customer_id = 1) THEN 1 ELSE 0 END;       -- stops at first
```

---

## 8. Common anti-patterns and fixes

**N+1 queries** — one query to get a list, then one more query *per row* of
that list, instead of a single join:
```text
BAD  (pseudocode):
    customers = query("SELECT * FROM customers WHERE tier = 'Gold'")
    for customer in customers:
        orders = query("SELECT * FROM orders WHERE customer_id = ?", customer.id)

GOOD (one query):
    query("""
        SELECT c.customer_id, COUNT(o.order_id)
        FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id
        WHERE c.tier = 'Gold'
        GROUP BY c.customer_id
    """)
```
50 Gold customers means 51 round trips in the N+1 version vs. 1 in the
join version — the gap only grows with row count, and N+1 is one of the
most common real-world causes of an application that's "mysteriously slow"
despite every individual query looking fine in isolation.

**`DISTINCT` as a band-aid for a bad join** — `DISTINCT` hides duplicate
rows produced by an incorrect or incomplete join condition instead of
fixing it:
```text
BAD:  SELECT DISTINCT o.order_id, c.customer_name FROM orders o, customers c WHERE ...
GOOD: fix the join condition so it doesn't produce duplicates in the first place
```
If you find yourself reaching for `DISTINCT` to make a join-heavy query
"look right," that's a signal to go re-examine the join, not to paper over
it.

**Implicit type conversion** — comparing a column to a literal of the
wrong type (`customer_id = '100'` against an `INTEGER` column) can silently
prevent index usage on some engines, depending on version and column type
affinity. Match parameter types to column types.

**Deep nested subqueries vs CTEs** — functionally often equivalent in
performance, but CTEs are far more maintainable:
```sql
-- Works, but reads inside-out
SELECT * FROM (
    SELECT customer_id, total_orders FROM (
        SELECT customer_id, COUNT(*) AS total_orders FROM orders GROUP BY customer_id
    ) sub WHERE total_orders > 20
) sub2 ORDER BY total_orders DESC LIMIT 5;

-- Same result, reads top to bottom
WITH order_counts AS (
    SELECT customer_id, COUNT(*) AS total_orders FROM orders GROUP BY customer_id
)
SELECT customer_id, total_orders FROM order_counts
WHERE total_orders > 20 ORDER BY total_orders DESC LIMIT 5;
```

```text
OPTIMIZATION CHECKLIST
1. Check EXPLAIN QUERY PLAN for SCAN (suspect) vs SEARCH (good)
2. Index columns used in WHERE, JOIN, and ORDER BY
3. Use covering indexes when a query only needs a few columns
4. Never wrap an indexed column in a function (kills sargability)
5. Prefer EXISTS over COUNT(*) > 0 for existence checks
6. Use keyset pagination for deep pages
7. Select only the columns you need -- never SELECT *
8. Replace N+1 query patterns with a single JOIN
9. Match parameter types to column types
10. Prefer CTEs over deep nesting for readability (usually same performance)
```

---

## Key Takeaways

- `EXPLAIN QUERY PLAN` is the first move on any "why is this slow"
  question — `SCAN` (reads everything) vs `SEARCH ... USING INDEX` (jumps
  to matches) is the headline signal.
- A composite index only accelerates queries that filter on its **leftmost
  column(s), in order** — a query filtering only on a trailing column gets
  no benefit and needs its own index.
- A covering index answers a query entirely from the index itself, never
  touching table rows — `SELECT *` can never use one, since it always needs
  every column.
- `EXISTS`/`IN`/`JOIN` converge in performance once the right index exists
  on the join column — the index matters more than which of the three you
  write.
- Never wrap an indexed column in a function in a predicate ("sargability")
  — it forces per-row evaluation and defeats the index.
- Keyset (seek) pagination stays constant-time at any depth; `OFFSET/LIMIT`
  gets slower the deeper you page, because the engine must walk past every
  skipped row first.
- N+1 queries and `DISTINCT`-as-a-band-aid are both signals of a missing or
  broken join, not features to leave in place — fix the join, don't paper
  over its symptom.
