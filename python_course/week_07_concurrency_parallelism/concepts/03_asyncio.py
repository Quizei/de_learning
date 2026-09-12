"""
Asyncio in Python
=================
Asynchronous I/O for high-concurrency applications.
"""

import asyncio
import time

# ================================
# BASIC ASYNC/AWAIT
# ================================

async def say_hello(name, delay):
    print(f"Hello {name}!")
    await asyncio.sleep(delay)
    print(f"Goodbye {name}!")
    return f"Done: {name}"

async def main():
    print("--- Basic Async/Await ---")

    # Sequential (slow)
    start = time.time()
    await say_hello("Alice", 0.1)
    await say_hello("Bob", 0.1)
    print(f"Sequential: {time.time() - start:.2f}s")

    # Concurrent (fast)
    start = time.time()
    results = await asyncio.gather(
        say_hello("Alice", 0.1),
        say_hello("Bob", 0.1)
    )
    print(f"Concurrent: {time.time() - start:.2f}s")
    print(f"Results: {results}")

asyncio.run(main())

# ================================
# ASYNC PATTERNS
# ================================

async def patterns():
    print("\n--- Async Patterns ---")

    # Create tasks
    async def fetch(url):
        await asyncio.sleep(0.1)
        return f"Data from {url}"

    # gather - run concurrently
    results = await asyncio.gather(
        fetch("url1"),
        fetch("url2"),
        fetch("url3")
    )
    print(f"Gather results: {results}")

    # as_completed - process as they finish
    tasks = [asyncio.create_task(fetch(f"url{i}")) for i in range(3)]
    for coro in asyncio.as_completed(tasks):
        result = await coro
        print(f"Completed: {result}")

    # Timeout
    try:
        await asyncio.wait_for(asyncio.sleep(1), timeout=0.1)
    except asyncio.TimeoutError:
        print("Timeout occurred!")

asyncio.run(patterns())

# ================================
# ASYNC CONTEXT MANAGERS
# ================================

class AsyncResource:
    async def __aenter__(self):
        print("Acquiring resource")
        await asyncio.sleep(0.05)
        return self

    async def __aexit__(self, *args):
        print("Releasing resource")
        await asyncio.sleep(0.05)

    async def do_work(self):
        return "Work done"

async def use_resource():
    print("\n--- Async Context Manager ---")
    async with AsyncResource() as resource:
        result = await resource.do_work()
        print(result)

asyncio.run(use_resource())

# ================================
# ASYNC GENERATORS
# ================================

async def async_range(n):
    for i in range(n):
        await asyncio.sleep(0.01)
        yield i

async def use_async_gen():
    print("\n--- Async Generator ---")
    async for num in async_range(5):
        print(f"Got: {num}")

asyncio.run(use_async_gen())

print("\n✅ Asyncio complete!")
