# Concept 19: Testing & Debugging PySpark Jobs

**Covers:**
- Unit-testing a PySpark transformation function
- A local SparkSession fixture for tests
- assertDataFrameEqual vs manual collect()+sorted comparison
- Why small pure functions beat testing a monolithic pipeline script
- Common runtime errors and what they actually mean: OutOfMemoryError, FetchFailedException, Task not serializable, AnalysisException
- Where to actually look when a job fails (Spark UI, executor logs)
- A pytest-style test suite using plain assert statements

> *Note: this topic isn't in the source YouTube playlist — added because it's essential and commonly asked about.*

*The PySpark snippets below reflect what you'd run against a real Spark session; the worked test-suite example and its output are simulated here in pure Python so you can follow along without a cluster or pytest installed.*

---

## 1. Unit-testing a PySpark transformation function

The pattern that makes PySpark code testable: write your business logic as PURE FUNCTIONS that take a DataFrame (plus maybe some parameters) and return a DataFrame — no reading from a specific path, no writing to a specific sink, no reliance on global state. The I/O (reading sources, writing sinks) stays in a thin outer layer that you don't unit-test the same way (or test with mocks/integration tests instead).

Then in a test, you build a small SparkSession, construct a tiny input DataFrame by hand (a handful of representative/edge-case rows — not real production data), call the function, and assert on the output.

```python
# ---- transformations.py (the code you want to test) ----
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

def add_tax(df: DataFrame, tax_rate: float) -> DataFrame:
    """Pure function: takes a DataFrame, returns a DataFrame."""
    return df.withColumn("total", F.col("amount") * (1 + tax_rate))

def filter_valid_orders(df: DataFrame) -> DataFrame:
    return df.filter((F.col("amount") > 0) & F.col("customer_id").isNotNull())
```

---

## 2. The local SparkSession test fixture

Tests need a real (but tiny, local) SparkSession — `local[1]` (a single thread) is a common choice: fast to start, deterministic ordering is easier to reason about, and you're testing LOGIC correctness, not parallelism/performance (that's what your concept files on partitioning/skew/etc. are for).

With pytest, this is typically a SESSION-scoped fixture so the (relatively expensive) SparkSession is created once and reused across many test functions in the same test run, not per-test.

```python
# ---- conftest.py ----
import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    spark = (
        SparkSession.builder
        .master("local[1]")
        .appName("pytest-pyspark")
        .config("spark.sql.shuffle.partitions", "1")  # keep tests fast/simple
        .getOrCreate()
    )
    yield spark
    spark.stop()
```

---

## 3. Asserting DataFrame equality

Two ways to compare an actual DataFrame to an expected result:

1. **`pyspark.testing.assertDataFrameEqual`** (Spark 3.5+): purpose-built — compares schema and data, with options for row-order-insensitivity, floating-point tolerance, etc. Gives much better failure messages (a diff) than a raw assert.
2. **Manual `collect()` + sorted comparison** (works on any version): `.collect()` pulls all rows to the driver as a list of Row objects (fine for small test data, NEVER for real pipeline data at scale). Convert to a plain comparable structure (tuples/dicts) and SORT before comparing, because Spark does not guarantee row order unless you explicitly `orderBy` — comparing unsorted lists is a classic flaky-test bug.

```python
# ---- Spark 3.5+ : pyspark.testing ----
from pyspark.testing import assertDataFrameEqual

def test_add_tax(spark):
    input_df = spark.createDataFrame(
        [(1, 100.0), (2, 200.0)], ["id", "amount"]
    )
    expected_df = spark.createDataFrame(
        [(1, 100.0, 110.0), (2, 200.0, 220.0)], ["id", "amount", "total"]
    )
    result_df = add_tax(input_df, tax_rate=0.10)
    assertDataFrameEqual(result_df, expected_df)  # order-insensitive by default

# ---- Older Spark: manual collect + sorted comparison ----
def test_add_tax_manual(spark):
    input_df = spark.createDataFrame(
        [(1, 100.0), (2, 200.0)], ["id", "amount"]
    )
    result_df = add_tax(input_df, tax_rate=0.10)

    actual = sorted(result_df.collect(), key=lambda r: r["id"])
    expected = sorted(
        [(1, 100.0, 110.0), (2, 200.0, 220.0)], key=lambda r: r[0]
    )
    for row, exp in zip(actual, expected):
        assert row["id"] == exp[0]
        assert abs(row["total"] - exp[2]) < 1e-9   # float comparison: use tolerance
```

---

## 4. Why small pure functions beat a monolithic script

A common anti-pattern: one giant `main()` (or top-level module code) that reads input, does 15 transformation steps inline, and writes output — all in one block, with no function boundaries.

Problems this causes for testing/debugging:

