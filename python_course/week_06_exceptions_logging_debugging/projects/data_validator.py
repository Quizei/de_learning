"""
Week 6 Project: Data Validator
==============================
Robust data validation with comprehensive error handling and logging.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Custom Exceptions
class ValidationError(Exception):
    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"{field}: {message} (got {value!r})")

class SchemaError(Exception):
    pass

@dataclass
class ValidationResult:
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class Validator:
    """Field validator with chainable rules."""

    def __init__(self, field_name: str):
        self.field_name = field_name
        self.rules: List[Callable] = []
        self.required = False

    def is_required(self):
        self.required = True
        return self

    def is_type(self, expected_type):
        def check(value):
            if not isinstance(value, expected_type):
                raise ValidationError(
                    self.field_name, value,
                    f"Expected {expected_type.__name__}"
                )
        self.rules.append(check)
        return self

    def min_length(self, length):
        def check(value):
            if len(value) < length:
                raise ValidationError(
                    self.field_name, value,
                    f"Minimum length is {length}"
                )
        self.rules.append(check)
        return self

    def max_length(self, length):
        def check(value):
            if len(value) > length:
                raise ValidationError(
                    self.field_name, value,
                    f"Maximum length is {length}"
                )
        self.rules.append(check)
        return self

    def in_range(self, min_val, max_val):
        def check(value):
            if not min_val <= value <= max_val:
                raise ValidationError(
                    self.field_name, value,
                    f"Must be between {min_val} and {max_val}"
                )
        self.rules.append(check)
        return self

    def matches(self, pattern):
        import re
        def check(value):
            if not re.match(pattern, value):
                raise ValidationError(
                    self.field_name, value,
                    f"Must match pattern {pattern}"
                )
        self.rules.append(check)
        return self

    def validate(self, value) -> List[ValidationError]:
        errors = []
        for rule in self.rules:
            try:
                rule(value)
            except ValidationError as e:
                errors.append(e)
        return errors

class Schema:
    """Schema for validating data records."""

    def __init__(self):
        self.validators: Dict[str, Validator] = {}

    def field(self, name: str) -> Validator:
        validator = Validator(name)
        self.validators[name] = validator
        return validator

    def validate(self, data: Dict) -> ValidationResult:
        result = ValidationResult(valid=True)

        for field_name, validator in self.validators.items():
            if field_name not in data:
                if validator.required:
                    result.errors.append(
                        ValidationError(field_name, None, "Field is required")
                    )
                    result.valid = False
                continue

            errors = validator.validate(data[field_name])
            if errors:
                result.errors.extend(errors)
                result.valid = False

        # Warn about unknown fields
        for field_name in data:
            if field_name not in self.validators:
                result.warnings.append(f"Unknown field: {field_name}")

        return result

def main():
    # Define schema
    schema = Schema()
    schema.field("name").is_required().is_type(str).min_length(2).max_length(50)
    schema.field("email").is_required().is_type(str).matches(r'.+@.+\..+')
    schema.field("age").is_required().is_type(int).in_range(0, 150)

    # Test data
    test_cases = [
        {"name": "Alice", "email": "alice@example.com", "age": 30},
        {"name": "B", "email": "invalid", "age": 200},
        {"name": "Charlie"},
        {"name": "David", "email": "d@e.com", "age": 25, "unknown": "field"},
    ]

    for i, data in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Data: {data}")
        result = schema.validate(data)
        print(f"Valid: {result.valid}")
        for error in result.errors:
            print(f"  Error: {error}")
        for warning in result.warnings:
            print(f"  Warning: {warning}")

if __name__ == "__main__":
    main()
