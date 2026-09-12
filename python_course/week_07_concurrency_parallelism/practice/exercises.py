"""
Week 7 Practice Exercises: Concurrency & Parallelism
=====================================================
"""

import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time

def show_solutions():
    print("=== SOLUTIONS ===")

    # Exercise 1: Thread-safe counter
    print("\n--- Thread-Safe Counter ---")

    class ThreadSafeCounter:
        def __init__(self):
            self._value = 0
            self._lock = threading.Lock()

        def increment(self):
            with self._lock:
                self._value += 1

        @property
        def value(self):
            return self._value

    counter = ThreadSafeCounter()
    threads = [threading.Thread(target=counter.increment) for _ in range(1000)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"Counter: {counter.value}")

    # Exercise 2: Parallel URL fetcher
    print("\n--- Parallel URL Fetcher ---")

    def fetch_url(url):
        time.sleep(0.05)  # Simulate network
        return f"Content from {url}"

    urls = [f"https://api.example.com/page/{i}" for i in range(5)]

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(fetch_url, urls))
    print(f"Fetched {len(results)} pages")

    # Exercise 3: Async task runner
    print("\n--- Async Task Runner ---")

    async def async_task(name, delay):
        await asyncio.sleep(delay)
        return f"{name} complete"

    async def run_tasks():
        tasks = [
            async_task("Task1", 0.1),
            async_task("Task2", 0.05),
            async_task("Task3", 0.08),
        ]
        results = await asyncio.gather(*tasks)
        return results

    results = asyncio.run(run_tasks())
    print(f"Results: {results}")

    # Exercise 4: Producer-Consumer
    print("\n--- Producer-Consumer ---")

    from queue import Queue

    def producer(q, items):
        for item in items:
            q.put(item)
        q.put(None)

    def consumer(q, results):
        while True:
            item = q.get()
            if item is None:
                break
            results.append(item * 2)
            q.task_done()

    q = Queue()
    results = []
    prod = threading.Thread(target=producer, args=(q, [1, 2, 3, 4, 5]))
    cons = threading.Thread(target=consumer, args=(q, results))
    prod.start()
    cons.start()
    prod.join()
    cons.join()
    print(f"Processed: {results}")

    print("\n✅ All solutions demonstrated!")

if __name__ == "__main__":
    show_solutions()
