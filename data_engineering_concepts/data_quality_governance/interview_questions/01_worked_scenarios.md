# 1. Worked Design Scenarios

Part of the [Interview Questions](README.md) series — see that index for the full taxonomy of question types and how the files fit together.

Like `etl_elt_patterns`'s version of this file, this one isn't fully code-free — a short SQL snippet or Python sketch shows up wherever it's the fastest way to make a design decision concrete. The point being scored is still the reasoning: how you scope an open-ended governance problem, prioritize under real constraints, and defend your design against the follow-up — not the syntax.

Three full scenarios are worked below, each with clarifying questions → design → narrated trade-offs, and two carry a "Now You Try" companion (hidden debrief). Read all three straight through once, including every debrief, then use the two companions to run the same process yourself before expanding the answer.

---

## A. Building a Data Quality Framework From Zero

**Interviewer prompt:**
> "You've just joined a company with roughly 200 tables in its warehouse and effectively no data quality checks anywhere. Where do you start?"

### Step 1 — Clarifying questions before proposing anything

- **What's actually driving this?** A recent incident (a bad number reached an executive dashboard), a compliance requirement (PII governance), or just general hygiene? → Interviewer says: a bad revenue number reached finance last quarter, and leadership wants it to stop happening.
- **Is there any existing tooling** (an orchestrator, a warehouse with row-level `PRAGMA`-style introspection, an existing catalog)? → Airflow orchestrates everything; no catalog, no quality tooling at all today.
- **Team size and time budget?** → Two data engineers, expected to show meaningful progress in a quarter, not solve all 200 tables.

Asking "what's driving this" first is the single highest-leverage question in the whole scenario — an incident-driven mandate and a compliance-driven mandate lead to genuinely different priority orders, and starting there instead of jumping to "here's my six-dimension framework" is what signals a strong answer.

### Step 2 — Refuse to boil the ocean: tier the tables first

> "200 tables with zero checks is not a 'write 200 tables' worth of checks' problem on day one — it's a prioritization problem first. I'd tier tables by business criticality: does it feed an executive-facing report, a customer-facing feature, or a regulatory filing (Tier 1); does it feed an internal analytics dashboard (Tier 2); or is it exploratory/rarely queried (Tier 3). Given the stated incident was a revenue number, Tier 1 starts with anything upstream of finance-facing reporting — traced with the lineage techniques from `concepts/04_lineage_and_cataloging.md` if any lineage exists yet, or by asking the finance team directly if it doesn't."

```text
Tier 1 (start here): tables feeding exec dashboards, finance, compliance filings
Tier 2 (next):        tables feeding internal analytics / self-service BI
Tier 3 (later):       exploratory / low-traffic tables
```

### Step 3 — For Tier 1 tables, implement checks across the dimensions that matter most for THIS incident

> "For each Tier 1 table, I'd implement completeness and validity checks on the columns finance actually sums or filters on, a consistency check reconciling the table's key totals against whatever finance's own source of truth is, and a schema-validation check so a silent structural change doesn't slip through unnoticed — the same dimension checks from `concepts/01_data_quality_dimensions.md`, scoped specifically to the columns that caused last quarter's incident, not applied uniformly and generically everywhere on day one."

### Step 4 — Wire checks into the pipeline with a real severity policy, not a firehose of alerts

> "Each check gets a severity: a Tier 1 table's completeness or reconciliation check failing is `critical` and blocks the pipeline / pages someone; a Tier 2 validity check failing is a `warning` that shows up on a dashboard. Getting this policy wrong in either direction — paging on everything, or wiring nothing to actually page — is exactly the alert-fatigue-vs-silent-rot trade-off from `concepts/05_anomaly_detection_and_monitoring.md`, and it's worth naming explicitly rather than assuming 'more alerts is safer.'"

### Step 5 — Only after Tier 1 is stable, introduce contracts at the team boundaries that broke it

> "Once Tier 1 has real checks, I'd look at *why* last quarter's number was wrong specifically — if it traces back to an upstream team changing a schema without warning, that's exactly the case for a data contract (`concepts/03_data_contracts.md`) between that producing team and the pipeline, enforced in CI. I would not try to roll out contracts to all 200 tables' producers at once — that's a much bigger organizational lift than a quarter allows, and it should follow evidence of where it's actually needed, not lead the effort."

### Step 6 — Trade-off, stated unprompted

> "The honest limitation of this plan: 190 of 200 tables still have zero checks at the end of the quarter. That's the right trade-off given a two-person team and an incident-driven mandate — depth on the tables that actually caused the problem, rather than a thin, uniform layer of checks across everything that would take far longer to build and wouldn't have caught last quarter's specific incident any faster. I'd frame the plan explicitly as 'Tier 1 this quarter, Tier 2 next' so leadership isn't expecting all 200 tables covered on the same timeline."

---

### Now You Try: Absorbing 50 Tables From an Acquired Company

**Interviewer prompt:**
> "Your company just acquired a smaller one. Their warehouse — 50 tables — needs to be integrated into yours, and their data quality conventions (what little exists) don't match yours at all."

