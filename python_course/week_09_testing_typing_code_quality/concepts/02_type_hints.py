"""
Type Hints in Python
====================
Adding type annotations for better code quality.
"""

from typing import (
    List, Dict, Set, Tuple,
    Optional, Union,
    Callable, TypeVar, Generic,
    Any, Literal
)
from dataclasses import dataclass

# ================================
# BASIC TYPE HINTS
# ================================

# Variables
name: str = "Alice"
age: int = 30
price: float = 99.99
is_active: bool = True

# Functions
def greet(name: str) -> str:
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b

def process(data: str) -> None:
    print(data)

# ================================
# COLLECTION TYPES
# ================================

# Lists
def get_names() -> List[str]:
    return ["Alice", "Bob"]

# Dicts
def get_scores() -> Dict[str, int]:
    return {"Alice": 95, "Bob": 87}

# Sets
def get_unique_ids() -> Set[int]:
    return {1, 2, 3}

# Tuples
def get_point() -> Tuple[int, int]:
    return (10, 20)

# Tuple with mixed types
def get_user() -> Tuple[str, int, bool]:
    return ("Alice", 30, True)

# ================================
# OPTIONAL AND UNION
# ================================

# Optional - can be None
def find_user(user_id: int) -> Optional[str]:
    users = {1: "Alice", 2: "Bob"}
    return users.get(user_id)  # Returns str or None

# Union - multiple types
def process_id(id: Union[int, str]) -> str:
    return str(id)

# Python 3.10+ syntax
# def process_id(id: int | str) -> str:
#     return str(id)

# ================================
# CALLABLE
# ================================

# Function type
def apply_func(func: Callable[[int, int], int], a: int, b: int) -> int:
    return func(a, b)

result = apply_func(lambda x, y: x + y, 5, 3)

# Callable with no args
def run_task(task: Callable[[], None]) -> None:
    task()

# ================================
# TYPE VARIABLES (GENERICS)
# ================================

T = TypeVar('T')

def first(items: List[T]) -> T:
    return items[0]

# Works with any type
num = first([1, 2, 3])        # int
name = first(["a", "b", "c"])  # str

# Bounded TypeVar
Number = TypeVar('Number', int, float)

def double(x: Number) -> Number:
    return x * 2

# ================================
# GENERIC CLASSES
# ================================

class Box(Generic[T]):
    def __init__(self, content: T):
        self.content = content

    def get(self) -> T:
        return self.content

int_box: Box[int] = Box(42)
str_box: Box[str] = Box("hello")

# ================================
# LITERAL TYPES
# ================================

def set_status(status: Literal["pending", "active", "done"]) -> None:
    print(f"Status: {status}")

set_status("active")  # OK
# set_status("invalid")  # Type error

# ================================
# TYPE ALIASES
# ================================

UserId = int
UserDict = Dict[str, Any]
Callback = Callable[[str], None]

def get_user(user_id: UserId) -> UserDict:
    return {"id": user_id, "name": "Alice"}

# ================================
# TYPED DATACLASSES
# ================================

@dataclass
class User:
    id: int
    name: str
    email: str
    age: Optional[int] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

user = User(id=1, name="Alice", email="alice@example.com")

# ================================
# PROTOCOL (STRUCTURAL TYPING)
# ================================

from typing import Protocol

class Drawable(Protocol):
    def draw(self) -> None: ...

class Circle:
    def draw(self) -> None:
        print("Drawing circle")

def render(shape: Drawable) -> None:
    shape.draw()

render(Circle())  # Works because Circle has draw()

# ================================
# BEST PRACTICES
# ================================

print("--- Type Hints Best Practices ---")
print("""
1. Always type function signatures
2. Use Optional for nullable values
3. Use TypeVar for generic functions
4. Create type aliases for complex types
5. Use mypy to check types: mypy your_file.py
6. Don't overuse Any - it defeats the purpose
7. Type hints are not enforced at runtime
""")

print("\n✅ Type hints complete!")
