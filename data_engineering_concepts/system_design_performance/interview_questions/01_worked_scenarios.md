# 1. Worked Scenarios: Full Mock System Design Interviews

Part of the [Interview Questions](README.md) series — see that index for the
full taxonomy.

This section is the heart of the flagship topic. Three scenarios are worked
in full, interviewer-simulation format: clarifying questions asked and WHY,
the architecture reasoning, a narrated walkthrough of how data actually
flows, and how the design scales and fails. A fourth scenario is yours to run
yourself before checking the debrief.

Read scenario 1 straight through once as the model. Then treat 2 and 3 the
same way. Then do 4 yourself, out loud, before expanding the debrief.

---

## Scenario 1: Real-Time Fraud Detection Dashboard

**Interviewer prompt:**
> "Design a data pipeline that powers a real-time fraud detection dashboard
> for a payments company. Analysts and risk officers need to see suspicious
> transaction patterns as they emerge, and the system should be able to
> automatically flag (not necessarily block) transactions that match known
> fraud patterns."

### Step 1 — Clarifying questions, and why each one matters

A candidate who starts naming Kafka and Flink before asking anything is
optimizing for looking busy over looking right. The questions ARE the signal:

- **Is this "flag for review" or "block the transaction"?** → Interviewer
  says: flag for review; blocking is a separate system (the payment
  authorization path) this pipeline feeds signals into but doesn't own. →
  This matters enormously: a pipeline that only has to flag within seconds
  has very different latency pressure than one that must block within the
  authorization window (typically under 200ms) — conflating the two leads to
  over-building for a constraint that doesn't actually apply here.
- **What counts as "real-time" — seconds? sub-second?** → Interviewer says:
  dashboard should reflect a flagged transaction within 10 seconds. → Rules
  out a naive batch approach; doesn't require the sub-100ms latency of an
  in-line blocking system.
- **Where do the fraud rules/models come from — a fixed rule set, or a model
  that gets retrained?** → Interviewer says: both — a fast rule engine
  (velocity checks, known-bad-actor lists) for immediate flags, PLUS an ML
  model retrained periodically on labeled fraud outcomes. → Signals a hybrid
  design: rules evaluated inline in the stream, model-based scoring as a
  slightly heavier step that can tolerate a little more latency.
- **Scale?** → Interviewer says: ~2,000 transactions/sec sustained, spiking to
  10x during known high-traffic windows (holidays). → Confirms this needs a
  horizontally-scalable streaming layer, not a single-node processor, and
  that the design must explicitly handle a 10x spike, not just steady state.
- **What happens to a transaction the model can't score in time (feature
  store lookup times out, model service is slow)?** → Interviewer says: it
  should still show up on the dashboard, just unscored, rather than being
  dropped. → Rules out any design where a slow dependency can silently lose
  a transaction.
- **Retention — how far back does "real-time dashboard" history need to go
  vs. long-term fraud investigation/audit?** → Interviewer says: dashboard
  shows a rolling 24 hours; full history retained for 7 years for investigation
  and regulatory purposes. → Confirms a two-tier storage design (hot recent
  window + cold long-term archive), not one retention policy for everything.

### Step 2 — State the requirements back, quantified

> "So: ~2,000 TPS sustained, 20,000 TPS at peak. Flag latency target is 10
> seconds end to end. Two scoring paths — a fast rule engine and a
> periodically-retrained ML model. Never drop a transaction, even if scoring
> fails. Dashboard shows a rolling 24 hours; everything is retained 7 years
> for investigation."

Stating this back, with the numbers, before drawing anything is exactly the
capacity-planning discipline from `../concepts/04_capacity_planning_and_cost.md`
— it also gives the interviewer a chance to correct a misunderstanding before
you've built an architecture on top of it.

### Step 3 — Architecture, with the diagram drawn before the details

