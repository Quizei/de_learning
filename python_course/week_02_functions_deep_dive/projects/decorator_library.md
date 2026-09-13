# Week 2 Project: Decorator Library

Build a collection of production-ready decorators for data engineering tasks.

This project applies:
- Closures for state management
- Decorators with arguments
- functools for proper wrapping
- Error handling patterns

```python
import time
import logging
from functools import wraps, lru_cache
from typing import Callable, Any, Optional, Tuple
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

## 1. TIMING DECORATOR

```python
def timeit(func: Callable = None, *, log_level: str = "INFO") -> Callable:
    """
    Measure and log execution time.

    Can be used with or without arguments:
        @timeit
        @timeit(log_level="DEBUG")
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = fn(*args, **kwargs)
            elapsed = time.perf_counter() - start

            log_func = getattr(logger, log_level.lower())
            log_func(f"{fn.__name__} executed in {elapsed:.4f}s")

            return result
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
```

## 2. RETRY DECORATOR

```python
def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple = (Exception,),
    on_failure: Callable = None
) -> Callable:
    """
    Retry a function on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch
        on_failure: Callback function on final failure
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}"
                    )

                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff

            logger.error(f"{func.__name__} failed after {max_attempts} attempts")

            if on_failure:
                on_failure(last_exception)

            raise last_exception

        return wrapper
    return decorator
```

## 3. CACHE WITH TTL

```python
def cache_with_ttl(ttl_seconds: int = 300) -> Callable:
    """
    Cache function results with time-to-live.

    Args:
        ttl_seconds: Time in seconds before cache entry expires
    """
    def decorator(func: Callable) -> Callable:
        cache = {}

        @wraps(func)
        def wrapper(*args):
            current_time = time.time()

            # Check cache
            if args in cache:
                result, timestamp = cache[args]
                if current_time - timestamp < ttl_seconds:
                    logger.debug(f"Cache hit for {func.__name__}{args}")
                    return result
                else:
                    logger.debug(f"Cache expired for {func.__name__}{args}")

            # Compute and cache
            result = func(*args)
            cache[args] = (result, current_time)
            return result

        def clear_cache():
            cache.clear()

        def cache_info():
            return {
                "size": len(cache),
                "keys": list(cache.keys())
            }

        wrapper.clear_cache = clear_cache
        wrapper.cache_info = cache_info
        return wrapper

    return decorator
```

## 4. RATE LIMITER

```python
def rate_limit(calls: int, period: float) -> Callable:
    """
    Limit function call rate.

    Args:
        calls: Maximum number of calls allowed
        period: Time period in seconds
    """
    def decorator(func: Callable) -> Callable:
        call_times = []

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal call_times
            current_time = time.time()

            # Remove old calls outside the period
            call_times = [t for t in call_times if current_time - t < period]

            if len(call_times) >= calls:
                wait_time = period - (current_time - call_times[0])
                logger.warning(
                    f"Rate limit reached for {func.__name__}. "
                    f"Waiting {wait_time:.2f}s"
                )
                time.sleep(wait_time)
                call_times = call_times[1:]

            call_times.append(time.time())
            return func(*args, **kwargs)

        return wrapper
    return decorator
```

## 5. VALIDATE ARGUMENTS

```python
def validate(**validators) -> Callable:
    """
    Validate function arguments using custom validators.

    Example:
        @validate(
            age=lambda x: x >= 0,
            name=lambda x: len(x) > 0
        )
        def create_user(name, age): ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get argument names
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each argument
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    if not validator(value):
                        raise ValueError(
                            f"Validation failed for '{param_name}': {value}"
                        )

            return func(*args, **kwargs)
        return wrapper
    return decorator
```

## 6. LOG EXECUTION

```python
def log_execution(
    include_args: bool = True,
    include_result: bool = False,
    log_level: str = "INFO"
) -> Callable:
    """
    Log function execution details.

    Args:
        include_args: Whether to log function arguments
        include_result: Whether to log return value
        log_level: Logging level to use
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            log_func = getattr(logger, log_level.lower())

            # Log start
            if include_args:
                log_func(
                    f"Calling {func.__name__} with "
                    f"args={args}, kwargs={kwargs}"
                )
            else:
                log_func(f"Calling {func.__name__}")

            try:
                result = func(*args, **kwargs)

                if include_result:
                    log_func(f"{func.__name__} returned: {result}")
                else:
                    log_func(f"{func.__name__} completed successfully")

                return result

            except Exception as e:
                logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
                raise

        return wrapper
    return decorator
