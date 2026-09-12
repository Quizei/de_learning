"""
Exception Handling in Python
============================
Proper error handling for robust applications.
"""

# ================================
# BASIC EXCEPTION HANDLING
# ================================

print("--- Basic Exception Handling ---")

# try/except/else/finally
try:
    result = 10 / 2
except ZeroDivisionError:
    print("Cannot divide by zero")
else:
    print(f"Result: {result}")  # Runs if no exception
finally:
    print("Cleanup code")  # Always runs

# Multiple exceptions
try:
    value = int("abc")
except (ValueError, TypeError) as e:
    print(f"Conversion error: {e}")

# ================================
# EXCEPTION HIERARCHY
# ================================

print("\n--- Exception Hierarchy ---")
print("""
BaseException
├── SystemExit
├── KeyboardInterrupt
├── GeneratorExit
└── Exception
    ├── ValueError
    ├── TypeError
    ├── KeyError
    ├── IndexError
    ├── FileNotFoundError
    ├── IOError
    └── ... many more
""")

# ================================
# RAISING EXCEPTIONS
# ================================

print("\n--- Raising Exceptions ---")

def validate_age(age):
    if not isinstance(age, int):
        raise TypeError("Age must be an integer")
    if age < 0 or age > 150:
        raise ValueError(f"Age must be 0-150, got {age}")
    return age

try:
    validate_age(-5)
except ValueError as e:
    print(f"Validation error: {e}")

# Re-raising exceptions
def process_data(data):
    try:
        return data['key']
    except KeyError:
        print("Logging error...")
        raise  # Re-raise the same exception

# ================================
# CUSTOM EXCEPTIONS
# ================================

print("\n--- Custom Exceptions ---")

class ValidationError(Exception):
    """Base validation error."""
    pass

class EmailValidationError(ValidationError):
    """Email-specific validation error."""
    def __init__(self, email, message="Invalid email"):
        self.email = email
        self.message = message
        super().__init__(f"{message}: {email}")

class DataPipelineError(Exception):
    """Error in data pipeline."""
    def __init__(self, stage, message, original_error=None):
        self.stage = stage
        self.original_error = original_error
        super().__init__(f"[{stage}] {message}")

# Usage
try:
    raise EmailValidationError("invalid-email", "Missing @ symbol")
except EmailValidationError as e:
    print(f"Email error: {e.email} - {e.message}")

# ================================
# EXCEPTION CHAINING
# ================================

print("\n--- Exception Chaining ---")

def fetch_data():
    raise ConnectionError("Network unreachable")

def process():
    try:
        fetch_data()
    except ConnectionError as e:
        raise DataPipelineError("fetch", "Failed to fetch data") from e

try:
    process()
except DataPipelineError as e:
    print(f"Pipeline error: {e}")
    print(f"Caused by: {e.__cause__}")

# ================================
# CONTEXT MANAGERS FOR CLEANUP
# ================================

print("\n--- Cleanup with Context Managers ---")

class DatabaseConnection:
    def __enter__(self):
        print("Opening connection")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Closing connection")
        if exc_type:
            print(f"Error occurred: {exc_val}")
        return False  # Don't suppress exceptions

with DatabaseConnection():
    print("Using database")

print("\n✅ Exception handling complete!")
