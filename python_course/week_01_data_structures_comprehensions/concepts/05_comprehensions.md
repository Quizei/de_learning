# Comprehensions: List, Dict, Set, and Generator Expressions

Comprehensions are concise ways to create collections from iterables.
More readable and often faster than equivalent loops.

## LIST COMPREHENSIONS

```python
# Basic syntax: [expression for item in iterable]
squares = [x**2 for x in range(10)]
print("Squares:", squares)

# With condition: [expression for item in iterable if condition]
even_squares = [x**2 for x in range(10) if x % 2 == 0]
print("Even squares:", even_squares)

# With if-else (note: expression position changes)
labels = ["even" if x % 2 == 0 else "odd" for x in range(5)]
print("Labels:", labels)

# Nested loops
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
flattened = [num for row in matrix for num in row]
print("Flattened:", flattened)

# Creating a matrix
matrix_3x3 = [[i + j*3 for i in range(1, 4)] for j in range(3)]
print("Matrix:", matrix_3x3)

# Multiple conditions
filtered = [x for x in range(50) if x % 2 == 0 if x % 3 == 0]
print("Divisible by 2 AND 3:", filtered)
```

## DICT COMPREHENSIONS

```python
# Basic syntax: {key_expr: value_expr for item in iterable}
square_dict = {x: x**2 for x in range(1, 6)}
print("\nSquare dict:", square_dict)

# Swapping keys and values
original = {'a': 1, 'b': 2, 'c': 3}
swapped = {v: k for k, v in original.items()}
print("Swapped:", swapped)

# Filtering dict
scores = {'alice': 85, 'bob': 72, 'charlie': 90, 'diana': 68}
passed = {name: score for name, score in scores.items() if score >= 75}
print("Passed:", passed)

# From two lists
keys = ['name', 'age', 'city']
values = ['Alice', 30, 'NYC']
combined = {k: v for k, v in zip(keys, values)}
print("Combined:", combined)

# Nested dict comprehension
users_data = {
    'alice': [10, 20, 30],
    'bob': [5, 15, 25],
}
user_sums = {user: sum(scores) for user, scores in users_data.items()}
print("User sums:", user_sums)
```

## SET COMPREHENSIONS

```python
# Basic syntax: {expression for item in iterable}
unique_lengths = {len(word) for word in ['hello', 'world', 'python', 'code']}
print("\nUnique lengths:", unique_lengths)

# Remove duplicates with transformation
words = ['Hello', 'WORLD', 'hello', 'Python']
unique_lower = {word.lower() for word in words}
print("Unique lowercase:", unique_lower)
```

## GENERATOR EXPRESSIONS

```python
# Syntax: (expression for item in iterable) - uses parentheses
# Lazy evaluation - doesn't create full list in memory

# Compare memory usage
import sys

list_comp = [x**2 for x in range(1000)]
gen_exp = (x**2 for x in range(1000))

print(f"\nList size: {sys.getsizeof(list_comp)} bytes")
print(f"Generator size: {sys.getsizeof(gen_exp)} bytes")

# Generator is consumed on iteration
gen = (x for x in range(3))
print("First:", next(gen))   # 0
print("Second:", next(gen))  # 1
print("Third:", next(gen))   # 2
# print(next(gen))  # StopIteration!

# Use with functions that accept iterables
total = sum(x**2 for x in range(10))  # No need for extra parentheses
print("Sum of squares:", total)
```

## REAL-WORLD EXAMPLES

```python
# Example 1: Parse log file data
logs = [
    "2024-01-01 ERROR: Connection failed",
    "2024-01-01 INFO: User logged in",
    "2024-01-02 ERROR: Timeout",
    "2024-01-02 INFO: Data processed",
]

errors = [log for log in logs if "ERROR" in log]
print("\nErrors:", errors)

# Example 2: Transform data records
raw_data = [
    {'name': 'alice', 'score': '85'},
    {'name': 'bob', 'score': '72'},
    {'name': 'charlie', 'score': '90'},
]

processed = [
    {'name': d['name'].title(), 'score': int(d['score'])}
    for d in raw_data
]
print("Processed:", processed)

# Example 3: Group by category
products = [
    ('Apple', 'Fruit', 1.50),
    ('Banana', 'Fruit', 0.75),
    ('Carrot', 'Vegetable', 0.50),
    ('Potato', 'Vegetable', 0.80),
]

# Get unique categories
categories = {product[1] for product in products}
print("Categories:", categories)

# Example 4: Create lookup table
users = [
    {'id': 1, 'name': 'Alice'},
    {'id': 2, 'name': 'Bob'},
    {'id': 3, 'name': 'Charlie'},
]

user_lookup = {u['id']: u['name'] for u in users}
print("Lookup:", user_lookup)
print("User 2:", user_lookup[2])
```
