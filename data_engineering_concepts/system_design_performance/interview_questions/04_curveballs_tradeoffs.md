# 4. Curveballs & Trade-off Questions

Part of the [Interview Questions](README.md) series.

The last question type: mid-conversation follow-ups that take whatever you
just designed (in a real interview, or in one of file 1's worked scenarios)
and push on one assumption. There's rarely one "correct" answer — what's
scored is whether you reason through the trade-off out loud instead of
freezing or giving a one-word answer. Try answering each before expanding
the model answer; several explicitly build on file 1's scenarios.

---

**Curveball: "Take the fraud detection dashboard from Scenario 1. Now it
needs to BLOCK the transaction, not just flag it for review. What changes?"**

<details>
<summary>Model answer</summary>

This changes the latency budget by roughly two orders of magnitude — from
"flag within 10 seconds" to "decide within the payment authorization window,"
typically under 200ms end-to-end, and that budget has to cover the ENTIRE
round trip including the model call, not just the stream processor picking
up the event. State plainly that this is no longer the same design with a
tighter number, it's a genuinely different system: the async-with-timeout
model call from Scenario 1 (which tolerated slowness by degrading
gracefully to unscored) doesn't work when the caller is BLOCKED waiting for
an answer — now you need a model-serving path built for sub-100ms p99
latency (an in-memory or co-located model, not a network hop to a general
model service), and a hard fallback decision (fail open and let the
transaction through, or fail closed and block it) for when even that fast
path times out. That fallback choice is itself a business decision, not a
technical one — say explicitly you'd escalate it rather than assume.

</details>

---

**Curveball: "The ride-sharing surge-pricing platform from Scenario 2 is
now expanding to multiple regions with a data residency requirement — EU
rider data must stay in the EU. What changes?"**

<details>
<summary>Model answer</summary>

This is a sharding/replication question wearing a compliance costume
(`../concepts/02_scalability_patterns.md`, section 2's geographic sharding).
The Kafka topics, Redis serving stores, and warehouse tables all need to be
partitioned by region at the infrastructure level, not just logically — an
EU rider's GPS pings and ride events must never transit through or persist
in a non-EU data center, which usually means fully separate regional
deployments of the ingestion and processing stack (separate Kafka clusters,
separate Flink jobs, separate Redis instances), not just a `region` column
on shared infrastructure. State the harder follow-up explicitly: cross-region
aggregation (a global "total rides today" number for the executive
dashboard) now requires a deliberate, compliant aggregation step — summary
statistics can cross the boundary even when raw data can't, but that
distinction has to be a designed choice, not an accident of which table
happened to be reachable from which region.

</details>

---

**Curveball: "The IoT telemetry pipeline from Scenario 3 — the source
system (the ingest gateway) goes down for 6 hours due to a cloud provider
outage. What happens, and how do you recover?"**

<details>
<summary>Model answer</summary>

First, name what does NOT happen: devices don't just stop generating
readings — most IoT devices buffer locally for some period and resend on
reconnect, which is exactly the "firmware rollout burst" scenario from
Scenario 3's Step 1, just triggered by an outage instead of a planned
rollout — so the recovery design (Kafka sized above steady-state, partition
count exceeding consumer parallelism) already exists for this. Say plainly
what's LOST during the gap: threshold alerting for those 6 hours didn't
happen in real time — a temperature breach during the outage wasn't caught
within the 15-second SLA, because it couldn't have been. The recovery plan
needs a specific reconciliation step: once the buffered readings flood back
in, re-run threshold evaluation over that backfilled window specifically
(not just let it flow through the normal real-time path, which would now be
evaluating "real-time" alerts on 6-hour-old data with a misleading
timestamp) and clearly flag any breach found during backfill as
"detected late, during outage recovery" rather than silently blending it
into the live alert stream as if it were caught on time.

</details>

---

**Curveball: "For any of these three designs — the team building it shrinks
from 8 engineers to 2 overnight (an acquisition, a reorg, whatever the
reason). Does the architecture still make sense?"**

<details>
<summary>Model answer</summary>

Explicitly re-evaluate operational complexity against team size, the same
axis `../../de_rewamp/data_modeling/interview_questions/`'s Lambda-related
curveball flags for team capacity. A Lambda architecture (Scenario 2)
maintaining two codepaths is a real ongoing tax that a team of 2 likely
can't sustain reliably — the honest answer is naming that you'd actively
consider simplifying toward Kappa or even pure batch, ACCEPTING a worse
freshness SLA, rather than keeping an architecture the team can't safely
operate just because it was "already built." The same logic applies to
Scenario 1's separate rule-engine-plus-model-scoring path — a smaller team
might justify temporarily disabling the model-scoring path (falling back to
rule-only fraud detection) rather than carrying the operational burden of
keeping a model-serving pipeline healthy with no capacity to do so. The
scored behavior here is prioritizing "can this team actually operate what I
designed" over "is this the most sophisticated design possible" — the same
discipline the decision matrix in `../concepts/01_pipeline_architectures.md`
already argues for even at full staffing.

</details>

---

**Curveball: "This pipeline needs exactly-once processing guarantees now —
right now it's at-least-once, and a transient failure occasionally causes a
duplicate event to be processed. What actually changes?"**

<details>
<summary>Model answer</summary>

Name the real mechanism, not just the buzzword: exactly-once in a streaming
system is usually achieved through IDEMPOTENT processing plus deduplication,
not through some magic delivery guarantee that prevents duplicates from ever
arriving — duplicates from at-least-once delivery (a consumer crashes after
processing but before committing its offset, so it reprocesses on restart)
are a fact of life in any distributed system, and "exactly-once" really
means the SYSTEM'S EFFECT is as if each event were processed once, even
though the event itself might physically arrive twice. Concretely: give
every event a stable unique ID (or derive one from its natural key +
timestamp), and make every downstream write an upsert keyed on that ID
(a `MERGE`/idempotent write) rather than a blind append or increment — a
duplicate event then either doesn't change anything (upsert to the same
values) or is explicitly detected and skipped (a dedup table/cache of
recently-seen IDs), rather than double-counting revenue or double-firing an
alert. State the cost explicitly: this adds a real lookup/storage cost to
every event (checking "have I seen this ID"), which is why teams that don't
NEED true exactly-once (approximate metrics, for instance) reasonably stay
at-least-once and accept occasional double-counting as noise.

</details>

---

**Curveball: "Your design assumed steady, predictable load. The interviewer
says: 'actually, this needs to handle a 50x spike for exactly 10 minutes,
twice a year, and otherwise be as cheap as possible the rest of the time.'
What changes?"**

<details>
<summary>Model answer</summary>

This is explicitly a capacity-and-cost trade-off question
(`../concepts/04_capacity_planning_and_cost.md`, section 4) — reserved,
always-on capacity sized for the 50x peak would sit almost entirely idle
364 days a year, which is the wrong shape of spend for a KNOWN, narrow,
predictable spike. The better answer: keep steady-state infrastructure sized
for normal load (reserved/committed pricing, since that part IS steady and
predictable), and handle the spike with elastic, on-demand capacity that
scales out specifically for those two 10-minute windows — an autoscaling
consumer group, a serverless processing tier, or simply pre-provisioning
extra capacity for the KNOWN spike windows in advance (since they're
predictable events on a calendar, not a surprise) rather than relying purely
on reactive autoscaling, which has ramp-up latency that could miss most of a
10-minute window entirely. Naming that "known and predictable, even if
extreme" is fundamentally easier to design for cheaply than "unpredictable
and extreme" is the trade-off insight being tested here.

</details>

---

**Curveball: "You've now got budget approval to eliminate the 10-second
staleness window entirely in Scenario 1 — true sub-second, in-line
processing everywhere. Should you actually do it?"**

<details>
<summary>Model answer</summary>

Push back, out loud, rather than just accepting the ask at face value — this
is exactly the senior-level instinct interviewers are listening for. Ask
what business outcome sub-second unlocks that 10 seconds doesn't: if the
answer is "nothing measurable, it just sounds better," that's a sign the ask
is solving an imagined problem, and the honest answer is that the
architectural complexity, cost, and operational risk of chasing sub-second
guarantees everywhere is not worth it for a marginal, unmeasured improvement
over a working 10-second design. If there IS a real answer (e.g., "we're
moving from flag-for-review to block-in-line," which is the actual scenario
in this file's first curveball above), then yes, it's worth it — but that's
a DIFFERENT, harder system, not a tuning pass on the existing one. The
scored behavior is treating "more real-time" as a trade-off to be justified
by a business outcome, never as a default upgrade path pursued for its own
sake.

</details>

---

**Next:** back to [the index](README.md), or restart the sequence at
[01 — Worked Scenarios](01_worked_scenarios.md).
