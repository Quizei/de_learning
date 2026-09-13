# Week 8 Project: API to Database Pipeline

Fetch data from API and store in database with proper error handling.

```python
import sqlite3
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
```

## MODELS

```python
@dataclass
class User:
    id: int
    name: str
    email: str
    username: str
```

## MOCK API CLIENT

```python
class MockAPIClient:
    """Simulates an external API."""

    def __init__(self):
        self._data = [
            {"id": 1, "name": "Alice Smith", "email": "alice@example.com", "username": "alice"},
            {"id": 2, "name": "Bob Jones", "email": "bob@example.com", "username": "bob"},
            {"id": 3, "name": "Charlie Brown", "email": "charlie@example.com", "username": "charlie"},
        ]

    def get_users(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        start = (page - 1) * limit
        end = start + limit
        users = self._data[start:end]
        return {
            "data": users,
            "page": page,
            "total": len(self._data)
        }
```

## DATABASE LAYER

```python
class Database:
    def __init__(self, db_path: str = ':memory:'):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self):
        if self.conn:
            self.conn.close()

    def _create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                username TEXT UNIQUE,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def upsert_user(self, user: User):
        self.conn.execute('''
            INSERT INTO users (id, name, email, username)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                email = excluded.email,
                username = excluded.username,
                synced_at = CURRENT_TIMESTAMP
        ''', (user.id, user.name, user.email, user.username))

    def get_all_users(self) -> List[Dict]:
        cursor = self.conn.execute("SELECT * FROM users")
        return [dict(row) for row in cursor.fetchall()]

    def commit(self):
        self.conn.commit()
```

## PIPELINE

```python
class APIToDatabasePipeline:
    def __init__(self, api_client: MockAPIClient, database: Database):
        self.api = api_client
        self.db = database
        self.stats = {"fetched": 0, "stored": 0, "errors": 0}

    def run(self):
        """Execute the pipeline."""
        print("Starting pipeline...")
        self.db.connect()

        try:
            # Fetch from API
            page = 1
            while True:
                response = self.api.get_users(page=page)
                users_data = response["data"]

                if not users_data:
                    break

                self.stats["fetched"] += len(users_data)

                # Transform and store
                for data in users_data:
                    try:
                        user = User(
                            id=data["id"],
                            name=data["name"],
                            email=data["email"],
                            username=data["username"]
                        )
                        self.db.upsert_user(user)
                        self.stats["stored"] += 1
                    except Exception as e:
                        print(f"Error storing user {data['id']}: {e}")
                        self.stats["errors"] += 1

                page += 1

            self.db.commit()
            print(f"Pipeline complete: {self.stats}")

        finally:
            self.db.close()

    def get_results(self):
        self.db.connect()
        users = self.db.get_all_users()
        self.db.close()
        return users

def main():
    # Initialize components
    api = MockAPIClient()
    db = Database(':memory:')

    # Run pipeline
    pipeline = APIToDatabasePipeline(api, db)
    pipeline.run()

    # Verify results
    print("\nStored users:")
    db.connect()
    for user in db.get_all_users():
        print(f"  {user['name']} ({user['email']})")
    db.close()

if __name__ == "__main__":
    main()
```
