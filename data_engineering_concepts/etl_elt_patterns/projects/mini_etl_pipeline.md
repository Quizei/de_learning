# Project: Mini ETL Pipeline

## Goal

Build a small, production-inspired ETL pipeline class that pulls this whole topic together: multi-source extraction, a real transform chain, idempotent staging-based loading, incremental watermark tracking, and full re-run safety. This is the capstone every concept file in this topic feeds into — if a design decision from `concepts/` or a bug from `interview_questions/03_critique_and_debug.md` doesn't show up as a concrete requirement below, that's worth noticing.

This brief describes the **interface and requirements** — the shape a strong solution takes, and the specific behaviors it must demonstrate — not a full worked solution. Write it yourself; use `concepts/` and `practice/` to check individual pieces as you go.

---

## Requirements

Your pipeline must:

1. **Extract from three different source shapes in one run:** a CSV string, a paginated mock API, and a source SQLite database — each independently, and each tracked with its **own** watermark, since one source updating shouldn't force a re-read of the others.
2. **Transform in a clear, ordered chain:** clean (trim strings, cast/validate types, drop unusably malformed rows) → deduplicate (by natural key, keeping the most complete/most recent record) → enrich (join in at least one reference dataset) → validate (route rule violations to an error/dead-letter table instead of loading them).
3. **Load idempotently via staging + merge:** stage the transformed batch, then merge into a target warehouse table keyed on a natural id, such that re-running the exact same input produces the exact same target state.
4. **Support incremental mode:** each source's watermark is read at the start of extraction and only written back after that source's data has been successfully merged into the target — not before.
5. **Be safe to re-run at any point:** re-running the whole pipeline with no new source data must load zero additional rows and leave the target table byte-for-byte unchanged. This is the single test that catches almost every idempotency bug in this whole topic — run it before you consider the project done.
6. **Log every step and expose run statistics:** counts extracted/transformed/loaded/errored per run, plus enough of a trail that "why does the target have 998 rows instead of 1000" is answerable from logs alone, not by re-running with print statements added.

## What a Strong Solution Demonstrates

- Multi-source extraction (`concepts/01_extraction_patterns.md`)
- A named, chained transform pipeline (`concepts/02_transformation_patterns.md`)
- Staging + merge loading (`concepts/03_loading_strategies.md`)
- Per-source incremental watermarks that only advance after a successful load (`concepts/04_incremental_vs_full.md`)
- A dead-letter table for records that fail validation, and — if you extend the project — a retry-with-backoff wrapper around the mock API's simulated transient failures (`concepts/06_idempotency_reliability.md`)
- A re-run of the full pipeline against unchanged sources producing zero new rows and zero changed rows in the target

## Starter Data (given — build against this, don't redesign it)

```python
CSV_SOURCE = """\
id,name,email,amount,region,created_at
101,  Alice Smith ,alice@example.com,250.50,East,2024-01-15T10:00:00
102,Bob Jones,bob@example.com,75.00,West,2024-01-16T11:30:00
103, Charlie Brown,charlie@example.com,1200.00,East,2024-01-17T09:15:00
104,Diana Prince,diana@example.com,340.00,North,2024-01-18T14:00:00
105,Eve Adams,,180.75,South,2024-01-19T16:45:00
106,Frank Castle,frank@example.com,NULL,East,2024-01-20T08:30:00
107,Alice Smith,alice@example.com,300.00,East,2024-01-21T10:00:00
"""
# Notice: row 105 has no email, row 106 has amount=NULL, and rows 101/107
# are the same real person (Alice Smith) under two different ids -- your
# transform chain has to decide what to do with all three on purpose,
# not by accident.

class MockAPISource:
    """Simulates a paginated REST API returning customer orders.
    Real APIs fail transiently sometimes -- consider making .fetch()
    randomly raise ConnectionError on ~15% of calls, and building your
    extraction to retry through it (concepts/01_extraction_patterns.md,
    concepts/06_idempotency_reliability.md)."""
    def __init__(self, seed=42):
        ...   # generate ~15 records, paginated 5 at a time

def create_sqlite_source():
    """A source SQLite database simulating an OLTP system, with a
    `transactions` table shaped like the CSV/API data above, including
    at least one repeated natural-key situation of its own."""
    ...

REGION_DETAILS = {
    "East": {"timezone": "EST", "manager": "R. East"},
    "West": {"timezone": "PST", "manager": "R. West"},
    "North": {"timezone": "CST", "manager": "R. North"},
    "South": {"timezone": "CST", "manager": "R. South"},
}   # your enrichment reference data

TIER_RULES = [(1000, "platinum"), (500, "gold"), (200, "silver"), (0, "bronze")]
```

## Interface to Implement

