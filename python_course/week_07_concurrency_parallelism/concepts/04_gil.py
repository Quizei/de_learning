"""
GIL (Global Interpreter Lock)
=============================
Understanding Python's threading limitation.
"""

import threading
import multiprocessing
import time

# ================================
# WHAT IS THE GIL?
# ================================

print("--- What is the GIL? ---")
print("""
The Global Interpreter Lock (GIL) is a mutex that protects
access to Python objects, preventing multiple threads from
executing Python bytecodes at once.

Key Points:
- Only one thread executes Python code at a time
- I/O operations release the GIL
- CPU-bound threads don't benefit from threading
- Use multiprocessing for CPU-bound parallelism
""")

# ================================
# GIL IMPACT DEMONSTRATION
# ================================

def cpu_bound(n):
    """CPU-intensive task."""
    total = 0
    for i in range(n):
        total += i * i
    return total

def io_bound(seconds):
    """I/O-bound task (simulated)."""
    time.sleep(seconds)
    return "done"

# CPU-bound with threads (GIL limits parallelism)
print("\n--- CPU-bound with Threads ---")
start = time.time()
threads = []
for _ in range(4):
    t = threading.Thread(target=cpu_bound, args=(1000000,))
    threads.append(t)
    t.start()
for t in threads:
    t.join()
print(f"Threads: {time.time() - start:.2f}s")

# CPU-bound sequential
start = time.time()
for _ in range(4):
    cpu_bound(1000000)
print(f"Sequential: {time.time() - start:.2f}s")

# I/O-bound with threads (GIL released during I/O)
print("\n--- I/O-bound with Threads ---")
start = time.time()
threads = []
for _ in range(4):
    t = threading.Thread(target=io_bound, args=(0.1,))
    threads.append(t)
    t.start()
for t in threads:
    t.join()
print(f"Threads: {time.time() - start:.2f}s")

# I/O-bound sequential
start = time.time()
for _ in range(4):
    io_bound(0.1)
print(f"Sequential: {time.time() - start:.2f}s")

# ================================
# WHEN TO USE WHAT
# ================================

print("\n--- When to Use What ---")
print("""
Threading (threading module):
  ✓ I/O-bound tasks (network, file I/O)
  ✓ Waiting for external resources
  ✗ CPU-bound computation

Multiprocessing (multiprocessing module):
  ✓ CPU-bound tasks
  ✓ True parallelism
  ✗ Higher memory overhead
  ✗ IPC complexity

Asyncio:
  ✓ High-concurrency I/O
  ✓ Many simultaneous connections
  ✓ Single-threaded, no GIL issues
  ✗ All code must be async

Summary:
  CPU-bound → multiprocessing
  I/O-bound → threading or asyncio
  Many connections → asyncio
""")

print("\n✅ GIL explanation complete!")
