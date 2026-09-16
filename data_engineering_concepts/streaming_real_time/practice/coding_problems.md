# Streaming & Real-Time — Coding Problems

Two harder, interview-length problems: an O(1)-memory deduplication algorithm for a sorted stream, and a small windowed stream-processing engine that has to handle late-arriving, out-of-order data correctly. Each includes the problem statement, sample input/output, and a hidden reference solution with an explanation of the pattern it's testing.

How to use this file: read the problem, write your own solution against the sample input, and only then expand the reference solution. Problem 1 is pulled from this course's bonus optimization problem set (`bonus_coding_problems/medium/02_optimization_problems.py`, problem 4); Problem 2 is an original problem written to the "stream processing engine — windowed aggregation, late data" brief from this course's hard system-design problem set.

---

## Problem 1: Deduplicate a Sorted Stream in O(1) Memory

**Problem statement:** you're given a stream of records that is already sorted by key (the common case for anything read off a sorted index, an ordered log, or output that's already been merge-sorted upstream). Duplicate keys are therefore always **adjacent**. Deduplicate the stream using O(1) memory — do not build a `set()` of every key seen, which is the obvious O(n)-memory approach and the one to explicitly reject in an interview before writing a line of code.

**Requirements:**
- Track only the *last* key seen — nothing more.
- Support a composite key (dedup by a tuple of fields, not just one field).
- Should work as a generator, so it never buffers the whole stream even for the *output*, not just the input.

**Sample input:**
```python
sorted_stream = [
    {"timestamp": "2024-01-01 00:00:00", "user_id": 1, "event": "login"},
    {"timestamp": "2024-01-01 00:00:00", "user_id": 1, "event": "login"},   # dup
    {"timestamp": "2024-01-01 00:00:01", "user_id": 1, "event": "click"},
    {"timestamp": "2024-01-01 00:00:01", "user_id": 2, "event": "login"},
    {"timestamp": "2024-01-01 00:00:01", "user_id": 2, "event": "login"},   # dup
    {"timestamp": "2024-01-01 00:00:02", "user_id": 1, "event": "purchase"},
    {"timestamp": "2024-01-01 00:00:03", "user_id": 3, "event": "login"},
    {"timestamp": "2024-01-01 00:00:03", "user_id": 3, "event": "login"},   # dup
    {"timestamp": "2024-01-01 00:00:03", "user_id": 3, "event": "login"},   # dup
]
key_fields = ["timestamp", "user_id", "event"]
```

**Expected output** (5 records survive, in original order):
```text
ts=2024-01-01 00:00:00, user=1, event=login
ts=2024-01-01 00:00:01, user=1, event=click
ts=2024-01-01 00:00:01, user=2, event=login
ts=2024-01-01 00:00:02, user=1, event=purchase
ts=2024-01-01 00:00:03, user=3, event=login
```

<details>
<summary>Reference solution</summary>

```python
def dedup_sorted_stream(stream, key_fields):
    """O(1) memory: since the stream is sorted, any duplicate of the
    current record must be immediately adjacent to it -- so remembering
    only the single most recently emitted key is enough to catch every
    duplicate, no matter how large the overall stream is."""
    last_key = None
    for record in stream:
        current_key = tuple(record[f] for f in key_fields)
        if current_key != last_key:
            last_key = current_key
            yield record
        # else: duplicate of the immediately preceding record -- skip

deduped = list(dedup_sorted_stream(sorted_stream, ["timestamp", "user_id", "event"]))
for r in deduped:
    print(f"ts={r['timestamp']}, user={r['user_id']}, event={r['event']}")
```

**Why this is the pattern being tested:** the naive `set()`-based dedup is *correct* on unsorted data (and only unsorted data actually needs it — see the "handle a composite key" requirement, which is the same idea whether keys are a single field or several). But if an interviewer tells you the input is sorted, that's not incidental color — it's the whole problem. Recognizing "sorted implies duplicates are adjacent implies I only need to remember one key, not all of them" and saying so before writing code is exactly the signal a `bonus_coding_problems/medium/02_optimization_problems.py`-style optimization problem is scoring. As a generator, this also composes directly with a real streaming pipeline: it can sit between a sorted source and a downstream `windowed_aggregate()` step without ever materializing the full deduplicated list in memory, which is what makes it a genuinely *streaming* algorithm rather than merely a memory-efficient batch one.

