# 1. Worked Scenarios: Write This Query Live

Part of the [Interview Questions](README.md) series — see that index for
how this file fits with the other three.

A SQL round is almost always **live coding against a schema the interviewer
hands you** — not "design a schema from scratch" (that's data modeling's
job) and not multiple choice. What's scored is whether you can turn a
one-sentence business question into a correct query while *talking through
your reasoning*, including catching your own mistakes. Every scenario below
follows the same shape: the business question, a narrated first attempt
that's subtly wrong (a real mistake people actually make under pressure,
not a strawman), why it's wrong, then the corrected query with its actual
output shown.

**Read scenarios 1–5 straight through once** to see the reasoning modeled
end to end. Then do scenario 6 yourself, out loud, before expanding the
debrief.

---

## The schema (given once, used for every scenario below)

> In a real interview this would be handed to you on a whiteboard/shared
> doc. Treat it exactly that way here — every scenario below queries
> *this* schema, nothing more.

```sql
CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    signup_date  TEXT NOT NULL,
    country      TEXT NOT NULL
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL,
    order_date   TEXT NOT NULL,
    status       TEXT NOT NULL   -- 'completed' or 'cancelled'
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL
);
```

```text
customers                          products
1  Alice  2023-11-01  US           1  Widget A  Gadgets
2  Bob    2023-12-15  US           2  Widget B  Gadgets
3  Carol  2024-01-05  UK           3  Widget C  Home
4  Dave   2024-01-20  US           4  Widget D  Home
5  Eve    2024-02-10  UK           5  Widget E  Office

orders                                          order_items (order_item_id, order_id, product_id, qty, unit_price)
101  cust 1  2024-01-05  completed               1   101  1  2  20.00
102  cust 1  2024-02-10  completed               2   101  3  1  30.00
103  cust 2  2024-01-15  completed               3   102  2  3  15.00
104  cust 3  2024-01-06  completed               4   103  1  1  20.00
105  cust 3  2024-03-01  completed               5   103  5  2  10.00
106  cust 4  2024-01-25  completed               6   104  3  2  30.00
107  cust 5  2024-02-12  completed               7   104  4  1  25.00
108  cust 2  2024-02-01  cancelled               8   105  2  5  15.00
                                                  9   106  5  1  10.00
                                                 10   106  1  3  20.00
                                                 11   107  4  2  25.00
                                                 12   108  1  1  20.00
```

Note the deliberate landmine: **order 108 is cancelled** — every revenue
question below has to decide, and say out loud, whether cancelled orders
count.

---

## Scenario 1: "Top-selling product, by revenue, in each category"

**Interviewer:** *"For each product category, find the top-selling product
by revenue. Only count completed orders."*

**Narrated wrong first attempt:**
> "I'll join everything, group by category, and take the max revenue."
```sql
SELECT p.category, p.product_name, SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status = 'completed'
GROUP BY p.category
ORDER BY revenue DESC;
```
**Why it's wrong, caught mid-sentence:** *"Wait — I grouped by `category`
only, but `product_name` isn't in the `GROUP BY` and isn't wrapped in an
aggregate. SQLite will silently pick *some* product_name per category
(usually the first one it scans), not necessarily the top one — this
doesn't even error, it just quietly returns a `product_name` that has
nothing to do with the `revenue` number next to it. I need per-*product*
revenue first, then rank products *within* category."*

**Corrected query:**
```sql
WITH product_revenue AS (
    SELECT p.category, p.product_name,
           SUM(oi.quantity * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE o.status = 'completed'
    GROUP BY p.category, p.product_id, p.product_name
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rnk
    FROM product_revenue
)
SELECT category, product_name, revenue
FROM ranked
WHERE rnk = 1
ORDER BY category, product_name;
```

**Output:**
```text
category   product_name   revenue
Gadgets    Widget A       120.0
Gadgets    Widget B       120.0
Home       Widget C       90.0
Office     Widget E       30.0
```

**Narration of the interesting part:** *"Notice Gadgets has **two** rows —
Widget A and Widget B are tied at exactly $120. I used `RANK()`, not
`ROW_NUMBER()`, on purpose: `RANK()` correctly surfaces both tied leaders;
`ROW_NUMBER()` would have arbitrarily kept only one of them and silently
hidden the tie. If the ask were 'exactly one product per category no
matter what,' I'd switch to `ROW_NUMBER()` and say out loud that ties get
broken arbitrarily."*

---

## Scenario 2: "Month-over-month revenue growth"

**Interviewer:** *"Show total revenue per month, completed orders only, and
the percent change from the previous month."*

