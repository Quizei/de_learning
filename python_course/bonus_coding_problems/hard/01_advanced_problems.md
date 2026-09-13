# Hard Advanced Problems

Challenging problems for senior data engineering interviews.

```python
from typing import List, Dict, Any, Iterator, Tuple
from collections import defaultdict
import heapq
```

## PROBLEM 1: K-Way Merge Sorted Iterators

```python
def k_way_merge(*iterators: Iterator) -> Iterator:
    """Merge k sorted iterators into one sorted iterator."""
    heap = []

    # Initialize heap with first element from each iterator
    for i, it in enumerate(iterators):
        try:
            val = next(it)
            heapq.heappush(heap, (val, i, it))
        except StopIteration:
            pass

    # Yield smallest element and refill from same iterator
    while heap:
        val, idx, it = heapq.heappop(heap)
        yield val
        try:
            next_val = next(it)
            heapq.heappush(heap, (next_val, idx, it))
        except StopIteration:
            pass

# Test
result = list(k_way_merge(iter([1, 4, 7]), iter([2, 5, 8]), iter([3, 6, 9])))
assert result == [1, 2, 3, 4, 5, 6, 7, 8, 9]
print("✓ Problem 1: K-Way Merge")
```

## PROBLEM 2: Stream Median

```python
class MedianFinder:
    """Find median from a data stream."""

    def __init__(self):
        self.small = []  # Max heap (negated)
        self.large = []  # Min heap

    def add_num(self, num: int) -> None:
        heapq.heappush(self.small, -num)
        heapq.heappush(self.large, -heapq.heappop(self.small))

        if len(self.large) > len(self.small):
            heapq.heappush(self.small, -heapq.heappop(self.large))

    def find_median(self) -> float:
        if len(self.small) > len(self.large):
            return -self.small[0]
        return (-self.small[0] + self.large[0]) / 2

# Test
mf = MedianFinder()
mf.add_num(1)
mf.add_num(2)
assert mf.find_median() == 1.5
mf.add_num(3)
assert mf.find_median() == 2
print("✓ Problem 2: Stream Median")
```

## PROBLEM 3: Implement Trie (Prefix Tree)

```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True

    def search(self, word: str) -> bool:
        node = self._find_node(word)
        return node is not None and node.is_end

    def starts_with(self, prefix: str) -> bool:
        return self._find_node(prefix) is not None

    def _find_node(self, prefix: str) -> TrieNode:
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

# Test
trie = Trie()
trie.insert("apple")
assert trie.search("apple") == True
assert trie.search("app") == False
assert trie.starts_with("app") == True
print("✓ Problem 3: Trie Implementation")
```

## PROBLEM 4: Parallel Task Scheduler

```python
def schedule_tasks(tasks: List[Tuple[str, int, List[str]]]) -> List[str]:
    """
    Schedule tasks respecting dependencies.
    tasks: List of (task_id, duration, dependencies)
    Returns execution order.
    """
    # Build dependency graph
    in_degree = defaultdict(int)
    graph = defaultdict(list)
    task_set = set()

    for task_id, duration, deps in tasks:
        task_set.add(task_id)
        for dep in deps:
            graph[dep].append(task_id)
            in_degree[task_id] += 1

    # Ensure all tasks are in in_degree
    for task in task_set:
        if task not in in_degree:
            in_degree[task] = 0

    # Topological sort (Kahn's algorithm)
    queue = [t for t in task_set if in_degree[t] == 0]
    result = []

    while queue:
        task = queue.pop(0)
        result.append(task)

        for dependent in graph[task]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(task_set):
        raise ValueError("Circular dependency detected")

    return result

# Test
tasks = [
    ("build", 10, []),
    ("test", 5, ["build"]),
    ("deploy", 3, ["test"]),
    ("notify", 1, ["deploy"]),
]
order = schedule_tasks(tasks)
assert order.index("build") < order.index("test")
assert order.index("test") < order.index("deploy")
print("✓ Problem 4: Task Scheduler")
```

## PROBLEM 5: Consistent Hashing

```python
import hashlib
import bisect

class ConsistentHash:
    """Consistent hashing for distributed systems."""

    def __init__(self, nodes: List[str] = None, replicas: int = 100):
        self.replicas = replicas
        self.ring = []
        self.nodes = {}

        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str) -> None:
        for i in range(self.replicas):
            key = f"{node}:{i}"
            h = self._hash(key)
            bisect.insort(self.ring, h)
            self.nodes[h] = node

    def remove_node(self, node: str) -> None:
        for i in range(self.replicas):
            key = f"{node}:{i}"
            h = self._hash(key)
            self.ring.remove(h)
            del self.nodes[h]

    def get_node(self, key: str) -> str:
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect(self.ring, h) % len(self.ring)
        return self.nodes[self.ring[idx]]

# Test
ch = ConsistentHash(["node1", "node2", "node3"])
assert ch.get_node("key1") is not None
assert ch.get_node("key2") is not None
print("✓ Problem 5: Consistent Hashing")
```

## PROBLEM 6: Time Series Aggregation

```python
from datetime import datetime, timedelta

def aggregate_time_series(
    data: List[Tuple[datetime, float]],
    interval_minutes: int
) -> Dict[datetime, float]:
    """Aggregate time series data into fixed intervals."""
    if not data:
        return {}

    result = defaultdict(list)

    for timestamp, value in data:
        # Round down to interval
        minutes = (timestamp.minute // interval_minutes) * interval_minutes
        bucket = timestamp.replace(minute=minutes, second=0, microsecond=0)
        result[bucket].append(value)

    return {k: sum(v) / len(v) for k, v in result.items()}

# Test
now = datetime.now().replace(minute=0, second=0, microsecond=0)
data = [
    (now + timedelta(minutes=1), 10),
    (now + timedelta(minutes=2), 20),
    (now + timedelta(minutes=6), 30),
]
result = aggregate_time_series(data, 5)
assert len(result) == 2
print("✓ Problem 6: Time Series Aggregation")

print("\n✅ All hard problems completed!")
```
