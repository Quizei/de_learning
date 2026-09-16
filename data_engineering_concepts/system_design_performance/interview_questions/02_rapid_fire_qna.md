# 2. Rapid-Fire Q&A

Part of the [Interview Questions](README.md) series.

[File 1](01_worked_scenarios.md) rehearses full design conversations. This
file is the other interview mode: fast, direct definitional questions with no
scenario attached — the kind asked in a phone screen, or dropped mid-
conversation to check you actually understand a term you just used. Answer
each one out loud in under 30 seconds before reading the model answer.

Every term here is demonstrated somewhere in `../concepts/` or in file 1 —
cross-references point back to the concrete moment it showed up.

---

## Architecture Patterns

**Q: Batch vs. streaming — what's the actual difference, not just "speed"?**
> Batch processes a bounded chunk of data on a schedule and either succeeds
> or fails as a whole, so recovery is "re-run it." Streaming processes an
> unbounded sequence continuously, holds in-flight state (windows,
> aggregations) that must be checkpointed, and has no natural "job run"
> boundary — health is measured by consumer lag, not by an exit code. It's a
> different operating model, not the same job running faster
> (`../concepts/01_pipeline_architectures.md`, sections 1-2).

**Q: When do you actually reach for Lambda instead of just streaming?**
> Only when you need BOTH a fast, approximate number AND a strictly
> accurate/audited number for the SAME metric, and both are genuinely
> non-negotiable — e.g. Scenario 2's surge pricing (live pricing needs speed;
> finance needs a corrected number). If there's no real second, differently-
> derived need, Lambda is just paying for two codepaths that will drift out
> of sync (`01_worked_scenarios.md`, Scenario 2, Step 3).

**Q: What's the difference between Lambda and Kappa, in one line each?**
> Lambda runs two SEPARATE codepaths (batch + streaming) computing related
> but genuinely different views of the same data. Kappa runs ONE streaming
> codepath and handles "recompute everything correctly" by replaying the
> immutable log through a new processor version instead of maintaining a
> second batch layer (`../concepts/01_pipeline_architectures.md`, sections
> 3-4).

**Q: Name a real scenario where Kappa is clearly better than Lambda, and one
where the reverse is true.**
> Kappa wins when there's no genuinely SECOND derivation needed — Scenario
> 3's IoT telemetry (raw + rollup is one computation at two grains, not two
> competing ones). Lambda wins when the two audiences truly need different
> business logic applied to the same underlying signal — Scenario 2's surge
> pricing (live approximation vs. corrected historical). The tell is whether
> you can name what's DIFFERENT about the two derivations, not just that two
> layers exist.

---

## Scalability

**Q: Vertical vs. horizontal scaling — how do you decide, in an interview?**
> Default to vertical until it demonstrably runs out, or until a single-node
> failure is unacceptable for the SLA — reaching for a sharded, horizontally
> distributed design immediately is over-engineering for a problem a bigger
> single instance would solve. State this preference explicitly; it reads as
> judgment, not as a lack of ambition (`../concepts/02_scalability_patterns.md`,
> section 1).

**Q: Hash sharding vs. range sharding — the one-line trade-off?**
> Hash gives even distribution but kills efficient range queries; range
> enables range queries but risks a hot shard when the key is monotonically
> increasing (auto-increment IDs, timestamps) — all new writes land on the
> newest shard (`../concepts/02_scalability_patterns.md`, section 2).

**Q: CAP theorem — what's the actual choice being made, and give a real
system for each side?**
> Network partitions are inevitable, so the real choice is Consistency vs.
> Availability during one. CP (e.g. HBase, MongoDB default): refuse to serve
> possibly-stale reads during a partition. AP (e.g. Cassandra, DynamoDB):
> always answer, possibly with stale data. Naming a real system for each
> side, tied to a real use case (a payments ledger is CP; a "likes" counter
> is AP), is what separates understanding from reciting letters
> (`../concepts/02_scalability_patterns.md`, section 4).

**Q: What does "eventually consistent" actually promise?**
> That IF writes stop, all replicas converge to the same value — with NO
> promised time bound unless you state one yourself. An answer that says
> "eventually consistent" without naming an expected convergence window
> (seconds? minutes?) hasn't actually specified anything concrete
> (`../concepts/02_scalability_patterns.md`, section 5).

**Q: Leader-follower vs. multi-leader replication — when do you need
multi-leader specifically?**
> When you need writes accepted in multiple regions without round-tripping
> every write to one region's leader — but multi-leader requires an explicit
> conflict-resolution strategy (last-write-wins, CRDT merge, application
> rule) for writes to the same key from two leaders before they've synced.
> Leader-follower is simpler and sufficient whenever a single write region is
> acceptable (`../concepts/02_scalability_patterns.md`, section 3).

**Q: What's backpressure, and name the four handling strategies.**
> Backpressure is a consumer unable to keep up with a producer — a normal,
> constant condition in streaming systems, not an edge case. Strategies:
> drop (fine for approximate telemetry, never for anything individually
> audited), buffer (bounded — an unbounded buffer just delays the OOM),
> throttle (slow the producer — requires producer cooperation), sample
> (process every Nth message, when approximate is acceptable)
> (`../concepts/02_scalability_patterns.md`, section 7).

---

