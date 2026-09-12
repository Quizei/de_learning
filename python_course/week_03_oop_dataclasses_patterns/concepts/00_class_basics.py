"""
Class Basics in Python
======================
Classes are blueprints for creating objects. They bundle data (attributes)
and behavior (methods) into a single unit. This is the foundation of
Object-Oriented Programming (OOP).
"""

# ================================
# WHAT IS A CLASS?
# ================================

# A class defines a new type. An object is an instance of that type.
# Think of a class as a cookie cutter and objects as the cookies.

class Dog:
    """A simple class representing a dog."""

    def __init__(self, name, breed):
        """Constructor - called automatically when you create an instance.
        'self' refers to the instance being created."""
        self.name = name    # instance attribute
        self.breed = breed  # instance attribute

    def bark(self):
        """An instance method - operates on a specific instance via 'self'."""
        return f"{self.name} says: Woof!"


# Creating instances (objects)
dog1 = Dog("Rex", "German Shepherd")
dog2 = Dog("Buddy", "Golden Retriever")

print("--- What is a Class? ---")
print(f"dog1.name: {dog1.name}")       # Rex
print(f"dog2.breed: {dog2.breed}")     # Golden Retriever
print(f"dog1.bark(): {dog1.bark()}")   # Rex says: Woof!
print(f"type(dog1): {type(dog1)}")     # <class '__main__.Dog'>

# Each instance is independent
dog1.name = "Max"
print(f"dog1.name: {dog1.name}")  # Max (changed)
print(f"dog2.name: {dog2.name}")  # Buddy (unchanged)


# ================================
# INSTANCE vs CLASS ATTRIBUTES
# ================================

class Employee:
    """Demonstrates instance vs class attributes."""

    # Class attribute - shared by ALL instances
    company = "TechCorp"
    employee_count = 0

    def __init__(self, name, role):
        # Instance attributes - unique to EACH instance
        self.name = name
        self.role = role
        Employee.employee_count += 1  # modify class attribute via class name

    def info(self):
        return f"{self.name} ({self.role}) at {self.company}"


e1 = Employee("Alice", "Engineer")
e2 = Employee("Bob", "Manager")

print("\n--- Instance vs Class Attributes ---")
print(f"e1.info(): {e1.info()}")              # Alice (Engineer) at TechCorp
print(f"e2.info(): {e2.info()}")              # Bob (Manager) at TechCorp
print(f"Employee.employee_count: {Employee.employee_count}")  # 2

# Class attribute is shared - changing it affects all instances
Employee.company = "NewCorp"
print(f"e1.company: {e1.company}")  # NewCorp
print(f"e2.company: {e2.company}")  # NewCorp

# But assigning on an instance creates an instance attribute (shadows class attr)
e1.company = "StartupInc"
print(f"e1.company: {e1.company}")  # StartupInc (instance attribute)
print(f"e2.company: {e2.company}")  # NewCorp (still class attribute)
print(f"Yaha dekho : {e1.employee_count}")

# ================================
# METHODS: INSTANCE, SELF
# ================================

class BankAccount:
    """Demonstrates instance methods and how 'self' works."""

    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount):
        """Instance method - 'self' is passed automatically."""
        self.balance += amount
        return self.balance

    def withdraw(self, amount):
        if amount > self.balance:
            print(f"Insufficient funds! Balance: {self.balance}")
            return self.balance
        self.balance -= amount
        return self.balance

    def summary(self):
        return f"{self.owner}'s account: ${self.balance:,.2f}"


acc = BankAccount("Alice", 1000)
acc2 = BankAccount("Fardin")
print(acc2.summary())

print("\n--- Methods and Self ---")
print(acc.summary())            # Alice's account: $1,000.00
acc.deposit(500)
print(f"After deposit: {acc.summary()}")   # Alice's account: $1,500.00
acc.withdraw(200)
print(f"After withdraw: {acc.summary()}")  # Alice's account: $1,300.00
acc.withdraw(5000)              # Insufficient funds! Balance: 1300

# Behind the scenes: acc.deposit(500) is same as BankAccount.deposit(acc, 500)
# Python passes the instance as the first argument automatically.


# ================================
# INHERITANCE
# ================================

# Inheritance lets a class (child) reuse and extend another class (parent).

class Animal:
    """Parent / Base class."""

    def __init__(self, name, sound):
        self.name = name
        self.sound = sound

    def speak(self):
        return f"{self.name} says {self.sound}!"

    def info(self):
        return f"{self.name} is an animal"


