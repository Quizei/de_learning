"""
itertools Module
================
Efficient iterators for looping and combining data.
"""

import itertools
from itertools import (
    count, cycle, repeat,
    chain, islice, compress, filterfalse,
    accumulate, starmap, takewhile, dropwhile,
    groupby, zip_longest,
    product, permutations, combinations, combinations_with_replacement
)

# ================================
# INFINITE ITERATORS
# ================================

print("--- Infinite Iterators ---")

# count(start, step) - count from start by step
counter = count(10, 2)
print("count(10, 2):", [next(counter) for _ in range(5)])  # [10, 12, 14, 16, 18]

# cycle(iterable) - cycle through iterable forever
cycler = cycle(['A', 'B', 'C'])
print("cycle(['A','B','C']):", [next(cycler) for _ in range(7)])

# repeat(elem, n) - repeat element n times
print("repeat('X', 3):", list(repeat('X', 3)))


# ================================
# ITERATORS FOR COMBINING
# ================================

print("\n--- Combining Iterators ---")

# chain(*iterables) - chain iterables together
list1 = [1, 2, 3]
list2 = [4, 5, 6]
list3 = [7, 8, 9]
print("chain:", list(chain(list1, list2, list3)))

# chain.from_iterable - flatten one level
nested = [[1, 2], [3, 4], [5, 6]]
print("chain.from_iterable:", list(chain.from_iterable(nested)))

# zip_longest - zip with fill value for shorter iterables
a = [1, 2, 3]
b = ['a', 'b']
print("zip_longest:", list(zip_longest(a, b, fillvalue='?')))


# ================================
# SLICING ITERATORS
# ================================

print("\n--- Slicing Iterators ---")

# islice(iterable, stop) or islice(iterable, start, stop, step)
data = range(100)
print("islice(range(100), 5):", list(islice(data, 5)))
print("islice(range(100), 10, 20, 2):", list(islice(data, 10, 20, 2)))

# Works with any iterator, even infinite ones
print("islice(count(), 5, 10):", list(islice(count(), 5, 10)))


# ================================
# FILTERING ITERATORS
# ================================

print("\n--- Filtering Iterators ---")

# compress(data, selectors) - filter by selector booleans
data = ['A', 'B', 'C', 'D', 'E']
selectors = [True, False, True, False, True]
print("compress:", list(compress(data, selectors)))  # ['A', 'C', 'E']

# filterfalse(predicate, iterable) - opposite of filter
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
print("filterfalse (odd):", list(filterfalse(lambda x: x % 2, numbers)))

# takewhile(predicate, iterable) - take while condition is true
print("takewhile (<5):", list(takewhile(lambda x: x < 5, numbers)))

# dropwhile(predicate, iterable) - drop while condition is true
print("dropwhile (<5):", list(dropwhile(lambda x: x < 5, numbers)))


# ================================
# ACCUMULATING ITERATORS
# ================================

print("\n--- Accumulating Iterators ---")

# accumulate(iterable, func) - running totals
numbers = [1, 2, 3, 4, 5]
print("accumulate (sum):", list(accumulate(numbers)))
print("accumulate (product):", list(accumulate(numbers, lambda x, y: x * y)))

# With operator module
import operator
print("accumulate (max):", list(accumulate([3, 1, 4, 1, 5, 9], max)))

# starmap(func, iterable) - apply func to unpacked tuples
pairs = [(2, 3), (4, 5), (6, 7)]
print("starmap (pow):", list(starmap(pow, pairs)))  # [8, 1024, 279936]


# ================================
# GROUPING
# ================================

print("\n--- Grouping ---")

# groupby(iterable, key) - group consecutive elements
# IMPORTANT: Data must be sorted by key first!

data = [
    {'name': 'Alice', 'dept': 'Engineering'},
    {'name': 'Bob', 'dept': 'Engineering'},
    {'name': 'Charlie', 'dept': 'Marketing'},
    {'name': 'Diana', 'dept': 'Marketing'},
    {'name': 'Eve', 'dept': 'Engineering'},
]

# Sort first!
data.sort(key=lambda x: x['dept'])

for dept, group in groupby(data, key=lambda x: x['dept']):
    print(f"  {dept}: {[p['name'] for p in group]}")


# ================================
# COMBINATORICS
# ================================

print("\n--- Combinatorics ---")

# product - cartesian product
print("product([1,2], ['a','b']):", list(product([1, 2], ['a', 'b'])))
print("product('AB', repeat=2):", list(product('AB', repeat=2)))

# permutations - all orderings
print("permutations('ABC', 2):", list(permutations('ABC', 2)))

# combinations - unordered selections (no replacement)
print("combinations('ABCD', 2):", list(combinations('ABCD', 2)))

# combinations_with_replacement - unordered with replacement
print("combinations_with_replacement('AB', 2):",
      list(combinations_with_replacement('AB', 2)))


# ================================
# PRACTICAL EXAMPLES
# ================================

print("\n--- Practical Examples ---")

# 1. Enumerate with custom start using zip and count
items = ['apple', 'banana', 'cherry']
for i, item in zip(count(1), items):
    print(f"  {i}. {item}")

# 2. Pairwise iteration (Python 3.10+ has itertools.pairwise)
def pairwise(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)

print("\nPairwise:")
for a, b in pairwise([1, 2, 3, 4, 5]):
    print(f"  {a} -> {b}")

# 3. Round-robin scheduling
def roundrobin(*iterables):
    """Round-robin iteration."""
    iterators = [iter(it) for it in iterables]
    while iterators:
        for i, it in enumerate(list(iterators)):
            try:
                yield next(it)
            except StopIteration:
                iterators.remove(it)

print("\nRound-robin:")
print(list(roundrobin([1, 2, 3], ['a', 'b'], [100, 200, 300, 400])))

# 4. Unique elements preserving order
def unique_everseen(iterable):
    """Unique elements, preserving order."""
    seen = set()
    for element in iterable:
        if element not in seen:
            seen.add(element)
            yield element

print("\nUnique everseen:")
print(list(unique_everseen([1, 2, 1, 3, 2, 4, 1, 5])))

# 5. Chunking with islice
def chunked(iterable, size):
    """Chunk iterable into fixed-size pieces."""
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk

print("\nChunked:")
for chunk in chunked(range(10), 3):
    print(f"  {chunk}")

# 6. Running average
def running_average(iterable):
    """Calculate running average."""
    for count, total in enumerate(accumulate(iterable), 1):
        yield total / count

print("\nRunning average:")
print(list(running_average([1, 3, 5, 7, 9])))


# ================================
# ITERTOOLS RECIPES
# ================================

print("\n--- Common Recipes ---")

# Take first n items
def take(n, iterable):
    return list(islice(iterable, n))

# Drop first n items
def drop(n, iterable):
    return islice(iterable, n, None)

# Prepend value to iterator
def prepend(value, iterable):
    return chain([value], iterable)

# nth item (default if not found)
def nth(iterable, n, default=None):
    return next(islice(iterable, n, None), default)

# Consume iterator entirely
def consume(iterable):
    from collections import deque
    deque(iterable, maxlen=0)

# All equal check
def all_equal(iterable):
    g = groupby(iterable)
    return next(g, True) and not next(g, False)

print(f"take(3, range(10)): {take(3, range(10))}")
print(f"nth(range(10), 5): {nth(range(10), 5)}")
print(f"all_equal([1, 1, 1]): {all_equal([1, 1, 1])}")
print(f"all_equal([1, 1, 2]): {all_equal([1, 1, 2])}")
