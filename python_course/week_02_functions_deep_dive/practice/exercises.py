"""
Week 2 Practice Exercises: Functions Deep Dive
===============================================
Complete each exercise. Solutions are at the bottom.
"""

from functools import wraps
import time

# ================================
# EXERCISE 1: Higher-Order Function
# ================================
"""
Create a function `apply_to_all` that takes a list of numbers and a function,
and returns a new list with the function applied to each element.

Example:
    apply_to_all([1, 2, 3], lambda x: x * 2) -> [2, 4, 6]
    apply_to_all([1, 4, 9], lambda x: x ** 0.5) -> [1.0, 2.0, 3.0]
"""

def apply_to_all(numbers, func):
    result = []
    for number in numbers:
       result.append(func(number))
    return result


# ================================
# EXERCISE 2: Closure - Counter Factory
# ================================
"""
Create a function `make_counter` that returns a counter function.
The counter should:
- Start from 0 (or a given start value)
- Increment by 1 (or a given step) each time it's called
- Return the current count

Example:
    counter = make_counter()
    counter() -> 1
    counter() -> 2

    counter2 = make_counter(start=10, step=5)
    counter2() -> 15
    counter2() -> 20
"""

def make_counter(start=0, step=1):
    current = start
    def counter():
        nonlocal current
        value = current
        current += step
        return value
    return counter

# ================================
# EXERCISE 3: Basic Decorator
# ================================
"""
Create a decorator `uppercase_result` that converts the string result
of a function to uppercase.

Example:
    @uppercase_result
    def greet(name):
        return f"hello, {name}"

    greet("alice") -> "HELLO, ALICE"
"""
def uppercase_result(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result.upper()
    return wrapper


# ================================
# EXERCISE 4: Decorator with Arguments
# ================================
"""
Create a decorator `repeat(n)` that calls the decorated function n times
and returns a list of all results.

Example:
    @repeat(3)
    def get_random():
        import random
        return random.randint(1, 100)

    get_random() -> [45, 78, 12]  # (random values)
"""

def repeat(n):
    # Your code here
    pass


# ================================
# EXERCISE 5: Timer Decorator
# ================================
"""
Create a decorator `timed` that:
- Measures execution time of the function
- Prints the time taken
- Returns both the result and the time as a tuple

Example:
    @timed
    def slow_func():
        time.sleep(0.1)
        return "done"

    result, elapsed = slow_func()
    # Prints: "slow_func took 0.1003 seconds"
    # result = "done", elapsed ≈ 0.1
"""

def timed(func):
    # Your code here
    pass


# ================================
# EXERCISE 6: Memoization Decorator
# ================================
"""
Create a decorator `memoize` that caches function results.
The cache should be accessible via `function.cache`.

Example:
    @memoize
    def expensive_func(n):
        time.sleep(0.01)  # Simulate expensive operation
        return n * 2

    expensive_func(5)  # Slow
    expensive_func(5)  # Fast (cached)
    print(expensive_func.cache)  # {(5,): 10}
"""

from functools import wraps

def memoize(func):
    cache = {}

    @wraps(func)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))

        if key in cache:
            return cache[key]

        result = func(*args, **kwargs)
        cache[key] = result
        return result

    wrapper.cache = cache  
    return wrapper


# ================================
# EXERCISE 7: Validate Decorator
# ================================
"""
Create a decorator `validate_positive` that raises ValueError
if any numeric argument is negative.

Example:
    @validate_positive
    def calculate_area(width, height):
        return width * height

    calculate_area(5, 3) -> 15
    calculate_area(-5, 3) -> ValueError: "Negative values not allowed"
"""

def validate_positive(func):
    # Your code here
    pass


# ================================
# EXERCISE 8: Retry Decorator
# ================================
"""
Create a decorator `retry(max_attempts, exceptions)` that:
- Retries the function on specified exceptions
- Stops after max_attempts
- Raises the last exception if all attempts fail

Example:
    @retry(max_attempts=3, exceptions=(ValueError,))
    def unstable_func():
        import random
        if random.random() < 0.7:
            raise ValueError("Random failure")
        return "Success"
"""

import time 

def retry(max_attempts=3, exceptions=(Exception,) , delay = 2):
    def decorator_outer(fun):
        def decorator_inner(*args , **kwargs):
            for attempt in range(0,max_attempts):
                try:
                    return fun(*args , **kwargs)
                except exceptions as e:
                    if attempt == max_attempts-1:
                        raise 
                    
                    print(f"attempt no {attempt + 1} Retrying...")
                    time.sleep(delay)
        return decorator_inner
    return decorator_outer
    
@retry(max_attempts=3, exceptions=(ValueError,), delay =1)
def unstable_func():
    import random
    if random.random() < 0.7:
        raise ValueError("Random failure")
    return "Success"
    
print(unstable_func())


# ================================
# EXERCISE 9: Compose Functions
# ================================
"""
Create a function `compose` that takes multiple functions and returns
a new function that applies them from right to left.

Example:
    add_one = lambda x: x + 1
    double = lambda x: x * 2
    square = lambda x: x ** 2

    f = compose(square, double, add_one)
    f(3) -> 64  # square(double(add_one(3))) = square(double(4)) = square(8) = 64
"""

