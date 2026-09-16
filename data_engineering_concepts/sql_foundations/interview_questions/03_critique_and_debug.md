# 3. Critique & Debug

Part of the [Interview Questions](README.md) series.

A different SQL-round mode from [file 01](01_worked_scenarios.md): instead
of writing a query from scratch, you're handed **someone else's query**
(the schema is correct — this isn't a data-modeling problem) and told
either "the output is wrong" or "this is too slow," and asked to find why.
This tests whether you can *read* SQL critically under pressure, which is
a different skill from writing it. Every case gives you the query, the
symptom, and (where relevant) an `EXPLAIN` snippet — form your diagnosis
before expanding the debrief.

---

## Case 1: The Revenue That Tripled After Adding a Join

**Setup:** A dashboard computed `SUM(orders.total_amount)` correctly. A
teammate then joined in `order_items` so the dashboard could also show
`item_count`, and now the "total revenue" number is **3x too high** for
some orders and correct for others.

```sql
SELECT o.order_id, o.total_amount, COUNT(oi.order_item_id) AS item_count
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.total_amount;

-- then, separately, summed at the report layer:
SELECT SUM(total_amount) FROM (
    SELECT o.order_id, o.total_amount
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
) x;
```

<details>
<summary>Debrief</summary>

**Diagnosis:** joining `orders` to `order_items` produces **one row per
line item**, not one row per order — an order with 3 line items now
appears 3 times in the joined result, each time carrying the *same*
`total_amount`. The first query is actually fine (`GROUP BY o.order_id`
collapses back to one row per order before `COUNT`). The second query is
the bug: it selects `order_id, total_amount` from the **joined, ungrouped**
result — so an order with 3 line items contributes its `total_amount`
three times to the outer `SUM`.

**Fix:** either aggregate `order_items` down to one row per order *before*
joining, or apply `SUM(DISTINCT total_amount)` per order first via a
`GROUP BY`-then-sum in two steps — never sum a header-level column read
through a fan-out join without collapsing the grain first:
```sql
SELECT SUM(total_amount) FROM (
    SELECT o.order_id, o.total_amount
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY o.order_id, o.total_amount    -- collapse back to one row per order
) x;
```

**The interview tell:** naming this instantly as "a fan-out from joining a
header table to its detail table, multiplying a header-level measure by
however many detail rows exist" — rather than groping toward `DISTINCT` as
a band-aid — is what separates recognizing the *pattern* from patching one
instance of it. This is the same root cause as the "double-counted
revenue" schema critique in
[`data_modeling/interview_questions/03_critique_and_debug.md`, Case 1](../../data_modeling/interview_questions/03_critique_and_debug.md) —
there it was baked into the *schema*; here the schema is fine and the same
mistake was made fresh, in the *query*.

</details>

---

## Case 2: The Churn Report That Always Shows Zero

**Setup:** A "customers with no orders this quarter" report is supposed to
flag churned accounts. It has returned **zero rows every single run for
six months**, even though the business has visibly lost customers in that
time.

```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE c.customer_id NOT IN (
    SELECT customer_id FROM orders WHERE order_date >= '2024-01-01'
);
```

<details>
<summary>Debrief</summary>

**Diagnosis:** if `orders.customer_id` can ever be `NULL` for even one row
in the whole table (a guest checkout, an import that didn't backfill the
FK, a data quality issue upstream), the subquery's result list contains a
`NULL`. `NOT IN (list containing NULL)` evaluates to `NULL` for **every**
row of the outer query, and `WHERE` discards rows where the condition
isn't `TRUE` — so the report silently returns zero rows, forever, with no
error, until someone notices the business reality doesn't match the
dashboard.

**Fix:** filter the subquery's NULLs explicitly, or — the more robust
long-term choice — switch to `NOT EXISTS`, which is completely unaffected
by NULLs in the correlated table:
```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE NOT EXISTS (
    SELECT 1 FROM orders o
    WHERE o.customer_id = c.customer_id AND o.order_date >= '2024-01-01'
);
```

**The interview tell:** the six-months-of-silence detail is deliberate —
this bug produces **no error, no warning, just a plausible-looking empty
result**, which is exactly why it survives so long in production. Anyone
who's been burned by this once will check `NOT IN` subqueries for nullable
columns on sight, for the rest of their career. See
[Concept 01, section 9](../concepts/01_joins_and_subqueries.md#9-exists-vs-in-vs-join).

</details>

---

## Case 3: The Top-Product Report With the Wrong Number Next to the Right Name (or Vice Versa)

**Setup:** A "top-selling product per category" report, built on SQLite,
returns exactly one row per category — but the revenue numbers and product
names don't line up with a manual spot-check. Widget A shows revenue that
actually belongs to a different product in the same category.

```sql
SELECT p.category, p.product_name, SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
GROUP BY p.category
ORDER BY revenue DESC;
```

<details>
<summary>Debrief</summary>

**Diagnosis:** `GROUP BY p.category` collapses to one row per category,
but `p.product_name` is selected without being in `GROUP BY` and without
an aggregate wrapped around it. Standard SQL should reject this outright
("column must appear in GROUP BY or be used in an aggregate function"),
but **SQLite specifically allows it** and silently picks *some* row's
`product_name` for the group — not necessarily the one associated with the
`MAX`/`SUM` shown next to it. The `revenue` figure is a real, correctly
computed category total; the `product_name` next to it is close to
arbitrary.

**Fix:** decide what grain you actually want. If the intent is "top single
product per category," you need per-product aggregation first, then
ranking within category (see
[interview_questions/01_worked_scenarios.md, Scenario 1](01_worked_scenarios.md#scenario-1-top-selling-product-by-revenue-in-each-category)
for the corrected version, built the same way). If the intent really is
"total revenue per category" with no single product implied, drop
`product_name` from the `SELECT` entirely rather than let it ride along
misleadingly.

**The interview tell:** knowing that this specific query would **error on
Postgres/MySQL's `ONLY_FULL_GROUP_BY` mode but silently misbehave on
SQLite** is a strong, specific signal — it shows you understand `GROUP BY`
correctness as a *language rule*, not something you rely on your engine to
catch for you.

</details>

---

## Case 4: The Query That Takes 40 Seconds

**Setup:** A dashboard query against a 20-million-row `events` table takes
40 seconds. `EXPLAIN QUERY PLAN` shows:

```text
SCAN TABLE events
```

```sql
SELECT user_id, COUNT(*) AS event_count
FROM events
WHERE strftime('%Y-%m', event_time) = '2024-06'
GROUP BY user_id
HAVING COUNT(*) > 50;
```

There's a `CREATE INDEX idx_events_time ON events(event_time);` already in
place. It isn't being used.

<details>
<summary>Debrief</summary>

**Diagnosis:** `strftime('%Y-%m', event_time)` wraps the indexed column in
a function. The index on `events(event_time)` is sorted by the raw
`event_time` values — it has no way to jump to "all rows where
`strftime(...)` equals a specific string" without computing that function
for every single row first, which is exactly a full scan. This predicate
is **not sargable**, and no index on the raw column can rescue it.

**Fix:** rewrite as a sargable range comparison against the raw column,
which the existing index can actually use:
```sql
SELECT user_id, COUNT(*) AS event_count
FROM events
WHERE event_time >= '2024-06-01' AND event_time < '2024-07-01'
GROUP BY user_id
HAVING COUNT(*) > 50;
```
This flips the plan from `SCAN TABLE events` to
`SEARCH TABLE events USING INDEX idx_events_time (event_time>? AND event_time<?)`
— the index is now usable because the comparison operates directly on the
column's actual stored values.

**The interview tell:** many candidates correctly diagnose "needs an
index" but miss that **an index already exists** and is being defeated by
the function wrapper — reading the `EXPLAIN` output (`SCAN`, not
`SEARCH`) and connecting it back to the specific line of SQL causing it is
the actual skill being tested, not just knowing indexes exist. See
[Concept 05, section 7](../concepts/05_query_optimization_and_indexing.md#7-query-rewriting-strategies).

</details>

---

## Case 5: The Dashboard Where Every Row Shows Its Own Salary as the "Department Minimum"

**Setup:** A report is supposed to show each employee's salary next to
their department's minimum salary, for a "how far above the floor" metric.
Instead, `dept_min_salary` is identical to `salary` on every single row —
as if the department only ever contained the current employee.

```sql
SELECT name, department, salary,
       LAST_VALUE(salary) OVER (
           PARTITION BY department ORDER BY salary DESC
       ) AS dept_min_salary
FROM employees;
```

<details>
<summary>Debrief</summary>

**Diagnosis:** the window has an `ORDER BY` but no explicit frame, so it
defaults to `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.
`LAST_VALUE` under that frame is, by definition, **the current row's own
value** — the frame never extends past "the row I'm currently
computing." This is the single most common `LAST_VALUE` bug, and it
produces no error at all — just a number that happens to look plausible
(it *is* a real salary, just the wrong one) until someone checks it by
hand.

**Fix:** explicitly widen the frame to the whole partition:
```sql
SELECT name, department, salary,
       LAST_VALUE(salary) OVER (
           PARTITION BY department ORDER BY salary DESC
           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
       ) AS dept_min_salary
FROM employees;
```
Or sidestep `LAST_VALUE` entirely and use `MIN(salary) OVER (PARTITION BY
department)` — no `ORDER BY` needed at all for a whole-partition min/max,
which is simpler and avoids the frame gotcha altogether.

**The interview tell:** recommending `MIN() OVER (PARTITION BY ...)`
instead of fighting with `LAST_VALUE`'s frame is the stronger answer — it
shows you know *when a simpler tool solves the same problem*, not just how
to patch the one you were handed. See
[Concept 02, section 5](../concepts/02_window_functions.md#5-first_value-and-last_value--the-default-frame-trap).

</details>

---

## Case 6: The Pagination That Gets Slower on Every Page

**Setup:** An API paginates a 5-million-row `orders` table, 50 rows per
page. Page 1 returns in 5ms. Page 4,000 takes over 2 seconds. Nothing in
the query changed between pages except the page number.

```sql
SELECT order_id, customer_id, total_price
FROM orders
ORDER BY order_id
LIMIT 50 OFFSET 200000;   -- page 4000: (4000 - 1) * 50
```

<details>
<summary>Debrief</summary>

**Diagnosis:** `OFFSET` doesn't skip rows for free — the engine must
generate (and then discard) every one of the 200,000 preceding rows before
it can return the 50 requested. Cost grows linearly with how deep the page
is, which is exactly the observed symptom: page 1 (offset 0) is instant,
page 4,000 (offset 200,000) is not.

**Fix:** keyset (seek) pagination — carry the last `order_id` seen on the
client, and use it as a `WHERE` bound instead of an `OFFSET`:
```sql
SELECT order_id, customer_id, total_price
FROM orders
WHERE order_id > :last_seen_order_id
ORDER BY order_id
LIMIT 50;
```
With an index on `order_id` (the primary key, here, already indexed for
free), this runs at roughly constant cost regardless of how deep into the
result set the client has paged, because it `SEARCH`es directly to the
right starting point instead of scanning past everything before it.

**The interview tell:** the honest trade-off to name unprompted: keyset
pagination can't jump to an arbitrary page number directly (only "next
page after X") and needs a stable, unique ordering column — the right
trade for an infinite-scroll feed or an API cursor, the wrong one for a
UI with literal page-7-of-40 links. See
[Concept 05, section 6](../concepts/05_query_optimization_and_indexing.md#6-pagination-offsetlimit-vs-keyset).

</details>

---

## What Interviewers Are Actually Scoring

- Can you tell "the query runs but returns the wrong answer" apart from
  "the query is correct but slow" — and diagnose each with a different
  process (reasoning through row multiplication / NULL semantics vs.
  reading an `EXPLAIN` plan)?
- Do you name the *general pattern* (fan-out join, NOT IN + NULL,
  non-sargable predicate, window frame default) rather than only patching
  the one query in front of you?
- Do you propose the simplest fix, not just *a* fix — e.g. recommending
  `MIN() OVER (...)` over wrestling `LAST_VALUE`'s frame syntax?
- Do you say out loud *why* a bug like Case 2 or Case 5 can survive
  silently in production for months with no error at all?

**Next:** [04 — Curveballs & Trade-offs](04_curveballs_tradeoffs.md)
