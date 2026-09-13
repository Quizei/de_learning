# Debugging in Python

Techniques for finding and fixing bugs.

## USING BREAKPOINT()

```python
print("--- Using breakpoint() ---")

def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    # breakpoint()  # Uncomment to debug - drops into pdb
    return total / count

result = calculate_average([1, 2, 3, 4, 5])
print(f"Average: {result}")
```

## PDB COMMANDS

```python
print("\n--- PDB Commands ---")
print("""
n (next)      - Execute next line
s (step)      - Step into function
c (continue)  - Continue execution
q (quit)      - Quit debugger
p expr        - Print expression
pp expr       - Pretty print expression
l (list)      - Show source code
w (where)     - Show call stack
b line        - Set breakpoint at line
cl            - Clear breakpoints
h (help)      - Show help
""")
```

## DEBUGGING TECHNIQUES

```python
print("\n--- Debugging Techniques ---")

# 1. Print debugging (simple but effective)
def process_data(data):
    print(f"DEBUG: Input data = {data}")
    result = [x * 2 for x in data]
    print(f"DEBUG: Result = {result}")
    return result

# 2. Assert statements
def divide(a, b):
    assert b != 0, "Divisor cannot be zero"
    return a / b

# 3. Using __debug__ flag
if __debug__:
    print("Debug mode is on (run with python -O to disable)")

# 4. Inspect module for introspection
import inspect

def example_function(a, b, c=10):
    """Example function."""
    frame = inspect.currentframe()
    print(f"Local variables: {frame.f_locals}")
    return a + b + c

example_function(1, 2)

# 5. Traceback module
import traceback

def function_a():
    function_b()

def function_b():
    function_c()

def function_c():
    print("Call stack:")
    traceback.print_stack()

function_a()
```

## DEBUGGING DECORATORS

```python
print("\n--- Debugging Decorators ---")

from functools import wraps
import time

def debug_calls(func):
    """Log function calls with arguments and return value."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        print(f"Calling {func.__name__}({signature})")
        result = func(*args, **kwargs)
        print(f"{func.__name__} returned {result!r}")
        return result
    return wrapper

@debug_calls
def add(a, b):
    return a + b

add(2, 3)

print("\n✅ Debugging complete!")
```