> "This is a streaming architecture, not Lambda — I don't need a separately
> maintained 'batch view' of the SAME fraud-scoring logic; I need one
> continuously-running scoring path, plus a completely separate (and much
> simpler) batch job that periodically retrains the model on labeled
> outcomes. That's not two codepaths for the same computation — it's one
> streaming path and one unrelated batch job, so this doesn't have Lambda's
> drift problem."

```
Payment Service --> Kafka (txn_events, partitioned by account_id)
                        |
                        v
              +-------------------+
              | Stream Processor  |  (Flink)
              |  - rule engine    |  <-- fast, inline, sub-second
              |  - feature lookup |  <-- from a low-latency feature store
              |  - model scoring  |  <-- async call, times out gracefully
              +-------------------+
                    |         |
                    v         v
          Flagged-txn topic   Scored-txn topic (ALL transactions,
          (Kafka)              scored or not)
                    |                |
                    v                v
          Alerting service    Serving store (Redis / OLAP-friendly
          (pages risk team     store) --> Dashboard (rolling 24h)
           for high-severity)
                                      |
                                      v
                          Data Lake (S3, Parquet, partitioned by
                          txn_date) --> 7-year retention, batch
                          model retraining reads from here
```

### Step 4 — Component choices, with trade-offs stated out loud

- **Kafka, partitioned by `account_id`.** Partitioning by account (not
  transaction ID) means all of one account's transactions land on the same
  partition in order — required for the rule engine's velocity checks ("5
  transactions from this account in 2 minutes"), which need to see an
  account's transactions in sequence. Trade-off named explicitly: an account
  with unusually high transaction volume (a large merchant, not an
  individual) becomes a hot partition — worth flagging as a known risk to
  watch for (Concept 2, section 2), with salting only if it's actually
  observed, not preemptively.
- **Flink over Spark Structured Streaming for the scoring path**, specifically
  because the rule engine needs low-latency STATEFUL processing (tracking a
  rolling window of recent transactions per account) with strong
  checkpointing guarantees — Flink's exactly-once state model is a better fit
  here than treating this as a series of micro-batches.
- **The model scoring call is asynchronous with a timeout, not a blocking
  step in the main stream.** This directly answers the "never drop a
  transaction" requirement from Step 1 — if the model service is slow, the
  transaction still flows through to the scored-txn topic and dashboard,
  just flagged as "unscored," rather than backing up (or dropping) the whole
  stream waiting on one slow dependency.
- **Two Kafka topics downstream (flagged vs. all-scored), not one.** The
  alerting service that pages a human should only ever see high-confidence
  flags — piping EVERY transaction through the same topic the pager reads
  from would either drown the risk team in noise or force them to build
  their own filtering layer redundantly.
- **Redis (or similar) for the rolling-24h dashboard serving layer, S3/Parquet
  for the 7-year archive** — this is the two-tier retention split from Step
  1, made concrete: hot/recent data optimized for dashboard read latency,
  cold/long-term data optimized for cheap storage and periodic batch reads
  (model retraining, investigation queries), not the same store trying to
  serve both needs.

### Step 5 — Narrate the data flow for a concrete transaction

> "A transaction hits the payment service, gets published to `txn_events`
> keyed by account ID. Flink picks it up, runs it against the rule engine
> immediately — say a velocity check fires because this is the 6th
> transaction from this account in 90 seconds. In parallel, it fires an
> async feature-store lookup and model-scoring call. Say the model responds
> in 400ms with a high fraud-probability score. Both signals get merged onto
> this transaction's record, which is published to `scored_txn_events`
> regardless of outcome, and — because the combined signal cleared the
> flagging threshold — also to `flagged_txn_events`. The alerting service
> picks that up and pages the on-call risk analyst within the 10-second
> target. The dashboard, reading from the Redis-backed serving store, shows
> this transaction in the rolling 24-hour view immediately. Independently,
> the raw event lands in the S3 archive, partitioned by transaction date,
> where it'll sit for 7 years and also feed the next scheduled model
> retraining run."

### Step 6 — How it scales and how it fails

