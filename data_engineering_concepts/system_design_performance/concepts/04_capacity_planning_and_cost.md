# Concept 4: Capacity Planning and Cost Trade-offs

**Covers:**
- Back-of-envelope math for pipeline throughput (events/sec, daily volume, storage)
- Sizing Kafka partitions and compute from that math
- Why "quantify it" is scored as heavily as the architecture choice itself
- Cost trade-offs across storage tiers, compute models, and architecture choices
- A worked capacity-planning example end to end, with every step of arithmetic shown

*This concept doesn't come from a single source file the way 01-03 do — it fills a real gap: a tuning-focused course covers HOW to optimize a pipeline, but a system-design interview also expects you to size one from a business scenario before you've built anything. This is that muscle.*

---

## 1. Why Quantify at All

"We'll get millions of events a day" is not an answer an interviewer can evaluate — it doesn't tell them whether you need one Kafka partition or two hundred, one Spark executor or fifty. **Every number you state should be derivable from the requirements you were given**, and stating the arithmetic out loud (not just the final number) is exactly what's being scored — it's proof you're reasoning quantitatively rather than pattern-matching to "big data means Kafka and Spark."

The habit to build: whenever a scenario gives you a rate or a volume, immediately convert it into the three numbers that drive every downstream decision — **events/second, bytes/day, and bytes retained** — before touching architecture or technology choices.

---

## 2. Worked Example: Capacity Planning for a Log Analytics Platform

**Scenario:** 10,000 servers, each producing 500 log lines/second, average line size 200 bytes. Retain 30 days, assume 5x compression on write.

```text
Step 1 -- Events per second:
  total_events_per_sec = servers x logs_per_sec_per_server
                        = 10,000 x 500
                        = 5,000,000 events/sec

Step 2 -- Daily raw volume:
  daily_bytes = events_per_sec x avg_bytes_per_event x seconds_per_day
              = 5,000,000 x 200 x 86,400
              = 86,400,000,000,000 bytes
              ~= 78.2 TB/day (raw, uncompressed)

Step 3 -- 30-day storage, compressed:
  storage_30d = (daily_TB x 30) / compression_ratio
              = (78.2 x 30) / 5
              ~= 469 TB

Step 4 -- Partitioning (if partitioned hourly):
  partitions_per_day = 24   (one per hour -- the natural choice for a
                              time-series workload with mostly-recent-data reads)

Step 5 -- Kafka partition count, sized for throughput:
  Given each partition can sustain ~10,000 msg/sec (a real, conservative
  per-partition throughput assumption for typical message sizes):
  kafka_partitions = total_events_per_sec / per_partition_throughput
                    = 5,000,000 / 10,000
                    = 500 partitions

RECOMMENDATION:
  ~500 Kafka partitions (round to a number divisible by your consumer
  count so partition assignment is even), hourly partitioning downstream,
  ~469 TB of compressed 30-day storage to provision.
```

This is the whole skill: convert given rates into events/sec, multiply out to a daily volume, divide by a retention/compression assumption to get storage, and divide the events/sec by a per-unit throughput assumption to size the ingestion layer. Every step is arithmetic a reader can check — that's exactly why it reads as rigorous instead of guessed.

---

## 3. Sizing Compute from the Same Numbers

The same inputs that size storage also size compute, using rule-of-thumb ratios you state explicitly (and would validate against a real benchmark before committing in production):

```text
Batch (Spark) sizing heuristic:
  > 1 TB/day  -> multi-node cluster, roughly 1 node per 250GB/day of volume
  100GB-1TB/day -> smaller cluster, roughly 1 node per 200GB/day
  < 100GB/day -> 1-2 nodes, or serverless/on-demand is often more cost-effective
              than maintaining a dedicated cluster at all

Streaming (Flink) sizing heuristic:
  > 50,000 events/sec -> 1 TaskManager per ~10,000 events/sec
  5,000-50,000 events/sec -> 2+ TaskManagers, smaller each
  < 5,000 events/sec -> 1-2 TaskManagers is plenty

Warehouse compute sizing heuristic (concurrency-driven, not volume-driven):
  > 50 concurrent analysts -> auto-scaling warehouse, separate ETL vs BI compute
  10-50 concurrent          -> medium warehouse, split ETL/BI to avoid contention
  < 10 concurrent           -> a single small warehouse is enough
```

