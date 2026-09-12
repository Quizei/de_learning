"""
Multiprocessing in Python
=========================
True parallelism for CPU-bound tasks (bypasses GIL).
"""

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import time

# ================================
# BASIC MULTIPROCESSING
# ================================

def cpu_intensive(n):
    """CPU-bound task."""
    return sum(i * i for i in range(n))

if __name__ == "__main__":
    print("--- Basic Multiprocessing ---")

    # Create processes
    def worker(name):
        print(f"Worker {name} starting (PID: {mp.current_process().pid})")
        time.sleep(0.1)
        print(f"Worker {name} done")

    processes = []
    for i in range(3):
        p = mp.Process(target=worker, args=(i,))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    # ================================
    # PROCESS POOL
    # ================================

    print("\n--- ProcessPoolExecutor ---")

    with ProcessPoolExecutor(max_workers=4) as executor:
        numbers = [1000000, 2000000, 3000000, 4000000]
        results = list(executor.map(cpu_intensive, numbers))
        print(f"Results: {results}")

    # ================================
    # SHARED DATA
    # ================================

    print("\n--- Shared Data ---")

    # Shared value
    counter = mp.Value('i', 0)
    lock = mp.Lock()

    def increment_shared(counter, lock):
        for _ in range(1000):
            with lock:
                counter.value += 1

    procs = [mp.Process(target=increment_shared, args=(counter, lock)) for _ in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    print(f"Shared counter: {counter.value}")

    # ================================
    # POOL WITH MAP
    # ================================

    print("\n--- Pool.map ---")

    with mp.Pool(processes=4) as pool:
        results = pool.map(cpu_intensive, [100000, 200000, 300000])
        print(f"Pool results: {results}")

    print("\n✅ Multiprocessing complete!")
