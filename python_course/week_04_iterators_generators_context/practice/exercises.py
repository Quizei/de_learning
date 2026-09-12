"""
Week 4 Practice Exercises: Iterators, Generators & Context Managers
====================================================================
Complete each exercise. Solutions are at the bottom.
"""

from typing import Iterator, List, Any, Generator
from contextlib import contextmanager
import itertools

# ================================
# EXERCISE 1: Custom Iterator
# ================================
"""
Create a `Fibonacci` iterator class that generates Fibonacci numbers
up to a maximum value.

Example:
    for n in Fibonacci(100):
        print(n)  # 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89
"""

class Fibonacci:
    def __init__(self , limit):
        self.a , self.b = 0 , 1
        self.limit = limit

    def __iter__(self):
        return self
    
    def __next__(self):
        value = self.a
        if self.limit <= self.a:
            raise StopIteration
            
        self.a , self.b = self.b , self.a+self.b
        return value



# ================================
# EXERCISE 2: Generator Function
# ================================
"""
Create a generator `read_csv_lazy(data)` that yields one row at a time
as a dictionary. Input is a list of strings (like lines from a file).
First line is the header.

Example:
    lines = [
        "name,age,city",
        "Alice,30,NYC",
        "Bob,25,LA"
    ]
    for row in read_csv_lazy(lines):
        print(row)  # {'name': 'Alice', 'age': '30', 'city': 'NYC'}
"""

def read_csv_lazy(lines: List[str]) -> Generator[dict, None, None]:
    headers = lines[0].split(",")
    for line in lines[1:]:
        values = line.split(",")
        yield dict(zip(headers, values))


# ================================
# EXERCISE 3: Generator with State
# ================================
"""
Create a generator `running_stats(numbers)` that yields a dict with
running statistics: count, sum, min, max, average.

Example:
    for stats in running_stats([5, 2, 8, 1, 9]):
        print(stats)
    # {'count': 1, 'sum': 5, 'min': 5, 'max': 5, 'avg': 5.0}
    # {'count': 2, 'sum': 7, 'min': 2, 'max': 5, 'avg': 3.5}
    # ...
"""

def running_stats(numbers):
    count = 0
    total = 0
    min_val = float('inf')
    max_val = float('-inf')

    for n in numbers:
        count += 1
        total += n
        min_val = min(min_val, n)
        max_val = max(max_val, n)

        yield {
            "count": count,
            "sum": total,
            "min": min_val,
            "max": max_val,
            "avg": total / count
        }


# ================================
# EXERCISE 4: Using itertools
# ================================
"""
Create a function `window_aggregate(data, window_size, agg_func)` that:
- Creates sliding windows of the given size
- Applies agg_func to each window
- Returns a generator of results

Example:
    data = [1, 2, 3, 4, 5]
    list(window_aggregate(data, 3, sum))  # [6, 9, 12]
    list(window_aggregate(data, 3, max))  # [3, 4, 5]
"""

def window_aggregate(data, window_size, agg_func):
    # Your code here
    pass


# ================================
# EXERCISE 5: Flattening Generator
# ================================
"""
Create a generator `deep_flatten(nested)` that flattens arbitrarily
nested iterables (except strings).

Example:
    nested = [1, [2, [3, 4]], [[5, 6], 7], 'abc']
    list(deep_flatten(nested))  # [1, 2, 3, 4, 5, 6, 7, 'abc']
"""

def window_aggregate(data , size , agg_fun):
    from collections import deque
    window = deque(maxlen=size)
    
    for i in data:
        window.append(i)
        if len(window) == size:
            yield agg_fun(window)


# ================================
# EXERCISE 6: Context Manager Class
# ================================
"""
Create a `DatabaseConnection` context manager class that:
- Prints "Connecting to {db_name}" on enter
- Returns the connection object
- Prints "Closing connection" on exit
- Prints "Rolling back due to error" if exception occurred
- Does NOT suppress exceptions

Example:
    with DatabaseConnection("mydb") as conn:
        conn.execute("SELECT * FROM users")
"""

