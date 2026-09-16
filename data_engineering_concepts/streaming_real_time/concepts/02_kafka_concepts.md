# Concept 02: Apache Kafka Concepts

**Covers:**
- Architecture: brokers, topics, partitions, replicas
- Producers: partitioning strategies and acknowledgement levels
- Consumers and consumer groups: offset management and rebalancing
- Message ordering guarantees — and their limits
- Retention policies: time-based, size-based, log compaction

*All Python below is real, runnable stdlib — copy any block into a `python3` shell and it runs as shown. Kafka itself isn't installed anywhere here; every class below simulates the real mechanism closely enough that the behavior — and the gotchas — transfer directly. Real Kafka API calls are shown in comments throughout.*

Kafka is a distributed, partitioned, replicated commit log that acts as a durable message bus between producers and consumers. Almost everything interview-worthy about Kafka follows from that one sentence — it's a *log*, not a queue, and once you see it that way, offsets, replay, and consumer groups all stop being separate facts to memorize.

---

## 1. Architecture: Brokers, Topics, Partitions, Replicas

A **topic** is a named stream of messages, split into **partitions** for parallelism. Each partition is an ordered, append-only log — every message gets a monotonically increasing **offset**, and that offset is only ever meaningful *within its own partition*.

```python
import threading

class Partition:
    """An ordered, immutable sequence of messages. Ordering is guaranteed
    WITHIN a partition; each message gets a monotonically increasing offset."""
    def __init__(self, partition_id):
        self.partition_id = partition_id
        self.messages = []
        self.high_watermark = 0  # next offset to be written
        self._lock = threading.Lock()

    def append(self, message):
        with self._lock:
            message["offset"] = self.high_watermark
            self.messages.append(message)
            self.high_watermark += 1
        return message["offset"]

    def read(self, offset, max_messages=10):
        end = min(offset + max_messages, len(self.messages))
        return self.messages[offset:end]


class Topic:
    """A named feed of messages, split into partitions. More partitions =
    more parallelism, but more complexity (ordering only holds per-partition,
    more moving parts to coordinate). Typical production topics: 6-12
    partitions, replication factor 3."""
    def __init__(self, name, num_partitions=3, replication_factor=1):
        self.name = name
        self.num_partitions = num_partitions
        self.replication_factor = replication_factor
        self.partitions = {i: Partition(i) for i in range(num_partitions)}
```

```text
Kafka cluster layout (replication factor 3, 3 partitions, 3 brokers):

  +-----------+    +-----------+    +-----------+
  | Broker 0  |    | Broker 1  |    | Broker 2  |
  | P0 (lead) |    | P1 (lead) |    | P2 (lead) |
  | P1 (repl) |    | P2 (repl) |    | P0 (repl) |
  | P2 (repl) |    | P0 (repl) |    | P1 (repl) |
  +-----------+    +-----------+    +-----------+

Every partition has one leader broker (handles all reads/writes) and
N-1 replica brokers that passively copy the leader's log. If a leader's
broker dies, one of its replicas is promoted -- this is what
"replication factor 3" buys: the topic survives up to 2 broker failures
per partition without losing committed data.
```

---

## 2. Producers: Partitioning Strategies and Acknowledgements

A producer decides which partition each message lands in, using one of three strategies:

- **Key-based** (the default and the one worth knowing cold): `hash(key) % num_partitions`. Every message with the same key always lands in the same partition.
- **Round-robin**: spread messages evenly when there's no key (or ordering doesn't matter).
- **Custom**: a user-supplied partitioner function for special routing needs.

```python
import hashlib

class Producer:
    def __init__(self, acks="all"):
        self.acks = acks  # 0 = fire-and-forget, 1 = leader ack, all = every replica acks
        self._rr_counter = 0

    def _partition_for(self, key, num_partitions):
        if key is None:
            p = self._rr_counter % num_partitions
            self._rr_counter += 1
            return p
        h = int(hashlib.md5(str(key).encode()).hexdigest(), 16)
        return h % num_partitions

    def send(self, topic, key, value):
        partition = self._partition_for(key, topic.num_partitions)
        offset = topic.partitions[partition].append({"key": key, "value": value})
        return {"partition": partition, "offset": offset}

topic = Topic("user-clicks", num_partitions=3)
producer = Producer(acks="all")

events = [
    ("user-101", "click /home"), ("user-102", "click /products"),
    ("user-101", "purchase laptop"), ("user-103", "click /home"),
    ("user-102", "click /cart"), ("user-101", "click /checkout"),
]
for key, value in events:
    result = producer.send(topic, key, value)
    print(f"key={key:<10} -> partition={result['partition']}, offset={result['offset']}")
# key=user-101  -> partition=2, offset=0
# key=user-102  -> partition=0, offset=0
# key=user-101  -> partition=2, offset=1   <- same key, same partition, next offset
# key=user-103  -> partition=1, offset=0
# key=user-102  -> partition=0, offset=1
# key=user-101  -> partition=2, offset=2
```

