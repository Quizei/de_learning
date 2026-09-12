"""
Abstract Base Classes (ABC)
===========================
Define interfaces that subclasses must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Any

# ================================
# BASIC ABSTRACT CLASS
# ================================

class Shape(ABC):
    """Abstract base class for shapes."""

    @abstractmethod
    def area(self) -> float:
        """Calculate area - must be implemented by subclasses."""
        pass

    @abstractmethod
    def perimeter(self) -> float:
        """Calculate perimeter - must be implemented by subclasses."""
        pass

    # Non-abstract method - inherited by subclasses
    def describe(self) -> str:
        return f"{self.__class__.__name__}: area={self.area():.2f}, perimeter={self.perimeter():.2f}"


class Rectangle(Shape):
    """Concrete rectangle implementation."""

    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height

    def perimeter(self) -> float:
        return 2 * (self.width + self.height)


class Circle(Shape):
    """Concrete circle implementation."""

    def __init__(self, radius: float):
        self.radius = radius

    def area(self) -> float:
        import math
        return math.pi * self.radius ** 2

    def perimeter(self) -> float:
        import math
        return 2 * math.pi * self.radius


print("--- Abstract Base Class ---")
# shape = Shape()  # TypeError: Can't instantiate abstract class

rect = Rectangle(5, 3)
circle = Circle(4)

print(rect.describe())
print(circle.describe())

# All shapes work polymorphically
shapes: List[Shape] = [rect, circle]
total_area = sum(s.area() for s in shapes)
print(f"Total area: {total_area:.2f}")


# ================================
# ABSTRACT PROPERTIES
# ================================

class Vehicle(ABC):
    """Vehicle with abstract properties."""

    @property
    @abstractmethod
    def max_speed(self) -> float:
        """Maximum speed in km/h."""
        pass

    @property
    @abstractmethod
    def fuel_type(self) -> str:
        """Type of fuel used."""
        pass

    def describe(self) -> str:
        return f"{self.__class__.__name__}: max {self.max_speed} km/h, uses {self.fuel_type}"


class Car(Vehicle):
    def __init__(self, model: str, max_speed: float):
        self.model = model
        self._max_speed = max_speed

    @property
    def max_speed(self) -> float:
        return self._max_speed

    @property
    def fuel_type(self) -> str:
        return "gasoline"


class ElectricBike(Vehicle):
    @property
    def max_speed(self) -> float:
        return 45

    @property
    def fuel_type(self) -> str:
        return "electricity"


print("\n--- Abstract Properties ---")
car = Car("Sedan", 180)
bike = ElectricBike()

print(car.describe())
print(bike.describe())


# ================================
# ABSTRACT CLASS METHODS
# ================================

class Serializable(ABC):
    """Interface for serializable objects."""

    @abstractmethod
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'Serializable':
        """Create instance from dictionary."""
        pass


class User(Serializable):
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def to_dict(self) -> dict:
        return {"name": self.name, "email": self.email}

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(data["name"], data["email"])


print("\n--- Abstract Class Methods ---")
user = User("Alice", "alice@example.com")
data = user.to_dict()
print(f"Serialized: {data}")

user2 = User.from_dict(data)
print(f"Deserialized: {user2.name}, {user2.email}")


# ================================
# REGISTERING VIRTUAL SUBCLASSES
# ================================

class JSONSerializable(ABC):
    """Interface for JSON serializable objects."""

    @abstractmethod
    def to_json(self) -> str:
        pass


# Register existing class as virtual subclass
@JSONSerializable.register
class ExistingClass:
    """This class becomes a virtual subclass of JSONSerializable."""

    def to_json(self) -> str:
        return "{}"


print("\n--- Virtual Subclasses ---")
obj = ExistingClass()
print(f"Is subclass: {isinstance(obj, JSONSerializable)}")  # True!


# ================================
# PRACTICAL EXAMPLE: DATA PIPELINE
# ================================

class DataSource(ABC):
    """Abstract base for data sources."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to data source."""
        pass

    @abstractmethod
    def read(self) -> List[dict]:
        """Read data from source."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connection."""
        pass

    # Context manager support
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class DatabaseSource(DataSource):
    """Database data source."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connected = False

    def connect(self) -> None:
        print(f"Connecting to database: {self.connection_string}")
        self.connected = True

    def read(self) -> List[dict]:
        if not self.connected:
            raise RuntimeError("Not connected")
        return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    def close(self) -> None:
        print("Closing database connection")
        self.connected = False


class APISource(DataSource):
    """API data source."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.session = None

    def connect(self) -> None:
        print(f"Creating session for API: {self.endpoint}")
        self.session = "mock_session"

    def read(self) -> List[dict]:
        if not self.session:
            raise RuntimeError("No session")
        return [{"data": "from API"}]

    def close(self) -> None:
        print("Closing API session")
        self.session = None


class FileSource(DataSource):
    """File data source."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.file = None

    def connect(self) -> None:
        print(f"Opening file: {self.filepath}")
        self.file = "mock_file_handle"

    def read(self) -> List[dict]:
        if not self.file:
            raise RuntimeError("File not open")
        return [{"line": 1}, {"line": 2}]

    def close(self) -> None:
        print("Closing file")
        self.file = None


def process_data(source: DataSource) -> List[dict]:
    """Process data from any source - polymorphism in action."""
    with source:
        data = source.read()
        print(f"Read {len(data)} records")
        return data


print("\n--- Data Pipeline Example ---")
# All sources work the same way
db_source = DatabaseSource("postgresql://localhost/mydb")
api_source = APISource("https://api.example.com")
file_source = FileSource("/data/input.csv")

for source in [db_source, api_source, file_source]:
    print()
    data = process_data(source)


# ================================
# ABSTRACT BASE CLASSES FROM collections.abc
# ================================

from collections.abc import Iterable, Iterator, Mapping, MutableMapping

print("\n--- Built-in ABCs ---")
print("""
Common ABCs from collections.abc:

Container    - __contains__
Iterable     - __iter__
Iterator     - __iter__, __next__
Sized        - __len__
Callable     - __call__

Sequence     - __getitem__, __len__ (+ Iterable, Container, Sized)
MutableSequence - above + __setitem__, __delitem__, insert

Mapping      - __getitem__, __len__, __iter__
MutableMapping - above + __setitem__, __delitem__

Set          - like Sequence but for sets
MutableSet   - like MutableSequence but for sets
""")

# Example: Check if something is iterable
print(f"List is Iterable: {isinstance([], Iterable)}")
print(f"String is Iterable: {isinstance('abc', Iterable)}")
print(f"Int is Iterable: {isinstance(42, Iterable)}")
