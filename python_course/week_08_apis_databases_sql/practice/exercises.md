# Week 8 Practice Exercises: APIs & Databases

```python
import sqlite3
from contextlib import contextmanager

def show_solutions():
    print("=== SOLUTIONS ===")

    # Exercise 1: Create an API client with retry
    print("\n--- API Client with Retry ---")

    import time

    class RobustAPIClient:
        def __init__(self, base_url, max_retries=3):
            self.base_url = base_url
            self.max_retries = max_retries

        def get(self, endpoint):
            for attempt in range(self.max_retries):
                try:
                    print(f"Attempt {attempt + 1}: GET {endpoint}")
                    # Simulate success on 3rd attempt
                    if attempt < 2:
                        raise ConnectionError("Network error")
                    return {"status": "ok"}
                except ConnectionError as e:
                    if attempt == self.max_retries - 1:
                        raise
                    time.sleep(0.1)

    client = RobustAPIClient("https://api.example.com")
    print(client.get("/users"))

    # Exercise 2: Database CRUD
    print("\n--- Database CRUD ---")

    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            price REAL
        )
    ''')

    # Create
    cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", ("Widget", 29.99))

    # Read
    cursor.execute("SELECT * FROM products")
    print(f"Products: {cursor.fetchall()[0]['name']}")

    # Update
    cursor.execute("UPDATE products SET price = ? WHERE name = ?", (39.99, "Widget"))

    # Delete
    cursor.execute("DELETE FROM products WHERE name = ?", ("Widget",))

    conn.commit()
    conn.close()

    # Exercise 3: Transaction handling
    print("\n--- Transaction Handling ---")

    @contextmanager
    def transaction(conn):
        try:
            yield conn.cursor()
            conn.commit()
            print("Transaction committed")
        except Exception as e:
            conn.rollback()
            print(f"Transaction rolled back: {e}")
            raise

    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE accounts (id INTEGER, balance REAL)")
    cursor.execute("INSERT INTO accounts VALUES (1, 100)")
    cursor.execute("INSERT INTO accounts VALUES (2, 50)")
    conn.commit()

    with transaction(conn) as cur:
        cur.execute("UPDATE accounts SET balance = balance - 30 WHERE id = 1")
        cur.execute("UPDATE accounts SET balance = balance + 30 WHERE id = 2")

    conn.close()

    print("\n✅ All solutions demonstrated!")

if __name__ == "__main__":
    show_solutions()
```