**Edge case worth naming out loud:** this only works because the input is *actually* sorted by the same key used for dedup. If the input is sorted by `timestamp` alone but deduplicated on `(timestamp, user_id, event)`, two records with the same full composite key are still guaranteed adjacent (since `timestamp` — the sort key — is a prefix of the dedup key), so the algorithm still holds. If the dedup key were *not* a function of the sort order at all (e.g. sorted by `timestamp` but deduplicating on `user_id` alone), duplicates would no longer be guaranteed adjacent, and this whole approach silently breaks — that's the one clarifying question worth asking before committing to O(1) memory.

</details>

---

## Problem 2: Stream Processing Engine — Windowed Aggregation With Late Data

**Problem statement:** design and implement a small stream-processing engine that consumes a stream of out-of-order events, maintains tumbling-window aggregations keyed on **event time**, and correctly handles late-arriving data using a watermark — rather than either (a) ignoring lateness entirely and producing wrong aggregates, or (b) buffering every event forever and never emitting a final result. This is a from-scratch reconstruction of the "stream processing engine — windowed aggregation, late data" problem from this course's hard/system-design bonus problem set.

**Requirements:**
- Ingest events as `{"event_time": float, "value": float}`, arriving in arbitrary (not necessarily sorted) order.
- Maintain a watermark: `watermark = max_event_time_seen - allowed_lateness`.
- Assign each on-time event to a tumbling window and accumulate a running `(sum, count)` per window — do not buffer raw events forever; only keep what's needed to finish the aggregation.
- A window is safe to **emit** (finalize and hand off) once the watermark has advanced past that window's end. Once emitted, a window is closed.
- An event whose window has *already been emitted* is **late**: route it to a separate `late_events` list rather than silently dropping it or silently mutating an already-emitted result.
- Return, at the end of the stream: all emitted window results (`window_start -> {"sum", "count", "avg"}`) and the list of late events.

**Sample input:**
```python
events = [
    {"event_time": 1,  "value": 100},
    {"event_time": 4,  "value": 200},
    {"event_time": 2,  "value": 150},   # arrives late in order, but still within allowed_lateness
    {"event_time": 8,  "value": 300},
    {"event_time": 11, "value": 400},   # watermark now 11-3=8 -> [0,10) can emit once we pass it
    {"event_time": 3,  "value": 120},   # watermark is 8 -- 3 < 8, and window [0,10) hasn't emitted yet
    {"event_time": 14, "value": 500},   # watermark now 14-3=11 -> [0,10) emits (11 >= 10)
    {"event_time": 6,  "value": 250},   # window [0,10) already emitted -- LATE
]
window_size = 10
allowed_lateness = 3
```

**Expected output:**
```text
Emitted windows:
  [0, 10): sum=870, count=5, avg=174.0     (100 + 200 + 150 + 300 + 120)
  [10, 20): sum=900, count=2, avg=450.0    (400 + 500)

Late events: [{"event_time": 6, "value": 250}]
```

<details>
<summary>Reference solution</summary>