**Work through:** how this differs from the from-zero scenario above, what you'd check before writing a single integration query, and how you'd decide whether to conform their tables to your conventions or leave them as-is.

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **How it differs:** this isn't "no checks exist," it's "checks exist, defined differently" — the acquired company's `customer_status` might use different allowed values than yours, their `dim_customer`-equivalent might use natural keys where yours uses surrogates, and their idea of "active" might not match yours at all. This is a **conformed-dimension-at-organizational-scale** problem before it's a data-quality problem — the same reasoning as the conformed-dimension curveball in data modeling's `interview_questions/04_curveballs_tradeoffs.md`, just triggered by an acquisition instead of two internal teams.
- **What to check before writing any integration query:** profile every acquired table first (`concepts/02_validation_frameworks.md`, section 2) — null rates, distinct-value sets for anything that looks like an enum, actual date ranges — rather than trusting their documentation (which, if quality conventions were thin, is probably also thin or stale).
- **Conform or leave as-is:** conform anything that needs to join against or be unioned with your existing tables (shared customer/product concepts) — that requires an explicit identity-resolution and value-mapping step (their `"active"` maps to your `1`, their customer IDs need a crosswalk table), not a silent assumption they mean the same thing. Leave alone anything that's genuinely standalone and won't be joined against your existing model — forcing a conformance effort onto data nobody will ever combine with anything else is wasted work.
- **The tell:** recognizing this as fundamentally a *semantic mapping* problem (do their values and yours mean the same real-world thing) rather than a *technical* one (can the tables physically be copied over) is what separates a strong answer here — the SQL to move the data is the easy part.

</details>

---

## B. "This Dashboard Number Is Wrong" — Walking the Investigation

**Interviewer prompt:**
> "A VP tells you the 'monthly active users' number on the executive dashboard looks wrong — it dropped 30% overnight with no explanation. Walk me through how you'd investigate, out loud."

### Step 1 — Clarifying questions, asked before touching any table

- **Wrong compared to what?** Compared to their own memory of the trend, or against a second source (a separate marketing tool reporting a similar metric)? → Interviewer says: it dropped sharply between yesterday and today, with nothing else in the business changing.
- **Did the underlying pipeline actually run, and report success?** → Yes, the job completed with no errors — this rules out "the job crashed and nobody noticed" as the very first hypothesis and pushes the investigation toward "it ran, but produced a wrong result."

### Step 2 — Use lineage to walk backward from the dashboard, not forward from a guess

> "Rather than guessing which upstream table is at fault, I'd use lineage (`concepts/04_lineage_and_cataloging.md`) to walk backward from the dashboard's source table through every transformation that feeds it — a mart, a staging table, the raw source — and check each hop in order, closest to the dashboard first, since that's usually the fastest way to localize a regression that just appeared."

```text
report.executive_dashboard <- mart.daily_active_users <- staging.events <- raw.clickstream
     check here first             then here                then here         then here
```

### Step 3 — At each hop, run the checks that would catch "ran but wrong"

> "At each hop, I'm checking: did the row count for today look anomalous relative to its own recent history (`concepts/05`, row-count anomaly detection) — a silent drop in raw event volume would explain a 30% MAU drop directly. If row counts look normal at every hop, I'd check for a schema change around the time the drop started — a column that got renamed, retyped, or had its semantics quietly changed by an upstream team, exactly the kind of change a data contract's CI check should have caught before it shipped (`concepts/03_data_contracts.md`)."

### Step 4 — Narrate finding the actual root cause

> "Say the trail leads here: `raw.clickstream` row counts look completely normal, but a new deploy from the mobile team yesterday renamed an event field from `user_id` to `userId` without renaming it in the contract — `staging.events`'s transformation step was silently matching on the old field name, getting nulls, and the null-safe join used everywhere downstream was quietly excluding every event with no resolved user, collapsing the active-user count. This is exactly the schema-evolution failure mode from `concepts/03_data_contracts.md` — a rename is neither a clean addition nor a clean removal, and it slipped through because there was no contract enforcing the mobile team's event schema in the first place."

### Step 5 — Fix, and decide whether history needs correcting

> "The immediate fix is restoring the join to handle both field names during a transition window (or getting the mobile team to revert / alias the field), then backfilling the one day of `mart.daily_active_users` that was computed wrong once the real join is restored. Whether to *silently* correct that one day or publish it with a visible annotation is a stakeholder communication call, not just a technical one — the VP who noticed the drop should be told what happened and that the historical number is being corrected, not have it quietly change under them."

### Step 6 — Close with the systemic fix, not just today's fix

> "The unprompted addition that separates a good answer from a great one here: fixing today's number doesn't prevent this exact failure from recurring the next time an upstream team renames a field. I'd propose two things leadership can act on — a data contract with the mobile team's event schema (`concepts/03_data_contracts.md`), enforced in their CI, and a null-rate drift check on the join key specifically (`concepts/05_anomaly_detection_and_monitoring.md`) so a silently-broken join trips an alert automatically instead of waiting for a VP to notice a dashboard looks off."

