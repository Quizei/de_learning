# Streaming & Real-Time — Practice Exercises

Ten exercises covering: classifying a processing model, tumbling/sliding/session windows, watermark-based late-data filtering, Kafka partition assignment, idempotent message processing, event-sourced state rebuild, consumer-group rebalancing, and a small end-to-end windowed pipeline with alerting.

How to use this file: read the exercise, write your own solution, and only then expand the reference solution to check yourself. Every solution is real, runnable stdlib Python.

---

## Exercise 1: Classify a Processing Model — Easy

Given a plain-English description of a pipeline, classify it as `"batch"`, `"micro-batch"`, or `"true-streaming"`.

**Test cases:**
```python
("Process all sales data every night at 2am",                "batch")
("Trigger every 500ms to process accumulated clicks",         "micro-batch")
("Each credit card swipe is scored for fraud in 50ms",        "true-streaming")
("Spark Structured Streaming with 2-second trigger interval",  "micro-batch")
("Flink processes each sensor reading as it arrives",          "true-streaming")
```

<details>
<summary>Reference solution</summary>

```python
def classify(description):
    desc = description.lower()
    stream_keywords = ["each", "per-event", "as it arrives", "50ms", "real-time", "sub-second"]
    micro_keywords = ["trigger", "interval", "accumulated", "micro", "500ms", "second trigger"]
    for kw in stream_keywords:
        if kw in desc:
            return "true-streaming"
    for kw in micro_keywords:
        if kw in desc:
            return "micro-batch"
    return "batch"
```

Check *streaming* keywords before *micro-batch* ones — "Flink processes each sensor reading as it arrives" would otherwise never match "each" if a broader batch-y keyword list were checked first. See `concepts/01_streaming_fundamentals.md`, section 2, for why "2-second trigger interval" is micro-batch, not true streaming, even though it's still processing an unbounded stream.

</details>

---

## Exercise 2: Tumbling Window Aggregation — Easy

Given `events = [(timestamp, value), ...]` and a `window_size`, return `{window_start: sum_of_values}`.

```python
events = [(0, 10), (1, 20), (2, 30), (5, 40), (7, 50), (10, 60), (12, 70), (14, 80)]
# window_size=5 -> {0: 60, 5: 90, 10: 210}
```

<details>
<summary>Reference solution</summary>

```python
from collections import defaultdict

def tumbling_aggregate(events, window_size):
    windows = defaultdict(int)
    for ts, value in events:
        windows[(ts // window_size) * window_size] += value
    return dict(windows)
```

Straight from `concepts/03_windowing_and_watermarks.md`, section 2 — the entire window key is `(ts // window_size) * window_size`.

</details>

---

## Exercise 3: Sliding Window Aggregation — Medium

Given `events`, `window_size`, and `slide`, return `{window_start: sum}` for every window starting at `0, slide, 2*slide, ...` up to the max timestamp. An event belongs to window `[ws, ws+window_size)` if `ws <= ts < ws+window_size`.

```python
events = [(1, 10), (3, 20), (5, 30), (7, 40), (9, 50)]
# window_size=5, slide=3 -> {0: 30, 3: 90, 6: 90, 9: 50}
```

<details>
<summary>Reference solution</summary>

```python
def sliding_aggregate(events, window_size, slide):
    max_ts = max(ts for ts, _ in events)
    windows = defaultdict(int)
    for window_start in range(0, max_ts + 1, slide):
        window_end = window_start + window_size
        for ts, value in events:
            if window_start <= ts < window_end:
                windows[window_start] += value
    return dict(windows)
```

Note this is `O(num_windows * num_events)` — fine for an exercise, but a real sliding-window operator maintains an incremental running sum per key rather than re-scanning every event for every window, since re-scanning doesn't scale to high-volume streams. Worth naming that trade-off out loud if asked to optimize it.

</details>

---

## Exercise 4: Session Window Detection — Medium

Given sorted `timestamps` and a `gap_threshold`, group into sessions — a new session starts whenever the gap since the previous event exceeds the threshold.

```python
timestamps = [1, 2, 3, 10, 11, 12, 25, 26, 27, 28]
# gap_threshold=5 -> [[1, 2, 3], [10, 11, 12], [25, 26, 27, 28]]
```

<details>
<summary>Reference solution</summary>

```python
def detect_sessions(timestamps, gap_threshold):
    if not timestamps:
        return []
    sessions = [[timestamps[0]]]
    for i in range(1, len(timestamps)):
        if timestamps[i] - timestamps[i - 1] > gap_threshold:
            sessions.append([timestamps[i]])
        else:
            sessions[-1].append(timestamps[i])
    return sessions
```

See `concepts/03_windowing_and_watermarks.md`, section 4 — a session window's boundary genuinely isn't knowable until the gap has actually elapsed, which is why session windows depend the most on watermark configuration of the three window types.