class DatabaseConnection:
    def __init__(self , db_name):
        self.db_name = db_name
        self.connection = None

    def __enter__(self):
        print(f"Connecting to {self.db_name}")
        self.connection = connect(self.db_name)
        return self.connection
    
    def __exit__(self , exc_type , exc_val , exc_tb):
        try:
            if exc_type:
                print(f"Rolling back due to error: {exc_val}")
            else:
                self.connection.commit()
        finally:
            print("Closing connection")
            self.connection.close()

        return False



# ================================
# EXERCISE 7: Context Manager Decorator
# ================================
"""
Create a `@cached_property_context` decorator using @contextmanager that:
- Prints "Computing {name}"
- Times the computation
- Prints "Computed {name} in {time}s"

Example:
    with cached_property_context("expensive_value"):
        result = expensive_computation()
"""

@contextmanager
def cached_property_context(name):
    # Your code here
    pass


# ================================
# EXERCISE 8: Batch Iterator
# ================================
"""
Create a class `BatchIterator` that:
- Takes an iterable and batch_size
- Yields batches as lists
- Last batch may be smaller
- Is reusable (can iterate multiple times)

Example:
    batches = BatchIterator(range(10), 3)
    list(batches)  # [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    list(batches)  # [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]] (can reuse)
"""

class BatchIterator:
    def __init__(self, data, size):
        self.data = data
        self.size = size

    def __iter__(self):
        # This method is called every time you start a new loop
        result = []
        for i in self.data:
            result.append(i)
            if len(result) == self.size:
                yield result
                result = []
        if result:
            yield result


# ================================
# EXERCISE 9: Combining Generators
# ================================
"""
Create a function `merge_sorted(*iterables)` that merges multiple
sorted iterables into a single sorted iterator.

Example:
    a = [1, 4, 7]
    b = [2, 5, 8]
    c = [3, 6, 9]
    list(merge_sorted(a, b, c))  # [1, 2, 3, 4, 5, 6, 7, 8, 9]
"""

def merge_sorted(*iterables):
    import heapq
    iterators = [iter(it) for it in iterables]
    heap = []

    # Seed the heap with the first element from each iterator
    for i, it in enumerate(iterators):
        try:
            val = next(it)
            heapq.heappush(heap, (val, i, it))
        except StopIteration:
            pass

    while heap:
        val, i, it = heapq.heappop(heap)
        yield val
        try:
            next_val = next(it)
            heapq.heappush(heap, (next_val, i, it))
        except StopIteration:
            pass


# ================================
# EXERCISE 10: Resource Pool
# ================================
"""
Create a `ResourcePool` context manager that:
- Manages a pool of reusable resources
- Provides a resource on enter
- Returns it to pool on exit
- Creates new resources if pool is empty

Example:
    pool = ResourcePool(lambda: "new_connection", max_size=3)
    with pool.acquire() as resource:
        use(resource)
    # Resource returned to pool
"""

class ResourcePool:
    # Your code here
    pass


# ================================================================
# SOLUTIONS (Don't look until you've tried!)
# ================================================================
"""
Scroll down for solutions...



















"""

