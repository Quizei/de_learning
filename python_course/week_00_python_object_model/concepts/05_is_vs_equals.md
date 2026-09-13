# is vs == in Python

Understanding identity vs equality.

KEY INSIGHT:
- 'is' checks IDENTITY: "Are these the exact same object?"
- '==' checks EQUALITY: "Do these have the same value?"

## IDENTITY VS EQUALITY

```python
print("--- Identity vs Equality ---")

a = [1, 2, 3]
b = [1, 2, 3]
c = a

print(f"a = {a}")
print(f"b = {b}")
print(f"c = a")
print()

# Equality (==): Do they have the same VALUE?
print(f"a == b: {a == b}")  # True - same content
print(f"a == c: {a == c}")  # True - same content

# Identity (is): Are they the SAME OBJECT?
print(f"a is b: {a is b}")  # False - different objects!
print(f"a is c: {a is c}")  # True - same object

print(f"\nid(a) = {id(a)}")
print(f"id(b) = {id(b)}")  # Different from a
print(f"id(c) = {id(c)}")  # Same as a
```

## WHEN TO USE EACH

```python
print("\n--- When to Use Each ---")

# Use '==' for comparing VALUES (almost always)
name1 = "Alice"
name2 = "Alice"
if name1 == name2:
    print(f"Names are equal: {name1} == {name2}")

# Use 'is' ONLY for:
# 1. Comparing to None
# 2. Comparing to True/False (rare)
# 3. Checking if two names refer to same object

# Correct way to check for None
value = None
if value is None:
    print("Value is None (correct way)")

# Why not use == for None?
# It usually works, but some objects can override __eq__
# and break the comparison. 'is' is guaranteed to work.
```

## SMALL INTEGER CACHING

```python
print("\n--- Small Integer Caching ---")

# Python caches small integers (-5 to 256)
a = 100
b = 100
print(f"a = 100, b = 100")
print(f"a == b: {a == b}")  # True
print(f"a is b: {a is b}")  # True! (cached)

a = 1000
b = 1000
print(f"\na = 1000, b = 1000")
print(f"a == b: {a == b}")  # True
print(f"a is b: {a is b}")  # Usually False (not cached)

# DON'T rely on this behavior!
# Always use == for comparing integer values
```

## STRING INTERNING

```python
print("\n--- String Interning ---")

# Python interns some strings (simple identifiers)
s1 = "hello"
s2 = "hello"
print(f"s1 = 'hello', s2 = 'hello'")
print(f"s1 == s2: {s1 == s2}")  # True
print(f"s1 is s2: {s1 is s2}")  # True (interned)

# Strings with spaces typically not interned
s1 = "hello world"
s2 = "hello world"
print(f"\ns1 = 'hello world', s2 = 'hello world'")
print(f"s1 == s2: {s1 == s2}")  # True
print(f"s1 is s2: {s1 is s2}")  # May be True or False!

# Manual interning
import sys
s1 = sys.intern("hello world!")
s2 = sys.intern("hello world!")
print(f"\nAfter sys.intern:")
print(f"s1 is s2: {s1 is s2}")  # True

# DON'T rely on interning!
# Always use == for comparing string values
```

## NONE, TRUE, FALSE

```python
print("\n--- None, True, False ---")

# There is only ONE None object
a = None
b = None
print(f"a = None, b = None")
print(f"a is b: {a is b}")  # Always True
print(f"a is None: {a is None}")  # Correct way

# True and False are singletons too
a = True
b = True
print(f"\na = True, b = True")
print(f"a is b: {a is b}")  # True

# But be careful with boolean expressions!
x = 1
print(f"\nx = 1")
print(f"x == True: {x == True}")  # True (1 equals True)
print(f"x is True: {x is True}")  # False (different objects!)
```

## COMMON MISTAKES

```python
print("\n--- Common Mistakes ---")

# Mistake 1: Using 'is' for string comparison
def check_status_wrong(status):
    if status is "active":  # WRONG!
        return True
    return False

def check_status_right(status):
    if status == "active":  # Correct
        return True
    return False

# This might work sometimes due to interning, but it's unreliable
status = "active"
print(f"Wrong way: {check_status_wrong(status)}")  # Might be True
print(f"Right way: {check_status_right(status)}")  # Always correct

# Mistake 2: Using 'is' for number comparison
def is_zero_wrong(n):
    return n is 0  # WRONG!

def is_zero_right(n):
    return n == 0  # Correct

print(f"\nis_zero_wrong(0): {is_zero_wrong(0)}")  # True (cached)
print(f"is_zero_wrong(0.0): {is_zero_wrong(0.0)}")  # False! Different type

# Mistake 3: Using == for None
class WeirdClass:
    def __eq__(self, other):
        return True  # Always returns True!

obj = WeirdClass()
print(f"\nobj == None: {obj == None}")  # True (but obj is NOT None!)
print(f"obj is None: {obj is None}")  # False (correct)
```

## HOW EQUALITY WORKS

```python
print("\n--- How == Works (dunder methods) ---")

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y

p1 = Point(1, 2)
p2 = Point(1, 2)
p3 = p1

print(f"p1 == p2: {p1 == p2}")  # True (same values)
print(f"p1 is p2: {p1 is p2}")  # False (different objects)
print(f"p1 is p3: {p1 is p3}")  # True (same object)
```

## KEY TAKEAWAYS

```python
print("\n--- Key Takeaways ---")
print("""
1. '==' checks equality (values)
2. 'is' checks identity (same object in memory)

3. Use '==' for comparing values (almost always)
4. Use 'is' for: None, True, False, or checking object identity

5. 'is' compares id() values

6. Don't rely on integer caching or string interning!

7. Always use 'is' for None:
   ✓ if x is None
   ✗ if x == None

8. a is b  ⟹  a == b  (but not vice versa!)
""")
```