```text
# Real Kafka producer (confluent-kafka-python):
#   from confluent_kafka import Producer
#   p = Producer({'bootstrap.servers': 'localhost:9092'})
#   p.produce('user-clicks', key='user-101', value='{"action":"click"}')
#   p.flush()
```

**Acknowledgement levels (`acks`)** trade latency for durability:

| `acks` | Meaning | Risk |
|---|---|---|
| `0` | Fire and forget, don't wait for any broker response | Message can be silently lost |
| `1` | Wait for the partition leader to acknowledge | Lost if the leader crashes before replicating |
| `all` | Wait for every in-sync replica to acknowledge | Slowest, but safest — no acknowledged message is lost as long as at least one replica survives |

---

## 3. Consumers and Consumer Groups

A **consumer group** is Kafka's mechanism for parallel consumption with a guarantee: **each partition is assigned to exactly one consumer within a group at a time.** This is the single fact that explains both scaling up and a whole category of interview curveballs.

```python
class Consumer:
    def __init__(self, consumer_id):
        self.consumer_id = consumer_id
        self.assigned_partitions = []
        self.offsets = {}  # partition_id -> next offset to read

    def assign(self, partition_ids):
        self.assigned_partitions = partition_ids
        for pid in partition_ids:
            self.offsets.setdefault(pid, 0)

    def poll(self, topic, max_messages=10):
        results = []
        for pid in self.assigned_partitions:
            batch = topic.partitions[pid].read(self.offsets[pid], max_messages)
            results.extend(batch)
            if batch:
                self.offsets[pid] = batch[-1]["offset"] + 1
        return results


class ConsumerGroup:
    """Round-robin partition assignment. Kafka guarantees one partition
    -> one consumer within a group; if consumers > partitions, the extra
    consumers sit idle."""
    def __init__(self, group_id):
        self.group_id = group_id
        self.consumers = []

    def add_consumer(self, consumer):
        self.consumers.append(consumer)

    def rebalance(self, topic):
        for c in self.consumers:
            c.assigned_partitions = []
        n = len(self.consumers)
        if n == 0:
            return {}
        for pid in range(topic.num_partitions):
            self.consumers[pid % n].assigned_partitions.append(pid)
        for c in self.consumers:
            c.assign(c.assigned_partitions)
        return {c.consumer_id: c.assigned_partitions for c in self.consumers}
```

```python
topic = Topic("user-clicks", num_partitions=3)

# Scenario 1: 3 consumers, 3 partitions -- perfect 1:1
group = ConsumerGroup("analytics-group")
for i in range(1, 4):
    group.add_consumer(Consumer(f"consumer-{i}"))
print(group.rebalance(topic))
# {'consumer-1': [0], 'consumer-2': [1], 'consumer-3': [2]}

# Scenario 2: 2 consumers, 3 partitions -- uneven, one consumer does 2x the work
group2 = ConsumerGroup("dashboard-group")
group2.add_consumer(Consumer("consumer-A"))
group2.add_consumer(Consumer("consumer-B"))
print(group2.rebalance(topic))
# {'consumer-A': [0, 2], 'consumer-B': [1]}

# Scenario 3: 4 consumers, 3 partitions -- one consumer sits idle
group3 = ConsumerGroup("excess-group")
for i in range(4):
    group3.add_consumer(Consumer(f"consumer-{i}"))
print(group3.rebalance(topic))
# {'consumer-0': [0], 'consumer-1': [1], 'consumer-2': [2], 'consumer-3': []}
```

```text
# Real Kafka consumer:
#   c = Consumer({'bootstrap.servers': 'localhost:9092',
#                 'group.id': 'analytics-group',
#                 'auto.offset.reset': 'earliest',
#                 'enable.auto.commit': False})   # manual commit -- see 05_exactly_once_semantics.md
#   c.subscribe(['user-clicks'])
#   while True:
#       msg = c.poll(1.0)
#       if msg: process(msg); c.commit(msg)
```

Two consequences worth stating unprompted in an interview:

