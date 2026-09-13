# Memory Management in Python

Understanding how Python manages memory.

```python
import sys
import gc
```

## OBJECT IDENTITY AND REFERENCES

```python
print("--- Object Identity ---")

a = [1, 2, 3]
b = a        # Same object (reference)
c = [1, 2, 3]  # Different object (same value)

print(f"a is b: {a is b}")  # True - same object
print(f"a is c: {a is c}")  # False - different objects
print(f"a == c: {a == c}")  # True - same value

print(f"id(a): {id(a)}")
print(f"id(b): {id(b)}")
print(f"id(c): {id(c)}")
```

## REFERENCE COUNTING

```python
print("\n--- Reference Counting ---")

x = [1, 2, 3]
print(f"Ref count: {sys.getrefcount(x)}")  # +1 for getrefcount arg

y = x  # Add reference
print(f"After y = x: {sys.getrefcount(x)}")

del y  # Remove reference
print(f"After del y: {sys.getrefcount(x)}")
```

## SMALL INTEGER CACHING

```python
print("\n--- Integer Caching ---")

# Python caches integers -5 to 256
a = 100
b = 100
print(f"100 is 100: {a is b}")  # True - cached

a = 1000
b = 1000
print(f"1000 is 1000: {a is b}")  # May be False

# String interning
s1 = "hello"
s2 = "hello"
print(f"'hello' is 'hello': {s1 is s2}")  # True - interned
```

## MUTABLE VS IMMUTABLE

```python
print("\n--- Mutable vs Immutable ---")

# Immutable: int, float, str, tuple, frozenset
x = 10
print(f"Before: id(x) = {id(x)}")
x += 1  # Creates new object
print(f"After: id(x) = {id(x)}")

# Mutable: list, dict, set
lst = [1, 2, 3]
print(f"Before: id(lst) = {id(lst)}")
lst.append(4)  # Same object
print(f"After: id(lst) = {id(lst)}")
```

## GARBAGE COLLECTION

```python
print("\n--- Garbage Collection ---")

# Manual GC
print(f"GC enabled: {gc.isenabled()}")
print(f"GC thresholds: {gc.get_threshold()}")

# Force collection
collected = gc.collect()
print(f"Collected {collected} objects")

# GC statistics
stats = gc.get_stats()
print(f"Generation 0 collections: {stats[0]['collections']}")
```

## MEMORY USAGE

```python
print("\n--- Memory Usage ---")

# Object size
print(f"Size of int: {sys.getsizeof(1)} bytes")
print(f"Size of float: {sys.getsizeof(1.0)} bytes")
print(f"Size of empty list: {sys.getsizeof([])} bytes")
print(f"Size of [1,2,3]: {sys.getsizeof([1,2,3])} bytes")
print(f"Size of empty dict: {sys.getsizeof({})} bytes")
print(f"Size of 'hello': {sys.getsizeof('hello')} bytes")
```

## __SLOTS__ FOR MEMORY OPTIMIZATION

```python
print("\n--- __slots__ ---")

class RegularClass:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class SlottedClass:
    __slots__ = ['x', 'y']
    def __init__(self, x, y):
        self.x = x
        self.y = y

regular = RegularClass(1, 2)
slotted = SlottedClass(1, 2)

print(f"Regular object size: {sys.getsizeof(regular)} + dict")
print(f"Slotted object size: {sys.getsizeof(slotted)}")
print(f"Regular has __dict__: {hasattr(regular, '__dict__')}")
print(f"Slotted has __dict__: {hasattr(slotted, '__dict__')}")
```

## WEAK REFERENCES

```python
print("\n--- Weak References ---")

import weakref

class MyClass:
    pass

obj = MyClass()
weak_ref = weakref.ref(obj)

print(f"Object exists: {weak_ref() is not None}")
del obj
gc.collect()
print(f"After del: {weak_ref() is not None}")

print("\n✅ Memory management complete!")
```
