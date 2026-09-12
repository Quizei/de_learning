"""
Week 1 Practice Exercises
=========================
Complete each exercise. Solutions are at the bottom (no peeking!).
"""

# ================================
# EXERCISE 1: Counter Basics
# ================================
"""
Given a list of HTTP status codes from a web server log,
find the 3 most common status codes and their counts.

Input: [200, 200, 404, 200, 500, 404, 200, 301, 500, 200]
Expected Output: [(200, 5), (404, 2), (500, 2)]
"""

status_codes = [200, 200, 404, 200, 500, 404, 200, 301, 500, 200]

# Your code here:
from collections import Counter
word_count = Counter(status_codes)
# result = ...
print(f"3 most common are {word_count .most_common(3)}")


# ================================
# EXERCISE 2: defaultdict Grouping
# ================================
"""
Group these transactions by user_id and calculate total amount per user.

Input: transactions list below
Expected Output: {'user_1': 250, 'user_2': 175, 'user_3': 100}
"""

transactions = [
    {'user_id': 'user_1', 'amount': 100},
    {'user_id': 'user_2', 'amount': 75},
    {'user_id': 'user_1', 'amount': 150},
    {'user_id': 'user_3', 'amount': 100},
    {'user_id': 'user_2', 'amount': 100},
]

from collections import defaultdict
totals = defaultdict(int)

for t in transactions:
    totals[t['user_id']] += t['amount']

print(dict(totals))
# user_totals = ...


# ================================
# EXERCISE 3: deque Sliding Window
# ================================
"""
Implement a function that returns the maximum value in each
sliding window of size k.

Input: nums = [1, 3, -1, -3, 5, 3, 6, 7], k = 3
Expected Output: [3, 3, 5, 5, 6, 7]

Explanation:
Window [1, 3, -1] -> max = 3
Window [3, -1, -3] -> max = 3
Window [-1, -3, 5] -> max = 5
... and so on
"""

def sliding_window_max(nums, k):
    # Your code here:
    pass


# ================================
# EXERCISE 4: namedtuple Data Processing
# ================================
"""
Create a namedtuple called 'Stock' with fields: symbol, price, volume
Then find:
1. The stock with highest price
2. Total volume of all stocks
3. Average price

Input: stock_data list below
"""

stock_data = [
    ('AAPL', 175.50, 1000000),
    ('GOOGL', 140.25, 500000),
    ('MSFT', 378.90, 750000),
    ('AMZN', 178.25, 600000),
]

# Your code here:
# Stock = ...
# highest_price_stock = ...
# total_volume = ...
# average_price = ...


# ================================
# EXERCISE 5: List Comprehension
# ================================
"""
Given a list of dictionaries representing products,
create a new list with only products that:
- Are in stock (quantity > 0)
- Have price > 50
And format each as: "ProductName: $XX.XX"

Input: products list below
Expected Output: ['Laptop: $999.99', 'Phone: $699.99', 'Tablet: $449.99']
"""

products = [
    {'name': 'Laptop', 'price': 999.99, 'quantity': 5},
    {'name': 'Mouse', 'price': 29.99, 'quantity': 0},
    {'name': 'Phone', 'price': 699.99, 'quantity': 10},
    {'name': 'Cable', 'price': 9.99, 'quantity': 100},
    {'name': 'Tablet', 'price': 449.99, 'quantity': 3},
]

# Your code here:
# result = ...


# ================================
# EXERCISE 6: Dict Comprehension
# ================================
"""
Given a string, create a dictionary mapping each unique character
to the list of indices where it appears.

Input: "mississippi"
Expected Output: {'m': [0], 'i': [1, 4, 7, 10], 's': [2, 3, 5, 6], 'p': [8, 9]}
"""

text = "mississippi"

# Your code here:
# char_indices = ...


# ================================
# EXERCISE 7: Nested Comprehension
# ================================
"""
Given a 2D matrix, transpose it (swap rows and columns).

Input: [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
Expected Output: [[1, 4, 7], [2, 5, 8], [3, 6, 9]]
"""

matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

# Your code here:
# transposed = ...


# ================================
# EXERCISE 8: Walrus Operator
# ================================
"""
Rewrite this code using the walrus operator to avoid
calling expensive_operation twice:

results = []
for item in data:
    result = expensive_operation(item)
    if result > 10:
        results.append(result)
"""

def expensive_operation(x):
    """Simulates expensive computation."""
    return x * 3

data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Your code here (use walrus operator in list comprehension):
# results = ...


# ================================
# EXERCISE 9: Combined Challenge
# ================================
"""
You have server logs with format: "timestamp|level|message"
Parse the logs and create a summary:
1. Count of each log level
2. Group messages by level
3. Find the level with most messages

Input: logs list below
Expected Output:
- counts: Counter({'ERROR': 3, 'INFO': 2, 'WARNING': 2})
- grouped: {'ERROR': [...messages...], 'INFO': [...], 'WARNING': [...]}
- most_common_level: 'ERROR'
"""