- **10x traffic spike (holiday shopping):** Kafka absorbs the burst
  natively via partitioning; Flink's consumer parallelism scales out to
  match; the queue-based load-leveling pattern (Concept 2, section 8) is
  exactly what's protecting the scoring path from the spike hitting the
  dashboard directly. Pre-provision extra Flink task slots ahead of a KNOWN
  spike window (Black Friday) rather than relying purely on reactive
  autoscaling, which has ramp-up latency.
- **Model service goes down entirely:** the async-with-timeout design means
  transactions keep flowing, unscored, through the rule-engine path alone —
  degraded (rule-only) fraud detection, not a full outage. This is the
  concrete payoff of the Step 4 design choice, not a bolt-on afterthought.
- **A known bad actor's account is a hot partition:** monitor per-partition
  throughput; if one account is genuinely producing disproportionate load
  (not just normal merchant volume), it's likely already a fraud signal
  itself — but the technical fix, if needed, is salting that specific
  account's key the same way a skewed join key gets salted (Concept 3,
  section 5).
- **Schema evolution** (a new field added to the transaction event): use a
  schema registry (Avro/Protobuf) with backward-compatible evolution rules,
  so the stream processor and downstream consumers don't break the moment
  upstream adds a field.

### Step 7 — Close with the trade-offs made, unprompted

> "I kept this to one streaming codepath plus an unrelated batch retraining
> job specifically to avoid Lambda's drift risk — the fraud SCORING logic
> only exists once. The two-tier retention split (Redis for hot/recent,
> S3 for the 7-year cold archive) trades a bit of design complexity for a
> much cheaper long-term storage bill, which matters given the 7-year
> regulatory retention requirement stated up front. If sub-200ms in-line
> BLOCKING were ever required instead of flag-for-review, that changes the
> latency budget enough that I'd want to revisit the model-serving path
> entirely — that's a different, harder problem than what was asked here."

---

## Scenario 2: Surge Pricing Analytics for a Ride-Sharing App

**Interviewer prompt:**
> "Design a data pipeline that powers surge pricing for a ride-sharing app —
> the system needs to compute a real-time surge multiplier per city zone
> based on supply and demand, and also produce the historical analytics
> finance and ops teams use to evaluate pricing strategy."

### Step 1 — Clarifying questions

