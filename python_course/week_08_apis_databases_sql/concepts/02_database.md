# Database Connectivity

Working with SQLite and database patterns.

```python
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional
```

## BASIC SQLITE

```python
print("--- Basic SQLite ---")

# Connect and create table
conn = sqlite3.connect(':memory:')  # In-memory database
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        age INTEGER
    )
''')

# Insert data
cursor.execute(
    "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
    ('Alice', 'alice@example.com', 30)
)

# Insert multiple
users = [
    ('Bob', 'bob@example.com', 25),
    ('Charlie', 'charlie@example.com', 35),
]
cursor.executemany(
    "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
    users
)
conn.commit()

# Query
cursor.execute("SELECT * FROM users")
print("All users:", cursor.fetchall())

cursor.execute("SELECT name, age FROM users WHERE age > ?", (26,))
print("Age > 26:", cursor.fetchall())
```

## ROW FACTORY

```python
print("\n--- Row Factory ---")

conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM users WHERE id = 1")
row = cursor.fetchone()
print(f"Name: {row['name']}, Email: {row['email']}")
```

## CONTEXT MANAGER

```python
print("\n--- Context Manager ---")

@contextmanager
def get_db_connection(db_path=':memory:'):
    """Database connection context manager."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

## REPOSITORY PATTERN

```python
print("\n--- Repository Pattern ---")

@dataclass
class User:
    id: Optional[int]
    name: str
    email: str
    age: int

class UserRepository:
    """Repository for User operations."""

    def __init__(self, conn):
        self.conn = conn
        self._ensure_table()

    def _ensure_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                age INTEGER
            )
        ''')

    def create(self, user: User) -> User:
        cursor = self.conn.execute(
            "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
            (user.name, user.email, user.age)
        )
        user.id = cursor.lastrowid
        return user

    def get_by_id(self, user_id: int) -> Optional[User]:
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return User(id=row['id'], name=row['name'],
                       email=row['email'], age=row['age'])
        return None

    def get_all(self) -> List[User]:
        cursor = self.conn.execute("SELECT * FROM users")
        return [User(id=r['id'], name=r['name'],
                    email=r['email'], age=r['age'])
                for r in cursor.fetchall()]

    def update(self, user: User) -> None:
        self.conn.execute(
            "UPDATE users SET name=?, email=?, age=? WHERE id=?",
            (user.name, user.email, user.age, user.id)
        )

    def delete(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM users WHERE id=?", (user_id,))

# Usage
conn = sqlite3.connect(':memory:')
conn.row_factory = sqlite3.Row
repo = UserRepository(conn)

user = repo.create(User(None, 'David', 'david@example.com', 28))
print(f"Created: {user}")

all_users = repo.get_all()
print(f"All users: {all_users}")

conn.close()
```

## SQL INJECTION PREVENTION

```python
print("\n--- SQL Injection Prevention ---")
print("""
NEVER do this:
  cursor.execute(f"SELECT * FROM users WHERE name = '{user_input}'")

ALWAYS use parameterized queries:
  cursor.execute("SELECT * FROM users WHERE name = ?", (user_input,))
""")

print("\n✅ Database basics complete!")
```
