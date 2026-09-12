"""
Week 4 Project: Lazy Data Processor
====================================
A memory-efficient data processing library using generators and context managers.

This project applies:
- Custom iterators for data sources
- Generators for lazy evaluation
- Context managers for resource management
- itertools for data manipulation
"""

from typing import Iterator, Callable, Any, List, Dict, Optional
from contextlib import contextmanager
from dataclasses import dataclass
import itertools
import time


# ================================
# DATA RECORDS
# ================================

@dataclass
class ProcessingStats:
    """Statistics about data processing."""
    records_read: int = 0
    records_written: int = 0
    records_filtered: int = 0
    errors: int = 0
    duration_seconds: float = 0.0


# ================================
# LAZY DATA SOURCES
# ================================

class LazyDataSource:
    """Base class for lazy data sources."""

    def __iter__(self) -> Iterator[Dict]:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class MockDatabaseSource(LazyDataSource):
    """Simulates a database that yields records lazily."""

    def __init__(self, table_name: str, batch_size: int = 100):
        self.table_name = table_name
        self.batch_size = batch_size
        self._total_records = 500  # Simulated total

    def __iter__(self) -> Iterator[Dict]:
        print(f"[DB] Opening cursor for {self.table_name}")
        for batch_start in range(0, self._total_records, self.batch_size):
            # Simulate fetching a batch
            for i in range(batch_start, min(batch_start + self.batch_size, self._total_records)):
                yield {
                    "id": i,
                    "name": f"User_{i}",
                    "email": f"user{i}@example.com",
                    "score": (i * 17) % 100,  # Pseudo-random score
                    "active": i % 3 != 0
                }
        print(f"[DB] Closing cursor")


class CSVSource(LazyDataSource):
    """Simulates reading CSV file lazily."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        # Simulated CSV data
        self._data = [
            "id,product,price,quantity",
            "1,Widget,29.99,100",
            "2,Gadget,49.99,50",
            "3,Gizmo,19.99,200",
            "4,Doohickey,39.99,75",
            "5,Thingamajig,59.99,30",
        ]

    def __iter__(self) -> Iterator[Dict]:
        print(f"[CSV] Opening {self.filepath}")
        lines = iter(self._data)
        headers = next(lines).split(',')

        for line in lines:
            values = line.split(',')
            record = dict(zip(headers, values))
            # Type conversion
            record['id'] = int(record['id'])
            record['price'] = float(record['price'])
            record['quantity'] = int(record['quantity'])
            yield record

        print(f"[CSV] Closed {self.filepath}")


# ================================
# LAZY TRANSFORMATIONS
# ================================

def lazy_filter(predicate: Callable[[Dict], bool]):
    """Create a lazy filter transformation."""
    def transform(source: Iterator[Dict]) -> Iterator[Dict]:
        for record in source:
            if predicate(record):
                yield record
    return transform


def lazy_map(mapper: Callable[[Dict], Dict]):
    """Create a lazy map transformation."""
    def transform(source: Iterator[Dict]) -> Iterator[Dict]:
        for record in source:
            yield mapper(record)
    return transform


def lazy_batch(size: int):
    """Create a lazy batching transformation."""
    def transform(source: Iterator[Dict]) -> Iterator[List[Dict]]:
        batch = []
        for record in source:
            batch.append(record)
            if len(batch) >= size:
                yield batch
                batch = []
        if batch:
            yield batch
    return transform


def lazy_limit(n: int):
    """Create a lazy limit transformation."""
    def transform(source: Iterator[Dict]) -> Iterator[Dict]:
        for i, record in enumerate(source):
            if i >= n:
                break
            yield record
    return transform


def lazy_skip(n: int):
    """Create a lazy skip transformation."""
    def transform(source: Iterator[Dict]) -> Iterator[Dict]:
        for i, record in enumerate(source):
            if i >= n:
                yield record
    return transform


# ================================
# LAZY SINKS
# ================================

class LazySink:
    """Base class for data sinks."""

    def write(self, record: Dict) -> None:
        raise NotImplementedError

    def write_batch(self, records: List[Dict]) -> None:
        for record in records:
            self.write(record)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class ConsoleSink(LazySink):
    """Write records to console."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def write(self, record: Dict) -> None:
        print(f"{self.prefix}{record}")


