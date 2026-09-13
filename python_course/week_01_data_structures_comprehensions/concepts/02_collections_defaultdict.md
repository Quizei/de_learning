# Collections Module: defaultdict

defaultdict provides a default value for missing keys.
Eliminates the need for checking if key exists before using it.

```python
from collections import defaultdict

# Problem with regular dict
regular_dict = {}
# regular_dict['missing_key'].append(1)  # KeyError!

# Solution 1: Check and initialize (verbose)
if 'key' not in regular_dict:
    regular_dict['key'] = []
regular_dict['key'].append(1)

# Solution 2: Use defaultdict (clean)
dd_list = defaultdict(list)
dd_list['key'].append(1)  # No KeyError!
dd_list['key'].append(2)
dd_list['another_key'].append(10)
print("defaultdict(list):", dict(dd_list))
# Output: {'key': [1, 2], 'another_key': [10]}

# Common default factories
dd_int = defaultdict(int)  # Default: 0
dd_int['count'] += 1
dd_int['count'] += 1
print("defaultdict(int):", dict(dd_int))  # {'count': 2}

dd_set = defaultdict(set)  # Default: empty set
dd_set['users'].add('alice')
dd_set['users'].add('bob')
dd_set['users'].add('alice')  # Duplicate ignored
print("defaultdict(set):", dict(dd_set))  # {'users': {'alice', 'bob'}}

dd_str = defaultdict(str)  # Default: empty string
dd_str['name'] += 'Hello'
dd_str['name'] += ' World'
print("defaultdict(str):", dict(dd_str))  # {'name': 'Hello World'}

# Custom default factory
def default_value():
    return {'count': 0, 'items': []}

dd_custom = defaultdict(default_value)
dd_custom['user1']['count'] += 1
dd_custom['user1']['items'].append('item1')
print("Custom default:", dict(dd_custom))

# Lambda as factory
dd_lambda = defaultdict(lambda: 'N/A')
dd_lambda['known'] = 'Value'
print("Known:", dd_lambda['known'])  # 'Value'
print("Unknown:", dd_lambda['unknown'])  # 'N/A'

# Real-world example: Grouping data
transactions = [
    {'user': 'alice', 'amount': 100},
    {'user': 'bob', 'amount': 200},
    {'user': 'alice', 'amount': 150},
    {'user': 'charlie', 'amount': 300},
    {'user': 'bob', 'amount': 50},
]

# Group transactions by user
user_transactions = defaultdict(list)
for txn in transactions:
    user_transactions[txn['user']].append(txn['amount'])

print("\nTransactions by user:", dict(user_transactions))
# Output: {'alice': [100, 150], 'bob': [200, 50], 'charlie': [300]}

# Calculate totals per user
user_totals = defaultdict(int)
for txn in transactions:
    user_totals[txn['user']] += txn['amount']

print("Totals by user:", dict(user_totals))
# Output: {'alice': 250, 'bob': 250, 'charlie': 300}

# Nested defaultdict - useful for multi-level grouping
nested = defaultdict(lambda: defaultdict(int))
nested['2024']['jan'] += 100
nested['2024']['feb'] += 200
nested['2023']['dec'] += 50
print("\nNested:", {k: dict(v) for k, v in nested.items()})
# Output: {'2024': {'jan': 100, 'feb': 200}, '2023': {'dec': 50}}
```
