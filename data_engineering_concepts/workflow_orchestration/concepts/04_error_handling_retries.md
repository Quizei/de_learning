# Concept 04: Error Handling & Retries

**Covers:**
- Retry policies — fixed, linear, exponential backoff, and why jitter matters
- The full task lifecycle: callbacks, timeouts, and how a state machine ties them together
- SLAs — what they actually do (alert), and what they deliberately don't do (stop the task)
- Dead-letter-queue handling for bad records vs. failed tasks
- The circuit breaker pattern, and why it's a different tool from a retry policy
- Idempotency — the property that makes every pattern in this file *safe*, not just present

*Code below is runnable, dependency-free Python.*

---

## 1. Retry Policies: Fixed, Linear, Exponential, and Jitter

Not every failure deserves the same retry treatment. A transient network blip and a downstream system that's genuinely down for ten minutes both look identical on the first failure — retry strategy is a bet about which one you're facing:

```python
import random

class RetryPolicy:
    def __init__(self, max_retries=3, base_delay=1.0, strategy="exponential",
                 max_delay=60.0, jitter=True):
        self.max_retries, self.base_delay = max_retries, base_delay
        self.strategy, self.max_delay, self.jitter = strategy, max_delay, jitter

    def get_delay(self, attempt):
        if self.strategy == "fixed":
            delay = self.base_delay
        elif self.strategy == "linear":
            delay = self.base_delay * (attempt + 1)
        else:  # exponential
            delay = self.base_delay * (2 ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay += random.uniform(0, delay * 0.5)
        return round(delay, 2)


for strategy in ["fixed", "linear", "exponential"]:
    policy = RetryPolicy(base_delay=1.0, strategy=strategy, jitter=False)
    print(f"{strategy:12s} {[policy.get_delay(i) for i in range(5)]}")
```

```text
fixed        [1.0, 1.0, 1.0, 1.0, 1.0]
linear       [1.0, 2.0, 3.0, 4.0, 5.0]
exponential  [2.0, 4.0, 8.0, 16.0, 32.0]
```

**Jitter** adds randomness (commonly 0-50% extra) on top of whatever the base strategy computes. Its purpose has nothing to do with any one task — it exists for the case where *many* tasks fail at the same moment (a shared dependency, like a database, going down) and would otherwise all retry in unison on the exact same clock tick. Synchronized retries recreate the very load spike that caused the outage the moment the system starts to recover — a **thundering herd**. Jitter staggers those retries so recovery is gradual instead of another spike.

---

## 2. The Task Lifecycle: State Machine + Callbacks + Timeout

A production task runner combines four things: a state machine, a retry loop, an optional timeout, and lifecycle callbacks fired at the right transitions:

```python
import time, threading
from enum import Enum

class TaskState(Enum):
    PENDING, RUNNING, SUCCESS, FAILED, UP_FOR_RETRY, TIMED_OUT = range(6)

class TaskRunner:
    def __init__(self, task_id, callable_fn, retry_policy=None, timeout_seconds=None,
                 on_success=None, on_failure=None, on_retry=None):
        self.task_id = task_id
        self.callable_fn = callable_fn
        self.retry_policy = retry_policy or RetryPolicy(max_retries=0)
        self.timeout_seconds = timeout_seconds
        self.on_success, self.on_failure, self.on_retry = on_success, on_failure, on_retry
        self.state = TaskState.PENDING
        self.attempt = 0
        self.max_attempts = self.retry_policy.max_retries + 1

    def _execute_with_timeout(self):
        if self.timeout_seconds is None:
            return self.callable_fn()
        box = {"value": None, "error": None}
        def target():
            try:
                box["value"] = self.callable_fn()
            except Exception as e:
                box["error"] = e
        t = threading.Thread(target=target, daemon=True)
        t.start(); t.join(timeout=self.timeout_seconds)
        if t.is_alive():
            raise TimeoutError(f"'{self.task_id}' exceeded {self.timeout_seconds}s")
        if box["error"]:
            raise box["error"]
        return box["value"]

    def run(self):
        for attempt in range(self.max_attempts):
            self.attempt = attempt + 1
            self.state = TaskState.RUNNING
            try:
                result = self._execute_with_timeout()
                self.state = TaskState.SUCCESS
                if self.on_success:
                    self.on_success({"task_id": self.task_id, "attempt": self.attempt})
                return result
            except Exception as e:
                is_last = attempt == self.max_attempts - 1
                self.state = TaskState.FAILED if is_last else TaskState.UP_FOR_RETRY
                ctx = {"task_id": self.task_id, "attempt": self.attempt, "error": str(e)}
                if is_last:
                    if self.on_failure:
                        self.on_failure(ctx)
                else:
                    if self.on_retry:
                        self.on_retry(ctx)
                    time.sleep(self.retry_policy.get_delay(attempt))
        return None
```

