# Concept 01: Streaming Fundamentals

**Covers:**
- Batch vs. stream processing — the core paradigm shift and why it matters for interviews
- Micro-batch vs. true streaming, and where each real system sits
- Event time vs. processing time — the distinction nearly every streaming bug traces back to
- Where windowing and watermarks fit (full treatment lives in `concepts/03_windowing_and_watermarks.md`)

*All Python below is real, runnable stdlib — copy any block into a `python3` shell and it runs as shown. No Kafka, no Flink, no external services required; the comments show the real-world equivalent API for each pattern.*

---

## 1. Batch vs. Stream Processing

Batch processing operates on a **finite, bounded** dataset, on a schedule: collect a day's worth of data, then run a job over all of it. Stream processing operates on an **infinite, unbounded** dataset, continuously: data keeps arriving forever, and the system reacts to each piece (or each small group of pieces) as it shows up.

```python
table = [
    ("Dimension",       "Batch Processing",           "Stream Processing"),
    ("Data scope",      "Finite / bounded dataset",   "Infinite / unbounded"),
    ("Latency",         "Minutes to hours",            "Milliseconds to seconds"),
    ("Trigger",         "Scheduled (cron, daily)",     "Continuous / per-event"),
    ("State",           "Recomputed each run",         "Maintained incrementally"),
    ("Fault tolerance", "Re-run entire batch",          "Checkpoints + replay"),
    ("Tools",           "Spark, Hive, dbt",             "Kafka Streams, Flink"),
    ("Use case",        "Daily reports, ML training",  "Fraud detection, alerts"),
    ("Complexity",      "Simpler to reason about",     "Harder (ordering, late data)"),
]
for dim, batch, stream in table:
    print(f"{dim:<18} {batch:<30} {stream}")
```

The interview-relevant framing isn't "streaming is strictly better" — it's that streaming trades simplicity for latency. A batch job that reruns from scratch every night can afford to be sloppy about intermediate state, because "just rerun it" is always available as a fallback. A streaming job runs forever and must maintain state incrementally, correctly, under failures, without ever getting a clean restart — that's what makes streaming systems harder to reason about, not the data volume itself.

---

## 2. Micro-Batch vs. True Streaming

Both process unbounded data, but differ in unit of work:

- **Micro-batch** (Spark Structured Streaming's default mode): collect events for a short, fixed interval (100ms, 1s, 5s), then process that interval's events together as a small batch. Trades a little latency for the operational simplicity of reusing batch-style processing code.
- **True streaming** (Apache Flink, Kafka Streams): process each event individually, the instant it arrives. Lower latency, but every operator has to be written to handle one record at a time, and to manage its own state across records.

```python
from collections import defaultdict

events = [
    {"ts": 0.0, "user": "alice", "action": "click"},
    {"ts": 0.1, "user": "bob",   "action": "click"},
    {"ts": 0.3, "user": "alice", "action": "purchase"},
    {"ts": 0.5, "user": "carol", "action": "click"},
    {"ts": 0.7, "user": "bob",   "action": "purchase"},
    {"ts": 1.1, "user": "alice", "action": "click"},
]

# --- Micro-batch: collect into 0.5s intervals, then process each batch ---
interval = 0.5
batches = defaultdict(list)
for e in events:
    batches[int(e["ts"] // interval)].append(e)

for batch_id in sorted(batches):
    ws = batch_id * interval
    print(f"Batch [{ws:.1f}s-{ws+interval:.1f}s): {len(batches[batch_id])} events")
# Batch [0.0s-0.5s): 3 events
# Batch [0.5s-1.0s): 2 events
# Batch [1.0s-1.5s): 1 events

# --- True streaming: process each event the moment it "arrives" ---
for e in events:
    print(f"t={e['ts']:.1f}s -> process({e['user']}, {e['action']})")
# t=0.0s -> process(alice, click)
# t=0.1s -> process(bob, click)
# ...
```

```text
# Real Kafka Streams equivalent — true streaming, per-record:
#   KStream<String, Event> stream = builder.stream("clicks");
#   stream.foreach((key, event) -> process(event));

# Real Spark Structured Streaming equivalent — micro-batch:
#   df = spark.readStream.format("kafka").option("subscribe", "clicks").load()
#   df.writeStream.trigger(processingTime="1 second").start()
```

A common interview trap: someone describes a "2-second trigger interval" and calls it "real-time streaming." It's streaming in the sense that data is unbounded, but it's micro-batch, not true per-event streaming — worth naming the distinction unprompted, since "how would you classify this pipeline" is a direct rapid-fire question (`interview_questions/02_rapid_fire_qna.md`).

---

## 3. Event Time vs. Processing Time

**Event time**: when the event actually happened in the real world (embedded in the data itself, e.g. a `timestamp` field the producer set).
**Processing time**: when the streaming system actually gets around to handling the event (the system's wall clock at the moment of processing).

These diverge constantly — network delays, retries, a mobile device buffering events offline and replaying them hours later, a slow consumer falling behind its producer. Correct streaming systems window and aggregate on **event time**, not processing time, because a report keyed on "when we happened to process it" is not reproducible and not meaningful to the business.

```python
events = [
    {"event_time": "12:00:01", "value": 10, "note": "arrives on time"},
    {"event_time": "12:00:03", "value": 20, "note": "arrives on time"},
    {"event_time": "12:00:02", "value": 15, "note": "delayed -- arrives AFTER 12:00:03"},
    {"event_time": "12:00:05", "value": 25, "note": "arrives on time"},
    {"event_time": "12:00:04", "value": 30, "note": "delayed by 2 seconds"},
]

print("Processing order (arrival order):")
for i, e in enumerate(events, 1):
    print(f"  {i}. event_time={e['event_time']} value={e['value']}  ({e['note']})")

print("\nSorted by EVENT time (correct order for analytics):")
for e in sorted(events, key=lambda x: x["event_time"]):
    print(f"  {e['event_time']}  value={e['value']}")
# 12:00:01  value=10
# 12:00:02  value=15
# 12:00:03  value=20
# 12:00:04  value=30
# 12:00:05  value=25
```

Notice the event with `value=15` (event_time `12:00:02`) physically *arrives* after the `value=20` event (event_time `12:00:03`) — this is exactly what "out-of-order arrival" means, and it's the reason a system can't just process-and-aggregate in arrival order and call it correct. If a 5-second tumbling window closed the instant processing time crossed the 5-second mark, the `value=15` event would already have missed its window by the time it showed up. That's precisely the problem watermarks exist to manage — worked in full, with a timeline diagram, in `concepts/03_windowing_and_watermarks.md`.

---

## Key Takeaways

- Batch processes finite data on a schedule; streaming processes unbounded data continuously. The real cost of streaming isn't volume, it's that state must be maintained incrementally, correctly, forever, with no clean "just rerun it" fallback.
- Micro-batch (Spark) trades a little latency for batch-style processing simplicity; true streaming (Flink, Kafka Streams) processes event-by-event for the lowest latency at the cost of more complex per-record state management. A fixed "trigger every N seconds" system is micro-batch, not true streaming — say so explicitly if asked to classify one.
- Always window and aggregate on **event time**, never processing time — events arrive out of order and late as a simple fact of distributed systems, and processing-time-based logic is neither reproducible nor meaningful.
- Windowing strategies (tumbling/sliding/session) and watermark-based late-data handling are covered in full, with worked timelines, in `concepts/03_windowing_and_watermarks.md` — this file only establishes why event time matters; that file is where the mechanics live.