## Optimization

**Q: Predicate pushdown vs. partition pruning vs. column pruning — the
one-line distinction for each?**
> Pushdown: apply a filter at the scan/storage layer instead of after
> loading everything. Partition pruning: skip whole files/directories based
> on partition metadata, without opening them. Column pruning: read only the
> columns a query needs — a real win specifically in columnar formats
> (`../concepts/03_optimization_techniques.md`, section 1).

**Q: Result cache vs. materialized view vs. pre-aggregation — how are these
actually different?**
> A result cache stores the exact output of ONE specific query — a changed
> WHERE clause is a miss. A materialized view stores a precomputed query
> result as a queryable table that OTHER queries can filter/aggregate
> further on top of. Pre-aggregation is the same mechanism, purpose-built
> for one known reporting need. All three are staleness bets — the staleness
> window should be stated explicitly, not left implicit
> (`../concepts/03_optimization_techniques.md`, section 3).

**Q: How do you choose a compression algorithm?**
> By how often the data is read, not by "best ratio." Hot, constantly-read
> data favors fast decompression (Snappy/Zstd) even at a worse ratio — CPU
> spent decompressing on every read adds up. Cold archival data favors
> maximum ratio (Gzip) since it's rarely read and storage cost dominates.
> High-entropy data (UUIDs, already-compressed blobs) barely compresses
> under any algorithm — don't spend CPU on it
> (`../concepts/03_optimization_techniques.md`, section 4).

**Q: What's the small-file problem, and how do you actually fix it?**
> Thousands of tiny files impose fixed per-file overhead (open/close,
> metadata, task scheduling) that dominates over the trivial data in each
> one. It's an overhead problem, not a storage-size problem — the fix is
> scheduled COMPACTION (merging small files within a partition), not
> reducing data volume (`../concepts/03_optimization_techniques.md`,
> section 6).

**Q: Data skew at the system-design level — how is it the same problem
whether it's a Spark shuffle, a Kafka partition, or a database shard?**
> All three partition work by a key, and all three inherit that key's
> real-world distribution — a hot key sends disproportionate load to one
> partition/shard regardless of which system is doing the partitioning. The
> fix generalizes too: salt the hot key so its load spreads across N
> sub-partitions instead of landing on one
> (`../concepts/03_optimization_techniques.md`, section 5).

---

## Capacity Planning & Cost

**Q: Someone says "we'll have millions of events a day" — what's your very
next question or step?**
> Convert it into events/sec, daily bytes, and retained bytes immediately —
> a volume stated in "millions a day" doesn't tell you whether you need one
> Kafka partition or two hundred. Every number you use downstream should be
> derivable from the requirements you were given, and showing the arithmetic
> is what's being scored (`../concepts/04_capacity_planning_and_cost.md`,
> sections 1-2).

**Q: What drives storage sizing vs. streaming compute sizing vs. warehouse
compute sizing — are they the same driver?**
> No, and naming that they're different is the signal. Storage: volume x
> retention / compression. Streaming compute: events/sec. Warehouse compute:
> CONCURRENCY, not raw data size — a huge warehouse queried by 3 analysts
> needs far less compute than a small one queried by 200 simultaneously
> (`../concepts/04_capacity_planning_and_cost.md`, section 3).

**Q: Why is Lambda architecture usually the most expensive option, in cost
terms specifically (not just complexity)?**
> Because it pays for a batch cluster's compute AND a continuously-running
> stream processor for the same underlying computation — streaming compute
> in particular runs (and costs money) whether or not there's traffic right
> now, so Lambda is paying that always-on cost on top of batch's cost, not
> instead of it (`../concepts/04_capacity_planning_and_cost.md`, section 4).

**Q: Reserved/committed vs. on-demand cloud compute — how do you decide
which parts of a design get which?**
> Steady-state, predictable load (a stream processor that's always on, a
> batch job that always runs) → reserved/committed pricing is meaningfully
> cheaper for the same capacity. Spiky, unpredictable load → on-demand or
> serverless, since reserving for peak capacity that mostly sits idle is the
> more expensive mistake (`../concepts/04_capacity_planning_and_cost.md`,
> section 4).

---

## The SPADE Framework

**Q: What does SPADE stand for, and why structure an answer around it?**
> Scope (clarify requirements and scale), Pipeline (sources → transforms →
> sinks), Architecture (batch/streaming/Lambda/Kappa, justified), Data Model
> (schemas, partitioning, storage format), Edge Cases (failure, skew, late
> data, scale). It exists to keep a 30-45 minute answer structured under time
> pressure — the interviewer is also implicitly checking that you covered all
> five, not just that you designed something reasonable
> (`01_worked_scenarios.md` uses this shape throughout, though narrated in
> prose rather than as five labeled headers).

**Q: If you're running out of time in a system design interview, what do you
cut, and what do you never cut?**
> Never cut Scope (clarifying questions) or a stated Architecture choice
> with justification — those anchor everything else and their absence reads
> as not knowing where to start. If short on time, compress the Data Model
> section to the fact/dimension shape without full column lists, and pick
> ONE edge case to go deep on rather than shallowly listing five — depth on
> one edge case reads stronger than a shallow list of many.

---

**Next:** [03 — Critique & Debug](03_critique_and_debug.md)