```python
attempts = {"n": 0}
def flaky_api():
    attempts["n"] += 1
    if attempts["n"] < 3:
        raise ConnectionError("API returned 503")
    return {"status": "ok"}

runner = TaskRunner(
    "fetch_data", flaky_api,
    retry_policy=RetryPolicy(max_retries=3, base_delay=0.01, jitter=False),
    on_retry=lambda ctx: print(f"  retry #{ctx['attempt']}: {ctx['error']}"),
    on_success=lambda ctx: print(f"  succeeded on attempt {ctx['attempt']}"),
)
print(runner.run())
```

```text
  retry #1: API returned 503
  retry #2: API returned 503
  succeeded on attempt 3
{'status': 'ok'}
```

`on_failure` is what actually wires a pipeline into PagerDuty/Slack — it's the callback that fires once, on the *final* exhausted attempt, and it's the natural place to page someone rather than something a human has to notice by watching a dashboard.

---

## 2b. Retries Are Not Free: The Non-Idempotent Trap

Everything above assumes retrying the task is safe to do more than once. **It frequently isn't**, and this is one of the most common real orchestration bugs (see `interview_questions/03_critique_and_debug.md`): a task that appends a row, sends an email, or charges a payment on every call will, under a naive retry policy, do that side effect multiple times if it fails *after* the side effect but before it reports success — a network timeout on the response, not the request, is a completely ordinary way for this to happen.

```text
Non-idempotent (dangerous to retry blindly):
  INSERT INTO orders VALUES (...)          -- retry -> duplicate row
  send_email(customer, "order shipped")    -- retry -> duplicate email
  POST /charge-card                        -- retry -> double charge

Idempotent (safe to retry any number of times):
  INSERT ... ON CONFLICT (order_id) DO UPDATE ...    -- upsert keyed on a natural ID
  DELETE FROM t WHERE date = :d; INSERT INTO t ...    -- delete-then-insert on a partition key
  send_email(...) guarded by an idempotency key       -- provider dedupes on the key
  POST /charge-card  with an Idempotency-Key header   -- provider dedupes server-side
```

The fix is never "add fewer retries" — it's making the task itself idempotent, so retrying it (by the orchestrator, or by a human manually clearing and rerunning it) produces the same end state no matter how many times it runs. This is the same property backfills depend on (`concepts/05_backfills_and_catchup.md`) and it's worth stating explicitly in an interview: **a retry policy is a band-aid over a non-idempotent task, not a substitute for making the task idempotent.**

---

## 3. SLAs: They Alert, They Do Not Stop Anything

