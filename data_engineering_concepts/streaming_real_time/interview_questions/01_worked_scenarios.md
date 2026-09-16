# 1. Worked Design & Diagnosis Scenarios

Part of the [Interview Questions](README.md) series — see that index for the full taxonomy of question types and how the files fit together.

This file is deliberately **code-free** — no `CREATE` statements, no Python, no Kafka config. The point is to rehearse the *reasoning* an interviewer is actually scoring: how you scope the problem, name the shape of the pipeline, justify the trade-offs, and — for the diagnosis scenario — how you triage a symptom before jumping to a fix. Once the reasoning is solid, the implementation is what `concepts/` and `practice/` are for.

Four scenarios below: three design conversations and one live-diagnosis conversation, chosen because together they force nearly every idea in this topic — windowing, partitioning, exactly-once, consumer-group mechanics, and the batch-vs-streaming boundary.

---

## Scenario A: Rolling 5-Minute Click-Through-Rate per Ad Campaign

**Interviewer prompt:**
> "Design a real-time pipeline that computes a rolling 5-minute click-through-rate (CTR) per ad campaign, updated continuously, for a live dashboard the ad-ops team watches during a campaign launch."

### Step 1 — Clarifying questions

- **What events feed this?** Ad impressions and ad clicks, each carrying `campaign_id` and a timestamp. → Confirmed; two separate event types, or one event type with an `event_type` field — either works, ask which the actual event schema uses.
- **"Rolling," updated how often — every 5 minutes, or continuously recomputed?** → Interviewer clarifies: CTR should reflect "the last 5 minutes" and refresh every few seconds, not just once every 5 minutes. → This is a **sliding window**, not a tumbling one (`concepts/03_windowing_and_watermarks.md`), since the requirement is a trailing window recomputed frequently, not a series of disjoint 5-minute buckets.
- **How much lateness is tolerable?** Impressions/clicks can arrive up to ~30 seconds late due to mobile network conditions. → Sets `allowed_lateness ≈ 30s`, small relative to the 5-minute window, so it costs little in freshness.
- **What happens to a click that never gets a matching impression, or vice versa?** → Interviewer says: CTR is `clicks / impressions` per campaign in the window — a click without a matching impression still just counts as a click; there's no join required, only a per-event-type count. (Naming this — that this does *not* require joining click events to specific impression events — is worth stating explicitly, since a candidate too eager to build a stream-join can over-engineer a much simpler counting problem.)
- **Scale?** A few hundred campaigns, tens of thousands of events/second at launch spikes. → Confirms partitioning by `campaign_id` is fine — a few hundred distinct keys spread reasonably across a topic with a sane partition count, not a hot-partition risk (`concepts/02_kafka_concepts.md`, section 4).

### Step 2 — Declare the shape before naming any component

> "Two counters per campaign, maintained over a sliding 5-minute window: impression count and click count. CTR is derived, not stored directly, as `click_count / impression_count`, recomputed on every window slide."

This is the streaming analog of "declare the grain first" from dimensional modeling — before touching Kafka topic names or window APIs, state precisely what's being counted and over what window, because everything downstream (partition key choice, state size, emission frequency) follows from that one sentence.

### Step 3 — Partitioning and windowing decisions, narrated

> "Partition the events topic by `campaign_id` — every event for a given campaign lands in the same partition, which matters here because the aggregation is naturally scoped *per campaign* anyway, so partition-local state is sufficient; no cross-partition coordination is needed to compute one campaign's CTR.
>
> Window: sliding, size=5 minutes, slide=~10 seconds (frequent enough to feel 'live' on a dashboard without recomputing on every single event). Watermark: `allowed_lateness=30s`, small relative to the window size, so a late click or impression is still very likely to land inside the correct window before it closes.
>
> Emit: on every slide, write `{campaign_id, window_end, impressions, clicks, ctr}` to an output topic (or directly to whatever the dashboard reads from) — a periodic snapshot in spirit, one row per campaign per slide."

