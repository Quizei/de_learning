# 5. dbt Project Structure & Testing Strategy Drill

Part of the [Interview Questions](README.md) series.

"How would you structure a dbt project?" and "what's your testing
strategy?" come up in some form in nearly every dbt-adjacent interview,
often as a standalone question rather than embedded in a full scenario
— frequent enough, and practical enough, to warrant its own dedicated
drill rather than living only inside [file 1](01_worked_scenarios.md).
This file works through the decision points one at a time. Answer each
before expanding the model answer.

---

## Part A: Structure

**Q: Someone hands you a brand-new dbt project with a single `models/`
folder containing forty flat `.sql` files, no subfolders, mixed staging
and mart logic. What's your first move, and why in that order?**

<details>
<summary>Model answer</summary>

First, read enough of the DAG (`dbt docs generate` or `dbt list
--select ...`) to identify which models are doing 1:1 source cleanup
(staging candidates) versus final business-facing tables (mart
candidates) versus business-logic joins in between (intermediate
candidates) — classify before moving anything. Then physically
reorganize into `staging/`, `intermediate/`, `marts/` subfolders,
renaming to the `stg_`/`int_`/`fct_`/`dim_` conventions as you go. The
reason to classify *before* restructuring, rather than restructuring
folder-by-folder as you go, is that dbt's file location doesn't affect
execution order at all (the DAG comes from `ref()`/`source()` calls,
not folder structure) — so there's no risk of breaking anything by
reorganizing, which means there's no reason to rush it model-by-model
instead of planning the full target layout first.

</details>

---

**Q: Why does the staging layer specifically forbid joins, even a
simple one?**

<details>
<summary>Model answer</summary>

Because a staging model's entire job is making exactly *one* source
table trustworthy (rename, cast, clean) — the moment it joins to
another table, it's no longer 1:1 with a single source, and any model
downstream that `ref()`s it can no longer reason about it as "the
cleaned version of table X." Business logic and joins belong one layer
up (intermediate), specifically so staging models stay a stable,
predictable, swap-in-replaceable layer between raw sources and
everything that depends on them — if a source's raw schema changes, the
blast radius should be contained to that one staging model, not smeared
across a staging model that also happens to encode a join.

</details>

---

**Q: When would you organize marts by *domain* (finance/, sales/,
product/) versus by *entity* (fct_orders.sql, dim_customers.sql,
fct_events.sql all flat)?**

<details>
<summary>Model answer</summary>

Organize by consuming domain/team once a project has enough marts that
"which team owns/consumes this" is the more useful question day to day
than "what entity does this represent" — typically once a project
crosses roughly a dozen or more mart models with genuinely different
consumers. A small project (a handful of marts, one BI consumer) gains
nothing from domain folders and just adds navigation overhead. The
signal to watch for: if two teams' folders both need their own version
of "customer," that's not a structural problem to fix by picking a
different folder scheme — it's the conformed-dimension problem
(`data_modeling/interview_questions/02_rapid_fire_qna.md`), and it needs
a shared upstream model (e.g. a conformed `int_customers__unified`)
that both domain folders' marts build from, not two independently
reasoned "customer" definitions.

</details>

---

**Q: A model needs the same three-way join logic in two different
marts. Where does that shared logic belong?**

<details>
<summary>Model answer</summary>

