# System Design & Performance — Practice Exercises

Ten exercises covering capacity estimation, architecture selection, query optimization, sharding design, data skew, operational trade-offs, SCD implementation, backpressure, partition pruning, and a full mini system design.

How to use this file: read the prompt, write down (or say out loud) your own answer — genuinely commit before looking — and only then expand the reference answer. Each answer notes which concept file covers the relevant background.

---

## Exercise 1: Capacity Estimation for a Log Analytics Platform

A company ingests server logs from 10,000 servers. Each server produces 500 log lines/second. Average log line size: 200 bytes.

Calculate: (a) total events/sec, (b) daily raw data volume, (c) 30-day storage assuming 5x compression, (d) partitions/day if partitioned hourly, (e) Kafka partition count if each partition handles 10K msg/sec.

<details>
<summary>Reference answer (try it yourself first)</summary>

```text
a) Events/sec:        10,000 servers x 500 logs/sec = 5,000,000 events/sec
b) Daily raw volume:  5,000,000 x 200 bytes x 86,400 sec ~= 78.2 TB/day
c) 30-day compressed: (78.2 TB x 30) / 5 ~= 469 TB
d) Partitions/day:    24 (one per hour)
e) Kafka partitions:  5,000,000 / 10,000 = 500 partitions
```

*(Concept 4, section 2 — this is the exact worked example there, walked through step by step.)*

</details>

---

## Exercise 2: Choose the Right Architecture

For each scenario, choose Batch / Streaming / Lambda / Kappa, and justify:

- **A)** Daily financial reconciliation report (must be 100% accurate).
- **B)** Real-time fraud detection for credit card transactions.
- **C)** A trending-topics feed updated every minute, that ALSO needs an accurate daily trend report.
- **D)** IoT sensor monitoring with alerting on threshold breaches.
- **E)** ML model retraining on accumulated user behavior data.

<details>
<summary>Reference answer (try it yourself first)</summary>

- **A) Batch.** 100% accuracy plus a tolerable T+1 latency is the textbook batch case — full recomputation and auditability matter more than freshness. *(Concept 1, section 1.)*
- **B) Streaming.** Fraud must be caught before the transaction clears — sub-second latency is a hard requirement, not a nice-to-have. *(Concept 1, section 2.)*
- **C) Lambda.** This is the canonical Lambda case stated explicitly in the prompt: real-time AND accurate-daily are both required for the SAME metric. Say out loud that you'd only accept the two-codepath cost because both requirements are truly non-negotiable. *(Concept 1, section 3.)*
- **D) Streaming, or Kappa if you want replay-based reprocessing** for sensor history (e.g., re-deriving alerts after a threshold-logic bug fix). *(Concept 1, sections 2 and 4.)*
- **E) Batch.** Retraining on the full accumulated dataset is computationally heavy and doesn't need to happen per-event — daily/weekly batch is standard, and reaching for streaming here would be over-engineering. *(Concept 1, section 1.)*

</details>

---

## Exercise 3: Optimize This Query

Given a 10M-row `events` table (`id, user_id, event_type, event_date, payload` — `payload` is a large JSON blob), this query is slow:

```sql
SELECT * FROM events
WHERE event_date >= '2024-01-01' AND event_date < '2024-02-01'
  AND event_type = 'purchase';
```

Apply three optimization techniques and explain each.

<details>
<summary>Reference answer (try it yourself first)</summary>

1. **Composite index** on `(event_date, event_type)` — the two columns the query filters on, in that order (date first since it's the more selective range filter here).
2. **Column pruning** — select only the columns actually needed (`id, user_id, event_date`), not `*`. `payload` is a large JSON blob; reading and transferring it for rows the caller doesn't need is pure waste.
3. **Predicate pushdown is implicit here** since the filter is already in SQL — the win is verifying (via `EXPLAIN QUERY PLAN`) that the engine is actually using the new index (a `SEARCH` step) rather than falling back to a full `SCAN`.

*(Concept 3, sections 1 and 2.)*

</details>

---

## Exercise 4: Design a Sharding Strategy

A `users` table has 500M rows. Query pattern: 80% look up by `user_id`, 15% list by `country`, 5% search by `email`.

Work out: (a) sharding key and why, (b) how to handle the country-listing query efficiently, (c) what happens if one country holds 40% of all users, (d) shard count if each shard should hold ~50M rows.

<details>
<summary>Reference answer (try it yourself first)</summary>

A) **Hash shard on `user_id`.** It's the dominant query pattern (80%) and a point lookup — hash sharding gives even distribution and O(1) shard routing for exactly this access pattern. *(Concept 2, section 2.)*

B) The country-listing query doesn't align with the shard key, so it would otherwise fan out to every shard. Fix with a **secondary index/lookup table** — a separate `country -> [user_id, ...]` mapping (or a search-optimized store like Elasticsearch for this and the email-search case) rather than resharding the primary table around a query that's only 15% of traffic.