class CollectorSink(LazySink):
    """Collect records into a list."""

    def __init__(self):
        self.records: List[Dict] = []

    def write(self, record: Dict) -> None:
        self.records.append(record)


# ================================
# PIPELINE BUILDER
# ================================

class LazyPipeline:
    """Fluent interface for building lazy data pipelines."""

    def __init__(self, source: Iterator[Dict]):
        self._source = source
        self._transforms: List[Callable] = []
        self._stats = ProcessingStats()

    @classmethod
    def from_source(cls, source: LazyDataSource) -> 'LazyPipeline':
        """Create pipeline from a data source."""
        return cls(iter(source))

    def filter(self, predicate: Callable[[Dict], bool]) -> 'LazyPipeline':
        """Add a filter transformation."""
        self._transforms.append(lazy_filter(predicate))
        return self

    def map(self, mapper: Callable[[Dict], Dict]) -> 'LazyPipeline':
        """Add a map transformation."""
        self._transforms.append(lazy_map(mapper))
        return self

    def limit(self, n: int) -> 'LazyPipeline':
        """Limit to first n records."""
        self._transforms.append(lazy_limit(n))
        return self

    def skip(self, n: int) -> 'LazyPipeline':
        """Skip first n records."""
        self._transforms.append(lazy_skip(n))
        return self

    def batch(self, size: int) -> 'LazyPipeline':
        """Batch records together."""
        self._transforms.append(lazy_batch(size))
        return self

    def _build_iterator(self) -> Iterator:
        """Build the complete iterator chain."""
        result = self._source
        for transform in self._transforms:
            result = transform(result)
        return result

    def collect(self) -> List[Dict]:
        """Execute pipeline and collect all results."""
        return list(self._build_iterator())

    def foreach(self, action: Callable[[Dict], None]) -> ProcessingStats:
        """Execute pipeline and apply action to each record."""
        start_time = time.perf_counter()

        for record in self._build_iterator():
            try:
                action(record)
                self._stats.records_written += 1
            except Exception as e:
                self._stats.errors += 1

        self._stats.duration_seconds = time.perf_counter() - start_time
        return self._stats

    def to_sink(self, sink: LazySink) -> ProcessingStats:
        """Execute pipeline and write to sink."""
        return self.foreach(sink.write)

    def count(self) -> int:
        """Count records (consumes the pipeline)."""
        return sum(1 for _ in self._build_iterator())

    def first(self, default=None):
        """Get first record or default."""
        return next(iter(self._build_iterator()), default)

    def take(self, n: int) -> List:
        """Take first n records."""
        return list(itertools.islice(self._build_iterator(), n))


# ================================
# CONTEXT MANAGERS
# ================================

@contextmanager
def processing_context(name: str):
    """Context manager for tracking processing."""
    print(f"\n{'='*50}")
    print(f"Starting: {name}")
    print('='*50)

    stats = ProcessingStats()
    start_time = time.perf_counter()

    try:
        yield stats
    finally:
        stats.duration_seconds = time.perf_counter() - start_time
        print(f"\n--- Processing Complete ---")
        print(f"Duration: {stats.duration_seconds:.3f}s")
        print(f"Records: {stats.records_written}")
        print(f"Errors: {stats.errors}")


@contextmanager
def source_context(source: LazyDataSource):
    """Context manager for data sources."""
    print(f"[SOURCE] Opening {type(source).__name__}")
    try:
        yield source
    finally:
        print(f"[SOURCE] Closed {type(source).__name__}")


# ================================
# AGGREGATORS
# ================================

