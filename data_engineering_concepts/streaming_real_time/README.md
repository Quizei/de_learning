# Streaming & Real-Time Data

## Why This Matters

Batch processing has a delay built into it by design — it collects data, then processes it on a schedule. Whenever a business decision genuinely can't wait for the next scheduled run (fraud detection, a live dashboard driving an in-the-moment decision, an inventory system that has to react to a sale before overselling), the pipeline has to be streaming instead. Kafka is the backbone most of the industry has standardized on for this, and "explain how Kafka guarantees ordering," "design a real-time pipeline for X," and "what's the difference between at-least-once and exactly-once" are asked in some form in nearly every data engineering interview loop that touches real-time systems at all.

The harder, more interview-relevant skill this topic drills isn't Kafka trivia — it's the reasoning that separates a streaming design that looks fine in a whiteboard sketch from one that survives out-of-order events, a consumer crash mid-batch, a hot partition key, or a stakeholder who asked for "real-time" without actually needing it. That reasoning — event time vs. processing time, windowing and watermarks, delivery guarantees, and when *not* to reach for streaming at all — is what this folder is built to teach.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: read top to bottom like notes, with prose explaining the "why," an ASCII diagram or worked timeline where one clarifies the mechanism, and real, runnable stdlib Python showing the pattern and its actual output. No Kafka installation, no external services — every mechanism (partitions, consumer groups, watermarks) is simulated closely enough in plain Python that the behavior, and the gotchas, transfer directly to the real thing.
- `practice/` — `exercises.md` (10 build-it-yourself drills, hidden-answer format) and `coding_problems.md` (2 harder, interview-length problems — sorted-stream deduplication in O(1) memory, and a windowed stream-processing engine with real late-data handling — each with a problem statement, sample input/output, and a hidden, verified solution).
- `interview_questions/` — a five-file, mostly code-free drill covering every shape a streaming interview question tends to take: worked design/diagnosis scenarios, rapid-fire definitions, critique-a-broken-pipeline, curveball trade-offs, and a dedicated drill on recognizing when "real-time" isn't actually the right requirement. See `interview_questions/README.md` for the full breakdown.
- `projects/` — one capstone project brief (`stream_processor.md`) that asks you to build a small, Kafka-inspired stream processing engine — partitioned broker, consumer groups, windowed aggregation, watermark-driven late-data handling, and exactly-once dedup — as one working system, not five separate exercises.

Every `concepts/*.md` file follows the same shape: a **Covers** list, one `##`/`###` section per sub-topic with a prose "why," an ASCII diagram or worked timeline where one helps, real runnable code, and a worked example with its actual output shown in a comment. Every code block is copy-pasteable stdlib Python — paste it into a `python3` shell and it runs exactly as shown.

---

## How to Use This Folder

Work through it in this order:

1. **`concepts/`** (01 → 05) — the vocabulary and mechanics: what event time actually buys you, how Kafka's partitioning and consumer groups work, how windowing and watermarks handle out-of-order and late data, event-driven architecture patterns, and what "exactly-once" really means. Read these first; everything else assumes this vocabulary, especially the windowing/watermark file, which most other files cross-reference directly.
2. **`practice/exercises.md`**, then **`practice/coding_problems.md`** — apply the vocabulary directly: implement tumbling/sliding/session windows, a watermark filter, Kafka-style partition assignment, an idempotent processor, and (in the coding problems) a full watermark-driven windowed engine with a late-events side output. Commit to your own answer before expanding each hidden solution.
3. **`interview_questions/`** — the conversation an interviewer actually scores, rehearsed end to end: clarifying questions → design shape → failure handling → narrated trade-offs, across several realistic scenarios (including a live diagnosis of a rebalancing consumer group), plus rapid-fire definitions, critique-the-broken-pipeline cases, curveball follow-ups, and a dedicated drill on the single most commonly-skipped question in this whole topic: does this actually need to be real-time at all?
4. **`projects/stream_processor.md`** — a capstone that asks you to build a small, multi-part streaming system and prove its two hardest properties directly: correct results under out-of-order/late/duplicate input, and memory that stays bounded no matter how long the stream runs.

---

## Topics Covered

### Concepts

| # | Topic | File | Interview question it answers |
|---|-------|------|-------------------------------|
| 1 | Streaming Fundamentals | `concepts/01_streaming_fundamentals.md` | "Explain the difference between batch and stream processing." / "Why does event time matter?" |
| 2 | Kafka Concepts | `concepts/02_kafka_concepts.md` | "How does Kafka guarantee ordering?" / "What are consumer groups, and why do they matter?" |
| 3 | Windowing & Watermarks | `concepts/03_windowing_and_watermarks.md` | "Design a windowed aggregation." / "How do you handle late-arriving data?" |
| 4 | Event-Driven Architecture | `concepts/04_event_driven_architecture.md` | "What is event sourcing?" / "How does CQRS work?" / "How do you evolve an event schema safely?" |
| 5 | Exactly-Once Semantics | `concepts/05_exactly_once_semantics.md` | "How do you achieve exactly-once processing?" / "At-most-once vs. at-least-once vs. exactly-once?" |

