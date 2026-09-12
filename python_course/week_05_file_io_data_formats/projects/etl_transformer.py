"""
Week 5 Project: ETL Transformer
================================
CSV to JSON transformer with validation and error handling.
"""

import json
import csv
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime

@dataclass
class TransformResult:
    success: int = 0
    failed: int = 0
    errors: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []

class ETLTransformer:
    def __init__(self, input_path: str, output_path: str):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

    def transform(self, transformers: Dict[str, callable] = None) -> TransformResult:
        result = TransformResult()
        records = []

        with open(self.input_path, 'r') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                try:
                    if transformers:
                        for field, func in transformers.items():
                            if field in row:
                                row[field] = func(row[field])
                    records.append(row)
                    result.success += 1
                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"Row {i}: {e}")

        with open(self.output_path, 'w') as f:
            json.dump(records, f, indent=2)

        return result

def main():
    # Create sample CSV
    csv_content = """id,name,score,date
1,Alice,85,2024-01-15
2,Bob,92,2024-01-16
3,Charlie,78,2024-01-17"""

    Path('input.csv').write_text(csv_content)

    # Transform with type conversions
    etl = ETLTransformer('input.csv', 'output.json')
    result = etl.transform({
        'id': int,
        'score': int,
    })

    print(f"Success: {result.success}, Failed: {result.failed}")
    print(f"Output:\n{Path('output.json').read_text()}")

    # Cleanup
    Path('input.csv').unlink()
    Path('output.json').unlink()

if __name__ == "__main__":
    main()
