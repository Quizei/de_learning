# File Handling in Python

Reading, writing, and managing files efficiently.

```python
import os
from pathlib import Path
```

## BASIC FILE OPERATIONS

```python
# Writing to a file
with open('example.txt', 'w') as f:
    f.write('Hello, World!\n')
    f.write('Second line\n')

# Reading entire file
with open('example.txt', 'r') as f:
    content = f.read()
    print("Full content:", repr(content))

# Reading line by line (memory efficient)
with open('example.txt', 'r') as f:
    for line in f:
        print(f"Line: {line.strip()}")
```

## PATHLIB (MODERN PATH HANDLING)

```python
print("\n--- pathlib ---")
file_path = Path('example.txt')
print(f"Exists: {file_path.exists()}")
print(f"Size: {file_path.stat().st_size} bytes")

# Path operations
data_dir = Path('data') / 'processed' / 'output'
print(f"Combined path: {data_dir}")

# Path properties
p = Path('/Users/user/documents/report.pdf')
print(f"Name: {p.name}, Stem: {p.stem}, Suffix: {p.suffix}")
```

## HANDLING LARGE FILES

```python
def read_in_chunks(filepath, chunk_size=1024):
    """Read file in chunks to save memory."""
    with open(filepath, 'r') as f:
        while chunk := f.read(chunk_size):
            yield chunk

def count_lines(filepath):
    """Count lines efficiently."""
    with open(filepath, 'rb') as f:
        return sum(1 for _ in f)
```

## ENCODING

```python
with open('unicode.txt', 'w', encoding='utf-8') as f:
    f.write('Hello, 世界! 🌍\n')

with open('unicode.txt', 'r', encoding='utf-8') as f:
    print(f"Unicode: {f.read()}")

# Clean up
os.remove('example.txt')
os.remove('unicode.txt')

print("\n✅ File handling basics complete!")
```
