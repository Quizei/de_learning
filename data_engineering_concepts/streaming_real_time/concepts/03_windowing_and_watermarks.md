# Concept 03: Windowing and Watermarks

**Covers:**
- Why unbounded streams need windows at all
- Tumbling, sliding, and session windows — mechanics and when to reach for each
- Watermarks: the system's estimate of "how far along in event time have we gotten"
- A fully worked timeline: an out-of-order event, a watermark, and what happens to a late arrival
- Strategies for late data: drop, update-and-emit-again, side output
- Common failure modes: no watermark at all, and watermark configured too tight or too loose

*All Python below is real, runnable stdlib — copy any block into a `python3` shell and it runs as shown.*

This is one of the most heavily-tested streaming concepts at the mid-level, precisely because it's where "streaming is just batch but faster" stops being true. A batch job can sort its entire input before aggregating; a streaming job has to decide, continuously and without ever seeing the future, when it's safe to say "this group of events is done, emit the result" — windows and watermarks are the two mechanisms that make that decision possible.

---

## 1. Why Windows Exist

An unbounded stream has no natural endpoint to aggregate up to — "sum of all clicks" is a number that changes forever and is never final. A **window** carves the infinite stream into finite chunks by *time*, so "sum of clicks in this window" is a question with a real, eventually-final answer. Every windowed aggregation is really answering: which events belong together, and when is it safe to say we've seen them all?

```text
Tumbling:  |----5min----|----5min----|----5min----|   (non-overlapping, fixed)
Sliding:   |----5min----|                              (overlapping by slide interval;
                |----5min----|                          one event can land in >1 window)
Session:   |--events--|   gap   |--events--|            (activity-based, no fixed size)
```

---

## 2. Tumbling Windows

Fixed-size, back-to-back, non-overlapping. Every event belongs to exactly one window: `window_start = (event_time // window_size) * window_size`.

```python
from collections import defaultdict

events = [
    (1, "click"),  (3, "click"),  (7, "purchase"),
    (12, "click"), (14, "click"), (15, "purchase"),
    (22, "click"), (28, "click"), (35, "click"),
]

window_size = 10
tumbling = defaultdict(list)
for ts, action in events:
    window_start = (ts // window_size) * window_size
    tumbling[window_start].append(action)

for ws in sorted(tumbling):
    print(f"Window [{ws}s-{ws+window_size}s): {tumbling[ws]}")
# Window [0s-10s):  ['click', 'click', 'purchase']
# Window [10s-20s): ['click', 'click', 'purchase']
# Window [20s-30s): ['click', 'click']
# Window [30s-40s): ['click']
```

```text
# Real Kafka Streams equivalent:
#   stream.groupByKey()
#         .windowedBy(TimeWindows.of(Duration.ofSeconds(10)))
#         .count()
```

Use tumbling windows for "per-interval" reporting — clicks per minute, revenue per hour — where each event should count toward exactly one bucket. It's the simplest window type and the right default when nothing pushes you toward one of the other two.

---

## 3. Sliding Windows

Fixed-size, but windows start at every `slide` interval, so `window_size > slide` means windows **overlap** and a single event contributes to more than one window's result.

```python
window_size, slide = 10, 5
events = [(1, 10), (3, 20), (5, 30), (7, 40), (9, 50)]  # (timestamp, value)

max_ts = max(ts for ts, _ in events)
sliding = defaultdict(list)
for window_start in range(0, max_ts + 1, slide):
    window_end = window_start + window_size
    for ts, value in events:
        if window_start <= ts < window_end:
            sliding[window_start].append(value)

for ws in sorted(sliding):
    print(f"Window [{ws}s-{ws+window_size}s): sum={sum(sliding[ws])}")
# Window [0s-10s):  sum=150   (10+20+30+40+50)
# Window [5s-15s):  sum=120   (30+40+50 -- overlaps with the window above)
```

Sliding windows answer "what does the trailing N-minute average look like, updated every M minutes" — a rolling 5-minute click-through-rate recomputed every 30 seconds is a sliding window, not a tumbling one. The cost is real: each event is processed once per window it belongs to (`window_size / slide` times), so a 5-minute window sliding every second means every event gets aggregated into roughly 300 separate windows.

---

## 4. Session Windows

