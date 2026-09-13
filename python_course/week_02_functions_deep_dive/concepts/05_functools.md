# functools Module

Higher-order functions and operations on callable objects.
Essential for functional programming in Python.

```python
from functools import (
    partial, partialmethod,
    lru_cache, cache,
    wraps,
    reduce,
    total_ordering,
    singledispatch
)
import time
```

## partial - Freeze Some Arguments

```python
def power(base, exponent):
    """Calculate base raised to exponent."""
    return base ** exponent

# Create specialized functions
square = partial(power, exponent=2)
cube = partial(power, exponent=3)

print("--- partial ---")
print(f"square(5) = {square(5)}")  # 25
print(f"cube(3) = {cube(3)}")      # 27

# Practical example: API client with default headers
def make_request(url, method="GET", headers=None, timeout=30):
    """Simulate API request."""
    return f"{method} {url} (timeout={timeout}, headers={headers})"

# Create specialized request functions
api_get = partial(make_request, method="GET", timeout=10)
api_post = partial(make_request, method="POST", headers={"Content-Type": "application/json"})

print("\n--- partial with API ---")
print(api_get("https://api.example.com/users"))
print(api_post("https://api.example.com/users"))
```

## lru_cache - Memoization

```python
@lru_cache(maxsize=128)
def fibonacci(n):
    """Calculate nth Fibonacci number with caching."""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print("\n--- lru_cache ---")
start = time.perf_counter()
result = fibonacci(35)
end = time.perf_counter()
print(f"fib(35) = {result} (took {end - start:.6f}s)")

# Cache info
print(f"Cache info: {fibonacci.cache_info()}")

# Clear cache
fibonacci.cache_clear()
print(f"After clear: {fibonacci.cache_info()}")

# Python 3.9+ has @cache (unlimited size, simpler)
# @cache
# def factorial(n):
#     return n * factorial(n-1) if n else 1


# lru_cache with typed=True (treats 1 and 1.0 as different)
@lru_cache(maxsize=100, typed=True)
def typed_function(x):
    return x * 2

print(f"\ntyped_function(1) = {typed_function(1)}")
print(f"typed_function(1.0) = {typed_function(1.0)}")
print(f"Cache info (typed): {typed_function.cache_info()}")
```

## reduce - Cumulative Operations

```python
from functools import reduce

numbers = [1, 2, 3, 4, 5]

# Sum (though sum() is preferred for this)
total = reduce(lambda x, y: x + y, numbers)
print(f"\n--- reduce ---")
print(f"Sum: {total}")

# Product
product = reduce(lambda x, y: x * y, numbers)
print(f"Product: {product}")

# Max (though max() is preferred)
maximum = reduce(lambda x, y: x if x > y else y, numbers)
print(f"Max: {maximum}")

# With initial value
total_with_init = reduce(lambda x, y: x + y, numbers, 100)
print(f"Sum with initial 100: {total_with_init}")

# Practical: Flatten nested list
nested = [[1, 2], [3, 4], [5, 6]]
flattened = reduce(lambda x, y: x + y, nested)
print(f"Flattened: {flattened}")

# Practical: Compose functions
def compose(*functions):
    """Compose multiple functions."""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)

double = lambda x: x * 2
add_one = lambda x: x + 1
square = lambda x: x ** 2

pipeline = compose(square, add_one, double)
print(f"compose(square, add_one, double)(5) = {pipeline(5)}")  # square(add_one(double(5))) = 121
```

## wraps - Preserve Function Metadata

```python
# Without wraps
def decorator_without_wraps(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# With wraps
def decorator_with_wraps(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@decorator_without_wraps
def func1():
    """This is func1's docstring."""
    pass

@decorator_with_wraps
def func2():
    """This is func2's docstring."""
    pass

print("\n--- wraps ---")
print(f"Without wraps: name={func1.__name__}, doc={func1.__doc__}")
print(f"With wraps: name={func2.__name__}, doc={func2.__doc__}")
```

## total_ordering - Complete Comparisons

```python
@total_ordering
class Money:
    """Money class with complete ordering from just __eq__ and __lt__."""

    def __init__(self, amount, currency="USD"):
        self.amount = amount
        self.currency = currency

    def __eq__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __lt__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError("Cannot compare different currencies")
        return self.amount < other.amount

    def __repr__(self):
        return f"Money({self.amount}, '{self.currency}')"

m1 = Money(100)
m2 = Money(200)

print("\n--- total_ordering ---")
print(f"{m1} < {m2}: {m1 < m2}")
print(f"{m1} <= {m2}: {m1 <= m2}")
print(f"{m1} > {m2}: {m1 > m2}")
print(f"{m1} >= {m2}: {m1 >= m2}")
```

## singledispatch - Function Overloading

```python
@singledispatch
def process(data):
    """Process data based on type."""
    raise NotImplementedError(f"Cannot process type: {type(data)}")

@process.register
def _(data: str):
    return f"Processing string: {data.upper()}"

@process.register
def _(data: int):
    return f"Processing integer: {data * 2}"

@process.register
def _(data: list):
    return f"Processing list of {len(data)} items"

@process.register(dict)  # Alternative syntax
def _(data):
    return f"Processing dict with keys: {list(data.keys())}"

print("\n--- singledispatch ---")
print(process("hello"))
print(process(42))
print(process([1, 2, 3]))
print(process({"a": 1, "b": 2}))
```

## PRACTICAL EXAMPLES

```python
# 1. Cached database query
@lru_cache(maxsize=1000)
def get_user_by_id(user_id: int):
    """Simulate database query with caching."""
    print(f"  Fetching user {user_id} from database...")
    return {"id": user_id, "name": f"User_{user_id}"}

print("\n--- Cached Database Query ---")
print(get_user_by_id(1))
print(get_user_by_id(1))  # Cached!
print(get_user_by_id(2))


# 2. Partial for callback configuration
def send_notification(message, channel, priority="normal"):
    return f"[{priority.upper()}] {channel}: {message}"

# Pre-configure channels
slack_alert = partial(send_notification, channel="slack", priority="high")
email_notify = partial(send_notification, channel="email")

print("\n--- Partial for Callbacks ---")
print(slack_alert("Server down!"))
print(email_notify("Weekly report ready"))


# 3. Reduce for data aggregation
data_points = [
    {"value": 10, "weight": 1},
    {"value": 20, "weight": 2},
    {"value": 30, "weight": 3},
]

def weighted_avg_reducer(acc, item):
    return {
        "sum": acc["sum"] + item["value"] * item["weight"],
        "weight_sum": acc["weight_sum"] + item["weight"]
    }

result = reduce(weighted_avg_reducer, data_points, {"sum": 0, "weight_sum": 0})
weighted_avg = result["sum"] / result["weight_sum"]
print(f"\n--- Reduce for Aggregation ---")
print(f"Weighted average: {weighted_avg}")
```
