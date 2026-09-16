# 3. Critique & Debug: What's Wrong With This Architecture?

Part of the [Interview Questions](README.md) series.

A different interview mode from file 1: instead of designing something from
scratch, you're handed an architecture (or a description of one) and asked
**"what's wrong with this?"** or **"what breaks at 10x scale?"** This tests
whether you can read a system critically, not just produce one. Every case
is described in plain prose — no diagrams to over-index on — because the
skill being tested is spotting the flaw from a description, the way it would
actually be described to you out loud.

Read the setup, form your diagnosis, then expand the debrief.

---

## Case 1: The Lambda Architecture Nobody Needed

**Setup:** A team builds a Lambda architecture for a weekly sales summary
report. The batch layer (Spark, nightly) computes accurate weekly totals.
The speed layer (Flink) maintains a "live" running total, updated every few
seconds, that's displayed on an internal ops dashboard nobody outside the
data team actually looks at more than once a week. Six months in, the team
spends a disproportionate amount of on-call time on speed-layer incidents
(Flink checkpoint failures, state store corruption) for a dashboard that
gets glanced at during the Monday planning meeting.

<details>
<summary>Debrief</summary>

**Diagnosis:** this is Lambda without a real reason for the "L" — nobody
articulated a genuine, non-negotiable need for a live number distinct from
the batch number. "Weekly sales summary, glanced at once a week" doesn't
need sub-second freshness; a nightly (or even just a same-day) batch refresh
would have served the actual use case, and the speed layer exists purely
because it seemed like the more sophisticated architecture, not because a
requirement demanded it.

**Fix:** drop the speed layer entirely. Recompute the summary on the same
nightly batch cadence as everything else, or at most add a same-day
incremental refresh if there's a real (but still stated explicitly) reason
the Monday number needs to reflect Friday's late data. This removes an
entire class of on-call burden for zero loss of actual business value.

**The interview tell:** naming "what was the ACTUAL latency requirement that
justified this" as the very first diagnostic question — rather than
critiquing Flink configuration details — is what separates someone who
understands Lambda's cost/benefit trade-off from someone who can operate
Flink but never questioned why it was there
(`../concepts/01_pipeline_architectures.md`, section 3, and
`../concepts/04_capacity_planning_and_cost.md`, section 4, on Lambda's real
cost).

</details>

---

## Case 2: The Sharding Scheme That Works Great Until It Doesn't

**Setup:** An events table is range-sharded by an auto-incrementing
`event_id`, split into shards of 100M IDs each (`shard 0: 0-99,999,999`,
`shard 1: 100,000,000-199,999,999`, etc.). At launch, with modest traffic,
write throughput across the 4 provisioned shards looks fine in testing. Six
months post-launch, write latency has degraded badly, and monitoring shows
shard 3 (the newest range) handling nearly all writes while shards 0-2 sit
almost completely idle.

<details>
<summary>Debrief</summary>

**Diagnosis:** this is the textbook range-sharding failure mode
(`../concepts/02_scalability_patterns.md`, section 2) — with a
monotonically increasing key, EVERY new write by definition falls into the
highest, newest range. The "even" distribution in testing was an illusion
of the load-testing pattern (likely inserting across a pre-generated ID
range rather than truly append-only), not a property of the sharding scheme
itself; in production, where IDs are assigned strictly in increasing order,
the newest shard was always going to become the sole write target the
moment the older ranges filled up.