- **What's the actual latency requirement for a surge multiplier to
  update?** → Interviewer says: within 30 seconds of a meaningful shift in
  supply/demand. → Confirms streaming, and gives a concrete window size for
  the computation (a 30-second window is far more actionable than "make it
  fast").
- **Granularity — per city, or finer?** → Interviewer says: per geohash
  zone within a city (roughly neighborhood-sized), since demand is
  extremely local — a surge in one part of downtown doesn't mean the
  suburbs are surging too. → This is a scoping question that changes the
  data model, not just an implementation detail: the key for every
  aggregation is `(geohash_zone, time_window)`, not `(city, time_window)`.
- **Does historical analytics need the SAME surge numbers the live system
  computed, or a recomputed, corrected version?** → Interviewer says:
  recomputed and corrected — live surge is a fast approximation, but
  finance needs numbers that account for late-arriving GPS pings and
  corrected ride records. → This is the Lambda trigger: a genuine need for
  both a fast approximate number AND a separately-computed accurate one for
  the SAME underlying metric (surge/demand), which Scenario 1 explicitly did
  NOT have.
- **Scale?** → Interviewer says: 200 active cities, 5M rides/day, ~500K GPS
  pings/second platform-wide. → GPS ping volume, not ride volume, is
  clearly the dominant throughput driver here — worth naming out loud.
- **What happens to a driver's GPS signal in a tunnel/dead zone?** →
  Interviewer says: gaps are expected and normal. → Signals a genuine
  late-arriving-data requirement, not an edge case to hand-wave.

### Step 2 — State it back, quantified

> "500K GPS pings/sec is the dominant load, not the 5M rides/day. Surge
> multiplier per geohash zone must update within 30 seconds. Live surge is
> fast-approximate; a separately-computed, corrected historical view is a
> hard requirement for finance — so this needs both a speed layer and a
> batch layer for the same underlying supply/demand signal. GPS gaps
> (tunnels) are expected, not exceptional, so late data handling is core to
> the design, not an edge case bolted on at the end."

### Step 3 — Architecture

> "This is Lambda, and I want to say explicitly why, given Concept 1's
> warning about Lambda's cost: the live surge multiplier and the
> finance-grade historical surge/demand numbers are genuinely different
> computations over the same raw signal — one is a fast, windowed
> approximation; the other reprocesses with corrected/late data and
> different business rules (e.g., excluding driver-app glitches that
> shouldn't count as 'went offline'). This isn't a case where the same logic
> is being awkwardly duplicated — it's a case where the two audiences
> genuinely need different derivations, which is exactly when Lambda's cost
> is worth paying."

```
Driver App (GPS pings) --> Kafka (geo_pings, partitioned by geohash prefix)
Rider App (ride requests) --> Kafka (ride_events)
                                   |
                +------------------+------------------+
                |                                       |
                v                                       v
      SPEED LAYER (Flink)                     BATCH LAYER (Spark, daily)
      - 30s tumbling windows                  - reprocesses full raw events
      - per-geohash supply/demand count       - corrects for late GPS, app
      - surge multiplier formula                glitches, cancelled-ride noise
      - writes to Redis (geohash -> multiplier) - writes corrected daily
                |                                 supply/demand + surge to
                v                                 warehouse (fact_surge_daily)
      Pricing Service reads live                          |
      multiplier from Redis                                v
      (sub-ms lookup at ride-request time)        Finance/Ops BI dashboards,
                                                    pricing-strategy analysis
```

### Step 4 — Component choices, with trade-offs

- **Geohash-prefix partitioning of the GPS topic**, not raw driver ID.
  Grouping pings by geographic proximity means the stream processor's
  per-zone aggregation doesn't require a cross-partition shuffle to compute
  a zone's supply count — pings for the same zone are already co-located.
  Trade-off: a single very dense downtown geohash can still be a hot
  partition relative to a sparse suburban one — mitigated by choosing a
  geohash precision level fine enough that even the densest zone is a
  reasonable partition size (a capacity-planning decision, Concept 4).
- **Watermarking for late GPS data**, explicitly sized from Step 1's answer
  ("gaps are expected, not exceptional") — a 5-minute watermark lets the
  30-second window computation still finalize promptly for the live surge
  number, while the BATCH layer (which isn't time-pressured) can
  incorporate arbitrarily late data without a watermark cutoff at all. This
  is the concrete mechanism behind "speed layer approximates, batch layer
  corrects."
- **Redis as the live serving store for the pricing service**, not the
  warehouse — the pricing service needs a sub-millisecond lookup at the
  moment a ride is requested; a warehouse query, however fast, is the wrong
  tool for that access pattern (this is the same "match the store to the
  access pattern" reasoning from `03_optimization_techniques.md`, applied to
  system design rather than query tuning).
- **The batch layer doesn't just re-run the SAME formula on more complete
  data — it can legitimately use a different, more careful business rule**
  (e.g., a driver who reports "no GPS signal" for under 60 seconds isn't
  treated as "went offline" in the corrected view, but the live system,
  optimizing for speed, doesn't distinguish this case). Naming this
  difference explicitly is what shows the interviewer you understand WHY
  the two layers diverge, not just that Lambda "has two layers."

### Step 5 — Narrate the data flow

> "A driver's GPS ping lands in the `geo_pings` topic, keyed by geohash
> prefix. Flink's 30-second tumbling window aggregates supply (idle nearby
> drivers) against demand (recent ride requests in that zone), computes a
> surge multiplier via the pricing formula, and writes `zone -> multiplier`
> into Redis. A rider requesting a ride triggers a sub-millisecond Redis
> lookup by the pricing service — that's the entire live path, end to end,
> well within the 30-second freshness target. Separately, every raw ping
> and ride event also lands in the data lake. Once a day, a Spark job
> reprocesses the full day's raw events — now with any late-arriving GPS
> pings incorporated and app-glitch noise filtered out — and writes a
> corrected `fact_surge_daily` to the warehouse. Finance's pricing-strategy
> dashboard reads from THAT table, never from Redis — it's explicitly not
> looking at the same numbers the live system used, and that's by design,
> not an inconsistency to be alarmed by."

### Step 6 — Scaling and failure

- **A city's demand spikes 10x during a major event (a concert letting
  out):** Flink's parallelism scales per-partition; if that city's geohash
  zones are hot relative to others, this is the exact "known event, pre-
  provision ahead of it" pattern from Scenario 1 — a predictable spike is
  cheaper to handle by planning than by relying purely on reactive scaling.
- **Redis serving layer goes down:** the pricing service needs a defined
  fallback (serve a cached last-known multiplier, or fall back to a
  non-surge default price) rather than failing ride requests outright —
  worth naming explicitly, since a silent full outage of the pricing path
  is a business-critical failure mode, not a minor one.
- **The batch layer's daily correction disagrees meaningfully with what the
  live system charged riders that day:** this needs an explicit reconciliation
  process (finance's number is the system of record; a "why did live and
  batch diverge" investigation runbook), because Lambda's very premise
  (two derivations of the same underlying reality) guarantees they'll
  disagree sometimes — pretending they never will is a design gap, not
  reassurance.

### Step 7 — Close with the trade-offs

> "I chose Lambda here specifically because the live and historical surge
> numbers are legitimately different computations for different audiences,
> not the same logic duplicated for no reason — that's the bar I'd hold
> before accepting Lambda's operational cost anywhere else in this design.
> Geohash-prefix partitioning keeps the live aggregation shuffle-free at the
> cost of a known, monitorable hot-zone risk in dense areas. If the business
> ever needed the LIVE number to also be audit-grade accurate, that would
> be the point where I'd say this needs to become a genuinely different
> (and harder) design, not a tweak to this one."

---

## Scenario 3: Ingesting and Querying IoT Sensor Data from Millions of Devices

**Interviewer prompt:**
> "Design a system to ingest and query telemetry from several million IoT
> sensors (think industrial equipment monitors), supporting both
> threshold-based alerting and ad-hoc historical analysis by engineers."

### Step 1 — Clarifying questions

- **How many devices, and how often does each report?** → Interviewer says:
  3 million devices, each reporting a small telemetry payload (temperature,
  vibration, status) every 10 seconds. → Immediately convert this:
  `3,000,000 / 10 = 300,000 events/sec` sustained — that number drives
  every downstream sizing decision (Concept 4).
- **Alerting latency requirement?** → Interviewer says: a threshold breach
  (e.g., temperature exceeding a safety limit) must alert within 15 seconds.
  → Confirms a streaming alerting path is required, separate from historical
  query needs.
- **What does "ad-hoc historical analysis" actually look like — dashboards,
  or genuinely exploratory queries?** → Interviewer says: engineers
  investigating an incident want to query raw sensor history for a specific
  device over an arbitrary time range, not just pre-built dashboards. →
  Rules out an architecture that ONLY keeps pre-aggregated rollups; raw,
  queryable history at the individual-device grain must be retained and
  genuinely queryable, not just summarized away.
- **Retention?** → Interviewer says: raw telemetry for 90 days, aggregated
  (hourly rollups) for 3 years. → Another two-tier retention split, same
  shape as Scenario 1's, for a different reason (query-pattern-driven here,
  regulatory-driven there) — worth distinguishing out loud.
- **Are all 3M devices reporting at genuinely uniform intervals, or bursty?**
  → Interviewer says: mostly uniform, but a firmware update rollout can
  cause thousands of devices to reconnect and flush buffered readings at
  once. → A real backpressure scenario (Concept 2, section 7), not
  hypothetical.

### Step 2 — State it back, quantified

> "300,000 events/sec sustained is the baseline load, from 3M devices
> reporting every 10 seconds. Threshold alerting needs 15-second latency.
> Ad-hoc queries need raw, device-level history queryable for 90 days, with
> 3-year hourly rollups for longer-range analysis. Firmware rollouts create
> real burst load on reconnect, which needs explicit backpressure handling,
> not just 'the queue will absorb it' hand-waving."

### Step 3 — Architecture

> "This is Kappa, not Lambda, and not plain batch. Kappa fits because every
> input here is naturally an event (a telemetry reading), the alerting need
> is genuinely real-time, and — unlike Scenario 2 — I don't have a
> requirement for a SEPARATELY-derived, differently-computed historical
> number. The 'historical' need here is really 'the same raw events, kept
> longer and queryable' plus 'rollups of the same computation at a coarser
> grain' — not a second, corrected derivation. That's exactly the case where
> Kappa's single codepath is the better fit than Lambda's two."

```
3M Devices --> Ingest Gateway (lightweight, handles device auth + protocol
               translation, e.g. MQTT -> Kafka)
                        |
                        v
          Kafka (device_telemetry, partitioned by device_id hash,
                 sized for 300K events/sec sustained)
                        |
              +---------+---------+
              |                    |
              v                    v
    Stream Processor (Flink)   Sink: raw events -> S3/GCS
    - threshold rule eval        (Parquet, partitioned by ingest_date +
      per reading                 device_id hash bucket) -- 90-day raw
    - 15s alert latency target    retention, queryable via a lakehouse
    - hourly rollup aggregation   engine (Trino/Athena/Spark SQL) for
      (count, avg, min/max per    ad-hoc engineer investigation
      device per hour)
              |
              v
    Alert topic --> Alerting        Hourly rollups --> Warehouse table,
    service (pages on-call)         3-year retention, powers dashboards
```

### Step 4 — Component choices, with trade-offs

- **A lightweight ingest gateway in front of Kafka**, translating from a
  device-friendly protocol (MQTT is standard for constrained IoT devices)
  into Kafka messages, rather than having 3 million devices speak Kafka's
  protocol directly. This is a real architectural layer, not a nicety —
  device-side simplicity (cheap firmware, unreliable connectivity) is a
  hard constraint that shapes the ingestion tier's design.
- **Partition by a HASH of `device_id`, not by any geographic/customer
  grouping.** Unlike Scenario 2's geohash partitioning (where locality was
  the point), here each device's readings are independent and there's no
  cross-device windowing need — hash partitioning for even load
  distribution is the right default (Concept 2, section 2), and the
  firmware-rollout burst risk (Step 1) is a reason to make SURE partition
  count comfortably exceeds consumer parallelism, so a burst doesn't
  concentrate on too few partitions.
- **Raw events land in the lake AND get rolled up — not rolled-up-only.**
  This directly answers Step 1's clarification that engineers need raw,
  device-level query access for incident investigation — a design that only
  kept hourly rollups would silently fail that requirement the first time
  an engineer needed to see the actual raw readings around an incident.
- **Kafka sized generously above the 300K/sec baseline specifically for the
  firmware-rollout burst case** — this is where the backpressure/load-
  leveling patterns (Concept 2, sections 7-8) get named explicitly rather
  than assumed: partition count and consumer parallelism should be sized
  to a stated burst multiple (e.g., "handle a 5x burst without falling
  behind more than 2 minutes"), not just the steady-state number.

### Step 5 — Narrate the data flow

> "A sensor reports a temperature reading over MQTT to the ingest gateway,
> which authenticates the device and republishes it to `device_telemetry` in
> Kafka, keyed by a hash of `device_id`. Flink picks it up: if the reading
> breaches a configured threshold, it's published to the alert topic
> immediately — well inside the 15-second target — and the alerting service
> pages on-call. Independently, the SAME event is written to the S3 raw
> archive, partitioned by ingest date, where it sits queryable for 90 days.
> Flink also maintains an hourly rolling aggregation per device — count,
> average, min/max — flushed to the warehouse each hour, which is what
> powers the standard dashboards and survives for 3 years. When an engineer
> investigates an incident from last week, they query the raw S3 archive
> directly (via Athena/Trino) for that specific device's full-resolution
> history around the incident window — the rollup table wouldn't have the
> resolution they need for that kind of investigation."

### Step 6 — Scaling and failure

- **Firmware rollout burst (thousands of devices reconnect and flush
  buffered readings at once):** this is exactly why Kafka is sized above
  steady-state and why partition count exceeds current consumer
  parallelism — a burst absorbs into partition backlog rather than dropping
  or overwhelming the stream processor; consumer lag is the metric to alert
  on, with a defined "how stale is too stale" threshold.
- **A single device sending malformed or absurdly frequent data (a bug in
  one firmware version):** this is a device-level "hot key" — the fix is
  the same salting concept applied differently: rate-limit or quarantine at
  the ingest gateway BEFORE it reaches Kafka, rather than letting one
  misbehaving device degrade the shared pipeline for all 3 million others.
- **90-day raw retention getting expensive at 300K events/sec sustained:**
  worth naming the storage-tiering lever from Concept 4 explicitly — the
  most-recent, most-likely-to-be-queried days can sit in a faster/costlier
  tier, with the tail of the 90-day window moved to a cheaper tier as it
  ages, without waiting for the full retention period to lapse before any
  cost optimization kicks in.

### Step 7 — Close with the trade-offs

> "I picked Kappa over Lambda specifically because there's no genuinely
> different SECOND derivation needed here — raw-plus-rollup is one codepath
> at two grains, not two competing computations of the same metric. I sized
> Kafka above steady-state specifically for the firmware-rollout burst case
> named in the clarifying questions, rather than discovering that gap during
> the first real rollout. If the business later needed cross-device
> correlation (e.g., 'alert if 5% of devices in the same facility breach a
> threshold within a minute'), that's a genuinely new windowing requirement
> that would push me to reconsider the hash-based partitioning — worth
> flagging as a real extension point, not something this design already
> handles for free."

---

## Now You Try: Migrating a Retailer from Nightly Batch to Near-Real-Time

**Interviewer prompt:**
> "A mid-size retailer currently runs all analytics as nightly batch jobs —
> inventory, sales reporting, and a recommendation engine all update once a
> day. Leadership wants inventory and sales visible near-real-time within
> six months, without a full rebuild. Design the migration path and the
> resulting architecture."

Work through Steps 1–7 yourself, out loud, before reading the debrief.
Specifically make sure you cover: what clarifying questions you'd ask, which
architecture you'd land on and why, what changes vs. what survives from the
existing batch system, and how you'd sequence the migration given the
"without a full rebuild" and "six months" constraints.

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **Clarifying questions that matter most here:** (1) "Near-real-time" for
  WHICH metrics specifically — all of inventory/sales/recommendations, or a
  subset? (Interviewer likely narrows to inventory + sales; recommendations
  can stay batch, since a recommendation being a day stale is a much smaller
  business problem than inventory being a day stale — this is the
  scoping question that keeps the answer from ballooning into "rebuild
  everything.") (2) What does "near-real-time" mean quantified — minutes?
  seconds? (assume: a few minutes is acceptable, not sub-second) (3) Is the
  underlying source system (the OLTP inventory/order DB) able to support
  CDC (log-based change capture), or would this require application-level
  changes? (assume: yes, CDC-capable, a common and reasonable assumption for
  a modern retailer's OLTP stack).

- **Architecture: Kappa-leaning hybrid, NOT a full Lambda rebuild.** The key
  insight the "without a full rebuild" constraint is testing for: you do
  NOT need to throw away the nightly batch warehouse loads — you need to
  ADD a streaming path (CDC from the OLTP database via a tool like Debezium
  → Kafka → a stream processor maintaining near-real-time inventory/sales
  aggregates) that feeds a small, new "hot" serving layer (updated within
  minutes), while the EXISTING nightly batch pipeline keeps running
  unchanged as the accurate, audited system of record for finance/deep
  historical reporting and for the recommendation engine that doesn't need
  to change at all. This is explicitly NOT full Lambda (Concept 1, section
  3) — it's closer to "add a speed-layer-shaped addition next to an
  unchanged, already-working batch system," because the batch layer was
  never broken and doesn't need reinventing.

- **What survives unchanged, and why that matters for the "six months, no
  full rebuild" constraint:** the nightly ETL into the warehouse, the star
  schema, the recommendation engine's batch training — none of it needs to
  change. This is the single biggest thing a strong answer says explicitly:
  naming what does NOT need to change is as important as naming the new
  streaming path, because it's what makes "six months, no full rebuild" an
  achievable scope instead of an implicit full-platform migration disguised
  as an add-on.

- **Migration sequencing (a genuinely different kind of reasoning than the
  first three scenarios, since this prompt is explicitly ABOUT the
  migration path, not just the end-state):**
  1. Stand up CDC (Debezium) on the OLTP source in parallel with the
     existing batch extract — read-only, no risk to the existing pipeline,
     validate it captures changes correctly before anything downstream
     depends on it.
  2. Build the new streaming aggregation path (inventory/sales rollups)
     feeding a new serving store, running in SHADOW mode — computing
     results but not yet exposed to any dashboard — and reconcile its
     numbers against the next morning's batch numbers daily, to build
     confidence the streaming path is correct before anyone relies on it.
  3. Only once reconciliation is clean for a sustained period, cut the
     inventory/sales dashboards over to read from the new near-real-time
     serving store; the nightly batch warehouse load keeps running
     unchanged underneath, as it always did, for everything else.
  4. Explicitly do NOT touch the recommendation engine in this project —
     naming that as an intentional non-goal (rather than silently ignoring
     it) shows the scoping discipline the "near-real-time... without a full
     rebuild" prompt is testing for.

- **Edge cases worth naming:** CDC lag during a source-database maintenance
  window (define a fallback: serving store shows a "data as of" timestamp
  rather than silently going stale with no indication); the reconciliation
  step catching a real discrepancy (this is a FEATURE of the shadow-mode
  rollout, not a failure — it's precisely why shadow mode runs before cutover
  rather than cutting over on day one and hoping).

- **The interview tell:** the strongest answers to a "migrate X to
  real-time" prompt spend MORE time on the migration path (what changes,
  what doesn't, how you validate before cutover) than on describing the
  end-state architecture in isolation — because the prompt explicitly asked
  for the migration, and a candidate who only describes "here's what a
  real-time architecture looks like" answered a different, easier question
  than the one asked.

</details>

---

## What Interviewers Are Actually Scoring

- Did you ask clarifying questions that change the design, not just
  procedural ones ("what's your tech stack") — and quantify the answers?
- Did you name a specific architecture (batch/streaming/Lambda/Kappa) AND
  justify it against the SPECIFIC requirements just stated, rather than
  reciting the general trade-off table?
- Did every major component choice come with a stated trade-off, not just a
  technology name dropped without justification?
- Did you narrate the data flow for a CONCRETE example (one transaction,
  one ride, one sensor reading) rather than staying abstract the whole time?
- Did you address scaling AND failure modes without being asked — and tie
  each one back to a specific component you already named?
- Did you close by naming the trade-offs you accepted, unprompted — and
  flag where the design would need to change if a stated assumption changed?

If you can do all of the above before writing a line of implementation code,
the implementation (see `../concepts/` and `../practice/`) is the easy part.

---

**Next:** [02 — Rapid-Fire Q&A](02_rapid_fire_qna.md)
