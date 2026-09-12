"""
Week 5 Practice Exercises: File I/O & Data Formats
==================================================
"""

import json
import csv
from pathlib import Path

# EXERCISE 1: Read a file and count word frequency
# EXERCISE 2: Parse CSV and calculate column statistics
# EXERCISE 3: Convert CSV to JSON
# EXERCISE 4: Merge multiple JSON files
# EXERCISE 5: Process large file in chunks

def show_solutions():
    print("=== SOLUTIONS ===")

    # Exercise 1: Word frequency
    print("\n--- Word Frequency ---")
    text = "hello world hello python world python python"
    Path('test.txt').write_text(text)

    from collections import Counter
    words = Path('test.txt').read_text().split()
    freq = Counter(words)
    print(f"Frequency: {freq}")
    Path('test.txt').unlink()

    # Exercise 2: CSV statistics
    print("\n--- CSV Statistics ---")
    csv_data = "name,score\nAlice,85\nBob,90\nCharlie,78"
    Path('scores.csv').write_text(csv_data)

    with open('scores.csv') as f:
        reader = csv.DictReader(f)
        scores = [int(row['score']) for row in reader]
    print(f"Avg: {sum(scores)/len(scores)}, Max: {max(scores)}, Min: {min(scores)}")
    Path('scores.csv').unlink()

    # Exercise 3: CSV to JSON
    print("\n--- CSV to JSON ---")
    csv_data = "id,name\n1,Alice\n2,Bob"
    Path('data.csv').write_text(csv_data)

    with open('data.csv') as f:
        rows = list(csv.DictReader(f))
    Path('data.json').write_text(json.dumps(rows, indent=2))
    print(f"Converted: {rows}")
    Path('data.csv').unlink()
    Path('data.json').unlink()

    print("\n✅ All solutions demonstrated!")

if __name__ == "__main__":
    show_solutions()
