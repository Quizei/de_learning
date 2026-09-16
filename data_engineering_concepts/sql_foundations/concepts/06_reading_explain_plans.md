# Concept 06: Reading EXPLAIN Plans Out Loud

**Covers:**
- Why this is its own concept file, separate from Concept 05
- SQLite's `EXPLAIN QUERY PLAN`: the two-word vocabulary (recap + when it's not enough)
- Postgres `EXPLAIN` / `EXPLAIN ANALYZE`: reading a plan tree bottom-up
- The scan node types: Seq Scan, Index Scan, Index Only Scan, Bitmap Heap Scan
- The join node types: Nested Loop, Hash Join, Merge Join — and what each implies about table sizes
- `cost=`, `rows=`, `actual time=` — what the numbers mean, and the #1 thing to check (estimated vs actual row mismatch)
- A full worked plan, read aloud line by line, the way an interviewer wants to hear it
- One-paragraph note on MySQL's `EXPLAIN` for completeness

> This file is intentionally engine-agnostic in spirit but concrete in one
> engine (**Postgres**) for the worked example, because reading a real
> cost-based optimizer's plan — not just SQLite's SCAN/SEARCH — is what a
> "walk me through this query plan" interview question is actually testing.
> If you only ever touch SQLite day to day, read this file anyway: the
> *vocabulary* (scan types, join types, cost vs actual) is what gets asked
> about, independent of which engine's flavor of syntax you'd type.

---

## Why this file exists

[Concept 05](05_query_optimization_and_indexing.md) covers SQLite's
`EXPLAIN QUERY PLAN`, which only really says two things: `SCAN` (read
everything) or `SEARCH ... USING INDEX` (index-assisted). That's the right
amount of detail for tuning a query against SQLite, but it's **not** the
depth a mid-level interview question expects when someone says *"here's an
`EXPLAIN ANALYZE` output, walk me through it."* Real production engines
(Postgres, MySQL, SQL Server, Snowflake, BigQuery) expose a cost-based
optimizer's actual decision: which join algorithm it picked, how many rows
it expected vs how many it actually got, and where the time really went.
Being able to read that output *out loud, node by node* is one of the most
reliable "are you actually senior" signals in a SQL round.

---

## 1. The scan node types

Every plan node reads data from somewhere at the leaves of the tree. The
four you'll see constantly:

- **Seq Scan** (Postgres) / full table scan — reads every row in the table,
  in physical storage order. Correct when a query legitimately needs most
  of the table (small table, or a filter that isn't selective), a red flag
  on a large table with a selective `WHERE`.
- **Index Scan** — walks a B-tree index to find matching rows, then fetches
  each matching row individually from the table (a "heap fetch") to get any
  column not in the index. Fast when the filter is selective; can actually
  be *slower* than a Seq Scan if the filter matches a large fraction of the
  table, because of all the extra random-access heap fetches.
- **Index Only Scan** — like Index Scan, but every column the query needs
  is already in the index, so **no heap fetch is needed at all**. This is
  Postgres's name for exactly the "covering index" concept from Concept 05.
- **Bitmap Heap Scan** (paired with a **Bitmap Index Scan**) — builds an
  in-memory bitmap of matching row locations from the index first, sorts
  those locations, then fetches rows from the table in physical order.
  This is the optimizer's middle ground: better than a plain Index Scan
  when many rows match (fewer random heap fetches, more sequential ones),
  better than a Seq Scan when *not* every row matches.

```text
Selectivity spectrum (roughly), matching filter -> matches ~x% of table:
   very selective (<1%)     Index Scan / Index Only Scan   fastest
   moderately selective     Bitmap Heap Scan                middle
   not selective (>~20%)    Seq Scan                        often fastest anyway
                             (random heap fetches for every match cost more
                              than just reading the table start to finish)
```

---

## 2. The join node types

Just as important as scans: which **join algorithm** the optimizer picked,
and what that implies about the sizes it estimated for each side.

- **Nested Loop** — for every row on the outer side, scan (or index-probe)
  the inner side looking for matches. `O(n * m)` in the worst case (or
  `O(n * log m)` if the inner side is index-probed) — cheap when one side
  is small, or when there's a good index to probe with, expensive
  otherwise. Seeing a Nested Loop over two large tables with **no** index
  on the inner side's join key is the single most common "explain this slow
  plan" interview answer.
- **Hash Join** — build an in-memory hash table on the smaller side (the
  "build" side) once, then stream the larger side through it, probing the
  hash table per row. The relational-database equivalent of Spark's Shuffle
  Hash Join — see
  [`spark_course/concepts/14_join_strategies.md`](../../../spark_course/concepts/14_join_strategies.md)
  if that comparison helps. Good default for large-large equi-joins when
  there's enough memory (`work_mem` in Postgres) to hold the smaller side's
  hash table.
- **Merge Join** — both sides are sorted (or already arrive sorted, e.g.
  off an index) by the join key, then merged in one linear pass — the same
  idea as Spark's Sort-Merge Join. Chosen when both inputs are already
  sorted for free (avoiding an explicit sort step) or when memory for a
  hash table is scarce.

```text
Nested Loop:  for each outer row -> probe/scan inner side       O(n*m) worst case
Hash Join:    build hash table on smaller side, probe with larger  O(n+m)
Merge Join:   both sides sorted by key, single merge pass          O(n+m), needs sorted input
```

---

## 3. Reading the numbers: cost, rows, actual time

A Postgres plan line looks like:

```text
Hash Join  (cost=1.23..845.67 rows=312 width=48) (actual time=0.045..12.301 rows=298 loops=1)
```

- **`cost=1.23..845.67`** — the optimizer's own estimated cost, in
  arbitrary units, as `startup_cost..total_cost`. Startup cost is the work
  needed before the *first* row can be returned (relevant for a query with
  `LIMIT`); total cost is the estimate to return *all* rows. These numbers
  are only meaningful relative to each other within the same plan — never
  read them as milliseconds.
- **`rows=312`** — the optimizer's *estimate* of how many rows this node
  will produce, based on table statistics.
- **`actual time=0.045..12.301 rows=298 loops=1`** — only present with
  `EXPLAIN ANALYZE` (which actually **runs** the query, not just plans it):
  real elapsed time for the first row and for all rows, the real row
  count, and how many times this node executed (`loops` — a Nested Loop's
  inner side runs once *per outer row*, so `loops` can be large there).

**The single most important comparison on the whole plan: estimated `rows=`
vs actual `rows=`.** A large mismatch (estimated 10, actual 2,000,000) means
the optimizer's statistics are stale or the predicate is something it can't
estimate well (a UDF, a highly-correlated multi-column filter) — and a bad
row estimate is *why* the optimizer might pick a Nested Loop where a Hash
Join would have been far cheaper. This exact failure mode is the SQL-engine
analogue of the Spark AQE story in
[`spark_course/practice/exercises.md`, Exercise 7](../../../spark_course/practice/exercises.md)
— stale/unavailable statistics lead the optimizer to the wrong physical
strategy, and the fix in both worlds is the same shape: refresh statistics
(`ANALYZE table_name` in Postgres, same command name coincidentally), or
force the strategy explicitly if you can't trust the estimate.

---

## 4. A full worked plan, read aloud

```text
EXPLAIN ANALYZE
SELECT o.order_id, c.customer_name, o.total_price
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE c.tier = 'Gold' AND o.order_date >= '2024-01-01';

QUERY PLAN
-----------------------------------------------------------------------------------
Hash Join  (cost=14.50..892.30 rows=1450 width=52) (actual time=0.412..8.203 rows=1523 loops=1)
  Hash Cond: (o.customer_id = c.customer_id)
  ->  Seq Scan on orders o  (cost=0.00..820.00 rows=14800 width=24)
                             (actual time=0.010..5.100 rows=15012 loops=1)
        Filter: (order_date >= '2024-01-01')
        Rows Removed by Filter: 34988
  ->  Hash  (cost=12.00..12.00 rows=200 width=36) (actual time=0.380..0.380 rows=198 loops=1)
        ->  Index Scan using idx_customers_tier on customers c
              (cost=0.29..12.00 rows=200 width=36) (actual time=0.015..0.320 rows=198 loops=1)
              Index Cond: (tier = 'Gold')
Planning Time: 0.315 ms
Execution Time: 8.512 ms
```

Read **bottom-up, inside-out** — the deepest-indented nodes run first and
feed their parent:

1. *"The plan roots at a `Hash Join`."* Its two children are the build and
   probe sides.
2. *"The build side is `customers`: an `Index Scan using idx_customers_tier`
   filters to `tier = 'Gold'`, estimated 200 rows, actually got 198 — close
   estimate, healthy statistics."* Those 198 rows get built into an
   in-memory hash table (the `Hash` node above it).
3. *"The probe side is `orders`: a `Seq Scan`, not an Index Scan — even
   though there's a filter on `order_date`, the planner chose to read the
   whole table and filter in memory (`Rows Removed by Filter: 34988`),
   which means either there's no index on `order_date`, or the planner
   decided the filter isn't selective enough for an index to be worth it."*
4. *"Every row surviving that filter (15,012 of them) streams through and
   probes the 198-row hash table built from `customers` — cheap, because
   the hash table is small."*
5. *"Estimated vs actual rows are close everywhere (14,800 vs 15,012;
   1,450 vs 1,523) — statistics look healthy, so I'd trust this plan rather
   than suspect stale stats."*