### Step 4 — Delivery guarantee, stated explicitly

> "This is a dashboard, not a payment ledger — at-least-once with idempotent aggregation is the right guarantee here, not full exactly-once transactions. Since the aggregation is a re-derivable count over a window (not an irreversible side effect like charging a card), a duplicate event being counted twice for one slide, if it ever happens, self-corrects on the next slide once the window moves past it — the business cost of an occasional slightly-off CTR blip on a dashboard is low enough that paying for Kafka transactions end-to-end isn't justified."

Naming this trade-off *unprompted* — that not every streaming pipeline needs exactly-once, and that the deciding factor is "is the effect of a duplicate reversible/self-correcting or not" — is exactly the reasoning `concepts/05_exactly_once_semantics.md` and `interview_questions/04_curveballs_tradeoffs.md` are built to drill.

### Step 5 — Failure/backpressure handling

> "If the consumer falls behind during a launch-day traffic spike, the sliding window still catches up correctly once it drains, because everything is keyed on event time, not processing time — a CTR number computed 90 seconds 'late' due to consumer lag still reflects the correct 5-minute window, it's just delivered to the dashboard later than usual. That's a freshness degradation, not a correctness bug, and it's worth stating that distinction out loud: falling behind and being wrong are different failure modes, and this design only risks the first one."

### Step 6 — Trade-offs, stated unprompted

> "I chose per-campaign partition-local aggregation specifically because CTR doesn't need any cross-campaign join or global state — if a future requirement needed 'CTR ranked across all campaigns, live,' that's a materially harder problem (it needs a global view, not a partition-local one), and I'd flag that as a new conversation rather than pretending this design already handles it."

---

## Scenario B (Diagnosis): A Consumer Group Is Rebalancing Constantly

**Interviewer prompt:**
> "Here's a consumer group that processes an orders topic. Every few minutes, the group rebalances — consumers drop out and rejoin, processing pauses each time, and end-to-end latency has been climbing for two days. Diagnose it."

<details>
<summary>Expand only after you've talked through your own triage sequence</summary>

**Scope first, per the general triage discipline** (see `workflow_orchestration/interview_questions/05_oncall_incident_triage.md` for the same framework applied to orchestration — the shape transfers directly): is this *one* consumer misbehaving, or the whole group? Ask whether the rebalances correlate with one specific consumer instance's logs, or happen even when all consumers seem healthy.

**Read before assuming a cause.** The single most common root cause of "rebalances constantly, no crash, no deploy" is a *consumer that's alive but not calling `poll()` frequently enough* — Kafka's consumer-group protocol requires each consumer to poll within `max.poll.interval.ms`, or the broker assumes it's dead and kicks it out of the group, triggering a rebalance. A consumer whose per-batch processing (a slow downstream call, a large synchronous transform) routinely takes longer than that interval looks, from the broker's point of view, exactly like a crashed consumer — even though it's still running.

**The tell:** naming that a rebalance doesn't require an actual crash — a consumer that's simply too slow between polls triggers the exact same symptom, and it's the far more common real-world cause than an actual repeated crash loop. Confirming this means checking: does `max.poll.interval.ms` correlate with observed processing time per batch? Is `max.poll.records` set high enough that one batch's processing routinely exceeds the poll interval? Is there a specific step in this consumer's processing (an external API call it's waiting on, a lock, a slow downstream write) that's grown slower over the two days latency has been climbing?

**Decide.** If it's the poll-interval issue: either reduce `max.poll.records` (smaller batches, more frequent polls) or increase `max.poll.interval.ms` (if the processing genuinely needs that long and can't be sped up) — and separately, if there's a slow synchronous call inside the batch loop, that's the thing actually worth fixing rather than just tuning around it. If instead it *is* an actual crash loop (check for OOM kills, unhandled exceptions in consumer logs), the fix is different: find what's crashing the process, not what's slowing the poll loop.

