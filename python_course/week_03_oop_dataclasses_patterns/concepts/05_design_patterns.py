"""
Common Design Patterns in Python
================================
Patterns frequently used in data engineering and Python applications.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable
from dataclasses import dataclass, field
from functools import wraps

# ================================
# 1. SINGLETON PATTERN
# ================================

class SingletonMeta(type):
    """Metaclass for creating Singleton classes."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabaseConnection(metaclass=SingletonMeta):
    """Database connection that ensures only one instance exists."""

    def __init__(self, host="localhost", port=5432):
        self.host = host
        self.port = port
        self.connected = False
        print(f"Creating connection to {host}:{port}")

    def connect(self):
        self.connected = True
        return self

    def query(self, sql):
        return f"Executing: {sql}"


print("--- Singleton Pattern ---")
db1 = DatabaseConnection()
db2 = DatabaseConnection()
print(f"Same instance: {db1 is db2}")  # True


# Simpler singleton using decorator
def singleton(cls):
    """Decorator-based singleton."""
    instances = {}

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


@singleton
class ConfigManager:
    """Configuration manager singleton."""

    def __init__(self):
        self.config = {}

    def set(self, key, value):
        self.config[key] = value

    def get(self, key, default=None):
        return self.config.get(key, default)


# ================================
# 2. FACTORY PATTERN
# ================================

class DataParser(ABC):
    """Abstract parser interface."""

    @abstractmethod
    def parse(self, data: str) -> dict:
        pass


class JSONParser(DataParser):
    def parse(self, data: str) -> dict:
        import json
        return json.loads(data)


class XMLParser(DataParser):
    def parse(self, data: str) -> dict:
        # Simplified XML parsing
        return {"xml": "parsed"}


class CSVParser(DataParser):
    def parse(self, data: str) -> dict:
        lines = data.strip().split('\n')
        return {"rows": len(lines)}


class ParserFactory:
    """Factory for creating parsers based on format."""

    _parsers = {
        'json': JSONParser,
        'xml': XMLParser,
        'csv': CSVParser,
    }

    @classmethod
    def create(cls, format_type: str) -> DataParser:
        """Create a parser for the given format."""
        parser_class = cls._parsers.get(format_type.lower())
        if not parser_class:
            raise ValueError(f"Unknown format: {format_type}")
        return parser_class()

    @classmethod
    def register(cls, format_type: str, parser_class: type):
        """Register a new parser type."""
        cls._parsers[format_type.lower()] = parser_class


print("\n--- Factory Pattern ---")
json_parser = ParserFactory.create('json')
result = json_parser.parse('{"name": "Alice"}')
print(f"JSON parsed: {result}")

csv_parser = ParserFactory.create('csv')
result = csv_parser.parse("header\nrow1\nrow2")
print(f"CSV parsed: {result}")


# ================================
# 3. STRATEGY PATTERN
# ================================

class CompressionStrategy(ABC):
    """Strategy interface for compression."""

    @abstractmethod
    def compress(self, data: bytes) -> bytes:
        pass

    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        pass


class GzipStrategy(CompressionStrategy):
    def compress(self, data: bytes) -> bytes:
        import gzip
        return gzip.compress(data)

    def decompress(self, data: bytes) -> bytes:
        import gzip
        return gzip.decompress(data)


class NoCompressionStrategy(CompressionStrategy):
    def compress(self, data: bytes) -> bytes:
        return data

    def decompress(self, data: bytes) -> bytes:
        return data


class DataExporter:
    """Exporter that uses different compression strategies."""

    def __init__(self, strategy: CompressionStrategy = None):
        self.strategy = strategy or NoCompressionStrategy()

    def set_strategy(self, strategy: CompressionStrategy):
        """Change compression strategy at runtime."""
        self.strategy = strategy

    def export(self, data: str) -> bytes:
        raw_bytes = data.encode('utf-8')
        compressed = self.strategy.compress(raw_bytes)
        print(f"Original: {len(raw_bytes)} bytes, Compressed: {len(compressed)} bytes")
        return compressed


print("\n--- Strategy Pattern ---")
exporter = DataExporter()
exporter.export("Hello, World!")

exporter.set_strategy(GzipStrategy())
exporter.export("Hello, World!" * 100)


# ================================
# 4. OBSERVER PATTERN
# ================================

class EventManager:
    """Simple event/observer manager."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, listener: Callable):
        """Subscribe to an event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: str, listener: Callable):
        """Unsubscribe from an event type."""
        if event_type in self._listeners:
            self._listeners[event_type].remove(listener)

    def emit(self, event_type: str, data: Any = None):
        """Emit an event to all listeners."""
        if event_type in self._listeners:
            for listener in self._listeners[event_type]:
                listener(data)


print("\n--- Observer Pattern ---")
events = EventManager()

# Define listeners
def log_handler(data):
    print(f"  [LOG] {data}")

def email_handler(data):
    print(f"  [EMAIL] Sending notification: {data}")

# Subscribe
events.subscribe("user_created", log_handler)
events.subscribe("user_created", email_handler)
events.subscribe("error", log_handler)

# Emit events
print("Emitting 'user_created':")
events.emit("user_created", {"user_id": 123, "name": "Alice"})

