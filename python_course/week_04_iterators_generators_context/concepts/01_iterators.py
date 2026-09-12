"""
Iterators in Python
===================
Iterator protocol: __iter__() and __next__()
"""

# ================================
# ITERABLES VS ITERATORS
# ================================

# Iterable: object that can return an iterator (has __iter__)
# Iterator: object that produces values one at a time (has __iter__ and __next__)

my_list = [1, 2, 3]  # Iterable
my_iter = iter(my_list)  # Iterator

print("--- Iterable vs Iterator ---")
print(f"List has __iter__: {hasattr(my_list, '__iter__')}")
print(f"Iterator has __next__: {hasattr(my_iter, '__next__')}")

# Get values from iterator
print(next(my_iter))  # 1
print(next(my_iter))  # 2
print(next(my_iter))  # 3
# print(next(my_iter))  # StopIteration!        

                    # ================================
# HOW FOR LOOPS WORK
# ================================

# This:
for item in [1, 2, 3]:
    print(item)

# Is equivalent to:
iterator = iter([1, 2, 3])
while True:
    try:
        item = next(iterator)
        print(item)
    except StopIteration:
        break


# ================================
# CUSTOM ITERATOR
# ================================

class CountDown:
    """Iterator that counts down from n to 1."""

    def __init__(self, start):
        self.current = start

    def __iter__(self):
        """Return self - iterator is its own iterable."""
        return self

    def __next__(self):
        """Return next value or raise StopIteration."""
        if self.current <= 0:
            raise StopIteration
        value = self.current
        self.current -= 1
        return value


print("\n--- Custom Iterator: CountDown ---")
for num in CountDown(5):
    print(num, end=" ")
print()


# ================================
# SEPARATE ITERABLE AND ITERATOR
# ================================

class Range:
    """Custom range implementation with separate iterator."""

    def __init__(self, start, stop, step=1):
        self.start = start
        self.stop = stop
        self.step = step

    def __iter__(self):
        """Return a new iterator each time."""
        return RangeIterator(self.start, self.stop, self.step)


class RangeIterator:
    """Iterator for Range."""

    def __init__(self, start, stop, step):
        self.current = start
        self.stop = stop
        self.step = step

    def __iter__(self):
        return self

    def __next__(self):
        if self.current >= self.stop:
            raise StopIteration
        value = self.current
        self.current += self.step
        return value


print("\n--- Separate Iterable/Iterator ---")
my_range = Range(0, 10, 2)

# Can iterate multiple times
print("First iteration:", list(my_range))
print("Second iteration:", list(my_range))


# ================================
# INFINITE ITERATOR
# ================================

class InfiniteCounter:
    """Iterator that counts forever."""

    def __init__(self, start=0):
        self.current = start

    def __iter__(self):
        return self

    def __next__(self):
        value = self.current
        self.current += 1
        return value


print("\n--- Infinite Iterator ---")
counter = InfiniteCounter()
print("First 5:", [next(counter) for _ in range(5)])
print("Next 5:", [next(counter) for _ in range(5)])


# ================================
# ITERATOR WITH SENTINEL
# ================================

# iter() can take a callable and sentinel value
import random

def roll_dice():
    return random.randint(1, 6)

print("\n--- Iterator with Sentinel ---")
print("Rolling until 6:")
rolls = list(iter(roll_dice, 6))  # Stop when 6 is rolled
print(f"Rolls before 6: {rolls}")


# ================================
# PRACTICAL EXAMPLE: PAGINATED API
# ================================

class PaginatedResults:
    """Iterator for paginated API results."""

    def __init__(self, fetch_func, page_size=10):
        self.fetch_func = fetch_func
        self.page_size = page_size
        self.current_page = 0
        self.buffer = []
        self.exhausted = False

    def __iter__(self):
        return self

    def __next__(self):
        # Refill buffer if empty
        if not self.buffer and not self.exhausted:
            self.buffer = self.fetch_func(self.current_page, self.page_size)
            self.current_page += 1
            if len(self.buffer) < self.page_size:
                self.exhausted = True

        if not self.buffer:
            raise StopIteration

        return self.buffer.pop(0)


# Simulate API
def mock_api(page, size):
    """Simulate paginated API - 25 total items."""
    total_items = 25
    start = page * size
    if start >= total_items:
        return []
    end = min(start + size, total_items)
    return [f"item_{i}" for i in range(start, end)]


print("\n--- Paginated API Iterator ---")
results = PaginatedResults(mock_api, page_size=10)
all_items = list(results)
print(f"Total items: {len(all_items)}")
print(f"First 3: {all_items[:3]}")
print(f"Last 3: {all_items[-3:]}")


# ================================
# FILE ITERATOR (LINES)
# ================================

class FileLines:
    """Iterate over lines in a file."""

    def __init__(self, filepath):
        self.filepath = filepath

    def __iter__(self):
        with open(self.filepath) as f:
            for line in f:
                yield line.strip()


# ================================
# DATA CHUNKER
# ================================

class DataChunker:
    """Iterate over data in chunks."""

    def __init__(self, data, chunk_size):
        self.data = data
        self.chunk_size = chunk_size

    def __iter__(self):
        for i in range(0, len(self.data), self.chunk_size):
            yield self.data[i:i + self.chunk_size]


print("\n--- Data Chunker ---")
data = list(range(10))
for chunk in DataChunker(data, 3):
    print(f"Chunk: {chunk}")


# ================================
# SUMMARY
# ================================

print("\n--- Iterator Protocol Summary ---")
print("""
Iterable:
  - Has __iter__() method
  - Returns an iterator
  - Can be used in for loops

Iterator:
  - Has __iter__() and __next__() methods
  - __iter__() returns self
  - __next__() returns next value or raises StopIteration
  - Maintains iteration state

Benefits:
  - Memory efficient (lazy evaluation)
  - Can represent infinite sequences
  - Clean interface for iteration
  - Works with for loops, list(), sum(), etc.
""")