In its own intermediate model, `ref()`'d by both marts — never
duplicated as the same SQL pasted into two mart files. This is the
direct DRY (don't repeat yourself) argument for the intermediate layer
existing at all: the moment business logic needs to change (a new join
condition, a corrected filter), it changes in exactly one place and
every mart that depends on it picks up the fix automatically on the
next run, instead of someone needing to remember to update both copies.

</details>

---

## Part B: Testing Strategy

**Q: You have a fixed budget of "test-writing time" for a new project.
Where do you spend it first?**

<details>
<summary>Model answer</summary>

Primary-key integrity on every mart first: `unique` + `not_null` on
every `fct_*`/`dim_*` table's key column. This is the cheapest test to
write, catches the most common and most damaging class of bug (a join
that fanned out unexpectedly, producing duplicate rows that silently
inflate every downstream sum), and is close to zero-cost to run. Next,
`relationships` tests from every fact table's foreign keys back to
their dimension tables, catching orphaned rows from a late-arriving or
broken source. Only after those two categories are in place does it
make sense to invest in singular tests for specific business-rule
invariants (revenue reconciliation, non-negative balances) — those are
higher-value per test but also higher-effort to write and specific to
one team's business logic, so they're the right place to spend
*remaining* budget, not the first place.

</details>

---

**Q: Where do source freshness checks belong in this priority order,
and why?**

<details>
<summary>Model answer</summary>

Essentially tied with primary-key integrity for "do this first" — not
because it's the same *kind* of check, but because it protects against
a failure mode neither `unique`/`not_null` nor `relationships` can
catch at all: an upstream sync silently stalling. Every schema test in
the project can be green while a dashboard is eleven days stale, simply
because there's nothing new to fail a test against — this exact gap is
worked through in `03_critique_and_debug.md`, Case 6. A project with
excellent schema tests but no freshness checks has a real, specific
blind spot, not just "room for more tests."

</details>

---

**Q: A generic `not_null` test and a singular test both seem able to
express "this column shouldn't be null." When do you actually need the
singular version instead of just adding a generic test?**

<details>
<summary>Model answer</summary>

Never, for a plain "this column is never null" rule — that's exactly
what the generic `not_null` test is for, and reaching for a singular
test there is needless extra code. Singular tests earn their keep the
moment the rule needs a join, an aggregation, or cross-model logic a
generic test's single-column, single-model shape can't express — "this
column is never null *when a related column has a specific value*," or
"this order's total matches the sum of its line items," aren't
expressible as a parameterized single-column check. The decision rule:
default to a generic test; drop to a singular test only when the
assertion genuinely needs more than one column or one table to state.

</details>

---

**Q: A test fails in CI on a pull request. The PR author says "that
test is flaky, it fails randomly" and wants to skip it and merge. How do
you respond?**

<details>
<summary>Model answer</summary>

Push back on "skip it," because a schema/data test in dbt is
deterministic by construction — it's a `SELECT` that returns zero rows
on pass. A test that "fails randomly" almost always means the
*underlying data* genuinely varies run to run (a race condition in an
upstream load, a test running against a non-deterministic sample, or a
test asserting something that was never actually guaranteed, like
assuming a specific row count). The right response is treating the
so-called flakiness as a real bug to diagnose — either in the test's
own logic (it's asserting something too strict, or against a
non-stable dataset) or in the pipeline it's testing (an actual race
condition worth fixing, not hiding) — not something to silence to
unblock a merge. Skipping a "randomly failing" test without
understanding why is how a real data-quality regression quietly starts
shipping.

</details>

---

**Q: How do you decide whether a business rule belongs in a dbt test,
versus being enforced upstream (e.g. an application-level constraint,
or a warehouse-level `CHECK`/foreign key)?**

<details>
<summary>Model answer</summary>

A dbt test is a *detection* mechanism — it runs after the fact, on
data that's already landed, and tells you something's wrong; it cannot
by itself prevent bad data from ever existing. An upstream constraint
(application validation, a source-system database constraint) is
*prevention* — it stops the bad data from being created in the first
place. The two aren't substitutes: dbt tests are the right (and often
only) place to enforce a rule when you don't own or can't modify the
source system's validation (the overwhelmingly common case for a
central data team consuming from many teams' systems), while an
upstream constraint is strictly better *when you can get it*, since
catching an error at the point of entry is cheaper than catching it a
day later in a nightly `dbt build`. The mature answer names both layers
and says dbt tests are the safety net every project needs regardless,
specifically because you usually don't control the sources feeding it.

</details>