logs = [
    "2024-01-01T10:00:00|ERROR|Connection timeout",
    "2024-01-01T10:01:00|INFO|User logged in",
    "2024-01-01T10:02:00|ERROR|Database error",
    "2024-01-01T10:03:00|WARNING|High memory usage",
    "2024-01-01T10:04:00|INFO|Request completed",
    "2024-01-01T10:05:00|ERROR|API failure",
    "2024-01-01T10:06:00|WARNING|Slow response",
]

# Your code here:
# counts = ...
# grouped = ...
# most_common_level = ...


# ================================
# EXERCISE 10: Performance Comparison
# ================================
"""
Compare memory usage between list comprehension and generator expression.
Create both for squaring numbers from 0 to 999999.
Print the memory size of each using sys.getsizeof().
"""

import sys

# Your code here:
# list_squares = ...
# gen_squares = ...
# print(f"List size: {sys.getsizeof(list_squares)} bytes")
# print(f"Generator size: {sys.getsizeof(gen_squares)} bytes")


# ================================================================
# SOLUTIONS (Don't look until you've tried!)
# ================================================================
"""
Scroll down for solutions...



















"""

def show_solutions():
    from collections import Counter, defaultdict, namedtuple, deque
    import sys

    print("=" * 50)
    print("SOLUTIONS")
    print("=" * 50)

    # Exercise 1
    print("\n--- Exercise 1 ---")
    status_codes = [200, 200, 404, 200, 500, 404, 200, 301, 500, 200]
    result = Counter(status_codes).most_common(3)
    print(f"Top 3 status codes: {result}")

    # Exercise 2
    print("\n--- Exercise 2 ---")
    transactions = [
        {'user_id': 'user_1', 'amount': 100},
        {'user_id': 'user_2', 'amount': 75},
        {'user_id': 'user_1', 'amount': 150},
        {'user_id': 'user_3', 'amount': 100},
        {'user_id': 'user_2', 'amount': 100},
    ]
    user_totals = defaultdict(int)
    for txn in transactions:
        user_totals[txn['user_id']] += txn['amount']
    print(f"User totals: {dict(user_totals)}")

    # Exercise 3
    print("\n--- Exercise 3 ---")
    def sliding_window_max(nums, k):
        if not nums or k == 0:
            return []
        result = []
        window = deque()
        for i in range(len(nums)):
            # Remove elements outside window
            while window and window[0] < i - k + 1:
                window.popleft()
            # Remove smaller elements
            while window and nums[window[-1]] < nums[i]:
                window.pop()
            window.append(i)
            if i >= k - 1:
                result.append(nums[window[0]])
        return result

    nums = [1, 3, -1, -3, 5, 3, 6, 7]
    print(f"Sliding max: {sliding_window_max(nums, 3)}")

    # Exercise 4
    print("\n--- Exercise 4 ---")
    Stock = namedtuple('Stock', ['symbol', 'price', 'volume'])
    stocks = [Stock._make(s) for s in stock_data]
    highest = max(stocks, key=lambda s: s.price)
    total_vol = sum(s.volume for s in stocks)
    avg_price = sum(s.price for s in stocks) / len(stocks)
    print(f"Highest: {highest.symbol}, Total Vol: {total_vol}, Avg Price: ${avg_price:.2f}")

    # Exercise 5
    print("\n--- Exercise 5 ---")
    result = [f"{p['name']}: ${p['price']}" for p in products
              if p['quantity'] > 0 and p['price'] > 50]
    print(f"Filtered products: {result}")

    # Exercise 6
    print("\n--- Exercise 6 ---")
    text = "mississippi"
    char_indices = defaultdict(list)
    for i, c in enumerate(text):
        char_indices[c].append(i)
    print(f"Char indices: {dict(char_indices)}")

    # Exercise 7
    print("\n--- Exercise 7 ---")
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    transposed = [[row[i] for row in matrix] for i in range(len(matrix[0]))]
    print(f"Transposed: {transposed}")

    # Exercise 8
    print("\n--- Exercise 8 ---")
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    results = [res for item in data if (res := expensive_operation(item)) > 10]
    print(f"Results with walrus: {results}")

    # Exercise 9
    print("\n--- Exercise 9 ---")
    parsed = [(log.split('|')[1], log.split('|')[2]) for log in logs]
    counts = Counter(level for level, _ in parsed)
    grouped = defaultdict(list)
    for level, msg in parsed:
        grouped[level].append(msg)
    most_common_level = counts.most_common(1)[0][0]
    print(f"Counts: {counts}")
    print(f"Most common: {most_common_level}")

    # Exercise 10
    print("\n--- Exercise 10 ---")
    list_squares = [x**2 for x in range(1000000)]
    gen_squares = (x**2 for x in range(1000000))
    print(f"List size: {sys.getsizeof(list_squares):,} bytes")
    print(f"Generator size: {sys.getsizeof(gen_squares)} bytes")


if __name__ == "__main__":
    print("Complete the exercises above, then run show_solutions()")
    # Uncomment to see solutions:
    # show_solutions()
