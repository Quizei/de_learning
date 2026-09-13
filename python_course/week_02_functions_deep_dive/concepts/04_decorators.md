# Decorators in Python

Decorators modify or enhance functions without changing their source code.
They're functions that take a function and return a modified function.

```python
import time
from functools import wraps
```

## BASIC DECORATOR

```python
def simple_decorator(func):
    """A simple decorator that wraps a function."""
    def wrapper():
        print("Before function call")
        func()
        print("After function call")
    return wrapper

@simple_decorator
def say_hello():
    print("Hello!")

print("--- Basic Decorator ---")
say_hello()
# Output:
# Before function call
# Hello!
# After function call
```

## DECORATOR WITH ARGUMENTS

```python
def decorator_with_args(func):
    """Decorator that preserves function arguments."""
    @wraps(func)  # Preserves original function metadata
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        result = func(*args, **kwargs)
        print(f"Result: {result}")
        return result
    return wrapper

@decorator_with_args
def add(a, b):
    """Add two numbers."""
    return a + b

print("\n--- Decorator with Arguments ---")
result = add(5, 3)
print(f"Function name: {add.__name__}")  # 'add' (preserved by @wraps)
print(f"Docstring: {add.__doc__}")       # 'Add two numbers.'
```

## COMMON DECORATORS

```python
# 1. Timer decorator
def timer(func):
    """Measure execution time of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} took {end - start:.4f} seconds")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(0.1)
    return "Done"

print("\n--- Timer Decorator ---")
slow_function()


# 2. Retry decorator
def retry(max_attempts=3, delay=1):
    """Retry a function on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    print(f"Attempt {attempts} failed: {e}")
                    if attempts < max_attempts:
                        time.sleep(delay)
            raise Exception(f"Failed after {max_attempts} attempts")
        return wrapper
    return decorator

@retry(max_attempts=3, delay=0.1)
def unstable_function():
    import random
    if random.random() < 0.7:
        raise ValueError("Random failure")
    return "Success!"

print("\n--- Retry Decorator ---")
try:
    result = unstable_function()
    print(f"Result: {result}")
except Exception as e:
    print(f"Final error: {e}")


# 3. Cache/Memoize decorator
def memoize(func):
    """Cache function results."""
    cache = {}

    @wraps(func)
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]

    wrapper.cache = cache  # Expose cache for inspection
    return wrapper

@memoize
def fibonacci(n):
    """Calculate nth Fibonacci number."""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print("\n--- Memoize Decorator ---")
print(f"fib(30) = {fibonacci(30)}")
print(f"Cache size: {len(fibonacci.cache)}")


# 4. Validate arguments decorator
def validate_types(*types):
    """Validate argument types."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for arg, expected_type in zip(args, types):
                if not isinstance(arg, expected_type):
                    raise TypeError(
                        f"Expected {expected_type.__name__}, got {type(arg).__name__}"
                    )
            return func(*args, **kwargs)
        return wrapper
    return decorator

@validate_types(str, int)
def repeat_string(s, times):
    return s * times

print("\n--- Validate Types Decorator ---")
print(repeat_string("hello", 3))
try:
    repeat_string(123, 3)  # Should raise TypeError
except TypeError as e:
    print(f"Error: {e}")
```

## STACKING DECORATORS

```python
def bold(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return f"<b>{func(*args, **kwargs)}</b>"
    return wrapper

def italic(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return f"<i>{func(*args, **kwargs)}</i>"
    return wrapper

@bold
@italic
def get_text(text):
    return text

print("\n--- Stacked Decorators ---")
print(get_text("Hello"))  # <b><i>Hello</i></b>
# Decorators apply bottom-up: italic first, then bold
```

## CLASS-BASED DECORATOR

```python
class CountCalls:
    """Count how many times a function is called."""

    def __init__(self, func):
        self.func = func
        self.count = 0
        # Preserve function metadata
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__

    def __call__(self, *args, **kwargs):
        self.count += 1
        return self.func(*args, **kwargs)

@CountCalls
def greet(name):
    return f"Hello, {name}!"

print("\n--- Class-based Decorator ---")
print(greet("Alice"))
print(greet("Bob"))
print(f"Called {greet.count} times")
```

## DECORATOR WITH OPTIONAL ARGUMENTS

```python
def repeat(times_or_func=None, *, times=2):
    """Decorator that can be used with or without arguments."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            results = []
            for _ in range(times):
                results.append(func(*args, **kwargs))
            return results
        return wrapper

    if callable(times_or_func):
        # Used without parentheses: @repeat
        times = 2
        return decorator(times_or_func)
    else:
        # Used with arguments: @repeat(times=5)
        if times_or_func is not None:
            times = times_or_func
        return decorator

@repeat
def say_hi():
    return "Hi"

@repeat(times=3)
def say_bye():
    return "Bye"

print("\n--- Optional Arguments Decorator ---")
print(say_hi())   # ['Hi', 'Hi']
print(say_bye())  # ['Bye', 'Bye', 'Bye']
```

## REAL-WORLD EXAMPLES

```python
# 1. Logging decorator for data pipelines
def log_execution(func):
    """Log function execution for debugging."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(func.__module__)

        logger.info(f"Starting {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Completed {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper

# 2. Rate limiting decorator
def rate_limit(calls_per_second=1):
    """Limit function call rate."""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]  # Use list to allow modification in closure

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_called[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator
```
