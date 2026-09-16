# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 01](01_worked_scenarios.md) rehearses full live-coding scenarios.
This file is the other SQL-round mode: **fast, direct conceptual
questions** with no schema attached — the kind asked in a phone screen, or
dropped in the middle of a live-coding session to check you actually
understand a term you just used mid-query. Answer each in under 30 seconds
out loud before reading the model answer.

---

## Joins & Set Operations

**Q: INNER JOIN vs LEFT JOIN — the one-sentence difference?**
> `INNER JOIN` keeps only rows with a match on both sides; `LEFT JOIN`
> keeps every row from the left table regardless of a match, filling
> unmatched right-side columns with `NULL`.

**Q: How do you write a RIGHT JOIN or FULL OUTER JOIN on an engine that
doesn't support them (SQLite, older MySQL)?**
> `RIGHT JOIN B ON cond` is identical to swapping table order and writing
> `B LEFT JOIN A ON cond`. `FULL OUTER JOIN` is a `UNION` (not `UNION ALL`,
> to drop the duplicate matched rows) of a `LEFT JOIN` and its reverse.

**Q: What causes an "accidental" Cartesian product, and how do you spot
it?**
> A `JOIN` with a missing or incomplete join condition — including an
> old-style comma-join (`FROM a, b`) with no matching `WHERE` clause. The
> tell is a result set far larger than either input table; check the join
> condition covers every table pairing before assuming the data is
> "duplicated."

**Q: UNION vs UNION ALL?**
> `UNION` de-duplicates the combined result (it implicitly sorts/hashes to
> find duplicates, which costs something); `UNION ALL` just concatenates,
> keeping duplicates, and is cheaper. Default to `UNION ALL` unless you
> specifically need de-duplication.

**Q: Why does a self join need two aliases?**
> Because both "sides" of the join are the same physical table — SQL needs
> two distinct names to refer to "this row" and "the related row" (e.g.
> employee vs manager) inside the same query.

---

## Window Functions

**Q: What's the one-sentence difference between a window function and
GROUP BY?**
> `GROUP BY` collapses each group to one output row; a window function
> keeps every row and adds a computed column derived from that row's
> partition/frame. Same aggregate functions, completely different output
> shape.

**Q: ROW_NUMBER vs RANK vs DENSE_RANK — the tie behavior for each?**
> `ROW_NUMBER`: always unique, ties broken arbitrarily. `RANK`: ties share
> a rank, next rank skips by the tie count. `DENSE_RANK`: ties share a
> rank, no skip. Full worked example in
> [Concept 02, section 2](../concepts/02_window_functions.md#2-ranking-row_number-rank-dense_rank).

**Q: Why can't you filter directly on a window function's result in the
same SELECT's WHERE clause?**
> Because of clause execution order: `WHERE` runs before window functions
> are evaluated. You have to compute the window function in a subquery or
> CTE, then filter on it in an outer query's `WHERE`.

**Q: What does LAG return for the first row of a partition, and what
happens if you do arithmetic with it?**
> `NULL` (no default supplied). Any arithmetic involving that `NULL`
> propagates to `NULL` — `current_value - NULL` is `NULL`, not
> `current_value`. Supply an explicit default (`LAG(col, 1, 0)`) if that's
> not what you want.

**Q: What's the trap with LAST_VALUE?**
> With the default window frame (`RANGE UNBOUNDED PRECEDING .. CURRENT
> ROW`, implied whenever `ORDER BY` is present), `LAST_VALUE` just returns
> the *current* row's value — you must explicitly widen the frame to
> `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` to get the
> partition's actual last value.

**Q: How do you get "exactly top N per group," guaranteed?**
> `ROW_NUMBER() OVER (PARTITION BY group ORDER BY metric DESC)` in a
> subquery/CTE, then `WHERE rn <= N` in the outer query. `RANK()` would let
> ties push the row count above N.

---

## Aggregation & Grouping

**Q: WHERE vs HAVING?**
> `WHERE` filters individual rows before grouping; `HAVING` filters groups
> after aggregation — you can reference an aggregate function in `HAVING`
> but not in `WHERE`.

**Q: Does COUNT(*) count NULLs? Does COUNT(column)? Does AVG?**
> `COUNT(*)` counts every row regardless of NULLs. `COUNT(column)` counts
> only non-NULL values of that column. `AVG`/`SUM`/`MIN`/`MAX` all silently
> skip NULLs too — critically, `AVG` divides by the **non-NULL** count, not
> the total row count.

**Q: What does GROUP BY require of every column in the SELECT list?**
> Every selected column must either appear in `GROUP BY` or be wrapped in
> an aggregate function — otherwise it's ambiguous which row's value to
> show for a collapsed group. Most engines reject the query outright;
> SQLite is a notable exception that will *silently* pick an arbitrary
> row's value, which is worse.

**Q: How do you include a group with zero matching rows in an aggregated
report, instead of it silently disappearing?**
> `LEFT JOIN` from the "always present" side (e.g. all products) to the
> activity table, then wrap the aggregate in `COALESCE(..., 0)` — `COUNT`
> of an all-NULL group is already 0, but `SUM`/`AVG` return `NULL` without
> the `COALESCE`.

**Q: What do ROLLUP/CUBE/GROUPING SETS do, and does SQLite support them?**
> They compute multiple grouping levels (subtotals + a grand total) in a
> single query instead of several unioned queries. `ROLLUP` gives
> hierarchical subtotals, `CUBE` gives every combination, `GROUPING SETS`
> gives exactly the combinations you list. **SQLite supports none of the
> three** — the portable fallback is `UNION ALL` of each grouping level.

---

## Subqueries & CTEs

**Q: Correlated vs non-correlated subquery?**
> Non-correlated: self-contained, evaluated once, reused. Correlated:
> references a column from the outer query, conceptually re-evaluated once
> per outer row.

**Q: EXISTS vs IN — when do they actually differ in behavior, not just
style?**
> With `NULL`s. `NOT IN` against a subquery that can return even one `NULL`
> silently returns **zero rows** for the entire outer query (three-valued
> logic poisons the whole `AND` chain to `NULL`, which `WHERE` treats as
> false). `NOT EXISTS` has no such trap. `IN`/`EXISTS` (the positive forms)
> don't have this specific problem, but the `NOT` forms are where it bites.

**Q: What must a scalar subquery return?**
> Exactly one row and one column. More than one row raises a runtime error;
> it's usable anywhere a single expression is legal (`SELECT`, `WHERE`,
> `HAVING`).