**Fix:** either (a) switch to hash sharding on `event_id` (or a different,
well-distributed key) if range queries on ID aren't actually a real access
pattern, or (b) if range queries genuinely matter (e.g., "give me all events
between ID X and Y"), pre-split future ranges across MULTIPLE shards in a
round-robin or hash-of-range-bucket fashion rather than one contiguous
range per shard, so new writes fan out instead of concentrating.

**The interview tell:** recognizing that the FAILURE MODE is inherent to
range sharding on a monotonic key — not a tuning problem, not something more
shards would fix (more shards just delays the same problem, since the
newest one is STILL the sole write target) — is the difference between a
surface fix and understanding why this was always going to happen.

</details>

---

## Case 3: The Caching Layer With No Way to Know It's Wrong

**Setup:** A product analytics dashboard caches the result of its main
aggregation query in Redis, keyed by the query text, with no TTL and no
invalidation logic — the reasoning was "the underlying data only changes
once a day anyway, from the nightly batch load." Three months later, an
engineer manually backfills a data-quality fix directly into the warehouse
table outside the normal nightly load. The dashboard continues showing
the OLD (wrong) numbers for two full weeks before anyone notices, because
nobody thought to clear the cache and there was no TTL to force a refresh.

<details>
<summary>Debrief</summary>

**Diagnosis:** the cache design encoded an assumption ("data only changes
via the nightly load") as a hard invariant with no safety net for when that
assumption turned out to be false — exactly the risk called out in
`../practice/coding_problems.md`'s LRU cache problem, where TTL and
invalidation are listed as REQUIREMENTS, not nice-to-haves, specifically
because "the cache is stale and nobody knows it" is a correctness bug, not
just a missed performance optimization.

**Fix:** add a TTL as a safety net regardless of how confident the "only
changes once a day" assumption feels (a TTL of a few hours means a manual
backfill is wrong for hours, not weeks) AND wire cache invalidation into
whatever writes to the warehouse table — including out-of-band backfills,
which is precisely the case an untested assumption failed to anticipate.

**The interview tell:** the deeper answer isn't "add a TTL" alone — it's
recognizing that a cache invalidation strategy built entirely on an
assumption about HOW data changes will eventually meet a way the data
changes that the assumption didn't cover, and a TTL is the generic safety
net for exactly that class of unknown-unknown.

</details>

---

## Case 4: The Architecture That Was Right at 1x and Wrong at 10x

**Setup:** A team built a streaming fraud-scoring pipeline (similar in shape
to `01_worked_scenarios.md` Scenario 1) where the stream processor calls the
ML model-scoring service SYNCHRONOUSLY, inline, before a transaction can
proceed to the next stage — at launch volume (a few hundred TPS), this
added a barely-noticeable ~50ms per transaction. The interviewer asks: "the
business grows 10x over the next year — what happens to this design, and
what would you change today to avoid it?"

<details>
<summary>Debrief</summary>

**Diagnosis:** a synchronous, in-line call to an external service inside a
stream processor doesn't scale linearly with throughput the way the rest of
the pipeline does — at 10x volume, EITHER the model-scoring service needs
10x its own capacity (a dependency the pipeline's own scaling now
transitively requires and must provision for), OR — more realistically — the
model service becomes a bottleneck that backs up the entire stream, since a
synchronous call blocks that consumer thread until it returns. What was
"barely noticeable" latency at low volume becomes the pipeline's throughput
ceiling at 10x, because now every transaction is serialized behind a
round-trip to a dependency that wasn't designed to scale in lockstep with
the ingestion layer.

**Fix (and this maps directly onto Scenario 1's actual design choice):**
make the model-scoring call ASYNCHRONOUS with a timeout, so a slow or
saturated model service degrades the pipeline (transactions flow through
unscored, or scored by the faster rule-engine path alone) rather than
serializing and backing up the whole stream. This is exactly why Scenario 1
made that choice proactively rather than reactively — the interview signal
here is recognizing that a synchronous external dependency inside a
high-throughput stream is a scaling landmine BEFORE it detonates, not
after.

**The interview tell:** a candidate who says "we'd add more model-service
replicas" hasn't found the actual bug — more replicas helps until the
synchronous call pattern itself becomes the bottleneck (queueing behind a
blocking call, not a throughput-of-the-dependency problem). The stronger
answer changes the CALL PATTERN (synchronous → async-with-timeout), not
just the amount of the dependency's capacity.

</details>

---

## Case 5: The Monitoring That Only Watches the Happy Path

**Setup:** A daily batch pipeline has extensive monitoring: job success/
failure alerts, row-count checks, and a runtime SLA alert if the job takes
longer than 2 hours. Six weeks after launch, a subtle upstream schema
change causes one non-critical column to silently start arriving as NULL
for every row — the job completes successfully, in normal time, with the
normal row count. Nobody notices for a month, until a downstream ML feature
that depended on that column quietly degrades in accuracy and someone
finally traces it back.

<details>
<summary>Debrief</summary>

**Diagnosis:** every alert configured was about the pipeline's OPERATIONAL
health (did it run, did it run on time, did it produce roughly the right
number of rows) and none of them checked DATA QUALITY at the column/value
level — a job can succeed, on time, with a normal row count, while still
silently producing wrong data. This is a real, common gap: "the pipeline
ran successfully" and "the pipeline produced correct data" are different
claims, and monitoring only the first one leaves the second entirely
unchecked.

**Fix:** add data-quality checks as a genuine pipeline stage, not just
infrastructure monitoring — null-rate checks on columns with a known-normal
baseline (alert if a column's null rate jumps from 2% to 100% overnight),
referential integrity checks, and distribution/range sanity checks on key
measures. This is the same "grain uniqueness / referential integrity /
reconciliation totals / row-count sanity" checklist from
`../../de_rewamp/data_modeling/interview_questions/`'s curveball on "how do
you know your fact table is correct" — the same discipline applies to any
pipeline's OUTPUT, not just a data model's.

**The interview tell:** recognizing the CATEGORY of gap ("we monitor that it
ran, not that it's right") rather than just proposing "add a null check on
that one column" — the fix for THIS column doesn't prevent the next
column's silent schema drift; the fix for the CATEGORY (systematic
data-quality checks as a pipeline stage) does.

</details>

---

## Case 6: The Backpressure Strategy That Silently Drops Money

**Setup:** A payment-events stream processor is configured with a bounded
buffer and a DROP strategy for backpressure — chosen early on, modeled
after a metrics pipeline the team had built previously, where dropping
excess telemetry under load was an acceptable, well-understood trade-off.
Nobody revisited the choice when this new pipeline was repurposed to
process payment confirmation events instead of metrics. Under a traffic
spike, the buffer fills and the pipeline silently drops several hundred
payment confirmation events.

<details>
<summary>Debrief</summary>

**Diagnosis:** the backpressure STRATEGY (drop) was copied from a different
system where the DATA TYPE justified it (approximate telemetry, where a gap
is invisible and harmless) without re-evaluating whether the same
justification held for the new data type (individually meaningful,
financially significant events, where every single dropped record is a real
incident). `../concepts/02_scalability_patterns.md`, section 7 names this
explicitly: which strategy to use depends on what the data IS, and this
case is exactly the failure mode of applying yesterday's answer to a
different question.

**Fix:** for payment confirmation events specifically, backpressure should
buffer (bounded, but generously sized against a stated burst multiple) and
throttle the producer, NEVER drop — every event needs to either be
processed or explicitly land in a dead-letter/retry path, so nothing simply
vanishes. If the buffer's capacity is genuinely exceeded even after
throttling, that's a capacity-planning failure to fix (a bigger buffer,
faster consumers, or upstream rate limiting), not a case where dropping is
an acceptable trade-off.

**The interview tell:** the fix isn't "buffer instead of drop" recited as a
rule — it's explicitly re-deriving the strategy from what the data IS each
time a pipeline is reused or repurposed, rather than treating a
backpressure strategy as a generic infrastructure setting that transfers
unchanged across use cases.

</details>

---

**Next:** [04 — Curveballs & Trade-offs](04_curveballs_tradeoffs.md)
