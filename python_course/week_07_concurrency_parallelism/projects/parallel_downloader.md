# Week 7 Project: Parallel Data Downloader

A concurrent downloader demonstrating threading, multiprocessing, and asyncio.

```python
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict
from queue import Queue

@dataclass
class DownloadResult:
    url: str
    success: bool
    data: str = ""
    error: str = ""
    duration: float = 0.0

class ParallelDownloader:
    """Download multiple URLs in parallel using threads."""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers

    def _download_one(self, url: str) -> DownloadResult:
        """Simulate downloading a URL."""
        start = time.time()
        try:
            # Simulate network latency
            time.sleep(0.1 + hash(url) % 100 / 1000)
            return DownloadResult(
                url=url,
                success=True,
                data=f"Content from {url}",
                duration=time.time() - start
            )
        except Exception as e:
            return DownloadResult(
                url=url,
                success=False,
                error=str(e),
                duration=time.time() - start
            )

    def download_all(self, urls: List[str]) -> List[DownloadResult]:
        """Download all URLs using thread pool."""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._download_one, url): url for url in urls}
            for future in as_completed(futures):
                results.append(future.result())
        return results

class AsyncDownloader:
    """Download multiple URLs using asyncio."""

    async def _download_one(self, url: str) -> DownloadResult:
        start = time.time()
        try:
            await asyncio.sleep(0.1 + hash(url) % 100 / 1000)
            return DownloadResult(
                url=url,
                success=True,
                data=f"Async content from {url}",
                duration=time.time() - start
            )
        except Exception as e:
            return DownloadResult(
                url=url,
                success=False,
                error=str(e),
                duration=time.time() - start
            )

    async def download_all(self, urls: List[str]) -> List[DownloadResult]:
        tasks = [self._download_one(url) for url in urls]
        return await asyncio.gather(*tasks)

def main():
    urls = [f"https://api.example.com/data/{i}" for i in range(20)]

    # Thread-based downloader
    print("--- ThreadPool Downloader ---")
    start = time.time()
    downloader = ParallelDownloader(max_workers=5)
    results = downloader.download_all(urls)
    print(f"Downloaded {len(results)} URLs in {time.time() - start:.2f}s")
    print(f"Success: {sum(1 for r in results if r.success)}")

    # Async downloader
    print("\n--- Async Downloader ---")
    start = time.time()
    async_downloader = AsyncDownloader()
    results = asyncio.run(async_downloader.download_all(urls))
    print(f"Downloaded {len(results)} URLs in {time.time() - start:.2f}s")
    print(f"Success: {sum(1 for r in results if r.success)}")

    # Comparison with sequential
    print("\n--- Sequential (for comparison) ---")
    start = time.time()
    for url in urls[:5]:  # Only 5 to save time
        time.sleep(0.1)
    print(f"5 URLs sequential: {time.time() - start:.2f}s")

if __name__ == "__main__":
    main()
```