### Interview Questions

`interview_questions/` is a five-file drill:

1. [Worked Design & Diagnosis Scenarios](interview_questions/01_worked_scenarios.md) — full walkthroughs: a rolling 5-minute CTR pipeline, live diagnosis of a constantly-rebalancing consumer group, exactly-once payment processing end to end, and a real-time fraud-detection design to try yourself
2. [Rapid-Fire Q&A](interview_questions/02_rapid_fire_qna.md) — fast definitional questions, no scenario attached
3. [Critique & Debug](interview_questions/03_critique_and_debug.md) — classic streaming bugs: committing offsets before processing, a windowed aggregation with no watermark, a hot partition key, at-least-once silently double-processing a non-idempotent sink, and a "real-time" dashboard that's actually just slow batch
4. [Curveballs & Trade-offs](interview_questions/04_curveballs_tradeoffs.md) — mid-conversation follow-ups: scaling past one-consumer-per-partition, state too large for memory, exactly-once across two different systems, hard deletes with no CDC access, breaking schema changes, testing a system that runs forever
5. [Does This Even Need to Be Real-Time?](interview_questions/05_does_this_need_to_be_real_time.md) — a dedicated drill on the meta-question underneath most streaming requests: recognizing when the right answer is "no, a more frequent batch job is fine"

See `interview_questions/README.md` for how to use the set.

---

## Key Mental Models

### 1. Streaming Is a Different Correctness Problem, Not Just a Faster Batch

```
Batch:     collect everything -> sort/join/aggregate with the full dataset in view -> done, rerun if wrong
Streaming: process forever, never seeing the future -> must decide, continuously,
           when a partial result is "done enough" to emit -- that decision is what
           windows and watermarks exist to make possible.
```

### 2. Kafka's Ordering Guarantee Has a Very Specific Scope

```
Same key  -> same partition -> strictly ordered within that partition.
Different keys -> no ordering relationship to each other, ever, no matter what.

Partitioning is a design decision, not an implementation detail: too few
distinct keys relative to partition count creates a hot partition that
caps throughput regardless of how many partitions the topic has.
```

### 3. A Watermark Decides When a Window Is Safe to Forget

```
watermark = max_event_time_seen - allowed_lateness

An event is late if its event_time < the CURRENT watermark -- not merely
"has its window technically closed yet." No watermark at all means either
a window that never closes, or unbounded memory as every window ever
opened is held in memory forever.
```

### 4. Exactly-Once Is an Effect, Not a Deliverable Guarantee Over the Network

```
True exactly-once DELIVERY isn't achievable -- a sender can't always tell
"it failed" from "it succeeded but the ack was lost."

What's achievable: at-least-once delivery (retry freely) + idempotent
processing (a duplicate has no additional effect) = exactly-once EFFECT.
```

### 5. "Real-Time" Is a Requirement to Interrogate, Not Accept at Face Value

```
Ask: what decision or action actually depends on this freshness?
Ask: how fresh, as an actual number -- not the word "real-time" itself?
Most requests phrased as "real-time" tolerate minutes and are better
served by a more frequent batch job than by adopting streaming
infrastructure's ongoing operational cost.
```

---

## Practice Goals

- [ ] Implement tumbling, sliding, and session window aggregation, and explain when each is the right fit
- [ ] Implement a watermark-based late-data filter, and explain the difference between "late relative to the watermark" and "the window has technically closed"
- [ ] Implement Kafka-style key-based partition assignment and consumer-group rebalancing, including the "more consumers than partitions" and "hot partition key" edge cases
- [ ] Implement an idempotent/deduplicating processor, and explain why exactly-once *delivery* over a network isn't achievable but exactly-once *effect* is
- [ ] Design an event schema with a real backward-compatible evolution path (upcasting an old-shape event into the current shape)
- [ ] Run a full "design a real-time pipeline for X" conversation end to end, narrating clarifying questions, windowing/partitioning/delivery-guarantee decisions, and trade-offs without writing full code
- [ ] Diagnose a broken streaming system from a plain-English description of its symptom (a rebalancing consumer group, a memory-leaking aggregation, a double-charged customer) — not from reading a stack trace
- [ ] Push back, with reasoning, on a stated "real-time" requirement that doesn't actually need streaming infrastructure

---

## Prerequisites

`etl_elt_patterns` is helpful, not required — several scenarios and cross-references in this topic assume its Change Data Capture concept (`etl_elt_patterns/concepts/05_change_data_capture.md`), since a streaming pipeline very often consumes a CDC feed as its source, and its idempotency/reliability concept (`etl_elt_patterns/concepts/06_idempotency_reliability.md`), since "exactly-once" in streaming is the same underlying idea as idempotent batch loading, applied per-message instead of per-batch. `data_modeling` is referenced occasionally (mini-dimensions, conformed dimensions) where a streaming design curveball rhymes directly with a modeling one. Neither is required to start: every concept file here is self-contained Markdown with runnable stdlib Python — no Kafka installation, no warehouse, no external service required. Any `python3` is enough to run every example in this folder yourself.
