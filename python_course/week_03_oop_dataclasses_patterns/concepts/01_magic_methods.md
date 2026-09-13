# Magic/Dunder Methods in Python

Special methods that Python calls implicitly.
They enable operator overloading and customize object behavior.

## BASIC MAGIC METHODS

```python
class Point:
    """A 2D point demonstrating common magic methods."""

    def __init__(self, x, y):
        """Initialize - called when creating instance."""
        self.x = x
        self.y = y

    def __repr__(self):
        """Developer-friendly string representation.
        Used by repr() and in interactive console."""
        return f"Point({self.x}, {self.y})"

    def __str__(self):
        """User-friendly string representation.
        Used by str() and print()."""
        return f"({self.x}, {self.y})"

    def __eq__(self, other):
        """Equality comparison: =="""
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        """Make hashable (required if __eq__ is defined).
        Allows use in sets and as dict keys."""
        return hash((self.x, self.y))

    def __bool__(self):
        """Boolean value - used by bool() and if statements."""
        return self.x != 0 or self.y != 0

    def __len__(self):
        """Length - used by len()."""
        return 2  # A point has 2 dimensions


# Demo basic methods
p1 = Point(3, 4)
p2 = Point(3, 4)
p3 = Point(0, 0)

print("--- Basic Magic Methods ---")
print(f"repr: {repr(p1)}")      # Point(3, 4)
print(f"str: {str(p1)}")        # (3, 4)
print(f"p1 == p2: {p1 == p2}")  # True
print(f"bool(p1): {bool(p1)}")  # True
print(f"bool(p3): {bool(p3)}")  # False (origin)
print(f"len(p1): {len(p1)}")    # 2
```

## ARITHMETIC OPERATORS

```python
class Vector:
    """A vector with arithmetic operations."""

    def __init__(self, *components):
        self.components = tuple(components)

    def __repr__(self):
        return f"Vector{self.components}"

    def __add__(self, other):
        """Addition: self + other"""
        if isinstance(other, Vector):
            if len(self.components) != len(other.components):
                raise ValueError("Vectors must have same dimension")
            return Vector(*(a + b for a, b in zip(self.components, other.components)))
        return NotImplemented

    def __radd__(self, other):
        """Reverse addition: other + self (when other doesn't support +)"""
        return self.__add__(other)

    def __sub__(self, other):
        """Subtraction: self - other"""
        if isinstance(other, Vector):
            return Vector(*(a - b for a, b in zip(self.components, other.components)))
        return NotImplemented

    def __mul__(self, scalar):
        """Scalar multiplication: self * scalar"""
        if isinstance(scalar, (int, float)):
            return Vector(*(c * scalar for c in self.components))
        return NotImplemented

    def __rmul__(self, scalar):
        """Reverse multiplication: scalar * self"""
        return self.__mul__(scalar)

    def __neg__(self):
        """Negation: -self"""
        return Vector(*(-c for c in self.components))

    def __abs__(self):
        """Absolute value: abs(self) - returns magnitude"""
        return sum(c ** 2 for c in self.components) ** 0.5


v1 = Vector(1, 2, 3)
v2 = Vector(4, 5, 6)

print("\n--- Arithmetic Operators ---")
print(f"v1 + v2 = {v1 + v2}")       # Vector(5, 7, 9)
print(f"v1 - v2 = {v1 - v2}")       # Vector(-3, -3, -3)
print(f"v1 * 2 = {v1 * 2}")         # Vector(2, 4, 6)
print(f"3 * v1 = {3 * v1}")         # Vector(3, 6, 9)
print(f"-v1 = {-v1}")               # Vector(-1, -2, -3)
print(f"abs(v1) = {abs(v1):.2f}")   # 3.74
```

## COMPARISON OPERATORS

```python
class Money:
    """Money class with full comparison support."""

    def __init__(self, amount, currency="USD"):
        self.amount = amount
        self.currency = currency

    def __repr__(self):
        return f"Money({self.amount}, '{self.currency}')"

    def __eq__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __lt__(self, other):
        """Less than: <"""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError("Cannot compare different currencies")
        return self.amount < other.amount

    def __le__(self, other):
        """Less than or equal: <="""
        return self == other or self < other

    def __gt__(self, other):
        """Greater than: >"""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError("Cannot compare different currencies")
        return self.amount > other.amount

    def __ge__(self, other):
        """Greater than or equal: >="""
        return self == other or self > other


m1 = Money(100)
m2 = Money(200)

print("\n--- Comparison Operators ---")
print(f"m1 < m2: {m1 < m2}")   # True
print(f"m1 <= m2: {m1 <= m2}")  # True
print(f"m1 > m2: {m1 > m2}")   # False
```

