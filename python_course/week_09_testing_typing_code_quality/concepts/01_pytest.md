# Testing with Pytest

Writing and organizing tests effectively.

## BASIC TESTS

```python
# --- Code to test ---
def add(a, b):
    return a + b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

# --- Tests ---
def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0

def test_divide():
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3

def test_divide_by_zero():
    import pytest
    with pytest.raises(ValueError):
        divide(10, 0)
```

## FIXTURES

```python
import pytest

@pytest.fixture
def sample_data():
    """Fixture that provides test data."""
    return {"users": ["alice", "bob"], "count": 2}

@pytest.fixture
def database():
    """Fixture with setup and teardown."""
    print("\nSetting up database")
    db = {"connected": True}
    yield db
    print("\nTearing down database")
    db["connected"] = False

def test_with_fixture(sample_data):
    assert sample_data["count"] == 2
    assert "alice" in sample_data["users"]

def test_with_database(database):
    assert database["connected"] is True
```

## PARAMETRIZED TESTS

```python
@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (-1, 1, 0),
    (0, 0, 0),
    (100, 200, 300),
])
def test_add_parametrized(a, b, expected):
    assert add(a, b) == expected

@pytest.mark.parametrize("input,expected", [
    ("hello", 5),
    ("", 0),
    ("python", 6),
])
def test_string_length(input, expected):
    assert len(input) == expected
```

## MARKERS

```python
@pytest.mark.slow
def test_slow_operation():
    """Marked as slow - can skip with: pytest -m 'not slow'"""
    import time
    time.sleep(0.1)
    assert True

@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.skipif(True, reason="Condition met")
def test_conditional_skip():
    pass
```

## TEST CLASSES

```python
class TestUserOperations:
    """Group related tests in a class."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.users = ["alice", "bob"]

    def test_user_count(self):
        assert len(self.users) == 2

    def test_user_exists(self):
        assert "alice" in self.users
```

## MOCKING

```python
from unittest.mock import Mock, patch, MagicMock

def get_user_from_api(user_id):
    """Function that calls external API."""
    # In real code: return requests.get(f'/users/{user_id}').json()
    pass

def test_with_mock():
    # Create a mock
    mock_api = Mock()
    mock_api.get_user.return_value = {"id": 1, "name": "Alice"}

    result = mock_api.get_user(1)
    assert result["name"] == "Alice"
    mock_api.get_user.assert_called_once_with(1)

def test_with_patch():
    with patch('builtins.open', mock_open(read_data="test content")):
        # open() is now mocked
        pass

def mock_open(read_data):
    """Helper for mocking open()."""
    m = MagicMock()
    m.return_value.__enter__.return_value.read.return_value = read_data
    return m

# Run with: pytest -v concepts/01_pytest.py
print("Run tests with: pytest -v")
```
