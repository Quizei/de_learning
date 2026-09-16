# 3. Critique & Debug: "What's Wrong With This?"

Part of the [Interview Questions](README.md) series.

A different interview mode from [file 1](01_worked_scenarios.md): instead of "design something from scratch," you're handed a check, a process, or a report and asked **"what's wrong with this?"** Every case below is described in plain prose — no code — because the skill being tested is spotting the flaw from a description, the same way it'd be described to you out loud in an interview. Read the symptom, form your diagnosis, then expand the debrief.

---

## Case 1: The Completeness Check That Passed on a Sample

**Setup:** A team runs `check_completeness` (`concepts/01_data_quality_dimensions.md`) as part of nightly validation, and it's been reporting 99.5% completeness on a critical `email` column for months. A support ticket reveals thousands of customers with genuinely missing emails who never got a required notification. Investigating the check, it turns out someone had added `LIMIT 10000` to the underlying query "to keep the nightly job fast," on a table with 40 million rows.

<details>
<summary>Debrief</summary>

**Diagnosis:** the check was never wrong about the sample it looked at — it was wrong about being told to represent 40 million rows with 10,000 of them, with no guarantee that sample was representative. If missing emails cluster in a particular segment (say, a legacy import that never enforced the field), a small unrepresentative sample can easily show 99.5% while the true population sits far lower.

**Fix:** completeness (and every other dimension check) must run against the actual full table, or, if performance genuinely requires sampling at scale, use an explicit, statistically justified sampling strategy (a large enough random sample with a computed margin of error, not an arbitrary `LIMIT`) and report the check's result *with* that margin of error, not as a bare percentage indistinguishable from a full scan.

**The interview tell:** noticing that "the check is technically correct about what it measured" and "the check answers the question it needs to answer" are two different claims — a `LIMIT` silently added for performance is exactly the kind of change that makes a check keep reporting green while quietly stopping being trustworthy, with no error, no crash, nothing to page anyone about.

</details>

---

## Case 2: The Duplicate Check That Missed Every Fuzzy Duplicate

**Setup:** A customer table's uniqueness check (`GROUP BY name, email HAVING COUNT(*) > 1`) reports zero duplicates, every run, for months. A data cleanup project later finds thousands of duplicate customer records: `"Alice Johnson"` / `"alice@example.com"` sitting alongside `"Alice  Johnson "` (extra space) / `"ALICE@EXAMPLE.COM"` — clearly the same person, entered twice through two different signup flows.

<details>
<summary>Debrief</summary>

**Diagnosis:** an exact-match `GROUP BY` uniqueness check can only ever catch rows that are byte-for-byte identical on the grouped columns. Case differences, whitespace, and genuine near-duplicates (a typo in one field, a nickname vs. a full name) all sail straight through it, because from the database's point of view they're simply different strings — this is the structural blind spot named explicitly in `concepts/01_data_quality_dimensions.md`, section 2.

**Fix:** two layers, not one. First, normalize before comparing — lowercase and trim whitespace on `email`/`name` before the exact-match check, which catches the case/whitespace variant for free. Second, for genuinely fuzzy duplicates (a typo, a nickname), exact matching can never be the mechanism at all — string-similarity-based clustering (Jaccard similarity over character bigrams, or edit-distance ratio) is required, worked as its own problem in `practice/coding_problems.md`.

**The interview tell:** recognizing that "zero duplicates found" from an exact-match check is a claim about the check's *reach*, not a claim about the data being duplicate-free — a candidate who treats a passing uniqueness check as proof of uniqueness, full stop, is missing exactly this distinction.

</details>

---

## Case 3: The Schema Change That Silently Passed CI

**Setup:** A producing team adds a new required column to their events table, with a default value applied only in their own application layer, not in the database. Their CI check (comparing old vs. new schema) reports the change as "added_required_column_with_default" — non-breaking — and the PR merges cleanly. Two weeks later, a downstream BI report that assumes every row in that column is non-null starts silently under-counting, because rows written by any code path that bypassed the application layer (a backfill script, a direct SQL insert from an internal tool) have the column as a real database NULL, contradicting the "has a default" classification.

<details>
<summary>Debrief</summary>

**Diagnosis:** the compatibility classifier was checking the schema *specification* ("this column has a documented default"), not the actual database or write-path guarantee that every writer respects that default. `SchemaEvolution`'s breaking/non-breaking rule (`concepts/03_data_contracts.md`, section 2) is only as good as the thing it's comparing — if "has a default" is asserted in a config file but not enforced at the database or write-path level, the classification can be true on paper and false in practice.