1. **Adding more consumers than partitions doesn't add throughput.** Scenario 3 is the direct answer to "how do I scale this consumer group further" once you're already at one consumer per partition — the honest answer is "add more partitions to the topic," not "add more consumers."
2. **A rebalance stops the world for that group, briefly.** Every time a consumer joins or leaves (deploy, crash, scale-up), the group re-assigns partitions, and consumers pause processing during that window. A consumer group that rebalances *constantly* — because a consumer keeps crashing, or a poke-mode long-poll makes a consumer look dead — is a real, common production incident; see `interview_questions/01_worked_scenarios.md` for a full diagnostic walkthrough of that exact symptom.

**Offset commits.** A consumer's committed offset is its durable bookmark — "everything up to and including this offset has been handled." Offsets can be auto-committed on a timer (simple, but risks committing an offset for a message that was read but not yet fully processed) or manually committed after processing completes (safer, and the only way to get at-least-once rather than accidentally-at-most-once — see `concepts/05_exactly_once_semantics.md`).

---

## 4. Message Ordering Guarantees

Kafka's ordering guarantee is precise and easy to state, and precisely as easy to misremember under pressure:

```text
- Messages with the SAME KEY always go to the SAME partition.
- Within a single partition, messages are STRICTLY ordered.
- ACROSS partitions, there is NO ordering guarantee at all.
```

```python
order_topic = Topic("orders", num_partitions=2)
producer = Producer()

events = [
    ("order-A", "step 1 - created"), ("order-B", "step 1 - created"),
    ("order-A", "step 2 - paid"),    ("order-B", "step 2 - paid"),
    ("order-A", "step 3 - shipped"), ("order-B", "step 3 - shipped"),
]
for key, value in events:
    producer.send(order_topic, key, value)

for pid in range(order_topic.num_partitions):
    msgs = order_topic.partitions[pid].messages
    if msgs:
        print(f"Partition {pid}:")
        for m in msgs:
            print(f"  offset={m['offset']}: {m['value']}")
# Partition 0 (order-B lands here): step 1 - created, step 2 - paid, step 3 - shipped
# Partition 1 (order-A lands here): step 1 - created, step 2 - paid, step 3 - shipped
# -- each order's own steps are in order; order-A and order-B have no
#    ordering relationship to each other at all.
```

This is exactly why choosing the partition key correctly is a design decision, not an implementation detail: pick `order_id` as the key when per-order ordering is what matters, and don't expect any global ordering across different orders. Picking a key with too little cardinality (say, a fixed `region` with only 4 possible values on a 50-partition topic) creates a **hot partition** — most of the topic's parallelism goes unused, and the few partitions that do get traffic become the throughput ceiling. This exact failure mode is worked as a diagnosis exercise in `interview_questions/03_critique_and_debug.md`.

---

## 5. Retention Policies

Kafka retains messages according to one of three policies, set per-topic:

```text
1. TIME-BASED (default):    retention.ms = 604800000 (7 days)
   Messages older than the window are deleted. Good for: raw event logs, clickstreams.

2. SIZE-BASED:               retention.bytes = 1073741824 (1 GB per partition)
   Oldest messages deleted once a partition exceeds this size. Good for:
   high-volume topics with a hard storage budget.

3. LOG COMPACTION:           cleanup.policy = compact
   Keeps only the LATEST message per key, forever -- not a time or size window.
   Good for: changelogs, entity snapshots, CDC streams.

   Example of compaction:
     Before:  key=A:v1, key=B:v1, key=A:v2, key=B:v2, key=A:v3
     After:   key=B:v2, key=A:v3   (only the latest value per key survives)
```

| Topic type | Retention | Cleanup policy |
|---|---|---|
| Raw events | 7 days | delete |
| Aggregated | 30 days | delete |
| User profiles / entity state | forever | compact |
| CDC changelog | forever | compact |
| Temporary / debug | 1 hour | delete |

Log compaction is the mechanism that lets Kafka serve as the durable backbone for a CDC stream or an event-sourced entity store — see `concepts/04_event_driven_architecture.md` and `etl_elt_patterns/concepts/05_change_data_capture.md`, since CDC streams are one of the most common things a streaming pipeline actually consumes from Kafka.

---

## Key Takeaways

- A topic is split into partitions for parallelism; ordering is only guaranteed *within* a partition, never across partitions.
- Producers route messages to partitions by hashing the key (same key → same partition, guaranteeing per-key ordering); choosing a low-cardinality key creates a hot partition that caps throughput regardless of how many partitions the topic has.
- A consumer group guarantees one partition per consumer at a time — scaling past one consumer per partition adds nothing; the topic needs more partitions instead. Frequent rebalancing (a consumer that keeps looking dead and rejoining) is a real operational failure mode, not just theory.
- Retention is time-based, size-based, or compacted (keep only the latest value per key) — compaction is what makes Kafka viable as a durable changelog/CDC backbone, not just a transient event bus.
