# Generators in Python

Functions that use yield to produce a sequence of values lazily.

## BASIC GENERATOR

```python
def count_up_to(n):
    """Generator that counts from 1 to n."""
    i = 1
    while i <= n:
        yield i  # Pause and return value
        i += 1


print("--- Basic Generator ---")
gen = count_up_to(5)
print(f"Type: {type(gen)}")  # <class 'generator'>

# Get values one at a time
print(next(gen))  # 1
print(next(gen))  # 2

# Or use in for loop
print("Rest:", list(gen))  # [3, 4, 5]
```

## GENERATOR VS LIST

```python
import sys

def squares_list(n):
    """Return list of squares."""
    return [x**2 for x in range(n)]

def squares_gen(n):
    """Generate squares lazily."""
    for x in range(n):
        yield x**2


print("\n--- Memory Comparison ---")
list_result = squares_list(1000)
gen_result = squares_gen(1000)

print(f"List size: {sys.getsizeof(list_result):,} bytes")
print(f"Generator size: {sys.getsizeof(gen_result)} bytes")
```

## GENERATOR EXECUTION

```python
def demo_execution():
    """Demonstrate generator execution flow."""
    print("  Starting generator")
    yield 1
    print("  After first yield")
    yield 2
    print("  After second yield")
    yield 3
    print("  Generator exhausted")


print("\n--- Execution Flow ---")
gen = demo_execution()
print("Created generator (nothing printed yet)")
print(f"First value: {next(gen)}")
print(f"Second value: {next(gen)}")
print(f"Third value: {next(gen)}")
```

## GENERATOR EXPRESSIONS

```python
# Generator expression - like list comprehension but lazy
gen_exp = (x**2 for x in range(10))

print("\n--- Generator Expression ---")
print(f"Type: {type(gen_exp)}")
print(f"Sum: {sum(gen_exp)}")

# Compare with list comprehension
list_comp = [x**2 for x in range(10)]
gen_exp = (x**2 for x in range(10))

print(f"List comp size: {sys.getsizeof(list_comp)} bytes")
print(f"Gen exp size: {sys.getsizeof(gen_exp)} bytes")
```

## YIELD FROM

```python
def nested_generator():
    """Traditional way to yield from another iterable."""
    for i in range(3):
        yield i
    for i in range(3, 6):
        yield i

def nested_generator_v2():
    """Using yield from."""
    yield from range(3)
    yield from range(3, 6)


print("\n--- yield from ---")
print("Traditional:", list(nested_generator()))
print("yield from:", list(nested_generator_v2()))


# Flatten nested lists
def flatten(nested):
    """Flatten arbitrarily nested lists."""
    for item in nested:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item


nested = [1, [2, 3, [4, 5]], 6, [7, [8, 9]]]
print(f"Flattened: {list(flatten(nested))}")
```

## GENERATOR METHODS

```python
def accumulator():
    """Generator that can receive values."""
    total = 0
    while True:
        value = yield total
        if value is not None:
            total += value


print("\n--- Generator Methods ---")
acc = accumulator()
print(f"Initial: {next(acc)}")       # Start generator, get 0
print(f"Send 10: {acc.send(10)}")    # Send 10, get 10
print(f"Send 20: {acc.send(20)}")    # Send 20, get 30
print(f"Send 5: {acc.send(5)}")      # Send 5, get 35


# Generator with close and throw
def closeable_gen():
    """Generator that handles close."""
    try:
        while True:
            yield "value"
    except GeneratorExit:
        print("  Generator was closed")


gen = closeable_gen()
print(f"\nGet value: {next(gen)}")
gen.close()  # Triggers GeneratorExit
```

## PRACTICAL EXAMPLES

```python
# 1. Read large file in chunks
def read_in_chunks(filepath, chunk_size=1024):
    """Read file in chunks to save memory."""
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


# 2. Infinite sequence
def fibonacci():
    """Generate Fibonacci sequence infinitely."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


print("\n--- Fibonacci Generator ---")
fib = fibonacci()
print("First 10:", [next(fib) for _ in range(10)])


# 3. Batch processing
def batch_processor(items, batch_size):
    """Process items in batches."""
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:  # Don't forget the last partial batch
        yield batch


print("\n--- Batch Processor ---")
items = range(10)
for batch in batch_processor(items, 3):
    print(f"Processing batch: {batch}")


# 4. Pipeline of generators
def read_data():
    """Simulate reading data."""
    for i in range(5):
        yield {"id": i, "value": i * 10}

def filter_data(data):
    """Filter records."""
    for record in data:
        if record["value"] > 15:
            yield record

def transform_data(data):
    """Transform records."""
    for record in data:
        yield {**record, "processed": True}


print("\n--- Generator Pipeline ---")
pipeline = transform_data(filter_data(read_data()))
for record in pipeline:
    print(record)


# 5. Sliding window
def sliding_window(iterable, size):
    """Generate sliding windows."""
    from collections import deque
    window = deque(maxlen=size)

    for item in iterable:
        window.append(item)
        if len(window) == size:
            yield tuple(window)


print("\n--- Sliding Window ---")
data = [1, 2, 3, 4, 5, 6]
for window in sliding_window(data, 3):
    print(f"Window: {window}")
```

## GENERATOR VS ITERATOR CLASS

```python
print("\n--- When to Use Each ---")
print("""
Use Generator (function with yield):
  + Simpler syntax
  + Less boilerplate
  + Good for simple sequences
  Best for: Most cases

Use Iterator Class:
  + More control over state
  + Can have multiple methods
  + Can be reset
  Best for: Complex iteration logic, reusable iterators
""")
```
