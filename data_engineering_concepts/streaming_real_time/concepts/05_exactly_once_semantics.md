# Concept 05: Exactly-Once Semantics

**Covers:**
- The three delivery guarantees: at-most-once, at-least-once, exactly-once
- How Kafka actually achieves exactly-once: idempotent producers + transactions
- Application-level deduplication strategies, when infrastructure-level exactly-once isn't available
- Two-phase commit — where it fits, and why sagas are usually preferred across services
- Where the same idea lives on the batch side, so you don't re-derive it from scratch

*All Python below is real, runnable stdlib — copy any block into a `python3` shell and it runs as shown.*

In a distributed streaming system, failures aren't an edge case — networks partition, brokers crash, consumers restart mid-batch. The question every delivery guarantee answers is the same one: **when something fails partway through, how many times does each message actually get processed?**

---

## 1. At-Most-Once: Fire and Forget

Send the message, don't wait for an acknowledgement. If the network drops it, it's gone — no retry, no recovery.

```python
import random
random.seed(42)

messages = [f"msg-{i}" for i in range(10)]
network_failure_rate = 0.3
delivered = []
for m in messages:
    if random.random() < network_failure_rate:
        continue  # lost -- no retry, ever
    delivered.append(m)

print(f"Sent: {len(messages)}, Delivered: {len(delivered)}, Lost: {len(messages) - len(delivered)}")
# Sent: 10, Delivered: 5, Lost: 5
```

```text
# Real Kafka: producer = Producer({'acks': '0'})
```

Fastest, simplest, and the only guarantee that can silently lose data. Use it for metrics sampling and best-effort logging — never for payments, orders, or anything where a missing record is a real business problem.

---

## 2. At-Least-Once: Retry Until Acknowledged

Retry sending until an acknowledgement comes back. If the *message* was actually delivered but its *acknowledgement* was lost in transit, the sender doesn't know that — it retries, and the message is now duplicated downstream.

```python
random.seed(42)
messages = [f"msg-{i}" for i in range(10)]
failure_rate, max_retries = 0.3, 3
delivered_log = []

for m in messages:
    for attempt in range(1, max_retries + 1):
        ack_lost = random.random() < failure_rate
        delivered_log.append(m)          # message reaches the queue regardless
        if not (ack_lost and attempt < max_retries):
            break                        # stop retrying once "acknowledged"

unique = len(set(delivered_log))
print(f"Original: {len(messages)}, Total deliveries: {len(delivered_log)}, Unique: {unique}, Dupes: {len(delivered_log) - unique}")
# Original: 10, Total deliveries: 18, Unique: 10, Dupes: 8
```

```text
# Real Kafka: producer = Producer({'acks': 'all', 'retries': 5})
# Consumer side: if offsets auto-commit BEFORE processing, a crash after
# commit-but-before-processing LOSES the message entirely -- see the
# critique case in interview_questions/03_critique_and_debug.md.
```

No data loss, but duplicates are now the downstream system's problem. This is the default most real streaming systems run at, precisely because it's the guarantee that's cheap to provide at the infrastructure layer — the cost gets paid at the processing layer instead, via idempotent handling or deduplication.

---

## 3. Exactly-Once: Idempotent Producer + Transactions

Kafka achieves an exactly-once *effect* (not a magically exactly-once network, which is provably impossible — see below) by combining two mechanisms:

1. **Idempotent producer.** Every message carries a `(producer_id, sequence_number)`. The broker tracks the highest sequence number it has accepted per producer and silently drops any retry whose sequence number it's already seen — a retried send is detected and rejected as a duplicate at the broker itself, not left for the consumer to notice.
2. **Transactions.** The producer's write to the output topic and the consumer's offset commit happen atomically — either both are visible, or neither is. This is what makes "read, process, write, commit offset" safe to retry as a whole unit without ever producing a partial, half-applied result.

```python
class IdempotentQueue:
    def __init__(self):
        self.messages = []
        self._seen_sequences = {}  # producer_id -> highest sequence accepted

    def put(self, producer_id, sequence_num, message):
        if sequence_num <= self._seen_sequences.get(producer_id, -1):
            return False  # duplicate -- rejected
        self._seen_sequences[producer_id] = sequence_num
        self.messages.append(message)
        return True

random.seed(42)
queue = IdempotentQueue()
messages = [f"msg-{i}" for i in range(10)]
failure_rate, max_retries, producer_id = 0.3, 3, "producer-001"
rejected = 0

for seq, m in enumerate(messages):
    for attempt in range(1, max_retries + 1):
        ack_lost = random.random() < failure_rate
        accepted = queue.put(producer_id, seq, m)
        if not accepted:
            rejected += 1
        if not (ack_lost and attempt < max_retries):
            break

print(f"Original: {len(messages)}, Accepted: {len(queue.messages)}, Duplicates rejected: {rejected}")
# Original: 10, Accepted: 10, Duplicates rejected: 8
```

```text
# Real Kafka exactly-once producer:
#   producer = Producer({'enable.idempotence': True, 'transactional.id': 'my-txn-producer'})
#   producer.init_transactions()
#   producer.begin_transaction()
#   producer.produce('output-topic', value='result')
#   producer.send_offsets_to_transaction(consumer.position(), consumer.group_metadata())
#   producer.commit_transaction()
```

