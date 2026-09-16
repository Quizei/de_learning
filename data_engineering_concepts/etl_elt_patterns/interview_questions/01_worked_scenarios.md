# 1. Worked Design Scenarios

Part of the [Interview Questions](README.md) series — see that index for the full taxonomy of question types and how the files fit together.

Unlike data modeling's worked scenarios, this file isn't fully code-free — a short snippet (a watermark query, a merge statement) is shown wherever it's the fastest way to make a design decision concrete. The point is still the reasoning: how you scope the problem, choose an extraction/load strategy, and defend it against failure — not the syntax.

Four full scenarios are worked below, each with clarifying questions → design → narrated failure handling → trade-offs, and two carry a "Now You Try" companion (hidden debrief). Read the four straight through once, including every debrief, then use the two companions to run the same process yourself.

---

## A. Daily Incremental Load: Postgres OLTP → Warehouse

**Interviewer prompt:**
> "Walk me through how you'd build a daily incremental load from a Postgres orders database into our warehouse."

### Step 1 — Clarifying questions before designing anything

- **What does the source table actually guarantee?** Does every row have a reliably-maintained `updated_at`, bumped on every `UPDATE` by the application (or a trigger), not just set once on insert? → Interviewer confirms yes, via an `ON UPDATE` trigger.
- **Can rows be deleted in the source?** → Yes, rarely — cancelled test orders get hard-deleted a few times a month.
- **Freshness requirement?** → Once daily is fine; this isn't a real-time requirement.
- **Volume?** → 200M rows in `orders`, growing by roughly 50K rows/day.
- **What happens on failure — is a partial day's load acceptable to re-run?** → It must be safe to re-run; the on-call engineer will just re-trigger the job if it fails.

Asking about deletes specifically, before designing anything, is the single most valuable question in this scenario — it's the detail that changes the whole shape of the answer, not a minor footnote.

### Step 2 — Choose an extraction strategy and say why

> "Given a reliable `updated_at` and no real-time requirement, incremental extraction by timestamp is the right default — not a full daily reload of 200M rows, and not log-based CDC, which would be over-engineering for a once-a-day, delete-is-rare requirement."

```sql
SELECT * FROM orders WHERE updated_at > :watermark ORDER BY updated_at;
```

The watermark is read from a durable metadata table before the run and only written back *after* the load into the warehouse succeeds — writing it early is exactly the bug in `interview_questions/03_critique_and_debug.md`, Case 2.

### Step 3 — Handle the delete gap explicitly

> "Timestamp-based incremental extraction has a structural blind spot: a deleted row produces nothing for `WHERE updated_at > ?` to find, because there's no row left to filter on. Since deletes here are rare and not latency-sensitive, I wouldn't reach for full CDC just to solve this — I'd run a lightweight nightly reconciliation: pull just the primary keys from source and target, anti-join to find IDs present in the warehouse but absent from source, and soft-delete (flag, don't hard-delete) those rows in the warehouse."

Naming the gap *and* picking a proportionate fix — rather than either ignoring deletes or jumping straight to full log-based CDC — is what separates a calibrated answer from a memorized one. If deletes were frequent or delete-latency mattered (fraud, compliance), the answer would flip toward CDC — see `interview_questions/04_curveballs_tradeoffs.md`.

### Step 4 — Make the load idempotent

> "The load target is a staging table, truncated and reloaded every run, merged into the warehouse table via `INSERT ... ON CONFLICT(id) DO UPDATE`. That makes the whole run safe to re-trigger: if it fails halfway through yesterday's batch and gets re-run today, the same rows just get upserted to the same final values — no duplicates, no double-counted revenue."

```sql
INSERT INTO wh_orders (id, customer_id, amount, status, updated_at)
SELECT id, customer_id, amount, status, updated_at FROM stg_orders
ON CONFLICT (id) DO UPDATE SET
    customer_id = excluded.customer_id, amount = excluded.amount,
    status = excluded.status, updated_at = excluded.updated_at;
```

### Step 5 — Narrate what happens on failure

> "If the job dies after extraction but before the merge commits, the watermark hasn't moved yet (it only advances after a successful merge), so the next run just re-extracts the same window and re-applies the same upsert — safe, by construction. If it dies mid-merge, Postgres's own transaction guarantees mean the merge either fully committed or fully rolled back; there's no 'half-merged' state to reason about."

### Step 6 — Close with the trade-off