C) A country with 40% of users sharded by `user_id` doesn't create a hot SHARD (since `user_id` hashing is independent of country) — but it DOES mean the secondary country-index lookup for that country returns a huge result set, which is its own scaling problem (pagination, or a pre-aggregated country-count rollup rather than materializing all 200M user IDs at query time).

D) `500,000,000 / 50,000,000 = 10 shards`.

*(Concept 2, section 2 — sharding strategy selection.)*

</details>

---

## Exercise 5: Fix the Data Skew

Joining `orders` with `products`. Product ID `GIFT_CARD` appears in 30% of all orders (a hot key) and is bottlenecking one partition/task.

Design a salting solution that distributes the hot key across N buckets, and state what has to change on the OTHER side of the join for it to still match correctly.

<details>
<summary>Reference answer (try it yourself first)</summary>

Salt the hot key on the `orders` side:
```python
if product_id == "GIFT_CARD":
    salted_key = f"{product_id}_salt{random.randint(0, N-1)}"
else:
    salted_key = product_id
```
This alone breaks the join — `products` only has ONE `GIFT_CARD` row, with no salt suffix to match against. The other required half: explode the `GIFT_CARD` row in `products` into N copies, one per salt value (`GIFT_CARD_salt0` ... `GIFT_CARD_saltN-1`), so every salted order key has a matching product row. Only the hot key needs this treatment — salting every key would spread ALL rows across N buckets unnecessarily, multiplying the small-side table size for no benefit. *(Concept 3, section 5; full mechanics with real code in `../../spark_course/concepts/08_salting.md`.)*

</details>

---

## Exercise 6: Trade-off Analysis — Monolith vs. Microservice Pipeline

Option A: one monolithic Spark job, everything end-to-end, simple to deploy, but a failure re-runs everything. Option B: an Airflow DAG with 10 tasks, each stage separate, retryable independently, more complex to deploy/monitor.

For each criterion, pick A or B and justify: (1) operational simplicity, (2) failure recovery speed, (3) resource efficiency, (4) development velocity for a team of 5, (5) observability/debugging.

<details>
<summary>Reference answer (try it yourself first)</summary>

