# 5. Idempotency & Exactly-Once Reasoning

Part of the [Interview Questions](README.md) series.

This file exists because "idempotency" and "exactly-once" are the two ETL/ELT terms almost every mid-level candidate can *define*, and the two terms a much smaller number can actually *reason about* under a follow-up question. The base four files each touch this — a load strategy here, a retry mechanism there — but the underlying reasoning deserves its own drill, the same way the "reasoning about idempotency" gap was flagged as a specific, recurring gotcha worth a dedicated file.

Every question below is a short scenario followed by "what happens if X fails at exactly this point" — the format that actually shows up when an interviewer wants to know whether you understand this or have just memorized the vocabulary.

---

## 1. "Exactly-once" is a claim about effect, not about delivery

**Q: Is true exactly-once *delivery* actually achievable across a network boundary — say, a pipeline calling an external API?**

<details>
<summary>Answer</summary>

No, not in the strict sense, and saying so plainly is a stronger answer than pretending otherwise. Any call across a network can fail *after* the receiver processed it but *before* the caller learns the result (the response is lost, the connection drops) — from the caller's point of view, that's indistinguishable from the call never having reached the receiver at all. The caller's only honest choices are: retry (risking a duplicate, if the call actually succeeded) or don't retry (risking silently losing an operation, if the call actually failed). There is no third option that reliably tells the caller which of those actually happened, in general, across an unreliable network.

What's actually achievable — and what "exactly-once" means in every real system that claims it — is **exactly-once effect**, built from **at-least-once delivery plus idempotent processing**: the caller retries freely (accepting duplicates at the delivery layer), and the receiver is built so that processing the same logical operation twice has no additional effect beyond processing it once. The exactly-once *guarantee* lives in the idempotency of the processing step, not in some impossible delivery mechanism.

</details>

---

## 2. Idempotency keys vs. database upserts

**Q: A pipeline calls a third-party shipping API to create a shipment for each order, then records the shipment ID in a `shipments` table via upsert. Why isn't the upsert enough to make retrying this pipeline safe?**

<details>
<summary>Answer</summary>

The upsert makes the *database write* idempotent — re-running it lands on the same final row. But the shipping API call happens *before* that write, and the API call itself is not automatically idempotent: if the pipeline crashes after the API successfully creates a shipment but before the upsert commits, a retry will call the API *again* for the same order, creating a second, real, physical shipment — a side effect no database upsert can undo, because it happened outside the database entirely.

The fix is pushing idempotency to the API call itself: many APIs that expect to be called from unreliable pipelines support a client-supplied **idempotency key** — a unique ID generated once per logical operation (e.g. derived from the order ID) and sent with every attempt, including retries. The API guarantees that repeated calls with the same key produce the same result without creating a second shipment. This is the general pattern: idempotency has to be established at *whichever* layer has a real, irreversible side effect — which is not always the database layer, and is often further out than candidates initially assume. This exact failure mode is worked as a full critique case in `interview_questions/03_critique_and_debug.md`, Case 5.

</details>

---

## 3. Checkpoint-then-process vs. process-then-checkpoint

**Q: A stream consumer reads a message, processes it (writes a row to the warehouse), then commits its offset (marking the message as consumed). It crashes after the write but before the offset commits. What happens on restart, and is that a problem?**

<details>
<summary>Answer</summary>

On restart, the consumer resumes from the last *committed* offset — which is still behind the message that was actually processed, since the offset commit never happened. It will re-read and re-process that same message. If the write is idempotent (an upsert keyed on a stable ID), this is completely safe — the message gets applied a second time with no additional effect, which is exactly the at-least-once-delivery-plus-idempotent-processing pattern from question 1.

Now flip the order: if the consumer commits the offset *first*, then processes the message, and crashes in between, the message is marked consumed but was never actually applied — a silent data loss, not a duplicate. This is why "process, then checkpoint" (not the reverse) is the only ordering that fails safely: a crash between the two steps produces a redundant retry (harmless, given idempotent processing) rather than a silent gap (real, permanent data loss). Whenever a pipeline's checkpoint/commit ordering is described, check which of these two orders it uses before evaluating anything else about it — the ordering alone determines whether crashes fail toward duplication or toward loss.

