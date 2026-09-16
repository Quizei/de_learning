# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

The last SQL-round mode: mid-conversation follow-ups that take a query you
just wrote (in this file, in [file 01](01_worked_scenarios.md), or in a
real interview) and push on one assumption. There's rarely one "correct"
answer — what's scored is whether you reason through the trade-off out
loud instead of freezing or giving a one-word answer. Try answering each
before expanding the model answer.

---

**Curveball: "Your top-N-per-group query uses ROW_NUMBER ordered by a
timestamp column. Now make it correct if two rows can share the exact same
timestamp."**

<details>
<summary>Model answer</summary>

With a plain `ROW_NUMBER() OVER (PARTITION BY group ORDER BY ts DESC)`, two
rows tied on `ts` get an **arbitrary** relative order — which one "wins"
top-N is undefined and can even change between runs on some engines. The
fix is a deterministic tiebreaker: add a second `ORDER BY` column that's
guaranteed unique, most simply the primary key —
`ORDER BY ts DESC, id ASC`. Say explicitly *why* this matters beyond
correctness pedantry: a non-deterministic top-N means the same query can
return **different rows** on a re-run against unchanged data, which breaks
reproducibility for anything downstream (a report that should be
identical if re-run, a regression test comparing query output over time).
If the business logic has a real preference for which tied row should win
(e.g. "prefer the lower `id`, since it was inserted first"), encode that
intent in the tiebreaker rather than defaulting to the primary key out of
convenience.

</details>

---

**Curveball: "This works fine at 10,000 rows. How would you paginate it
efficiently at 1 billion rows, especially if the ORDER BY column has a lot
of duplicate values?"**

<details>
<summary>Model answer</summary>

