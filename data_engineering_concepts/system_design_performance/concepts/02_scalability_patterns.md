# Concept 2: Scalability Patterns

**Covers:**
- Horizontal vs. vertical scaling — and why horizontal wins for data platforms
- Sharding strategies: hash, range, geographic — and the skew each one risks
- Replication: leader-follower vs. multi-leader, and the conflicts multi-leader creates
- CAP theorem, applied to real systems you'd actually pick
- Eventual consistency — what "eventually" really means operationally
- Partitioning a data lake (date/key/hash) and partition pruning
- Backpressure handling and queue-based load leveling

*This is the vocabulary for "how would this scale to 10x," which is asked in nearly every system-design interview regardless of which pipeline you designed. Config/commands shown are real; where a distributed-systems mechanism is being illustrated, the numbers are traced by hand.*

---

## 1. Horizontal vs. Vertical Scaling

**Vertical (scale UP):** add more CPU/RAM/disk to a single machine. Simpler — no distribution logic, no new failure modes — but has a hard ceiling (the biggest instance type your cloud provider sells) and a single point of failure.

**Horizontal (scale OUT):** add more machines and distribute the work. Virtually unlimited, but you now own partitioning, coordination, and partial-failure handling.

```text
Vertical:  [ 1 node: 4 -> 64 -> 512 GB RAM ]   simple, hits a ceiling
Horizontal: [node][node][node][node] ... [node]   distribute load, no ceiling,
             more moving parts (rebalancing, network partitions, coordination)
```

The practical answer in an interview: **vertical first, horizontal when vertical runs out or when a single-node failure is unacceptable** — reaching immediately for a sharded, horizontally-scaled design for a problem a bigger single Postgres instance would solve for another two years is a sign of over-engineering, not sophistication.

---

## 2. Sharding Strategies

Sharding splits data across multiple nodes so no single node holds (or serves) all of it.

**Hash sharding** — `shard = hash(key) % num_shards`. Gives near-even distribution regardless of the key's natural distribution, at the cost of losing any ability to do efficient range scans (adjacent keys land on random shards).

```python
shard_id = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16) % num_shards
```

**Range sharding** — assign contiguous key ranges to shards (`id 0-99 -> shard 0`, `100-199 -> shard 1`, ...). Enables efficient range queries (`WHERE id BETWEEN 150 AND 180` touches one shard), but is skew-prone: if writes are monotonically increasing (auto-incrementing IDs, append-only event timestamps), ALL new writes land on the newest shard — a classic "hot shard" failure mode.

```text
Range sharding failure mode with monotonic IDs:
  shard 0: ids 0-99        (fully written, now cold/read-only)
  shard 1: ids 100-199     (fully written, now cold/read-only)
  shard 2: ids 200-299     <- EVERY new write lands here, all others idle
```

**Geographic/attribute sharding** — shard by a business-meaningful attribute (region, tenant). Great for data-residency requirements (EU data stays on EU shards) and for co-locating a tenant's data for fast per-tenant queries, but distribution is only as even as the attribute itself — a platform that's 70% US traffic gives the US shard 70% of the load no matter how many shards exist.

```python
GEO_SHARD_MAP = {"US": 0, "EU": 1, "ASIA": 2, "OTHER": 3}
shard_id = GEO_SHARD_MAP.get(region, 3)
```

**Choosing one, out loud:** name the dominant query pattern first. Point lookups by a well-distributed key → hash. Range scans on an ordered key → range (and mitigate the hot-shard risk by pre-splitting or salting the key prefix). Data residency or per-tenant isolation requirements → geographic, and accept you'll need a secondary strategy for the sub-shard that's disproportionately large.

---

## 3. Replication

**Leader-Follower (master-slave):** all writes go to one leader; the leader asynchronously replicates to followers; reads can be served from any follower.

