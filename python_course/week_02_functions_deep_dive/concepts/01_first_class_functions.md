# First-Class Functions in Python

Functions are first-class citizens in Python, meaning:
- They can be assigned to variables
- They can be passed as arguments
- They can be returned from other functions
- They can be stored in data structures

## FUNCTIONS AS OBJECTS

```python
def greet(name):
    """Simple greeting function."""
    return f"Hello, {name}!"

# Functions have attributes
print("Function name:", greet.__name__)
print("Docstring:", greet.__doc__)

# Assign function to variable (no parentheses = reference to function)
say_hello = greet
print(say_hello("Alice"))  # "Hello, Alice!"

# The variable holds a reference to the same function
print(greet is say_hello)  # True
```

## FUNCTIONS AS ARGUMENTS

```python
def apply_operation(func, x, y):
    """Apply a function to two arguments."""
    return func(x, y)

def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

print("\n--- Functions as Arguments ---")
print("Add:", apply_operation(add, 5, 3))        # 8
print("Multiply:", apply_operation(multiply, 5, 3))  # 15


# Real-world example: Custom sorting
users = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25},
    {"name": "Charlie", "age": 35},
]

# Sort by age using key function
sorted_by_age = sorted(users, key=lambda u: u["age"])
print("\nSorted by age:", [u["name"] for u in sorted_by_age])

# Using a named function as key
def get_name(user):
    return user["name"]

sorted_by_name = sorted(users, key=get_name)
print("Sorted by name:", [u["name"] for u in sorted_by_name])
```

## FUNCTIONS RETURNING FUNCTIONS

```python
def create_multiplier(n):
    """Return a function that multiplies by n."""
    def multiplier(x):
        return x * n
    return multiplier

double = create_multiplier(2)
triple = create_multiplier(3)

print("\n--- Functions Returning Functions ---")
print("Double 5:", double(5))  # 10
print("Triple 5:", triple(5))  # 15


def create_greeting(greeting_word):
    """Factory function for greetings."""
    def greet(name):
        return f"{greeting_word}, {name}!"
    return greet

say_hi = create_greeting("Hi")
say_goodbye = create_greeting("Goodbye")

print(say_hi("Alice"))      # "Hi, Alice!"
print(say_goodbye("Bob"))   # "Goodbye, Bob!"
```

## FUNCTIONS IN DATA STRUCTURES

```python
def square(x):
    return x ** 2

def cube(x):
    return x ** 3

def sqrt(x):
    return x ** 0.5

# Store functions in a list
operations = [square, cube, sqrt]

print("\n--- Functions in Lists ---")
for op in operations:
    print(f"{op.__name__}(4) = {op(4)}")

# Store functions in a dictionary
math_ops = {
    "square": square,
    "cube": cube,
    "sqrt": sqrt,
}

# Call by name
print("\nUsing dict:", math_ops["cube"](3))  # 27
```

## HIGHER-ORDER FUNCTIONS

```python
# Functions that take or return functions are called higher-order functions

print("\n--- Higher-Order Functions ---")

# Built-in higher-order functions
numbers = [1, 2, 3, 4, 5]

# map: apply function to all elements
squared = list(map(lambda x: x**2, numbers))
print("map (square):", squared)

# filter: keep elements where function returns True
evens = list(filter(lambda x: x % 2 == 0, numbers))
print("filter (even):", evens)

# Custom higher-order function
def transform_data(data, transformers):
    """Apply multiple transformations to data."""
    result = data
    for transform in transformers:
        result = transform(result)
    return result

# Pipeline of transformations
pipeline = [
    lambda x: x * 2,      # double
    lambda x: x + 10,     # add 10
    lambda x: x ** 2,     # square
]

result = transform_data(5, pipeline)
print(f"\nPipeline result: {result}")  # ((5 * 2) + 10) ** 2 = 400
```

## PRACTICAL EXAMPLE: VALIDATOR FACTORY

```python
def create_validator(min_val, max_val):
    """Create a validator function for a range."""
    def validate(value):
        if min_val <= value <= max_val:
            return True, f"{value} is valid"
        return False, f"{value} is out of range [{min_val}, {max_val}]"
    return validate

# Create validators
age_validator = create_validator(0, 120)
percentage_validator = create_validator(0, 100)

print("\n--- Validator Factory ---")
print(age_validator(25))    # (True, '25 is valid')
print(age_validator(150))   # (False, '150 is out of range [0, 120]')
print(percentage_validator(85))  # (True, '85 is valid')
```
