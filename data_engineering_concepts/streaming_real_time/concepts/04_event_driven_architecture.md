# Concept 04: Event-Driven Architecture

**Covers:**
- Event sourcing — storing events instead of state, and rebuilding state by replay
- CQRS — separating the write model from the read model(s)
- The pub/sub pattern — decoupling producers from consumers
- Event schema evolution — backward/forward compatibility and upcasting
- The Saga pattern — distributed transactions without two-phase commit

*All Python below is real, runnable stdlib — copy any block into a `python3` shell and it runs as shown.*

Event-driven architecture is the design philosophy that streaming infrastructure like Kafka exists to support: instead of services calling each other directly and waiting for a response, they communicate by producing and reacting to events, each service knowing nothing about who (if anyone) consumes what it produces.

---

## 1. Event Sourcing: Store Events, Not State

The default way to model a bank account is to store its current balance and overwrite it on every transaction. **Event sourcing** stores the *sequence of things that happened* instead — `AccountOpened(1000)`, `MoneyDeposited(500)`, `MoneyWithdrawn(200)` — and derives current state by replaying that sequence from the beginning. The event log, not any derived balance, is the source of truth.

```python
import uuid
from collections import defaultdict
from datetime import datetime

class Event:
    def __init__(self, event_type, aggregate_id, data):
        self.event_id = str(uuid.uuid4())[:8]
        self.event_type = event_type
        self.aggregate_id = aggregate_id
        self.data = data
        self.timestamp = datetime.now().isoformat()
        self.version = None

class EventStore:
    """Append-only. Events are NEVER updated or deleted -- state is always
    derived by replaying from the start."""
    def __init__(self):
        self.streams = defaultdict(list)

    def append(self, stream_id, event):
        event.version = len(self.streams[stream_id]) + 1
        self.streams[stream_id].append(event)
        return event

    def read_stream(self, stream_id):
        return list(self.streams[stream_id])

class BankAccount:
    def __init__(self, account_id, store):
        self.account_id, self.store = account_id, store
        self.balance = 0

    def _apply(self, event):
        if event.event_type == "AccountOpened":
            self.balance = event.data["initial_balance"]
        elif event.event_type == "MoneyDeposited":
            self.balance += event.data["amount"]
        elif event.event_type == "MoneyWithdrawn":
            self.balance -= event.data["amount"]

    def load(self):
        self.balance = 0
        for e in self.store.read_stream(f"account-{self.account_id}"):
            self._apply(e)
        return self

    def open(self, initial_balance):
        e = Event("AccountOpened", self.account_id, {"initial_balance": initial_balance})
        self.store.append(f"account-{self.account_id}", e)
        self._apply(e)

    def deposit(self, amount):
        e = Event("MoneyDeposited", self.account_id, {"amount": amount})
        self.store.append(f"account-{self.account_id}", e)
        self._apply(e)

store = EventStore()
account = BankAccount("ACC-001", store)
account.open(1000)
account.deposit(500)
print(f"Balance: ${account.balance}")   # Balance: $1500

rebuilt = BankAccount("ACC-001", store).load()
print(f"Rebuilt from events: ${rebuilt.balance}, matches: {rebuilt.balance == account.balance}")
# Rebuilt from events: $1500, matches: True
```

```text
# Real-world: EventStoreDB, Kafka with log compaction DISABLED (compaction
# would collapse history to "latest value per key" -- the opposite of what
# event sourcing needs), DynamoDB Streams, or a Postgres table + outbox pattern.
```

**Why bother:** a complete audit trail (every change is a permanent, immutable record), temporal queries ("what was the balance at 3pm yesterday" — replay up to that point), and replay-driven debugging (reproduce any historical bug by replaying the exact event sequence that caused it). The cost: rebuilding state by replaying the *entire* history doesn't scale forever — production event-sourced systems periodically write a **snapshot** (a cached "state as of version N") so a rebuild only needs to replay events *after* the last snapshot, not from the beginning of time.

---