def compose(*functions):
    def composed(value):
        for func in reversed(functions):  
            value = func(value)
        return value
    return composed

# ================================
# EXERCISE 10: Pipeline Decorator
# ================================
"""
Create a decorator `pipeline` that allows chaining transformations.
The decorated function should have an `add_step` method to add transformations.

Example:
    @pipeline
    def process(data):
        return data

    process.add_step(lambda x: x.strip())
    process.add_step(lambda x: x.upper())
    process.add_step(lambda x: x.replace(" ", "_"))

    process("  hello world  ") -> "HELLO_WORLD"
"""

def pipeline(func):
    steps = []
    def decorator(*args):
        result = func(*args)
        for step in steps:
            result = step(result)
        return result
        
    def add_step(step_func):
        steps.append(step_func)

    decorator.add_step = add_step
    
    return decorator
        
@pipeline
def process(data):
    return data

process.add_step(lambda x: x.strip())
process.add_step(lambda x: x.upper())
process.add_step(lambda x: x.replace(" ", "_"))

print(process("  hello world  ") )


# ================================================================
# SOLUTIONS (Don't look until you've tried!)
# ================================================================
"""
Scroll down for solutions...



















"""

def show_solutions():
    print("=" * 50)
    print("SOLUTIONS")
    print("=" * 50)

    # Exercise 1
    print("\n--- Exercise 1: apply_to_all ---")
    def apply_to_all(numbers, func):
        return [func(n) for n in numbers]

    print(apply_to_all([1, 2, 3], lambda x: x * 2))
    print(apply_to_all([1, 4, 9], lambda x: x ** 0.5))

    # Exercise 2
    print("\n--- Exercise 2: make_counter ---")
    def make_counter(start=0, step=1):
        count = start
        def counter():
            nonlocal count
            count += step
            return count
        return counter

    c1 = make_counter()
    print(c1(), c1(), c1())
    c2 = make_counter(start=10, step=5)
    print(c2(), c2())

    # Exercise 3
    print("\n--- Exercise 3: uppercase_result ---")
    def uppercase_result(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return result.upper() if isinstance(result, str) else result
        return wrapper

    @uppercase_result
    def greet(name):
        return f"hello, {name}"

    print(greet("alice"))

    # Exercise 4
    print("\n--- Exercise 4: repeat ---")
    def repeat(n):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return [func(*args, **kwargs) for _ in range(n)]
            return wrapper
        return decorator

    @repeat(3)
    def get_value():
        return 42

    print(get_value())

    # Exercise 5
    print("\n--- Exercise 5: timed ---")
    def timed(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            print(f"{func.__name__} took {elapsed:.4f} seconds")
            return result, elapsed
        return wrapper

    @timed
    def slow_func():
        time.sleep(0.05)
        return "done"

    result, elapsed = slow_func()
    print(f"Result: {result}")

    # Exercise 6
    print("\n--- Exercise 6: memoize ---")
    def memoize(func):
        cache = {}
        @wraps(func)
        def wrapper(*args):
            if args not in cache:
                cache[args] = func(*args)
            return cache[args]
        wrapper.cache = cache
        return wrapper

    @memoize
    def double(n):
        return n * 2

    print(double(5), double(5))
    print("Cache:", double.cache)

    # Exercise 7
    print("\n--- Exercise 7: validate_positive ---")
    def validate_positive(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for arg in args:
                if isinstance(arg, (int, float)) and arg < 0:
                    raise ValueError("Negative values not allowed")
            for val in kwargs.values():
                if isinstance(val, (int, float)) and val < 0:
                    raise ValueError("Negative values not allowed")
            return func(*args, **kwargs)
        return wrapper

    @validate_positive
    def calc_area(w, h):
        return w * h

    print(calc_area(5, 3))
    try:
        calc_area(-5, 3)
    except ValueError as e:
        print(f"Error: {e}")

    # Exercise 8
    print("\n--- Exercise 8: retry ---")
    def retry(max_attempts=3, exceptions=(Exception,)):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        print(f"Attempt {attempt + 1} failed")
                raise last_exception
            return wrapper
        return decorator

    attempt_count = [0]
    @retry(max_attempts=3, exceptions=(ValueError,))
    def sometimes_fails():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ValueError("Failed")
        return "Success"

    print(sometimes_fails())

    # Exercise 9
    print("\n--- Exercise 9: compose ---")
    from functools import reduce

    def compose(*functions):
        return reduce(lambda f, g: lambda x: f(g(x)), functions)

    add_one = lambda x: x + 1
    double = lambda x: x * 2
    square = lambda x: x ** 2

    f = compose(square, double, add_one)
    print(f"compose(square, double, add_one)(3) = {f(3)}")

    # Exercise 10
    print("\n--- Exercise 10: pipeline ---")
    def pipeline(func):
        steps = []

        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            for step in steps:
                result = step(result)
            return result

        def add_step(step_func):
            steps.append(step_func)

        wrapper.add_step = add_step
        return wrapper

    @pipeline
    def process(data):
        return data

    process.add_step(lambda x: x.strip())
    process.add_step(lambda x: x.upper())
    process.add_step(lambda x: x.replace(" ", "_"))

    print(process("  hello world  "))


if __name__ == "__main__":
    print("Complete the exercises above, then run show_solutions()")
    # Uncomment to see solutions:
    # show_solutions()
