"""
Profiling and Performance
=========================
Measuring and optimizing Python code.
"""

import time
import cProfile
import pstats
from io import StringIO

# ================================
# TIMING CODE
# ================================

print("--- Timing with time ---")

def slow_function():
    total = 0
    for i in range(100000):
        total += i * i
    return total

start = time.perf_counter()
result = slow_function()
end = time.perf_counter()
print(f"Execution time: {end - start:.4f} seconds")

# ================================
# TIMEIT MODULE
# ================================

print("\n--- timeit ---")

import timeit

# Time a simple expression
time_taken = timeit.timeit('sum(range(1000))', number=10000)
print(f"sum(range(1000)) x 10000: {time_taken:.4f}s")

# Compare approaches
list_comp_time = timeit.timeit('[x*2 for x in range(1000)]', number=1000)
map_time = timeit.timeit('list(map(lambda x: x*2, range(1000)))', number=1000)
print(f"List comprehension: {list_comp_time:.4f}s")
print(f"Map: {map_time:.4f}s")

# ================================
# CPROFILE
# ================================

print("\n--- cProfile ---")

def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def main_function():
    for i in range(20):
        fibonacci(i)

# Profile the function
profiler = cProfile.Profile()
profiler.enable()
main_function()
profiler.disable()

# Print stats
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(5)

# ================================
# OPTIMIZATION TIPS
# ================================

print("\n--- Optimization Tips ---")

# 1. Use built-in functions
print("1. Built-ins are faster:")
# Slow
def sum_manual(lst):
    total = 0
    for x in lst:
        total += x
    return total

# Fast
# sum(lst)

# 2. Use list comprehensions
print("2. List comprehensions vs loops:")
# Slow
result = []
for i in range(1000):
    result.append(i * 2)

# Fast
result = [i * 2 for i in range(1000)]

# 3. Use generators for large data
print("3. Generators for memory efficiency:")
# Memory heavy
squares = [x**2 for x in range(1000000)]
# Memory efficient
squares_gen = (x**2 for x in range(1000000))

# 4. Use local variables
print("4. Local variables are faster:")
def fast_function():
    local_range = range  # Cache global lookup
    return [local_range(10) for _ in range(100)]

# 5. Use sets for membership testing
print("5. Sets for O(1) lookup:")
# Slow: O(n)
# if item in list_of_items:
# Fast: O(1)
# if item in set_of_items:

# 6. String concatenation
print("6. Join for string concatenation:")
# Slow
result = ""
for s in ["a", "b", "c"]:
    result += s
# Fast
result = "".join(["a", "b", "c"])

# ================================
# PERFORMANCE DECORATOR
# ================================

print("\n--- Performance Decorator ---")

from functools import wraps

def profile(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__}: {end - start:.4f}s")
        return result
    return wrapper

@profile
def compute():
    return sum(i*i for i in range(10000))

compute()

print("\n✅ Profiling complete!")
