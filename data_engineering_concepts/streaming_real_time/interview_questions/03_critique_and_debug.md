# 3. Critique & Debug: "What's Wrong With This?"

Part of the [Interview Questions](README.md) series.

A different interview mode from [file 1](01_worked_scenarios.md): instead of "design something from scratch," you're handed a description of a running (or recently-run) streaming system and asked **"what's wrong with this?"** This tests whether you can *read* a streaming design critically and spot the failure mode from a plain-English description — the way it would actually be described to you out loud in an interview, not from reading a stack trace.

Read the symptom, form your diagnosis, then expand the debrief.

---

## Case 1: The Consumer That Loses Messages on Crash

**Setup:** A consumer reads from a topic with `enable.auto.commit=true` and a short auto-commit interval. It polls a batch of messages, commits the offset almost immediately (auto-commit fires on its timer, independent of processing), and *then* processes the batch — writing results to a downstream database. One day the consumer process gets OOM-killed partway through processing a batch. On restart, those in-flight messages are never seen again.

<details>
<summary>Debrief</summary>

**Diagnosis:** the offset was committed *before* processing completed, not after. Auto-commit on a timer commits whatever offset the consumer has read up to, regardless of whether that data has actually been durably handled yet. When the crash happens between "offset committed" and "processing finished," the consumer group's bookmark says "everything up to here is done" — which is a lie — and on restart, the consumer resumes from that (already-advanced) offset, permanently skipping the messages that were in flight when it died.

**Fix:** disable auto-commit and commit the offset manually, *after* the batch's processing (and any downstream write) has actually completed and been durably applied. This is the exact same principle as `etl_elt_patterns/concepts/06_idempotency_reliability.md`'s "a watermark only advances after the load it describes actually succeeds" — an offset is a watermark, and the rule is identical: never advance the bookmark before the work it describes is done.

**The interview tell:** recognizing that this isn't really a "Kafka bug" or a rare edge case — it's the direct, guaranteed consequence of committing before processing, and it will lose data on *every* crash that happens in that window, not just unlucky ones. Naming "commit-before-process" as the root cause, rather than "sometimes messages get lost," is what separates a real diagnosis from a vague one.

</details>

---

## Case 2: The Windowed Aggregation With No Watermark

**Setup:** A tumbling-window aggregation counts events per 1-minute window, keyed on event time. It's been running in production for three months. Memory usage on the processing nodes has climbed steadily the entire time and now requires periodic manual restarts to avoid OOM. Windows do eventually "look right" when inspected, but results seem to update at unpredictable times, sometimes minutes after a window's nominal end.

<details>
<summary>Debrief</summary>