def show_solutions():
    print("=" * 50)
    print("SOLUTIONS")
    print("=" * 50)

    # Exercise 1
    print("\n--- Exercise 1: Fibonacci Iterator ---")

    class Fibonacci:
        def __init__(self, max_value):
            self.max_value = max_value

        def __iter__(self):
            a, b = 0, 1
            while a <= self.max_value:
                yield a
                a, b = b, a + b

    print(list(Fibonacci(100)))

    # Exercise 2
    print("\n--- Exercise 2: Lazy CSV Reader ---")

    def read_csv_lazy(lines):
        lines_iter = iter(lines)
        headers = next(lines_iter).split(',')
        for line in lines_iter:
            values = line.split(',')
            yield dict(zip(headers, values))

    csv_data = ["name,age,city", "Alice,30,NYC", "Bob,25,LA"]
    for row in read_csv_lazy(csv_data):
        print(row)

    # Exercise 3
    print("\n--- Exercise 3: Running Stats ---")

    def running_stats(numbers):
        count = 0
        total = 0
        min_val = float('inf')
        max_val = float('-inf')

        for num in numbers:
            count += 1
            total += num
            min_val = min(min_val, num)
            max_val = max(max_val, num)
            yield {
                'count': count,
                'sum': total,
                'min': min_val,
                'max': max_val,
                'avg': total / count
            }

    for stats in running_stats([5, 2, 8, 1, 9]):
        print(stats)

    # Exercise 4
    print("\n--- Exercise 4: Window Aggregate ---")

    def window_aggregate(data, window_size, agg_func):
        from collections import deque
        window = deque(maxlen=window_size)
        for item in data:
            window.append(item)
            if len(window) == window_size:
                yield agg_func(window)

    print("Sum:", list(window_aggregate([1, 2, 3, 4, 5], 3, sum)))
    print("Max:", list(window_aggregate([1, 2, 3, 4, 5], 3, max)))

    # Exercise 5
    print("\n--- Exercise 5: Deep Flatten ---")

    def deep_flatten(nested):
        for item in nested:
            if isinstance(item, (list, tuple)) and not isinstance(item, str):
                yield from deep_flatten(item)
            else:
                yield item

    nested = [1, [2, [3, 4]], [[5, 6], 7], 'abc']
    print(list(deep_flatten(nested)))

    # Exercise 6
    print("\n--- Exercise 6: Database Context Manager ---")

    class DatabaseConnection:
        def __init__(self, db_name):
            self.db_name = db_name

        def __enter__(self):
            print(f"Connecting to {self.db_name}")
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                print("Rolling back due to error")
            print("Closing connection")
            return False

        def execute(self, query):
            print(f"Executing: {query}")

    with DatabaseConnection("mydb") as conn:
        conn.execute("SELECT * FROM users")

    # Exercise 7
    print("\n--- Exercise 7: Cached Property Context ---")

    import time

    @contextmanager
    def cached_property_context(name):
        print(f"Computing {name}")
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            print(f"Computed {name} in {elapsed:.4f}s")

    with cached_property_context("expensive_value"):
        time.sleep(0.05)

    # Exercise 8
    print("\n--- Exercise 8: Batch Iterator ---")

    class BatchIterator:
        def __init__(self, iterable, batch_size):
            self.iterable = iterable
            self.batch_size = batch_size

        def __iter__(self):
            batch = []
            for item in self.iterable:
                batch.append(item)
                if len(batch) == self.batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch

    batches = BatchIterator(range(10), 3)
    print("First:", list(batches))
    print("Second:", list(batches))

    # Exercise 9
    print("\n--- Exercise 9: Merge Sorted ---")

    import heapq

    def merge_sorted(*iterables):
        return heapq.merge(*iterables)

    a, b, c = [1, 4, 7], [2, 5, 8], [3, 6, 9]
    print(list(merge_sorted(a, b, c)))

    # Exercise 10
    print("\n--- Exercise 10: Resource Pool ---")

    class ResourcePool:
        def __init__(self, factory, max_size=10):
            self.factory = factory
            self.max_size = max_size
            self.pool = []
            self.in_use = 0

        @contextmanager
        def acquire(self):
            if self.pool:
                resource = self.pool.pop()
                print(f"Reusing resource from pool")
            else:
                resource = self.factory()
                print(f"Created new resource")
            self.in_use += 1
            try:
                yield resource
            finally:
                self.in_use -= 1
                if len(self.pool) < self.max_size:
                    self.pool.append(resource)
                    print(f"Returned to pool (size: {len(self.pool)})")

    pool = ResourcePool(lambda: "connection", max_size=2)
    with pool.acquire() as r1:
        print(f"Using: {r1}")
    with pool.acquire() as r2:
        print(f"Using: {r2}")

    print("\n✅ All solutions demonstrated!")


if __name__ == "__main__":
    print("Complete the exercises above, then run show_solutions()")
    # Uncomment to see solutions:
    # show_solutions()
