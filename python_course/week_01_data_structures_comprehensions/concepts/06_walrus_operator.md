# Walrus Operator (:=) - Assignment Expression

Introduced in Python 3.8, allows assignment within expressions.
Named "walrus" because := looks like walrus eyes and tusks.

## BASIC USAGE

```python
# Without walrus operator
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Traditional approach - compute twice or use temp variable
if len(data) > 5:
    print(f"List has {len(data)} items")  # len() called twice

# With walrus operator - compute once, use multiple times
if (n := len(data)) > 5:
    print(f"List has {n} items")
```

## COMMON USE CASES

```python
# 1. While loops with assignment
# Traditional
line = input("Enter text (or 'quit'): ") if False else "example"
# while line != 'quit':
#     print(f"You entered: {line}")
#     line = input("Enter text (or 'quit'): ")

# With walrus - cleaner
# while (line := input("Enter text (or 'quit'): ")) != 'quit':
#     print(f"You entered: {line}")

# 2. List comprehensions with expensive operations
# Without walrus - function called twice
words = ["hello", "world", "python", "programming"]

# Traditional (inefficient if process() is expensive)
def process(word):
    """Simulate expensive operation."""
    return word.upper() + "!"

# Without walrus - calls process() twice per word if filtering
# result = [process(w) for w in words if len(process(w)) > 6]

# With walrus - calls process() once per word
result = [processed for w in words if len(processed := process(w)) > 6]
print("Processed (len > 6):", result)

# 3. Conditional expressions
numbers = [1, 2, 3, 4, 5]

# Check and use result
if (total := sum(numbers)) > 10:
    print(f"Total {total} is greater than 10")

# 4. Regex matching
import re

text = "Contact: john@example.com"
pattern = r'[\w\.-]+@[\w\.-]+'

# Traditional
match = re.search(pattern, text)
if match:
    email = match.group()
    print(f"Found email: {email}")

# With walrus
if (match := re.search(pattern, text)):
    print(f"Found email: {match.group()}")

# 5. Reading files in chunks
# Traditional way to read file in chunks:
# while True:
#     chunk = file.read(8192)
#     if not chunk:
#         break
#     process(chunk)

# With walrus:
# while (chunk := file.read(8192)):
#     process(chunk)
```

## DATA ENGINEERING EXAMPLES

```python
# Example 1: Processing API responses
def fetch_data(page):
    """Simulate API that returns data or None when exhausted."""
    pages = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9]}
    return pages.get(page)

all_data = []
page = 1
# Without walrus
while True:
    data = fetch_data(page)
    if data is None:
        break
    all_data.extend(data)
    page += 1

print("All data (traditional):", all_data)

# With walrus - more concise
all_data = []
page = 1
# Note: This would be in a loop with page incrementing
# while (data := fetch_data(page)) is not None:
#     all_data.extend(data)
#     page += 1

# Example 2: Filtering with validation
records = [
    {"id": 1, "value": "100"},
    {"id": 2, "value": "invalid"},
    {"id": 3, "value": "200"},
    {"id": 4, "value": "not_a_number"},
]

def parse_value(val):
    """Try to parse value as int, return None if invalid."""
    try:
        return int(val)
    except ValueError:
        return None

# Filter valid records and transform in one comprehension
valid_records = [
    {"id": r["id"], "value": parsed}
    for r in records
    if (parsed := parse_value(r["value"])) is not None
]
print("Valid records:", valid_records)

# Example 3: Finding first match
items = [
    {"name": "apple", "price": 1.0},
    {"name": "banana", "price": 0.5},
    {"name": "cherry", "price": 2.0},
]

# Find first item over $1
if (expensive := next((i for i in items if i["price"] > 1), None)):
    print(f"First expensive item: {expensive['name']}")
```

## WHEN NOT TO USE WALRUS

```python
# Don't sacrifice readability
# Bad - too clever
# result = [(y := x * 2, y + 1) for x in range(5)]

# Good - clear intent
result = []
for x in range(5):
    doubled = x * 2
    result.append((doubled, doubled + 1))

# Don't use for simple assignments
# Bad
# (x := 5)

# Good
x = 5

print("\n✅ Walrus operator is best for:")
print("   - Avoiding repeated expensive operations")
print("   - Simplifying while loops with assignment")
print("   - List comprehensions with filtering on computed values")
```
