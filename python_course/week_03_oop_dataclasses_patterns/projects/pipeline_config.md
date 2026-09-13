# Week 3 Project: Data Pipeline Configuration System

A flexible configuration system for data pipelines using OOP patterns.

This project applies:
- Data classes for configuration objects
- Abstract base classes for interfaces
- Factory pattern for creating components
- Builder pattern for pipeline construction
- Strategy pattern for different behaviors

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import json
```

## ENUMS

```python
class SourceType(Enum):
    DATABASE = "database"
    API = "api"
    FILE = "file"
    STREAM = "stream"


class TransformType(Enum):
    FILTER = "filter"
    MAP = "map"
    AGGREGATE = "aggregate"
    JOIN = "join"


class SinkType(Enum):
    DATABASE = "database"
    FILE = "file"
    API = "api"
    CONSOLE = "console"
```

## DATA CLASSES

```python
@dataclass
class SourceConfig:
    """Configuration for a data source."""
    name: str
    source_type: SourceType
    connection_string: str
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformConfig:
    """Configuration for a transformation step."""
    name: str
    transform_type: TransformType
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SinkConfig:
    """Configuration for a data sink."""
    name: str
    sink_type: SinkType
    connection_string: str
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""
    name: str
    description: str = ""
    source: SourceConfig = None
    transforms: List[TransformConfig] = field(default_factory=list)
    sink: SinkConfig = None
    schedule: Optional[str] = None
    retry_count: int = 3
    timeout_seconds: int = 3600
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "source": {
                "name": self.source.name,
                "type": self.source.source_type.value,
                "connection": self.source.connection_string,
                "options": self.source.options
            } if self.source else None,
            "transforms": [
                {
                    "name": t.name,
                    "type": t.transform_type.value,
                    "params": t.params
                } for t in self.transforms
            ],
            "sink": {
                "name": self.sink.name,
                "type": self.sink.sink_type.value,
                "connection": self.sink.connection_string,
                "options": self.sink.options
            } if self.sink else None,
            "schedule": self.schedule,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds
        }
```

## ABSTRACT COMPONENTS

```python
class DataSource(ABC):
    """Abstract base class for data sources."""

    def __init__(self, config: SourceConfig):
        self.config = config

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def read(self) -> List[Dict]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class DataTransform(ABC):
    """Abstract base class for transformations."""

    def __init__(self, config: TransformConfig):
        self.config = config

    @abstractmethod
    def transform(self, data: List[Dict]) -> List[Dict]:
        pass


class DataSink(ABC):
    """Abstract base class for data sinks."""

    def __init__(self, config: SinkConfig):
        self.config = config

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def write(self, data: List[Dict]) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass
```

## CONCRETE IMPLEMENTATIONS

```python
class MockDatabaseSource(DataSource):
    """Mock database source for demonstration."""

    def connect(self) -> None:
        print(f"  [DB] Connecting to {self.config.connection_string}")

    def read(self) -> List[Dict]:
        print(f"  [DB] Reading from {self.config.name}")
        return [
            {"id": 1, "name": "Alice", "amount": 100},
            {"id": 2, "name": "Bob", "amount": 200},
            {"id": 3, "name": "Charlie", "amount": 150},
        ]

    def close(self) -> None:
        print(f"  [DB] Closing connection")


class MockAPISource(DataSource):
    """Mock API source for demonstration."""

    def connect(self) -> None:
        print(f"  [API] Creating session for {self.config.connection_string}")

    def read(self) -> List[Dict]:
        print(f"  [API] Fetching from {self.config.name}")
        return [{"api_data": "sample"}]

    def close(self) -> None:
        print(f"  [API] Closing session")


class FilterTransform(DataTransform):
    """Filter records based on condition."""

    def transform(self, data: List[Dict]) -> List[Dict]:
        field = self.config.params.get("field")
        op = self.config.params.get("operator", "eq")
        value = self.config.params.get("value")

        def matches(record):
            record_value = record.get(field)
            if op == "eq":
                return record_value == value
            elif op == "gt":
                return record_value > value
            elif op == "lt":
                return record_value < value
            elif op == "gte":
                return record_value >= value
            elif op == "lte":
                return record_value <= value
            return True

        result = [r for r in data if matches(r)]
        print(f"  [FILTER] {len(data)} -> {len(result)} records")
        return result


class MapTransform(DataTransform):
    """Map/transform fields."""

    def transform(self, data: List[Dict]) -> List[Dict]:
        mappings = self.config.params.get("mappings", {})
        result = []

        for record in data:
            new_record = {}
            for new_key, old_key in mappings.items():
                if old_key in record:
                    new_record[new_key] = record[old_key]
            result.append(new_record)

        print(f"  [MAP] Transformed {len(result)} records")
        return result


class ConsoleSink(DataSink):
    """Output data to console."""

    def connect(self) -> None:
        print(f"  [CONSOLE] Ready to output")

    def write(self, data: List[Dict]) -> None:
        print(f"  [CONSOLE] Writing {len(data)} records:")
        for record in data:
            print(f"    {record}")

    def close(self) -> None:
        print(f"  [CONSOLE] Done")
```

## FACTORIES

```python
class SourceFactory:
    """Factory for creating data sources."""

    _sources = {
        SourceType.DATABASE: MockDatabaseSource,
        SourceType.API: MockAPISource,
    }

    @classmethod
    def create(cls, config: SourceConfig) -> DataSource:
        source_class = cls._sources.get(config.source_type)
        if not source_class:
            raise ValueError(f"Unknown source type: {config.source_type}")
        return source_class(config)

    @classmethod
    def register(cls, source_type: SourceType, source_class: type):
        cls._sources[source_type] = source_class


