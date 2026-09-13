# Shallow vs Deep Copy in Python

Understanding how to properly duplicate objects.

KEY INSIGHT:
- Assignment (=) creates an alias, NOT a copy
- Shallow copy creates a new object but references same nested objects
- Deep copy creates completely independent copy of everything

```python
import copy
```

## ASSIGNMENT IS NOT COPYING

```python
print("--- Assignment is NOT Copying ---")

original = [1, 2, 3]
alias = original  # NOT a copy! Same object.

alias.append(4)
print(f"original: {original}")  # [1, 2, 3, 4] - affected!
print(f"alias: {alias}")        # [1, 2, 3, 4]
print(f"original is alias: {original is alias}")  # True
```

## SHALLOW COPY

```python
print("\n--- Shallow Copy ---")

# Methods to create shallow copies:
original = [1, 2, 3]

# Method 1: copy() method
copy1 = original.copy()

# Method 2: list() constructor
copy2 = list(original)

# Method 3: Slicing
copy3 = original[:]

# Method 4: copy.copy()
copy4 = copy.copy(original)

print(f"original: {original}")
print(f"copy1:    {copy1}")
print(f"original is copy1: {original is copy1}")  # False - different objects!

copy1.append(4)
print(f"\nAfter copy1.append(4):")
print(f"original: {original}")  # [1, 2, 3] - NOT affected
print(f"copy1:    {copy1}")     # [1, 2, 3, 4]
```

## SHALLOW COPY LIMITATION

```python
print("\n--- Shallow Copy Limitation (Nested Objects) ---")

original = [[1, 2], [3, 4], [5, 6]]
shallow = original.copy()

print(f"original: {original}")
print(f"shallow:  {shallow}")
print(f"original is shallow: {original is shallow}")  # False
print(f"original[0] is shallow[0]: {original[0] is shallow[0]}")  # TRUE!

# The nested lists are SHARED
shallow[0].append(99)
print(f"\nAfter shallow[0].append(99):")
print(f"original: {original}")  # [[1, 2, 99], ...] - AFFECTED!
print(f"shallow:  {shallow}")   # [[1, 2, 99], ...]

# But reassigning the element itself doesn't affect original
shallow[1] = [100, 200]
print(f"\nAfter shallow[1] = [100, 200]:")
print(f"original: {original}")  # [[1, 2, 99], [3, 4], [5, 6]]
print(f"shallow:  {shallow}")   # [[1, 2, 99], [100, 200], [5, 6]]
```

## DEEP COPY

```python
print("\n--- Deep Copy ---")

original = [[1, 2], [3, 4], [5, 6]]
deep = copy.deepcopy(original)

print(f"original: {original}")
print(f"deep:     {deep}")
print(f"original is deep: {original is deep}")        # False
print(f"original[0] is deep[0]: {original[0] is deep[0]}")  # FALSE! Different!

deep[0].append(99)
print(f"\nAfter deep[0].append(99):")
print(f"original: {original}")  # [[1, 2], [3, 4], [5, 6]] - NOT affected
print(f"deep:     {deep}")      # [[1, 2, 99], [3, 4], [5, 6]]
```

## DICT COPYING

```python
print("\n--- Dict Copying ---")

original = {"a": [1, 2], "b": [3, 4]}

# Shallow copy methods for dicts
shallow1 = original.copy()
shallow2 = dict(original)
shallow3 = {**original}  # Spread operator

print(f"original is shallow1: {original is shallow1}")  # False
print(f"original['a'] is shallow1['a']: {original['a'] is shallow1['a']}")  # True!

# Deep copy
deep = copy.deepcopy(original)
print(f"original['a'] is deep['a']: {original['a'] is deep['a']}")  # False
```

## WHEN TO USE EACH

```python
print("\n--- When to Use Each ---")
print("""
Assignment (=):
    Use when you WANT both names to refer to same object
    Example: alias = original

Shallow Copy (copy(), [:], etc.):
    Use for flat structures (no nested mutable objects)
    Use when you only need to modify the top-level structure
    Faster than deep copy

Deep Copy (copy.deepcopy()):
    Use when you need completely independent copy
    Use for nested structures that you want to modify separately
    Slower, uses more memory
""")
```

