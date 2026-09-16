# Project: Pipeline Designer — Write a Design Doc From a Business Scenario

## Why This Project

Every other project in this course produces code. This one deliberately
doesn't — because the actual deliverable of a senior data engineering
system-design interview is a **design doc**, not a running pipeline. The
skill this project builds is the same one `../interview_questions/` drills
conversationally, but here you produce the written artifact: given a
business scenario and a set of requirements, write a design doc that an
engineer could actually pick up and build from, and that a principal
engineer reviewing it would sign off on without a dozen follow-up
questions.

This mirrors `../../spark_course/projects/01_diagnose_and_fix_capstone.md`'s
shape (a realistic scenario, a task to attempt before looking, a reference
solution) but inverted: that capstone hands you a broken pipeline to
diagnose; this one hands you a blank page and a business need to design
for, which is the harder and more common shape of the actual interview
question.

---

## The Design Doc Template

Every design doc you write for this project should cover six sections. This
is the SPADE framework from `../concepts/01_pipeline_architectures.md`,
plus an explicit capacity/cost section — treat a design doc missing any of
these as incomplete, the same way an interviewer would:

```text
1. SCOPE
   - Functional requirements (what must the system do)
   - Non-functional requirements (latency, availability, compliance)
   - Scale estimates, in real numbers (events/sec, GB/day, retention)
     -- derived with shown arithmetic, per `../concepts/04_capacity_planning_and_cost.md`

2. PIPELINE
   - Data sources (named specifically -- "Postgres via CDC," not "a database")
   - Transformations (what happens to the data, and WHERE -- streaming or batch)
   - Sinks (where it lands, and who/what reads from there)

3. ARCHITECTURE
   - Batch / Streaming / Lambda / Kappa -- named explicitly
   - Justified against THIS scenario's specific requirements, not generic
     trade-offs
   - Specific technology choices per component, each with a one-line "why
     this and not the alternative"

4. DATA MODEL
   - Table/schema shapes (fact/dimension where relevant -- see `../../de_rewamp/data_modeling/`)
   - Partitioning strategy, named and justified
   - Storage format(s)

5. CAPACITY & COST
   - Storage, compute, and network sizing, with the arithmetic shown
   - A named cost trade-off (storage tiering, reserved vs. on-demand,
     or a lever from `../concepts/04_capacity_planning_and_cost.md`)

6. EDGE CASES
   - At least three: pick from failure modes, scaling spikes, late/out-of-
     order data, schema evolution, or a compliance/security requirement
   - Each with a stated mitigation, not just a name
```

A design doc that's strong on Architecture but silent on Edge Cases, or
strong on Data Model but never quantifies Capacity, reads as unfinished —
graders (real interviewers and the self-grading rubric at the end of this
file) look for all six sections being genuinely present, not just the ones
that were easy to write.

---

## Worked Example: Startup Analytics Pipeline

**Scenario:** A 15-person startup wants its first real analytics pipeline.
Data sources: a Postgres application database, an S3 bucket where a
third-party billing provider drops daily CSV exports, and a marketing
team's ad-spend API. Consumers: a small BI dashboard (Looker) and a monthly
board-deck export. Team: 2 data engineers. Budget: low. No compliance
requirements beyond standard data handling.

Below is a complete design doc for this scenario — read it as the model for
what "done" looks like before attempting the two scenarios that follow.

### 1. Scope

**Functional requirements:** ingest application data (users, orders),
billing CSVs, and ad-spend data; support a BI dashboard for weekly
operating metrics; support a monthly board-deck data pull.

**Non-functional requirements:** T+1 freshness is entirely acceptable (no
stakeholder needs same-day data); must run reliably with a 2-person team
and no dedicated on-call rotation; low budget rules out maintaining
multiple always-on compute clusters.

**Scale estimates:** Postgres app DB is small (order of a few GB, a few
thousand new rows/day) — this is nowhere near a volume that requires
distributed processing. Billing CSVs: one file/day, low MBs. Ad-spend API:
a handful of daily-granularity rows per campaign. Total daily new data:
comfortably under 1 GB/day. This number alone rules out needing Spark,
Kafka, or any distributed system at all — naming that explicitly, rather
than defaulting to "big data" tooling out of habit, is the single most
important judgment call in this design.

### 2. Pipeline

- **Sources:** Postgres (application DB), S3 (billing CSV drops), REST API
  (ad-spend).
- **Transformations:** extract Postgres tables (a simple daily full or
  incremental pull — volume is far too low to need CDC), parse and validate
  the billing CSV, pull and normalize the ad-spend API response; join and
  model into a small star schema.
