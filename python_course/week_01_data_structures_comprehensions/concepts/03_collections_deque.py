"""
Collections Module: deque (Double-Ended Queue)
===============================================
deque is optimized for fast appends and pops from both ends.
Lists are O(n) for operations at the beginning, deque is O(1).
"""

from collections import deque

# Basic deque operations
d = deque([1, 2, 3, 4, 5])
print("Initial deque:", d)

# Append operations - O(1) on both ends
d.append(6)         # Add to right
d.appendleft(0)     # Add to left
print("After appends:", d)  # deque([0, 1, 2, 3, 4, 5, 6])

# Pop operations - O(1) on both ends
right = d.pop()      # Remove from right
left = d.popleft()   # Remove from left
print(f"Popped: left={left}, right={right}")
print("After pops:", d)  # deque([1, 2, 3, 4, 5])

# Extend operations
d.extend([6, 7, 8])        # Extend right
d.extendleft([-1, 0])      # Extend left (note: reverses order)
print("After extend:", d)  # deque([0, -1, 1, 2, 3, 4, 5, 6, 7, 8])

# Rotation - shift elements
d = deque([1, 2, 3, 4, 5])
d.rotate(2)   # Rotate right by 2
print("Rotate right 2:", d)  # deque([4, 5, 1, 2, 3])

d.rotate(-2)  # Rotate left by 2
print("Rotate left 2:", d)   # deque([1, 2, 3, 4, 5])

# maxlen - fixed size deque (useful for sliding windows)
fixed_deque = deque(maxlen=3)
for i in range(5):
    fixed_deque.append(i)
    print(f"Added {i}: {fixed_deque}")
# Output:
# Added 0: deque([0], maxlen=3)
# Added 1: deque([0, 1], maxlen=3)
# Added 2: deque([0, 1, 2], maxlen=3)
# Added 3: deque([1, 2, 3], maxlen=3)  <- 0 is automatically removed
# Added 4: deque([2, 3, 4], maxlen=3)  <- 1 is automatically removed

# Real-world example 1: Sliding window for moving average
def moving_average(data, window_size):
    """Calculate moving average using deque as sliding window."""
    window = deque(maxlen=window_size)
    averages = []

    for value in data:
        window.append(value)
        if len(window) == window_size:
            averages.append(sum(window) / window_size)

    return averages

prices = [100, 102, 104, 103, 105, 108, 107, 110]
print("\nPrices:", prices)
print("3-day moving avg:", moving_average(prices, 3))

# Real-world example 2: Recent items / history
class BrowsingHistory:
    def __init__(self, max_items=5):
        self.history = deque(maxlen=max_items)

    def visit(self, url):
        self.history.append(url)

    def get_recent(self, n=None):
        if n is None:
            return list(self.history)
        return list(self.history)[-n:]

history = BrowsingHistory(max_items=3)
history.visit("google.com")
history.visit("github.com")
history.visit("stackoverflow.com")
history.visit("python.org")  # google.com is removed
print("\nBrowsing history:", history.get_recent())

# Real-world example 3: BFS (Breadth-First Search)
def bfs_example():
    """BFS uses deque as a queue."""
    graph = {
        'A': ['B', 'C'],
        'B': ['D', 'E'],
        'C': ['F'],
        'D': [], 'E': [], 'F': []
    }

    visited = set()
    queue = deque(['A'])
    order = []

    while queue:
        node = queue.popleft()  # O(1) - efficient!
        if node not in visited:
            visited.add(node)
            order.append(node)
            queue.extend(graph[node])

    return order

print("\nBFS traversal:", bfs_example())
# Output: ['A', 'B', 'C', 'D', 'E', 'F']
