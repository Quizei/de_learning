# Project: Mini Stream Processor

## Goal

Build a small, Kafka-inspired stream processing engine that pulls this whole topic together: a message broker with topics/partitions/consumer groups, windowed aggregation keyed on event time, watermark-driven late-data handling, and exactly-once processing via deduplication. This is the capstone every concept file in this topic feeds into — if a design decision from `concepts/` or a bug from `interview_questions/03_critique_and_debug.md` doesn't show up as a concrete requirement below, that's worth noticing.

This brief describes the **interface and requirements** — the shape a strong solution takes, and the specific behaviors it must demonstrate — not a full worked solution. Write it yourself; use `concepts/` and `practice/` to check individual pieces as you go.

---

## Requirements

Your stream processor must:

1. **Simulate a Kafka-like broker:** named topics split into a configurable number of partitions, each an ordered append-only log with its own offsets. Producing with a key must route to the same partition every time that key is used (`concepts/02_kafka_concepts.md`, section 2).
2. **Support consumer groups with real rebalancing:** partitions assigned round-robin across a group's consumers, re-assigned whenever a consumer is added or removed — and correctly demonstrate the "more consumers than partitions leaves some idle" case, not just the even-split case.
3. **Window on event time, not processing time:** implement tumbling windows at minimum (stretch: sliding and/or session windows too — see `concepts/03_windowing_and_watermarks.md`), keyed off each event's own `event_time` field, fed events in a deliberately **out-of-order** arrival sequence to prove windowing doesn't depend on arrival order.
4. **Track a watermark and handle late data on purpose:** maintain `watermark = max_event_time_seen - allowed_lateness`, and route any event whose window has already emitted to a `late_events` output rather than silently dropping it or silently mutating an already-finalized result (`concepts/03_windowing_and_watermarks.md`, section 5 and `practice/coding_problems.md`, Problem 2, are both worked references for exactly this behavior — don't just copy them, but check your own implementation's outputs against that worked example's arithmetic).
5. **Process exactly once under simulated retries:** deduplicate by an event ID/idempotency key so that a message delivered twice (simulating an at-least-once redelivery after a consumer crash) is counted once in the final aggregation, not twice — and expose a stat showing how many duplicates were caught.
6. **Bound your own memory:** an emitted (closed) window's raw event buffer must actually be released, not just marked "done" while still resident — re-read `concepts/03_windowing_and_watermarks.md`, section 6 before considering this requirement met; "it works on a short demo run" does not prove this requirement is satisfied.
7. **Expose run statistics and a way to inspect state:** counts processed / deduplicated / late / windows-emitted, plus a way to print the current watermark, the currently-open windows, and the late-events log — "why did event X get marked late" should be answerable from these, not by adding print statements and re-running.

## What a Strong Solution Demonstrates

- Key-based partitioning with a demonstrated ordering guarantee per key, and a demonstrated *lack* of ordering guarantee across keys (`concepts/02_kafka_concepts.md`)
- Consumer-group rebalancing across at least three scenarios: even split, more partitions than consumers, more consumers than partitions
- A tumbling-window aggregation that produces the *correct* result specifically because it keys on event time while consuming events in an out-of-order arrival sequence (`concepts/01_streaming_fundamentals.md`, section 3; `concepts/03_windowing_and_watermarks.md`)
- A watermark that correctly identifies late events using the same rule worked through in `concepts/03_windowing_and_watermarks.md` (`event_time < current_watermark`), and a late-events side output that is inspectable, not silently discarded
- Deduplication that provably reduces a stream containing deliberate retries back down to the correct unique count (`concepts/05_exactly_once_semantics.md`)
- Bounded memory: an emitted window's per-event state is actually freed, demonstrated by running a long synthetic stream and confirming open-window count stays small and roughly constant rather than growing with total events processed

## Starter Data (given — build against this, don't redesign it)

```python
import random

EVENT_TYPES = ["page_view", "click", "add_to_cart", "purchase"]
USERS = [f"user_{i:03d}" for i in range(1, 11)]

def generate_event_stream(num_events=200, late_probability=0.15, max_lateness=8.0, seed=42):
    """Generates events with a monotonically increasing 'true' event time,
    but returns them in a shuffled/out-of-order ARRIVAL sequence, with a
    fraction deliberately assigned an event_time far enough behind the
    current max to be genuinely late once processed. Also injects a small
    number of exact duplicates (same event_id, same event_time) to exercise
    deduplication."""
    random.seed(seed)
    events = []
    for i in range(num_events):
        true_time = i * 0.5  # events are 0.5s apart in "true" event time
        if random.random() < late_probability:
            event_time = true_time - random.uniform(2, max_lateness)
        else:
            event_time = true_time
        events.append({
            "event_id": f"evt-{i:05d}",
            "event_time": round(event_time, 3),
            "user_id": random.choice(USERS),
            "event_type": random.choice(EVENT_TYPES),
        })

    # Inject ~5% exact duplicates (simulating at-least-once redelivery)
    duplicates = random.sample(events, k=max(1, num_events // 20))
    events.extend(duplicates)

    random.shuffle(events)  # arrival order != event-time order
    return events

# Your broker/processor must handle this stream correctly: out-of-order
# arrival, genuinely late events mixed in with on-time ones, and exact
# duplicates -- all three at once, not as separate isolated test cases.
```

## Interface to Implement

```python
class Partition:
    """An ordered, append-only log. Each message gets a monotonically
    increasing offset. Ordering is guaranteed only within one partition."""
    def __init__(self, partition_id):
        raise NotImplementedError

    def append(self, message) -> int:
        """Append a message, return its offset."""
        raise NotImplementedError

    def read(self, offset, max_messages=100) -> list:
        raise NotImplementedError


class MessageBroker:
    """Kafka-like broker: named topics, each split into partitions;
    key-based routing; consumer-group offset tracking and rebalancing."""

    def create_topic(self, name, num_partitions=3):
        raise NotImplementedError

    def produce(self, topic_name, key, value) -> dict:
        """Route by hash(key) % num_partitions (round-robin if key is None).
        Return {"partition": int, "offset": int}."""
        raise NotImplementedError

    def consume(self, topic_name, group_id, consumer_id, max_records=100) -> list:
        """Read from this consumer's currently-assigned partitions,
        advancing that group's offsets."""
        raise NotImplementedError

    def rebalance(self, topic_name, group_id, consumer_ids: list) -> dict:
        """Round-robin assign partitions across the given consumers.
        Return {consumer_id: [partition_ids]}."""
        raise NotImplementedError


class WindowedStreamProcessor:
    """Tumbling-window aggregation on event time, watermark-driven late
    data handling, and exactly-once processing via deduplication."""

    def __init__(self, window_size_seconds, allowed_lateness_seconds):
        """Set up empty open-window state, watermark tracking (start at
        -infinity), a dedup cache, and a late_events list."""
        raise NotImplementedError

    def process_event(self, event) -> dict:
        """
        In order:
          1. Dedup check on event_id -- if seen before, return
             {"status": "deduplicated", ...} and do nothing else.
          2. Update the watermark from event_time.
          3. If this event's window has ALREADY been emitted, route to
             late_events and return {"status": "late", ...}.
          4. Otherwise fold into the correct (possibly not-yet-open)
             window's running aggregate and return {"status": "processed", ...}.
        """
        raise NotImplementedError

    def emit_closed_windows(self) -> dict:
        """Finalize and RELEASE the state of any window whose end has
        fallen behind the current watermark. Returns the newly emitted
        windows this call discovered (not the full history)."""
        raise NotImplementedError

    def finalize(self) -> dict:
        """End-of-stream: emit every still-open window regardless of
        watermark (there's no more data coming). Return all emitted
        windows and the late_events list."""
        raise NotImplementedError

    def get_stats(self) -> dict:
        """{'processed': int, 'deduplicated': int, 'late': int,
        'windows_emitted': int, 'open_window_count': int}"""
        raise NotImplementedError


class Pipeline:
    """Ties EventSource-style input -> MessageBroker -> WindowedStreamProcessor
    -> a printable sink together as one runnable demonstration."""

    def run(self, events: list, topic_name="events", window_size=5.0,
            allowed_lateness=3.0, num_partitions=3, num_consumers=2) -> dict:
        """Produce all events into the broker (keyed by user_id), rebalance
        a consumer group across num_consumers, consume everything, feed it
        through the processor, and return a stats dict covering every
        requirement above."""
        raise NotImplementedError
```

## Demonstration Script to Run Against Your Own Implementation

Write a small `main()` that proves the requirements, not just exercises the happy path:

```python
events = generate_event_stream(num_events=200, late_probability=0.15, seed=42)

pipeline = Pipeline()
stats = pipeline.run(events, window_size=5.0, allowed_lateness=3.0,
                      num_partitions=3, num_consumers=2)

print(stats)
# Requirement 5: duplicates injected into the stream must be caught.
assert stats["deduplicated"] > 0, "the injected duplicates should have been caught"

# Requirement 4: late events must be routed, not silently dropped --
# with late_probability=0.15 on a 200-event stream, some should land
# after their window already emitted.
assert stats["late"] > 0, "some events should have landed after their window closed"

# Requirement 6: memory must be bounded -- open window count should stay
# small and roughly constant, not grow with total events processed.
# Prove this by running a MUCH larger stream and asserting the processor's
# open_window_count never exceeds a small constant (e.g. a handful of
# windows -- allowed_lateness / window_size bounds how many can plausibly
# still be open at once) at any point during processing, not just at the end.
big_events = generate_event_stream(num_events=20000, late_probability=0.15, seed=7)
big_pipeline = Pipeline()
big_stats = big_pipeline.run(big_events, window_size=5.0, allowed_lateness=3.0)
assert big_stats["open_window_count"] <= 5, "window state should not grow with stream length"
```

## Stretch Goals

- Add sliding windows as a second aggregation mode, and demonstrate the same input stream producing correctly overlapping window results (`concepts/03_windowing_and_watermarks.md`, section 3).
- Run the broker's producer and the processor's consumer loop on separate threads (mirroring the source project's threaded demo), and confirm your watermark/dedup/late-data logic is still correct under real concurrent access — this is where a naive, unlocked implementation of the dedup cache or the open-windows dict will surface a race condition that a single-threaded test run never would.
- Add a configurable `late-data strategy` (drop / side-output / update-and-re-emit — `concepts/03_windowing_and_watermarks.md`, section 5) instead of hard-coding "route to late_events," and demonstrate all three against the same input stream producing three different, individually correct outputs.
- Extend the exactly-once dedup cache with an LRU eviction policy (bounded size, not unbounded) and demonstrate that an old-enough duplicate — one whose original has already been evicted from the cache — is, correctly, no longer caught, and explain in a comment why that's an acceptable, deliberate trade-off rather than a bug.

## Grading Yourself

The two tests that matter most, in order:

1. **Feed it a stream with duplicates, late events, and out-of-order arrival, all mixed together in one run — not three separate isolated tests.** If your window results are numerically correct (verifiable by hand for a small enough stream, the way `practice/coding_problems.md`, Problem 2's sample input is), your late-events list contains exactly the events that should be there, and your dedup count matches the number of injected duplicates, the core of this project is solid.
2. **Run a stream 100x longer than your first test and check that open-window count doesn't grow.** If it does, you've reimplemented the unbounded-state bug from `interview_questions/03_critique_and_debug.md`, Case 2 — go re-read `concepts/03_windowing_and_watermarks.md`, section 6, before touching anything else.