class Cat(Animal):
    """Child class - inherits from Animal."""

    def __init__(self, name, indoor=True):
        # super() calls the parent's __init__
        super().__init__(name, sound="Meow")
        self.indoor = indoor  # new attribute specific to Cat

    def purr(self):
        """New method only Cat has."""
        return f"{self.name} purrs..."


class Lion(Animal):
    """Another child class."""

    def __init__(self, name):
        super().__init__(name, sound="ROAR")

    def speak(self):
        """Override parent method - Lion speaks differently."""
        return f"{self.name} ROARS loudly: {self.sound}!!!"


print("\n--- Inheritance ---")
cat = Cat("Whiskers")
lion = Lion("Simba")

print(cat.speak())    # Whiskers says Meow!  (inherited from Animal)
print(cat.purr())     # Whiskers purrs...    (Cat's own method)
print(cat.info())     # Whiskers is an animal (inherited from Animal)
print(f"Indoor: {cat.indoor}")  # True

print(lion.speak())   # Simba ROARS loudly: ROAR!!! (overridden method)
print(lion.info())    # Simba is an animal (inherited from Animal)

# isinstance() and issubclass()
print(f"\nisinstance(cat, Cat): {isinstance(cat, Cat)}")        # True
print(f"isinstance(cat, Animal): {isinstance(cat, Animal)}")   # True
print(f"isinstance(lion, Cat): {isinstance(lion, Cat)}")       # False
print(f"issubclass(Cat, Animal): {issubclass(Cat, Animal)}")   # True


# ================================
# METHOD RESOLUTION ORDER (MRO)
# ================================

# When a class inherits from multiple parents, Python uses MRO
# to determine which method to call. It follows C3 linearization.

class A:
    def greet(self):
        return "Hello from A"

class B(A):
    def greet(self):
        return "Hello from B"

class C(A):
    def greet(self):
        return "Hello from C"

class D(B, C):
    pass  # inherits from both B and C


print("\n--- Method Resolution Order ---")
d = D()
print(f"d.greet(): {d.greet()}")  # Hello from B (B comes first)
print(f"MRO: {[cls.__name__ for cls in D.__mro__]}")  # [D, B, C, A, object]


# ================================
# ENCAPSULATION: PUBLIC vs PRIVATE
# ================================

# Python uses naming conventions (not enforced access modifiers):
#   name     -> public (use freely)
#   _name    -> protected (convention: internal use)
#   __name   -> private (name-mangled to _ClassName__name)

class User:
    """Demonstrates naming conventions for access control."""

    def __init__(self, username, email, password):
        self.username = username     # public
        self._email = email          # protected (convention only)
        self.__password = password   # private (name-mangled)

    def check_password(self, attempt):
        """Public method to interact with private data."""
        return attempt == self.__password

    def get_email(self):
        return self._email


user = User("alice", "alice@mail.com", "secret123")

print("\n--- Encapsulation ---")
print(f"Public - username: {user.username}")     # alice
print(f"Protected - _email: {user._email}")      # alice@mail.com (accessible, but convention says don't)
print(f"check_password: {user.check_password('secret123')}")  # True

# __password is name-mangled, direct access raises AttributeError
try:
    print(user.__password)
except AttributeError as e:
    print(f"Cannot access __password: {e}")

# But it's still accessible via mangled name (Python doesn't truly enforce privacy)
print(f"Name-mangled: {user._User__password}")   # secret123


# ================================
# PRACTICAL EXAMPLE: SHAPE HIERARCHY
# ================================

import math

class Shape:
    """Base class for geometric shapes."""

    def __init__(self, color="black"):
        self.color = color

    def area(self):
        raise NotImplementedError("Subclasses must implement area()")

    def describe(self):
        return f"{self.color} {self.__class__.__name__} with area {self.area():.2f}"


class Circle(Shape):
    def __init__(self, radius, color="black"):
        super().__init__(color)
        self.radius = radius

    def area(self):
        return math.pi * self.radius ** 2


class Rectangle(Shape):
    def __init__(self, width, height, color="black"):
        super().__init__(color)
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height


class Square(Rectangle):
    """Square is a special Rectangle where width == height."""

    def __init__(self, side, color="black"):
        super().__init__(side, side, color)


print("\n--- Shape Hierarchy ---")
shapes = [
    Circle(5, "red"),
    Rectangle(4, 6, "blue"),
    Square(3, "green"),
]

for shape in shapes:
    print(shape.describe())
# red Circle with area 78.54
# blue Rectangle with area 24.00
# green Square with area 9.00

# Polymorphism: same method call, different behavior per class
print(f"\nAll are Shapes: {all(isinstance(s, Shape) for s in shapes)}")  # True
print(f"Square is Rectangle: {isinstance(Square(3), Rectangle)}")       # True