> "I picked timestamp-based incremental plus a nightly delete-reconciliation sweep over full CDC because the freshness requirement (once daily) and the delete frequency (rare) don't justify CDC's operational cost here. If deletes became common, or freshness moved to minutes, that calculus flips — and that's a real, new requirement worth naming as its own conversation, not something to silently over-build for today."

---

### Now You Try: Incremental Sync From a Rate-Limited SaaS API

**Interviewer prompt:**
> "Same idea, but the source is a third-party SaaS CRM's REST API, not a database you control. It's paginated, rate-limited to 100 requests/minute, and only exposes a `modified_since` query parameter — no delete events at all."

**Work through:** what extraction strategy, how you'd respect the rate limit without the job timing out, how you'd detect deletes given the API gives you nothing to work with, and what you'd track as the "watermark" when you don't control the source's internal clock.

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **Extraction strategy:** incremental by `modified_since`, same shape as the Postgres case — the mechanism doesn't change just because the source is an API instead of a database.
- **Respecting the rate limit:** the retry/backoff machinery from `concepts/01_extraction_patterns.md` and `concepts/06_idempotency_reliability.md` applies directly — a `429` response is treated as a transient failure and retried with backoff, and the pagination loop itself should throttle proactively (sleep between requests to stay under 100/minute) rather than relying purely on reactive backoff after being rate-limited.
- **Detecting deletes with nothing to work with:** this is structurally the same gap as the Postgres scenario, but *harder* — there's no reconciliation option via a direct anti-join against source, because there's no cheap way to list all current source IDs without another full paginated pull. The honest answer: periodically (say, weekly, not nightly) run a full ID-only extraction specifically to reconcile deletes, accepting that deletes are detected on a longer delay than updates. This is a real, common trade-off with third-party API sources, not a design flaw.
- **What the watermark actually is:** the *source's* `modified_since` value from the last successful run — never your own pipeline's wall-clock time, because clock skew between your pipeline and the API's servers (or a slow-running extraction that takes 20 minutes to finish) means "now, when I started" is not a safe value to record as "everything up to here is captured." Always derive the watermark from the maximum value actually observed in the returned data, exactly as in `concepts/04_incremental_vs_full.md`.

</details>

---

## B. A Pipeline That Handles Late-Arriving and Out-of-Order Records

**Interviewer prompt:**
> "Design a pipeline that has to handle late-arriving and out-of-order records — say, mobile clients that sync events hours after they happened, sometimes out of order relative to each other."

### Step 1 — Clarifying questions

- **How late can "late" be?** → Interviewer says: usually minutes, but up to 48 hours for an offline mobile client that reconnects.
- **Does anything downstream depend on daily aggregates being "final"?** → Yes — a daily revenue rollup is published each morning for the previous day.
- **Is exact ordering required, or just eventual correctness?** → Eventual correctness; a report can be corrected after the fact, it doesn't need to be perfect the instant it's published.

### Step 2 — Separate two different problems: "late" and "out of order"

> "These are related but distinct. Late-arriving means a record's *event time* (when it actually happened) is well before its *arrival time* (when the pipeline saw it) — the pipeline's watermark has already moved past that point. Out-of-order means two records both arrive close together in time, but not in the order their event times would suggest. A pipeline can have either problem without the other."

```
event_time:     records store WHEN something happened
arrival_time:   records show up in the pipeline WHENEVER they show up
watermark:      the pipeline's belief about "how far in event_time are we
                 confident we've seen everything" -- late data violates that belief
```

### Step 3 — Design around a bounded lateness window, not "wait forever"

> "I'd define an explicit lateness allowance — say, 48 hours, matching the worst realistic mobile sync delay — and treat any daily aggregate as *provisional* until that window closes, not final the moment the day ends. A record arriving within the 48-hour window reopens and recomputes the affected day's aggregate; the published report gets a visible 'as of' timestamp and a note that revenue for the last 2 days may still be corrected."

This is the direct application of the late-arriving-data mechanics in `concepts/04_incremental_vs_full.md`, section 4, at the aggregate-reporting layer rather than just the raw-extraction layer.

### Step 4 — Handle out-of-order application at the row level

> "Within the lateness window, records for the same key must still be applied in event-time order, not arrival order — the same requirement as CDC event application in `concepts/05_change_data_capture.md`. If two updates to the same order arrive close together but out of order, naively applying them in arrival order can leave a stale value as 'final.' I'd carry the event timestamp on every record and, at merge time, only overwrite a value if the incoming record's event time is newer than what's already stored — a last-writer-wins rule keyed on event time, not on arrival time."

