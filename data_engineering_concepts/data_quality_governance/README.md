# Data Quality & Governance

## Why This Matters

Bad data is worse than no data — a pipeline that fails loudly gets fixed; a pipeline that succeeds while silently producing wrong numbers erodes trust in every dashboard and every decision built on top of it, often for weeks before anyone notices. Every data engineering interview loop eventually asks some version of "how do you know your data is actually correct" or "how do you know your pipeline didn't silently break" — and the follow-ups (what happens when a stakeholder tells you a number is wrong, how do you stop an upstream team from breaking your pipeline every quarter) are where the reasoning actually gets tested, not just the vocabulary.

This topic is deliberately about **detecting and governing bad data**, not about pipeline reliability mechanics — idempotent loads, retries, exactly-once semantics, and checkpointing live in `etl_elt_patterns/concepts/06_idempotency_reliability.md`. The two topics are complementary and cross-linked throughout rather than overlapping: a pipeline can be perfectly idempotent and reliable while still loading data that's wrong, late, or silently drifting — that gap is what this folder covers.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like notes, with prose explaining the "why," an ASCII diagram where one clarifies the mechanism, and real, runnable Python + `sqlite3` code (no external dependencies, no warehouse account needed) showing the pattern and its actual output.
- `practice/` — `exercises.md` (12 build-it-yourself drills with the answer hidden behind `<details>`) and `coding_problems.md` (4 harder problems — a full quality monitoring engine with alerting and scoring, a schema contract enforcer with version history, a lineage impact analyzer, and a multi-metric anomaly detection engine — each with a problem statement, sample input/output, and a hidden reference solution with an explanation of the pattern it tests).
- `interview_questions/` — a five-file, mostly-code-free drill covering every shape a data quality interview question tends to take: worked design/investigation scenarios, rapid-fire definitions, critique-a-broken-check, curveball trade-offs, and a dedicated drill on responding to a live data incident. See `interview_questions/README.md` for the full breakdown.
- `projects/` — one capstone project brief (`quality_checker.md`) that forces you to implement a reusable, rule-based quality checker with dimension scoring and contract validation, not just recognize the individual checks.

Every `concepts/*.md` file follows the same shape: a **Covers** list, one `##`/`###` section per sub-topic with a prose "why," an ASCII diagram where one helps, real runnable code, and a worked example with its actual output shown in a comment. Every code block is copy-pasteable stdlib Python + `sqlite3` — paste it into a `python3` shell and it runs exactly as shown.

---

## How to Use This Folder

Work through it in this order:

1. **`concepts/`** (01 → 05) — the implementation vocabulary: the six dimensions of data quality, how a validation framework is actually structured, what makes a schema change breaking, what lineage and cataloging are for, and how ongoing monitoring differs from one-time validation. Read these first; everything else assumes this vocabulary.
2. **`practice/exercises.md`**, then **`practice/coding_problems.md`** — apply the vocabulary directly: write a completeness check, build a mini expectation suite, classify a schema change, walk a lineage graph, and build a full monitoring engine with alerting and scoring. Commit to your own answer before expanding each hidden solution.
3. **`interview_questions/`** — the conversation an interviewer actually scores, rehearsed end to end: clarifying questions → design/investigation → narrated trade-offs, across realistic scenarios, plus rapid-fire definitions, critique-the-broken-check cases, curveball follow-ups, and a dedicated drill on what to actually do when something's already wrong in production.
4. **`projects/quality_checker.md`** — a capstone that asks you to build a small, reusable quality-checking tool with dimension scoring and contract validation as general-purpose code, not one-off examples.

---

## Topics Covered

### Concepts

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Data Quality Dimensions | `concepts/01_data_quality_dimensions.md` | "What are the dimensions of data quality?" / "How do you measure whether a table is trustworthy?" |
| 2 | Validation Frameworks | `concepts/02_validation_frameworks.md` | "How would you build a Great Expectations-style validation suite?" / "What's the difference between validating one row and validating a dataset?" |
| 3 | Data Contracts | `concepts/03_data_contracts.md` | "What's a data contract, and how do you stop a schema change from silently breaking downstream consumers?" |
| 4 | Lineage & Cataloging | `concepts/04_lineage_and_cataloging.md` | "How do you track where data comes from, and what breaks if this column changes?" |
| 5 | Anomaly Detection & Statistical Monitoring | `concepts/05_anomaly_detection_and_monitoring.md` | "How do you know your pipeline silently broke, even though the job reported success?" |

### Interview Questions

`interview_questions/` is a five-file drill:

1. [Worked Design Scenarios](interview_questions/01_worked_scenarios.md) — full walkthroughs: building a data quality framework from zero across 200 tables, investigating a stakeholder's "this dashboard number is wrong," and designing a schema contract process with an upstream product team — each with clarifying questions, a narrated design, and a stated trade-off
2. [Rapid-Fire Q&A](interview_questions/02_rapid_fire_qna.md) — fast definitional questions, no scenario attached
3. [Critique & Debug](interview_questions/03_critique_and_debug.md) — classic data quality bugs: a completeness check that silently ran on a `LIMIT`ed sample, a duplicate check that missed every fuzzy near-duplicate, a schema change that passed CI but broke a downstream report anyway, an anomaly threshold so loose it never fires, and a contract that enforced schema but missed a semantic meaning change
4. [Curveballs & Trade-offs](interview_questions/04_curveballs_tradeoffs.md) — mid-conversation follow-ups: hard-gating every check, contract friction pushback, catalog ROI without budget, monitoring coverage gaps, shared-dimension ownership, a single warehouse-wide quality score
5. [Responding to a Data Incident](interview_questions/05_incident_response.md) — a dedicated drill on the question every other file assumes you'd prevented: something is already wrong in production right now — triage, containment, root-cause search, the backfill decision, stakeholder communication, and a postmortem that actually leads to a fix

See `interview_questions/README.md` for how to use the set.

---

## Key Mental Models

### 1. The Six Dimensions

```
Completeness:   Are all required fields present?
Accuracy:       Do values match reality?
Consistency:    Do related datasets/values agree?
Timeliness:     Is data fresh enough?
Uniqueness:     Are there duplicates?
Validity:       Do values match expected formats/ranges?
```

### 2. Point-in-Time Checks vs. Ongoing Monitoring

```
Point-in-time (concepts 01, 02):  is TODAY's data internally well-formed?
Ongoing monitoring (concepts 05): is TODAY's data consistent with how this
                                   table normally behaves over TIME?

A pipeline can pass every point-in-time check and still be silently broken --
that gap is exactly why monitoring is a distinct topic, not a subset of validation.
```

### 3. The Precise Test for a Breaking Schema Change

```
Can code written against the OLD schema keep working, unmodified,
against the NEW one?

  Yes -> non-breaking (add an optional column, widen a type, expand allowed values)
  No  -> breaking (remove a required column, narrow a type, shrink allowed values,
                    add a required column with no default)
```

### 4. Data Contracts = APIs for Data

```
Producer promises:
  - Schema (columns, types, nullable)
  - Freshness (updated by 6 AM daily)
  - Quality (< 1% null rate on key fields)

Consumer expects:
  - Stable schema (no breaking changes without a version bump + notice)
  - Consistent quality
  - Documented semantics -- NOT just structure (concepts/03, and
    interview_questions/03_critique_and_debug.md, Case 5)
```

### 5. Lineage Answers "Where," a Catalog Answers "What" and "Who"

```
Source API -> Raw Layer -> Staging -> Transformations -> Mart -> Dashboard
     ^                                                              ^
  "Where did this data come from?"          "What feeds this dashboard?"
  (lineage)                                  (lineage -- impact analysis)

"Does this dataset exist, what does it mean, who owns it, can I use it?"
  (catalog -- a different question lineage alone doesn't answer)
```

---

## Practice Goals

- [ ] Implement a check for all six data quality dimensions against a real SQLite table
- [ ] Build a mini Great Expectations-style expectation suite and run it as a checkpoint
- [ ] Classify a schema change as breaking or non-breaking, and explain backward vs. forward compatibility precisely
- [ ] Build a lineage graph and correctly answer an upstream ("root cause") and a downstream ("impact analysis") query against it, including a diamond dependency
- [ ] Design a rolling-baseline anomaly check (row count or null rate) and explain why a fixed threshold isn't the same thing
- [ ] Run a full "design a data quality framework" or "investigate this wrong number" conversation end to end, narrating the reasoning without writing full code
- [ ] Walk through what you'd actually do in the first five minutes of a live data incident, not just how you'd have prevented it

---

## Prerequisites

None required. Every concept file is self-contained Markdown with runnable Python + `sqlite3` code blocks — no warehouse, no orchestrator, no external service required. `data_modeling` and `etl_elt_patterns` are helpful but not required: a few worked scenarios reference star-schema/conformed-dimension concepts from the former, and a few cross-references point to idempotency/reliability mechanics in the latter — `etl_elt_patterns/concepts/06_idempotency_reliability.md` in particular is worth reading alongside this folder's monitoring concept, since the two topics are complementary (reliable delivery vs. correct content) rather than overlapping. Any `python3` with the standard-library `sqlite3` module is enough to run every example in this folder yourself.
