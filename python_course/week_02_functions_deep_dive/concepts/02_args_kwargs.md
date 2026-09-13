# *args and **kwargs

Flexible function parameters for variable arguments.

## *args - Variable Positional Arguments

```python
def sum_all(*args):
    """Accept any number of positional arguments."""
    print(f"args is a tuple: {args}")
    return sum(args)

print("Sum:", sum_all(1, 2, 3, 4, 5))  # 15
print("Sum:", sum_all(10, 20))          # 30

# Combine with regular parameters
def greet(greeting, *names):
    """Greet multiple people."""
    for name in names:
        print(f"{greeting}, {name}!")

print("\n--- Combined with regular params ---")
greet("Hello", "Alice", "Bob", "Charlie")
```

## **kwargs - Variable Keyword Arguments

```python
def print_info(**kwargs):
    """Accept any number of keyword arguments."""
    print(f"kwargs is a dict: {kwargs}")
    for key, value in kwargs.items():
        print(f"  {key}: {value}")

print("\n--- **kwargs ---")
print_info(name="Alice", age=30, city="NYC")


# Combine with regular and keyword-only parameters
def create_user(username, *, admin=False, **extra):
    """Create user with flexible extra fields."""
    user = {"username": username, "admin": admin}
    user.update(extra)
    return user

print("\n--- Combined kwargs ---")
user = create_user("alice", email="alice@example.com", department="Engineering")
print(user)
```

## *args AND **kwargs TOGETHER

```python
def flexible_function(*args, **kwargs):
    """Accept both positional and keyword arguments."""
    print(f"Positional: {args}")
    print(f"Keyword: {kwargs}")

print("\n--- Both together ---")
flexible_function(1, 2, 3, name="Alice", age=30)


# Order of parameters: regular, *args, keyword-only, **kwargs
def complete_example(a, b, *args, option=None, **kwargs):
    """Demonstrates all parameter types."""
    print(f"a={a}, b={b}")
    print(f"args={args}")
    print(f"option={option}")
    print(f"kwargs={kwargs}")

print("\n--- Complete example ---")
complete_example(1, 2, 3, 4, 5, option="test", extra="value")
```

## UNPACKING ARGUMENTS

```python
def add_three(a, b, c):
    return a + b + c

# Unpack list/tuple with *
numbers = [1, 2, 3]
print("\n--- Unpacking ---")
print("Unpacked list:", add_three(*numbers))

# Unpack dict with **
def introduce(name, age, city):
    return f"{name} is {age} years old from {city}"

person = {"name": "Alice", "age": 30, "city": "NYC"}
print("Unpacked dict:", introduce(**person))
```

## REAL-WORLD USE CASES

```python
# 1. Wrapper/Decorator pattern (preserves original signature)
def logging_wrapper(func):
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        result = func(*args, **kwargs)
        print(f"Result: {result}")
        return result
    return wrapper

@logging_wrapper
def calculate(a, b, operation="add"):
    if operation == "add":
        return a + b
    return a - b

print("\n--- Wrapper Pattern ---")
calculate(5, 3, operation="add")


# 2. Configuration with defaults
def connect_to_database(host, port=5432, **options):
    """Connect with flexible options."""
    config = {
        "host": host,
        "port": port,
        "timeout": options.get("timeout", 30),
        "retry": options.get("retry", 3),
        "ssl": options.get("ssl", True),
    }
    print(f"Connecting with config: {config}")
    return config

print("\n--- Flexible Config ---")
connect_to_database("localhost", timeout=60, ssl=False)


# 3. Function composition
def compose(*functions):
    """Compose multiple functions into one."""
    def composed(x):
        result = x
        for func in reversed(functions):
            result = func(result)
        return result
    return composed

double = lambda x: x * 2
add_one = lambda x: x + 1
square = lambda x: x ** 2

# Create composed function
f = compose(square, add_one, double)
print("\n--- Function Composition ---")
print("compose(square, add_one, double)(3):", f(3))  # square(add_one(double(3))) = 49


# 4. Building SQL queries (simplified example)
def build_query(table, *columns, **conditions):
    """Build a simple SELECT query."""
    cols = ", ".join(columns) if columns else "*"
    query = f"SELECT {cols} FROM {table}"

    if conditions:
        where_clauses = [f"{k} = '{v}'" for k, v in conditions.items()]
        query += " WHERE " + " AND ".join(where_clauses)

    return query

print("\n--- Query Builder ---")
print(build_query("users"))
print(build_query("users", "name", "email"))
print(build_query("users", "name", "email", status="active", role="admin"))
```