**Communicate and follow up.** State which of the two you've confirmed — poll-interval starvation vs. actual crashes — before proposing a fix, since they have different remediations and it's easy to guess wrong under pressure. And note explicitly: "climbing for two days" suggests something is *degrading over time* (a growing queue somewhere downstream the consumer calls into, a memory leak lengthening GC pauses), not a static misconfiguration that would have caused constant rebalancing from day one — that observation alone should shift the investigation toward "what changed/grew over the last two days" rather than "what was misconfigured from the start."

</details>

---

## Scenario C: Exactly-Once Processing of Payment Events, End to End

**Interviewer prompt:**
> "Design a pipeline that processes payment events — a customer's card gets charged exactly once per payment intent, even under retries, consumer crashes, and network failures. Walk me through where duplication could sneak in and how you close each gap."

### Step 1 — Clarifying questions

- **What does "process" actually mean here — read an event and write a row, or read an event and call an external payment gateway?** → Interviewer clarifies: the pipeline consumes a `PaymentRequested` event and calls a (simulated) external payment processor's charge API, then writes the result to an internal ledger. → This is the detail that changes everything: the external charge call is the one operation that is **not** naturally idempotent just because Kafka's internals are.
- **Does the payment gateway itself support idempotency keys?** → Yes, the gateway accepts an `idempotency_key` and guarantees it will charge a given key at most once, even if the same request is sent multiple times. → This is the single most important fact in the whole design — it moves "exactly-once effect" from something the streaming layer alone can guarantee into something the *gateway* is contractually providing, as long as the pipeline supplies a stable key.

### Step 2 — Name where duplication can sneak in, one layer at a time

> "There are three separate places a duplicate can be introduced, and they need three separate answers:
>
> 1. **Producer → topic.** A retried produce could write the same `PaymentRequested` event twice. Fixed by Kafka's idempotent producer (`concepts/05_exactly_once_semantics.md`, section 3) — `(producer_id, sequence_number)` dedup at the broker.
> 2. **Consumer offset handling.** If offsets auto-commit *before* processing completes, a crash mid-process causes the event to be reprocessed on restart — this is normal, expected at-least-once behavior, not a bug, as long as step 3 handles it. If offsets commit *before* the charge call even starts, that's the more dangerous variant — see the critique case in `interview_questions/03_critique_and_debug.md`.
> 3. **The charge call itself.** Even with a perfectly-once Kafka layer, if the consumer's own code retries the charge call after a timeout without knowing whether the first attempt actually succeeded, that's the point where a customer gets double-charged — and Kafka's guarantees don't reach this far on their own."

### Step 3 — The actual design

> "Use the payment intent's own natural identifier — `payment_intent_id` — as the idempotency key sent to the gateway, not something generated per-attempt. That one decision means: however many times this event gets reprocessed (crash-and-retry, at-least-once redelivery, a consumer group rebalance mid-processing), the gateway itself refuses to charge the same `payment_intent_id` twice, no matter how many times the pipeline calls it. The pipeline's own job reduces to: consume the event, call the gateway with a stable key, write the result to the ledger, commit the offset — in that order, and only after the ledger write succeeds.
>
> The ledger write itself should also be an idempotent upsert keyed on `payment_intent_id` (`INSERT ... ON CONFLICT DO UPDATE`, or an idempotent write of any kind) rather than a plain insert — so reprocessing the same event after a crash doesn't produce two ledger rows for one payment, independent of whatever the gateway does."

### Step 4 — Why this doesn't need Kafka transactions end-to-end