```

## 7. DEPRECATION WARNING

```python
def deprecated(message: str = None, replacement: str = None) -> Callable:
    """
    Mark a function as deprecated.

    Args:
        message: Custom deprecation message
        replacement: Suggested replacement function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import warnings

            warn_msg = f"{func.__name__} is deprecated."
            if message:
                warn_msg += f" {message}"
            if replacement:
                warn_msg += f" Use {replacement} instead."

            warnings.warn(warn_msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper
    return decorator
```

## 8. SINGLETON PATTERN

```python
def singleton(cls):
    """
    Make a class a singleton.
    Only one instance will ever be created.
    """
    instances = {}

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
```

## 9. RUN IN THREAD

```python
def run_async(func: Callable) -> Callable:
    """
    Run a function in a separate thread.
    Returns a Future-like object.
    """
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=4)

    @wraps(func)
    def wrapper(*args, **kwargs):
        return executor.submit(func, *args, **kwargs)

    return wrapper
```

## 10. CIRCUIT BREAKER

```python
def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0
) -> Callable:
    """
    Implement circuit breaker pattern.

    Opens circuit after failure_threshold failures,
    waits recovery_timeout before allowing retry.
    """
    def decorator(func: Callable) -> Callable:
        failures = 0
        last_failure_time = 0
        circuit_open = False

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal failures, last_failure_time, circuit_open

            # Check if circuit should be reset
            if circuit_open:
                if time.time() - last_failure_time > recovery_timeout:
                    logger.info(f"Circuit breaker reset for {func.__name__}")
                    circuit_open = False
                    failures = 0
                else:
                    raise RuntimeError(
                        f"Circuit open for {func.__name__}. "
                        f"Try again in {recovery_timeout - (time.time() - last_failure_time):.1f}s"
                    )

            try:
                result = func(*args, **kwargs)
                failures = 0  # Reset on success
                return result

            except Exception as e:
                failures += 1
                last_failure_time = time.time()

                if failures >= failure_threshold:
                    circuit_open = True
                    logger.error(
                        f"Circuit breaker opened for {func.__name__} "
                        f"after {failures} failures"
                    )

                raise

        def get_state():
            return {
                "failures": failures,
                "circuit_open": circuit_open,
                "last_failure": last_failure_time
            }

        wrapper.get_state = get_state
        return wrapper

    return decorator
```

## DEMO

```python
def main():
    """Demonstrate the decorator library."""

    print("=" * 60)
    print("DECORATOR LIBRARY DEMO")
    print("=" * 60)

    # 1. Timing
    print("\n--- @timeit ---")

    @timeit
    def slow_operation():
        time.sleep(0.1)
        return "completed"

    slow_operation()

    # 2. Retry
    print("\n--- @retry ---")

    attempt = [0]

    @retry(max_attempts=3, delay=0.1, backoff=1.5)
    def flaky_function():
        attempt[0] += 1
        if attempt[0] < 3:
            raise ValueError("Temporary failure")
        return "success"

    result = flaky_function()
    print(f"Result: {result}")

    # 3. Cache with TTL
    print("\n--- @cache_with_ttl ---")

    @cache_with_ttl(ttl_seconds=60)
    def expensive_query(user_id):
        print(f"  Fetching user {user_id}...")
        return {"id": user_id, "name": f"User_{user_id}"}

    print(expensive_query(1))
    print(expensive_query(1))  # Cached
    print(f"Cache info: {expensive_query.cache_info()}")

    # 4. Rate limit
    print("\n--- @rate_limit ---")

    @rate_limit(calls=3, period=1.0)
    def api_call(endpoint):
        return f"Called {endpoint}"

    for i in range(4):
        print(api_call(f"/endpoint_{i}"))

    # 5. Validate
    print("\n--- @validate ---")

    @validate(
        age=lambda x: 0 <= x <= 120,
        name=lambda x: len(x) >= 2
    )
    def create_person(name, age):
        return {"name": name, "age": age}

    print(create_person("Alice", 30))

    try:
        create_person("A", -5)
    except ValueError as e:
        print(f"Validation error: {e}")

    # 6. Log execution
    print("\n--- @log_execution ---")

    @log_execution(include_args=True, include_result=True)
    def process_data(data):
        return sum(data)

    process_data([1, 2, 3, 4, 5])

    # 7. Deprecated
    print("\n--- @deprecated ---")

    @deprecated(replacement="new_function()")
    def old_function():
        return "old result"

    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        old_function()
        if w:
            print(f"Warning: {w[0].message}")

    # 8. Circuit breaker
    print("\n--- @circuit_breaker ---")

    failure_count = [0]

    @circuit_breaker(failure_threshold=3, recovery_timeout=1.0)
    def unreliable_service():
        failure_count[0] += 1
        if failure_count[0] <= 4:
            raise ConnectionError("Service unavailable")
        return "success"

    for i in range(5):
        try:
            result = unreliable_service()
            print(f"Call {i+1}: {result}")
        except Exception as e:
            print(f"Call {i+1}: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("All decorators demonstrated!")


if __name__ == "__main__":
    main()
```
