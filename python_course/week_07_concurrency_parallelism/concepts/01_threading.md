# Threading in Python

Concurrent execution with threads (best for I/O-bound tasks).

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor
```

## BASIC THREADING

```python
print("--- Basic Threading ---")

def worker(name, delay):
    print(f"{name} starting")
    time.sleep(delay)
    print(f"{name} finished")

# Create and start threads
t1 = threading.Thread(target=worker, args=("Thread-1", 0.2))
t2 = threading.Thread(target=worker, args=("Thread-2", 0.1))

t1.start()
t2.start()

t1.join()  # Wait for completion
t2.join()

print("All threads done")
```

## THREAD POOL EXECUTOR

```python
print("\n--- ThreadPoolExecutor ---")

def fetch_url(url):
    time.sleep(0.1)  # Simulate network request
    return f"Data from {url}"

urls = [f"https://api.example.com/{i}" for i in range(5)]

with ThreadPoolExecutor(max_workers=3) as executor:
    results = executor.map(fetch_url, urls)
    for result in results:
        print(f"  {result}")
```

## THREAD SYNCHRONIZATION

```python
print("\n--- Thread Synchronization ---")

counter = 0
lock = threading.Lock()

def increment():
    global counter
    for _ in range(10000):
        with lock:
            counter += 1

threads = [threading.Thread(target=increment) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Counter: {counter}")  # Should be 50000
```

## THREAD-SAFE QUEUE

```python
print("\n--- Thread-Safe Queue ---")

from queue import Queue

def producer(q, items):
    for item in items:
        q.put(item)
        print(f"Produced: {item}")
    q.put(None)  # Sentinel

def consumer(q):
    while True:
        item = q.get()
        if item is None:
            break
        print(f"Consumed: {item}")
        q.task_done()

q = Queue()
prod = threading.Thread(target=producer, args=(q, [1, 2, 3]))
cons = threading.Thread(target=consumer, args=(q,))

prod.start()
cons.start()
prod.join()
cons.join()

print("\n✅ Threading complete!")
```
