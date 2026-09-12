"""
Medium Data Processing Problems
===============================
Real-world data engineering interview problems.
"""

from typing import List, Dict, Any
from collections import defaultdict, Counter
from datetime import datetime

# ================================
# PROBLEM 1: Group By and Aggregate
# ================================

def group_aggregate(records: List[Dict], group_key: str, agg_key: str) -> Dict:
    """Group records and calculate sum of agg_key."""
    result = defaultdict(int)
    for record in records:
        result[record[group_key]] += record[agg_key]
    return dict(result)

# Test
orders = [
    {"customer": "Alice", "amount": 100},
    {"customer": "Bob", "amount": 200},
    {"customer": "Alice", "amount": 150},
]
result = group_aggregate(orders, "customer", "amount")
assert result == {"Alice": 250, "Bob": 200}
print("✓ Problem 1: Group and Aggregate")

# ================================
# PROBLEM 2: Deduplicate by Key
# ================================

def deduplicate(records: List[Dict], key: str, keep: str = "first") -> List[Dict]:
    """Remove duplicates based on key, keeping first or last."""
    seen = {}
    for record in records:
        k = record[key]
        if keep == "first":
            if k not in seen:
                seen[k] = record
        else:  # last
            seen[k] = record
    return list(seen.values())

# Test
data = [
    {"id": 1, "value": "a"},
    {"id": 2, "value": "b"},
    {"id": 1, "value": "c"},
]
result = deduplicate(data, "id", "first")
assert len(result) == 2
assert result[0]["value"] == "a"
print("✓ Problem 2: Deduplicate by Key")

# ================================
# PROBLEM 3: Parse Log File
# ================================

def parse_logs(logs: List[str]) -> Dict[str, int]:
    """Parse logs and count by level."""
    pattern_counts = Counter()
    for log in logs:
        # Format: "2024-01-01 10:00:00 ERROR message"
        parts = log.split(" ", 3)
        if len(parts) >= 3:
            level = parts[2]
            pattern_counts[level] += 1
    return dict(pattern_counts)

# Test
logs = [
    "2024-01-01 10:00:00 ERROR Connection failed",
    "2024-01-01 10:01:00 INFO User logged in",
    "2024-01-01 10:02:00 ERROR Timeout",
    "2024-01-01 10:03:00 WARNING High load",
]
result = parse_logs(logs)
assert result["ERROR"] == 2
assert result["INFO"] == 1
print("✓ Problem 3: Parse Log File")

# ================================
# PROBLEM 4: Join Tables
# ================================

def left_join(left: List[Dict], right: List[Dict], key: str) -> List[Dict]:
    """Left join two lists of dicts on key."""
    right_lookup = {r[key]: r for r in right}
    result = []
    for l in left:
        merged = l.copy()
        if l[key] in right_lookup:
            for k, v in right_lookup[l[key]].items():
                if k != key:
                    merged[k] = v
        result.append(merged)
    return result

# Test
users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
orders = [{"id": 1, "total": 100}]
result = left_join(users, orders, "id")
assert result[0]["total"] == 100
assert "total" not in result[1]
print("✓ Problem 4: Join Tables")

# ================================
# PROBLEM 5: Window Function
# ================================

def running_average(nums: List[int], window: int) -> List[float]:
    """Calculate running average with window size."""
    from collections import deque
    result = []
    window_queue = deque(maxlen=window)

    for num in nums:
        window_queue.append(num)
        result.append(sum(window_queue) / len(window_queue))

    return result

# Test
result = running_average([1, 2, 3, 4, 5], 3)
assert result[2] == 2.0  # avg of [1, 2, 3]
assert result[4] == 4.0  # avg of [3, 4, 5]
print("✓ Problem 5: Running Average")

# ================================
# PROBLEM 6: Find Top N
# ================================

def top_n(records: List[Dict], key: str, n: int) -> List[Dict]:
    """Find top N records by key."""
    import heapq
    return heapq.nlargest(n, records, key=lambda x: x[key])

# Test
products = [
    {"name": "A", "sales": 100},
    {"name": "B", "sales": 500},
    {"name": "C", "sales": 250},
]
result = top_n(products, "sales", 2)
assert result[0]["name"] == "B"
assert result[1]["name"] == "C"
print("✓ Problem 6: Top N")

# ================================
# PROBLEM 7: Validate Schema
# ================================

def validate_record(record: Dict, schema: Dict[str, type]) -> List[str]:
    """Validate record against schema, return list of errors."""
    errors = []
    for field, expected_type in schema.items():
        if field not in record:
            errors.append(f"Missing field: {field}")
        elif not isinstance(record[field], expected_type):
            errors.append(f"Invalid type for {field}")
    return errors

# Test
schema = {"name": str, "age": int}
record = {"name": "Alice", "age": "30"}  # age is wrong type
errors = validate_record(record, schema)
assert len(errors) == 1
assert "age" in errors[0]
print("✓ Problem 7: Validate Schema")

print("\n✅ All medium data processing problems completed!")
