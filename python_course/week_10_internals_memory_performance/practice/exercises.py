"""
Week 10 Practice Exercises: Internals & Performance
====================================================
"""

import sys
import time
import gc

def show_solutions():
    print("=== SOLUTIONS ===")

    # Exercise 1: Compare memory usage
    print("\n--- Memory Comparison ---")

    class Regular:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    class Slotted:
        __slots__ = ['x', 'y', 'z']
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    # Create many instances
    regular_list = [Regular(1, 2, 3) for _ in range(1000)]
    slotted_list = [Slotted(1, 2, 3) for _ in range(1000)]

    print(f"Regular object has __dict__: {hasattr(regular_list[0], '__dict__')}")
    print(f"Slotted object has __dict__: {hasattr(slotted_list[0], '__dict__')}")

    # Exercise 2: Profile function
    print("\n--- Profile Function ---")

    def profile(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            print(f"{func.__name__}: {(end-start)*1000:.2f}ms")
            return result
        return wrapper

    @profile
    def slow_sum(n):
        return sum(i*i for i in range(n))

    slow_sum(100000)

    # Exercise 3: Optimize code
    print("\n--- Code Optimization ---")

    # Slow version
    def slow_dedupe(items):
        result = []
        for item in items:
            if item not in result:
                result.append(item)
        return result

    # Fast version
    def fast_dedupe(items):
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    items = list(range(1000)) * 10  # 10000 items with duplicates

    start = time.perf_counter()
    slow_dedupe(items)
    slow_time = time.perf_counter() - start

    start = time.perf_counter()
    fast_dedupe(items)
    fast_time = time.perf_counter() - start

    print(f"Slow dedupe: {slow_time:.4f}s")
    print(f"Fast dedupe: {fast_time:.4f}s")
    print(f"Speedup: {slow_time/fast_time:.1f}x")

    # Exercise 4: Reference counting
    print("\n--- Reference Counting ---")

    class Tracked:
        instances = 0
        def __init__(self):
            Tracked.instances += 1
        def __del__(self):
            Tracked.instances -= 1

    obj1 = Tracked()
    obj2 = Tracked()
    print(f"Instances: {Tracked.instances}")
    del obj1
    gc.collect()
    print(f"After del: {Tracked.instances}")

    print("\n✅ All exercises demonstrated!")

if __name__ == "__main__":
    show_solutions()
