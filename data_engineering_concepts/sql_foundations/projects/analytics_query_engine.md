# Capstone Project: Analytics Query Engine

## Why this project

Every concept file in this folder teaches one technique in isolation. A
real interview — and real work — asks you to reach for the *right*
combination of them against one dataset, under time pressure, and to
justify why you indexed what you indexed. This capstone is a single
SQLite database and a fixed list of 12 analytics questions you must answer
with SQL, plus one performance-tuning pass at the end. It forces joins,
window functions, CTEs, conditional aggregation, and `EXPLAIN`-driven
indexing to all show up in one connected piece of work, the way they
actually do on the job.

Treat this as what a take-home SQL exercise or a 60–90 minute live-coding
final round looks like. Budget roughly 2–3 hours end to end if you're
doing every query and the tuning pass properly.

---

## What you're building

A **read-only analytics layer** over a small e-commerce dataset: customers,
products, orders, order line items, and a page-view event log. You will
not build an application — you're writing the SQL a real analytics/BI
layer would run, and proving each query is both *correct* and
*reasonably efficient* against a dataset large enough that a bad query
plan is actually slow (tens of thousands of rows, not five).

---

## Step 1 — Build the schema and generate data

```python
import sqlite3, random
from datetime import date, timedelta

random.seed(42)
conn = sqlite3.connect("analytics_engine.db")   # file-based, not :memory:, so it
cur = conn.cursor()                              # persists between runs while you work

cur.executescript("""
DROP TABLE IF EXISTS page_views;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    signup_date  TEXT NOT NULL,
    country      TEXT NOT NULL,
    referral_source TEXT
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    unit_price   REAL NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL,
    order_date   TEXT NOT NULL,
    status       TEXT NOT NULL   -- 'completed' | 'cancelled' | 'refunded'
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL   -- price AT TIME OF SALE, may differ from products.unit_price
);

CREATE TABLE page_views (
    view_id      INTEGER PRIMARY KEY,
    customer_id  INTEGER,          -- NULL for anonymous/logged-out views
    product_id   INTEGER,
    view_time    TEXT NOT NULL
);
""")

countries = ["US", "US", "US", "UK", "UK", "DE", "IN", "CA"]
sources   = ["organic", "paid_search", "referral", "email", None]
categories = {
    "Electronics": [("Laptop", 1200), ("Mouse", 25), ("Monitor", 300), ("Keyboard", 60)],
    "Home":        [("Desk Chair", 220), ("Lamp", 40), ("Rug", 150)],
    "Books":       [("SQL Guide", 35), ("Data Novel", 18)],
}

start = date(2023, 1, 1)

# customers
for i in range(1, 2001):
    signup = start + timedelta(days=random.randint(0, 700))
    cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        (i, f"Customer_{i}", signup.isoformat(), random.choice(countries), random.choice(sources)))

# products
pid = 1
product_ids_by_category = {}
for cat, items in categories.items():
    product_ids_by_category[cat] = []
    for name, price in items:
        cur.execute("INSERT INTO products VALUES (?, ?, ?, ?)", (pid, name, cat, price))
        product_ids_by_category[cat].append(pid)
        pid += 1
all_product_ids = [p for ids in product_ids_by_category.values() for p in ids]

# orders + order_items (deliberately skewed: a handful of customers order A LOT)
order_id, item_id = 1, 1
power_users = set(random.sample(range(1, 2001), 20))
for cust_id in range(1, 2001):
    n_orders = random.randint(8, 40) if cust_id in power_users else random.randint(0, 6)
    for _ in range(n_orders):
        odate = start + timedelta(days=random.randint(0, 730))
        status = random.choices(["completed", "cancelled", "refunded"], weights=[85, 10, 5])[0]
        cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?)",
            (order_id, cust_id, odate.isoformat(), status))
        for _ in range(random.randint(1, 4)):
            prod = random.choice(all_product_ids)
            price = [p for p in cur.execute("SELECT unit_price FROM products WHERE product_id=?", (prod,))][0][0]
            cur.execute("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
                (item_id, order_id, prod, random.randint(1, 3), price))
            item_id += 1
        order_id += 1

# page_views (10x the order volume, mostly anonymous)
for _ in range(60000):
    vtime = start + timedelta(days=random.randint(0, 730), hours=random.randint(0, 23))
    cust = random.choice([None] * 3 + list(range(1, 2001)))
    cur.execute("INSERT INTO page_views VALUES (?, ?, ?, ?)",
        (_ + 1, cust, random.choice(all_product_ids), vtime.isoformat()))

conn.commit()
print("Rows:", {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ["customers", "products", "orders", "order_items", "page_views"]})
```