**Q: What's the actual difference between a CTE and a subquery in FROM?**
> Functionally, for a single reference, essentially none — a CTE is
> readability sugar for the same derived-table idea. The real, engine-
> dependent nuance: some engines (older Postgres versions, notably)
> materialize a CTE as an optimization fence, meaning the planner can't
> push predicates into it the way it could into an inline subquery — worth
> mentioning if asked about performance differences, while being honest
> that modern Postgres (12+) inlines simple CTEs by default now too.

**Q: Can a CTE reference itself, or one defined after it, in the same
WITH block?**
> It can reference **itself** only in a `RECURSIVE` CTE's own recursive
> term. A plain (non-recursive) CTE can reference any CTE defined **before**
> it in the same block, never one defined after.

**Q: What are the two parts of a recursive CTE, and what stops the
recursion?**
> An anchor (base case) and a recursive step, joined by `UNION ALL`. The
> recursion stops when an iteration of the recursive step produces zero new
> rows — controlled by the `WHERE`/`JOIN` condition inside that step.

---

## NULLs & Three-Valued Logic

**Q: What does SQL return for `NULL = NULL`?**
> `NULL`, not `TRUE`. Comparing `NULL` to anything with `=` or `<>` yields
> `NULL` — you must use `IS NULL`/`IS NOT NULL` to actually test for it.

**Q: Why does `x <> NULL` inside a NOT IN subquery break the whole query?**
> `NOT IN (a, b, NULL)` expands to `x<>a AND x<>b AND x<>NULL`. The last
> term is always `NULL`, and `NULL` in an `AND` chain makes the whole
> expression `NULL` — which `WHERE` treats as not-true, so the row is
> dropped. This silently zeroes out results with no error.

**Q: Does `ORDER BY column` put NULLs first or last?**
> Engine-dependent by default — Postgres/Oracle default to `NULL` last on
> `ASC` (last is actually "NULLS LAST" not guaranteed without saying so,
> but that's the common default), SQLite and MySQL default to `NULL` first
> on `ASC`. Never rely on the default — say `ORDER BY column NULLS LAST`
> (or `NULLS FIRST`) explicitly when it matters, on the engines that
> support the clause.

---

## Indexing & Performance

**Q: What's the difference between SCAN and SEARCH in a query plan?**
> `SCAN` reads every row in the table; `SEARCH` uses an index (or a
> primary key) to jump directly to matching rows without reading
> everything.

**Q: Why doesn't a composite index (a, b) help a query that only filters
on b?**
> An index can only be used from its leftmost column(s) inward, like a
> phone book sorted by (last name, first name) — you can jump to "Smith"
> or "Smith, John," but not to "everyone named John" without scanning the
> whole thing.

**Q: What's a covering index?**
> An index that contains every column a query needs, so the engine answers
> the query entirely from the index without a separate lookup into the
> table's actual rows — the fastest possible plan shape.

**Q: What makes a predicate "sargable," and give an example of one that
isn't?**
> Sargable = the engine can use an index to evaluate it directly.
> `WHERE SUBSTR(date_col, 1, 4) = '2024'` is **not** sargable (the function
> wrapping the column defeats the index); `WHERE date_col >= '2024-01-01'
> AND date_col < '2025-01-01'` is sargable and can use an index on
> `date_col`.

**Q: Why does OFFSET/LIMIT pagination get slower on deeper pages, and what
fixes it?**
> The engine has to generate and discard every skipped row before it can
> return the requested page — cost grows with the offset. Keyset (seek)
> pagination (`WHERE id > last_seen_id ORDER BY id LIMIT n`) uses an index
> to jump straight there, at roughly constant cost regardless of depth.

---

## Transactions & Concurrency (the SQL-round basics)

**Q: What does ACID stand for, one clause each?**
> **A**tomicity — a transaction's operations all happen or none do.
> **C**onsistency — a transaction moves the database from one valid state
> to another, respecting constraints. **I**solation — concurrent
> transactions don't see each other's uncommitted changes (to a degree set
> by the isolation level). **D**urability — once committed, a change
> survives a crash.

**Q: Name the standard isolation levels, weakest to strongest.**
> Read Uncommitted -> Read Committed -> Repeatable Read -> Serializable.
> Weaker levels allow more concurrency but more anomalies (dirty reads,
> non-repeatable reads, phantom reads); Serializable prevents all of them
> at the cost of the most contention.

**Q: What's a dirty read vs a phantom read?**
> A dirty read sees another transaction's **uncommitted** change (which
> might later roll back). A phantom read is when re-running the same query
> twice in one transaction returns a **different set of rows** the second
> time, because another transaction inserted/deleted rows matching the
> filter in between.

---

**Next:** [03 — Critique & Debug](03_critique_and_debug.md)