**Narrated wrong first attempt:**
> "I'll get monthly revenue, then use LAG to grab the previous month and
> compute a percent change."
```sql
SELECT SUBSTR(o.order_date, 1, 7) AS month,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       ROUND((SUM(oi.quantity * oi.unit_price)
              - LAG(SUM(oi.quantity * oi.unit_price)) OVER (ORDER BY SUBSTR(o.order_date, 1, 7)))
             * 100.0 / SUM(oi.quantity * oi.unit_price), 1) AS pct_change
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status = 'completed'
GROUP BY SUBSTR(o.order_date, 1, 7);
```
**Why it's wrong, caught mid-sentence:** *"I divided by `SUM(...)` — the
**current** month's revenue — but percent change should be relative to the
**previous** month's revenue. I need `LAG(...)` in the denominator too, not
the current month's sum. Also, mixing a raw aggregate and a window function
that both reference the same expression this way is error-prone — I'll
compute monthly revenue in a CTE first, then apply `LAG` cleanly on top of
one column."*

**Corrected query:**
```sql
WITH monthly_revenue AS (
    SELECT SUBSTR(o.order_date, 1, 7) AS month,
           SUM(oi.quantity * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY SUBSTR(o.order_date, 1, 7)
)
SELECT month, revenue,
       LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue,
       ROUND((revenue - LAG(revenue) OVER (ORDER BY month)) * 100.0
             / LAG(revenue) OVER (ORDER BY month), 1) AS pct_change
FROM monthly_revenue
ORDER BY month;
```

**Output:**
```text
month     revenue   prev_month_revenue   pct_change
2024-01   265.0     None                 None
2024-02   95.0      265.0                -64.2
2024-03   75.0      95.0                 -21.1
```

**Narration:** *"January has no `prev_month_revenue`, so `pct_change` is
correctly `NULL`, not zero or an error — that's expected and worth stating,
not something to paper over with `COALESCE`."*

---

## Scenario 3: "Customers who ordered in January but not February"

**Interviewer:** *"Find every customer who placed an order in January 2024
but placed no order at all in February 2024."*

**Narrated wrong first attempt:**
> "I'll filter orders to January-or-February, then just check the date is
> in January and also check it's not in February, in one WHERE."
```sql
SELECT DISTINCT customer_id
FROM orders
WHERE order_date >= '2024-01-01' AND order_date < '2024-02-01'
  AND order_date NOT (order_date >= '2024-02-01' AND order_date < '2024-03-01');
```
**Why it's wrong, caught mid-sentence:** *"This doesn't even make sense
once I say it out loud — a single `order_date` on a single row can't be
'in January' AND 'not in February' as two conditions on the *same column
value* the way I've written it; that second half is nonsensical here (and
wouldn't even parse). The real question spans **two different rows** for
the same customer — one in January, and the absence of any row in
February. That's a job for two separate scopes of `orders`, joined or
anti-joined by `customer_id`, not one `WHERE` clause on one row."*

**Corrected query:**
```sql
SELECT DISTINCT o1.customer_id
FROM orders o1
WHERE o1.order_date >= '2024-01-01' AND o1.order_date < '2024-02-01'
  AND NOT EXISTS (
      SELECT 1 FROM orders o2
      WHERE o2.customer_id = o1.customer_id
        AND o2.order_date >= '2024-02-01' AND o2.order_date < '2024-03-01'
  )
ORDER BY o1.customer_id;
```

**Output:**
```text
customer_id
3
4
```

**Narration:** *"Carol (3) and Dave (4) ordered in January and never
touched February. Bob (2) is excluded even though his one February order
(108) was *cancelled* — because I didn't filter on `status` at all here,
and I'd say that out loud as a real ambiguity: does a cancelled order count
as 'placed an order' for this question? I'd ask the interviewer rather than
silently pick one interpretation."*

---

## Scenario 4: "Days between each customer's first and second order"

**Interviewer:** *"For each customer with at least two orders, how many
days elapsed between their first and second order?"*

**Narrated wrong first attempt:**
> "Self-join orders to itself where the second order's date is later than
> the first, then take the difference."
```sql
SELECT o1.customer_id, MIN(julianday(o2.order_date) - julianday(o1.order_date)) AS days_to_next
FROM orders o1
JOIN orders o2 ON o1.customer_id = o2.customer_id AND o2.order_date > o1.order_date
GROUP BY o1.customer_id;
```
**Why it's wrong, caught mid-sentence:** *"This finds, for every order,
the closest *later* order — but I haven't pinned `o1` down to specifically
be each customer's **first** order. If a customer had three or more
orders, this join produces every later-pair combination, and the `MIN(...)`
GROUP BY collapses it in a way that doesn't clearly mean 'gap between order
1 and order 2' anymore — it's coincidentally right for customers with
exactly two orders, and wrong the moment there's a third. I should assign
an explicit order sequence per customer first, then join sequence 1 to
sequence 2 by name."*

**Corrected query:**
```sql
WITH sequenced AS (
    SELECT customer_id, order_date,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) AS seq
    FROM orders
)
SELECT first_o.customer_id,
       CAST(julianday(second_o.order_date) - julianday(first_o.order_date) AS INTEGER) AS days_between
FROM sequenced first_o
JOIN sequenced second_o
  ON first_o.customer_id = second_o.customer_id
 AND first_o.seq = 1 AND second_o.seq = 2
ORDER BY first_o.customer_id;
```

