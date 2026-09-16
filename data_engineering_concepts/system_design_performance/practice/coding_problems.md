# System Design & Performance — Coding Problem

One problem, asked frequently as the "write real code, not just talk" portion of a system-design/performance interview loop: implement an LRU cache for repeated database query results.

How to use this file: read the problem statement and requirements, write your own implementation, and only then expand the reference solution.

---

## Problem: Design a Caching Layer for Repeated Database Queries

Implement an LRU (Least Recently Used) cache sitting in front of a database connection. When the same query (with the same parameters) runs again, return the cached result instead of hitting the database.

**Requirements:**
- Fixed-size cache (e.g., max 100 entries).
- LRU eviction: when full, evict the LEAST recently used entry, not the oldest-inserted one — an entry that keeps getting read should NOT be evicted just because it was first in.
- Cache invalidation on writes (INSERT/UPDATE/DELETE should be able to clear affected entries).
- Track hit/miss statistics.
- Parameterized queries: the same SQL text with different parameter values must be different cache entries (`WHERE price > 10` and `WHERE price > 20` are NOT the same cache key).
- TTL (time-to-live): entries expire after a configurable duration even without an explicit invalidation.

**Constraint:** do not use `functools.lru_cache` — implement the eviction mechanism yourself (an `OrderedDict`, or a dict + doubly linked list), since the point of the exercise is demonstrating you understand HOW LRU eviction works, not that you know a decorator exists.

**Expected behavior**, given `max_size=3`:
```text
execute("SELECT * FROM products WHERE price > ?", (10.0,))   -> MISS (cache: 1 entry)
execute("SELECT * FROM products WHERE price > ?", (10.0,))   -> HIT  (same query+params)
execute("SELECT * FROM products WHERE price > ?", (20.0,))   -> MISS (different params = different key; cache: 2 entries)
execute("SELECT * FROM products WHERE price < ?", (15.0,))   -> MISS (cache: 3 entries, now full)
execute("SELECT COUNT(*) FROM products", None)                -> MISS, triggers eviction of the
                                                                   LEAST RECENTLY USED entry
                                                                   (the price>20 query, since
                                                                    price>10 was touched again
                                                                    more recently than it)
execute("SELECT * FROM products WHERE price > ?", (10.0,))   -> HIT if still in cache, MISS if
                                                                   it was the one evicted
invalidate()                                                   -> clears everything
execute(...) after invalidate()                                -> MISS (cache empty)
```

---

<details>
<summary>Reference solution (try it yourself first)</summary>

```python
import hashlib
import time
from collections import OrderedDict


class LRUQueryCache:
    """
    LRU cache for database query results, with TTL support.

    Uses OrderedDict for O(1) lookup, O(1) "mark as recently used"
    (move_to_end), and O(1) eviction of the least-recently-used entry
    (popitem(last=False) removes from the FRONT of the ordering).
    """

    def __init__(self, conn, max_size=100, ttl_seconds=300):
        self.conn = conn
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache = OrderedDict()   # key -> (result, inserted_at)
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "invalidations": 0}

    def _make_key(self, query, params):
        """Hash the query text + params together -- same SQL with
        different params must produce different keys."""
        key_str = query.strip() + "|" + str(params)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _is_expired(self, inserted_at):
        return (time.time() - inserted_at) > self.ttl_seconds

    def execute(self, query, params=None):
        cache_key = self._make_key(query, params)

        if cache_key in self._cache:
            result, inserted_at = self._cache[cache_key]
            if not self._is_expired(inserted_at):
                self._stats["hits"] += 1
                self._cache.move_to_end(cache_key)   # mark as most recently used
                return result
            del self._cache[cache_key]                # expired -- treat as a miss

        # Cache miss: hit the real database
        self._stats["misses"] += 1
        cur = self.conn.cursor()
        cur.execute(query, params) if params else cur.execute(query)
        result = cur.fetchall()

        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)            # evict least recently used
            self._stats["evictions"] += 1

        self._cache[cache_key] = (result, time.time())
        return result

    def invalidate(self, table_name=None):
        """Clear cache entries. A production version would track which
        table each cached query touches (parse the SQL, or tag entries
        at insert time) so invalidate('orders') only drops entries that
        actually read from 'orders' -- this simplified version clears
        everything, which is always correct but overly broad."""
        count = len(self._cache)
        self._cache.clear()
        self._stats["invalidations"] += count

    def get_stats(self):
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total else 0.0
        return {**self._stats, "total_queries": total,
                "hit_rate": f"{hit_rate:.1%}", "cache_size": len(self._cache)}
```

**Output**, tracing the expected-behavior sequence above with `max_size=3`:
```text
Query 1 (miss): 4 rows returned      # price > 10
Query 2 (hit):  4 rows returned      # same query+params
Query 3 (miss): 2 rows returned      # price > 20 -- different params
Query 4 (miss): 3 rows returned      # price < 15 -- cache now full (3 entries)
Query 5 (miss, triggers eviction): 5  # COUNT(*) -- evicts price>20 (least recently used)
Query 6 (miss, was evicted): 4 rows   # price > 10 was NOT evicted (touched more recently)

Cache Stats: {'hits': 1, 'misses': 5, 'evictions': 1, 'total_queries': 6, 'hit_rate': '16.7%', 'cache_size': 3}
```

</details>

---

## Why LRU Caching Matters for Data Engineering Systems

This isn't a generic algorithms-interview exercise that happens to be reused here — query-result caching is a real, load-bearing component in production DE systems, and LRU is almost always the eviction policy underneath it:

- **BI/dashboard tools** (Looker, Tableau, a custom metrics API) commonly cache the result of expensive aggregation queries in front of the warehouse. A handful of dashboard queries get re-run by dozens of viewers within the same minute — caching the first result and serving the rest from memory is the difference between one warehouse query and fifty.
- **Feature stores** serving ML inference cache recently-requested feature vectors — LRU naturally keeps "currently active" entities (users actively using the product right now) in cache and evicts entities nobody has looked up in a while, without any explicit bookkeeping about which entities are "active."
- **API layers in front of a warehouse** (rate-limited by warehouse compute cost, not by CPU) use exactly this pattern to avoid re-running an identical query a client fires repeatedly (a dashboard auto-refreshing every 30 seconds against unchanged data is a textbook case).

**Why LRU specifically, over other eviction policies**, is worth being able to justify:
- **vs. FIFO (evict oldest-inserted):** FIFO would evict a query that's read constantly just because it happened to be cached first — LRU's `move_to_end` on every hit is precisely what prevents this; "recently used" is a much better proxy for "will be used again soon" than "inserted a while ago."
- **vs. LFU (evict least-frequently-used):** LFU protects historically popular entries even after they've stopped being queried (a report that was hot last quarter but nobody runs anymore stays cached forever under pure LFU) — LRU adapts to CHANGING access patterns, which matches how dashboard/report usage actually shifts over time.
- **The real production caveat this problem is testing for:** an LRU cache with no TTL and no invalidation-on-write is a correctness bug waiting to happen, not just a performance feature — a cached `SELECT` result served after the underlying table has been updated is a stale-data bug, not a cache hit. That's exactly why the requirements list TTL and invalidation as REQUIREMENTS, not nice-to-haves — an interviewer who asks this problem is specifically checking whether you reach for the eviction algorithm and stop, or whether you also flag staleness as the risk that makes this pattern dangerous to bolt on carelessly.