Dynamic-length windows with no fixed size at all — a new session starts whenever the gap since the last event exceeds a threshold, and the window closes only after that gap has actually elapsed. This is the window type used for "user activity sessions," where a burst of clicks is one session and 20 minutes of silence starts a new one.

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

timestamps = [1, 2, 3, 10, 11, 12, 25, 26, 27, 28]
print(detect_sessions(timestamps, gap_threshold=5))
# [[1, 2, 3], [10, 11, 12], [25, 26, 27, 28]]
# gaps: 1->2(1) 2->3(1) 3->10(7, EXCEEDS 5 -> new session)
#       10->11(1) 11->12(1) 12->25(13, EXCEEDS 5 -> new session)
#       25->26(1) 26->27(1) 27->28(1)
```

A session window can only be declared "closed" once enough real time has passed with no new activity — which means, unlike tumbling and sliding windows, you don't even know a session's boundaries until *after* it ends. That makes session windows the type most dependent on getting watermarks right, which is exactly what the rest of this file covers.

---

## 5. Watermarks: Estimating "How Far Along Are We"

A **watermark** is the stream processor's own running estimate, in event time, of *"I have now seen everything up to this point — anything with an event time before this is either here already or isn't coming."* The standard policy:

```text
watermark = max_event_time_seen_so_far - allowed_lateness
```

An event is **on time** if its event time is at or after the current watermark; it's **late** if the watermark has already passed the window that event belongs to. Windows use the watermark, not processing time, to decide when it's finally safe to emit a result: a window is considered closed once `watermark >= window_end`.

### Worked timeline: an out-of-order event crossing a watermark

Walk through this table left to right exactly as a stream processor would — one event arriving at a time, updating its watermark, and deciding what to do:

```text
allowed_lateness = 3s   window_size = 10s

  Event   Event    Max event    Watermark      Window it        Decision
  order   time     time seen    (max - 3)      belongs to
  -----   -----    ---------    ---------      ----------       --------
  1       t=1      1            -2             [0,10)           ON TIME  -> add to [0,10)
  2       t=4      4             1             [0,10)           ON TIME  -> add to [0,10)
  3       t=2      4             1             [0,10)           ON TIME  -> t=2 >= watermark(1), still fine
  4       t=8      8             5             [0,10)           ON TIME  -> add to [0,10)
  5       t=11     11            8             [10,20)          ON TIME  -> add to [10,20), watermark now past [0,10)'s end? No: [0,10) closes when watermark>=10
  6       t=3      11            8             [0,10)           LATE     -> watermark(8) already > t=3, and window [0,10)
                                                                            would close once watermark>=10 -- this event
                                                                            missed its chance to be counted safely
  7       t=14     14            11            [10,20)          ON TIME  -> watermark(11) now >= 10, so [0,10) OFFICIALLY CLOSES and emits
  8       t=6      14            11            [0,10)           VERY LATE -> [0,10) has already closed and emitted; t=6 arrives
                                                                              after the result was already produced
```

Event 6 (`t=3`) is the one worth narrating slowly in an interview: at the moment it arrives, the watermark sits at `8` (from event 4's `t=8`). The watermark is the processor's declaration that *"I believe I've seen everything up through event-time 8; I won't wait any longer for anything earlier than that."* Event 6's `t=3` is behind that declaration (`3 < 8`), so it's classified late **immediately** — even though the window `[0,10)` it belongs to technically hasn't closed yet (that only happens once the watermark reaches `10`, at event 7). This is the subtlety that trips people up: **an event is judged late purely by comparing its event time to the current watermark, not by whether its window has literally closed** — the watermark is a single global "I won't wait for anything before this" line, and `allowed_lateness` is what controls how generous that line is, not a per-window cutoff applied only at close time.

```python
allowed_lateness = 3
window_size = 10
arrivals = [
    {"event_time": 1,  "value": 100},
    {"event_time": 4,  "value": 200},
    {"event_time": 2,  "value": 150},   # within lateness, still fine
    {"event_time": 8,  "value": 300},
    {"event_time": 11, "value": 400},
    {"event_time": 3,  "value": 120},   # LATE -- watermark has moved past it
    {"event_time": 14, "value": 500},
    {"event_time": 6,  "value": 250},   # VERY LATE
]

max_event_time = 0
window_results = defaultdict(list)
late_events = []

