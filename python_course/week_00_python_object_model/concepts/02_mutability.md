# Mutability in Python

Understanding mutable vs immutable types and their implications.

KEY INSIGHT: Immutable objects cannot be changed after creation.
             "Modifying" them creates a new object.

## IMMUTABLE TYPES

```python
print("--- Immutable Types ---")
print("""
Immutable types in Python:
- int, float, complex
- str
- tuple
- frozenset
- bytes
- bool (subclass of int)
""")

# Integers are immutable
x = 5
print(f"x = 5, id(x) = {id(x)}")
x = x + 1  # Creates NEW int object
print(f"x = x + 1, id(x) = {id(x)}")  # Different id!

# Strings are immutable
s = "hello"
print(f"\ns = 'hello', id(s) = {id(s)}")
s = s + " world"  # Creates NEW string object
print(f"s = s + ' world', id(s) = {id(s)}")  # Different id!
print(s[0])

# You cannot modify a string in place
# s[0] = "H"  # TypeError: 'str' object does not support item assignment

# Tuples are immutable
t = (1, 2, 3)
print(f"\nt = (1, 2, 3), id(t) = {id(t)}")
# t[0] = 99  # TypeError: 'tuple' object does not support item assignment
# t.append(4)  # AttributeError: 'tuple' object has no attribute 'append'
```

## MUTABLE TYPES

```python
print("\n--- Mutable Types ---")
print("""
Mutable types in Python:
- list
- dict
- set
- bytearray
- Custom objects (by default)
""")

# Lists are mutable
lst = [1, 2, 3]
original_id = id(lst)
print(f"lst = [1, 2, 3], id = {original_id}")

lst.append(4)  # Modifies in place
print(f"After append(4): lst = {lst}, id = {id(lst)}")
print(f"Same object: {id(lst) == original_id}")  # True!

lst[0] = 99  # Modifies in place
print(f"After lst[0] = 99: lst = {lst}, id = {id(lst)}")
print(f"Same object: {id(lst) == original_id}")  # True!

# Dicts are mutable
d = {"a": 1}
original_id = id(d)
d["b"] = 2  # Modifies in place
print(f"\nDict after adding key: {d}, same object: {id(d) == original_id}")

# Sets are mutable
s = {1, 2, 3}
original_id = id(s)
s.add(4)  # Modifies in place
print(f"Set after add: {s}, same object: {id(s) == original_id}")
```

## WHY MUTABILITY MATTERS

```python
print("\n--- Why Mutability Matters ---")

# 1. ALIASING BEHAVIOR

a = [1, 2, 3]
b = a
b.append(4)
print(f"Mutable aliasing:")
print(f"  a = {a}")  # [1, 2, 3, 4] - affected!
print(f"  b = {b}")  # [1, 2, 3, 4]

a = 5
b = a
b = b + 1
print(f"\nImmutable aliasing:")
print(f"  a = {a}")  # 5 - not affected
print(f"  b = {b}")  # 6

# 2. FUNCTION ARGUMENTS

def add_item(lst, item):
    lst.append(item)  # Modifies the original!

my_list = [1, 2, 3]
print(f"Before modifying {id(my_list)} ")
add_item(my_list, 4)
print(f"\nFunction modifying mutable: {my_list} , {id(my_list)}")  # [1, 2, 3, 4]

def try_modify_string(s):
    s = s + " world"  # Creates new string, doesn't affect original
    return s

my_string = "hello"
try_modify_string(my_string)
print(f"Function with immutable: {my_string}")  # "hello" - unchanged

# 3. DEFAULT ARGUMENTS GOTCHA

def append_to(item, target=[]):  # DANGEROUS! Mutable default
    target.append(item)
    return target

print(f"\nMutable default argument bug:")
print(f"  Call 1: {append_to(1)}")  # [1]
print(f"  Call 2: {append_to(2)}")  # [1, 2] - BUG! Same list reused!
print(f"  Call 3: {append_to(3)}")  # [1, 2, 3]

# CORRECT way:
def append_to_fixed(item, target=None):
    if target is None:
        target = []  # New list each time
    target.append(item)
    return target

print(f"\nFixed version:")
print(f"  Call 1: {append_to_fixed(1)}")  # [1]
print(f"  Call 2: {append_to_fixed(2)}")  # [2] - Correct!
```

## TUPLE WITH MUTABLE ELEMENTS

```python
print("\n--- Tuple with Mutable Elements ---")

# A tuple is immutable, but its elements might be mutable!
t = ([1, 2], [3, 4])
print(f"t = {t}")

# Can't reassign tuple elements
# t[0] = [5, 6]  # TypeError!

# BUT can modify mutable elements inside the tuple
t[0].append(99)
print(f"After t[0].append(99): t = {t}")  # ([1, 2, 99], [3, 4])

# This is called "shallow immutability"
```

## HASHABILITY

```python
print("\n--- Hashability ---")
print("""
Immutable objects are typically hashable (can be dict keys / set members).
Mutable objects are typically NOT hashable.
""")

# Works - immutable types as dict keys
d = {
    "string": 1,
    42: 2,
    (1, 2): 3,  # Tuple is hashable
}
print(f"Dict with immutable keys: {d}")

# Fails - mutable types as dict keys
try:
    d = {[1, 2]: "value"}  # List as key
except TypeError as e:
    print(f"List as key error: {e}")

try:
    d = {{1, 2}: "value"}  # Set as key
except TypeError as e:
    print(f"Set as key error: {e}")
```

## KEY TAKEAWAYS

```python
print("\n--- Key Takeaways ---")
print("""
1. Immutable: int, float, str, tuple, frozenset, bytes
2. Mutable: list, dict, set, custom objects

3. Immutable objects:
   - Cannot be changed after creation
   - "Modification" creates a new object
   - Safe to share between variables
   - Can be dict keys / set members

4. Mutable objects:
   - Can be changed in place
   - Changes affect all references
   - Dangerous as default arguments
   - Cannot be dict keys / set members

5. Always ask: "Am I mutating or rebinding?"
""")
```