## PRACTICAL EXAMPLES

```python
print("\n--- Practical Examples ---")

# Example 1: Modifying a list in a function without affecting original
def process_data(data):
    working_copy = data.copy()  # Shallow copy is fine for flat list
    working_copy.append("processed")
    return working_copy

original_data = [1, 2, 3]
result = process_data(original_data)
print(f"Original preserved: {original_data}")
print(f"Result: {result}")

# Example 2: Deep copy for nested config
config = {
    "database": {"host": "localhost", "port": 5432},
    "cache": {"enabled": True}
}

# If you modify test_config, you don't want to affect config
test_config = copy.deepcopy(config)
test_config["database"]["host"] = "testserver"

print(f"\nConfig: {config['database']['host']}")  # localhost
print(f"Test config: {test_config['database']['host']}")  # testserver

# Example 3: Default argument pitfall
def append_to(item, target=None):
    if target is None:
        target = []  # New list each call
    target.append(item)
    return target

# NOT:
# def append_to(item, target=[]):  # DANGEROUS!
#     target.append(item)
#     return target
```

## COPY AND CUSTOM OBJECTS

```python
print("\n--- Custom Objects ---")

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def __copy__(self):
        """Customize shallow copy behavior."""
        print("  __copy__ called")
        return Point(self.x, self.y)

    def __deepcopy__(self, memo):
        """Customize deep copy behavior."""
        print("  __deepcopy__ called")
        return Point(copy.deepcopy(self.x, memo),
                     copy.deepcopy(self.y, memo))

p1 = Point(1, 2)
p2 = copy.copy(p1)
p3 = copy.deepcopy(p1)
```

## VISUAL SUMMARY

```python
print("\n--- Visual Summary ---")
print("""
original = [[1, 2], [3, 4]]

Assignment: alias = original
┌──────────┐     ┌──────────┐
│ original │────►│ [→, →]   │
└──────────┘     └──────────┘
┌──────────┐          │
│  alias   │──────────┘
└──────────┘

Shallow Copy: shallow = original.copy()
┌──────────┐     ┌──────────┐     ┌───────┐
│ original │────►│ [→, →]   │────►│[1, 2] │
└──────────┘     └──────────┘     └───────┘
                       │          ┌───────┐
                       └─────────►│[3, 4] │
                                  └───────┘
                                    ▲   ▲
┌──────────┐     ┌──────────┐      │   │
│ shallow  │────►│ [→, →]   │──────┘   │
└──────────┘     └──────────┘──────────┘

Deep Copy: deep = copy.deepcopy(original)
┌──────────┐     ┌──────────┐     ┌───────┐
│ original │────►│ [→, →]   │────►│[1, 2] │
└──────────┘     └──────────┘     └───────┘
                       │          ┌───────┐
                       └─────────►│[3, 4] │
                                  └───────┘

┌──────────┐     ┌──────────┐     ┌───────┐
│   deep   │────►│ [→, →]   │────►│[1, 2] │ (independent copy)
└──────────┘     └──────────┘     └───────┘
                       │          ┌───────┐
                       └─────────►│[3, 4] │ (independent copy)
                                  └───────┘
""")
```

## KEY TAKEAWAYS

```python
print("\n--- Key Takeaways ---")
print("""
1. Assignment (=) creates an alias, not a copy

2. Shallow copy:
   - Creates new container object
   - Elements are references to SAME nested objects
   - Methods: .copy(), list(), dict(), [:], {**d}

3. Deep copy:
   - Creates new container AND new nested objects
   - Completely independent copy
   - Method: copy.deepcopy()

4. For flat structures, shallow copy is usually sufficient

5. For nested mutable structures, use deep copy if you need independence

6. Custom objects can define __copy__ and __deepcopy__ methods
""")
```