6. *"Total execution time 8.5ms — if this were slow in production, the
   first thing I'd check is whether `orders.order_date` has an index; a
   Seq Scan reading 50,000 rows to keep only 15,012 is the biggest single
   line item here."*

That six-sentence narration — root, then each child, then the
estimate-vs-actual sanity check, then a concrete next step — **is** the
shape of a strong answer to "walk me through this plan."

---

## 5. A one-paragraph note on MySQL

MySQL's `EXPLAIN` (and `EXPLAIN ANALYZE` since MySQL 8.0.18) uses different
vocabulary for the same ideas: `type` (`ALL` = full scan, `ref`/`eq_ref` =
index lookup, `index` = full index scan), `key` (which index was actually
used), `rows` (estimated rows examined), and `Extra` (`Using filesort`,
`Using temporary`, `Using index` for a covering index). The concepts map
directly — `type: ALL` is a Seq Scan, `Using index` is an Index-Only Scan,
`Using filesort`/`Using temporary` flag an expensive sort or temp table the
same way a Postgres plan would show an explicit `Sort` or `Hash` node — so
the reading strategy from section 4 (root down, check estimate vs actual,
name the expensive node) transfers, only the labels change.

---

## Key Takeaways

- SQLite's `EXPLAIN QUERY PLAN` (Concept 05) only distinguishes `SCAN` vs
  `SEARCH` — a real cost-based optimizer (Postgres/MySQL/SQL Server) exposes
  far more: which join algorithm, estimated vs actual row counts, and
  per-node timing. Know both vocabularies.
- The four scan types to name on sight: Seq Scan (full read), Index Scan
  (index + heap fetch), Index Only Scan (covering index, no heap fetch),
  Bitmap Heap Scan (the middle ground for medium selectivity).
- The three join types to name on sight: Nested Loop (cheap only when one
  side is small or index-probed), Hash Join (build a hash table on the
  smaller side, stream the larger), Merge Join (both sides pre-sorted, one
  linear pass).
- `cost=` is a unitless, relative-only estimate; `actual time=`/`rows=`
  (from `EXPLAIN ANALYZE`, which really executes the query) are real
  measurements — always prefer `ANALYZE` output when it's safe to run.
- The single highest-value check on any plan: **does the estimated row
  count match the actual row count?** A big mismatch means stale or
  unusable statistics, and it's usually *why* the optimizer picked the
  wrong physical strategy.
- When narrating a plan out loud: start at the root, walk down to the
  leaves, name each node's algorithm and its estimate-vs-actual, then
  name the single most expensive node and what you'd do about it.
