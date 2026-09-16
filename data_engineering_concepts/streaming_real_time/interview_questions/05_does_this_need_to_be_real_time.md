# 5. Does This Even Need to Be Real-Time?

Part of the [Interview Questions](README.md) series.

Streaming interviews increasingly test something upstream of any specific technical design: **can you tell when "make it real-time" is the wrong requirement to accept at face value?** This isn't "do you know Kafka" — it's "will you push back on a stakeholder's framing before spending three sprints building a stream processor for a problem batch already solves." This file drills that directly, as a distinct fifth shape from design (file 1), diagnosis (file 1's Scenario B), and trade-off follow-ups (file 4): each case here is a stated business requirement, and the thing being scored is whether you interrogate it before architecting anything.

---

## The General Framework

Before the specific cases below, the sequence worth having ready for any "we need this in real-time" request:

```text
1. ASK WHY        What decision or action actually depends on freshness?
                   If nobody can name one, "real-time" is a preference, not a requirement.

2. ASK HOW FRESH   "Real-time" is not a number. Get an actual figure: sub-second?
                   Under a minute? Under an hour? Each implies a completely
                   different architecture, and most stated "real-time" needs
                   turn out to tolerate minutes, not milliseconds.

3. CHECK THE COST  Does the freshness requirement change what ACTION gets taken,
                   or only how soon a human sees a number? A dashboard refreshing
                   faster than anyone reacts to it is cosmetic freshness, not
                   functional freshness.

4. NAME THE PRICE  Streaming buys latency at a real, ongoing cost: more
                   operational complexity, harder correctness reasoning
                   (ordering, late data, exactly-once), and infrastructure
                   that runs forever rather than a job that runs and finishes.
                   State that cost explicitly before recommending it.

5. PROPOSE THE     Sometimes the honest answer is streaming. Often it's
   RIGHT FIT       "batch, but more frequent." Occasionally it's "a small,
                   targeted real-time path for the one decision that needs it,
                   batch for everything else" -- most real systems are this.
```

Every case below is scored against this same shape — read the request, work through your own version of steps 1-5, then expand the debrief.

---

## Case 1: "We Need Real-Time Sales Dashboards"

**Request:** A VP wants the company's sales dashboard to update in real-time instead of its current nightly refresh.

<details>
<summary>Triage</summary>

**Ask why:** what decision changes based on seeing today's sales three hours sooner versus tomorrow morning? Often, on investigation, the answer is "nothing operational — it would just feel more modern," which is a legitimate but very different requirement from "a live operational decision depends on this."

**Ask how fresh:** press for a number. "Real-time" from a VP asking about a sales dashboard, when pressed, very often turns out to mean "I want to check it in the afternoon and see this morning's numbers," which is an hourly or even 15-minute refresh, not sub-second streaming.

**Check the cost:** a dashboard nobody is staring at continuously gets no value from sub-second freshness over 15-minute freshness — a human checking a dashboard twice a day cannot perceive the difference between "updated 10 seconds ago" and "updated 10 minutes ago."

**The right fit:** in the overwhelming majority of real versions of this request, the answer is "run the existing batch job more frequently" (hourly, or every 15 minutes, depending on source-system load) — a scheduling change, not an architecture change. True streaming infrastructure would be a significant, ongoing operational cost paid for a freshness improvement nobody downstream can actually act on differently. Say this plainly, with the reasoning, rather than either refusing the request or silently over-building.

</details>

---

## Case 2: "The Fraud Team Wants Real-Time Transaction Monitoring"

**Request:** The fraud team wants to know about suspicious transactions "as soon as possible."

<details>
<summary>Triage</summary>

**Ask why:** here the answer is concrete and different from Case 1 — a fraudulent transaction that isn't flagged before it clears can't be reversed, or is far more costly to reverse after the fact. There's a real action (block/hold the transaction) gated on freshness.

**Ask how fresh:** "as soon as possible" needs to become a number tied to the actual action — if the action is "block the transaction before it settles," that's a hard latency budget measured in the transaction-processing pipeline's own timing (often under a second), not a vague aspiration.

**Check the cost:** unlike Case 1, freshness here changes the *action taken*, not just when a human sees a chart — a transaction evaluated 10 seconds late might already be irreversible, which is a functional, not cosmetic, difference.

**The right fit:** this is a legitimate true-streaming requirement — per-event processing, low-latency keyed state (`interview_questions/01_worked_scenarios.md`'s fraud-detection scenario), and it's worth paying the operational cost streaming demands, because the cost of *not* paying it (a fraudulent transaction that clears before anyone could react) is concretely worse. The tell here isn't refusing the streaming architecture — it's being able to articulate *why* this specific request clears the bar that Case 1 didn't, using the same framework both times.

</details>

---

## Case 3: "Every Pipeline in This Org Should Be Migrated to Streaming, Batch Is Legacy"

**Request:** A new engineering leader wants a blanket initiative to migrate every batch pipeline to a streaming architecture, on the general principle that streaming is more modern.

<details>
<summary>Triage</summary>

**Ask why, per pipeline, not per org:** this request skips step 1 entirely by applying one answer to every pipeline regardless of what each one actually needs — the honest response is that "streaming" isn't a maturity upgrade batch pipelines graduate into, it's a different tool for a different requirement (continuous low-latency reaction to unbounded data), and plenty of legitimate workloads (nightly aggregation for finance reporting, monthly cohort analysis, ML training pipelines that need a stable, bounded snapshot to train against) are *correctly* modeled as batch and would not benefit from being forced into a streaming shape.

**Check the cost, org-wide this time:** migrating a pipeline that doesn't need low latency to a streaming architecture doesn't just fail to help — it actively adds ongoing operational burden (a system that must run continuously and be correctly monitored forever, rather than a job that runs, finishes, and is easy to reason about in isolation) for a business requirement that was never asking for continuous operation in the first place.

**The right fit:** push back on the blanket framing directly, and offer the actual decision criterion in its place — audit which pipelines have a real, stated freshness requirement with a concrete downstream action gated on it (Case 2's shape) versus which don't (Case 1's shape), and only migrate the former. This is the single most senior-flavored response across this whole file: recognizing that "modern architecture" is not a requirement, freshness-with-a-gated-action is.

</details>

---

## Case 4: "Customers Want to See Their Order Status Update Instantly"

**Request:** Product wants order-status changes (placed → paid → shipped → delivered) to appear on the customer's tracking page "instantly," and is asking whether this needs a full event-streaming rebuild of the order system.

<details>
<summary>Triage</summary>

**Ask why and how fresh, together:** "instantly" here almost always means "within a few seconds of the actual status change happening," which is a real, if modest, latency requirement — but critically, it's a *low-volume, low-complexity* one: one customer's own order updates, not an aggregation across millions of events.

**Check the cost:** this is the case worth distinguishing sharply from Case 1 and Case 2 — the *action* here (show an updated status to one specific customer) doesn't require any of the harder streaming machinery this whole topic covers: no windowed aggregation, no watermark/late-data handling, no cross-event join, no per-key rolling state. It requires exactly one thing: a low-latency notification that "order X changed status," pushed to that customer's session.

**The right fit:** this is commonly solved with a much lighter mechanism than a full stream-processing engine — a simple event notification (a message published on status change, delivered via a websocket/push channel, or even a CDC stream off the orders table feeding a lightweight fan-out service) rather than a Flink/Kafka Streams windowed-aggregation rebuild. The tell here: recognizing that "needs to happen quickly" and "needs the full apparatus of stream *processing* (windows, watermarks, stateful aggregation)" are different requirements — plenty of low-latency needs are satisfied by fast, simple event delivery with no aggregation logic at all, and correctly scoping which one you actually have avoids a large unnecessary build.

</details>

---

## Key Takeaways

- "Real-time" is not itself a requirement — press for what decision or action actually depends on freshness, and get an actual number for how fresh is fresh enough. Most requests phrased as "real-time" turn out to tolerate minutes, and a good number of those are satisfied by running an existing batch job more often, not by adopting streaming infrastructure at all.
- The deciding question is whether freshness changes the *action taken*, not just how soon a human sees a chart update — a dashboard nobody reacts to differently at 10 seconds vs. 10 minutes gets no real value from streaming; a transaction that becomes irreversible after a delay genuinely does.
- Streaming buys latency at a real, ongoing operational cost (correctness reasoning around ordering/late-data/exactly-once, infrastructure that runs forever rather than finishes) — naming that cost explicitly, rather than treating streaming as a free upgrade over batch, is itself part of a strong answer.
- Not every low-latency need requires the full apparatus of stream *processing* (windows, watermarks, stateful aggregation) — some are satisfied by simple, fast event notification with no aggregation logic at all. Scoping which one a request actually needs is a distinct skill from knowing how to build either.
