# Medium Algorithm Problems

Classic algorithm problems for interviews.

```python
from typing import List, Optional, Dict
```

## PROBLEM 1: LRU Cache

```python
from collections import OrderedDict

class LRUCache:
    """Least Recently Used Cache."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

# Test
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)  # Evicts key 2
assert cache.get(2) == -1
print("✓ Problem 1: LRU Cache")
```

## PROBLEM 2: Binary Search

```python
def binary_search(nums: List[int], target: int) -> int:
    """Find target in sorted list, return index or -1."""
    left, right = 0, len(nums) - 1

    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1

# Test
assert binary_search([1, 3, 5, 7, 9], 5) == 2
assert binary_search([1, 3, 5, 7, 9], 4) == -1
print("✓ Problem 2: Binary Search")
```

## PROBLEM 3: Merge Intervals

```python
def merge_intervals(intervals: List[List[int]]) -> List[List[int]]:
    """Merge overlapping intervals."""
    if not intervals:
        return []

    intervals.sort(key=lambda x: x[0])
    result = [intervals[0]]

    for start, end in intervals[1:]:
        if start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])

    return result

# Test
intervals = [[1, 3], [2, 6], [8, 10], [15, 18]]
result = merge_intervals(intervals)
assert result == [[1, 6], [8, 10], [15, 18]]
print("✓ Problem 3: Merge Intervals")
```

## PROBLEM 4: Valid Parentheses

```python
def is_valid_parentheses(s: str) -> bool:
    """Check if parentheses are balanced."""
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}

    for char in s:
        if char in '({[':
            stack.append(char)
        elif char in ')}]':
            if not stack or stack[-1] != pairs[char]:
                return False
            stack.pop()

    return len(stack) == 0

# Test
assert is_valid_parentheses("()[]{}") == True
assert is_valid_parentheses("([)]") == False
assert is_valid_parentheses("{[]}") == True
print("✓ Problem 4: Valid Parentheses")
```

## PROBLEM 5: Maximum Subarray (Kadane's)

```python
def max_subarray(nums: List[int]) -> int:
    """Find contiguous subarray with largest sum."""
    max_sum = nums[0]
    current_sum = nums[0]

    for num in nums[1:]:
        current_sum = max(num, current_sum + num)
        max_sum = max(max_sum, current_sum)

    return max_sum

# Test
assert max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6
print("✓ Problem 5: Maximum Subarray")
```

## PROBLEM 6: Rate Limiter

```python
import time
from collections import deque

class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = deque()

    def is_allowed(self) -> bool:
        now = time.time()

        # Remove old requests
        while self.requests and now - self.requests[0] > self.window:
            self.requests.popleft()

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False

# Test
limiter = RateLimiter(max_requests=3, window_seconds=1.0)
assert limiter.is_allowed() == True
assert limiter.is_allowed() == True
assert limiter.is_allowed() == True
assert limiter.is_allowed() == False  # Rate limited
print("✓ Problem 6: Rate Limiter")
```

## PROBLEM 7: Flatten Nested Dict

```python
def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """Flatten nested dictionary."""
    items = []
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep).items())
        else:
            items.append((new_key, value))
    return dict(items)

# Test
nested = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
result = flatten_dict(nested)
assert result == {"a": 1, "b.c": 2, "b.d.e": 3}
print("✓ Problem 7: Flatten Nested Dict")

print("\n✅ All medium algorithm problems completed!")
```