for e in arrivals:
    et, val = e["event_time"], e["value"]
    max_event_time = max(max_event_time, et)
    watermark = max_event_time - allowed_lateness
    window_start = (et // window_size) * window_size

    if et < watermark:
        late_events.append(e)
        status = "LATE -> dropped"
    else:
        window_results[window_start].append(val)
        status = "OK -> processed"
    print(f"event_time={et:<3} max_seen={max_event_time:<3} watermark={watermark:<3} {status}")

print("\nWindow results:")
for ws in sorted(window_results):
    vals = window_results[ws]
    print(f"  [{ws}s-{ws+window_size}s): sum={sum(vals)}, count={len(vals)}")
print(f"\nDropped as late: {[e['event_time'] for e in late_events]}")
# event_time=1   max_seen=1   watermark=-2  OK -> processed
# event_time=4   max_seen=4   watermark=1   OK -> processed
# event_time=2   max_seen=4   watermark=1   OK -> processed
# event_time=8   max_seen=8   watermark=5   OK -> processed
# event_time=11  max_seen=11  watermark=8   OK -> processed
# event_time=3   max_seen=11  watermark=8   LATE -> dropped
# event_time=14  max_seen=14  watermark=11  OK -> processed
# event_time=6   max_seen=14  watermark=11  LATE -> dropped
#
# Window results:
#   [0s-10s): sum=750, count=4     (100+200+150+300)
#   [10s-20s): sum=900, count=2    (400+500)
#
# Dropped as late: [3, 6]
```

### Strategies for late data

Once an event is determined to be late, a stream processor has three real options — the choice is a product decision as much as a technical one:

1. **Drop it.** Simplest; accepts silent, small inaccuracy. Fine for dashboards where a rounding-level miss doesn't matter.
2. **Update and re-emit the window's result.** The window's aggregate was already emitted once; a late arrival triggers a *revised* emission (Flink's `allowedLateness` + updating output; Spark's update output mode). Correct, but every downstream consumer of that window's output now has to handle "this result can change after I first saw it," which is a real complexity cost.
3. **Side output.** Route late events to a separate stream/topic instead of silently dropping or silently revising anything — a human or a separate reconciliation job deals with them out of band. This is often the best default for anything where correctness is audited (financial data), because it makes "we had late data and here's exactly what we did with it" an explicit, inspectable fact instead of a silent behavior.

---

## 6. Two Failure Modes Worth Naming Unprompted

**No watermark at all.** A windowed aggregation with no watermark logic has no way to ever decide a window is "done" — it either never emits a result (waiting forever for events that might still be late), or it emits based on wall-clock/processing time, which reintroduces every problem event-time processing was supposed to solve. Worse, without a watermark bounding how long a window's state is kept around, the processor has to retain state for *every window that has ever been opened, forever* — this is the classic **unbounded state** bug: memory grows without limit because nothing ever tells the system it's safe to forget an old window. This exact bug is drilled as a diagnosis case in `interview_questions/03_critique_and_debug.md`.

**Watermark configured too tight or too loose.** `allowed_lateness` is a real trade-off, not a constant to memorize: too tight (a small grace period) means more real events get dropped as "late" even though they were only slightly delayed by normal network jitter; too loose (a large grace period) means every window stays open far longer, holding more in-flight state and delaying every result — a `allowed_lateness` of 10 minutes means a 1-minute tumbling window's result might not be final until 11 minutes after it started. The right value comes from the actual observed lateness distribution of the specific data source, not a default copied from a blog post.

---

## Key Takeaways

- Windows exist because an unbounded stream has no natural point to say "the sum is final" — tumbling (fixed, non-overlapping), sliding (fixed, overlapping), and session (dynamic, gap-based) are the three ways to carve one up.
- A watermark is the processor's own running estimate, in event time, of what it's safely seen everything up through: `watermark = max_event_time_seen - allowed_lateness`. An event is late relative to the *watermark*, not relative to whether its window has literally closed yet — that distinction is what `allowed_lateness` exists to manage.
- Late data can be dropped, trigger an updated re-emission, or be routed to a side output — pick deliberately, since each has a different correctness/complexity trade-off, and "side output" is usually the right default when correctness needs to be auditable.
- A windowed aggregation with no watermark either never closes a window or falls back to unreliable processing-time closing, and its state grows without bound — this is one of the most common streaming bugs asked about directly (`interview_questions/03_critique_and_debug.md`).
