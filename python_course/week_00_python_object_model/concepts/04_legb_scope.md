# LEGB Scope Rule in Python

How Python looks up variable names.

KEY INSIGHT: Python searches for names in this order:
             Local → Enclosing → Global → Built-in

## THE LEGB RULE

```python
print("--- LEGB Rule ---")
print("""
L - Local:     Names defined inside the current function
E - Enclosing: Names in enclosing functions (closures)
G - Global:    Names defined at module level
B - Built-in:  Names in the built-in module (len, print, etc.)

Python searches in this order and uses the FIRST match.
""")
```

## LOCAL SCOPE

```python
print("\n--- Local Scope ---")

x = "global x"

def func():
    x = "local x"  # This is LOCAL to func
    print(f"Inside func: x = '{x}'")

func()
print(f"Outside func: x = '{x}'")
```

## GLOBAL SCOPE

```python
print("\n--- Global Scope ---")

y = "global y"

def func2():
    # No local 'y', so Python looks at Global scope
    print(f"Inside func2: y = '{y}'")

func2()
```

## ENCLOSING SCOPE (CLOSURES)

```python
print("\n--- Enclosing Scope ---")

def outer():
    z = "enclosing z"

    def inner():
        # No local 'z', check Enclosing scope → found!
        print(f"Inside inner: z = '{z}'")

    inner()

outer()

# More complex example
def outer2():
    x = "enclosing x"

    def inner():
        x = "local x"  # This shadows the enclosing 'x'
        print(f"Inner: x = '{x}'")

    inner()
    print(f"Outer: x = '{x}'")  # Still "enclosing x"

outer2()
```

## BUILT-IN SCOPE

```python
print("\n--- Built-in Scope ---")

# 'len' is found in Built-in scope
print(f"len([1,2,3]) = {len([1, 2, 3])}")

# You can shadow built-ins (but don't!)
def bad_example():
    len = 5  # Shadows built-in 'len'
    # print(len([1, 2, 3]))  # TypeError: 'int' object is not callable
    print(f"len = {len}")

bad_example()
print(f"Outside: len still works: {len([1,2,3])}")
```

## THE 'global' KEYWORD

```python
print("\n--- The 'global' Keyword ---")

counter = 0

def increment_wrong():
    # This creates a LOCAL variable, doesn't modify global
    counter = 1
    print(f"Inside (wrong): counter = {counter}")

def increment_right():
    global counter  # Tells Python to use the GLOBAL 'counter'
    counter = counter + 1
    print(f"Inside (right): counter = {counter}")

print(f"Before: counter = {counter}")
increment_wrong()
print(f"After wrong: counter = {counter}")  # Still 0!
increment_right()
print(f"After right: counter = {counter}")  # Now 1
```

## THE 'nonlocal' KEYWORD

```python
print("\n--- The 'nonlocal' Keyword ---")

def outer3():
    count = 0

    def inner():
        nonlocal count  # Refers to 'count' in enclosing scope
        count += 1
        print(f"Inner: count = {count}")

    inner()
    inner()
    print(f"Outer: count = {count}")

outer3()

# Without nonlocal:
def outer4():
    count = 0

    def inner():
        # count += 1  # UnboundLocalError! Python sees assignment,
                      # assumes it's local, but it's not defined yet
        pass

    inner()
```

## VARIABLE ASSIGNMENT CREATES LOCAL

```python
print("\n--- Assignment Creates Local Variable ---")

value = "global"

def test_scope():
    # Just READING global works:
    # print(value)  # Would print "global"

    # But if there's ANY assignment, Python assumes it's local
    value = "local"  # This makes 'value' LOCAL to entire function
    print(f"Inside: value = '{value}'")

test_scope()
print(f"Outside: value = '{value}'")

# This is why this fails:
def broken_scope():
    # print(x)  # UnboundLocalError!
    x = 10  # Assignment makes 'x' local for ENTIRE function
            # but we tried to read it before assignment

# broken_scope()
```

## LEGB LOOKUP EXAMPLE

```python
print("\n--- Complete LEGB Example ---")

x = "global"

def level1():
    x = "enclosing"

    def level2():
        x = "local"

        def level3():
            # What is x here?
            print(f"In level3: x = '{x}'")  # Found in enclosing (level2)

        level3()
        print(f"In level2: x = '{x}'")

    level2()
    print(f"In level1: x = '{x}'")

level1()
print(f"At module: x = '{x}'")
```

## PRACTICAL EXAMPLE: CLOSURE COUNTER

```python
print("\n--- Practical Example: Counter Factory ---")

def make_counter():
    count = 0  # Enclosing variable

    def counter():
        nonlocal count
        count += 1
        return count

    return counter

counter_a = make_counter()
counter_b = make_counter()  # Separate closure, separate 'count'

print(f"counter_a(): {counter_a()}")  # 1
print(f"counter_a(): {counter_a()}")  # 2
print(f"counter_b(): {counter_b()}")  # 1 (separate count)
print(f"counter_a(): {counter_a()}")  # 3
```

## KEY TAKEAWAYS

```python
print("\n--- Key Takeaways ---")
print("""
1. LEGB order: Local → Enclosing → Global → Built-in

2. Assignment ANYWHERE in a function makes it local for ENTIRE function

3. 'global' keyword: access/modify module-level variables

4. 'nonlocal' keyword: access/modify enclosing function variables

5. Each function call creates a new local namespace

6. Closures capture enclosing variables by reference

7. Don't shadow built-ins (len, list, dict, etc.)
""")
```