class TransformFactory:
    """Factory for creating transformations."""

    _transforms = {
        TransformType.FILTER: FilterTransform,
        TransformType.MAP: MapTransform,
    }

    @classmethod
    def create(cls, config: TransformConfig) -> DataTransform:
        transform_class = cls._transforms.get(config.transform_type)
        if not transform_class:
            raise ValueError(f"Unknown transform type: {config.transform_type}")
        return transform_class(config)


class SinkFactory:
    """Factory for creating data sinks."""

    _sinks = {
        SinkType.CONSOLE: ConsoleSink,
    }

    @classmethod
    def create(cls, config: SinkConfig) -> DataSink:
        sink_class = cls._sinks.get(config.sink_type)
        if not sink_class:
            raise ValueError(f"Unknown sink type: {config.sink_type}")
        return sink_class(config)
```

## PIPELINE BUILDER

```python
class PipelineBuilder:
    """Builder for constructing pipeline configurations."""

    def __init__(self, name: str):
        self._config = PipelineConfig(name=name)

    def description(self, desc: str) -> 'PipelineBuilder':
        self._config.description = desc
        return self

    def from_database(self, name: str, connection: str, **options) -> 'PipelineBuilder':
        self._config.source = SourceConfig(
            name=name,
            source_type=SourceType.DATABASE,
            connection_string=connection,
            options=options
        )
        return self

    def from_api(self, name: str, endpoint: str, **options) -> 'PipelineBuilder':
        self._config.source = SourceConfig(
            name=name,
            source_type=SourceType.API,
            connection_string=endpoint,
            options=options
        )
        return self

    def filter(self, name: str, field: str, operator: str, value: Any) -> 'PipelineBuilder':
        self._config.transforms.append(TransformConfig(
            name=name,
            transform_type=TransformType.FILTER,
            params={"field": field, "operator": operator, "value": value}
        ))
        return self

    def map_fields(self, name: str, **mappings) -> 'PipelineBuilder':
        self._config.transforms.append(TransformConfig(
            name=name,
            transform_type=TransformType.MAP,
            params={"mappings": mappings}
        ))
        return self

    def to_console(self, name: str = "console_output") -> 'PipelineBuilder':
        self._config.sink = SinkConfig(
            name=name,
            sink_type=SinkType.CONSOLE,
            connection_string="stdout"
        )
        return self

    def with_schedule(self, cron: str) -> 'PipelineBuilder':
        self._config.schedule = cron
        return self

    def with_retry(self, count: int) -> 'PipelineBuilder':
        self._config.retry_count = count
        return self

    def with_timeout(self, seconds: int) -> 'PipelineBuilder':
        self._config.timeout_seconds = seconds
        return self

    def build(self) -> PipelineConfig:
        if not self._config.source:
            raise ValueError("Pipeline must have a source")
        if not self._config.sink:
            raise ValueError("Pipeline must have a sink")
        return self._config
```

## PIPELINE EXECUTOR

```python
class PipelineExecutor:
    """Executes a pipeline configuration."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self) -> Dict[str, Any]:
        """Execute the pipeline and return results."""
        print(f"\n{'='*50}")
        print(f"Executing Pipeline: {self.config.name}")
        print(f"{'='*50}")

        start_time = datetime.now()

        # Create source
        source = SourceFactory.create(self.config.source)

        # Create transforms
        transforms = [
            TransformFactory.create(t)
            for t in self.config.transforms
        ]

        # Create sink
        sink = SinkFactory.create(self.config.sink)

        # Execute pipeline
        with source:
            data = source.read()
            print(f"\nRead {len(data)} records from source")

            # Apply transforms
            for transform in transforms:
                data = transform.transform(data)

            # Write to sink
            sink.connect()
            sink.write(data)
            sink.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return {
            "status": "success",
            "records_processed": len(data),
            "duration_seconds": duration
        }
```

## DEMO

```python
def main():
    """Demonstrate the pipeline configuration system."""

    print("=" * 60)
    print("DATA PIPELINE CONFIGURATION SYSTEM")
    print("=" * 60)

    # Build a pipeline using the builder
    pipeline_config = (PipelineBuilder("user_etl")
        .description("Extract users, filter by amount, and output")
        .from_database("users_db", "postgresql://localhost/users")
        .filter("high_value", field="amount", operator="gte", value=150)
        .map_fields("rename", user_name="name", total="amount")
        .to_console()
        .with_schedule("0 * * * *")
        .with_retry(3)
        .build())

    # Print configuration
    print("\n--- Pipeline Configuration ---")
    print(json.dumps(pipeline_config.to_dict(), indent=2))

    # Execute the pipeline
    executor = PipelineExecutor(pipeline_config)
    result = executor.run()

    print(f"\n--- Execution Result ---")
    print(f"Status: {result['status']}")
    print(f"Records: {result['records_processed']}")
    print(f"Duration: {result['duration_seconds']:.3f}s")

    # Build another pipeline
    print("\n\n--- Building API Pipeline ---")

    api_pipeline = (PipelineBuilder("api_sync")
        .description("Sync data from API")
        .from_api("external_api", "https://api.example.com/data")
        .to_console()
        .build())

    executor2 = PipelineExecutor(api_pipeline)
    executor2.run()


if __name__ == "__main__":
    main()
```