Notice the deliberate realism baked in: **20 power-user customers** account
for a disproportionate share of orders (a skew you'll have to reason about
in Question 11), `order_items.unit_price` can differ from
`products.unit_price` (prices change over time — always compute revenue
from the line item's price, never re-join back to the current catalog
price), `orders.status` has three values not two, and `page_views` is
mostly anonymous (`customer_id IS NULL`).

---

## Step 2 — Answer all 12 analytics questions

Write one query per question. Each must run correctly against the
generated data above — no partial credit for "the logic is right but I
didn't handle NULLs/cancelled orders/ties." State any assumption you make
explicitly as a SQL comment above the query.

1. **Monthly revenue trend.** Total revenue by month, completed orders
   only, with month-over-month percent change.
2. **Top 5 products by revenue**, overall, with their category.
3. **Top 2 products by revenue, per category** — and say out loud whether
   you used `ROW_NUMBER` or `RANK` and why.
4. **Customer lifetime value (LTV) leaderboard** — top 20 customers by
   total completed-order spend, including customers with zero orders
   (LTV = 0, not absent from the leaderboard).
5. **Cohort retention, month 1** — of customers who signed up in a given
   month, what percentage placed at least one order within 30 days of
   signup? Compute this per signup-month cohort.
6. **New vs. returning revenue split, per month** — for each month, how
   much revenue came from customers whose *first ever order* was in that
   same month (new) vs. customers who had ordered before (returning)?
7. **Cancellation/refund rate by product category.**
8. **Customers who viewed a product but never bought anything in that
   category** — a browse-to-buy gap report, joining `page_views` against
   `orders`/`order_items` with an anti-join.
9. **Days between signup and first order**, per customer, with `NULL` for
   customers who never ordered — and a summary row showing the overall
   median (SQLite has no `MEDIAN()`; derive it).
10. **Running total of cumulative revenue, all-time, by day** — one row per
    calendar day that had at least one completed order, with a cumulative
    total to date.
11. **The power-user skew, quantified** — what percentage of total
    completed-order revenue comes from the top 1% of customers by order
    count? (This is the report that should make the planted skew visible
    in your own numbers.)
12. **A referral-source funnel** — signup count, percentage who ever
    ordered, and average LTV, grouped by `referral_source` (including
    `NULL` as its own explicit group, not silently dropped).

<details>
<summary>Hints (expand only if stuck — try each question for real first)</summary>

- Q1, Q10: `LAG()`/`SUM() OVER (ORDER BY ...)` — see
  [Concept 02](../concepts/02_window_functions.md).
