# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design conversations. This file is the other interview mode: fast, direct definitional questions with no scenario attached — a phone-screen drill, or a check dropped mid-conversation to confirm you actually understand a term you just used. Answer each one out loud in under 30 seconds before reading the model answer.

Every term used here is demonstrated somewhere in `concepts/` or in file 1 — the cross-references point back to the concrete moment it showed up.

---

## Foundational

**Q: What are the six dimensions of data quality?**
> Completeness (are required fields populated), accuracy (does the value reflect reality), consistency (do related values/tables agree), timeliness (is it fresh enough), uniqueness (are there unwanted duplicates), validity (does it match a format/range/type rule). Full treatment with a check for each: `concepts/01_data_quality_dimensions.md`.

**Q: What's the difference between validity and accuracy?**
> Validity is about shape — does the value match an expected format, type, or range (`state` is 2 uppercase letters). Accuracy is about truth — does the value reflect reality (that state is actually where the customer lives). A value can be perfectly valid and still wrong; validity checks can't catch that on their own. Accuracy is usually only measurable through a domain-rule proxy or reconciliation against an external source of truth, since most pipelines don't have a ground truth on hand.

**Q: What's the 1-10-100 rule?**
> It costs roughly $1 to catch a bad value at the point of entry, $10 to clean it up after it's landed, and $100 to deal with the business impact once a decision has been made on top of it. It's the standard argument for validating early rather than reactively. See `concepts/01_data_quality_dimensions.md`, section 1.

**Q: SLI, SLA, SLO — define each.**
> SLI (Service Level Indicator) is the measured value itself — "completeness is 93% today." SLA (Service Level Agreement) is the promised threshold — "completeness must stay >= 95%." SLO (Service Level Objective) is an internal target, usually stricter than the SLA, that gives a team early warning before an actual SLA breach. Borrowed directly from SRE vocabulary, applied to data instead of uptime.

---

## Checks and Frameworks

**Q: Why can't an exact-match uniqueness check (`GROUP BY` the literal values) catch every duplicate?**
> It only catches rows that are byte-for-byte identical on the grouped columns. It misses near-duplicates — different casing, a trailing space, a typo in one field, two records for the same real-world entity entered independently. Catching those needs fuzzy/similarity-based matching (string similarity over bigrams, edit distance), a structurally different technique — worked as its own problem in `practice/coding_problems.md`.

**Q: What's the Great Expectations pattern, in one sentence per piece?**
> An **Expectation** is a single, named, parameterized check. An **ExpectationSuite** is a named, portable collection of expectations that together define what "healthy" means for one dataset. A **Checkpoint** is the execution engine that runs a suite against real data and reports pass/fail per expectation plus a summary. See `concepts/02_validation_frameworks.md`, section 3.

**Q: Why profile data before writing validation rules?**
> Because a threshold picked without looking at the actual distribution is a guess — profiling (null rate, distinct count, min/max/mean per column) tells you what a real, informed rule should be, and flags which columns need a statistical outlier check versus a simple range rule. Writing `price BETWEEN 0 AND 500` before ever looking at the data risks a rule that's either too loose to catch anything or too tight and full of false positives.

**Q: What's a z-score based outlier check, and what's it good for that a fixed range rule isn't?**
> It flags any value more than N standard deviations from the *current* data's own mean, rather than a hard-coded absolute bound. It self-adjusts as the underlying distribution legitimately shifts, where a fixed range has to be re-guessed by hand every time "normal" changes. See `concepts/02_validation_frameworks.md`, section 4.

**Q: What does schema validation check that value-level checks (completeness, validity) don't?**
> Structure, not content — do the right columns exist, with the right types and nullability. A table can pass every schema check and still be full of nulls and out-of-range values; schema validation is the prerequisite value-level checks depend on, not a substitute for them. See `concepts/02_validation_frameworks.md`, section 5.

---

## Data Contracts and Schema Evolution

**Q: What's a data contract, in one sentence?**
> A formal, published specification of a table's schema, freshness, and quality guarantees — the same idea as an OpenAPI spec for a REST API, applied to a dataset, so consumers build against a documented agreement instead of discovering the table's shape by querying it and hoping nothing changed.

**Q: Give the precise test for whether a schema change is breaking.**
> Can code written against the OLD schema keep working, unmodified, against the NEW one? If yes, it's additive-safe (adding an optional column, widening a type, expanding an allowed-values set). If no, it's breaking (removing a required column, narrowing a type, making an optional column required, shrinking an allowed-values set). See `concepts/03_data_contracts.md`, section 2.

**Q: Backward compatible vs. forward compatible — define both precisely.**
> Backward compatible: code written against the *new* schema can read data written by the *old* schema (safe: additive changes). Forward compatible: code written against the *old* schema can read data written by the *new* schema (safe: removing optional fields old readers never looked at). Backward compatibility is the one that matters almost all the time in practice, because producers usually ship before every consumer has caught up.