> "The externally-facing idempotency (the gateway's own idempotency key) is doing the heavy lifting here — Kafka's idempotent producer prevents duplicate *events*, but the actual business-critical guarantee (never charge a card twice) comes from the gateway's contract plus a stable key, not from Kafka transactions alone. This is worth stating explicitly, because it's a common overcorrection: reaching for Kafka's full transactional API (producer transactions + `send_offsets_to_transaction`) adds real latency and complexity, and here it wouldn't even close the actual gap — the charge call to an external system is outside any Kafka transaction's boundary regardless. The design that actually prevents double-charging is 'idempotency key all the way to the external system,' not 'exactly-once messaging internally.'"

### Step 5 — Trade-offs, stated unprompted

> "This design accepts that the same `PaymentRequested` event might genuinely be processed more than once end-to-end (at-least-once delivery, by design) — the guarantee isn't 'this never happens,' it's 'when it happens, it's provably harmless,' because both the external call and the ledger write are idempotent on the same natural key. That's a deliberately different, and I'd argue stronger, guarantee than trying to prevent reprocessing from ever occurring at all, which is a much harder (and in a distributed system, ultimately unachievable) problem."

---

## Now You Try: Real-Time Fraud Detection on Card Transactions

**Interviewer prompt:**
> "Design a real-time pipeline that flags a card transaction as potentially fraudulent within 200ms of the transaction occurring, based on the customer's recent transaction history."

Work through clarifying questions, the windowing/state decisions, the delivery-guarantee choice, and the trade-offs yourself before expanding the debrief.

**Questions to answer once you have a design:**
1. What state does "recent transaction history" require the pipeline to maintain per customer, and does a window type from `concepts/03_windowing_and_watermarks.md` fit it directly, or does this need something closer to a running/unbounded per-key state store?
2. A 200ms latency budget rules out which architectural choices from earlier in this topic?
3. If a fraud rule needs "transactions in the last 10 minutes" but a customer has been offline and their device just replayed 40 minutes of queued transactions at once, what happens?
4. Curveball: the fraud model's false-positive rate spikes right after a deploy. Is that a streaming-architecture problem, or a different team's problem entirely?

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **State shape:** this is closer to a **sliding window with a much shorter, tighter latency budget** than the CTR scenario — "recent history" for fraud is typically a per-customer sliding window (last N minutes or last N transactions) held in a low-latency state store (Kafka Streams' state stores / RocksDB, or Flink's keyed state) rather than recomputed from scratch per event. The key design fact: this state must be partitioned by `customer_id` so that a rule evaluating one customer's history never needs to touch another partition or another node — a cross-partition lookup at evaluation time would blow the 200ms budget by itself.
- **200ms rules out:** any micro-batch architecture with a trigger interval anywhere near or above 200ms (Spark Structured Streaming's default posture doesn't fit here at all), and rules out routing the decision through a system with its own meaningful queuing delay. This needs true per-event streaming (`concepts/01_streaming_fundamentals.md`, section 2) with the state store colocated with the processing, not a separate round-trip to an external database per transaction.
- **Replayed backlog of 40 minutes at once:** this is exactly a burst of *late* data relative to the fraud window's watermark — a naive implementation either (a) processes all 40 minutes' worth as if they just happened "now," corrupting the "recent history" window with stale transactions treated as fresh, or (b) if watermark-driven, correctly recognizes most of them as too old to matter for a "last 10 minutes" rule and handles them via whatever late-data strategy was chosen (`concepts/03_windowing_and_watermarks.md`, section 5) — likely a side output for audit rather than blindly feeding them into a live fraud decision that's already moot by the time they arrive.
- **Curveball:** a false-positive spike right after a model deploy is a **model/rules problem**, not a streaming-architecture problem — the pipeline's job is to deliver the right features to the model within budget and route its output correctly; if the model itself started making worse decisions after a deploy, that's squarely a data-quality/ML-ops conversation. The tell here is the same discipline as the data-modeling curveballs about naming the boundary of your own design ("that's a different conversation, want me to go there or stay on the pipeline architecture?") rather than trying to diagnose a model regression as if it were a windowing bug.

</details>