**Fix:** either enforce the default at the database level (a real `DEFAULT` clause, or a `NOT NULL` constraint the database itself rejects violations of) so "has a default" is a guarantee the database backs up, not just a doc comment — or, if that's not possible for this producer, downgrade the classification: a required column whose default is only enforced in application code, with other write paths in play, should be treated as potentially breaking until proven otherwise, not waved through automatically.

**The interview tell:** this is the sharper, easier-to-miss cousin of Case 1 — a check (here, the CI compatibility classifier) can be structurally correct in its own logic and still miss a bug, because it's reasoning about a *claim* about the system (a documented default) rather than an *enforced property* of the system (a database constraint). The fix is always the same shape: find where the claim and the enforcement have drifted apart, and close that gap rather than patch the specific symptom.

</details>

---

## Case 4: The Anomaly Threshold So Loose It Never Fires

**Setup:** A team sets up row-count anomaly detection (`concepts/05_anomaly_detection_and_monitoring.md`) on a critical orders table, using a z-score threshold of `max_zscore=5.0`. Six months later, an upstream integration silently breaks and daily order volume drops by 60% for four straight days before anyone notices — manually, not via the alert, which never fired.

<details>
<summary>Debrief</summary>

**Diagnosis:** a z-score threshold of 5.0 is extremely conservative — on a roughly-normal daily volume distribution, a value 5 standard deviations out is an almost absurdly rare event, so a 60% drop (very likely well inside 2-3 standard deviations for a table with any day-to-day noise at all) may never cross that bar. Whoever configured the check chose a threshold aimed at eliminating false positives entirely, without weighing the cost of the false negatives that choice guarantees.

**Fix:** the threshold is a genuine trade-off, not a constant to set once and forget — a lower threshold (2.5–3.0 is a common starting point) catches real drops faster at the cost of occasionally flagging a legitimately unusual-but-fine day; that cost is what the severity-routing policy from `concepts/05`, section 5 exists to absorb (route a lower-confidence anomaly to a ticket or a dashboard, not a page, so a slightly-too-sensitive threshold doesn't itself cause alert fatigue). The threshold should also be revisited periodically against real incident history, not set once at launch and never touched again.

**The interview tell:** this is the mirror image of alert fatigue, and naming both directions of the same trade-off — too sensitive causes fatigue, too loose causes silent rot, exactly as `concepts/05` states — rather than only worrying about false positives, is what shows a candidate has actually internalized that this is a tuned trade-off, not a threshold with one obviously correct value.

</details>

---

## Case 5: The Contract That Checked Schema and Nothing Else

**Setup:** A team is proud of their newly-adopted data contract process — every producing team's schema is checked in CI, and no breaking schema change has shipped in six months. Despite that, a downstream model retrains on bad data after an upstream team quietly changes `status` from meaning "the order's current fulfillment state" to "the order's state at time of last customer contact" — same column name, same type (`TEXT`), same allowed values (`pending`, `shipped`, `delivered`, `cancelled`). No schema check anywhere flags anything, because nothing about the schema actually changed.

<details>
<summary>Debrief</summary>

**Diagnosis:** the contract enforced *structure* (schema: types, nullability, allowed values) but the actual breaking change here was in **semantics** — what the column *means* — which a structural schema comparison has no way to see. `concepts/03_data_contracts.md`'s `semantics` field (grain, update frequency, meaning) exists precisely for this, but it's easy to treat as documentation rather than something that's actually checked or versioned alongside the schema.

**Fix:** semantic changes need their own review gate, distinct from the automated schema-diff check — a required, human-reviewed field in the contract's change process ("does this PR change what any existing column *means*, even if its type and name are unchanged?") that a producing team must explicitly answer, since a machine can't infer a meaning change from a type that didn't move. Some organizations pair this with a required "semantic version" bump (distinct from the schema's compatibility version) specifically for meaning changes, so consumers have something to grep for even when the schema diff is empty.

**The interview tell:** recognizing that "our CI hasn't blocked a breaking schema change in six months" and "our data has been safe from breaking changes for six months" are different claims — schema contracts are necessary but not sufficient, and a strong answer here names the gap (semantics) rather than concluding the process is working because its narrower metric (schema breaks blocked) looks good.

</details>

---

**Next:** [04 — Curveballs & Trade-offs](04_curveballs_tradeoffs.md)