**Q: Why does adding a required column with no default count as breaking, even though it's an addition?**
> Because existing writers — code that was writing rows under the old schema — have no way to populate that field, so any row they write under the new schema is instantly invalid. It fails the "can old code keep working" test just as surely as removing a column does; it's the one addition that isn't automatically safe.

**Q: What are the two mechanisms that actually enforce a data contract, and how do they differ?**
> A CI check (run at PR/commit time, comparing a proposed schema against the registered contract, failing the build on a breaking change against policy) and a schema registry (a service a producer must register a new schema version with before writing any data under it, refusing the write if it breaks policy). CI catches problems earliest but can be skipped if a pipeline bypasses it; a registry is the backstop that sits at the actual write path and can't be bypassed, at the cost of catching the problem later. See `concepts/03_data_contracts.md`, section 4.

**Q: Why does registering a breaking contract version get *rejected* rather than *silently versioned*?**
> Because the whole point of a contract is that a breaking change should never happen invisibly. Rejection forces it to become an explicit decision — a real major-version bump, a notification to known consumers, a migration window — rather than something that ships quietly and gets discovered by a downstream team the hard way.

---

## Lineage and Cataloging

**Q: Table-level vs. column-level lineage — why do you ever need the finer one?**
> Table-level lineage answers "which tables feed this one" — cheap to capture, usually inferable from query logs. Column-level lineage answers "which specific source column, through what transformation, produced this column" — necessary whenever one source column fans out into several target columns via different transformations (a `full_name` split into `first_name` and `last_name`), which table-level tracking flattens into a single, imprecise edge. It matters most for precise root-cause work and for GDPR-style "where does this person's data actually end up" questions.

**Q: What is impact analysis, mechanically?**
> A forward (downstream) walk of the lineage graph starting from a dataset that's about to change — every dataset reachable by following "feeds into" edges outward is something that change could affect. It's the operational payoff of maintaining lineage at all: knowing what to check or notify *before* a change ships, not discovering it after something breaks.

**Q: What's the difference between what a data catalog answers and what lineage answers?**
> Lineage answers "how did this data get here, and what does it feed" — a provenance question. A catalog answers "does this dataset exist, what does it mean, who owns it, and am I allowed to use it" — a discoverability and governance question. They're complementary, not the same thing; a catalog entry can exist for a dataset whose lineage was never tracked, and vice versa.

**Q: Why does PII tagging need to happen at the column level, not the table level?**
> Because a table with 20 columns might have exactly one PII column — tagging the whole table `confidential` either over-restricts the other 19 columns or, worse, under-protects the one that actually matters if the table-level tag is the only signal anyone checks. Column-level tagging is also what feeds column-level lineage's erasure-tracing use case: knowing exactly which column downstream is derived from a PII source column.

---

## Anomaly Detection and Monitoring

**Q: What question does anomaly/monitoring detection answer that a one-time validity or completeness check can't?**
> Whether today's data is consistent with how this table *normally behaves over time* — a pipeline can pass every point-in-time check (every value well-formed) and still be silently broken in a way only visible by comparing today's run against recent history (a row count that collapsed, a null rate that crept up). See `concepts/05_anomaly_detection_and_monitoring.md`, section 1.

**Q: Why use a rolling baseline for row-count anomaly detection instead of a fixed threshold?**
> Because "normal" volume genuinely drifts — growth over time, a legitimate weekly cycle. A fixed threshold either goes stale as the table grows or has to be hand-tuned per table forever; a rolling mean/stdev baseline self-adjusts to whatever normal currently looks like for that specific table.

**Q: What failure does a freshness check catch that a row-count anomaly check structurally cannot?**
> "Nothing happened at all" — a silently disabled job, an expired credential failing a job before it ever touches the table. That produces zero runs, not an anomalous run, so there's no row count for an anomaly check to even evaluate against. Freshness measures the gap since the table last actually changed, independent of any run's volume.

**Q: Absolute SLA vs. drift detection on a metric like null rate — what's the difference, and why do you need both?**
> An absolute SLA checks a fixed threshold ("completeness must stay above 95%"); drift detection checks movement from the metric's own recent baseline ("must not move more than N points from normal"), regardless of what that baseline is. A column that's always 40% null (a legitimately optional field) never trips a 95% absolute floor set for a different column, but a jump from 40% to 70% is still a real regression only drift detection catches. Mature monitoring runs both, because they catch different failure shapes.

**Q: How do you avoid a monitoring system that either causes alert fatigue or quietly rots?**
> Assign each check a severity up front and route it accordingly — critical failures page or block the pipeline, lesser ones open a ticket or just log to a dashboard — and revisit those assignments periodically as what's "normal" and "critical" for a table changes. Wiring everything to page causes fatigue (people start ignoring pages); wiring nothing to page, or setting thresholds so loose they never fire, is silent rot (nobody notices until a stakeholder does). See `concepts/05_anomaly_detection_and_monitoring.md`, section 5.

---

**Next:** [03 — Critique & Debug](03_critique_and_debug.md)