</details>

---

## Exercise 5: Watermark & Late-Data Filter — Medium

Given a stream of `{"event_time": int, "value": any}` in arrival order and `allowed_lateness`, maintain `watermark = max_event_time_seen - allowed_lateness` and split events into `(on_time, late)`. An event is on time if `event_time >= watermark` at the moment it arrives.

```python
events = [
    {"event_time": 10, "value": "a"}, {"event_time": 15, "value": "b"},
    {"event_time": 8,  "value": "c"},  # watermark=15-3=12, 8<12 -> late
    {"event_time": 20, "value": "d"},
    {"event_time": 14, "value": "e"},  # watermark=20-3=17, 14<17 -> late
    {"event_time": 19, "value": "f"},  # watermark=20-3=17, 19>=17 -> on time
]
# on_time values: ["a", "b", "d", "f"]   late values: ["c", "e"]
```

<details>
<summary>Reference solution</summary>

```python
def apply_watermark(events, allowed_lateness):
    max_event_time = 0
    on_time, late = [], []
    for event in events:
        max_event_time = max(max_event_time, event["event_time"])
        watermark = max_event_time - allowed_lateness
        (on_time if event["event_time"] >= watermark else late).append(event)
    return on_time, late
```

This is the exact mechanic behind the worked timeline in `concepts/03_windowing_and_watermarks.md`, section 5 — the watermark is recomputed on *every* arrival from the running max, not just once per window.

</details>

---

## Exercise 6: Kafka Partition Assignment — Medium

Given `messages = [{"key": str|None, "value": str}, ...]` and `num_partitions`, assign each message a partition: `hash(key) % num_partitions` for keyed messages, round-robin (via a counter) for `key=None`.

```python
messages = [
    {"key": "user-A", "value": "click"}, {"key": "user-B", "value": "click"},
    {"key": "user-A", "value": "purchase"},  # same key -> same partition as above
    {"key": None, "value": "log-1"}, {"key": None, "value": "log-2"},  # round-robin
]
```

<details>
<summary>Reference solution</summary>

```python
import hashlib

def assign_partitions(messages, num_partitions):
    rr_counter = 0
    results = []
    for msg in messages:
        if msg["key"] is None:
            partition = rr_counter % num_partitions
            rr_counter += 1
        else:
            h = int(hashlib.md5(msg["key"].encode()).hexdigest(), 16)
            partition = h % num_partitions
        results.append(partition)
    return results
```

Verify it yourself: the two `user-A` entries must land on the same partition number, and the two `key=None` entries should differ (unless `num_partitions` is small enough to collide) — both are asserted in `concepts/02_kafka_concepts.md`'s worked demo.

</details>

---

## Exercise 7: Idempotent Message Processor — Medium

Given `messages = [{"idempotency_key": str, "value": any}, ...]`, process each unique key once and skip duplicates. Return the list of processed values, in order, with no duplicates.

```python
messages = [
    {"idempotency_key": "k1", "value": "order-100"}, {"idempotency_key": "k2", "value": "order-200"},
    {"idempotency_key": "k1", "value": "order-100"},  # duplicate
    {"idempotency_key": "k3", "value": "order-300"},
]
# -> ["order-100", "order-200", "order-300"]
```

<details>
<summary>Reference solution</summary>

```python
def process_idempotent(messages):
    seen = set()
    processed = []
    for msg in messages:
        key = msg["idempotency_key"]
        if key not in seen:
            seen.add(key)
            processed.append(msg["value"])
    return processed
```

The exact "idempotency key" deduplication strategy from `concepts/05_exactly_once_semantics.md`, section 4 — this is the fallback to reach for whenever the delivery layer only promises at-least-once and infrastructure-level exactly-once isn't in play.

</details>

---

## Exercise 8: Event Sourcing — Rebuild Shopping Cart State — Hard

Given a list of cart events (`ItemAdded`, `ItemRemoved`, `QuantityChanged`), rebuild the current cart as `{item: {"qty", "price", "total"}}` plus a grand total.

```python
events = [
    {"type": "ItemAdded", "data": {"item": "Laptop", "qty": 1, "price": 999.99}},
    {"type": "ItemAdded", "data": {"item": "Mouse", "qty": 2, "price": 29.99}},
    {"type": "ItemAdded", "data": {"item": "Keyboard", "qty": 1, "price": 79.99}},
    {"type": "QuantityChanged", "data": {"item": "Mouse", "new_qty": 3}},
    {"type": "ItemRemoved", "data": {"item": "Keyboard"}},
]
# cart = {"Laptop": {"qty": 1, "price": 999.99, "total": 999.99},
#         "Mouse":  {"qty": 3, "price": 29.99,  "total": 89.97}}
# grand_total = 1089.96
```

<details>
<summary>Reference solution</summary>