An **SLA** (Service Level Agreement, in Airflow's specific sense) declares the maximum time a task or DAG is expected to take. Its entire job is to fire an alert if that's exceeded — it does **not** kill the task, cancel it, or affect retries in any way. That's a common point of confusion worth naming outright: SLA and timeout look similar but do opposite things.

```python
from datetime import timedelta

class SLAMonitor:
    def __init__(self):
        self.sla_definitions, self.violations = {}, []

    def set_sla(self, task_id, max_duration):
        self.sla_definitions[task_id] = max_duration

    def check_sla(self, task_id, actual_duration):
        sla = self.sla_definitions.get(task_id)
        if sla and actual_duration > sla:
            v = {"task_id": task_id, "exceeded_by": str(actual_duration - sla)}
            self.violations.append(v)
            return v
        return None


monitor = SLAMonitor()
monitor.set_sla("transform", timedelta(hours=1))
result = monitor.check_sla("transform", timedelta(hours=1, minutes=20))
print(result)
```

```text
{'task_id': 'transform', 'exceeded_by': '0:20:00'}
```

```text
SLA        "Alert someone if this took longer than expected." Task keeps running.
Timeout    "Kill this task if it runs longer than X."          Task is forcibly stopped.
```

Mixing these up in an interview answer — saying an SLA "kills the task" — is a specific, checkable tell that the concept wasn't fully internalized.

---

## 4. Dead Letter Queue: Isolating Bad Records, Not Failing the Pipeline

A **task** failing and a **record** being bad are different problems needing different responses. If 30 out of 10,000 rows in a batch have a malformed field, failing the entire task over 0.3% of the data is usually the wrong call — the standard pattern is to quarantine the bad rows and let the good ones through:

```python
class DeadLetterQueue:
    def __init__(self, max_ratio=0.05):
        self.dead_letters = []
        self.processed_count = 0
        self.max_ratio = max_ratio

    def process_batch(self, records, processor_fn):
        good = []
        for record in records:
            self.processed_count += 1
            try:
                good.append(processor_fn(record))
            except Exception as e:
                self.dead_letters.append({"record": record, "error": str(e)})
        return good

    def exceeded_threshold(self):
        if not self.processed_count:
            return False
        return len(self.dead_letters) / self.processed_count > self.max_ratio


records = [{"id": i, "amount": v} for i, v in
           enumerate(["100.50", "invalid", "250.00", None, "75.25"], start=1)]

def process(record):
    return {"id": record["id"], "cents": int(float(record["amount"]) * 100)}

dlq = DeadLetterQueue(max_ratio=0.10)
good = dlq.process_batch(records, process)
print(f"processed_ok={len(good)} dead_letters={len(dlq.dead_letters)} "
      f"exceeded={dlq.exceeded_threshold()}")
```

```text
processed_ok=3 dead_letters=2 exceeded=True
```

The `max_ratio` threshold is the important design decision here, not the mechanism itself: below it, quarantine and continue; above it, the failure rate itself has become the signal that something upstream is systemically broken, and the task should fail loudly rather than silently drop a large fraction of the data.

---

## 5. Circuit Breaker: Stop Hammering a System That's Already Down

Retrying a call to a dependency that is fully down doesn't help it recover faster — it adds load to a system already struggling, and burns time on retries that were never going to succeed. A **circuit breaker** tracks recent failure counts and, past a threshold, stops even trying for a cooldown period:

```python
class CircuitBreaker:
    CLOSED, OPEN, HALF_OPEN = "CLOSED", "OPEN", "HALF_OPEN"

    def __init__(self, failure_threshold=3, cooldown_seconds=5):
        self.state = self.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.last_failure_time = None

    def call(self, fn, *args, **kwargs):
        if self.state == self.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed < self.cooldown_seconds:
                raise RuntimeError(f"circuit OPEN, {self.cooldown_seconds - elapsed:.1f}s left")
            self.state = self.HALF_OPEN
        try:
            result = fn(*args, **kwargs)
            self.state, self.failure_count = self.CLOSED, 0
            return result
        except Exception:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold or self.state == self.HALF_OPEN:
                self.state = self.OPEN
            raise
```

```text
CLOSED     Normal operation -- calls go through, failures are just counted.
OPEN       Threshold breached -- fail FAST, don't even attempt the call, until cooldown expires.
HALF_OPEN  Cooldown expired -- let exactly one call through as a test.
             succeeds -> CLOSED (system recovered)
             fails    -> back to OPEN (not recovered yet, wait another cooldown)
```

**Circuit breaker vs. retry policy, stated as the interview answer:** a retry policy assumes the failure is transient and keeps trying the *same* call; a circuit breaker assumes enough consecutive failures means the dependency is *systemically* down right now, and the correct response is to stop calling it at all for a while — they compose (retry a few times, and if a circuit breaker downstream has already tripped, fail fast without spending the retries at all) rather than replace each other.

---

## Key Takeaways

- Exponential backoff plus jitter is the standard retry strategy for transient failures — backoff avoids re-hitting a struggling system immediately, jitter avoids every failed task retrying on the exact same clock tick and recreating the load spike (thundering herd).
- A retry policy is only safe if the task is idempotent; retrying a non-idempotent task (an insert, a charge, a send) risks duplicating the side effect, not just repeating a read.
- SLA and timeout are frequently confused but do opposite things: an SLA fires an alert while the task keeps running; a timeout forcibly kills the task.
- A dead letter queue isolates bad *records* so a task doesn't fail wholesale over a small bad fraction of a batch — but the failure-rate threshold itself should trip a real failure once it's high enough to signal a systemic problem, not just noisy data.
- A circuit breaker stops calling an already-down dependency instead of continuing to retry it — CLOSED (normal) → OPEN (fail fast) → HALF_OPEN (test one call) → CLOSED or back to OPEN.
- A production pipeline layers all of these together: retry+backoff for transient errors, a circuit breaker for systemic outages, a DLQ for bad records, SLA alerts for visibility, and callbacks wiring failures into PagerDuty/Slack — none of them individually is "the" error-handling strategy.