```python
from collections import defaultdict

class WindowedStreamEngine:
    """A minimal windowed aggregation engine: tumbling windows on event
    time, watermark-driven emission, and a side output for late events.
    Only ever holds open (not-yet-emitted) windows in memory -- an
    emitted window is finalized and its running state discarded."""

    def __init__(self, window_size, allowed_lateness):
        self.window_size = window_size
        self.allowed_lateness = allowed_lateness
        self.max_event_time = float("-inf")
        self.open_windows = defaultdict(lambda: {"sum": 0.0, "count": 0})
        self.emitted = {}          # window_start -> finalized result
        self.late_events = []

    def _window_start(self, event_time):
        return (event_time // self.window_size) * self.window_size

    def _watermark(self):
        return self.max_event_time - self.allowed_lateness

    def process(self, event):
        et, val = event["event_time"], event["value"]
        self.max_event_time = max(self.max_event_time, et)
        ws = self._window_start(et)

        if ws in self.emitted:
            # This window has already been finalized -- too late to
            # safely mutate its result. Route to the side output
            # instead of silently dropping or silently re-emitting.
            self.late_events.append(event)
            return "late"

        # Still open (or not yet started) -- safe to fold into the
        # running aggregate, even if it's arriving out of order.
        bucket = self.open_windows[ws]
        bucket["sum"] += val
        bucket["count"] += 1

        self._emit_closed_windows()
        return "processed"

    def _emit_closed_windows(self):
        watermark = self._watermark()
        for ws in sorted(self.open_windows):
            if ws + self.window_size <= watermark:
                bucket = self.open_windows.pop(ws)
                bucket["avg"] = round(bucket["sum"] / bucket["count"], 2)
                self.emitted[ws] = bucket

    def finalize(self):
        """Flush any still-open windows at end-of-stream (in a real
        system this fires when the source signals it's exhausted)."""
        for ws in sorted(self.open_windows):
            bucket = self.open_windows.pop(ws)
            bucket["avg"] = round(bucket["sum"] / bucket["count"], 2)
            self.emitted[ws] = bucket
        return self.emitted, self.late_events


events = [
    {"event_time": 1,  "value": 100}, {"event_time": 4,  "value": 200},
    {"event_time": 2,  "value": 150}, {"event_time": 8,  "value": 300},
    {"event_time": 11, "value": 400}, {"event_time": 3,  "value": 120},
    {"event_time": 14, "value": 500}, {"event_time": 6,  "value": 250},
]

engine = WindowedStreamEngine(window_size=10, allowed_lateness=3)
for e in events:
    engine.process(e)
results, late = engine.finalize()

for ws in sorted(results):
    r = results[ws]
    print(f"[{ws}, {ws + 10}): sum={r['sum']}, count={r['count']}, avg={r['avg']}")
print(f"Late events: {late}")
# [0, 10): sum=870.0, count=5, avg=174.0
# [10, 20): sum=900.0, count=2, avg=450.0
# Late events: [{'event_time': 6, 'value': 250}]
```

**Why this is the pattern being tested:** this problem is really three sub-skills stacked together, and an interviewer is watching whether you handle each cleanly rather than tangling them:

1. **Windows key on event time, not arrival order** — `event_time=3` folds correctly into window `[0,10)` even though it arrives *after* `event_time=8` and `event_time=11`, because the watermark (`8` at that point) hasn't yet passed that window's end (`10`). This is the exact mechanic from `concepts/03_windowing_and_watermarks.md`'s worked timeline, implemented instead of just narrated.
2. **A window only holds state until it's safe to emit, never longer** — `open_windows` only ever contains windows that haven't closed yet; the moment one closes it's popped out and finalized, so memory is bounded by "how many windows can plausibly still be open at once" (a function of `allowed_lateness`), not by total stream length. An implementation that instead buffers every raw event in a list forever and only aggregates at the very end has reintroduced the unbounded-state bug from `concepts/03_windowing_and_watermarks.md`, section 6 — call that out explicitly if you catch yourself doing it.
3. **A late event is data, not noise** — routing `event_time=6` to `late_events` instead of raising an exception, silently dropping it, or silently reopening and re-emitting window `[0,10)` is the "side output" strategy from `concepts/03_windowing_and_watermarks.md`, section 5, chosen deliberately over the other two options because it keeps the already-emitted result stable while still making the late data visible and actionable downstream (a reconciliation job, an alert, a dead-letter-style audit trail) rather than silently vanishing.

**A natural follow-up to practice out loud:** "what if `allowed_lateness` were `0`?" — every event would need to arrive with `event_time <= max_event_time_seen`, so any single out-of-order event becomes instantly late the moment a newer one has been seen; walking through why that makes `allowed_lateness=0` equivalent to naive processing-time windowing (no tolerance for reordering at all) is a good gut-check that you understand *why* the grace period exists, not just how to implement it.

</details>