## 2. CQRS: Command Query Responsibility Segregation

CQRS separates the **write model** (append events) from the **read model** (query-optimized projections built by consuming those events). The two don't have to share a schema, a database, or even a data store — each read model is shaped for exactly the query it needs to answer.

```python
def build_read_models(all_events):
    account_summaries = {}
    daily_totals = defaultdict(lambda: {"deposits": 0, "withdrawals": 0})

    for e in all_events:
        aid = e.aggregate_id
        if e.event_type == "AccountOpened":
            account_summaries[aid] = {"balance": e.data["initial_balance"]}
        elif e.event_type == "MoneyDeposited":
            account_summaries[aid]["balance"] += e.data["amount"]
            daily_totals[e.timestamp[:10]]["deposits"] += e.data["amount"]
        elif e.event_type == "MoneyWithdrawn":
            account_summaries[aid]["balance"] -= e.data["amount"]
            daily_totals[e.timestamp[:10]]["withdrawals"] += e.data["amount"]

    return account_summaries, daily_totals

all_events = [e for stream in store.streams.values() for e in stream]
summaries, totals = build_read_models(all_events)
print(summaries)  # {'ACC-001': {'balance': 1500}}
```

The payoff: **read models can always be thrown away and rebuilt** from the event log — a new reporting requirement doesn't mean a risky migration of live data, it means writing a new projection and replaying history into it. This is precisely why event sourcing and CQRS are so often paired: event sourcing supplies the durable, replayable source of truth; CQRS is what you build *from* it on the read side.

---

## 3. Pub/Sub: Decoupled Communication

In a pub/sub system, publishers emit events with no knowledge of who — if anyone — is listening; subscribers register interest in an event type and react independently.

```python
class EventBus:
    def __init__(self):
        self.subscribers = defaultdict(list)

    def subscribe(self, event_type, callback):
        self.subscribers[event_type].append(callback)

    def publish(self, event_type, data):
        for callback in self.subscribers[event_type]:
            callback(event_type, data)

bus = EventBus()
bus.subscribe("OrderPlaced", lambda t, d: print(f"[Inventory] reserving {d['item']}"))
bus.subscribe("OrderPlaced", lambda t, d: print(f"[Email] confirming to {d['customer']}"))
bus.subscribe("OrderPlaced", lambda t, d: print(f"[Fraud] checking order {d['order_id']}"))

bus.publish("OrderPlaced", {"order_id": "ORD-1", "customer": "alice@x.com", "item": "Laptop"})
# [Inventory] reserving Laptop
# [Email] confirming to alice@x.com
# [Fraud] checking order ORD-1
```

```text
# Real-world: Kafka topics, AWS SNS/SQS, Google Pub/Sub, RabbitMQ.
```

The order service that publishes `OrderPlaced` never calls Inventory, Email, or Fraud directly — adding a fourth subscriber (say, a new Analytics service) requires zero changes to the order service itself. This is the concrete payoff of "decoupled": services can be added, removed, or rewritten independently, as long as they agree on the event's shape — which is exactly why schema evolution (next section) matters so much in practice.

---

## 4. Event Schema Evolution

Systems evolve; event schemas change under them. A `UserCreated` event might start with `{name, email}`, later grow a `phone` field, then split `name` into `first_name`/`last_name`. Every consumer — including ones that haven't been redeployed yet — has to keep working through that.

```python
import copy, json

def upcast(event):
    """Transform an older-schema event into the latest schema version."""
    data = copy.deepcopy(event["data"])
    version = event.get("version", 1)
    if version < 2:
        data.setdefault("phone", None)               # v1 -> v2: add default
    if version < 3:
        name = data.pop("name", "Unknown Unknown")     # v2 -> v3: split name
        first, _, last = name.partition(" ")
        data["first_name"], data["last_name"] = first, last
    return {"type": event["type"], "version": 3, "data": data}

v1 = {"type": "UserCreated", "version": 1, "data": {"name": "Alice", "email": "a@x.com"}}
print(json.dumps(upcast(v1)["data"]))
# {"email": "a@x.com", "phone": null, "first_name": "Alice", "last_name": ""}
```

