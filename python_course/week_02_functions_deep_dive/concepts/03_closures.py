"""
Closures in Python
==================
A closure is a function that remembers values from its enclosing scope
even after that scope has finished executing.
"""

# ================================
# BASIC CLOSURE
# ================================

def outer_function(message):
    """Outer function that creates a closure."""

    def inner_function():
        """Inner function that 'closes over' message."""
        print(f"Message: {message}")

    return inner_function

# Create closures
hello_closure = outer_function("Hello, World!")
goodbye_closure = outer_function("Goodbye!")

# Call them - they remember their messages
hello_closure()    # "Message: Hello, World!"
goodbye_closure()  # "Message: Goodbye!"

# The outer function has finished, but inner still has access to 'message'


# ================================
# HOW CLOSURES WORK
# ================================

def make_counter():
    """Create a counter using closure."""
    count = 0  # This is the enclosed variable

    def counter():
        count  # Required to modify enclosed variable
        count += 1
        return count

    return counter

# Create independent counters
counter1 = make_counter()
counter2 = make_counter()

print("\n--- Counter Closures ---")
print("Counter 1:", counter1())  # 1
print("Counter 1:", counter1())  # 2
print("Counter 1:", counter1())  # 3
print("Counter 2:", counter2())  # 1 (independent)
print("Counter 1:", counter1())  # 4

# Check the closure's enclosed variables
print("\nClosure variables:", counter1.__closure__)
print("Cell contents:", counter1.__closure__[0].cell_contents)


# ================================
# THE `nonlocal` KEYWORD
# ================================

def outer():
    x = 10

    def inner():
        # Without nonlocal, this creates a new local variable
        # x = 20  # This would create a new local x

        nonlocal x  # Now we're modifying the outer x
        x = 20

    print(f"Before inner(): x = {x}")
    inner()
    print(f"After inner(): x = {x}")

print("\n--- nonlocal keyword ---")
outer()


# ================================
# PRACTICAL CLOSURE EXAMPLES
# ================================

# 1. Multiplier factory
def make_multiplier(factor):
    """Create a multiplier function."""
    def multiply(n):
        return n * factor
    return multiply

double = make_multiplier(2)
triple = make_multiplier(3)

print("\n--- Multiplier Factory ---")
print("Double 5:", double(5))
print("Triple 5:", triple(5))


# 2. Logger with prefix
def make_logger(prefix):
    """Create a logger with a specific prefix."""
    def log(message):
        print(f"[{prefix}] {message}")
    return log

error_log = make_logger("ERROR")
info_log = make_logger("INFO")

print("\n--- Logger Factory ---")
error_log("Connection failed")
info_log("User logged in")


# 3. Accumulator
def make_accumulator(initial=0):
    """Create an accumulator that remembers running total."""
    total = initial

    def add(value):
        nonlocal total
        total += value
        return total

    def get_total():
        return total

    def reset():
        nonlocal total
        total = initial

    # Return multiple functions sharing the same closure
    return add, get_total, reset

add, get_total, reset = make_accumulator(100)

print("\n--- Accumulator ---")
print("Add 10:", add(10))    # 110
print("Add 20:", add(20))    # 130
print("Total:", get_total()) # 130
reset()
print("After reset:", get_total())  # 100


# 4. Rate limiter
def make_rate_limiter(max_calls, period_seconds=60):
    """Create a rate limiter closure."""
    import time
    calls = []

    def is_allowed():
        nonlocal calls
        current_time = time.time()

        # Remove calls outside the period
        calls = [t for t in calls if current_time - t < period_seconds]

        if len(calls) < max_calls:
            calls.append(current_time)
            return True
        return False

    return is_allowed

# Allow 3 calls per minute
check_rate = make_rate_limiter(3, 60)

print("\n--- Rate Limiter ---")
for i in range(5):
    print(f"Call {i+1}: {'Allowed' if check_rate() else 'Rate limited'}")


# 5. Memoization (caching)
def make_memoized(func):
    """Create a memoized version of a function."""
    cache = {}

    def memoized(*args):
        if args not in cache:
            cache[args] = func(*args)
            print(f"  Cache miss: computing {func.__name__}{args}")
        else:
            print(f"  Cache hit: returning cached {func.__name__}{args}")
        return cache[args]

    return memoized

def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# Without memoization - slow!
# print(fibonacci(35))

# With memoization
fib_memo = make_memoized(fibonacci)

print("\n--- Memoization ---")
# Note: This simple example won't fully memoize recursive calls
# For that, you'd need to replace the function itself
print("fib(10):", fib_memo(10))
print("fib(10):", fib_memo(10))  # Cached!


# ================================
# COMMON CLOSURE PITFALL
# ================================

def create_multipliers_wrong():
    """Common mistake with closures in loops."""
    multipliers = []
    for i in range(5):
        def multiply(x):
            return x * i  # i is captured by reference!
        multipliers.append(multiply)
    return multipliers

def create_multipliers_correct():
    """Fixed version using default argument."""
    multipliers = []
    for i in range(5):
        def multiply(x, factor=i):  # Capture current value
            return x * factor
        multipliers.append(multiply)
    return multipliers

print("\n--- Closure Pitfall ---")
wrong = create_multipliers_wrong()
correct = create_multipliers_correct()

print("Wrong (all use i=4):", [m(10) for m in wrong])    # [40, 40, 40, 40, 40]
print("Correct:", [m(10) for m in correct])              # [0, 10, 20, 30, 40]
