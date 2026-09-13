# Concept 17: Structured Streaming Basics

**Covers:**
- The "unbounded table" model
- Sources and sinks (readStream/writeStream, Kafka, files, console)
- Output modes: Append, Complete, Update
- Triggers: default micro-batch, ProcessingTime, Once/AvailableNow, Continuous
- Watermarking and why it's needed for stateful aggregations
- Checkpointing (offsets + state for fault-tolerant restart)
- Worked example: windowed word count with watermark
- Simulation: micro-batches with late data and watermark decisions

> *Note: this topic isn't in the source YouTube playlist — added because it's essential and commonly asked about.*

*The PySpark snippets below reflect what you'd run against a real Spark session; the worked examples and their output are simulated here in pure Python so you can follow the mechanics without a cluster.*

---

## 1. The unbounded table model

Structured Streaming's core idea: treat a stream as a TABLE that keeps growing, one row (or batch of rows) at a time, forever. You write the exact same DataFrame/SQL transformations you'd write for a static/batch DataFrame — filters, joins, aggregations, window functions — and Spark re-runs (incrementally) the same logical query against the ever-growing table on each new micro-batch.

This is the key win over "manual streaming": you don't write separate batch and streaming logic. The query is defined once; the engine figures out how to apply it incrementally as new data arrives.

```text
Time ->

t=0   +--------+
      | row 1  |   Input table grows as new data arrives
      +--------+
t=1   +--------+
      | row 1  |
      | row 2  |
      | row 3  |
      +--------+
t=2   +--------+
      | row 1  |
      | row 2  |
      | row 3  |
      | row 4  |
      | row 5  |
      +--------+
```

Your query (filter/groupBy/window/join) is defined ONCE against this conceptually-unbounded table. Each micro-batch, Spark computes what the RESULT would be if the query ran against the table-so-far, and emits only what changed (per the output mode).

---

## 2. Sources and sinks

A streaming query needs a SOURCE (where new rows come from) and a SINK (where results go), connected via `readStream` / `writeStream`.

Common sources: Kafka, files (a directory that gets new files dropped into it), sockets (for local testing), rate (synthetic data generator for testing).

Common sinks: Kafka, files (parquet/delta/etc.), console (prints to stdout — for debugging only), memory (in-memory table — debugging), `foreachBatch` (run arbitrary batch code per micro-batch, e.g. write to multiple destinations or upsert into a table).

```python
# ---- Reading from Kafka ----
raw = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "broker1:9092,broker2:9092")
    .option("subscribe", "clickstream")
    .option("startingOffsets", "latest")
    .load()
)
# raw has columns: key, value (both bytes), topic, partition, offset, timestamp, ...
# you typically cast/parse `value` (e.g. from_json) into a real schema

# ---- Writing to a file sink (e.g. Parquet) ----
query = (
    parsed_df.writeStream
    .format("parquet")
    .option("path", "/data/output/")
    .option("checkpointLocation", "/data/checkpoints/clickstream")
    .start()
)

# ---- Console sink -- for local debugging only ----
debug_query = (
    parsed_df.writeStream
    .format("console")
    .outputMode("append")
    .start()
)

query.awaitTermination()
```

---

## 3. Output modes: Append, Complete, Update

Output mode controls WHAT gets written to the sink on each trigger:

**Append (default):**
- Only NEW rows added to the result table since the last trigger are output.
- Works for queries where existing output rows never change (e.g. simple filters/maps, or aggregations with a watermark where old windows are considered final and won't be updated again).
- Cannot be used with aggregations that might still update already-emitted rows, unless a watermark bounds that.

**Complete:**
- The ENTIRE result table is re-output on every trigger, not just changes. Needed for aggregations without a watermark, where any new row could still change any existing group's value (e.g. a running COUNT per key with no time bound).
- Only feasible when the full result table is small enough to hold and rewrite each trigger (e.g. count per category, not count per user in a system with billions of users).

**Update:**
- Only rows that CHANGED (or are new) since the last trigger are output — a middle ground. Good for aggregations where you want to see updates to existing groups without re-emitting the whole table each time.

```text
+----------+---------------------------------------------------+
| Mode     | What's written each trigger                        |
+----------+---------------------------------------------------+
| Append   | Only brand-new finalized rows                       |
| Complete | The WHOLE result table, every trigger               |
| Update   | Only rows that changed or are new                   |
+----------+---------------------------------------------------+
```

```python
query = df.writeStream.outputMode("append").format("console").start()
query = agg_df.writeStream.outputMode("complete").format("console").start()
query = agg_df.writeStream.outputMode("update").format("console").start()
```

---

## 4. Triggers

A trigger controls WHEN Spark checks for new data and runs a micro-batch:

- **Default (no trigger specified):** run the next micro-batch as soon as the previous one finishes. Effectively "as fast as possible."
- **`Trigger.ProcessingTime("10 seconds")`:** run a micro-batch every fixed interval, even if there's not much new data (or skip/combine if the previous batch is still running past the interval).
- **`Trigger.Once()` (older) / `Trigger.AvailableNow()` (newer, preferred):** process all currently-available data in one (`Once`) or several (`AvailableNow`, which can split into multiple micro-batches) runs, then STOP. This turns a "streaming" query into a scheduled, batch-like job — e.g. run every hour via a scheduler, process whatever arrived, then shut down. Cheaper than keeping a cluster running continuously for low-frequency data.
- **`Trigger.Continuous("1 second")` (experimental):** a fundamentally different low-latency execution mode (not micro-batch) aiming for ~1ms latencies, with a reduced set of supported operations. Still marked experimental in mainline Spark; rarely used in production compared to micro-batch.

```python
from pyspark.sql.streaming import Trigger

# Default: as fast as possible
df.writeStream.format("console").start()

# Fixed interval micro-batches
df.writeStream.trigger(processingTime="10 seconds").format("console").start()

# Process everything available right now, then stop (batch-like)
df.writeStream.trigger(availableNow=True).format("parquet").option("path", "out/").start()

# Experimental low-latency continuous mode
df.writeStream.trigger(continuous="1 second").format("kafka").start()
```

`Trigger.Once`/`AvailableNow` are popular for cost control: you get streaming-style incremental/checkpointed processing semantics, but only pay for compute when the scheduled job actually runs, instead of an always-on cluster.

---

## 5. Watermarking

Problem: for a windowed aggregation (e.g. "count events per 5-minute window"), Spark must keep STATE for every open window (partial counts) in memory, because a late-arriving event could still belong to an "old" window. Without a bound, this state grows forever as the stream runs — eventually exhausting memory.

Watermark: a declared bound on how late data is allowed to be. `withWatermark("event_time", "10 minutes")` tells Spark: "once we've seen an event with timestamp T, we will not wait for, or update results for, any window that ends more than 10 minutes before T." Concretely, the watermark value = (max event_time seen so far) - (the declared threshold). Windows entirely older than the current watermark are considered FINAL, their state is dropped, and any row that arrives late enough to belong to an already-dropped window is discarded.

This lets Spark bound state size (old windows get cleaned up) at the cost of: data arriving later than the watermark threshold for its window is simply dropped from that aggregation.

```python
windowed_counts = (
    events_df
    .withWatermark("event_time", "10 minutes")
    .groupBy(F.window("event_time", "5 minutes"))
    .count()
)
# As soon as the engine has seen an event_time of, say, 12:20, the
# watermark becomes 12:10. Any window ending before 12:10 is final;
# its state is dropped. An event with event_time=12:02 arriving AFTER
# this point is late beyond the watermark and gets dropped.
```

Without a watermark: state for EVERY window ever opened is kept forever -> unbounded memory growth over a long-running stream.

With a watermark: state for windows older than (max seen time - threshold) is dropped -> bounded memory, at the cost of dropping data that arrives later than the threshold allows.

---

## 6. Checkpointing

`checkpointLocation` tells Spark where to persist, per micro-batch:

- The read OFFSETS consumed from each source (e.g. Kafka topic/partition/offset), so on restart Spark knows exactly where to resume reading — not re-reading already-processed data, and not skipping data.
- The STATE of any stateful operation (aggregation state, watermark position, dedup state, stream-stream join buffers), so restarting doesn't lose in-progress aggregation results.

Combined with an idempotent/transactional sink, this is what gives Structured Streaming its end-to-end fault-tolerance / exactly-once style guarantees: if the driver or an executor crashes, restarting the query with the SAME `checkpointLocation` picks up exactly where it left off, re-processing at most the in-flight micro-batch (which sinks are expected to handle idempotently, e.g. via unique batch IDs).

A checkpoint location is tied to ONE query's logical plan — you generally can't freely change the query's transformations (e.g. add a new aggregation) and reuse the same checkpoint; some changes are supported, many are not, depending on Spark version.

```python
query = (
    parsed_df.writeStream
    .format("delta")
    .option("checkpointLocation", "/data/checkpoints/my_query")
    .outputMode("append")
    .start()
)

# On restart after a crash: Spark reads the checkpoint, finds the
# last committed offsets + state, and resumes from there -- no
# manual bookkeeping required.
```

---

## 7. Worked example: windowed word count with watermark

Classic streaming example: count words per 10-minute tumbling window, over a stream of (event_time, line) records, with a 5-minute watermark to bound state and drop very-late data.

```python
lines = (
    spark.readStream.format("socket")
    .option("host", "localhost").option("port", 9999)
    .load()
    .withColumn("event_time", F.current_timestamp())  # or a real event-time column
)

words = lines.select(
    F.explode(F.split(lines.value, " ")).alias("word"),
    lines.event_time,
)

windowed_counts = (
    words
    .withWatermark("event_time", "5 minutes")
    .groupBy(F.window("event_time", "10 minutes"), "word")
    .count()
)

query = (
    windowed_counts.writeStream
    .outputMode("update")
    .format("console")
    .option("checkpointLocation", "/tmp/checkpoints/word_count")
    .start()
)
```

---

## 8. Simulation: late data and watermark decisions

Simulate several micro-batches of events (event_time, word) arriving, with some events arriving LATE (their event_time is older than data already processed). Apply a watermark of 5 minutes and show which late events get INCLUDED vs DROPPED, and how the watermark advances. Windows are 10-minute tumbling windows over the simplified integer "minutes since stream start" event time.

```python
watermark_threshold_min = 5

# Each micro-batch: list of (event_time_minute, word)
micro_batches = [
    {"batch": 1, "events": [(10, "hello"), (12, "world"), (11, "hello")]},
    {"batch": 2, "events": [(15, "spark"), (14, "hello"), (7, "world")]},   # 7 is late
    {"batch": 3, "events": [(20, "hello"), (9, "spark"), (19, "world")]},   # 9 is very late
]

max_event_time_seen = -1
watermark = -1
window_state = {}  # window_start -> {word: count}, window = 10-minute tumbling

def window_for(t):
    window_size = 10
    start = (t // window_size) * window_size
    return start, start + window_size

for batch in micro_batches:
    for event_time, word in batch["events"]:
        max_event_time_seen = max(max_event_time_seen, event_time)
        win_start, win_end = window_for(event_time)

        if win_end <= watermark:
            # This window was already finalized and dropped -- late event discarded
            print(f"event(t={event_time}, '{word}') -> window [{win_start},{win_end}) "
                  f"already CLOSED (watermark={watermark}) -> DROPPED")
            continue

        window_state.setdefault((win_start, win_end), {}).setdefault(word, 0)
        window_state[(win_start, win_end)][word] += 1
        print(f"event(t={event_time}, '{word}') -> window [{win_start},{win_end}) -> INCLUDED")

    watermark = max_event_time_seen - watermark_threshold_min
    print(f"watermark advances to: max_event_time({max_event_time_seen}) - "
          f"{watermark_threshold_min} = {watermark}")

    # Report windows whose end has fallen at/behind the watermark (final)
    finalized = [w for w in window_state if w[1] <= watermark]
    for w in finalized:
        print(f"window {w} is now FINAL: {window_state[w]}")
```

**Output:**
```text
Watermark threshold: 5 minutes

--- Micro-batch 1 ---
  event(t=10, 'hello') -> window [10,20) -> INCLUDED
  event(t=12, 'world') -> window [10,20) -> INCLUDED
  event(t=11, 'hello') -> window [10,20) -> INCLUDED
  watermark advances to: max_event_time(12) - 5 = 7

--- Micro-batch 2 ---
  event(t=15, 'spark') -> window [10,20) -> INCLUDED
  event(t=14, 'hello') -> window [10,20) -> INCLUDED
  event(t=7, 'world') -> window [0,10) -> INCLUDED
  watermark advances to: max_event_time(15) - 5 = 10
  window (0, 10) is now FINAL: {'world': 1}

--- Micro-batch 3 ---
  event(t=20, 'hello') -> window [20,30) -> INCLUDED
  event(t=9, 'spark') -> window [0,10) already CLOSED (watermark=10) -> DROPPED
  event(t=19, 'world') -> window [10,20) -> INCLUDED
  watermark advances to: max_event_time(20) - 5 = 15
  window (0, 10) is now FINAL: {'world': 1}
```

Notice: the event at t=7 in batch 2 squeaked in (window not closed yet), but the event at t=9 in batch 3 was dropped because by then the watermark had advanced past its window's end. This is exactly the tradeoff a watermark makes: bounded state, at the cost of dropping sufficiently-late data.

(A closer look at this simulation's bookkeeping is itself instructive: it recomputes "finalized" windows fresh from `window_state` every batch rather than removing them once reported, so window (0, 10) is reprinted as FINAL again in batch 3 — its end, 10, still falls at or behind the batch-3 watermark of 15. Note also that window (10, 20), which is still open at the end of batch 3, is correctly NOT reported as final. A production job doesn't re-emit an already-finalized window's result this way; this is a simplified simulation of the underlying watermark/finalization logic, not the exact output-mode semantics Spark applies.)

---

## Key Takeaways

- Structured Streaming treats a stream as an ever-growing table — you write the same DataFrame/SQL logic as batch, incrementally applied.
- `readStream`/`writeStream` connect sources (Kafka, files, sockets) to sinks (Kafka, files, console for debugging, `foreachBatch` for custom logic).
- Output modes: Append (new finalized rows only), Complete (whole result table each trigger), Update (only changed/new rows).
- Triggers control cadence: default (as fast as possible), ProcessingTime (fixed interval), Once/AvailableNow (batch-like, process then stop), Continuous (experimental, low-latency).
- Watermarking bounds how late data can arrive before a window's state is dropped — required to keep stateful aggregation state from growing forever.
- `checkpointLocation` persists offsets + state, enabling fault-tolerant restart without reprocessing or losing in-progress aggregations.
- Data arriving later than the watermark threshold for its window is silently dropped — there's a real tradeoff between state size and how much lateness you tolerate.