---

### Now You Try: Two Dashboards Disagree With Each Other

**Interviewer prompt:**
> "Slightly different version of the same complaint: two different teams' dashboards both claim to show 'total active customers,' and they disagree by about 8%. Neither number changed suddenly — they've just always quietly disagreed. How do you investigate this one?"

**Work through:** how this differs from a sudden-drop investigation, where you'd actually look first, and what the likely root cause category is versus scenario B above.

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **How it differs:** scenario B is a *regression* (something changed) — lineage plus anomaly detection localizes it in time. This one is a *steady-state disagreement* with no trigger event, which means anomaly detection (which compares today to yesterday) won't find anything, because nothing changed recently on either side. The investigation has to start from definitions, not from a timeline.
- **Where to look first:** get the exact query or transformation logic behind each team's "active customer" definition, not just the number. This is very likely two independently-built definitions of "active" (different lookback windows, different inclusion of trial vs. paying accounts, different handling of a customer with a paused subscription) rather than a bug in either pipeline.
- **Likely root cause category:** this is the OBT/conformed-dimension disagreement failure mode named in data modeling's `interview_questions/03_critique_and_debug.md`, Case 8 — two teams each built their own version of a shared concept instead of referencing one centrally-defined, governed dimension. It's a governance gap, not a data quality bug in the traditional sense — nothing here is technically "wrong" in either pipeline; they're both internally consistent and simply answering slightly different questions under the same label.
- **The tell:** resisting the urge to "fix" either pipeline before both teams agree on one shared definition — the actual deliverable here is a governed definition of "active customer," centrally owned and referenced by both, not a patch to make one number match the other by coincidence.

</details>

---

## C. Designing a Schema Contract Process With an Upstream Product Team

**Interviewer prompt:**
> "The mobile product team keeps changing their event schema without telling anyone, and it keeps breaking your pipeline. Design a process that stops this."

### Step 1 — Clarifying questions

- **How do changes reach the pipeline today?** → The product team merges to their own repo and deploys; the data team finds out when something breaks downstream, sometimes days later.
- **Does the product team currently see themselves as having any obligation to the data team at all?** → Honestly, not really — this is as much an incentives problem as a technical one, worth naming out loud rather than pretending it's purely a tooling gap.
- **Is there any existing schema registry or CI gate on either side?** → No.

### Step 2 — Define the contract's content, jointly, not unilaterally

> "The contract (`concepts/03_data_contracts.md`) needs to specify the event schema (columns, types, required/optional, allowed values), a compatibility policy (backward, almost always, given that the data team's pipeline can't redeploy in lockstep with every mobile release), and a change-notification channel. Critically, I'd draft this *with* the product team, not hand it to them — a contract that shows up as a mandate from the data team, with no input from the people who have to live inside it, gets treated as red tape to route around rather than a shared tool."

### Step 3 — Make the enforcement mechanism cheap for the producer, not just safe for the consumer

> "The enforcement point is a CI check on the product team's own PRs — `SchemaEvolution.compare_schemas` run against the currently-registered contract version, failing the build only on a genuinely breaking change (removing a required field, narrowing a type, shrinking an allowed-values set), not on every change. This is the detail that makes or breaks adoption: if the check is noisy — flagging safe, additive changes as failures — the product team will get an exemption or disable it within a month. It has to be precise enough that a failure means something real."

```text
Mobile team's PR -> CI runs SchemaEvolution.compare_schemas(registered_contract, proposed_schema)
                 -> additive-safe change: PR proceeds, contract version bumped automatically
                 -> breaking change: PR blocked, must be paired with a version bump +
                                     notification to the data team's channel + migration window
```

### Step 4 — Handle the case where a breaking change is genuinely necessary

> "A contract can't just say 'no breaking changes ever' — sometimes the product team genuinely needs to rename or remove a field. The process needs an explicit path for that: a major version bump, a defined migration window (say, 30 days) where both the old and new field are populated side by side, and a notification that actually reaches the data team, not just a Slack message that scrolls past. This is the same registry-rejection-then-explicit-decision pattern from `concepts/03_data_contracts.md`, section 5 — breaking changes aren't forbidden, they're forced to become visible and deliberate instead of silent."

### Step 5 — Trade-off, stated unprompted

> "This process adds real friction to the mobile team's release process — a CI check that can block their merge, a migration window that delays how fast they can fully retire an old field. That friction is the entire point, not a regrettable side effect: it's trading a small, visible cost today (a CI check, a documented migration) for avoiding a large, invisible cost later (a silent break that costs an incident, a VP's trust, and hours of the data team's time tracing it down, exactly as in Scenario B). I'd frame the pitch to the product team in those terms — this protects them from being the team that broke finance's dashboard, not just protects the data team's pipeline."

---

**Next:** [02 — Rapid-Fire Q&A](02_rapid_fire_qna.md)