Keyset (seek) pagination is the baseline fix over `OFFSET/LIMIT` (constant
cost per page instead of cost growing with depth — see
[Concept 05, section 6](../concepts/05_query_optimization_and_indexing.md#6-pagination-offsetlimit-vs-keyset)),
but keyset pagination **requires a unique, totally-ordered key to seek on**
— if the `ORDER BY` column has duplicates, `WHERE col > last_seen_value` can
skip or repeat rows that share the boundary value. The fix is a **composite
seek key**: order and seek on `(order_by_col, primary_key)` together —
`WHERE (col, id) > (:last_col, :last_id)` (or the equivalent expanded
`AND`/`OR` form on engines without row-value comparison) — which makes the
seek position unambiguous even with heavy duplication on the primary sort
column. At a full billion rows, also flag the index requirement explicitly:
this only stays fast with a composite index on exactly `(order_by_col, id)`
matching the seek/sort order — without it, you've just moved the full-scan
cost from "per page" to "constant but still enormous."

</details>

---

**Curveball: "The table you're paginating through is being written to
continuously while a client pages through it. What breaks, and how do you
handle it?"**

<details>
<summary>Model answer</summary>

What breaks: a row inserted with a sort-key value **before** the client's
current position can shift every subsequent page's boundary — with
`OFFSET/LIMIT` this can cause a row to be skipped entirely or shown twice
across two page requests, since "row #200,050" isn't a stable identity,
it's a *position* that moves as rows are added/removed. Keyset pagination
is already more robust here by construction: because it seeks on an actual
value (`WHERE col > last_seen`), rows inserted after the client's current
position simply don't affect pages already fetched, and rows inserted
*before* it appear on a future page rather than corrupting the current one
— feels less like a fix and more like keyset pagination not sharing
`OFFSET`'s failure mode in the first place. For a stronger guarantee
(a truly frozen view of the data as of the moment paging started), the
options are a snapshot read (a transaction-level consistent snapshot, e.g.
Postgres's `REPEATABLE READ`/`SERIALIZABLE` isolation, or an explicit
"as of" timestamp column filtered on every page) — flag that this is a
real trade-off between "always show the latest data" and "guarantee every
page is internally consistent," and that most real APIs pick the former
and accept keyset's natural tolerance for concurrent writes as good enough.

</details>

---

**Curveball: "Your window function's PARTITION BY key is heavily skewed —
one partition key accounts for 90% of the rows in a billion-row table.
What changes?"**

<details>
<summary>Model answer</summary>

On a single-node relational engine, a skewed partition key mostly shows up
as one CPU core/worker doing disproportionate work if the engine
parallelizes the window computation by partition — the query doesn't fail,
it just doesn't get the speedup parallelism should give, and that one
partition's sort/frame computation dominates total runtime. This is the
exact same underlying problem as Spark data skew (see
[`spark_course/concepts/07_data_skew.md`](../../../spark_course/concepts/07_data_skew.md)),
just showing up inside a single engine's executor instead of across a
cluster's tasks. Concrete mitigations: check whether the skewed key
actually needs to be in the partition key at all (sometimes it's there out
of habit, not necessity); if the heavy key is a known, small set of values
("UNKNOWN", a single dominant customer), consider isolating and processing
it with a separate, simpler query and unioning the results, rather than
forcing one window spec to cover both the skewed and non-skewed
population; and if this is really a distributed-engine question in
disguise (the data actually lives in Spark/a distributed warehouse), name
that the fix there is the same salting/AQE-skew-join toolkit from the Spark
course, not a SQL-only trick.

</details>

---

**Curveball: "You added one more WHERE filter to an existing report and it
got 10x slower, not faster. How is that possible?"**

<details>
<summary>Model answer</summary>

Several real mechanisms, worth naming more than one: (1) the new filter
column has **no index**, so the optimizer might now choose a completely
different, worse join order or join algorithm to accommodate filtering on
it, even though the old plan (using an index on a different column) was
fine — check `EXPLAIN` before and after, don't assume the plan only got
"a little worse." (2) the new filter, combined with an existing one via
`OR`, defeated an index that a single `AND`-only predicate could have used
cleanly — `OR` across two different columns often can't use a single
index the way a chain of `AND`s can (see the `UNION` rewrite in
[Concept 05, section 7](../concepts/05_query_optimization_and_indexing.md#7-query-rewriting-strategies)).
(3) the new filter wraps a column in a function (even something as
innocent-looking as `LOWER(status) = 'pending'`) and silently made a
previously-sargable predicate non-sargable. (4) stale statistics: the
optimizer's row estimate for the new filter is badly wrong, leading it to
pick a Nested Loop where a Hash Join was actually warranted — re-running
`ANALYZE` on the table is a cheap first thing to try. The universal
first move for all four: **look at `EXPLAIN` before guessing**, and
specifically diff the plan before/after the change rather than
re-deriving one from scratch.

</details>

---

**Curveball: "How would you convince yourself this aggregation query is
actually correct, without eyeballing every row?"**

<details>
<summary>Model answer</summary>

Reconciliation against an independent total, not a row-by-row read: run a
single unfiltered `SELECT SUM(measure), COUNT(*) FROM base_table` and check
that it's consistent with the sum of your grouped/filtered report's output
(accounting for any intentional filters) — if your grouped revenue report
sums to a number 3x higher than the ungrouped total, that's the fan-out bug
from
[`03_critique_and_debug.md`, Case 1](03_critique_and_debug.md#case-1-the-revenue-that-tripled-after-adding-a-join),
caught by arithmetic instead of a manual spot-check. Also worth naming:
compare row counts at each join step (`SELECT COUNT(*)` before and after
adding each `JOIN`) to catch an unintended fan-out or an unintended row
loss early, rather than only checking the final aggregated numbers; and
spot-check a handful of *known* edge cases by hand (a customer with zero
orders, a group with exactly one row, a NULL-heavy row) rather than
random rows, since edge cases are where the bugs in this file actually
live.

</details>

---

**Curveball: "Your recursive CTE walks a manager hierarchy. What happens
if the underlying data has a cycle — Alice reports to Bob who reports to
Alice — and how do you defend against it?"**

<details>
<summary>Model answer</summary>

Without protection, the recursive step keeps finding "new" rows forever
(A -> B -> A -> B -> ...) — most engines eventually hit a recursion-depth
limit and error out, but that can take a long time and a lot of wasted
work first, and some engines/configurations may not have a limit tight
enough to save you quickly. The standard defense is tracking the visited
path inside the CTE itself and refusing to recurse into a node already on
that path:
```sql
WITH RECURSIVE org_chart AS (
    SELECT emp_id, manager_id, name, '/' || emp_id AS path
    FROM employees WHERE manager_id IS NULL
    UNION ALL
    SELECT e.emp_id, e.manager_id, e.name, oc.path || '/' || e.emp_id
    FROM employees e
    JOIN org_chart oc ON e.manager_id = oc.emp_id
    WHERE oc.path NOT LIKE '%/' || e.emp_id || '/%'   -- refuse a node already visited
)
SELECT * FROM org_chart;
```
Also worth naming as a second layer of defense (not a replacement): most
engines let you cap recursion explicitly (SQLite's
`PRAGMA recursive_triggers`/query-level limits, Postgres has no hard cap by
default but you can add `WHERE depth < N` yourself) — cheap insurance
against a data-quality bug turning into a runaway query even if the
path-tracking logic itself has a mistake.

</details>

---

## What Interviewers Are Actually Scoring

- Do you name the *mechanism* behind why something breaks (three-valued
  logic, plan re-costing, fan-out row multiplication), not just that it
  breaks?
- Do you propose a concrete fix with actual syntax, not just a hand-wave
  ("you'd need to handle that")?
- Do you flag genuine trade-offs (freshness vs consistency in the paging
  question, hard cap vs elegant cycle-detection) instead of presenting
  your first idea as the only option?
- Do you connect a SQL-specific gotcha back to a general principle (skew,
  sargability, stale statistics) you'd recognize again in a different
  guise next time?

If a curveball you've actually been asked doesn't fit cleanly into any of
these four files, that's worth noting — it likely means a fifth shape
worth adding here.
