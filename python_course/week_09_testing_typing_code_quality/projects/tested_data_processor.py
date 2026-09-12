"""
Week 9 Project: Fully Tested Data Processor
============================================
A data processing module with comprehensive tests and type hints.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import pytest

# ================================
# DATA MODELS
# ================================

class Status(Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"

@dataclass
class Record:
    id: int
    data: Dict[str, Any]
    status: Status = Status.PENDING
    error: Optional[str] = None

# ================================
# DATA PROCESSOR
# ================================

class DataProcessor:
    """Process records with validation and transformation."""

    def __init__(self, validators: List[Callable[[Dict], bool]] = None):
        self.validators = validators or []
        self.processed: List[Record] = []
        self.failed: List[Record] = []

    def add_validator(self, validator: Callable[[Dict], bool]) -> None:
        """Add a validation function."""
        self.validators.append(validator)

    def validate(self, data: Dict[str, Any]) -> bool:
        """Run all validators on data."""
        return all(v(data) for v in self.validators)

    def process_record(self, record: Record) -> Record:
        """Process a single record."""
        try:
            if not self.validate(record.data):
                record.status = Status.FAILED
                record.error = "Validation failed"
                self.failed.append(record)
            else:
                record.status = Status.PROCESSED
                self.processed.append(record)
        except Exception as e:
            record.status = Status.FAILED
            record.error = str(e)
            self.failed.append(record)
        return record

    def process_all(self, records: List[Record]) -> Dict[str, int]:
        """Process all records and return stats."""
        for record in records:
            self.process_record(record)
        return {
            "processed": len(self.processed),
            "failed": len(self.failed)
        }

    def get_processed(self) -> List[Record]:
        return self.processed

    def get_failed(self) -> List[Record]:
        return self.failed

# ================================
# TESTS
# ================================

class TestDataProcessor:
    """Tests for DataProcessor."""

    @pytest.fixture
    def processor(self) -> DataProcessor:
        """Create a processor with basic validators."""
        proc = DataProcessor()
        proc.add_validator(lambda d: "name" in d)
        proc.add_validator(lambda d: len(d.get("name", "")) > 0)
        return proc

    @pytest.fixture
    def valid_record(self) -> Record:
        return Record(id=1, data={"name": "Alice", "value": 100})

    @pytest.fixture
    def invalid_record(self) -> Record:
        return Record(id=2, data={"value": 100})  # Missing name

    def test_validate_valid_data(self, processor: DataProcessor):
        """Valid data should pass validation."""
        assert processor.validate({"name": "Alice"}) is True

    def test_validate_invalid_data(self, processor: DataProcessor):
        """Invalid data should fail validation."""
        assert processor.validate({}) is False
        assert processor.validate({"name": ""}) is False

    def test_process_valid_record(
        self, processor: DataProcessor, valid_record: Record
    ):
        """Valid record should be processed."""
        result = processor.process_record(valid_record)
        assert result.status == Status.PROCESSED
        assert result.error is None
        assert len(processor.get_processed()) == 1

    def test_process_invalid_record(
        self, processor: DataProcessor, invalid_record: Record
    ):
        """Invalid record should fail."""
        result = processor.process_record(invalid_record)
        assert result.status == Status.FAILED
        assert result.error is not None
        assert len(processor.get_failed()) == 1

    def test_process_all(self, processor: DataProcessor):
        """Process multiple records."""
        records = [
            Record(id=1, data={"name": "Alice"}),
            Record(id=2, data={"name": "Bob"}),
            Record(id=3, data={}),  # Invalid
        ]
        stats = processor.process_all(records)
        assert stats["processed"] == 2
        assert stats["failed"] == 1

    @pytest.mark.parametrize("name,expected", [
        ("Alice", True),
        ("", False),
        (None, False),
    ])
    def test_name_validation(
        self, processor: DataProcessor, name: Optional[str], expected: bool
    ):
        """Test name validation with various inputs."""
        data = {"name": name} if name is not None else {}
        assert processor.validate(data) == expected

# ================================
# RUN DEMO
# ================================

def main():
    print("=== Data Processor Demo ===\n")

    # Create processor
    processor = DataProcessor()
    processor.add_validator(lambda d: "name" in d)
    processor.add_validator(lambda d: d.get("value", 0) > 0)

    # Create records
    records = [
        Record(id=1, data={"name": "Alice", "value": 100}),
        Record(id=2, data={"name": "Bob", "value": 200}),
        Record(id=3, data={"name": "Charlie"}),  # Missing value
        Record(id=4, data={"value": 50}),  # Missing name
    ]

    # Process
    stats = processor.process_all(records)
    print(f"Stats: {stats}")

    print("\nProcessed:")
    for r in processor.get_processed():
        print(f"  {r}")

    print("\nFailed:")
    for r in processor.get_failed():
        print(f"  {r}")

    print("\n--- Run tests with: pytest -v projects/tested_data_processor.py ---")

if __name__ == "__main__":
    main()
