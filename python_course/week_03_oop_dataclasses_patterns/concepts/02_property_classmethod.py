"""
Property, Classmethod, and Staticmethod
=======================================
Special method decorators for different types of methods.
"""

# ================================
# @property - Managed Attributes
# ================================

class Temperature:
    """Temperature with Celsius as internal representation."""

    def __init__(self, celsius=0):
        self._celsius = celsius

    @property
    def celsius(self):
        """Get temperature in Celsius."""
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        """Set temperature in Celsius with validation."""
        if value < -273.15:
            raise ValueError("Temperature cannot be below absolute zero")
        self._celsius = value

    @celsius.deleter
    def celsius(self):
        """Reset temperature."""
        self._celsius = 0

    @property
    def fahrenheit(self):
        """Get temperature in Fahrenheit (computed property)."""
        return self._celsius * 9/5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value):
        """Set temperature via Fahrenheit."""
        self._celsius = (value - 32) * 5/9

    @property
    def kelvin(self):
        """Get temperature in Kelvin."""
        return self._celsius + 273.15


print("--- @property ---")
temp = Temperature(25)
print(f"Celsius: {temp.celsius}")       # 25
print(f"Fahrenheit: {temp.fahrenheit}") # 77.0
print(f"Kelvin: {temp.kelvin}")         # 298.15

temp.fahrenheit = 100  # Set via Fahrenheit
print(f"After setting 100°F: {temp.celsius:.1f}°C")  # 37.8°C


# Computed property that caches
class Circle:
    """Circle with cached computed properties."""

    def __init__(self, radius):
        self._radius = radius
        self._area = None  # Cache

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, value):
        if value < 0:
            raise ValueError("Radius cannot be negative")
        self._radius = value
        self._area = None  # Invalidate cache

    @property
    def area(self):
        """Computed and cached area."""
        if self._area is None:
            import math
            self._area = math.pi * self._radius ** 2
            print("  (Computing area...)")
        return self._area

    @property
    def diameter(self):
        return self._radius * 2


print("\n--- Cached Property ---")
c = Circle(5)
print(f"Area: {c.area:.2f}")  # Computes
print(f"Area: {c.area:.2f}")  # Cached
c.radius = 10
print(f"Area: {c.area:.2f}")  # Recomputes


# ================================
# @classmethod - Alternative Constructors
# ================================

class Date:
    """Date class with multiple constructors."""

    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day

    def __repr__(self):
        return f"Date({self.year}, {self.month}, {self.day})"

    @classmethod
    def from_string(cls, date_string):
        """Create Date from 'YYYY-MM-DD' string."""
        year, month, day = map(int, date_string.split('-'))
        return cls(year, month, day)

    @classmethod
    def from_timestamp(cls, timestamp):
        """Create Date from Unix timestamp."""
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp)
        return cls(dt.year, dt.month, dt.day)

    @classmethod
    def today(cls):
        """Create Date for today."""
        import datetime
        today = datetime.date.today()
        return cls(today.year, today.month, today.day)


print("\n--- @classmethod ---")
d1 = Date(2024, 1, 15)
d2 = Date.from_string("2024-06-20")
d3 = Date.today()

print(f"Direct: {d1}")
print(f"From string: {d2}")
print(f"Today: {d3}")


# Classmethod with inheritance
class Employee:
    """Base employee class."""

    def __init__(self, name, salary):
        self.name = name
        self.salary = salary

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.name}', {self.salary})"

    @classmethod
    def from_dict(cls, data):
        """Create from dictionary - works with subclasses too!"""
        return cls(data['name'], data['salary'])


class Manager(Employee):
    """Manager with team."""

    def __init__(self, name, salary, team_size=0):
        super().__init__(name, salary)
        self.team_size = team_size


print("\n--- Classmethod with Inheritance ---")
# from_dict works correctly for subclass
emp_data = {'name': 'Alice', 'salary': 50000}
emp = Employee.from_dict(emp_data)
mgr = Manager.from_dict(emp_data)  # Creates Manager, not Employee!

