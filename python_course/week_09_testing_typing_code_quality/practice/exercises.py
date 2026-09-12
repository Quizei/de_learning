"""
Week 9 Practice Exercises: Testing & Type Hints
================================================
"""

from typing import List, Dict, Optional, Callable
import pytest

# ================================
# EXERCISE 1: Write tests for a Calculator class
# ================================

class Calculator:
    def add(self, a: float, b: float) -> float:
        return a + b

    def subtract(self, a: float, b: float) -> float:
        return a - b

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

# Write tests here
class TestCalculator:
    @pytest.fixture
    def calc(self):
        return Calculator()

    def test_add(self, calc):
        assert calc.add(2, 3) == 5

    def test_divide_by_zero(self, calc):
        with pytest.raises(ValueError):
            calc.divide(10, 0)

# ================================
# EXERCISE 2: Add type hints to functions
# ================================

def process_users(users: List[Dict[str, str]]) -> List[str]:
    """Extract emails from user dicts."""
    return [u["email"] for u in users if "email" in u]

def find_by_id(items: List[Dict], item_id: int) -> Optional[Dict]:
    """Find item by ID or return None."""
    for item in items:
        if item.get("id") == item_id:
            return item
    return None

def apply_discount(
    prices: List[float],
    discount_func: Callable[[float], float]
) -> List[float]:
    """Apply discount function to all prices."""
    return [discount_func(p) for p in prices]

# ================================
# EXERCISE 3: Test with mocking
# ================================

from unittest.mock import Mock, patch

class UserService:
    def __init__(self, api_client):
        self.api = api_client

    def get_user_name(self, user_id: int) -> str:
        user = self.api.get_user(user_id)
        return user["name"]

def test_user_service_with_mock():
    mock_api = Mock()
    mock_api.get_user.return_value = {"id": 1, "name": "Alice"}

    service = UserService(mock_api)
    name = service.get_user_name(1)

    assert name == "Alice"
    mock_api.get_user.assert_called_once_with(1)

# ================================
# EXERCISE 4: Parametrized tests
# ================================

@pytest.mark.parametrize("input_str,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_uppercase(input_str: str, expected: str):
    assert input_str.upper() == expected

# ================================
# RUN TESTS
# ================================

def show_solutions():
    print("=== Testing Solutions ===")
    print("\nRun tests with: pytest -v practice/exercises.py")

    # Manual test execution
    calc = Calculator()
    print(f"\nCalculator tests:")
    print(f"  add(2, 3) = {calc.add(2, 3)}")
    print(f"  divide(10, 2) = {calc.divide(10, 2)}")

    # Type hints demo
    users = [{"email": "a@b.com"}, {"name": "Bob"}]
    print(f"\nprocess_users: {process_users(users)}")

    # Mock demo
    test_user_service_with_mock()
    print("Mock test passed!")

    print("\n✅ All exercises demonstrated!")

if __name__ == "__main__":
    show_solutions()
