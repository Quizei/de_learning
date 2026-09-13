# Argument Passing in Python

How Python passes arguments to functions.

KEY INSIGHT: Python uses "pass by object reference" (also called "pass by assignment").
             - The function receives a reference to the same object
             - NOT a copy of the value (pass by value)
             - NOT a pointer to the variable (pass by reference)

## PASS BY OBJECT REFERENCE

```python
print("--- Pass by Object Reference ---")

def show_id(name, obj):
    print(f"  {name}: value={obj}, id={id(obj)}")

# The function parameter is a NEW NAME bound to the SAME OBJECT
original_list = [1, 2, 3]
print(f"Outside function:")
show_id("original_list", original_list)

def receive_list(lst):
    print(f"\nInside function:")
    show_id("lst", lst)
    print(f"  lst is original_list: {lst is original_list}")

receive_list(original_list)
```

## MUTATING VS REBINDING INSIDE FUNCTIONS

```python
print("\n--- Mutating Inside Function ---")

def mutate_list(lst):
    """Mutates the original object."""
    lst.append(99)
    print(f"  Inside function after append: {lst}")

my_list = [1, 2, 3]
print(f"Before: {my_list}")
mutate_list(my_list)
print(f"After: {my_list}")  # [1, 2, 3, 99] - Changed!

print("\n--- Rebinding Inside Function ---")

def rebind_list(lst):
    """Rebinds the local name, doesn't affect original."""
    print(f"  Before rebind: id={id(lst)}")
    lst = [4, 5, 6]  # 'lst' now points to a NEW object
    print(f"  After rebind: {lst}, id={id(lst)}")

my_list = [1, 2, 3]
print(f"Before: {my_list}, id={id(my_list)}")
rebind_list(my_list)
print(f"After: {my_list}")  # [1, 2, 3] - Unchanged!
```

## IMMUTABLE ARGUMENTS

```python
print("\n--- Immutable Arguments ---")

def try_modify_int(x):
    print(f"  Before: x={x}, id={id(x)}")
    x = x + 1  # Creates new object, rebinds local 'x'
    print(f"  After: x={x}, id={id(x)}")
    return x

num = 5
print(f"Before call: num={num}, id={id(num)}")
result = try_modify_int(num)
print(f"After call: num={num}")  # 5 - Unchanged
print(f"Result: {result}")  # 6

def try_modify_string(s):
    s = s.upper()  # Creates new string, rebinds local 's'
    return s

text = "hello"
result = try_modify_string(text)
print(f"\nOriginal string: {text}")  # "hello" - unchanged
print(f"Returned string: {result}")  # "HELLO"
```

## COMMON PATTERNS

```python
print("\n--- Common Patterns ---")

# Pattern 1: Modify and return (works for any type)
def add_item_return(lst, item):
    new_list = lst.copy()  # Don't modify original
    new_list.append(item)
    return new_list

original = [1, 2, 3]
new = add_item_return(original, 4)
print(f"Pattern 1 - Copy and return:")
print(f"  Original: {original}")  # [1, 2, 3]
print(f"  New: {new}")  # [1, 2, 3, 4]

# Pattern 2: Modify in place (only for mutable types)
def add_item_inplace(lst, item):
    lst.append(item)
    # No return needed, original is modified

original = [1, 2, 3]
add_item_inplace(original, 4)
print(f"\nPattern 2 - Modify in place:")
print(f"  Original: {original}")  # [1, 2, 3, 4]

# Pattern 3: Replace object (rebind caller's variable)
# This DOESN'T work as expected:
def replace_list_wrong(lst):
    lst = [4, 5, 6]  # Only rebinds local name

my_list = [1, 2, 3]
replace_list_wrong(my_list)
print(f"\nPattern 3 - Rebinding doesn't work:")
print(f"  my_list: {my_list}")  # Still [1, 2, 3]

# To "replace", modify contents in place:
def replace_list_right(lst, new_contents):
    lst.clear()
    lst.extend(new_contents)

my_list = [1, 2, 3]
replace_list_right(my_list, [4, 5, 6])
print(f"\nPattern 3 - Modify contents in place:")
print(f"  my_list: {my_list}")  # [4, 5, 6]
```

## VISUAL EXPLANATION

```python
print("\n--- Visual Explanation ---")
print("""
When you call: func(my_list)

1. Python evaluates my_list -> gets the object (e.g., [1,2,3] at address 0x123)
2. Creates a new local variable 'lst' (inside func)
3. Binds 'lst' to the SAME object (0x123)

    my_list -----> [1, 2, 3]   (at 0x123)
                  /
    lst ---------/

Now inside func:
- lst.append(4)  -> Modifies object at 0x123. my_list sees change.
- lst = [4,5,6]  -> lst now points to NEW object. my_list unaffected.

    my_list -----> [1, 2, 3]   (at 0x123)

    lst ---------> [4, 5, 6]   (at 0x456)
""")
```

## INTERVIEW QUESTION EXAMPLES

```python
print("\n--- Interview Questions ---")

# Question 1: What's the output?
def mystery(a, b):
    a = a + b
    return a

x = [1, 2]
y = [3, 4]
z = mystery(x, y)
print(f"Q1: x={x}, y={y}, z={z}")
# x=[1,2] (unchanged - a + b creates new list)

# Question 2: What's the output?
def mystery2(a, b):
    a += b  # For lists, += is extend (modifies in place!)
    return a

x = [1, 2]
y = [3, 4]
z = mystery2(x, y)
print(f"Q2: x={x}, y={y}, z={z}")
# x=[1,2,3,4] (changed! += modifies in place for lists)

# Question 3: What's the output?
def mystery3(a, b):
    a.extend(b)
    a = [0]

x = [1, 2]
y = [3, 4]
mystery3(x, y)
print(f"Q3: x={x}")
# x=[1,2,3,4] (extend modified it, then rebind didn't affect x)
```

## KEY TAKEAWAYS

```python
print("\n--- Key Takeaways ---")
print("""
1. Python passes object references (not values, not variable references)

2. The parameter is a NEW NAME for the SAME OBJECT

3. Mutating the object inside a function affects the original

4. Rebinding the parameter inside a function does NOT affect the original

5. Immutable objects effectively behave like pass-by-value
   (because you can't mutate them, only rebind)

6. Common pitfall: += behaves differently for lists vs integers
   - For int: x += 1 creates new object (rebinding)
   - For list: x += [1] modifies in place (mutation)
""")
```
