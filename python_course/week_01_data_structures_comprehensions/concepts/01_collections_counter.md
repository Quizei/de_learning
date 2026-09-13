# Collections Module: Counter

Counter is a dict subclass for counting hashable objects.
Essential for data engineering tasks like log analysis, word frequency, etc.

```python
from collections import Counter

# Basic usage - counting elements
words = ['apple', 'banana', 'apple', 'cherry', 'banana', 'apple']
word_count = Counter(words)
print("Word counts:", word_count)
# Output: Counter({'apple': 3, 'banana': 2, 'cherry': 1})

# Counter from string
char_count = Counter("mississippi")
print("Character counts:", char_count)
# Output: Counter({'i': 4, 's': 4, 'p': 2, 'm': 1})

# Most common elements - very useful for top-N queries
print("Top 2 characters:", char_count.most_common(2))
# Output: [('i', 4), ('s', 4)]

# Arithmetic operations
counter1 = Counter({'a': 3, 'b': 2})
counter2 = Counter({'a': 1, 'b': 4, 'c': 2})

print("Addition:", counter1 + counter2)  # Counter({'b': 6, 'a': 4, 'c': 2})
print("Subtraction:", counter1 - counter2)  # Counter({'a': 2}) - only positive counts
print("Intersection:", counter1 & counter2)  # Counter({'b': 2, 'a': 1}) - minimum
print("Union:", counter1 | counter2)  # Counter({'b': 4, 'a': 3, 'c': 2}) - maximum

# Useful methods
print("Elements:", list(counter1.elements()))  # ['a', 'a', 'a', 'b', 'b']
print("Total count:", counter1.total())  # 5 (Python 3.10+)

# Update counter (add counts)
counter1.update(['a', 'a', 'c'])
print("After update:", counter1)  # Counter({'a': 5, 'b': 2, 'c': 1})

# Subtract (reduce counts)
counter1.subtract(['a', 'a', 'a', 'a', 'a'])
print("After subtract:", counter1)  # Counter({'b': 2, 'c': 1, 'a': 0})

# Real-world example: Log analysis
log_entries = [
    "ERROR: Connection failed",
    "INFO: User logged in",
    "ERROR: Timeout occurred",
    "WARNING: High memory usage",
    "ERROR: Connection failed",
    "INFO: Data processed",
]

log_levels = Counter(entry.split(":")[0] for entry in log_entries)
print("\nLog level distribution:", log_levels)
# Output: Counter({'ERROR': 3, 'INFO': 2, 'WARNING': 1})
```
