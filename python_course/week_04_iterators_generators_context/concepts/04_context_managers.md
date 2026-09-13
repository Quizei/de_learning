# Context Managers in Python

Manage resources with 'with' statement.
Ensure proper setup and cleanup.

## BASIC CONTEXT MANAGER

```python
# The 'with' statement
with open('temp.txt', 'w') as f:
    f.write('Hello, World!')

# Is equivalent to:
f = open('temp.txt', 'w')
try:
    f.write('Hello again!')
finally:
    f.close()

# Clean up temp file
import os
os.remove('temp.txt')
```

## CONTEXT MANAGER PROTOCOL

```python
class ManagedResource:
    """Custom context manager using __enter__ and __exit__."""

    def __init__(self, name):
        self.name = name
        print(f"Creating resource: {name}")

    def __enter__(self):
        """Called when entering 'with' block. Return value is assigned to 'as' variable."""
        print(f"Entering context: {self.name}")
        return self  # This is what gets assigned to 'as' variable

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Called when exiting 'with' block.

        Args:
            exc_type: Exception type if exception occurred, None otherwise
            exc_val: Exception value if exception occurred, None otherwise
            exc_tb: Traceback if exception occurred, None otherwise

        Returns:
            True to suppress exception, False to propagate it
        """
        print(f"Exiting context: {self.name}")
        if exc_type:
            print(f"Exception occurred: {exc_type.__name__}: {exc_val}")
        return False  # Don't suppress exceptions

    def do_something(self):
        print(f"Doing something with {self.name}")


print("--- Basic Context Manager ---")
with ManagedResource("MyResource") as resource:
    resource.do_something()
```

## EXCEPTION HANDLING

```python
class ExceptionHandler:
    """Context manager that handles exceptions."""

    def __init__(self, suppress=False):
        self.suppress = suppress

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            print(f"Caught exception: {exc_type.__name__}: {exc_val}")
        return self.suppress  # True suppresses, False propagates


print("\n--- Exception Handling ---")

# Suppress exception
with ExceptionHandler(suppress=True):
    print("About to raise...")
    raise ValueError("Test error")
    print("This won't print")

print("Continued after suppressed exception")

# Don't suppress (would propagate)
# with ExceptionHandler(suppress=False):
#     raise ValueError("This would propagate")
```

## CONTEXTLIB MODULE

```python
from contextlib import contextmanager, closing, suppress, redirect_stdout

# @contextmanager decorator - simpler way to create context managers
@contextmanager
def timer(name):
    """Time a block of code."""
    import time
    start = time.perf_counter()
    print(f"Starting {name}")
    try:
        yield  # Control passes to 'with' block here
    finally:
        elapsed = time.perf_counter() - start
        print(f"Finished {name} in {elapsed:.4f}s")


print("\n--- @contextmanager ---")
with timer("my operation"):
    import time
    time.sleep(0.1)


# Context manager that yields a value
@contextmanager
def temporary_value(obj, attr, value):
    """Temporarily set an attribute."""
    original = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield
    finally:
        setattr(obj, attr, original)


class Config:
    debug = False


print("\n--- Temporary Value ---")
config = Config()
print(f"Before: debug = {config.debug}")
with temporary_value(config, 'debug', True):
    print(f"Inside: debug = {config.debug}")
print(f"After: debug = {config.debug}")
```

## CLOSING

```python
from contextlib import closing

class NonClosingResource:
    """Resource that doesn't have context manager protocol."""

    def fetch(self):
        return "data"

    def close(self):
        print("Closed!")


print("\n--- closing() ---")
with closing(NonClosingResource()) as resource:
    print(resource.fetch())
# close() is called automatically
```

## SUPPRESS

```python
print("\n--- suppress() ---")

# Instead of try/except pass
with suppress(FileNotFoundError):
    os.remove('nonexistent_file.txt')
print("Continued without error")
```

## NESTED CONTEXT MANAGERS

```python
print("\n--- Nested Context Managers ---")

# Multiple with statements
with timer("outer"), timer("inner"):
    import time
    time.sleep(0.05)

# Or using ExitStack for dynamic number
from contextlib import ExitStack

@contextmanager
def managed_file(name):
    print(f"Opening {name}")
    try:
        yield f"file:{name}"
    finally:
        print(f"Closing {name}")


print("\n--- ExitStack ---")
files = ['a.txt', 'b.txt', 'c.txt']

with ExitStack() as stack:
    handles = [stack.enter_context(managed_file(f)) for f in files]
    print(f"All files: {handles}")
# All files closed when exiting
```

## PRACTICAL EXAMPLES

```python
# 1. Database transaction
@contextmanager
def transaction(connection):
    """Database transaction context manager."""
    cursor = connection.cursor()
    try:
        yield cursor
        connection.commit()
        print("Transaction committed")
    except Exception as e:
        connection.rollback()
        print(f"Transaction rolled back: {e}")
        raise


# 2. Temporary directory
@contextmanager
def temp_directory():
    """Create and cleanup temporary directory."""
    import tempfile
    import shutil

    dirpath = tempfile.mkdtemp()
    print(f"Created temp dir: {dirpath}")
    try:
        yield dirpath
    finally:
        shutil.rmtree(dirpath)
        print(f"Removed temp dir: {dirpath}")


print("\n--- Temp Directory ---")
with temp_directory() as tmpdir:
    print(f"Working in: {tmpdir}")


# 3. Changed directory
@contextmanager
def changed_directory(path):
    """Temporarily change working directory."""
    import os
    original = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


# 4. Locked resource
import threading

@contextmanager
def locked(lock):
    """Acquire lock for duration of block."""
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


# 5. Timing with statistics
@contextmanager
def timed_block(stats, name):
    """Record timing statistics."""
    import time
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        if name not in stats:
            stats[name] = []
        stats[name].append(elapsed)


print("\n--- Timing Statistics ---")
stats = {}

for i in range(3):
    with timed_block(stats, "operation"):
        import time
        time.sleep(0.01)

print(f"Timings: {stats}")
```

## ASYNC CONTEXT MANAGERS

```python
print("\n--- Async Context Managers (preview) ---")
print("""
For async code, use __aenter__ and __aexit__:

class AsyncResource:
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        return False

# Usage:
async with AsyncResource() as resource:
    await resource.do_something()

# Or with @asynccontextmanager from contextlib:
from contextlib import asynccontextmanager

@asynccontextmanager
async def async_timer():
    start = time.time()
    try:
        yield
    finally:
        print(f"Elapsed: {time.time() - start}")
""")
```