```python
class MiniETLPipeline:
    """
    A complete ETL pipeline: extracts from CSV/API/database sources,
    transforms (clean -> dedupe -> enrich -> validate), and loads into
    a SQLite warehouse via staging + merge. Incremental, idempotent,
    and fully re-runnable.
    """

    def __init__(self, warehouse_path=":memory:"):
        """Set up the warehouse schema: a target table, a staging table,
        an errors/dead-letter table, and a watermarks table -- one
        watermark row per source name, not one global watermark."""
        raise NotImplementedError

    # ----- EXTRACT -----

    def extract(self, csv_data=None, api_source=None, db_source=None):
        """
        Run extraction against whichever sources are provided.
        Each source's watermark is read independently and used to filter
        that source's data only -- one source having no new data must
        not block or skip another source that does.
        Returns the combined raw records; does not yet update any
        watermark (watermarks only advance after a successful LOAD).
        """
        raise NotImplementedError

    # ----- TRANSFORM -----

    def transform(self, raw_records):
        """
        Apply, in order: clean -> deduplicate -> enrich -> validate.
        Records failing validation are set aside (not raised, not
        silently dropped) for the load step to route into the errors
        table. Returns the list of records ready to load.
        """
        raise NotImplementedError

    # ----- LOAD -----

    def load(self, transformed_records, invalid_records):
        """
        Stage transformed_records, merge into the target table keyed
        on id (INSERT ... ON CONFLICT DO UPDATE), write invalid_records
        into the errors table, then advance each source's watermark --
        ONLY after the merge has committed successfully.
        """
        raise NotImplementedError

    # ----- RUN -----

    def run(self, csv_data=None, api_source=None, db_source=None):
        """Execute extract -> transform -> load as one run, and return
        a stats dict: {extracted, transformed, loaded, errors,
        duplicates_removed}."""
        raise NotImplementedError

    # ----- INSPECTION -----

    def show_target(self):
        """Print the current target table contents."""
        raise NotImplementedError

    def show_errors(self):
        """Print the dead-letter/errors table contents."""
        raise NotImplementedError

    def show_watermarks(self):
        """Print the current watermark per source."""
        raise NotImplementedError
```

## Demonstration Script to Run Against Your Own Implementation

Write a small `main()` that proves the requirements, not just exercises the happy path:

```python
pipeline = MiniETLPipeline()
api = MockAPISource(seed=42)
db_source = create_sqlite_source()

# Run 1: initial load from all three sources
stats1 = pipeline.run(csv_data=CSV_SOURCE, api_source=api, db_source=db_source)
pipeline.show_target()
pipeline.show_errors()
pipeline.show_watermarks()

# Run 2: re-run with the SAME sources, unchanged -- the idempotency test.
# Requirement 5 says this must load 0 new rows and leave the target
# byte-for-byte identical to after Run 1.
stats2 = pipeline.run(csv_data=CSV_SOURCE, api_source=api, db_source=db_source)
assert stats2["extracted"] == 0, "a truly incremental, idempotent pipeline should see nothing new here"

# Run 3: only the database source gets new rows.
# Requirement 1 says CSV and API watermarks being unaffected should mean
# this run extracts ONLY the new database rows, nothing re-extracted
# from CSV or API.
db_source.execute("INSERT INTO transactions VALUES (306, 'Leo Messi', 'leo@db.com', 1500.00, 'South', '2024-01-25T10:00:00')")
db_source.commit()
stats3 = pipeline.run(csv_data=CSV_SOURCE, api_source=api, db_source=db_source)
assert stats3["extracted"] == 1
```

## Stretch Goals

- Wrap the mock API's simulated transient failures in retry-with-backoff (`concepts/06_idempotency_reliability.md`, section 4), and confirm the pipeline still succeeds even when a handful of API calls fail before succeeding.
- Add a checkpoint table so a pipeline that crashes mid-run (simulate this by raising an exception partway through `load()`) resumes from where it left off on the next `run()` call, rather than restarting from `extract()`.
- Extend `create_sqlite_source()` to occasionally emit a hard delete, and add a reconciliation pass that detects and soft-deletes the corresponding target row — the pattern from `interview_questions/04_curveballs_tradeoffs.md`'s "source allows hard deletes, no CDC access" curveball.
- Add a schema-change detector (`practice/coding_problems.md`, Problem 3) that runs against the source schemas before extraction and raises a clear, actionable warning if a column this pipeline depends on has been removed or retyped.

## Grading Yourself

The one test that matters most: **run the pipeline twice in a row against unchanged sources.** If the target table, the row counts, and the watermarks are identical after both runs, the core idempotency requirement is met. If they aren't, that's the bug to chase down before anything else — re-read `concepts/06_idempotency_reliability.md` and `interview_questions/03_critique_and_debug.md`, Cases 1 and 2, for the two most common reasons this fails.