```python
def rebuild_cart(events):
    cart = {}
    for event in events:
        etype, data = event["type"], event["data"]
        if etype == "ItemAdded":
            cart[data["item"]] = {
                "qty": data["qty"], "price": data["price"],
                "total": round(data["qty"] * data["price"], 2),
            }
        elif etype == "ItemRemoved":
            cart.pop(data["item"], None)
        elif etype == "QuantityChanged":
            item = data["item"]
            if item in cart:
                cart[item]["qty"] = data["new_qty"]
                cart[item]["total"] = round(data["new_qty"] * cart[item]["price"], 2)
    grand_total = round(sum(v["total"] for v in cart.values()), 2)
    return cart, grand_total
```

This is `concepts/04_event_driven_architecture.md`'s event-sourcing pattern applied to a cart instead of a bank account: current state is always a fold over the event list, never stored directly. Notice `ItemRemoved` for `"Keyboard"` after it was added — the rebuild has to tolerate removing an item that exists, and (in a hardened version) *not* crash if a removal or quantity-change event arrives for an item that was never added, which would indicate the event stream itself is corrupt or out of order.

</details>

---

## Exercise 9: Consumer Group Rebalancing — Hard

Given `num_partitions` and `num_consumers`, assign partitions round-robin (`partition i -> consumer i % num_consumers`). Handle more consumers than partitions (some get empty lists) and a single consumer (gets everything).

```python
rebalance(6, 3)  # -> {0: [0, 3], 1: [1, 4], 2: [2, 5]}
rebalance(2, 4)  # -> {0: [0], 1: [1], 2: [], 3: []}
rebalance(4, 1)  # -> {0: [0, 1, 2, 3]}
```

<details>
<summary>Reference solution</summary>

```python
def rebalance(num_partitions, num_consumers):
    assignment = {c: [] for c in range(num_consumers)}
    for pid in range(num_partitions):
        assignment[pid % num_consumers].append(pid)
    return assignment
```

The `(2, 4)` case is worth sitting with: two consumers end up doing all the work and two sit permanently idle. That's the concrete mechanism behind "adding more consumers than partitions doesn't add throughput" from `concepts/02_kafka_concepts.md`, section 3 — it isn't a vague warning, it's this exact assignment function producing empty lists.

</details>

---

## Exercise 10: End-to-End Windowed Pipeline With Alerting — Hard

Build a mini pipeline over `readings = [(sensor_id, timestamp, temp_fahrenheit), ...]`:
1. Filter invalid readings (`temp < -50` or `temp > 150`).
2. Convert Fahrenheit to Celsius: `(temp_f - 32) * 5/9`.
3. Compute tumbling-window averages.
4. Alert if any window's average exceeds a threshold.

```python
readings = [
    ("S1", 0, 77), ("S2", 1, 86), ("S1", 2, -999),  # invalid
    ("S2", 3, 95), ("S1", 5, 104), ("S2", 6, 113),
    ("S1", 7, 200),  # invalid
    ("S2", 8, 122),
]
# window_size=5, alert_threshold_c=40
# window_averages: {0: 30.0, 5: 45.0}   alerts: [{"window_start": 5, "avg_temp": 45.0}]
```

<details>
<summary>Reference solution</summary>

```python
def run_pipeline(readings, window_size, alert_threshold_c):
    valid = [(sid, ts, t) for sid, ts, t in readings if -50 <= t <= 150]

    windows = defaultdict(list)
    for sid, ts, temp_f in valid:
        temp_c = (temp_f - 32) * 5 / 9
        windows[(ts // window_size) * window_size].append(temp_c)

    avgs, alerts = {}, []
    for ws in sorted(windows):
        avg = round(sum(windows[ws]) / len(windows[ws]), 2)
        avgs[ws] = avg
        if avg > alert_threshold_c:
            alerts.append({"window_start": ws, "avg_temp": avg})
    return avgs, alerts
```

This chains three ideas from this topic in one pass: filter-bad-data (a validation step no different in spirit from `etl_elt_patterns`'s transform validation), event-time tumbling windows (`concepts/03_windowing_and_watermarks.md`), and a threshold-based alert derived from a window result — the same shape as a real fraud-detection or infra-monitoring rule, just with temperature standing in for whatever metric actually matters.

**Extend it yourself:** add `allowed_lateness` and a watermark check (`concepts/03_windowing_and_watermarks.md`, section 5) so a reading that arrives after its window has already emitted gets routed to a `late_readings` side output instead of silently being dropped or silently mutating an already-emitted result.

</details>

---

## What to Do Next

Once these ten pass comfortably, move to `practice/coding_problems.md` for two harder, closer-to-interview-length problems (sorted-stream deduplication and a windowed stream-processing engine with late-data handling), then `interview_questions/` for the conversation these exercises are ultimately rehearsing for.