print("\nEmitting 'error':")
events.emit("error", "Connection timeout")


# ================================
# 5. DECORATOR PATTERN (Structural)
# ================================

class DataProcessor(ABC):
    """Base processor interface."""

    @abstractmethod
    def process(self, data: str) -> str:
        pass


class BasicProcessor(DataProcessor):
    """Basic processor that returns data as-is."""

    def process(self, data: str) -> str:
        return data


class ProcessorDecorator(DataProcessor):
    """Base decorator class."""

    def __init__(self, processor: DataProcessor):
        self._processor = processor

    def process(self, data: str) -> str:
        return self._processor.process(data)


class UppercaseDecorator(ProcessorDecorator):
    """Decorator that uppercases output."""

    def process(self, data: str) -> str:
        result = super().process(data)
        return result.upper()


class TrimDecorator(ProcessorDecorator):
    """Decorator that trims whitespace."""

    def process(self, data: str) -> str:
        result = super().process(data)
        return result.strip()


class PrefixDecorator(ProcessorDecorator):
    """Decorator that adds a prefix."""

    def __init__(self, processor: DataProcessor, prefix: str):
        super().__init__(processor)
        self.prefix = prefix

    def process(self, data: str) -> str:
        result = super().process(data)
        return f"{self.prefix}{result}"


print("\n--- Decorator Pattern (Structural) ---")
# Build processor pipeline
processor = BasicProcessor()
processor = TrimDecorator(processor)
processor = UppercaseDecorator(processor)
processor = PrefixDecorator(processor, "[PROCESSED] ")

result = processor.process("  hello world  ")
print(f"Result: {result}")


# ================================
# 6. BUILDER PATTERN
# ================================

@dataclass
class Query:
    """SQL query built with builder pattern."""
    table: str = ""
    columns: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    order_by: str = ""
    limit: int = 0

    def to_sql(self) -> str:
        cols = ", ".join(self.columns) if self.columns else "*"
        sql = f"SELECT {cols} FROM {self.table}"

        if self.conditions:
            sql += " WHERE " + " AND ".join(self.conditions)

        if self.order_by:
            sql += f" ORDER BY {self.order_by}"

        if self.limit:
            sql += f" LIMIT {self.limit}"

        return sql


class QueryBuilder:
    """Builder for constructing queries fluently."""

    def __init__(self):
        self._query = Query()

    def table(self, name: str) -> 'QueryBuilder':
        self._query.table = name
        return self

    def select(self, *columns: str) -> 'QueryBuilder':
        self._query.columns = list(columns)
        return self

    def where(self, condition: str) -> 'QueryBuilder':
        self._query.conditions.append(condition)
        return self

    def order_by(self, column: str) -> 'QueryBuilder':
        self._query.order_by = column
        return self

    def limit(self, n: int) -> 'QueryBuilder':
        self._query.limit = n
        return self

    def build(self) -> Query:
        return self._query


print("\n--- Builder Pattern ---")
query = (QueryBuilder()
    .table("users")
    .select("id", "name", "email")
    .where("status = 'active'")
    .where("age >= 18")
    .order_by("name")
    .limit(10)
    .build())

print(f"SQL: {query.to_sql()}")


# ================================
# 7. REPOSITORY PATTERN
# ================================

@dataclass
class User:
    id: int
    name: str
    email: str


class UserRepository(ABC):
    """Abstract repository for User entities."""

    @abstractmethod
    def get(self, user_id: int) -> User:
        pass

    @abstractmethod
    def get_all(self) -> List[User]:
        pass

    @abstractmethod
    def save(self, user: User) -> None:
        pass

    @abstractmethod
    def delete(self, user_id: int) -> None:
        pass


class InMemoryUserRepository(UserRepository):
    """In-memory implementation for testing."""

    def __init__(self):
        self._users: Dict[int, User] = {}

    def get(self, user_id: int) -> User:
        return self._users.get(user_id)

    def get_all(self) -> List[User]:
        return list(self._users.values())

    def save(self, user: User) -> None:
        self._users[user.id] = user

    def delete(self, user_id: int) -> None:
        if user_id in self._users:
            del self._users[user_id]


print("\n--- Repository Pattern ---")
repo = InMemoryUserRepository()

# Use repository
repo.save(User(1, "Alice", "alice@example.com"))
repo.save(User(2, "Bob", "bob@example.com"))

print(f"All users: {repo.get_all()}")
print(f"User 1: {repo.get(1)}")


# ================================
# SUMMARY
# ================================

print("\n--- Pattern Summary ---")
print("""
Singleton: Ensure only one instance exists
  Use for: Config managers, connection pools, caches

Factory: Create objects without specifying exact class
  Use for: Parser selection, handler creation, plugin systems

Strategy: Define family of interchangeable algorithms
  Use for: Compression, sorting, validation strategies

Observer: Notify multiple objects of state changes
  Use for: Event systems, pub/sub, reactive programming

Decorator (Structural): Add behavior to objects dynamically
  Use for: Logging, caching, transformation pipelines

Builder: Construct complex objects step by step
  Use for: Query builders, configuration builders

Repository: Abstract data access behind collection-like interface
  Use for: Database access, data layer abstraction
""")