- You can't test step 7's logic without also running steps 1-6 and having real (or realistically faked) input files on disk.
- A bug is hard to localize — you know "the final output is wrong" but not WHICH of 15 inline steps introduced it.
- Re-running to debug is slow (must re-read real data, run the whole pipeline) instead of instantiating a 3-row DataFrame and calling one function directly.

Small pure functions fix all of this: each one is independently testable with tiny hand-built input, each bug is localized to one function, and the orchestration layer (`main()`) becomes a thin, easy-to-read sequence of calls to already-tested functions.

```text
BAD (monolithic):                    GOOD (composed pure functions):
def main():                          def clean_nulls(df): ...
    df = spark.read...                 def add_tax(df, rate): ...
    df = df.filter(...)                def dedupe_orders(df): ...
    df = df.withColumn(...)            def join_customer_info(df, dim): ...
    df = df.join(...)
    df = df.groupBy(...)               def main():
    ... 10 more inline steps ...            df = read_source()
    df.write...                             df = clean_nulls(df)
                                             df = add_tax(df, 0.10)
Can't test step 5 in isolation             df = dedupe_orders(df)
without running 1-4 first and                df = join_customer_info(df, dim)
having real input data on disk.             write_sink(df)

                                      Each function testable alone with
                                      a 3-row DataFrame, no real files needed.
```

---

## 5. Common runtime errors and what they actually mean

**`java.lang.OutOfMemoryError: Java heap space`**
An executor JVM ran out of heap memory. Common causes: a partition is bigger than expected (skew, or too few partitions for the data size — see concepts 07 and 13), a broadcast join's "small" side turned out to be too large for executor memory, or a UDF/`collect()` pulling too much data into one place. Fix direction: repartition to shrink per-partition size, raise executor memory, lower/disable an inappropriate broadcast threshold, or check for a `collect()`/`toPandas()` on a large DataFrame.

**`org.apache.spark.shuffle.FetchFailedException`**
A REDUCE-side task failed to fetch shuffle data from a MAP-side executor — usually because that upstream executor died (often from its own OOM) or the node was lost (spot instance reclaimed, etc.) before the shuffle data could be read. Key debugging point: the error surfaces on the task that was FETCHING, but the root cause is almost always on the executor that PRODUCED the shuffle data and died. Look at that executor's logs (Spark UI -> Stages -> find the earlier failed/lost executor), not just the traceback shown for the fetching task.

**`Task not serializable`**
Spark ships your closure (lambda/UDF/function passed to `map`/`filter`/`foreach`/etc.) to executors by SERIALIZING it, along with anything it references from the enclosing scope. If that closure captures a non-serializable object — a raw JDBC/DB connection, a SparkSession/SparkContext itself, an open file handle, a non-picklable third-party client — serialization fails. Fix: don't reference the non-serializable object in the closure; instead create it INSIDE the closure/task (e.g. open the DB connection per-partition with `mapPartitions`), or mark it properly transient/lazy if using Scala, or restructure so the driver-only object never needs to cross to executors.

**`AnalysisException`**
A logical/semantic problem the query PLANNER caught before execution: referencing a column that doesn't exist, a table that isn't registered, an ambiguous column name after a join, a type that can't be cast as requested. Almost always means your assumed schema doesn't match reality — check upstream schema changes, typos in column names, or a join needing disambiguation (e.g. two DataFrames both having a column named "id").

| Error | What it actually means |
|---|---|
| `java.lang.OutOfMemoryError: Java heap space` | Executor ran out of heap — oversized partition, bad broadcast, or a collect()/UDF pulling too much data. |
| `org.apache.spark.shuffle.FetchFailedException` | A reduce task couldn't fetch shuffle data — the PRODUCING executor died/was lost. Check ITS logs, not the fetcher's. |
| `Task not serializable` | A closure captured a non-serializable object (DB connection, SparkSession) — create it inside the closure instead. |
| `AnalysisException` | Planner caught a schema/logical problem before running — missing column/table, ambiguous join column, bad cast. |

---

## 6. Where to actually look when a job fails

The driver's own traceback tells you the job/stage/task failed and often shows the LAST exception seen — but for distributed failures (`FetchFailedException`, executor lost, OOM on a specific executor), the real story is in the Spark UI and executor logs:

1. Spark UI -> Jobs tab: which job failed, how far did it get
2. Spark UI -> Stages tab: which STAGE failed, and the per-task breakdown — look for one task that's a huge outlier in duration/shuffle-read/shuffle-write (a skew signature) or the specific task/executor that actually errored
3. Click into the failed task -> "stderr" logs link for that specific executor — THIS is usually where the real underlying error lives (an OOM stack trace, a native error), not just the driver's summary
4. Stages tab's "Event Timeline" / task metrics (shuffle read/write size, spill to disk) to spot skew or memory-pressure patterns even when there's no hard failure yet, just slowness

