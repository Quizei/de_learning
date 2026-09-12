"""
Data Classes in Python
======================
dataclasses reduce boilerplate for classes that primarily store data.
Available in Python 3.7+
"""

from dataclasses import dataclass, field, asdict, astuple, replace
from typing import List, Optional
from datetime import datetime

# ================================
# BASIC DATACLASS
# ================================

@dataclass
class Point:
    """Simple 2D point."""
    x: float
    y: float


# Automatically generates:
# - __init__
# - __repr__
# - __eq__

p1 = Point(3, 4)
p2 = Point(3, 4)
p3 = Point(1, 2)

print("--- Basic Dataclass ---")
print(f"Point: {p1}")           # Point(x=3, y=4)
print(f"p1 == p2: {p1 == p2}")  # True
print(f"p1 == p3: {p1 == p3}")  # False


# ================================
# DEFAULT VALUES
# ================================

@dataclass
class Config:
    """Configuration with defaults."""
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    timeout: int = 30


print("\n--- Default Values ---")
cfg1 = Config()
cfg2 = Config(host="0.0.0.0", port=5000)

print(f"Default: {cfg1}")
print(f"Custom: {cfg2}")


# ================================
# MUTABLE DEFAULT VALUES
# ================================

# WRONG - mutable default shared between instances!
# @dataclass
# class WrongClass:
#     items: list = []  # All instances share same list!

# CORRECT - use field(default_factory=...)
@dataclass
class ShoppingCart:
    """Shopping cart with mutable defaults."""
    customer: str
    items: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


print("\n--- Mutable Defaults ---")
cart1 = ShoppingCart("Alice")
cart2 = ShoppingCart("Bob")

cart1.items.append("Apple")
print(f"Cart 1: {cart1.items}")  # ['Apple']
print(f"Cart 2: {cart2.items}")  # [] (separate list!)


# ================================
# FIELD OPTIONS
# ================================

@dataclass
class User:
    """User with various field options."""
    # Regular fields
    username: str
    email: str

    # With default
    role: str = "user"

    # Excluded from repr (sensitive data)
    password_hash: str = field(repr=False)

    # Not included in comparisons
    last_login: Optional[datetime] = field(default=None, compare=False)

    # Excluded from __init__ (computed)
    display_name: str = field(init=False)

    # Metadata (for documentation or serialization hints)
    age: int = field(default=0, metadata={"min": 0, "max": 150})

    def __post_init__(self):
        """Called after __init__, useful for computed fields."""
        self.display_name = f"@{self.username}"


print("\n--- Field Options ---")
user = User("alice", "alice@example.com", password_hash="abc123")
print(f"User: {user}")  # password_hash not shown
print(f"Display name: {user.display_name}")


# ================================
# FROZEN (IMMUTABLE) DATACLASS
# ================================

@dataclass(frozen=True)
class ImmutablePoint:
    """Immutable point - hashable, can be used as dict key."""
    x: float
    y: float


print("\n--- Frozen Dataclass ---")
ip = ImmutablePoint(3, 4)
print(f"Point: {ip}")
print(f"Hash: {hash(ip)}")  # Hashable!

# Use as dict key
distances = {
    ImmutablePoint(0, 0): 0,
    ImmutablePoint(3, 4): 5,
}
print(f"Distance to (3,4): {distances[ImmutablePoint(3, 4)]}")

# ip.x = 10  # FrozenInstanceError!


# ================================
# ORDERING
# ================================

@dataclass(order=True)
class Version:
    """Sortable version number."""
    # Order determined by field order
    major: int
    minor: int
    patch: int

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"


print("\n--- Ordering ---")
versions = [
    Version(1, 2, 3),
    Version(1, 0, 0),
    Version(2, 0, 0),
    Version(1, 2, 0),
]

print("Sorted versions:", [str(v) for v in sorted(versions)])


# Custom sort key
@dataclass(order=True)
class Student:
    """Student sortable by GPA then name."""
    # This field used for sorting (first in order)
    sort_index: float = field(init=False, repr=False)

    name: str
    gpa: float

    def __post_init__(self):
        # Negative for descending GPA, then name for tie-breaking
        self.sort_index = (-self.gpa, self.name)


# ================================
# UTILITY FUNCTIONS
# ================================

@dataclass
class Person:
    """Person for utility function demos."""
    name: str
    age: int
    city: str = "Unknown"


print("\n--- Utility Functions ---")
person = Person("Alice", 30, "NYC")

# Convert to dict
person_dict = asdict(person)
print(f"As dict: {person_dict}")

# Convert to tuple
person_tuple = astuple(person)
print(f"As tuple: {person_tuple}")

# Create modified copy
person2 = replace(person, city="LA", age=31)
print(f"Modified copy: {person2}")
print(f"Original unchanged: {person}")


# ================================
# INHERITANCE
# ================================

@dataclass
class Animal:
    """Base animal class."""
    name: str
    age: int


@dataclass
class Dog(Animal):
    """Dog with additional fields."""
    breed: str
    is_trained: bool = False


print("\n--- Inheritance ---")
dog = Dog("Buddy", 3, "Golden Retriever", True)
print(f"Dog: {dog}")


# ================================
# PRACTICAL EXAMPLES
# ================================

# 1. API Response
@dataclass
class APIResponse:
    """Structured API response."""
    status_code: int
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


# 2. Configuration
@dataclass(frozen=True)
class DatabaseConfig:
    """Immutable database configuration."""
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)
    pool_size: int = 5
    timeout: int = 30

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.username}@{self.host}:{self.port}/{self.database}"


# 3. Event
@dataclass
class Event:
    """Domain event."""
    event_type: str
    payload: dict
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: __import__('uuid').uuid4().hex)


print("\n--- Practical Examples ---")

response = APIResponse(200, {"users": ["alice", "bob"]})
print(f"API Response: {response.is_success}")

db_config = DatabaseConfig(
    host="localhost",
    port=5432,
    database="myapp",
    username="admin",
    password="secret"
)
print(f"DB Config: {db_config}")
print(f"Connection: {db_config.connection_string}")

event = Event("user_created", {"user_id": 123})
print(f"Event: {event}")


# ================================
# DATACLASS VS NAMEDTUPLE VS REGULAR CLASS
# ================================

print("\n--- When to Use What ---")
print("""
dataclass:
  + Auto-generates __init__, __repr__, __eq__
  + Mutable by default (frozen=True for immutable)
  + Supports inheritance well
  + Type hints built-in
  + Field-level customization
  Best for: Configuration, DTOs, domain models

namedtuple:
  + Immutable
  + Memory efficient
  + Can unpack like tuple
  + Hashable by default
  - No default values (use defaults= in Python 3.7+)
  - Limited customization
  Best for: Simple immutable records, dict keys

Regular class:
  + Full control
  + Complex logic in __init__
  + Custom metaclasses
  Best for: Complex objects with behavior
""")