```text
Compatibility rules (Avro/Protobuf style):
  BACKWARD compatible: new code can read data written by OLD code   (add optional fields)
  FORWARD compatible:  old code can read data written by NEW code   (ignore unknown fields)
  FULL compatible:     both directions hold

Best practices: never remove a required field; give new fields defaults;
use a schema registry (Confluent Schema Registry) so producers can't
publish an incompatible schema in the first place.
```

Applied to a **live** stream rather than a batch extract, schema evolution has no natural boundary to fix a break at — there's no "next run" to redeploy a corrected transform before more data arrives, the way there is in `etl_elt_patterns/interview_questions/03_critique_and_debug.md`'s batch version of this same bug. A consumer that assumes the old shape and crashes (or silently mis-parses) the instant the new shape starts flowing is a live incident, not a scheduled fix — which is the concrete reason production streaming systems insist on a schema registry enforcing compatibility *before* a bad schema ever reaches the topic.

---

## 5. The Saga Pattern: Distributed Transactions Without 2PC

A single business operation (placing an order) often spans multiple services (inventory, payment, shipping), each with its own local transaction. A **saga** runs these as a sequence of local transactions, each publishing an event; if any step fails, previously completed steps are undone via **compensating actions**, run in reverse order.

```python
class SagaOrchestrator:
    def __init__(self):
        self.completed = []  # [(step_name, compensation_fn), ...]

    def execute_step(self, name, action, compensation):
        try:
            result = action()
            self.completed.append((name, compensation))
            print(f"  {name}: SUCCESS ({result})")
            return True
        except Exception as e:
            print(f"  {name}: FAILED ({e})")
            self._compensate()
            return False

    def _compensate(self):
        for name, compensation in reversed(self.completed):
            print(f"  Undo {name}: {compensation()}")
        self.completed.clear()

saga = SagaOrchestrator()
saga.execute_step("Reserve Inventory", lambda: "5 items reserved", lambda: "5 items released")
saga.execute_step(
    "Process Payment",
    action=lambda: (_ for _ in ()).throw(Exception("Card declined")),
    compensation=lambda: "$499.95 refunded",
)
# Reserve Inventory: SUCCESS (5 items reserved)
# Process Payment: FAILED (Card declined)
#   Undo Reserve Inventory: 5 items released
```

| Aspect | Saga | Two-Phase Commit (2PC) |
|---|---|---|
| Coupling | Loosely coupled | Tightly coupled |
| Availability | High | Lower (blocks during the protocol) |
| Consistency | Eventual | Strong |
| Complexity | Compensation logic per step | Coordinator logic |
| Scalability | Better across services | Limited |

Sagas are the standard answer to "how do you keep data consistent across microservices without a distributed transaction" — 2PC is covered in full in `concepts/05_exactly_once_semantics.md`, where it shows up as the mechanism *inside* Kafka's own transactional producer, a genuinely different use case (one system's internal consistency) from cross-service business transactions (what sagas are for).

---

## Key Takeaways

- Event sourcing stores the sequence of things that happened, not derived current state — state is rebuilt by replaying events, giving a full audit trail and temporal queries at the cost of needing periodic snapshots at scale.
- CQRS separates the write model (append events) from read models (query-optimized projections) — read models are disposable and rebuildable from the event log, which is the entire point.
- Pub/sub decouples publishers from subscribers completely; adding a new consumer requires zero producer changes, but that decoupling only holds up as long as the event schema itself stays compatible across versions.
- Schema evolution needs explicit backward/forward compatibility rules and a schema registry — on a live stream, there's no natural "next run" boundary to fix a break, unlike a batch pipeline.
- The saga pattern replaces a distributed transaction with a sequence of local transactions plus compensating actions on failure — high availability, eventual consistency, in contrast to 2PC's strong consistency at the cost of blocking.
