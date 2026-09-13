# Names and Objects in Python

Understanding how variables work in Python.

KEY INSIGHT: Variables are names (labels) that point to objects.
             They are NOT boxes that hold values.

## VARIABLES ARE NAMES, NOT BOXES

```python
print("--- Variables are Names ---")

# When you write:
a = [1, 2, 3]

# You're NOT creating a box called 'a' containing [1, 2, 3]
# You're:
#   1. Creating a list object [1, 2, 3] in memory
#   2. Binding the name 'a' to that object

# The id() function shows the object's memory address
print(f"a = [1, 2, 3]")
print(f"id(a) = {id(a)}")  # Memory address of the list object
```

## MULTIPLE NAMES, ONE OBJECT

```python
print("\n--- Multiple Names, One Object ---")

a = [1, 2, 3]
b = a  # 'b' now points to THE SAME object as 'a'

print(f"a = {a}")
print(f"b = {b}")
print(f"id(a) = {id(a)}")
print(f"id(b) = {id(b)}")
print(f"a is b: {a is b}")  # True - same object!

# Modifying through 'b' affects 'a' (because it's the SAME object)
b.append(4)
print(f"\nAfter b.append(4):")
print(f"a = {a}")  # [1, 2, 3, 4] - a sees the change!
print(f"b = {b}")  # [1, 2, 3, 4]
```

## REBINDING VS MUTATING

```python
print("\n--- Rebinding vs Mutating ---")

# REBINDING: Making a name point to a DIFFERENT object
a = [1, 2, 3]
b = a
print(f"Before: id(a)={id(a)}, id(b)={id(b)}, a is b: {a is b}")

b = [4, 5, 6]  # 'b' now points to a NEW object
print(f"After b = [4, 5, 6]:")
print(f"a = {a}")  # [1, 2, 3] - unchanged
print(f"b = {b}")  # [4, 5, 6] - new object
print(f"id(a)={id(a)}, id(b)={id(b)}, a is b: {a is b}")  # False

# MUTATING: Changing the object itself
a = [1, 2, 3]
b = a
b.append(4)  # Mutates the shared object
print(f"\nAfter b.append(4):")
print(f"a = {a}")  # [1, 2, 3, 4] - both see change
print(f"b = {b}")  # [1, 2, 3, 4]
```

## AUGMENTED ASSIGNMENT

```python
print("\n--- Augmented Assignment (+=) ---")

# For IMMUTABLE types, += creates a NEW object
a = 5
b = a
print(f"Before: a={a}, b={b}, a is b: {a is b}")

a += 1  # Creates NEW int object, rebinds 'a'
print(f"After a += 1:")
print(f"a={a}, b={b}, a is b: {a is b}")  # False - different objects

# For MUTABLE types, += may modify in place
a = [1, 2]
b = a
print(f"\nBefore: a={a}, b={b}, a is b: {a is b}")

a += [3]  # For lists, += modifies in place (calls extend)
print(f"After a += [3]:")
print(f"a={a}, b={b}, a is b: {a is b}")  # True - same object, both modified

# GOTCHA: a = a + [3] is DIFFERENT from a += [3] for lists!
a = [1, 2]
b = a
a = a + [3]  # Creates NEW list, rebinds 'a'
print(f"\nAfter a = a + [3]:")
print(f"a={a}, b={b}, a is b: {a is b}")  # False - different objects
```

## FUNCTION PARAMETERS

```python
print("\n--- Function Parameters ---")

def modify_list(lst):
    """The parameter 'lst' is a new name for the same object."""
    print(f"  Inside function: id(lst) = {id(lst)}")
    lst.append(99)  # Modifies the original object

my_list = [1, 2, 3]
print(f"Before: my_list = {my_list}, id = {id(my_list)}")
modify_list(my_list)
print(f"After: my_list = {my_list}")  # [1, 2, 3, 99]
```

## VISUALIZING WITH MEMORY DIAGRAMS

```python
print("\n--- Mental Model ---")
print("""
Think of it like this:

    a = [1, 2, 3]
    b = a

    Memory:

    Names           Objects
    -----           -------
      a  ---------> [1, 2, 3]
                   /
      b  ---------/

    Both 'a' and 'b' point to THE SAME list object.
    Modifying through either name affects both.

    b = [4, 5, 6]  # Rebinding

    Names           Objects
    -----           -------
      a  ---------> [1, 2, 3]

      b  ---------> [4, 5, 6]

    Now they point to DIFFERENT objects.
""")
```

## KEY TAKEAWAYS

```python
print("\n--- Key Takeaways ---")
print("""
1. Variables are names (labels) bound to objects
2. Assignment (=) binds a name to an object, never copies
3. Multiple names can point to the same object (aliasing)
4. id() shows an object's identity (memory address)
5. 'is' checks identity, '==' checks equality
6. Mutating an object affects ALL names bound to it
7. Rebinding makes a name point to a different object
""")
```
