# Week 6 Practice Exercises: Exceptions, Logging & Debugging

```python
import logging

# EXERCISE 1: Create custom exception hierarchy for a banking app
# EXERCISE 2: Implement retry decorator with logging
# EXERCISE 3: Create a context manager that logs entry/exit
# EXERCISE 4: Build a validator with detailed error messages
# EXERCISE 5: Debug a buggy function using pdb

def show_solutions():
    print("=== SOLUTIONS ===")

    # Exercise 1: Custom exceptions
    print("\n--- Custom Exception Hierarchy ---")

    class BankError(Exception):
        pass

    class InsufficientFundsError(BankError):
        def __init__(self, balance, amount):
            self.balance = balance
            self.amount = amount
            super().__init__(f"Cannot withdraw {amount}, balance is {balance}")

    class InvalidAccountError(BankError):
        pass

    try:
        raise InsufficientFundsError(100, 150)
    except InsufficientFundsError as e:
        print(f"Error: {e}")

    # Exercise 2: Retry decorator with logging
    print("\n--- Retry Decorator ---")

    def retry_with_logging(max_attempts=3):
        def decorator(func):
            def wrapper(*args, **kwargs):
                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        print(f"Attempt {attempt} failed: {e}")
                        if attempt == max_attempts:
                            raise
            return wrapper
        return decorator

    attempt_counter = [0]

    @retry_with_logging(max_attempts=3)
    def unreliable():
        attempt_counter[0] += 1
        if attempt_counter[0] < 3:
            raise ValueError("Not yet!")
        return "Success!"

    print(unreliable())

    # Exercise 3: Logging context manager
    print("\n--- Logging Context Manager ---")

    from contextlib import contextmanager
    import time

    @contextmanager
    def log_execution(name):
        print(f"[START] {name}")
        start = time.time()
        try:
            yield
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            raise
        finally:
            elapsed = time.time() - start
            print(f"[END] {name} ({elapsed:.3f}s)")

    with log_execution("my_operation"):
        time.sleep(0.1)

    print("\n✅ All solutions demonstrated!")

if __name__ == "__main__":
    show_solutions()
```