- **Sinks:** a lightweight warehouse (BigQuery or a hosted Postgres — see
  Architecture) feeding the Looker dashboard and a scheduled export for the
  board deck.

### 3. Architecture

**Recommended: Batch.** Every non-functional requirement points here: T+1
is acceptable, the team is 2 engineers with no on-call capacity for a
streaming system's operational overhead, and total daily volume (under 1
GB) doesn't remotely approach a threshold where batch throughput would be a
bottleneck. This is a case where naming the SIMPLEST possible architecture,
explicitly, is the strongest possible answer — reaching for Kafka or Flink
here would be over-engineering relative to every stated constraint.

**Components:**
- **Orchestration:** a single scheduled job (Airflow if the team already
  knows it, or even just a scheduled cron + script for something this
  small — naming the low-budget, low-complexity option as legitimate,
  not a compromise) running once daily.
- **Extraction:** direct Postgres query (a full or incremental pull;
  volume doesn't justify CDC tooling), a simple S3 file-arrival check for
  the CSV, an API client for ad-spend.
- **Transform:** dbt for SQL-based modeling inside the warehouse — cheap,
  well-suited to a 2-engineer team, no separate compute cluster to
  operate.
- **Storage/warehouse:** BigQuery (pay-per-query, no cluster to manage —
  a better fit for a low-budget, low-volume team than a warehouse with
  always-on compute).
- **BI:** Looker (or any BI tool) connected directly to the warehouse.

### 4. Data Model

A small star schema: `fact_orders` (grain: one row per order), `dim_customers`,
`dim_date`, plus a `fact_ad_spend` table (grain: one row per
campaign per day) that's joined to order data only at the reporting layer
(no shared grain, so don't force them into one fact table). Partitioning:
by date, even at this volume — it costs nothing and future-proofs the
table if volume grows. Storage format: whatever the warehouse's native
format is (BigQuery-managed); no separate data-lake layer is justified at
this volume.

### 5. Capacity & Cost

At under 1 GB/day and a few thousand rows, storage and compute cost for this
entire pipeline is negligible — a pay-per-query warehouse (BigQuery) at this
volume likely costs single-digit dollars a month in compute, and storage
cost is immaterial at this scale. The explicit cost lever here isn't a
storage-tiering or reserved-capacity decision (both irrelevant at this
volume) — it's simply "don't provision a dedicated always-on cluster for a
sub-1GB/day workload," which is itself the main cost-saving judgment call
this design makes.

### 6. Edge Cases

- **Billing CSV doesn't arrive on schedule (a real, common failure for a
  third-party file drop):** the daily job should check for file presence
  before running and alert (a simple Slack/email notification is
  proportionate here) rather than silently processing stale or missing
  data.
- **Postgres schema changes** (a column added/renamed by the app team,
  who doesn't necessarily coordinate with the 2-person data team): use a
  schema-on-read staging layer and a lightweight schema-diff check in the
  daily job so a silent breaking change surfaces as a visible failure, not
  a silently wrong report.
- **Team of 2 goes on vacation simultaneously:** the entire pipeline must
  be simple enough (one scheduled job, no bespoke infra) that either
  engineer — or someone entirely outside the data team, in a pinch — can
  restart a failed run from a runbook, without deep tribal knowledge. This
  edge case is really a design constraint stated as a scenario: the low
  team size argues for simplicity everywhere else in this doc, and this is
  where that argument gets stated explicitly as a risk being mitigated.

---

## Your Turn — Scenario A: Real-Time Fintech Platform

Write a full six-section design doc for this scenario before expanding the
reference.

**Scenario:** A fintech company processes card transactions and needs a
data platform serving: real-time fraud/risk dashboards, alerting, a data
warehouse for finance and analytics, and features for an ML fraud model.
Scale: ~500 GB/day, ~50,000 events/sec at peak, sub-second (milliseconds)
latency required for the fraud/alerting path. Retention: 1 year. 200
concurrent analyst/BI queries during business hours. Compliance: SOX and
PCI apply. Budget: high. Team: 8 engineers.

<details>
<summary>Reference design doc (write your own first)</summary>

**1. Scope:** functional requirements span real-time fraud scoring/
alerting, a finance-grade warehouse, and ML feature serving — three
genuinely different consumers of the same underlying event stream.
Non-functional: milliseconds for fraud scoring, PCI/SOX compliance
(meaning audit trails and data handling controls are first-class
requirements, not afterthoughts), 99.99%-class availability implied by
"fintech" even where not stated outright — worth confirming explicitly
rather than assuming. Scale: 50,000 events/sec is the dominant sizing
number (`../concepts/04_capacity_planning_and_cost.md`, section 2's method
applies directly here).

**2. Pipeline:** sources are the transaction-processing system (via Kafka,
likely already event-shaped in a fintech's own architecture), a CDC feed
from an operational Postgres for account/customer data, and an API for
enrichment. Transformations: streaming fraud-rule + model scoring (mirrors
`../interview_questions/01_worked_scenarios.md` Scenario 1 closely — this
IS effectively that scenario, extended with a compliance dimension); batch
ELT into the warehouse for finance; feature computation for the ML model.
Sinks: an alerting service, a warehouse (Snowflake-class, given "high
budget"), a feature store.

**3. Architecture: Lambda**, and justify it explicitly rather than
defaulting to it because the volume is large: the fraud-scoring path needs
millisecond speed; the FINANCE/SOX-auditable numbers need full accuracy and
a complete audit trail that a fast approximate path can't guarantee — this
is a genuine dual-derivation need (same shape as `01_worked_scenarios.md`
Scenario 2's surge pricing), not Lambda reached for by habit. Components:
Kafka (partitioned by account, for the same velocity-check reasons as
Scenario 1), Flink for the speed layer, Spark for the batch/accurate layer,
Airflow orchestrating the batch side, a feature store (Redis online +
Hive/warehouse offline) for the ML path, and — specifically because of
PCI/SOX — an explicit audit-logging component for every access to raw
transaction data, which a lower-compliance design wouldn't need to name as
its own component.

**4. Data model:** `fact_transactions` (grain: one row per transaction,
partitioned by transaction date), `dim_customers` (SCD Type 2 — account risk
tier changing over time needs history for audit purposes, tying directly
into `../../de_rewamp/data_modeling/`'s SCD reasoning), a `feature_store`
table keyed by customer/account for the ML path. PCI compliance implies
card-number-adjacent fields are tokenized/masked at the earliest possible
stage (ingestion), not handled as raw values anywhere downstream — call
this out explicitly as a data model decision, not just an infra one.

**5. Capacity & cost:** at 50,000 events/sec, per
`../concepts/04_capacity_planning_and_cost.md` section 2's method, that's
roughly 5 Flink TaskManagers at the stated per-unit throughput heuristic,
and enough Kafka partitions to comfortably exceed that consumer
parallelism. Lambda's cost is explicitly the most expensive shape in the
decision matrix — name that trade-off directly: "high budget" in the
scenario is precisely why Lambda is affordable here in a way it wasn't in
Scenario 1's read of a lower-budget assumption. 200 concurrent analysts
argues for a separate ETL vs. BI warehouse split (Concept 4, section 3) so
heavy nightly loads don't contend with daytime analyst query load.

**6. Edge cases:** model-scoring service degradation (async-with-timeout,
identical reasoning to `01_worked_scenarios.md` Scenario 1); SOX/PCI audit
requirement that EVERY access to raw card data be logged immutably — a
genuinely new edge case this scenario's compliance requirement introduces
that the fraud-dashboard scenario in file 1 didn't have to handle; a team of
8 is enough to sustain Lambda's two-codepath operational cost (contrast
directly with `04_curveballs_tradeoffs.md`'s "team shrinks to 2" curveball,
where the SAME architecture would need to be reconsidered).

</details>

---

## Your Turn — Scenario B: Media Streaming Content Analytics

Write a full six-section design doc for this scenario before expanding the
reference.

**Scenario:** A video streaming service (think a mid-size competitor to a
major platform) wants a platform that: (1) tracks what's being watched, for
how long, and where viewers drop off, to feed content-investment decisions;
(2) powers a "trending now" row on the homepage that should reflect the
last hour of viewing activity; (3) feeds a nightly-retrained
recommendation model. Scale: 20 million daily active viewers, ~200,000
playback events/sec at peak (play, pause, seek, drop-off events), catalog
of 50,000 titles. Retention: 2 years of viewing history for content
strategy analysis. Budget: medium. Team: 6 engineers.

<details>
<summary>Reference design doc (write your own first)</summary>

**1. Scope:** three consumers with three different latency needs on the
SAME underlying event stream: content-investment analytics (batch is
entirely fine — decisions get made on a weekly/monthly cadence), "trending
now" (needs to reflect roughly the last hour — NOT sub-second; worth
explicitly noting this is a much looser latency bar than
`01_worked_scenarios.md`'s scenarios, which changes the architecture
conclusion), and nightly model retraining (batch, by definition). Scale:
200,000 events/sec at peak is the dominant sizing number.

**2. Pipeline:** sources are playback-event beacons from client apps
(mobile, TV, web), a content-catalog CDC feed, and a subscriber/billing CDC
feed. Transformations: streaming aggregation for the trending-now signal
(hourly-windowed rather than sub-minute — a deliberately looser window
given the actual requirement); batch ETL for the 2-year content-analytics
warehouse; batch feature engineering for nightly recommendation retraining.
Sinks: a serving cache for the homepage's trending row, a warehouse for
content-strategy analysts, a feature store/training dataset for the ML
team.

**3. Architecture: Kappa-leaning hybrid, explicitly NOT Lambda.** This is
the key architectural judgment call in this scenario, and the one most
candidates get wrong by defaulting to Lambda because the volume is large:
there's no genuine SECOND, differently-derived computation needed here the
way Scenario A's fraud path needed both a fast AND an audited number for
the SAME metric. "Trending now" (streaming, hourly-windowed) and "2-year
content analytics" (batch) are different QUESTIONS over the same raw
events, not two competing answers to the same question — much closer to
Scenario 3 (IoT telemetry)'s reasoning than to the fintech scenario's.
Components: Kafka (partitioned by a hash of title/content ID, since
per-title aggregation is the dominant access pattern for both trending and
analytics), a stream processor for the hourly trending aggregation, Spark
+ Airflow for the nightly batch warehouse load and recommendation feature
engineering, a serving cache (Redis) for the trending row specifically
(homepage read latency matters even though the underlying computation's
freshness bar is loose).

**4. Data model:** `fact_playback_events` (grain: one row per meaningful
playback event — play/pause/seek/drop-off — partitioned by event date,
2-year retention), `dim_titles`, `dim_subscribers`. A separate
`agg_trending_hourly` table (or a Redis structure, not a warehouse table at
all, given it's a serving concern) holds the hourly trending computation —
deliberately NOT the same table as the 2-year fact table, since their
access patterns and retention needs are entirely different (this is the
"materialized view / pre-aggregation" pattern from
`../concepts/03_optimization_techniques.md`, section 3, applied at the
architecture level).

**5. Capacity & cost:** at 200,000 events/sec, storage sizing follows
Concept 4's method directly; 2 years of retention at this event volume is
a meaningful storage cost, making storage TIERING a real, applicable lever
here specifically (unlike Scenario A's 1-year retention, or the worked
example's negligible volume) — recent months stay in a standard tier for
active content-strategy queries, older data moves to a cheaper tier since
"content performance from 18 months ago" is queried far less frequently
than last month's. Medium budget and a 6-person team argue against Lambda's
cost even though volume alone might tempt a candidate toward it — naming
that volume is NOT the deciding factor for architecture choice, need for a
genuine second derivation is, reinforces the same lesson Scenario A's high
budget/Lambda pairing teaches from the other direction.

**6. Edge cases:** a title going unexpectedly viral (a real "hot key" —
one title suddenly dominating playback-event volume, the same shape of
problem as `../concepts/03_optimization_techniques.md` section 5's data
skew, here applied to a streaming partition key rather than a Spark
shuffle key — mitigation: monitor per-key partition load and be ready to
salt that specific title's key temporarily); client apps sending
malformed or duplicate playback events under poor network conditions
(mobile/TV apps buffering and resending — needs idempotent event IDs and
dedup, the same mechanism discussed in `04_curveballs_tradeoffs.md`'s
exactly-once curveball); recommendation model retraining pipeline failing
silently on stale data (a genuine data-quality monitoring gap, the same
shape as `03_critique_and_debug.md` Case 5 — the retraining job succeeding
"on time" doesn't mean the training data was actually fresh/correct).

</details>

---

## Self-Grading Rubric

Score your own design doc (or a peer's) against these, honestly, before
comparing to the reference:

```text
[ ] Scope states scale as NUMBERS (events/sec, GB/day), not adjectives
    ("a lot of data")
[ ] Architecture choice is justified against THIS scenario's specific
    requirements, not the generic decision-matrix trade-offs recited
    without connecting them to the scenario
[ ] Every named technology has a one-line "why this, not the alternative"
[ ] Data model states the grain of every fact table explicitly
[ ] Capacity & Cost section shows arithmetic, not just conclusions
[ ] At least three edge cases, each with a stated mitigation — not just
    named and left hanging
[ ] The doc would let a different engineer start building without
    needing to ask you what you meant
```

A design doc that would pass all seven checks is doing the actual job this
whole topic folder is training for.
