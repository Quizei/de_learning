# Concept 1: Pipeline Architecture Patterns

**Covers:**
- Batch architecture (the ETL/warehouse pattern) — when "next day" is fine
- Streaming architecture (broker + stream processor) — when seconds matter
- Lambda architecture (batch + speed layers merged) — when you need both
- Kappa architecture (streaming-only, replay from an immutable log)
- A decision matrix for picking one, and the "start simple" default

*Every config shown below (Kafka, Flink, Spark, Airflow) is real and how you'd actually configure it. This is the architectural vocabulary every other file in this folder assumes — the interview questions in `../interview_questions/` constantly ask you to justify one of these four choices.*

---

## 1. Batch Architecture (the ETL / warehouse pattern)

```
Sources --> Extract --> Stage --> Transform --> Load --> Warehouse --> BI/Reports
```

Batch is the default architecture for analytics: pull data on a schedule (hourly, nightly), transform it in bulk, land it in a warehouse. It's the pattern the rest of this course (`etl_elt_patterns/`, `data_warehousing_lakes/`) assumes as a baseline.

**Why it's still the right default for most workloads:**
- High throughput per unit of operational complexity — one job, one failure mode (it either ran or it didn't), re-run to recover.
- Lets you do expensive, correctness-heavy transforms (large joins, dedup, SCD Type 2 merges) that don't fit a per-event processing model.
- Most business reporting genuinely tolerates T+1 latency — "yesterday's revenue by region" doesn't need to be live.

**Where it breaks down:** anything the business describes as "as it happens" — fraud must be blocked before the transaction clears, not flagged the next morning; a live ops dashboard that's 12 hours stale isn't a dashboard, it's a report.

```python
# spark-submit --deploy-mode cluster nightly_orders_etl.py
#   --conf spark.sql.shuffle.partitions=800
#   --conf spark.sql.adaptive.enabled=true

# Airflow DAG shape (orchestration, not the transform itself):
#   extract_orders >> stage_orders >> transform_and_dedupe >> load_fact_orders >> refresh_dashboards
```

**Worked characteristics:**

```text
Latency:            minutes to hours (T+1 is the common SLA)
Throughput:          very high (bulk I/O, columnar formats, whole-partition scans)
Failure recovery:    re-run the batch (idempotent load = safe to retry)
Best for:            reporting, ML training sets, data warehouse loads
```

---

## 2. Streaming Architecture (broker + stream processor)

```
Producers --> Message Broker (Kafka) --> Stream Processor (Flink/Spark SS) --> Sink (DB/Cache)
```

Every event is processed as it arrives instead of waiting for a batch window. This is a genuinely different operating model, not "batch but faster":

- **Continuous, not scheduled.** There's no "job run" to point at — the pipeline is always running, and "is it healthy" means checking consumer lag, not checking exit codes.
- **State lives in the processor.** Windowed aggregations (last 5 minutes of orders per region) require the stream processor to hold state and checkpoint it — that's what makes failure recovery hard: you're not just re-running a job, you're restoring in-flight state from a checkpoint.
- **Ordering and exactly-once semantics become real design questions** — a batch job re-run just overwrites the same output; a stream processor that double-processes a message after a crash can double-count revenue unless you design for idempotency (Kafka transactional producers, Flink's exactly-once checkpointing).

```python
# Kafka topic sized for expected throughput:
#   kafka-topics.sh --create --topic ride_events \
#       --partitions 24 --replication-factor 3 \
#       --config retention.ms=259200000   # 3-day retention for replay/recovery

# Flink job (conceptual): keyed stream, 30s tumbling window, watermark for lateness
# stream.keyBy(ride -> ride.cityId)
#        .window(TumblingEventTimeWindows.of(Time.seconds(30)))
#        .allowedLateness(Time.minutes(5))
#        .aggregate(new SurgeMultiplierAggregator())
```

**Worked characteristics:**

```text
Latency:            milliseconds to seconds
Throughput:          high, but per-event overhead is real (unlike batch's bulk I/O)
Failure recovery:    consumer offsets + processor checkpoints (harder than "re-run")
Best for:            fraud detection, live dashboards, IoT alerting, surge pricing
```

---

## 3. Lambda Architecture (batch + speed layers, merged)

```
                     +--- Batch Layer  ---- Batch Views (accurate, slow) ---+
All Events ----------|                                                      +--> Serving Layer
                     +--- Speed Layer  ---- Real-time Views (fast, approx) -+
```

Lambda exists because batch and streaming solve different problems and sometimes you genuinely need both answers merged: an *accurate* number (batch, recomputed from the full history, corrects for any late data or bugs) and a *fresh* number (speed layer, approximate, available within seconds) for the same metric.

```python
# Conceptual serving-layer merge:
def query_serving_layer(category, batch_views, realtime_views):
    accurate_total = batch_views.get(category, 0)       # from last batch recompute
    recent_delta = realtime_views.get(category, 0)       # events since that recompute
    return accurate_total + recent_delta
```

**The cost that makes Lambda controversial:** you maintain the SAME business logic twice, once in a batch engine (Spark) and once in a stream processor (Flink), and they WILL drift — a bug fix applied to one codepath and forgotten in the other silently produces two different numbers for the same metric. This is the single most commonly-cited reason teams move away from Lambda once they can.

**Worked characteristics:**

```text
Latency:            seconds (speed layer) + eventually-accurate (batch layer)
Complexity:          very high — two codepaths, two deploy pipelines, reconciliation
Best for:            when both strict accuracy AND low latency are hard requirements
                     (e.g. surge pricing needs to be live, but finance needs the
                      audited, corrected number for billing)
```

---

## 4. Kappa Architecture (streaming-only, replay from an immutable log)

```
Events --> Immutable Log (Kafka, long retention) --> Stream Processor v2 --> Serving
                |
                +---- Replay entire log with a NEW processor version when logic changes
```

Kappa's insight: if every write is already an event, and your log is retained long enough (and cheap enough) to replay in full, you don't need a separate batch layer for "recompute everything correctly" — you just replay the log through a new version of the SAME streaming processor.

```python
# Reprocessing with Kappa = deploy processor v2, replay from offset 0 (or a
# checkpoint), let it rebuild the serving store from scratch:
#
#   kafka-consumer-groups.sh --group processor_v2 --reset-offsets --to-earliest \
#       --topic ride_events --execute
#
# processor v2 differs from v1 only in its aggregation logic -- same log, same
# events, corrected business rule.
```

**Trade-off versus Lambda:** one codebase (no drift risk), but reprocessing a very large log is not free — replaying months of history through a stream processor to fix one bug is a real, sometimes multi-hour operation, and it REQUIRES your broker to retain that much history (Kafka with long retention, or tiered storage) rather than the usual few days.

**Worked characteristics:**

```text
Latency:            milliseconds to seconds
Complexity:          medium — simpler than Lambda, but replay cost is real
Best for:            genuinely event-sourced systems where "all data is an event"
                     is already true, and simplicity is valued over Lambda's
                     belt-and-suspenders accuracy guarantee
```

---

## 5. Decision Matrix

| | Batch | Streaming | Lambda | Kappa |
|---|---|---|---|---|
| Latency | Minutes–hours | ms–seconds | seconds + eventual accurate | ms–seconds |
| Throughput | Very high | High (per-event overhead) | Very high (both layers) | High |
| Operational complexity | Low | High | Very high (two codepaths) | Medium |
| Failure recovery | Re-run the batch | Checkpoints + offsets | Batch recomputes; speed replays | Replay the log |
| Best when | Freshness > 1 hour is fine | Sub-second freshness required | Need BOTH speed and perfect accuracy | Everything is naturally an event; want Lambda's benefits without two codepaths |

**Quick selection heuristic** (say this out loud in an interview, don't just recite the table):
1. Can the business genuinely tolerate an hour or more of staleness? → **Batch.** Don't reach for streaming because it sounds more impressive — it's a real ongoing operational cost.
2. Sub-second/seconds freshness is a hard requirement? → **Streaming** (or **Kappa** if the data is already fully event-shaped and you want replay-based reprocessing instead of a second codepath).
3. Both a live number AND a strictly-accurate, auditable number are non-negotiable for the SAME metric? → **Lambda** — but say out loud that you're accepting real operational cost for it, and that most teams should try to avoid needing this.
4. Not sure? → **Start with batch, add a streaming layer only for the specific metrics that actually need it.** This is the single most common "senior" answer — resist the urge to over-architect for imagined future scale.

---

## Key Takeaways

- Batch, streaming, Lambda, and Kappa aren't a maturity ladder — they're different trade-offs, and batch is the correct answer for most analytics workloads, not the "beginner" one.
- Streaming is a different operating model, not "batch but faster" — continuous processing, in-flight state, and exactly-once semantics are real new problems, not just a latency dial.
- Lambda buys you both accuracy and freshness at the real cost of maintaining (and keeping in sync) two independent codepaths for the same business logic — the most common reason teams abandon it.
- Kappa gets Lambda's single-codebase simplicity in exchange for replay cost and a broker that must retain much more history than the streaming default.
- The strongest interview answer names the latency requirement FIRST, then picks the simplest architecture that satisfies it — not the most sophisticated one available.