def lazy_aggregate(source: Iterator[Dict], key_func: Callable, value_func: Callable, agg_func: Callable):
    """Lazy aggregation using groupby (requires sorted input)."""
    for key, group in itertools.groupby(source, key=key_func):
        values = [value_func(record) for record in group]
        yield {"key": key, "result": agg_func(values)}


def running_aggregator(agg_func: Callable):
    """Create a running aggregator generator."""
    def aggregate(source: Iterator[Dict], value_func: Callable):
        values = []
        for record in source:
            values.append(value_func(record))
            yield {**record, "_running_agg": agg_func(values)}
    return aggregate


# ================================
# DEMO
# ================================

def main():
    """Demonstrate the lazy data processor."""

    print("=" * 60)
    print("LAZY DATA PROCESSOR")
    print("=" * 60)

    # Example 1: Basic Pipeline
    print("\n--- Example 1: Basic Pipeline ---")

    with source_context(MockDatabaseSource("users")) as source:
        results = (LazyPipeline.from_source(source)
            .filter(lambda r: r['active'])
            .filter(lambda r: r['score'] > 50)
            .map(lambda r: {
                'id': r['id'],
                'name': r['name'],
                'score': r['score']
            })
            .limit(5)
            .collect())

        print("High-scoring active users:")
        for r in results:
            print(f"  {r}")

    # Example 2: Processing with Stats
    print("\n--- Example 2: Processing with Stats ---")

    with processing_context("User Export") as stats:
        source = MockDatabaseSource("users", batch_size=50)
        sink = CollectorSink()

        (LazyPipeline.from_source(source)
            .filter(lambda r: r['score'] >= 70)
            .map(lambda r: {'name': r['name'], 'email': r['email']})
            .limit(10)
            .to_sink(sink))

        stats.records_written = len(sink.records)
        print(f"Exported {len(sink.records)} users")

    # Example 3: CSV Processing
    print("\n--- Example 3: CSV Processing ---")

    with source_context(CSVSource("products.csv")) as source:
        total_value = 0

        for record in LazyPipeline.from_source(source)._build_iterator():
            value = record['price'] * record['quantity']
            total_value += value
            print(f"  {record['product']}: ${value:.2f}")

        print(f"Total inventory value: ${total_value:.2f}")

    # Example 4: Batched Processing
    print("\n--- Example 4: Batched Processing ---")

    source = MockDatabaseSource("users", batch_size=100)

    pipeline = LazyPipeline.from_source(source)
    iterator = pipeline.filter(lambda r: r['active']).limit(10)._build_iterator()

    batch_transform = lazy_batch(3)
    for batch in batch_transform(iterator):
        print(f"Processing batch of {len(batch)} records")
        for record in batch:
            print(f"    {record['name']}")

    # Example 5: Chained Transformations
    print("\n--- Example 5: Chained Transformations ---")

    source = MockDatabaseSource("users")

    result = (LazyPipeline.from_source(source)
        .skip(10)
        .filter(lambda r: r['active'])
        .map(lambda r: {**r, 'score_doubled': r['score'] * 2})
        .filter(lambda r: r['score_doubled'] > 100)
        .limit(3)
        .collect())

    print("Transformed records:")
    for r in result:
        print(f"  {r['name']}: score={r['score']}, doubled={r['score_doubled']}")

    # Example 6: Memory Efficiency Demo
    print("\n--- Example 6: Memory Efficiency ---")

    import sys

    # This would be memory-efficient even with millions of records
    source = MockDatabaseSource("huge_table")

    # The pipeline is just a description - no data loaded yet
    pipeline = (LazyPipeline.from_source(source)
        .filter(lambda r: r['score'] > 90)
        .map(lambda r: {'id': r['id']}))

    print(f"Pipeline object size: {sys.getsizeof(pipeline)} bytes")
    print("(Data is only loaded as needed during iteration)")

    # Only loads one record at a time
    first = pipeline.first()
    print(f"First high scorer: {first}")


if __name__ == "__main__":
    main()