</details>

---

## 4. Idempotent load, non-idempotent watermark

**Q: An incremental pipeline's load step is a correct, idempotent upsert. Its watermark-update step runs as a separate statement immediately after. It crashes between the two. Walk through what happens on the next run — is this safe?**

<details>
<summary>Answer</summary>

Yes — and it's worth being precise about *why*, because it looks superficially similar to the dangerous version of this bug. If the load committed but the watermark update didn't, the next run's watermark is still behind where it "should" be — so the next run re-extracts a window that includes some already-loaded rows. Because the load step is an idempotent upsert, re-applying those already-loaded rows has no effect: they upsert to the same values they already had. The pipeline does slightly redundant work (re-processing a small overlap window) but produces a completely correct result.

Contrast this with `interview_questions/03_critique_and_debug.md`, Case 2, where the watermark update runs *before* the load instead of after — that ordering is the actually dangerous one, because a crash after the watermark update but before the load leaves rows permanently unextracted. The safe pattern here is exactly the reverse order: load first (idempotent, safe to redo), watermark second (only advance once the redo-safe step has actually succeeded). The general rule, stated once: **whichever step is not idempotent must run last**, so that a crash before it completes only ever causes safe, redundant repetition of the idempotent step(s) that already ran, never a silent gap.

</details>

---

## 5. At-least-once vs. at-most-once, and why almost nobody wants at-most-once

**Q: Why is at-most-once delivery (acknowledge before processing) almost never the right default for a data pipeline, even though it's simpler to reason about than at-least-once?**

<details>
<summary>Answer</summary>

At-most-once trades away correctness for simplicity in the wrong direction for most ETL/ELT use cases: it guarantees no duplicates, at the cost of silently dropping data on any failure between acknowledgment and processing — exactly the failure mode in question 3's second ordering. Losing data silently is almost always worse than processing it twice, because a duplicate is usually detectable and fixable after the fact (a row count that's higher than expected, an idempotent reprocessing pass), while a silent loss often isn't discovered until someone notices a downstream number looks wrong — which can be weeks later, as in `interview_questions/03_critique_and_debug.md`, Case 6.

At-most-once is a reasonable deliberate choice only when duplicated processing would be *actively harmful* and undetectable-after-the-fact (rare), or when the data itself is genuinely low-value and reprocessing isn't feasible anyway (e.g. best-effort telemetry where occasional gaps are an accepted cost). Absent one of those specific justifications, at-least-once delivery plus idempotent processing is the default every serious pipeline in this topic converges on — it's the combination every pattern in `concepts/03_loading_strategies.md` and `concepts/06_idempotency_reliability.md` is actually built around, even when the words "at-least-once" never appear in that file.

</details>

---

## 6. A rapid gut-check: crash points

For a pipeline shaped `extract -> stage -> upsert into target -> advance watermark`, where each arrow is a point a crash could occur — for each of the four possible crash points, is a simple re-run of the whole pipeline safe, and why?

<details>
<summary>Answer</summary>

```text
crash during extract:            SAFE to re-run -- nothing was written anywhere yet.
crash during staging:             SAFE to re-run -- staging is cleared/overwritten at
                                   the start of every run (concepts/03_loading_strategies.md).
crash during the upsert:          SAFE to re-run -- the upsert is idempotent; a partially
                                   applied upsert re-run from scratch converges to the
                                   same correct final state either way.
crash after upsert commits,       SAFE to re-run -- the watermark hasn't moved, so the
before watermark advances:        next run re-extracts an overlap window, but re-applying
                                   it through the idempotent upsert has no additional effect
                                   (this is question 4, worked in full).
```

Every single crash point in this pipeline is safe to blindly re-run from the top, with no special-case recovery logic needed anywhere — which is exactly the property a well-designed idempotent, watermark-last pipeline should have. If any crash point on this list required different recovery logic than "just re-run it," that would be the signal that idempotency isn't actually holding somewhere in the chain.

</details>
