# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

A question type that doesn't fit a full scenario or a flash-card definition — the interviewer takes whatever you just designed (in [file 1](01_worked_scenarios.md)) and pushes on one assumption. There's rarely one "correct" answer here; what's scored is whether you reason through the trade-off out loud instead of freezing or giving a one-word answer. Try answering each before expanding the model answer.

---

**Curveball: "Your consumer group needs to process more throughput. You've already got one consumer per partition. What now?"**

<details>
<summary>Model answer</summary>

Adding more consumers past one-per-partition adds nothing — Kafka guarantees exactly one consumer per partition within a group, so extra consumers just sit idle (`concepts/02_kafka_concepts.md`, section 3). The actual lever is increasing the topic's partition count, which requires re-examining the partition key: more partitions only help if the key has enough cardinality to actually spread across them (the hot-partition failure mode in `interview_questions/03_critique_and_debug.md`, Case 3). It's also worth naming the operational cost of increasing partitions on a live topic: existing consumers rebalance, and if ordering matters per-key, any messages already in flight for a key that moves to a different partition need care — this isn't a free, instant lever, it's a real migration with its own moment of disruption.

</details>

---

**Curveball: "Your windowed aggregation's state doesn't fit in memory anymore — the business added a new dimension to group by, and per-key cardinality exploded 100x. What changes?"**

<details>
<summary>Model answer</summary>

This is the streaming analog of dimension explosion, and the fix rhymes with the fix there: don't try to keep every key's full window state resident at once. Real streaming engines back windowed state with an embedded, disk-backed store (Flink's RocksDB state backend, Kafka Streams' RocksDB-backed state stores) specifically so state size isn't bounded by RAM — the trade-off is slower per-key access (disk vs. memory) in exchange for scaling past what fits in memory. If that's still not enough, the next lever is reconsidering the window itself: is every one of the new dimension's values actually queried, or would a coarser grouping (bucketing a high-cardinality dimension into ranges, the streaming version of a mini-dimension) satisfy the actual requirement at a fraction of the state size? Naming both levers — a disk-backed state store as the infrastructure answer, and reconsidering cardinality as the modeling answer — shows you're not treating this as purely an ops problem.

</details>

---

**Curveball: "You need exactly-once processing, but it spans two different systems — Kafka on one side, a Postgres table on the other. Kafka transactions don't reach into Postgres. What do you do?"**

<details>
<summary>Model answer</summary>

Kafka's transactional guarantee is scoped to Kafka itself (atomic produce + offset commit) — it structurally cannot make an external system's write part of the same atomic unit. The standard answer is the same one used for the payment-processing scenario in `interview_questions/01_worked_scenarios.md`: give the Postgres write a stable natural key and make it an idempotent upsert (`INSERT ... ON CONFLICT DO UPDATE`) keyed on that identifier, so however many times the same event gets reprocessed — at-least-once redelivery, a crash-and-retry, whatever — the write converges to the same end state rather than compounding. This reframes the problem from "make two systems commit atomically together" (genuinely hard, arguably impossible without a distributed transaction coordinator neither side wants to pay for) to "make the downstream write idempotent so at-least-once delivery is harmless" — a much cheaper, and in practice much more common, way to get the same *effect* as cross-system exactly-once.

</details>

---

**Curveball: "The source system for this stream can emit hard deletes — a record just vanishes, no delete event, no tombstone. How does your streaming pipeline even know?"**

<details>
<summary>Model answer</summary>

It doesn't, not from the stream alone — a stream of "here's what changed" events structurally cannot represent "this thing used to exist and now doesn't" if no event was ever emitted for the deletion. This is precisely why `etl_elt_patterns/concepts/05_change_data_capture.md` treats CDC as its own topic distinct from timestamp-based incremental extraction: log-based or trigger-based CDC captures a delete as an explicit event (a tombstone) specifically because polling/timestamp approaches can't. If the source genuinely can't emit CDC-quality delete events, the fallback is a periodic reconciliation pass — snapshot the source's current key set, diff it against what the streaming pipeline believes exists downstream, and soft-delete anything present downstream but absent from the latest source snapshot. That's a real architectural admission: a "purely streaming, always current" design can't fully solve this on its own, and a batch-style reconciliation safety net is a legitimate, common piece of an otherwise-streaming pipeline, not a failure to be purely event-driven.

</details>

---

**Curveball: "Your event schema needs a breaking change — a field is being removed, not just added — on a topic with several independent consumers you don't control. What's the plan?"**

<details>
<summary>Model answer</summary>

Never actually remove the field in a single, immediate change — that's the direct violation of the backward-compatibility rule from `concepts/04_event_driven_architecture.md`, section 4, and on a live stream there's no "next batch run" boundary to catch consumers up before more data flows; a break here is live and immediate for every consumer still expecting the old shape. The standard path: introduce the new shape as a new, additively-compatible version first (mark the old field deprecated but keep populating it alongside whatever replaces it), let every known consumer migrate to the new shape at their own pace, monitor for consumption of the deprecated field dropping to zero, and only then — once it's verified nothing still depends on it — actually stop populating it. This is slower than a hard cutover, and that's the point: the cost of getting it wrong is a live incident across every consumer you don't directly control, not a controlled batch replay.

</details>

---

**Curveball: "How do you test a streaming pipeline at all, given it's supposed to run forever and react to things as they happen?"**

<details>
<summary>Model answer</summary>

The "runs forever" property is actually not what makes testing hard — the same windowing/watermark logic that runs continuously in production can be driven deterministically in a test by feeding it a fixed, hand-constructed sequence of events with explicit event times (exactly the pattern every code example in `concepts/03_windowing_and_watermarks.md` uses), rather than needing wall-clock time to actually pass. The genuinely hard part is testing the *late-data and out-of-order* paths specifically, since those are the cases production will eventually hit but a happy-path test naturally won't construct on its own — a real test suite for a streaming pipeline should deliberately include: events delivered out of event-time order, at least one event that arrives after its window's watermark has passed (to exercise the late-data path, not just the on-time path), and a duplicate delivery of the same event (to exercise the idempotency/dedup path). A pipeline whose tests only ever feed it perfectly-ordered, on-time, non-duplicated events hasn't actually tested the parts of the design that exist specifically to handle the case where reality doesn't cooperate.

</details>

---

**Curveball: "Leadership now wants this pipeline's business logic changed frequently — new fraud rules added weekly. Does your streaming architecture accommodate that, or does every rule change mean redeploying the whole pipeline?"**

<details>
<summary>Model answer</summary>

If the rules are hard-coded into the stream-processing job's own logic, yes — every change means a redeploy, and a redeploy of a stateful streaming job is a real operational event (state migration or a cold restart, depending on the engine and how state is checkpointed), not a quick config push. The fix, if frequent rule changes are a known requirement upfront, is to design the rules themselves as *data* the pipeline reads rather than *code* the pipeline is compiled with — a rules table or a low-latency lookup the streaming job consults per event, updated independently of the pipeline's own deploy cycle. This is the same design instinct as the marketing-attribution bridge table in `data_modeling/interview_questions/01_worked_scenarios.md` — keeping "the logic that changes often" as pluggable, data-driven state instead of baking it into the thing that changes rarely (the pipeline's own code).

</details>