1. **Operational simplicity: A.** One deployable artifact, one thing to monitor for "did it run."
2. **Failure recovery speed: B.** A failure in stage 7 of 10 re-runs only stage 7, not the whole pipeline from scratch — meaningfully faster recovery once the pipeline is non-trivial in length/cost.
3. **Resource efficiency: depends on stage shape — usually B.** Separate tasks can be sized independently (a light validation step doesn't need the same executor count as a heavy join step); a monolith sizes everything for its heaviest stage the whole time it runs.
4. **Development velocity for a team of 5: B**, once the team is bigger than ~2-3 — separate tasks let different engineers own and deploy different stages without stepping on each other; a monolith becomes a merge-conflict and blast-radius bottleneck as the team grows.
5. **Observability/debugging: B** — per-task logs, retries, and timing in Airflow's UI localize a failure to one stage; a monolith's single log stream makes "which part of this 45-minute job actually failed" a harder question.

The overall shape of this answer: A wins on simplicity alone, B wins on almost everything that matters past a small scale — which is exactly why the standard trajectory is "start monolithic, break into an orchestrated DAG once a stage needs independent retry/scaling/ownership," not "always pick the more sophisticated option."

</details>

---

## Exercise 7: Implement SCD Type 2 for a Customer Change

`dim_customers(customer_key, customer_id, name, city, effective_date, expiry_date, is_current)`. Customer `C001` (Alice, New York) moves to San Francisco on `2024-06-15`. Write the two-step update.

<details>
<summary>Reference answer (try it yourself first)</summary>

```sql
-- Step 1: expire the current row
UPDATE dim_customers
SET expiry_date = '2024-06-15', is_current = 0
WHERE customer_id = 'C001' AND is_current = 1;

-- Step 2: insert the new current row
INSERT INTO dim_customers (customer_id, name, city, effective_date, expiry_date, is_current)
VALUES ('C001', 'Alice', 'San Francisco', '2024-06-15', '9999-12-31', 1);
```

Result: two rows for `C001` — the New York row now closed (`expiry_date = 2024-06-15`, `is_current = 0`), the San Francisco row open-ended and current. Any fact table joining on the surrogate `customer_key` that was current AT THE TIME of a historical event keeps pointing at the New York row — which is the entire point of Type 2 (see `../../de_rewamp/data_modeling/` for the full SCD taxonomy; this exercise is the mechanical implementation of a decision that topic covers in depth).

</details>

---

## Exercise 8: Backpressure with Adaptive Rate Limiting

Build a producer-consumer system: producer generates bursty events, consumer processes at a fixed rate, and when the buffer exceeds a threshold the PRODUCER slows itself down (not just drops). Track processed/dropped counts.

<details>
<summary>Reference answer (try it yourself first)</summary>

```python
buffer = deque(maxlen=20)
processed = dropped = 0

for tick in range(30):
    burst = 15 if tick % 5 == 0 else 5          # bursty producer

    if len(buffer) > 14:                        # 70% full -> backpressure signal
        burst = max(1, burst // 3)               # producer throttles itself

    for _ in range(burst):
        if len(buffer) < buffer.maxlen:
            buffer.append({"tick": tick})
        else:
            dropped += 1                          # buffer still full -> drop

    for _ in range(min(5, len(buffer))):          # consumer: steady rate
        buffer.popleft()
        processed += 1
```

The key design point: the buffer-depth check happens on the PRODUCER side before it even tries to enqueue — this is what makes it "adaptive rate limiting" rather than plain buffering. Plain buffering only reacts after the buffer is already full (dropping); adaptive throttling reduces the input rate proactively once the buffer crosses a threshold, reducing (though not eliminating) how often the drop path is hit at all. *(Concept 2, section 7.)*

</details>

---

## Exercise 9: Demonstrate Partition Pruning

Build a partitioned structure (a dict keyed by month, 10,000 records/month). Compare the time and records scanned for a full scan vs. a query pruned to a single month.

<details>
<summary>Reference answer (try it yourself first)</summary>

```python
partitioned = {f"2024-{m:02d}": [...10_000 records...] for m in range(1, 13)}
# 120,000 total records across 12 partitions

# Full scan: iterate every partition
full_scan_records_touched = 120_000

# Pruned scan: only touch the one partition the filter matches
pruned_scan_records_touched = 10_000

# Reduction: 12x fewer records touched, and proportionally faster
```

The point isn't the toy numbers — it's that partition pruning's speedup scales with the NUMBER of partitions your query can skip, which is exactly why "partition by the column your queries actually filter on" (Concept 2, section 6) is one of the highest-leverage, lowest-cost design decisions in a data lake.

</details>

---

## Exercise 10: Mini System Design — Real-Time Leaderboard (SPADE)

"Design a real-time leaderboard for an online game." Requirements: 10M players, ~100K concurrent at peak, scores update every 2-5 min/player, leaderboard must reflect updates within 5 seconds, supports global top-100 + friend leaderboard + regional leaderboard, plus historical daily/weekly/monthly views.

Use SPADE (Scope, Pipeline, Architecture, Data Model, Edge Cases) to structure a full answer before expanding the reference.

<details>
<summary>Reference answer (try it yourself first)</summary>

**S — Scope:** ~20K score updates/sec at peak (100K concurrent / avg 5s between actions, rounded for the estimate); hard 5-second freshness requirement; four leaderboard views (global, friends, regional, historical) with very different query shapes.

**P — Pipeline:** game servers emit score events → Kafka → stream processor updates a live ranked structure → periodic snapshot to a durable store for historical views.

**A — Architecture: Kappa.** All input is naturally event-shaped (a score update IS an event) and a single streaming layer keeps things simple — this avoids Lambda's two-codepath cost, and reprocessing (replaying Kafka) is affordable here since the working set (top players) is small relative to the full log.

**D — Data model:** Redis Sorted Sets (`ZADD leaderboard:global <score> <player_id>`) for O(log N) live updates and O(log N + M) range queries — sorted sets are purpose-built for exactly this "always ranked, always current" access pattern. Regional leaderboards are separate sorted sets keyed by region. Friend leaderboards are computed at query time (intersect the global/regional sorted set with the requesting player's friend list) rather than maintained continuously per-player, since maintaining a live sorted set PER PLAYER for friends doesn't scale to 10M players. Historical views are periodic (daily/weekly/monthly) snapshots written to a durable store (Postgres or the warehouse), not served from the live Redis structure at all.

**E — Edge cases:**
- **Tie-breaking:** compose the sort key as `score * 1e9 + recency_timestamp` so ties resolve by whoever reached that score first (or most recently, per product decision) — a raw score-only sort key has undefined tie order.
- **Whale friend lists:** a player with 5,000 friends can't have their friend leaderboard computed as a live per-request intersection cheaply at scale — pre-compute/cache it for high-friend-count accounts specifically, rather than optimizing for the common case that doesn't need it.
- **Redis memory:** don't keep all 10M players in the live sorted set — keep the top N (10,000, tunable) live, and serve "your rank" for players outside that window via a cheaper on-demand computation (rank estimate from the durable store) rather than paying live-memory cost for players nobody is browsing to.
- **Recovery:** if the live store is lost, replay the Kafka log from the last durable snapshot to rebuild it — this is exactly Kappa's replay property earning its keep.

</details>
