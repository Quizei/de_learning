"""
JSON and CSV Handling
=====================
Working with common data formats.
"""

import json
import csv
from datetime import datetime
from pathlib import Path

# ================================
# JSON OPERATIONS
# ================================

print("--- JSON ---")

data = {"name": "Alice", "age": 30, "tags": ["python", "data"]}

# To JSON string
json_str = json.dumps(data, indent=2)
print(f"JSON:\n{json_str}")

# From JSON string
parsed = json.loads(json_str)
print(f"Parsed: {parsed}")

# File operations
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

with open('data.json', 'r') as f:
    loaded = json.load(f)

# Custom encoder for datetime
def json_encoder(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")

complex_data = {"timestamp": datetime.now()}
print(json.dumps(complex_data, default=json_encoder))

# ================================
# CSV OPERATIONS
# ================================

print("\n--- CSV ---")

# Write CSV
rows = [
    {"name": "Alice", "age": 30, "city": "NYC"},
    {"name": "Bob", "age": 25, "city": "LA"},
]

with open('data.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=["name", "age", "city"])
    writer.writeheader()
    writer.writerows(rows)

# Read CSV
with open('data.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f"  {row}")

# ================================
# JSONL (JSON Lines)
# ================================

print("\n--- JSON Lines ---")

def write_jsonl(records, filepath):
    with open(filepath, 'w') as f:
        for record in records:
            f.write(json.dumps(record) + '\n')

def read_jsonl(filepath):
    with open(filepath, 'r') as f:
        for line in f:
            yield json.loads(line)

write_jsonl(rows, 'data.jsonl')
for record in read_jsonl('data.jsonl'):
    print(f"  {record}")

# Clean up
Path('data.json').unlink()
Path('data.csv').unlink()
Path('data.jsonl').unlink()

print("\n✅ JSON/CSV handling complete!")