The mental shift from Concept 1-3: sizing storage is driven by VOLUME and RETENTION; sizing streaming compute is driven by EVENTS/SEC; sizing warehouse compute is driven by CONCURRENCY, not raw data size — a 500TB warehouse queried by 3 analysts needs far less compute than a 5TB warehouse queried by 200 analysts simultaneously. Naming which driver applies to which layer is itself a signal of understanding, not just running a formula.

---

## 4. Cost Trade-offs for Cloud DE Systems

Capacity planning answers "how much." Cost optimization answers "how much does that cost, and where's the lever."

**Storage tiering** — not all data needs the same storage class. Hot data (queried daily) stays on standard object storage; data older than its typical query window moves to a cold/archive tier (S3 Glacier, GCS Coldline) at a fraction of the cost, with a real retrieval-latency trade-off (minutes to hours instead of milliseconds) — appropriate for compliance-retention data nobody queries interactively.

```text
Rough monthly storage cost shape (illustrative, S3-class pricing):
  Standard tier:  ~$23/TB/month
  Infrequent-access tier: ~$12-14/TB/month (cheaper storage, cost per GB retrieved)
  Archive tier:   ~$1-4/TB/month (cheapest storage, hours-scale retrieval)
-> A 500TB lake where 90% is >1 year old and rarely queried is a strong
   candidate for lifecycle rules moving that 90% to a cheaper tier —
   often the single biggest storage cost lever available, and it requires
   no architecture change at all.
```

**Compute cost shape**, by architecture (tying back to Concept 1's decision matrix):

```text
Batch:      cheapest per unit of data processed -- pay for compute only while
            the job runs; the "run it hourly instead of continuously" pattern
            is inherently cost-efficient.
Streaming:  compute runs continuously whether or not there's a traffic spike
            right now -- you're paying for always-on capacity, which is the
            real cost driver interviewers want you to name, not "Kafka is
            expensive."
Lambda:     pays for BOTH a batch cluster's compute AND a continuously-running
            stream processor -- explicitly the most expensive pattern, on top
            of being the most operationally complex one (Concept 1).
```

**Reserved vs. on-demand compute** — for steady-state, predictable workloads (a nightly batch job that always runs, a stream processor that's always on), reserved/committed-use pricing is meaningfully cheaper than on-demand for the same capacity; on-demand (or serverless/auto-scaling) is the right choice for spiky or unpredictable load where you'd otherwise be paying for reserved peak capacity that sits idle most of the time. Naming this distinction (steady-state → reserved, spiky → on-demand/serverless) is a stronger answer than "use spot instances" without qualification.

**Right-sizing before scaling** — the optimization hierarchy from the top-level README applies to cost too: a poorly-partitioned table or an ungoverned `SELECT *` habit driving up warehouse compute cost should be fixed before reaching for a bigger (more expensive) warehouse tier. Interviewers listen for whether you'd diagnose a cost complaint as an optimization problem first, an infrastructure-sizing problem second.

---

## 5. Putting It Together: The Capacity + Cost Narrative

A strong system-design answer doesn't present capacity and cost as two separate sections — it uses capacity numbers to justify the architecture AND flags the resulting cost shape as an explicit trade-off:

> "At 5M events/sec sustained, a streaming-only (Kappa) architecture means paying for that processing capacity continuously, 24/7, including the overnight hours when volume is actually a fraction of peak. If the business can tolerate even 15-minute staleness overnight, a hybrid design — streaming during business hours, batch catch-up overnight — meaningfully reduces the always-on compute bill without touching the daytime latency guarantee."

This is the level of trade-off reasoning `../interview_questions/01_worked_scenarios.md` expects throughout — capacity math that FEEDS a cost-aware architecture recommendation, not a capacity exercise done in isolation from the design.

---

## Key Takeaways

- Convert every given rate/volume into events/sec, daily bytes, and retained bytes FIRST — before choosing any technology — and show the arithmetic, not just the answer.
- Storage sizing is driven by volume + retention + compression; streaming compute by events/sec; warehouse compute by concurrency — know which driver applies to which layer.
- Storage tiering (hot/infrequent/archive) is usually the single biggest, lowest-risk cost lever in a data platform, and requires no architecture change.
- Lambda architectures pay for batch AND streaming compute simultaneously — the most expensive pattern in the decision matrix, and cost is a legitimate reason (alongside operational complexity) to avoid it unless both accuracy and freshness are hard requirements.
- Reserved/committed pricing suits steady-state, predictable load; on-demand/serverless suits spiky, unpredictable load — naming which applies to which part of your design is a stronger answer than a blanket "use spot instances."
- Diagnose cost complaints as an optimization problem (Concept 3) before reaching for a bigger, more expensive tier.