## CONTAINER METHODS

```python
class DataRow:
    """A row of data with container behavior."""

    def __init__(self, **fields):
        self._fields = fields

    def __repr__(self):
        return f"DataRow({self._fields})"

    def __getitem__(self, key):
        """Get item: row[key]"""
        return self._fields[key]

    def __setitem__(self, key, value):
        """Set item: row[key] = value"""
        self._fields[key] = value

    def __delitem__(self, key):
        """Delete item: del row[key]"""
        del self._fields[key]

    def __contains__(self, key):
        """Membership test: key in row"""
        return key in self._fields

    def __iter__(self):
        """Iteration: for key in row"""
        return iter(self._fields)

    def __len__(self):
        """Length: len(row)"""
        return len(self._fields)


row = DataRow(name="Alice", age=30, city="NYC")

print("\n--- Container Methods ---")
print(f"row['name']: {row['name']}")         # Alice
print(f"'age' in row: {'age' in row}")       # True
print(f"len(row): {len(row)}")               # 3
print(f"keys: {list(row)}")                  # ['name', 'age', 'city']

row['email'] = 'alice@example.com'
print(f"after adding email: {row}")
```

## CALLABLE & CONTEXT MANAGER

```python
class Multiplier:
    """A callable object."""

    def __init__(self, factor):
        self.factor = factor

    def __call__(self, value):
        """Make instance callable: obj(value)"""
        return value * self.factor


class Timer:
    """A context manager for timing code blocks."""

    def __enter__(self):
        """Called when entering 'with' block."""
        import time
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Called when exiting 'with' block."""
        import time
        self.elapsed = time.perf_counter() - self.start
        print(f"Elapsed: {self.elapsed:.4f}s")
        return False  # Don't suppress exceptions


print("\n--- Callable & Context Manager ---")
double = Multiplier(2)
triple = Multiplier(3)
print(f"double(5): {double(5)}")   # 10
print(f"triple(5): {triple(5)}")   # 15

import time
with Timer():
    time.sleep(0.1)
```

## ATTRIBUTE ACCESS

```python
class DynamicObject:
    """Demonstrates attribute access magic methods."""

    def __init__(self):
        self._data = {}

    def __getattr__(self, name):
        """Called when attribute is not found normally."""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
        return self._data.get(name, f"<undefined: {name}>")

    def __setattr__(self, name, value):
        """Called on every attribute assignment."""
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __delattr__(self, name):
        """Called when deleting an attribute."""
        if name in self._data:
            del self._data[name]


obj = DynamicObject()
obj.name = "Alice"
obj.age = 30

print("\n--- Attribute Access ---")
print(f"obj.name: {obj.name}")        # Alice
print(f"obj.unknown: {obj.unknown}")  # <undefined: unknown>
```

## PRACTICAL EXAMPLE: MONEY CLASS

```python
class Currency:
    """Full-featured currency class."""

    def __init__(self, amount, code="USD"):
        self._amount = round(amount, 2)
        self._code = code

    @property
    def amount(self):
        return self._amount

    @property
    def code(self):
        return self._code

    def __repr__(self):
        return f"Currency({self._amount}, '{self._code}')"

    def __str__(self):
        symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
        symbol = symbols.get(self._code, self._code)
        return f"{symbol}{self._amount:,.2f}"

    def __add__(self, other):
        if isinstance(other, Currency):
            if self._code != other._code:
                raise ValueError("Cannot add different currencies")
            return Currency(self._amount + other._amount, self._code)
        if isinstance(other, (int, float)):
            return Currency(self._amount + other, self._code)
        return NotImplemented

    def __radd__(self, other):
        return self.__add__(other)

    def __mul__(self, factor):
        if isinstance(factor, (int, float)):
            return Currency(self._amount * factor, self._code)
        return NotImplemented

    def __rmul__(self, factor):
        return self.__mul__(factor)

    def __eq__(self, other):
        if isinstance(other, Currency):
            return self._amount == other._amount and self._code == other._code
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Currency):
            if self._code != other._code:
                raise ValueError("Cannot compare different currencies")
            return self._amount < other._amount
        return NotImplemented

    def __hash__(self):
        return hash((self._amount, self._code))


print("\n--- Currency Class ---")
price = Currency(99.99)
tax = Currency(8.50)
total = price + tax

print(f"Price: {price}")     # $99.99
print(f"Tax: {tax}")         # $8.50
print(f"Total: {total}")     # $108.49
print(f"Double: {price * 2}")  # $199.98
```