print(f"Employee: {emp}")
print(f"Manager: {mgr}")


# ================================
# @staticmethod - Utility Functions
# ================================

class MathUtils:
    """Math utilities as static methods."""

    @staticmethod
    def is_prime(n):
        """Check if number is prime."""
        if n < 2:
            return False
        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                return False
        return True

    @staticmethod
    def factorial(n):
        """Calculate factorial."""
        if n <= 1:
            return 1
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

    @staticmethod
    def gcd(a, b):
        """Greatest common divisor."""
        while b:
            a, b = b, a % b
        return a


print("\n--- @staticmethod ---")
print(f"is_prime(17): {MathUtils.is_prime(17)}")  # True
print(f"factorial(5): {MathUtils.factorial(5)}")  # 120
print(f"gcd(48, 18): {MathUtils.gcd(48, 18)}")    # 6


# ================================
# WHEN TO USE EACH
# ================================

class DataProcessor:
    """Demonstrates when to use each type."""

    # Class attribute
    default_encoding = "utf-8"

    def __init__(self, data):
        self._data = data
        self._processed = False

    # Regular method - needs instance
    def process(self):
        """Process the data (needs instance)."""
        self._processed = True
        return self._data.upper()

    # Property - computed attribute
    @property
    def is_processed(self):
        """Check if data was processed (computed attribute)."""
        return self._processed

    # Class method - alternative constructor or class-level operation
    @classmethod
    def from_file(cls, filepath, encoding=None):
        """Create from file (alternative constructor)."""
        enc = encoding or cls.default_encoding
        # In real code: with open(filepath, encoding=enc) as f:
        return cls(f"data from {filepath}")

    @classmethod
    def set_default_encoding(cls, encoding):
        """Modify class state."""
        cls.default_encoding = encoding

    # Static method - utility that doesn't need class or instance
    @staticmethod
    def validate_data(data):
        """Validate data format (utility function)."""
        return isinstance(data, str) and len(data) > 0


print("\n--- When to Use Each ---")
print("""
@property:
  - Computed attributes
  - Attribute validation
  - Lazy loading

@classmethod:
  - Alternative constructors (from_string, from_file, etc.)
  - Factory methods
  - Modifying class state
  - Works correctly with inheritance

@staticmethod:
  - Utility functions related to the class
  - Don't need access to instance or class
  - Could be a module function, but logically belongs to class
""")


# ================================
# PRACTICAL EXAMPLE: USER MODEL
# ================================

import hashlib
from datetime import datetime

class User:
    """User model with various method types."""

    _user_count = 0

    def __init__(self, username, email, password):
        self._username = username
        self._email = email
        self._password_hash = self._hash_password(password)
        self._created_at = datetime.now()
        User._user_count += 1

    # Properties for controlled access
    @property
    def username(self):
        return self._username

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, value):
        if not self.validate_email(value):
            raise ValueError("Invalid email format")
        self._email = value

    @property
    def created_at(self):
        return self._created_at

    # Regular methods
    def check_password(self, password):
        """Verify password."""
        return self._password_hash == self._hash_password(password)

    def update_password(self, old_password, new_password):
        """Update password with verification."""
        if not self.check_password(old_password):
            raise ValueError("Invalid current password")
        self._password_hash = self._hash_password(new_password)

    # Class methods
    @classmethod
    def get_user_count(cls):
        """Get total users created."""
        return cls._user_count

    @classmethod
    def from_dict(cls, data):
        """Create user from dictionary."""
        return cls(data['username'], data['email'], data['password'])

    # Static methods
    @staticmethod
    def validate_email(email):
        """Validate email format."""
        import re
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return bool(re.match(pattern, email))

    @staticmethod
    def _hash_password(password):
        """Hash password (should use bcrypt in production)."""
        return hashlib.sha256(password.encode()).hexdigest()


print("\n--- User Model Example ---")
user = User("alice", "alice@example.com", "secret123")
print(f"Username: {user.username}")
print(f"Email: {user.email}")
print(f"Password check: {user.check_password('secret123')}")
print(f"Total users: {User.get_user_count()}")
