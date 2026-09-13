# Week 10 Project: Performance Optimizer

Profile and optimize a slow data processing script.

```python
import time
import cProfile
import pstats
from io import StringIO
from functools import lru_cache
from typing import List, Dict
```

## SLOW VERSION (TO OPTIMIZE)

```python
def slow_process_data(data: List[Dict]) -> Dict:
    """Slow, unoptimized version."""
    results = []

    for record in data:
        # Slow: repeated string concatenation
        name = ""
        for char in record.get("name", ""):
            name = name + char

        # Slow: list search instead of set
        if name not in results:
            results.append(name)

        # Slow: repeated calculation without caching
        score = calculate_score_slow(record.get("value", 0))

    return {
        "unique_names": len(results),
        "total_score": sum(calculate_score_slow(r.get("value", 0)) for r in data)
    }

def calculate_score_slow(value: int) -> int:
    """Slow calculation - no caching."""
    total = 0
    for i in range(value):
        total += i * i
    return total
```

## OPTIMIZED VERSION

```python
@lru_cache(maxsize=1000)
def calculate_score_fast(value: int) -> int:
    """Fast calculation with caching."""
    return sum(i * i for i in range(value))

def fast_process_data(data: List[Dict]) -> Dict:
    """Optimized version."""
    # Use set for O(1) lookup
    unique_names = set()

    for record in data:
        # Direct string access, no char-by-char concat
        name = record.get("name", "")
        unique_names.add(name)

    # Use cached calculation
    total_score = sum(
        calculate_score_fast(r.get("value", 0))
        for r in data
    )

    return {
        "unique_names": len(unique_names),
        "total_score": total_score
    }
```

## BENCHMARKING

```python
def benchmark(func, data, name: str):
    """Benchmark a function."""
    start = time.perf_counter()
    result = func(data)
    elapsed = time.perf_counter() - start
    print(f"{name}: {elapsed:.4f}s")
    return elapsed, result

def profile_function(func, data):
    """Profile with cProfile."""
    profiler = cProfile.Profile()
    profiler.enable()
    func(data)
    profiler.disable()

    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
    print(stream.getvalue())
```

## MAIN

```python
def main():
    print("=" * 60)
    print("PERFORMANCE OPTIMIZER")
    print("=" * 60)

    # Generate test data
    print("\nGenerating test data...")
    data = [
        {"name": f"user_{i % 100}", "value": i % 50}
        for i in range(5000)
    ]

    # Benchmark slow version
    print("\n--- Slow Version ---")
    slow_time, slow_result = benchmark(slow_process_data, data, "Slow")

    # Clear cache for fair comparison
    calculate_score_fast.cache_clear()

    # Benchmark fast version
    print("\n--- Fast Version ---")
    fast_time, fast_result = benchmark(fast_process_data, data, "Fast")

    # Speedup
    print(f"\n--- Results ---")
    print(f"Speedup: {slow_time / fast_time:.1f}x faster")
    print(f"Cache hits: {calculate_score_fast.cache_info().hits}")

    # Profile the slow version
    print("\n--- Profile Slow Version ---")
    profile_function(slow_process_data, data[:100])

    print("\n--- Optimization Tips Applied ---")
    print("""
    1. Used set instead of list for O(1) lookup
    2. Used @lru_cache for repeated calculations
    3. Avoided string concatenation in loop
    4. Used generator expressions
    """)

if __name__ == "__main__":
    main()
```