```text
Driver traceback                Spark UI
-----------------                --------
"Job aborted due to              Jobs tab      -> which job, how far
 stage failure..."               Stages tab    -> which stage, per-task
 (often just the LAST                            metrics, outlier tasks
 symptom, not the                Task detail   -> the FAILED task's
 root cause)                                       executor's stderr log
                                                    <- root cause usually here
Rule of thumb: for a FetchFailedException or executor-lost error,
the interesting log is on the executor that DIED, not the one
reporting the failure.
```

---

## 7. A pytest-style test suite (plain assert, no pytest required)

A small "pytest-style" test suite for a simple transformation function, written with plain Python and `assert` statements so it runs without pytest installed — framed exactly like pytest test functions would be (`test_*` naming, one behavior per test) so the translation to real pytest is direct. The function under test here is a pure-Python stand-in for a PySpark transformation, operating on a list of dict "rows" instead of an actual DataFrame, so this runs with no dependencies.

```python
def add_tax(rows, tax_rate):
    """Pure function: list[dict] -> list[dict], adds a 'total' field."""
    return [dict(r, total=round(r["amount"] * (1 + tax_rate), 2)) for r in rows]

def filter_valid_orders(rows):
    """Keep only rows with positive amount and a non-null customer_id."""
    return [r for r in rows if r["amount"] > 0 and r.get("customer_id") is not None]

# -- Test functions --
def test_add_tax_basic():
    input_rows = [{"id": 1, "amount": 100.0}, {"id": 2, "amount": 200.0}]
    result = add_tax(input_rows, tax_rate=0.10)
    assert result[0]["total"] == 110.0
    assert result[1]["total"] == 220.0

def test_add_tax_zero_rate():
    input_rows = [{"id": 1, "amount": 50.0}]
    result = add_tax(input_rows, tax_rate=0.0)
    assert result[0]["total"] == 50.0

def test_filter_valid_orders_drops_negative_amount():
    input_rows = [
        {"id": 1, "amount": 100.0, "customer_id": "c1"},
        {"id": 2, "amount": -5.0, "customer_id": "c2"},
    ]
    result = filter_valid_orders(input_rows)
    assert len(result) == 1
    assert result[0]["id"] == 1

def test_filter_valid_orders_drops_null_customer():
    input_rows = [
        {"id": 1, "amount": 100.0, "customer_id": None},
        {"id": 2, "amount": 100.0, "customer_id": "c2"},
    ]
    result = filter_valid_orders(input_rows)
    assert len(result) == 1
    assert result[0]["id"] == 2

def test_filter_valid_orders_empty_input():
    assert filter_valid_orders([]) == []

tests = [
    test_add_tax_basic,
    test_add_tax_zero_rate,
    test_filter_valid_orders_drops_negative_amount,
    test_filter_valid_orders_drops_null_customer,
    test_filter_valid_orders_empty_input,
]

passed, failed = 0, 0
for test in tests:
    try:
        test()
        print(f"PASS  {test.__name__}")
        passed += 1
    except AssertionError as e:
        print(f"FAIL  {test.__name__}: {e}")
        failed += 1
```

**Output:**
```text
Running test suite...

  PASS  test_add_tax_basic
  PASS  test_add_tax_zero_rate
  PASS  test_filter_valid_orders_drops_negative_amount
  PASS  test_filter_valid_orders_drops_null_customer
  PASS  test_filter_valid_orders_empty_input

5 passed, 0 failed out of 5 tests
```

In real PySpark, replace the list[dict] inputs/function bodies with DataFrame construction (`spark.createDataFrame`) and DataFrame operations — the test STRUCTURE (small function, tiny input, assert on output) stays identical.

---

## Key Takeaways

- Write transformations as pure functions (DataFrame in, DataFrame out) — this is what makes PySpark logic actually unit-testable.
- Use a session-scoped `local[1]` SparkSession fixture in tests — fast, deterministic, meant for correctness not performance.
- Prefer `assertDataFrameEqual` (Spark 3.5+) for clear diffs; fall back to sorted `collect()` comparisons on older versions (row order is never guaranteed without `orderBy`).
- A monolithic pipeline script is nearly untestable in isolation; small composed functions localize bugs and enable fast tests.
- `OutOfMemoryError` = oversized partition/broadcast/collect; `FetchFailedException` = check the DYING executor's logs, not the fetcher's; `Task not serializable` = a closure captured something non-serializable; `AnalysisException` = schema/logical mismatch.
- When a job fails, use Spark UI Jobs -> Stages -> failed task's executor stderr log — the driver traceback alone is often not the root cause for distributed failures.
- A test suite is just small, focused assertions on known inputs/outputs — you don't need pytest installed to think this way.
