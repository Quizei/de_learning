# Collections Module: namedtuple

namedtuple creates tuple subclasses with named fields.
More readable than regular tuples, immutable like tuples.
Lighter weight than classes.

```python
from collections import namedtuple

# Creating a namedtuple
Point = namedtuple('Point', ['x', 'y'])

# Alternative syntax options
Point2 = namedtuple('Point2', 'x y')  # Space-separated string
Point3 = namedtuple('Point3', 'x, y')  # Comma-separated string

# Creating instances
p1 = Point(3, 4)
p2 = Point(x=5, y=6)

# Accessing fields
print(f"Point: ({p1.x}, {p1.y})")  # By name
print(f"Point: ({p1[0]}, {p1[1]})")  # By index

# Unpacking
x, y = p1
print(f"Unpacked: x={x}, y={y}")

# Immutable - cannot modify
# p1.x = 10  # AttributeError!

# Creating new instance with modifications
p3 = p1._replace(x=10)
print(f"Original: {p1}, New: {p3}")

# Useful methods and attributes
print("Fields:", Point._fields)  # ('x', 'y')
print("As dict:", p1._asdict())  # {'x': 3, 'y': 4}

# Creating from iterable
data = [7, 8]
p4 = Point._make(data)
print(f"From list: {p4}")

# Default values (Python 3.7+)
Person = namedtuple('Person', ['name', 'age', 'city'], defaults=['Unknown', 0, 'N/A'])
print(Person('Alice'))  # Person(name='Alice', age=0, city='N/A')
print(Person('Bob', 25))  # Person(name='Bob', age=25, city='N/A')

# Real-world example 1: Data records
Employee = namedtuple('Employee', ['id', 'name', 'department', 'salary'])

employees = [
    Employee(1, 'Alice', 'Engineering', 80000),
    Employee(2, 'Bob', 'Marketing', 70000),
    Employee(3, 'Charlie', 'Engineering', 85000),
]

# Query-like operations
engineering = [e for e in employees if e.department == 'Engineering']
avg_salary = sum(e.salary for e in engineering) / len(engineering)
print(f"\nEngineering avg salary: ${avg_salary:,.0f}")

# Real-world example 2: API response parsing
APIResponse = namedtuple('APIResponse', ['status_code', 'data', 'error'])

def mock_api_call():
    return APIResponse(
        status_code=200,
        data={'users': ['alice', 'bob']},
        error=None
    )

response = mock_api_call()
if response.status_code == 200:
    print("Users:", response.data['users'])

# Real-world example 3: Database rows
Row = namedtuple('Row', ['id', 'created_at', 'value'])

# Simulating database results
db_results = [
    (1, '2024-01-01', 100),
    (2, '2024-01-02', 200),
    (3, '2024-01-03', 150),
]

# Convert to namedtuples for clarity
rows = [Row._make(r) for r in db_results]
for row in rows:
    print(f"ID {row.id}: {row.value} on {row.created_at}")

# Comparison with regular tuple
# Regular tuple - hard to read
user_tuple = ('alice', 'alice@example.com', 25, 'Engineer')
print(f"\nTuple email: {user_tuple[1]}")  # Which index is email?

# Namedtuple - self-documenting
User = namedtuple('User', ['name', 'email', 'age', 'role'])
user = User('alice', 'alice@example.com', 25, 'Engineer')
print(f"Namedtuple email: {user.email}")  # Crystal clear!
```
