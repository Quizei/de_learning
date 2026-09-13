# Week 3 Practice Exercises: OOP, Data Classes & Patterns

Complete each exercise. Solutions are at the bottom.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
```

## EXERCISE 1: Magic Methods

```python
"""
Create a `Money` class that:
- Has amount and currency attributes
- Supports addition with same currency: money1 + money2
- Supports multiplication by scalar: money * 2
- Has proper __repr__ and __str__
- Raises ValueError when adding different currencies

Example:
    m1 = Money(100, "USD")
    m2 = Money(50, "USD")
    m3 = m1 + m2  # Money(150, "USD")
    m4 = m1 * 2   # Money(200, "USD")
    print(m1)     # "$100.00"
"""

class Money():
    def __init__(self , amount , currency = 'INR'):
        self.amount = amount
        self.currency = currency
        
    def __repr__(self):
        return f"repr call {self.amount} {self.currency}"
        
    def __str__(self):
        return f"str call {self.amount} {self.currency}"
    
    def __add__(self , other):
        if not isinstance(other , Money):
              return NotImplemented
        if other.currency != self.currency:
            raise ValueError("Differet Currecy")
        return Money(self.amount + other.amount , self.currency)
        
    def __mul__(self , num):
        if not (isinstance(num , int) or isinstance(num , float)):
            raise ValueError("Not implemented")
        if num < 0:
            raise ValueError("Can't multiply negative number")
        return Money(self.amount * num , self.currency)
        
m1 = Money(20)
print(m1.__mul__(5.3))
print(m1)
m2 = Money(30)
print(m1+m2)
```

## EXERCISE 2: Property Decorators

```python
"""
Create a `BankAccount` class with:
- Private balance attribute
- Property `balance` (read-only)
- Property `is_overdrawn` (computed)
- Methods deposit(amount) and withdraw(amount)
- Withdraw should raise ValueError if insufficient funds

Example:
    account = BankAccount(100)
    account.deposit(50)     # balance = 150
    account.withdraw(30)    # balance = 120
    account.is_overdrawn    # False
"""

class BankAccount():
    def __init__(self , balance):
        self._balance = balance
    
    @property
    def balance(self):
        return self._balance
    @property       
    def is_overdrawn(self):
        return self._balance < 0
            
    def deposit(self , amount = 0):
        self._balance += amount
        
    def withdraw(self , amount =0):
        if self._balance < amount:
            raise ValueError("Insufficient funds")
        self._balance -= amount
```

## EXERCISE 3: Data Class

```python
"""
Create a `Task` dataclass with:
- id: int
- title: str
- description: str (default empty string)
- priority: int (default 1, range 1-5)
- tags: List[str] (default empty list)
- created_at: datetime (auto-set)
- completed: bool (default False, not in repr)

Add a method `add_tag(tag)` that adds a tag if not already present.
"""

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Task:
    id: int
    title: str
    description: str = field(default=" ")
    priority: int = 1
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed: bool = field(default=False, repr=False)
    
    def __post_init__(self):
        if not 1 <= self.priority <= 5:
            raise ValueError("worng priority")
```

## EXERCISE 4: Abstract Base Class

```python
"""
Create an abstract `Notification` class with:
- Abstract method send(message: str) -> bool
- Abstract property recipient

Then create concrete classes:
- EmailNotification(email_address)
- SMSNotification(phone_number)

Both should implement send() to return True and print the message.
"""

from abc import ABC, abstractmethod


class Notification(ABC):

    @abstractmethod
    def send(self, message: str) -> bool:
        pass

    @property
    @abstractmethod
    def recipient(self) -> str:
        pass

    @recipient.setter
    @abstractmethod
    def recipient(self, value: str) -> None:
        pass
    
class EmailNotification(Notification):
    def __init__(self, email_address: str):
        self.email_address = email_address
        self._recipient = None
        self._messages = None

    def send(self, message: str) -> bool:
        if not self._recipient:
            raise ValueError("Recipient not set")

        self._messages = message
        print(
            f"Sending '{message}' to {self._recipient} "
            f"via {self.email_address}"
        )
        return True

    @property
    def recipient(self) -> str:
        return self._recipient

    @recipient.setter
    def recipient(self, value: str) -> None:
        self._recipient = value
        

class SMSNotification(Notification):
    def __init__(self , phone_number):
        self.phone_number = phone_number
        self._recipient = None
        self._message = []
        
    def send(self, message: str) -> bool:
        if not self._recipient:
            raise ValueError("Recipient not set")

        self._messages = message
        print(
            f"Sending '{message}' to {self._recipient} "
            f"via {self.phone_number}"
        )
        return True

    @property
    def recipient(self) -> str:
        return self._recipient

    @recipient.setter
    def recipient(self, value: str) -> None:
        self._recipient = value