**Output:**
```text
customer_id   days_between
1             36
2             17
3             55
```

**Narration:** *"Customers 4 and 5 have exactly one order each, so they
correctly don't appear at all — an `INNER JOIN` on `seq = 1 AND seq = 2`
naturally drops anyone without a second row to match, which is exactly the
'at least two orders' requirement, for free, with no extra filter needed.
I also included order 108 (Bob's cancelled order) as his 'second order' —
worth flagging the same ambiguity as scenario 3: should a cancelled order
count toward the sequence at all?"*

---

## Scenario 5: "Cumulative distinct customers acquired, by month"

**Interviewer:** *"Show new customer signups per month, and a running total
of all customers acquired to date."*

**Narrated wrong first attempt:**
> "I'll just use a window function directly — COUNT DISTINCT customer_id,
> ordered by month."
```sql
SELECT SUBSTR(signup_date, 1, 7) AS month,
       COUNT(DISTINCT customer_id) OVER (ORDER BY SUBSTR(signup_date, 1, 7)) AS cumulative_customers
FROM customers;
```
**Why it's wrong, caught mid-sentence:** *"This actually errors —
`COUNT(DISTINCT ...)` is not allowed as a window function in SQLite, and
it isn't standard in most other engines either (Postgres doesn't support it
as a window function). I need to collapse to one row per month **first**
with an ordinary `GROUP BY`, and only run the window function on top of
that already-aggregated result."*

**Corrected query:**
```sql
WITH monthly_signups AS (
    SELECT SUBSTR(signup_date, 1, 7) AS month, COUNT(*) AS new_customers
    FROM customers
    GROUP BY SUBSTR(signup_date, 1, 7)
)
SELECT month, new_customers,
       SUM(new_customers) OVER (ORDER BY month) AS cumulative_customers
FROM monthly_signups
ORDER BY month;
```

**Output:**
```text
month     new_customers   cumulative_customers
2023-11   1               1
2023-12   1               2
2024-01   2               4
2024-02   1               5
```

**Narration:** *"Since every `customer_id` is already unique in
`customers`, `COUNT(*)` per month is the same as `COUNT(DISTINCT
customer_id)` per month here — the `GROUP BY` did the de-duplication, so
the window function on top just needs a plain `SUM`, no `DISTINCT`
required at that stage at all."*

---

## Now You Try: "Best customer per country, by lifetime spend"

**Interviewer prompt:**
> "For each country, find the customer with the highest total spend across
> all their completed orders. Show the country, customer name, and their
> total spend."

Write the query yourself — including at least one narrated wrong first
attempt — before expanding the debrief.

<details>
<summary>Debrief — expand only after you've attempted it</summary>

**A very tempting wrong first attempt:**
```sql
SELECT c.country, c.name, MAX(SUM(oi.quantity * oi.unit_price)) AS total_spend
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'completed'
GROUP BY c.country;
```
This doesn't run at all on most engines — `MAX(SUM(...))`, an aggregate
function wrapped around another aggregate function, is illegal in a single
`GROUP BY` level. The instinct behind it ("I need the max of a
per-customer total") is right; the fix is to compute the per-customer
total in one grouping step, and rank/max *that* in a second step.

**Correct query:**
```sql
WITH customer_spend AS (
    SELECT c.country, c.customer_id, c.name,
           SUM(oi.quantity * oi.unit_price) AS total_spend
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'completed'
    GROUP BY c.country, c.customer_id, c.name
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY country ORDER BY total_spend DESC) AS rnk
    FROM customer_spend
)
SELECT country, name, total_spend
FROM ranked
WHERE rnk = 1
ORDER BY country;
```

**Output (against the shared schema):**
```text
country   name    total_spend
UK        Carol   160.0
US        Alice   115.0
```

`ROW_NUMBER()`, not `RANK()`, is the right call here specifically because
the question says "**the** customer" (singular) — an explicit signal that
exactly one row per group is wanted even if there's a tie, unlike Scenario
1 where showing every tied leader was the more correct interpretation of
"top-selling product." Naming *why* you picked `ROW_NUMBER` over `RANK`
for this specific wording — not just defaulting to whichever one you
remember first — is the detail that separates a strong answer here.

</details>

---

## What Interviewers Are Actually Scoring

- Do you say the business question back in your own words before typing
  anything?
- Do you narrate the query as you build it, rather than typing silently
  and revealing a finished block?
- When you make a mistake (and you likely will, live), do you catch it
  yourself and explain *why* it's wrong — not just patch it silently?
- Do you flag genuine ambiguities in the question (does a cancelled order
  count? ties broken how?) instead of silently picking an interpretation?
- Can you justify `ROW_NUMBER` vs `RANK` for the *specific wording* of the
  question, not by rote?

**Next:** [02 — Rapid-Fire Q&A](02_rapid_fire_qna.md)