```python
def write(self, key, value):
    self.leader[key] = value
    self.pending_writes.append((key, value))   # replicated asynchronously

def replicate(self):
    while self.pending_writes:
        key, value = self.pending_writes.popleft()
        for follower in self.followers:
            follower[key] = value
```

The catch: a read against a follower immediately after a write can return stale data — the classic **replication lag** problem. This is fine for most analytics reads; it's a real bug if the application reads its own just-written data back from a follower ("read-your-writes" — usually solved by routing that specific read to the leader, or to a follower guaranteed caught up).

**Multi-Leader (master-master):** writes can go to ANY leader, and leaders sync with each other — needed for multi-region write availability (a region shouldn't have to round-trip writes to a leader on another continent). The cost: conflicting writes to the same key on two leaders before they've synced require an explicit resolution strategy.

```python
# Two leaders write the same key before syncing -> conflict
ml.write(leader_idx=0, key="product:1", value="price=99")
ml.write(leader_idx=1, key="product:1", value="price=109")

# Resolution strategy: last-write-wins (by timestamp), a CRDT merge, or an
# application-level rule ("higher price wins", "manual review queue").
```

```text
+-----------------+---------------------------+---------------------------+
| Dimension        | Leader-Follower           | Multi-Leader              |
+-----------------+---------------------------+---------------------------+
| Write path       | Single leader             | Any leader                |
| Multi-region     | Writes bottleneck to one  | Native multi-region write |
|                  | region                    |                           |
| Conflict handling| None needed (one writer)  | Required (LWW, merge, ...)|
| Complexity       | Lower                     | Higher                    |
+-----------------+---------------------------+---------------------------+
```

---

## 4. CAP Theorem

In a distributed system, a network partition WILL eventually happen — so CAP really asks: when it does, do you sacrifice **Consistency** or **Availability**? (Partition tolerance isn't optional; you don't get to choose not to handle partitions.)

```text
Partition happens: node B becomes unreachable from node A.

CP choice (e.g. HBase, MongoDB default, ZooKeeper):
    Refuse requests that can't be guaranteed consistent.
    "Read from Node B: ERROR — cannot guarantee consistency."
    -> Availability sacrificed for correctness.

AP choice (e.g. Cassandra, DynamoDB, CouchDB):
    Always answer, even with possibly-stale data.
    "Read from Node B: STALE but available."
    -> Consistency sacrificed for uptime.
```

Naming a real system for each side (not just the letters) is what separates a memorized answer from an understood one: a payments ledger is CP (an inconsistent balance is worse than a rejected request); a shopping cart or a "likes" counter is usually AP (showing a slightly stale count is far better than showing an error page).

---

## 5. Eventual Consistency

The AP choice above implies **eventual consistency**: if writes stop, every replica converges to the same value — eventually, not instantly.

```text
Write to replica 0:        [42, 0, 0]     <- inconsistent right after the write
Propagate round 1 (0->1):  [42, 42, 0]    <- still inconsistent
Propagate round 2 (1->2):  [42, 42, 42]   <- now consistent, IF no new writes arrived
```

The operational reality this hides: "eventual" has no upper bound unless your system defines one. A design that says "eventually consistent" without naming an expected convergence window (seconds? minutes?) hasn't actually specified anything — a strong interview answer quantifies it ("replication lag typically under 2 seconds, alerting if it exceeds 30").

---

## 6. Partitioning a Data Lake

The same "spread data out" idea applies to files in a lake, and it's the single biggest lever for query speed via **partition pruning** — skipping files that can't possibly match a query's filter.

```text
Common partitioning schemes:
  By date:  s3://lake/events/year=2024/month=01/day=15/
  By key:   s3://lake/orders/region=US/state=CA/
  By hash:  s3://lake/users/bucket=007/
```

```python
# Partition pruning in action: query for one day skips the other 29
total = sum(len(v) for v in data_lake.values())          # e.g. 300 records
scanned = len(data_lake["year=2024/month=01/day=15"])    # e.g. 12 records
# 96% of the table never touched — this is why "partition by the columns
# your queries actually filter on" is close to a free performance win.
```

Pick the partition column by query pattern, same discipline as sharding: date is the near-universal first choice (almost every analytical query has a date filter); a second-level partition or clustering column should be whatever's filtered WITHIN a date range often enough to be worth it (see `03_optimization_techniques.md`).

---

## 7. Backpressure Handling

Backpressure is what happens when a consumer can't keep up with a producer — a real, constant condition in streaming systems, not an edge case.

```text
Strategies:
  1. Drop:     discard excess (acceptable for metrics/telemetry, never for money)
  2. Buffer:   queue up to a limit (bounded — an unbounded buffer just delays the OOM)
  3. Throttle: slow the producer down (requires the producer to cooperate)
  4. Sample:   process every Nth message (acceptable when approximate is fine)
```

```python
class BackpressureHandler:
    def __init__(self, buffer_limit=10):
        self.buffer = deque(maxlen=buffer_limit)
        self.dropped = 0

    def produce(self, msg):
        if len(self.buffer) >= self.buffer_limit:
            self.dropped += 1          # drop strategy: excess is discarded, not queued
            return False
        self.buffer.append(msg)
        return True
```

**Which strategy, out loud:** name what the data IS before picking. Metrics/logs → drop or sample is usually fine (a gap in a metrics stream is invisible; nobody audits it row by row). Financial transactions or anything individually audit-able → buffer + throttle, never drop — a dropped payment event is a support ticket and possibly a compliance incident, not an acceptable trade-off.

---

## 8. Queue-Based Load Leveling

A queue sitting between a bursty producer and a steady-rate consumer absorbs the burst without either side needing to change behavior.

```python
bursts = [50, 5, 5, 100, 10, 5, 80, 5, 5, 5]   # incoming per tick — spiky
steady_rate = 30                                # consumer: fixed rate

for incoming in bursts:
    queue.enqueue_batch(range(incoming))
    processed = queue.dequeue_steady(steady_rate)
    # queue depth absorbs the spike; consumer never sees a burst directly
```

**Output** (tracing the first few ticks):
```text
Tick 0: +50 incoming, -30 processed, queue depth= 20
Tick 1: + 5 incoming, -30 processed, queue depth=  0   (consumer catches up)
Tick 2: + 5 incoming, - 5 processed, queue depth=  0
Tick 3: +100 incoming, -30 processed, queue depth= 70   (absorbing the spike)
Tick 4: + 10 incoming, -30 processed, queue depth= 50
```

This is exactly what a Kafka topic does in front of a stream processor, or what SQS does in front of a Lambda/worker fleet — the queue's depth is the metric to alert on (a permanently growing depth means the consumer is under-provisioned, not that the queue is "doing its job").

---

## Key Takeaways

- Prefer vertical scaling until it demonstrably runs out — horizontal scaling buys unlimited headroom at the cost of real distributed-systems complexity, and reaching for it too early is over-engineering.
- Hash sharding gives even distribution but kills range queries; range sharding enables range queries but risks hot shards on monotonic keys; geographic sharding matches data-residency needs but is only as even as the attribute itself.
- Leader-follower is simpler and has one writer; multi-leader supports multi-region writes but requires an explicit conflict-resolution strategy.
- CAP is not abstract — name a real system and a real reason for choosing CP or AP for the specific data in front of you.
- "Eventually consistent" without a quantified convergence window is an incomplete answer.
- Partition data lakes by the column your queries actually filter on (date first, almost always) — partition pruning is one of the cheapest wins available.
- Backpressure strategy depends on what the data IS: drop/sample for approximate telemetry, buffer/throttle for anything that must not be lost.
- A queue between a bursty producer and a steady consumer is the standard load-leveling pattern — Kafka and SQS are this pattern, productized.
