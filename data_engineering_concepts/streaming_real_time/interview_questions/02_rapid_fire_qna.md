# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design and diagnosis conversations. This file is the other interview mode: **fast, direct definitional questions** with no scenario attached — the kind asked in a phone screen, or dropped mid-conversation to check you actually understand a term you just used. Answer each one out loud in under 30 seconds before reading the model answer.

Every term here is demonstrated somewhere in `concepts/` or in file 1 — the cross-references point back to where it showed up worked in full.

---

## Streaming Fundamentals

**Q: Batch vs. stream processing — the one-sentence distinction?**
> Batch processes a finite, bounded dataset on a schedule; stream processing handles an infinite, unbounded dataset continuously, reacting to each event (or small group of events) as it arrives. `concepts/01_streaming_fundamentals.md`.

**Q: Micro-batch vs. true streaming?**
> Micro-batch (Spark Structured Streaming's default) collects events over a short fixed interval and processes them together as a small batch; true streaming (Flink, Kafka Streams) processes each event individually the instant it arrives. A "2-second trigger" system is micro-batch, not true streaming, even though both handle unbounded data.

**Q: Event time vs. processing time — why does it matter which one you window on?**
> Event time is when something actually happened; processing time is when the system happens to handle it. They diverge under network delay, retries, and out-of-order arrival. Windowing on processing time makes results depend on incidental system behavior rather than the business event itself — not reproducible, and wrong the moment anything arrives late. Always window on event time. `concepts/01_streaming_fundamentals.md`, section 3.

---

## Windowing & Watermarks

**Q: Name the three window types and the one-line distinguishing fact for each.**
> Tumbling — fixed size, non-overlapping, every event belongs to exactly one window. Sliding — fixed size, overlapping (slide < size), one event can belong to several windows. Session — dynamic size, closed by an inactivity gap rather than a fixed duration; its boundary genuinely isn't knowable until the gap has elapsed. `concepts/03_windowing_and_watermarks.md`.

**Q: What is a watermark, in one sentence?**
> The stream processor's own running estimate, in event time, of how far along it has gotten — computed as `max_event_time_seen - allowed_lateness` — used to decide when it's safe to consider a window "done" and emit its result.

**Q: What determines whether an event is "late"?**
> Its event time compared against the *current watermark* at the moment it arrives, not whether its window has technically closed yet — the watermark is one global "I won't wait for anything before this" line, and `allowed_lateness` controls how generous that line is. Worked in full, including the exact arithmetic, in `concepts/03_windowing_and_watermarks.md`, section 5.

**Q: Name the three strategies for handling late data once identified.**
> Drop it (simplest, accepts small inaccuracy); update and re-emit the window's result (correct, but downstream consumers must handle a result that can change after they first saw it); side output (route to a separate stream for out-of-band handling — usually the right default when correctness needs to be auditable).

**Q: What goes wrong with a windowed aggregation that has no watermark at all?**
> Either it never emits a result (waiting forever for events that might still be late), or it falls back to processing-time-based closing, reintroducing every problem event-time processing exists to solve. Worse, with nothing ever telling it a window is safe to forget, its state grows without bound — every window ever opened stays in memory forever. Drilled as a diagnosis case in `interview_questions/03_critique_and_debug.md`.

---

## Kafka Mechanics

**Q: What guarantees does Kafka actually make about message ordering?**
> Messages with the same key always land in the same partition; within one partition, order is strict; across partitions, there is no ordering guarantee at all. "Kafka guarantees ordering" without qualifying "within a partition, for a given key" is an incomplete — and interview-losing — answer.

**Q: How does a producer decide which partition a message goes to?**
> By default, `hash(key) % num_partitions` — same key, same partition, every time (guaranteeing per-key ordering). Messages with no key are spread round-robin. `concepts/02_kafka_concepts.md`, section 2.

**Q: What are the three Kafka `acks` levels, and what does each trade off?**
> `acks=0`: fire-and-forget, fastest, can silently lose messages. `acks=1`: the partition leader acknowledges, balanced. `acks=all`: every in-sync replica acknowledges, slowest but safest — no acknowledged message is lost as long as at least one replica survives.

**Q: What is a consumer group, and what's the one guarantee that defines it?**
> A set of consumers cooperatively reading a topic, where each partition is assigned to exactly one consumer within the group at any given time. This is the fact that explains both horizontal scaling (add consumers up to the partition count) and its limit (consumers beyond the partition count sit idle — more consumers doesn't mean more throughput past that point).

**Q: Why would a consumer group rebalance even if no consumer actually crashed?**
> A consumer that doesn't call `poll()` within `max.poll.interval.ms` — because its per-batch processing is slow — looks exactly like a dead consumer to the broker and gets evicted, triggering a rebalance. This is the most common real-world cause of a group that rebalances constantly with no visible crash. Fully diagnosed in `interview_questions/01_worked_scenarios.md`, Scenario B.

**Q: What causes a "hot partition," and why is it a problem?**
> A partition key with too little cardinality relative to the partition count — e.g. a fixed set of 4 region values on a 50-partition topic — sends most traffic to a small number of partitions regardless of how many partitions the topic has, capping throughput at whatever those few partitions can handle while the rest sit mostly idle. `concepts/02_kafka_concepts.md`, section 4; diagnosed as a critique case in `interview_questions/03_critique_and_debug.md`.

**Q: Three Kafka retention policies, one line each?**
> Time-based (delete after a fixed age, the default); size-based (delete oldest once a partition exceeds a byte limit); log compaction (`cleanup.policy=compact` — keep only the latest value per key, forever, rather than expiring by age or size). Compaction is what makes Kafka viable as a durable CDC/changelog backbone.

---

## Delivery Guarantees & Exactly-Once

**Q: Define at-most-once, at-least-once, and exactly-once in one line each.**
> At-most-once: fire and forget, can lose messages, never duplicates. At-least-once: retry until acknowledged, never loses messages, can duplicate. Exactly-once: idempotent producer + transactions, no loss and no duplication. `concepts/05_exactly_once_semantics.md`.

**Q: Is true exactly-once delivery actually achievable over a network?**
> No — a sender can never fully distinguish "the request failed" from "it succeeded but the response was lost," so it can never be certain whether to retry. What's achievable, and what Kafka actually provides, is exactly-once *effect*: at-least-once delivery combined with idempotent processing that makes a duplicate harmless. This distinction — effect vs. delivery — is the single most commonly-missed nuance in this whole topic.

**Q: How does Kafka's idempotent producer actually detect a duplicate?**
> Every message carries a `(producer_id, sequence_number)`. The broker tracks the highest sequence number accepted per producer and silently rejects any retry whose sequence number it's already seen.

**Q: If infrastructure-level exactly-once isn't available end-to-end (e.g. writing into a non-transactional external system), what's the fallback?**
> Application-level deduplication: an idempotency key (simplest, needs a key in the message), content-hash dedup (no key needed, but can't distinguish a legitimate repeat from a true duplicate), or a timestamped/versioned upsert (natural for entity state, needs a comparable version column). `concepts/05_exactly_once_semantics.md`, section 4.

**Q: Saga pattern vs. two-phase commit — when do you reach for each?**
> 2PC gives strong consistency but blocks every participant during the protocol — it's the mechanism Kafka uses internally for its own transactional writes. Across independently-owned services, a saga (a sequence of local transactions with compensating actions on failure) is almost always preferred: higher availability, eventual rather than strong consistency, no cross-service blocking.

---

## Event-Driven Architecture

**Q: What is event sourcing, in one sentence?**
> Storing the sequence of events that happened, rather than derived current state, and rebuilding state by replaying those events — giving a complete audit trail and temporal queries ("what was this at time T") at the cost of needing periodic snapshots once history gets long. `concepts/04_event_driven_architecture.md`.

**Q: What does CQRS actually separate, and why rebuild read models instead of migrating them?**
> The write model (append-only events) from the read model(s) (query-optimized projections built by consuming those events). Read models are disposable by design — a new reporting need means writing a new projection and replaying history into it, not a risky live-data migration.

**Q: What's the practical cost of pub/sub's decoupling, and what pays for it?**
> Publishers and subscribers agree on nothing except the event's shape — which means schema evolution (backward/forward compatibility, upcasting old events, ideally enforced by a schema registry) is what actually keeps that decoupling safe over time, not a nice-to-have on top of it.

**Q: Backward-compatible vs. forward-compatible, one line each?**
> Backward compatible: new consumer code can correctly read data written by old producer code (achieved by adding optional fields with defaults). Forward compatible: old consumer code can correctly read data written by new producer code (achieved by ignoring unknown fields rather than erroring on them).