**Diagnosis:** there's no watermark — nothing is telling the system when a given 1-minute window is safe to consider "done" and forget. Every window ever opened stays in memory indefinitely, because the only signal that would let the system finalize and discard a window's state (a watermark advancing past that window's end) doesn't exist. Three months of continuous operation means three months' worth of window state, most of it for windows that were realistically "finished" within seconds of opening, sitting in memory forever. The "results eventually look right, at unpredictable times" symptom is what happens when window emission is instead triggered by some incidental signal (a periodic flush, memory pressure itself) rather than a principled event-time watermark.

**Fix:** add an explicit watermark policy (`watermark = max_event_time_seen - allowed_lateness`) and emit + discard a window's state once the watermark passes that window's end. This bounds memory to roughly "how many windows can plausibly still be open," a function of `allowed_lateness`, instead of "every window that has ever existed." Full mechanics and a worked timeline: `concepts/03_windowing_and_watermarks.md`, section 6.

**The interview tell:** connecting "unbounded memory growth over months" directly to "no watermark," rather than treating it as a generic memory-leak investigation. A candidate who immediately reaches for "watermark" as the specific missing piece — rather than proposing to profile the heap first — is showing they understand *why* windowed streaming state is bounded at all, not just that it should be.

</details>

---

## Case 3: The Hot Partition That Caps Throughput

**Setup:** An orders topic is provisioned with 50 partitions to handle a target throughput. Messages are keyed by `region`, and the system only ever operates across 4 regions. Despite 50 partitions, overall consumer-group throughput plateaus far below what 50 partitions of the same broker hardware should be able to sustain, and monitoring shows most partitions sitting nearly empty while a handful are consistently the busiest.

<details>
<summary>Debrief</summary>

**Diagnosis:** the partition key has far too little cardinality for the partition count. `hash(region) % 50` can only ever produce at most 4 distinct partition values, no matter how the data is shaped — the other 46 partitions structurally cannot receive any traffic at all under this keying scheme. The "busiest handful" aren't randomly hot; they're the *only* partitions that can ever be written to, and the system's real throughput ceiling is whatever those 4 partitions (not 50) can sustain.

**Fix:** re-key on something with enough cardinality to actually spread across the partition count — `customer_id` or `order_id`, for instance — while still preserving whatever ordering guarantee the business actually needs. If per-region ordering genuinely must be preserved (region is the *correct* ordering scope, not just a convenient key), the fix isn't "pick a different key" but "accept that a region-scoped ordering requirement caps your usable parallelism at the number of regions" and provision partitions accordingly — 50 partitions was never going to help without a keying scheme that could use them.

**The interview tell:** immediately connecting "plateaued throughput despite lots of partitions" to key cardinality, rather than proposing to add more partitions (which does nothing here) or more consumers (which also does nothing — see the rapid-fire question on consumer-group scaling limits). This is the same failure mode named directly in `concepts/02_kafka_concepts.md`, section 4.

</details>

---

## Case 4: At-Least-Once Silently Double-Processing a Non-Idempotent Sink

**Setup:** A stream processor reads inventory-adjustment events and applies each one as `UPDATE inventory SET quantity = quantity - :amount WHERE sku = :sku` against a warehouse database. The pipeline runs at-least-once (the default, sensible choice for this delivery layer). After a routine consumer restart during a deploy, someone notices several SKUs show inventory counts lower than a physical count justifies.

<details>
<summary>Debrief</summary>

**Diagnosis:** the sink operation itself is not idempotent. `quantity = quantity - amount` has a different effect every time it's applied — applying the same adjustment event twice (which at-least-once delivery explicitly allows, by design, on any reprocessing after a restart) doesn't produce the same end state as applying it once; it subtracts twice. At-least-once didn't fail here — it did exactly what it promises. The bug is that the *processing step* assumed idempotency it never actually had.

**Fix:** make the write itself idempotent, independent of the delivery guarantee. Two standard options: (a) an idempotency-key check before applying the write — track processed event IDs and skip a write whose event ID has already been applied (`concepts/05_exactly_once_semantics.md`, section 4); or (b) reframe the write itself to be idempotent by construction — e.g., store the *absolute* resulting quantity per adjustment event rather than a relative delta, so reapplying the same event sets the same final value rather than compounding a delta. Either way, the fix is at the processing/sink layer, not at the delivery layer — switching to "exactly-once" messaging wouldn't be free, and it still wouldn't be the right first thing to reach for if the sink write itself can be made naturally idempotent instead.

**The interview tell:** recognizing this as the general "at-least-once + non-idempotent operation = silent double effect" pattern rather than a one-off inventory bug, and knowing that the fix belongs in the write's own semantics (relative-delta vs. absolute-value, or an idempotency-key guard), not in reaching for a heavier delivery guarantee as the default reflex.

</details>

---

## Case 5: The "Real-Time" Dashboard That's Actually Just Slow Batch

**Setup:** A team built a "real-time" revenue dashboard by having a Spark Structured Streaming job trigger every 10 minutes, reading the last 10 minutes of a Kafka topic and writing an aggregate to a reporting table. Stakeholders are frustrated the dashboard "isn't really real-time" and want it faster, and the team's response has been to try to tune Spark's trigger interval down.

<details>
<summary>Debrief</summary>

**Diagnosis:** this was mislabeled from the start, not under-tuned. A 10-minute (or even 10-second) fixed trigger interval is micro-batch, and shrinking the interval doesn't change *what kind* of system it is — it only moves the latency number. If stakeholders' actual complaint is architectural ("this should react per-event, sub-second"), no amount of trigger-interval tuning turns a micro-batch job into true streaming; that requires a different processing model (Flink/Kafka Streams, per-event) entirely, not a smaller number in the same configuration.

**Fix:** first separate the two different questions being conflated — "is 10 minutes fast enough for this business need" (a latency/requirements question, answerable by tuning the trigger) versus "does this need true per-event streaming" (an architecture question, not solvable by tuning at all). If the actual requirement really is sub-second reaction, that's a rewrite onto a true-streaming engine, not a config change — and that's worth saying plainly rather than promising incremental tuning will eventually get there.

**The interview tell:** not accepting "make the trigger interval smaller" as an adequate answer to "make it real-time" without first asking what latency the business actually needs and whether the current architecture can reach it at all. This exact distinction — and how to have this conversation with a stakeholder before committing to an architecture — is drilled in full in `interview_questions/05_does_this_need_to_be_real_time.md`.

</details>