A precise thing worth saying explicitly if asked "how does Kafka achieve exactly-once" cold: **true exactly-once *delivery* across an unreliable network is not achievable** — a sender can never fully distinguish "the request failed" from "the request succeeded but the response was lost," so it can never know for certain whether to retry. What Kafka actually provides is exactly-once **effect**: at-least-once delivery (retry freely, accept duplicates arriving at the broker) combined with idempotent processing (the broker recognizes and discards duplicates before they have any visible effect). That reframing — "exactly-once effect, not exactly-once delivery" — is the single most common thing candidates get subtly wrong.

---

## 4. Application-Level Deduplication

When infrastructure-level exactly-once isn't available (crossing between two different systems, e.g. Kafka into a non-transactional sink), deduplication moves to the application:

```python
from collections import OrderedDict
import hashlib

# --- Strategy 1: Idempotency key ---
class IdempotentProcessor:
    def __init__(self):
        self.processed_keys = set()
        self.results = []

    def process(self, idempotency_key, value):
        if idempotency_key in self.processed_keys:
            return "SKIPPED (duplicate)"
        self.processed_keys.add(idempotency_key)
        self.results.append(value)
        return f"processed: {value}"

p = IdempotentProcessor()
for key, val in [("k1", "order-A"), ("k2", "order-B"), ("k1", "order-A")]:
    print(p.process(key, val))
# processed: order-A
# processed: order-B
# SKIPPED (duplicate)

# --- Strategy 2: Content-hash dedup (no key available) ---
seen_hashes = set()
for msg in ['{"user":"a","action":"click"}', '{"user":"a","action":"click"}']:
    h = hashlib.sha256(msg.encode()).hexdigest()[:12]
    print("DUPLICATE" if h in seen_hashes else "NEW")
    seen_hashes.add(h)
# NEW
# DUPLICATE

# --- Strategy 3: Database upsert, last-write-wins by version/timestamp ---
database = {}
for event in [{"id": "U1", "name": "Alice", "ts": 1000}, {"id": "U1", "name": "Alice-old", "ts": 999}]:
    if event["id"] in database and database[event["id"]]["ts"] >= event["ts"]:
        print(f"SKIPPED stale write for {event['id']}")
    else:
        database[event["id"]] = event
        print(f"UPSERTED {event['id']}")
# UPSERTED U1
# SKIPPED stale write for U1
```

| Strategy | Pros | Cons |
|---|---|---|
| Idempotency key | Simple, reliable | Requires a key in the message |
| Content hash | No key needed | Can't distinguish a legitimate repeat event from a true duplicate |
| Database upsert | Natural fit for entity state | Needs a timestamp/version column to compare against |

This is exactly the same idea as `etl_elt_patterns/concepts/06_idempotency_reliability.md`'s framing of idempotency for batch loads — "replace what should exist for this scope" rather than "add this to whatever's already there" — applied at the level of a single streamed message instead of a whole batch load.

---

## 5. Two-Phase Commit (2PC), Briefly

2PC coordinates multiple participants into an all-or-nothing commit across two phases: **prepare** (coordinator asks "can you commit?", each participant votes yes/no) and **commit/abort** (if every vote was yes, tell everyone to commit; if any vote was no, tell everyone to abort). This is the mechanism operating *inside* Kafka's own transactional producer, coordinating writes across the partitions and brokers involved in one transaction.

```text
Phase 1: PREPARE         Phase 2: COMMIT or ABORT
  Broker-0: VOTE YES        (all yes) -> Broker-0: COMMITTED
  Broker-1: VOTE YES                     Broker-1: COMMITTED
  Broker-2: VOTE YES                     Broker-2: COMMITTED

  Broker-0: VOTE YES        (one no)  -> Broker-0: ABORTED
  Broker-1: VOTE NO                      Broker-1: ABORTED
  Broker-2: VOTE YES                     Broker-2: ABORTED
```

2PC guarantees strong consistency but **blocks** while every participant is polled — it trades availability for that guarantee. This is exactly why 2PC is the right tool *inside* a single system's internals (Kafka's own transaction coordinator) but the wrong tool *across* independently-owned services — that's what the Saga pattern (`concepts/04_event_driven_architecture.md`) exists to solve instead, accepting eventual consistency in exchange for not blocking one service on another's availability.

---

## 6. Comparison

| Property | At-Most-Once | At-Least-Once | Exactly-Once |
|---|---|---|---|
| Data loss? | Yes | No | No |
| Duplicates? | No | Yes | No |
| Kafka config | `acks=0` | `acks=all` + retries | `acks=all` + idempotence + transactions |
| Performance | Fastest | Fast | Slowest |
| Use case | Metrics, sampling | Most streaming workloads | Payments, financial/order data |

In practice, most streaming jobs run at-least-once plus application-level dedup rather than paying the full latency/throughput cost of infrastructure-level exactly-once everywhere — reach for true exactly-once specifically where a duplicate has real financial or correctness consequences, not as a default for every pipeline.

---

## Key Takeaways

- At-most-once can lose messages; at-least-once can duplicate them; exactly-once (idempotent producer + transactions) provides neither loss nor duplication, at the highest complexity and latency cost.
- True exactly-once *delivery* over an unreliable network isn't achievable — what's achievable, and what Kafka actually provides, is exactly-once *effect*: at-least-once delivery plus broker-side idempotent deduplication via `(producer_id, sequence_number)`.
- When exactly-once isn't available end-to-end (crossing into a non-transactional sink), application-level deduplication — idempotency keys, content hashing, or timestamped upserts — is the fallback, and it's the same idempotency discipline `etl_elt_patterns` teaches for batch loads, applied per-message.
- 2PC gives strong consistency at the cost of blocking, and is the mechanism inside Kafka's own transactional writes; across independently-owned services, the Saga pattern is almost always the better fit.