- Q3: `ROW_NUMBER()`/`RANK() OVER (PARTITION BY category ORDER BY revenue DESC)`
  in a CTE, filtered in the outer query — see
  [Concept 02, section 8](../concepts/02_window_functions.md#8-worked-example-top-n-per-group).
- Q4: `LEFT JOIN` from `customers`, `COALESCE(SUM(...), 0)` — see
  [Concept 04, section 6](../concepts/04_aggregations_and_grouping.md#6-coalesce-with-aggregates--including-zero-activity-groups).
- Q5, Q6, Q9: needs each customer's **first order date** as its own
  building block — compute it once in a CTE (`MIN(order_date) GROUP BY
  customer_id`, or `ROW_NUMBER() ... WHERE rn = 1`) and reuse it, rather
  than recomputing it inline in every downstream query.
- Q8: `page_views` anti-joined against a customer's own `orders`/
  `order_items` **for the same product's category**, not just "never
  ordered anything at all" — read the question grain carefully.
- Q9's median: SQLite has no `MEDIAN()`/`PERCENTILE_CONT` — derive it from
  `NTILE`/`ROW_NUMBER` and row-count parity, or via
  `OFFSET (COUNT(*)/2)` on a sorted list; state which approach you used
  and its limitation (e.g. doesn't average the two middle values on an
  even count, if that's the shortcut you took).
- Q11: this is Q4/Q11's LTV plus `NTILE(100)` or a computed percentile
  threshold on order count — the "top 1%" cutoff has to be *computed*, not
  hardcoded to a customer count you eyeballed.
- Q12: `LEFT JOIN customers` to an aggregated orders CTE, `GROUP BY
  referral_source` — and don't filter out `NULL` referral_source rows,
  since "we don't know their source" is itself a real, reportable segment.

</details>

---

## Step 3 — Tune it

Pick your **two slowest queries** from Step 2 (time them — wrap each in
the `timeit` pattern from
[Concept 05's setup](../concepts/05_query_optimization_and_indexing.md#0-setup--run-this-once)).
For each one:

1. Run `EXPLAIN QUERY PLAN` and identify every `SCAN` on a table larger
   than a few hundred rows.
2. Add the index(es) you believe will help, and re-run `EXPLAIN QUERY
   PLAN` to confirm the plan actually changed (`SCAN` -> `SEARCH`), not
   just that you added an index and hoped.
3. Re-time the query and report the before/after numbers.
4. Write one paragraph: what would you check first if this same query
   were still slow on a table with 500 million rows instead of tens of
   thousands? (Your answer should reference
   [Concept 06](../concepts/06_reading_explain_plans.md) — naming a real
   Postgres-style plan concept, e.g. "I'd want to see whether the
   optimizer chose a Nested Loop where a Hash Join was warranted, and
   check estimated vs. actual row counts for a stale-statistics problem,"
   is the level of specificity this paragraph should hit.)

---

## Stretch goals (optional, for a "senior" pass)

- Rewrite Q5 (cohort retention) so it produces every cohort month **and**
  every "days since signup" bucket (0–7, 8–30, 31–90, 90+) as columns —
  a small pivot report, using conditional aggregation
  ([Concept 04, section 5](../concepts/04_aggregations_and_grouping.md#5-case-inside-an-aggregate--conditional-counting-pivots)).
- Add a `WITH RECURSIVE` date-spine CTE so Q1 and Q10 show **every**
  month/day in range, including ones with zero completed orders, instead
  of silently omitting them — see
  [Concept 03, section 7](../concepts/03_ctes_and_recursive_queries.md#7-worked-example-generating-a-series-to-fill-report-gaps).
- Simulate `products.category` being renamed mid-dataset (update a
  category value for rows after a cutoff date) and show how Q2/Q3's
  "top products by category" numbers change depending on whether you treat
  the rename as a data correction or a real category change — this is the
  SQL-query-side mirror of the SCD Type 1 vs Type 2 reasoning from data
  modeling, applied to a query rather than a schema decision.

---

## Self-check rubric

Before considering this done, you should be able to say yes to all of the
following:

- [ ] All 12 queries run without error against the generated database.
- [ ] Every query that could return a misleading `NULL`-dropped or
      zero-activity-dropped result (Q4, Q7, Q12) explicitly handles it —
      not by luck, but because you checked.
- [ ] You can state, for at least 3 of the 12 queries, whether you used a
      window function or a `GROUP BY` and *why* that was the right choice
      for that specific question's grain.
- [ ] You ran `EXPLAIN QUERY PLAN` on your two slowest queries before
      guessing at an index, not after.
- [ ] You can explain, out loud, in under a minute, what the planted
      power-user skew (Q11) would mean for this same workload running on
      a distributed engine instead of single-node SQLite.
