# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

A question type that doesn't fit a full scenario or a flash-card definition — the interviewer takes whatever you just designed or claimed and pushes on one assumption. There's rarely one "correct" answer here; what's scored is whether you reason through the trade-off out loud instead of freezing or giving a one-word answer. Try answering each before expanding the model answer.

---

**Curveball: "You've convinced me data quality checks matter. Now every single pipeline run has to pass every check before anything downstream can consume the data. What's wrong with that policy?"**

<details>
<summary>Model answer</summary>

Making every check a hard gate treats every dimension and every table as equally critical, which is rarely true. A `critical` completeness failure on a revenue-bearing column should block the pipeline; a `warning`-level validity check flagging 0.3% of rows in a rarely-queried column probably shouldn't halt an entire warehouse's worth of downstream consumers over it. A blanket "everything blocks" policy either gets quietly disabled the first time it blocks something unimportant (undermining trust in the whole system), or it makes the pipeline dramatically less available for a marginal quality gain. The fix is the severity-routing policy from `concepts/05_anomaly_detection_and_monitoring.md`, section 5, applied to validation gating specifically: only `critical`-severity failures on `Tier 1`-style tables actually block; everything else surfaces as a visible, tracked issue that doesn't stop the pipeline. Deciding which checks earn hard-gate status is a judgment call made per table, not a global default.

</details>

---

**Curveball: "Your data contract with an upstream team is working — no breaking changes have shipped in months. The upstream team says the contract is slowing them down too much and wants to drop it. How do you respond?"**

<details>
<summary>Model answer</summary>

Don't just defend the contract on principle — get specific about what's actually slowing them down. If it's the CI check itself being slow or producing false positives (flagging safe changes as breaking), that's a real bug in the enforcement mechanism worth fixing, not a reason to drop the contract. If it's the migration-window requirement for a genuinely breaking change, ask whether the window length matches the actual risk — a 30-day window might be excessive for a low-traffic internal table and appropriate for a finance-facing one. The honest move is treating "the contract is friction" as a signal to calibrate, not a referendum on whether contracts are worth having at all — the same friction that's currently annoying them is exactly what prevented the incident in `01_worked_scenarios.md`, scenario B, and dropping it doesn't remove the underlying risk, it just makes the eventual break silent again.

</details>

---

**Curveball: "This company has no budget for a commercial data catalog tool, and honestly, cataloging 200 tables by hand sounds like it'll never get finished. Is a catalog worth doing at all here?"**

<details>
<summary>Model answer</summary>

A catalog's value doesn't require covering all 200 tables to start paying off — the same tiering logic from `01_worked_scenarios.md`, scenario A applies here. Cataloging the handful of tables that are frequently searched for, or that contain PII (which has a compliance argument independent of general convenience), returns real value almost immediately, while a "catalog everything or it's not worth starting" framing guarantees it never gets built. It's also worth naming that a catalog can start as something far lighter than a commercial tool — a structured metadata table with a name, description, owner, and PII tags per dataset, queryable the way `concepts/04_lineage_and_cataloging.md`'s `DataCatalog` class demonstrates, is enough to answer "does this exist and who owns it" long before a full commercial platform is in budget.

</details>

---

**Curveball: "You've built solid anomaly detection on row counts and null rates. A stakeholder asks: could this have caught last year's incident, where a currency conversion bug quietly overstated revenue by 15% for a month?"**

<details>
<summary>Model answer</summary>

Be honest that the answer is probably no, and explain why precisely: row-count and null-rate monitoring both watch *structural* properties of a table (how many rows, how populated a column is) — a currency conversion bug produces a table with completely normal row counts and completely populated columns, just with subtly wrong *values* in a numeric column. Catching that specific bug needs a different check: a statistical monitor on the numeric column's own distribution (mean/sum drifting outside its historical range, the same z-score machinery from `concepts/02_validation_frameworks.md` applied as an ongoing drift check rather than a one-time outlier scan) or, more directly, a reconciliation check against an independent source of truth (a finance system's own reported revenue). This is a good moment to name the general principle: monitoring has to be built for the specific failure shapes that matter to this business, and "we have anomaly detection" is not automatically "we'd catch any given bug" — it's worth an explicit inventory of what's covered and what isn't, rather than assuming coverage.

</details>

---

**Curveball: "Your lineage graph says table X only feeds one downstream report. You want to deprecate X. How confident should you actually be in that lineage before you delete it?"**

<details>
<summary>Model answer</summary>

Only as confident as the lineage capture mechanism is complete — and that's worth stating as the real caveat, not glossing over. If lineage was captured automatically from an orchestrator's DAG definitions, it's reasonably trustworthy for anything that flows through that orchestrator, but it can miss an ad-hoc query a BI analyst runs directly against X from a notebook, a scheduled export nobody registered as a "pipeline," or a dashboard built against a cached extract rather than a live query. Before deleting anything, I'd combine the lineage graph with a live check — query logs or access logs on X over a meaningful window (at least one full reporting cycle, e.g. a full month-end close) — to catch consumption lineage never recorded. This is the same caution as trusting a monitoring system's coverage in the previous curveball: a system that's correct about everything it tracks can still be silently incomplete, and the fix is verifying the tracking's completeness before trusting its absence-of-evidence as evidence of absence.

</details>

---

**Curveball: "Two teams both want to be the 'owner' of a shared dimension like `dim_customer` for data contract and catalog purposes. How do you resolve that?"**

<details>
<summary>Model answer</summary>

Ownership of a shared, conformed concept has to be singular and centralized, for the same reason a conformed dimension itself has to be built once rather than independently by every team that uses it (data modeling's `interview_questions/04_curveballs_tradeoffs.md`, the bus-matrix curveball) — if both teams can each unilaterally change what `dim_customer` means or looks like, the contract protecting it is meaningless, because "the contract" would actually be two different, occasionally-conflicting contracts. The practical resolution is usually organizational, not technical: one team (often the one closest to the *system of record* the dimension is sourced from, not the one that uses it most) becomes the sole owner in the catalog and the sole approver of contract changes, and the other team becomes a consumer with input rights (they can request a change) but not unilateral edit rights. Naming this as fundamentally a governance/ownership decision rather than something a schema or a tool can resolve on its own is the point being tested.

</details>

---

**Curveball: "Leadership asks for a single 'data quality score' — one number, for the whole warehouse, updated daily, on an exec dashboard. Good idea?"**

<details>
<summary>Model answer</summary>

Push back gently, the same way a strong answer pushes back on "should this have been One Big Table from the start" in data modeling's curveballs — not by refusing, but by naming what a single warehouse-wide number would hide. Averaging a quality score (`concepts/01_data_quality_dimensions.md`, section 3) across 200 tables of wildly different criticality means a severe problem on one Tier 1 finance table can be completely masked by 199 healthy, low-stakes tables — the exact opposite of what leadership actually wants to know about. A better version of the same instinct: a small number of *tiered* scores (Tier 1 tables' aggregate score, prominently, separate from an overall warehouse-health number) gives leadership the "is everything basically fine" signal they're asking for without hiding the one number that would actually justify waking someone up. If leadership specifically wants one number regardless, that's a legitimate ask to fulfill — but flagging the blind spot before building it is the stronger answer.

</details>

---

**Next:** [05 — Responding to a Data Incident](05_incident_response.md)