```

## EXERCISE 5: Factory Pattern

```python
"""
Create a `StorageFactory` that creates different storage backends:
- LocalStorage: stores in a dict, has save(key, value) and load(key)
- S3Storage: simulates S3, has save(key, value) and load(key)
- RedisStorage: simulates Redis, has save(key, value) and load(key)

Factory.create("local") returns LocalStorage instance, etc.
"""

from abc import ABC, abstractmethod
from typing import Any

class Storage(ABC):

    @abstractmethod
    def save(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def load(self, key: str) -> Any:
        pass

class LocalStorage(Storage):
    def __init__(self):
        self._data = {}

    def save(self, key: str, value: Any) -> None:
        self._data[key] = value

    def load(self, key: str) -> Any:
        return self._data.get(key)

class S3Storage(Storage):
    def __init__(self):
        self._data = {}

    def save(self, key: str, value: Any) -> None:
        print(f"[S3] Saving {key}")
        self._data[key] = value

    def load(self, key: str) -> Any:
        print(f"[S3] Loading {key}")
        return self._data.get(key)

class StorageFactory:
    _storages = {
        "local": LocalStorage,
        "s3": S3Storage,
    }

    _instances = {}   
    @classmethod
    def create(cls, storage_type: str):
        storage_type = storage_type.lower()

        if storage_type not in cls._instances:
            storage_class = cls._storages.get(storage_type)
            if not storage_class:
                raise ValueError("Unknown storage")

            cls._instances[storage_type] = storage_class()

        return cls._instances[storage_type]
```

## EXERCISE 6: Strategy Pattern

```python
"""
Create a pricing strategy system:
- PricingStrategy (abstract): calculate_price(base_price, quantity) -> float
- RegularPricing: no discount
- BulkPricing: 10% off if quantity >= 10
- PremiumPricing: 20% off always

Create a ShoppingCart that can use any pricing strategy.
"""

class PricingStrategy(ABC):
    # Your code here
    pass


class ShoppingCart:
    # Your code here
    pass
```

## EXERCISE 7: Builder Pattern

```python
"""
Create an `EmailBuilder` to build email messages:
- from_address(email)
- to(email) - can be called multiple times
- subject(text)
- body(text)
- attach(filename)
- build() -> returns Email dataclass

Example:
    email = (EmailBuilder()
        .from_address("sender@example.com")
        .to("recipient1@example.com")
        .to("recipient2@example.com")
        .subject("Hello")
        .body("Message body")
        .attach("file.pdf")
        .build())
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Email:
    from_addr: str
    to_addrs: List[str]
    subject: str
    body: str
    attachments: List[str] = field(default_factory=list)


class EmailBuilder:
    def __init__(self):
        self._from_addr = None
        self._to_addrs = []
        self._subject = ""
        self._body = ""
        self._attachments = []

    def from_address(self, sender: str) -> "EmailBuilder":
        self._from_addr = sender
        return self

    def to(self, recipient: str) -> "EmailBuilder":
        self._to_addrs.append(recipient)
        return self

    def subject(self, text: str) -> "EmailBuilder":
        self._subject = text
        return self

    def body(self, text: str) -> "EmailBuilder":
        self._body = text
        return self

    def attach(self, filename: str) -> "EmailBuilder":
        self._attachments.append(filename)
        return self

    def build(self) -> Email:
        if not self._from_addr:
            raise ValueError("Sender is required")
        if not self._to_addrs:
            raise ValueError("At least one recipient is required")

        return Email(
            from_addr=self._from_addr,
            to_addrs=self._to_addrs,
            subject=self._subject,
            body=self._body,
            attachments=self._attachments
        )
builder = EmailBuilder()
email1 = builder.from_address(...).to(...).build()
print(email1)
email2 = builder.to("new@example.com").build()        
print(email2)
```

## EXERCISE 8: Observer Pattern

```python
"""
Create a `Stock` class that notifies observers when price changes:
- Stock(symbol, price)
- Property `price` with setter that notifies observers
- Method add_observer(callback)
- Method remove_observer(callback)

Observers are functions that receive (symbol, old_price, new_price).
"""

from dataclasses import dataclass, field
from typing import List

class Stock():
    def __init__(self , symbol , price):
        self.symbol = symbol
        self._price = price
        self._observers= []
        
    @property
    def price(self):
        return self._price
        
    @price.setter
    def price(self , value):
        old_price = self._price
        self._price = value
        for observer in self._observers:
            observer(self.symbol , old_price , value)
            
    def add_observer(self , observer):
        self._observers.append(observer)
            
def callable(symbol , old , new):
    print(f"  {symbol}: ${old:.2f} -> ${new:.2f}")
    
stock = Stock("AAPL", 150.0)
stock.add_observer(callable)
stock.price = 155.0
stock.price = 152.0
```

## EXERCISE 9: Singleton Logger

```python
"""
Create a `Logger` singleton class:
- Only one instance should exist
- Has methods: debug(msg), info(msg), warning(msg), error(msg)
- Each method prints: "[LEVEL] message"
- Has a `level` property to filter messages (DEBUG=0, INFO=1, WARNING=2, ERROR=3)
"""

class Logger:
    _instance = None  # Class variable to hold the single instance

    def __new__(cls):
        # 1. If the instance doesn't exist yet, create it
        if cls._instance is None:
            # We call the parent class (object) to allocate memory
            cls._instance = super().__new__(cls)
            
            # 2. Initialize your properties HERE inside the 'if' block
            # This ensures they are only set ONCE for the life of the app
            cls._instance.level = 0 
            
        # 3. Always return the same stored instance
        return cls._instance

    # Your methods are already perfect!
    def debug(self, msg):
        if self.level <= 0:
            print(f"[DEBUG] {msg}")

    def info(self, msg):
        if self.level <= 1:
            print(f"[INFO] {msg}")

    def warning(self, msg):
        if self.level <= 2:
            print(f"[WARNING] {msg}")

    def error(self, msg):
        if self.level <= 3:
            print(f"[ERROR] {msg}")

# --- TEST DRIVE ---
logger1 = Logger()
logger2 = Logger()

print(f"Are they the same? {logger1 is logger2}") # Now this will print True!

logger1.level = 2
print("\n--- Testing Output (Level 2) ---")
logger1.debug("Hidden") 
logger2.warning("Visible!")
```

## EXERCISE 10: Complete System

```python
"""
Create a simple order processing system:

1. Product dataclass (id, name, price)
2. Order dataclass (id, products: List[Product], status)
3. OrderProcessor with Strategy pattern for different processors:
   - StandardProcessor: processes normally
   - ExpressProcessor: adds $10 fee, marks as "express"
4. OrderRepository (in-memory) to save/load orders
5. OrderEventManager to emit events: "order_created", "order_processed"
"""

# Your code here
```

## SOLUTIONS (Don't look until you've tried!)

```python
"""
Scroll down for solutions...



















"""

def show_solutions():
    print("=" * 50)
    print("SOLUTIONS")
    print("=" * 50)

    # Exercise 1
    print("\n--- Exercise 1: Money ---")

    class Money:
        def __init__(self, amount: float, currency: str = "USD"):
            self.amount = amount
            self.currency = currency

        def __repr__(self):
            return f"Money({self.amount}, '{self.currency}')"

        def __str__(self):
            symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
            symbol = symbols.get(self.currency, self.currency)
            return f"{symbol}{self.amount:.2f}"

        def __add__(self, other):
            if not isinstance(other, Money):
                return NotImplemented
            if self.currency != other.currency:
                raise ValueError("Cannot add different currencies")
            return Money(self.amount + other.amount, self.currency)

        def __mul__(self, scalar):
            if isinstance(scalar, (int, float)):
                return Money(self.amount * scalar, self.currency)
            return NotImplemented

        def __rmul__(self, scalar):
            return self.__mul__(scalar)

    m1 = Money(100, "USD")
    m2 = Money(50, "USD")
    print(f"m1 + m2 = {m1 + m2}")
    print(f"m1 * 2 = {m1 * 2}")
    print(f"str(m1) = {m1}")

    # Exercise 2
    print("\n--- Exercise 2: BankAccount ---")

    class BankAccount:
        def __init__(self, initial_balance: float = 0):
            self._balance = initial_balance

        @property
        def balance(self):
            return self._balance

        @property
        def is_overdrawn(self):
            return self._balance < 0

        def deposit(self, amount: float):
            if amount <= 0:
                raise ValueError("Deposit amount must be positive")
            self._balance += amount

        def withdraw(self, amount: float):
            if amount > self._balance:
                raise ValueError("Insufficient funds")
            self._balance -= amount

    account = BankAccount(100)
    account.deposit(50)
    print(f"Balance after deposit: {account.balance}")
    account.withdraw(30)
    print(f"Balance after withdraw: {account.balance}")

    # Exercise 3
    print("\n--- Exercise 3: Task ---")

    @dataclass
    class Task:
        id: int
        title: str
        description: str = ""
        priority: int = 1
        tags: List[str] = field(default_factory=list)
        created_at: datetime = field(default_factory=datetime.now)
        completed: bool = field(default=False, repr=False)

        def add_tag(self, tag: str):
            if tag not in self.tags:
                self.tags.append(tag)

    task = Task(1, "Complete exercise", priority=3)
    task.add_tag("python")
    task.add_tag("practice")
    print(f"Task: {task}")

    # Exercise 4
    print("\n--- Exercise 4: Notification ---")

    class Notification(ABC):
        @abstractmethod
        def send(self, message: str) -> bool:
            pass

        @property
        @abstractmethod
        def recipient(self) -> str:
            pass

    class EmailNotification(Notification):
        def __init__(self, email_address: str):
            self._email = email_address

        @property
        def recipient(self) -> str:
            return self._email

        def send(self, message: str) -> bool:
            print(f"Email to {self._email}: {message}")
            return True

    class SMSNotification(Notification):
        def __init__(self, phone_number: str):
            self._phone = phone_number

        @property
        def recipient(self) -> str:
            return self._phone

        def send(self, message: str) -> bool:
            print(f"SMS to {self._phone}: {message}")
            return True

    email = EmailNotification("test@example.com")
    email.send("Hello!")

    # Exercise 5
    print("\n--- Exercise 5: Storage Factory ---")

    class LocalStorage(Storage):
        def __init__(self):
            self._data = {}

        def save(self, key: str, value: Any) -> None:
            self._data[key] = value

        def load(self, key: str) -> Any:
            return self._data.get(key)

    class S3Storage(Storage):
        def __init__(self):
            self._data = {}

        def save(self, key: str, value: Any) -> None:
            print(f"[S3] Saving {key}")
            self._data[key] = value

        def load(self, key: str) -> Any:
            print(f"[S3] Loading {key}")
            return self._data.get(key)

    class StorageFactory:
        _storages = {
            "local": LocalStorage,
            "s3": S3Storage,
        }

        @classmethod
        def create(cls, storage_type: str) -> Storage:
            storage_class = cls._storages.get(storage_type.lower())
            if not storage_class:
                raise ValueError(f"Unknown storage: {storage_type}")
            return storage_class()

    storage = StorageFactory.create("local")
    storage.save("key1", "value1")
    print(f"Loaded: {storage.load('key1')}")

    # Exercise 6
    print("\n--- Exercise 6: Pricing Strategy ---")

    class PricingStrategy(ABC):
        @abstractmethod
        def calculate_price(self, base_price: float, quantity: int) -> float:
            pass

    class RegularPricing(PricingStrategy):
        def calculate_price(self, base_price: float, quantity: int) -> float:
            return base_price * quantity

    class BulkPricing(PricingStrategy):
        def calculate_price(self, base_price: float, quantity: int) -> float:
            total = base_price * quantity
            if quantity >= 10:
                total *= 0.9
            return total

    class ShoppingCart:
        def __init__(self, strategy: PricingStrategy = None):
            self.strategy = strategy or RegularPricing()

        def calculate_total(self, base_price: float, quantity: int) -> float:
            return self.strategy.calculate_price(base_price, quantity)

    cart = ShoppingCart(BulkPricing())
    print(f"Bulk pricing (10 items at $10): ${cart.calculate_total(10, 10)}")

    # Exercise 7
    print("\n--- Exercise 7: Email Builder ---")

    class EmailBuilder:
        def __init__(self):
            self._from = ""
            self._to = []
            self._subject = ""
            self._body = ""
            self._attachments = []

        def from_address(self, email: str) -> 'EmailBuilder':
            self._from = email
            return self

        def to(self, email: str) -> 'EmailBuilder':
            self._to.append(email)
            return self

        def subject(self, text: str) -> 'EmailBuilder':
            self._subject = text
            return self

        def body(self, text: str) -> 'EmailBuilder':
            self._body = text
            return self

        def attach(self, filename: str) -> 'EmailBuilder':
            self._attachments.append(filename)
            return self

        def build(self) -> Email:
            return Email(
                from_addr=self._from,
                to_addrs=self._to,
                subject=self._subject,
                body=self._body,
                attachments=self._attachments
            )

    email = (EmailBuilder()
        .from_address("sender@example.com")
        .to("recipient@example.com")
        .subject("Test")
        .body("Hello!")
        .build())
    print(f"Email: {email}")

    # Exercise 8
    print("\n--- Exercise 8: Stock Observer ---")

    class Stock:
        def __init__(self, symbol: str, price: float):
            self.symbol = symbol
            self._price = price
            self._observers = []

        @property
        def price(self) -> float:
            return self._price

        @price.setter
        def price(self, value: float):
            old_price = self._price
            self._price = value
            for observer in self._observers:
                observer(self.symbol, old_price, value)

        def add_observer(self, callback):
            self._observers.append(callback)

        def remove_observer(self, callback):
            self._observers.remove(callback)

    def price_alert(symbol, old, new):
        print(f"  {symbol}: ${old:.2f} -> ${new:.2f}")

    stock = Stock("AAPL", 150.0)
    stock.add_observer(price_alert)
    stock.price = 155.0
    stock.price = 152.0

    print("\n✅ All solutions demonstrated!")


if __name__ == "__main__":
    print("Complete the exercises above, then run show_solutions()")
    # Uncomment to see solutions:
    # show_solutions()
```