```sql
UPDATE orders SET status = :new_status, event_time = :new_event_time
WHERE id = :id AND event_time < :new_event_time;   -- no-op if this is actually the OLDER event
```

### Step 5 — Narrate the trade-off

> "A tighter lateness window (say, 2 hours instead of 48) makes reports 'final' sooner but silently drops or mis-attributes anything later than that; a wider window keeps correctness but means nothing is ever really final quickly. 48 hours here is a business decision — matching the worst realistic sync delay — not an arbitrary engineering choice, and it's exactly the kind of number I'd confirm with the stakeholder rather than picking myself."

---

### Now You Try: Multi-Region Event Stream With Clock Skew

**Interviewer prompt:**
> "Same late/out-of-order problem, but now events come from application servers in three different regions, and you've noticed their system clocks can drift by up to 90 seconds relative to each other. Does that change anything?"

**Work through:** whether clock skew is the same problem as late-arriving mobile data, and what changes about your event-time-based ordering rule when you can't fully trust event_time itself.

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **It's a related but distinct problem.** Late-arriving mobile data is late *arrival*, with a trustworthy event_time. Clock skew means the event_time *itself* may be wrong by up to 90 seconds relative to another region's events — the timestamp you're trusting to order records could itself be the source of the disorder.
- **The consequence for the last-writer-wins rule in Step 4:** a 90-second skew means two genuinely-simultaneous updates from different regions could have event_times that put them in the *wrong* relative order by up to 90 seconds. If this matters for correctness (not just cosmetically), the fix is widening the lateness/reconciliation window to absorb the skew, or — for anything where getting the order truly right matters (e.g. a financial ledger) — adding a secondary, trustworthy ordering signal (a centrally-assigned sequence number or a hybrid logical clock) rather than relying on wall-clock event_time alone across regions.
- **The tell:** recognizing that "trust the event_time" (Step 4's rule) has a hidden assumption — that event_time is itself accurate — and that clock skew is exactly the scenario where that assumption quietly breaks, is the generalizing move an interviewer is listening for, not just reciting "add a buffer."

</details>

---

## C. Backfilling Two Years of History Without Downtime

**Interviewer prompt:**
> "How would you backfill two years of history into this warehouse without taking down the incremental pipeline that's also currently running against live data?"

### Step 1 — Clarifying questions

- **Is the two years of history sitting in the same source, or a separate archive?** → Same Postgres source; `created_at` goes back that far, `updated_at` is reliable for the same period.
- **Can the backfill tolerate being slower than the live incremental job, as long as it doesn't block it?** → Yes.
- **Does the target table have any constraint that would make concurrent writes from two jobs risky (a single-writer assumption, a lock-heavy trigger)?** → No, it's a straightforward `ON CONFLICT`-upserted table.

### Step 2 — Name the core risk before proposing a design

> "The risk isn't the historical data itself — it's that a naive backfill (one big job reading two years of rows and writing them into the same target table the live incremental job also writes to) can starve the live job of database connections/IO, or worse, race with it: if the backfill and the incremental job both touch the same row concurrently, whichever writes last silently wins, with no guarantee it's the more-recent data."

### Step 3 — Design: chunked, isolated, and idempotent

> "I'd chunk the backfill by date range — say, one month at a time — running as a separate, lower-priority job, extracting and upserting through the exact same idempotent merge path the incremental job uses (`concepts/03_loading_strategies.md`'s staging + merge pattern). Because both jobs upsert on the same primary key with 'last value wins,' and the backfill is only ever touching dates the live incremental job has already passed and isn't revisiting, there's no meaningful overlap for them to race on in practice."

```
Backfill job:      chunks by month, oldest -> newest, low priority, upserts via ON CONFLICT
Incremental job:   keeps running normally against its own watermark, unaffected
Overlap risk:      near-zero in practice, IF the backfill only touches dates
                   strictly before the incremental job's watermark
```

### Step 4 — Call out the one real overlap risk and how to close it

> "The one place this could still go wrong: if the backfill's date chunking ever reaches up to *today*, it could momentarily touch the same rows the incremental job is actively upserting. I'd cap the backfill's range to end safely behind the incremental watermark — with a buffer — so the two jobs are provably touching disjoint row sets, rather than relying on 'probably fine because they're both upserts.'"

### Step 5 — Narrate monitoring and rollback

> "Each monthly chunk gets its own row-count and checksum-style sanity check against the source before moving to the next chunk — the goal is catching a bad chunk early, not discovering two years in that month 3 silently missed half its rows. Because every chunk's load is idempotent, a failed or wrong chunk can just be re-run from scratch with no cleanup step first."

### Step 6 — Trade-off, stated unprompted

> "Chunking by month, oldest-first, low-priority is slower than one giant parallel bulk load would be — but a giant parallel load is exactly what risks starving the live pipeline's connections/IO, which is the one thing this design isn't allowed to do. If 'as fast as possible' genuinely mattered more than 'never touch the live pipeline's headroom,' that's a different, explicit trade-off to negotiate with whoever owns that constraint — not something to quietly decide alone."

---

## D. Log-Based CDC: Replicating a MySQL Orders Table Near-Real-Time

**Interviewer prompt:**
> "Design a pipeline to replicate our MySQL `orders` table into the warehouse in near-real-time, including deletes."

### Step 1 — Clarifying questions

- **How near-real-time?** → Under a minute of lag is the goal.
- **Are deletes actually happening on this table, and do they matter for reporting?** → Yes — cancelled orders are hard-deleted, and finance needs cancellation counts to be accurate quickly.
- **Is direct binlog access to the MySQL instance something the team can get, operationally?** → Yes, replication user access is available.

### Step 2 — Name why this rules out timestamp-based incremental outright

> "Sub-minute freshness plus real deletes rules out timestamp-based incremental extraction on both counts — it can't see deletes at all, and polling frequently enough to approximate sub-minute freshness would hammer the source with near-continuous queries anyway. This is squarely a CDC problem, and specifically log-based CDC, not the trigger-based alternative — reading the binlog directly means zero extra write load on the OLTP table, versus a trigger adding a write to a shadow table on every single application write."

### Step 3 — Describe the architecture

```
MySQL orders table --(binlog)--> CDC connector (e.g. Debezium)
                                      |
                                 change event stream (ordered, per-key)
                                      |
                                 stream consumer -> upserts / tombstones into warehouse
```

> "The CDC connector reads the binlog and emits one event per row-level change, each carrying enough information to apply an upsert (for insert/update) or a tombstone (for delete). A stream consumer applies these events into the warehouse table, keyed on the order's primary key."

### Step 4 — Handle ordering, replay, and the connector's own offset

> "Two correctness requirements, both non-negotiable here: events for the *same key* must be applied in the order the binlog emitted them — most CDC connectors guarantee this per-key by partitioning the stream on the row's key. And the whole apply step must be idempotent, because any real message transport is at-least-once — the consumer may see the same event twice after a restart. I'd track the connector's own binlog position (its committed offset) durably, and make the apply step a no-op for any event at or behind the offset the consumer has already committed — the same gap-aware, idempotent-replay pattern in `practice/coding_problems.md`'s CDC problem."

### Step 5 — Handle a delete explicitly, and a schema change

> "A `DELETE` event applies as a tombstone — I'd default to a soft delete (flag `is_deleted = true`, keep the row) rather than physically removing it from the warehouse, so historical reporting isn't silently rewritten the moment something is deleted upstream; a hard delete is a business decision to make deliberately, not a default. If MySQL's schema changes mid-stream — a column added or retyped — the connector will start emitting events in the new shape; the consumer needs to handle both shapes gracefully during the transition, exactly the schema-drift risk in `interview_questions/03_critique_and_debug.md`, applied to a live stream instead of a batch job, where there's no natural 'next run' boundary to fix a break before more data arrives."

### Step 6 — Trade-off, stated unprompted

> "Log-based CDC is the right call given the stated freshness and delete requirements, but it's real added operational complexity — a CDC connector to run and monitor, binlog retention on the MySQL side to manage, and a new failure mode (the consumer falling behind the binlog's retention window, which would silently and permanently lose changes). If the freshness requirement were actually 'once a day is fine' and deletes were rare, I'd talk the team out of this in favor of the far simpler timestamp-incremental-plus-reconciliation design from Scenario A — CDC is the right tool here specifically because both constraints (sub-minute latency, real deletes) are true at once."

---

**Next:** [02 — Rapid-Fire Q&A](02_rapid_fire_qna.md)
