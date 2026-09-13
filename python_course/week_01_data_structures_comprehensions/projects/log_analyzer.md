# Week 1 Project: Log Analyzer

Build a log file analyzer using collections module and comprehensions.

This project applies:
- Counter for frequency analysis
- defaultdict for grouping
- namedtuple for structured data
- Comprehensions for data transformation

Your Task:
Complete the LogAnalyzer class methods marked with TODO.

```python
from collections import Counter, defaultdict, namedtuple
from datetime import datetime
from typing import List, Dict, Tuple

# Define structured log entry
LogEntry = namedtuple('LogEntry', ['timestamp', 'level', 'source', 'message'])


class LogAnalyzer:
    """Analyze server logs using collections and comprehensions."""

    def __init__(self):
        self.logs: List[LogEntry] = []

    def parse_log_line(self, line: str) -> LogEntry:
        """
        Parse a log line into a LogEntry namedtuple.

        Format: "2024-01-01T10:00:00|ERROR|auth_service|Login failed"

        TODO: Implement this method
        """
        parts = line.strip().split('|')
        return LogEntry(
            timestamp=datetime.fromisoformat(parts[0]),
            level=parts[1],
            source=parts[2],
            message=parts[3]
        )

    def load_logs(self, log_lines: List[str]) -> None:
        """
        Load multiple log lines.

        TODO: Use list comprehension to parse all lines
        """
        self.logs = [self.parse_log_line(line) for line in log_lines if line.strip()]

    def count_by_level(self) -> Counter:
        """
        Count logs by level (ERROR, WARNING, INFO, DEBUG).

        TODO: Use Counter to count log levels
        Expected return: Counter({'ERROR': 5, 'INFO': 10, ...})
        """
        return Counter(log.level for log in self.logs)

    def count_by_source(self) -> Counter:
        """
        Count logs by source/service.

        TODO: Use Counter to count by source
        """
        return Counter(log.source for log in self.logs)

    def group_by_level(self) -> Dict[str, List[LogEntry]]:
        """
        Group all logs by their level.

        TODO: Use defaultdict to group logs
        Expected return: {'ERROR': [LogEntry(...), ...], 'INFO': [...], ...}
        """
        grouped = defaultdict(list)
        for log in self.logs:
            grouped[log.level].append(log)
        return dict(grouped)

    def group_by_hour(self) -> Dict[int, List[LogEntry]]:
        """
        Group logs by hour of day (0-23).

        TODO: Use defaultdict to group by hour
        """
        grouped = defaultdict(list)
        for log in self.logs:
            grouped[log.timestamp.hour].append(log)
        return dict(grouped)

    def get_errors_by_source(self) -> Dict[str, List[str]]:
        """
        Get error messages grouped by source.

        TODO: Use defaultdict and comprehension
        Return only ERROR level logs, grouped by source with just messages
        """
        errors = defaultdict(list)
        for log in self.logs:
            if log.level == 'ERROR':
                errors[log.source].append(log.message)
        return dict(errors)

    def get_error_rate_by_source(self) -> Dict[str, float]:
        """
        Calculate error rate (errors / total) for each source.

        TODO: Use Counter and dict comprehension
        """
        total_by_source = Counter(log.source for log in self.logs)
        errors_by_source = Counter(
            log.source for log in self.logs if log.level == 'ERROR'
        )
        return {
            source: errors_by_source[source] / count
            for source, count in total_by_source.items()
        }

    def get_busiest_hours(self, n: int = 3) -> List[Tuple[int, int]]:
        """
        Get the N hours with most log entries.

        TODO: Use Counter.most_common()
        """
        hour_counts = Counter(log.timestamp.hour for log in self.logs)
        return hour_counts.most_common(n)

    def search_logs(self, keyword: str, level: str = None) -> List[LogEntry]:
        """
        Search logs containing keyword, optionally filtered by level.

        TODO: Use list comprehension with conditions
        """
        return [
            log for log in self.logs
            if keyword.lower() in log.message.lower()
            and (level is None or log.level == level)
        ]

    def get_summary(self) -> Dict:
        """
        Generate a complete summary of the logs.

        TODO: Combine multiple analysis methods
        """
        return {
            'total_logs': len(self.logs),
            'level_counts': dict(self.count_by_level()),
            'source_counts': dict(self.count_by_source()),
            'error_rate_by_source': self.get_error_rate_by_source(),
            'busiest_hours': self.get_busiest_hours(3),
        }


# Sample logs for testing
SAMPLE_LOGS = [
    "2024-01-01T08:00:00|INFO|auth_service|User login successful",
    "2024-01-01T08:05:00|INFO|api_gateway|Request processed",
    "2024-01-01T08:10:00|ERROR|database|Connection timeout",
    "2024-01-01T09:00:00|INFO|auth_service|User login successful",
    "2024-01-01T09:15:00|WARNING|api_gateway|High latency detected",
    "2024-01-01T09:30:00|ERROR|auth_service|Invalid credentials",
    "2024-01-01T10:00:00|INFO|database|Query executed",
    "2024-01-01T10:05:00|ERROR|api_gateway|Rate limit exceeded",
    "2024-01-01T10:10:00|INFO|auth_service|User logout",
    "2024-01-01T10:30:00|WARNING|database|Slow query detected",
    "2024-01-01T11:00:00|INFO|api_gateway|Health check passed",
    "2024-01-01T11:15:00|ERROR|database|Deadlock detected",
    "2024-01-01T11:30:00|INFO|auth_service|Password changed",
    "2024-01-01T11:45:00|ERROR|auth_service|Account locked",
    "2024-01-01T12:00:00|INFO|api_gateway|Cache refreshed",
]


def main():
    """Run the log analyzer demo."""
    print("=" * 60)
    print("LOG ANALYZER - Week 1 Project")
    print("=" * 60)

    # Initialize and load logs
    analyzer = LogAnalyzer()
    analyzer.load_logs(SAMPLE_LOGS)
    print(f"\nLoaded {len(analyzer.logs)} log entries")

    # Count by level
    print("\n--- Logs by Level ---")
    for level, count in analyzer.count_by_level().most_common():
        print(f"  {level}: {count}")

    # Count by source
    print("\n--- Logs by Source ---")
    for source, count in analyzer.count_by_source().most_common():
        print(f"  {source}: {count}")

    # Error rate by source
    print("\n--- Error Rate by Source ---")
    for source, rate in analyzer.get_error_rate_by_source().items():
        print(f"  {source}: {rate:.1%}")

    # Busiest hours
    print("\n--- Busiest Hours ---")
    for hour, count in analyzer.get_busiest_hours(3):
        print(f"  {hour:02d}:00 - {count} logs")

    # Errors by source
    print("\n--- Errors by Source ---")
    for source, messages in analyzer.get_errors_by_source().items():
        print(f"  {source}:")
        for msg in messages:
            print(f"    - {msg}")

    # Search
    print("\n--- Search: 'timeout' ---")
    results = analyzer.search_logs('timeout')
    for log in results:
        print(f"  [{log.level}] {log.source}: {log.message}")

    # Full summary
    print("\n--- Summary ---")
    summary = analyzer.get_summary()
    print(f"  Total logs: {summary['total_logs']}")
    print(f"  Level distribution: {summary['level_counts']}")


if __name__ == "__main__":
    main()
```
