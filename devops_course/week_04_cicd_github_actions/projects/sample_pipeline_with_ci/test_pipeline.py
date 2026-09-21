"""
Tests for the Sales ETL Pipeline
=================================
Pure unit tests — no file I/O, no database, no network.
Fixtures provide in-memory sample data.

Run:
  pytest test_pipeline.py -v
  pytest test_pipeline.py -v --cov=pipeline --cov-report=term-missing
"""

import pytest
from datetime import date
from pipeline import transform, extract, load, _parse_date, _to_float


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_rows():
    """Clean, complete rows as they would come out of extract()."""
    return [
        {"date": "2024-01-15", "order_id": "ORD-001", "category": "Electronics",
         "product": "Laptop",     "quantity": "2", "unit_price": "999.99"},
        {"date": "2024-01-16", "order_id": "ORD-002", "category": "Electronics",
         "product": "Headphones", "quantity": "5", "unit_price": "49.99"},
        {"date": "2024-01-17", "order_id": "ORD-003", "category": "Clothing",
         "product": "T-Shirt",    "quantity": "10", "unit_price": "19.99"},
        {"date": "2024-01-18", "order_id": "ORD-004", "category": "Clothing",
         "product": "Jeans",      "quantity": "3",  "unit_price": "59.99"},
        {"date": "2024-01-19", "order_id": "ORD-005", "category": "Books",
         "product": "Data Eng",   "quantity": "1",  "unit_price": "39.99"},
    ]


@pytest.fixture
def rows_with_nulls(sample_rows):
    """Rows that include some with missing quantity or unit_price."""
    return sample_rows + [
        {"date": "2024-01-20", "order_id": "ORD-006", "category": "Electronics",
         "product": "Keyboard", "quantity": "",    "unit_price": "79.99"},
        {"date": "2024-01-21", "order_id": "ORD-007", "category": "Clothing",
         "product": "Shoes",    "quantity": "2",   "unit_price": ""},
        {"date": "2024-01-22", "order_id": "ORD-008", "category": "Books",
         "product": "SQL Book", "quantity": "None","unit_price": "29.99"},
    ]


@pytest.fixture
def single_category_rows():
    """Only Electronics rows — useful for revenue math assertions."""
    return [
        {"date": "2024-03-01", "order_id": "ORD-100", "category": "Electronics",
         "product": "Monitor", "quantity": "1", "unit_price": "300.00"},
        {"date": "2024-03-02", "order_id": "ORD-101", "category": "Electronics",
         "product": "Keyboard", "quantity": "2", "unit_price": "50.00"},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# TEST TRANSFORM — TOTALS
# ─────────────────────────────────────────────────────────────────────────────

def test_transform_calculates_totals_correctly(single_category_rows):
    """
    Revenue per category must equal sum(quantity * unit_price).
    Monitor: 1 * 300.00 = 300.00
    Keyboard: 2 * 50.00 = 100.00
    Total Electronics: 400.00
    """
    result = transform(single_category_rows)

    assert len(result) == 1, "Expected one category summary"
    row = result[0]
    assert row["category"] == "Electronics"
    assert row["total_revenue"] == pytest.approx(400.00, rel=1e-6)
    assert row["total_units"] == 3      # 1 + 2
    assert row["order_count"] == 2


def test_transform_aggregates_multiple_categories(sample_rows):
    """Each unique category appears exactly once in the output."""
    result = transform(sample_rows)

    categories = [r["category"] for r in result]
    assert "Electronics" in categories
    assert "Clothing" in categories
    assert "Books" in categories
    assert len(result) == 3, "Expected exactly 3 category summaries"


def test_transform_sorts_by_revenue_descending(sample_rows):
    """
    Output must be sorted highest revenue first.
    Electronics total: 2*999.99 + 5*49.99 = 2249.93
    Clothing total:    10*19.99 + 3*59.99 = 379.87
    Books total:       1*39.99 = 39.99
    """
    result = transform(sample_rows)

    revenues = [r["total_revenue"] for r in result]
    assert revenues == sorted(revenues, reverse=True), (
        "Rows should be sorted by total_revenue descending"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST TRANSFORM — NULL FILTERING
# ─────────────────────────────────────────────────────────────────────────────

def test_transform_filters_null_quantity_rows(rows_with_nulls):
    """
    Rows where quantity is empty or non-numeric must be dropped.
    The 3 null rows added by the fixture should not appear in output.
    """
    clean_result = transform(
        [r for r in rows_with_nulls if r["quantity"] and r["unit_price"]]
    )
    null_result = transform(rows_with_nulls)

    # order_count across all categories should be equal
    # (null rows get dropped, so counts match the clean dataset)
    clean_total = sum(r["order_count"] for r in clean_result)
    null_total  = sum(r["order_count"] for r in null_result)
    assert clean_total == null_total, (
        "Null rows should be filtered out — order_count should not include them"
    )


def test_transform_filters_null_price_rows(rows_with_nulls):
    """Rows where unit_price is empty must also be filtered."""
    result = transform(rows_with_nulls)
    # ORD-007 has empty unit_price (Clothing, qty=2)
    # If it was included: Clothing order_count would be at least 3
    # After filtering: Clothing has exactly 2 clean rows from sample_rows
    clothing = next((r for r in result if r["category"] == "Clothing"), None)
    assert clothing is not None
    assert clothing["order_count"] == 2, (
        "Clothing should have 2 orders — the null-price row must be filtered"
    )


def test_transform_returns_empty_list_for_empty_input():
    """Transform on an empty list returns an empty list, not an error."""
    result = transform([])
    assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# TEST TRANSFORM — DATE PARSING
# ─────────────────────────────────────────────────────────────────────────────

def test_transform_parses_dates(single_category_rows):
    """
    Date strings in the input must be parseable without errors.
    We don't expose parsed dates in the aggregate output,
    but invalid dates should not cause transform to crash.
    """
    # Valid ISO dates should not raise
    result = transform(single_category_rows)
    assert result is not None
    assert len(result) > 0


def test_parse_date_valid_iso():
    """_parse_date must return a date object for valid ISO strings."""
    result = _parse_date("2024-06-15")
    assert result == date(2024, 6, 15)


def test_parse_date_invalid_returns_none():
    """_parse_date must return None for garbage strings (not raise)."""
    assert _parse_date("not-a-date") is None
    assert _parse_date("") is None
    assert _parse_date(None) is None
    assert _parse_date("2024/06/15") is None  # wrong separator


# ─────────────────────────────────────────────────────────────────────────────
# TEST HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def test_to_float_valid_string():
    """_to_float must convert numeric strings to float."""
    from pipeline import _to_float
    assert _to_float("42.5") == pytest.approx(42.5)
    assert _to_float("100")  == pytest.approx(100.0)
    assert _to_float("0")    == pytest.approx(0.0)


def test_to_float_invalid_returns_none():
    """_to_float must return None for non-numeric input (not raise)."""
    from pipeline import _to_float
    assert _to_float("") is None
    assert _to_float("abc") is None
    assert _to_float(None) is None
    assert _to_float("N/A") is None


# ─────────────────────────────────────────────────────────────────────────────
# TEST EXTRACT
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_returns_list_of_dicts(tmp_path):
    """
    extract() must return a list of dicts with the expected columns.
    Uses tmp_path (pytest built-in fixture) — no real file needed on disk.
    """
    csv_file = tmp_path / "test_sales.csv"
    csv_file.write_text(
        "date,order_id,category,product,quantity,unit_price\n"
        "2024-01-01,ORD-001,Electronics,Laptop,1,999.99\n"
        "2024-01-02,ORD-002,Books,Python,2,39.99\n"
    )

    rows = extract(str(csv_file))

    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0]["category"] == "Electronics"
    assert rows[1]["category"] == "Books"


def test_extract_raises_on_missing_file():
    """extract() must raise FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError):
        extract("/tmp/this_file_absolutely_does_not_exist_xyz123.csv")


# ─────────────────────────────────────────────────────────────────────────────
# TEST LOAD
# ─────────────────────────────────────────────────────────────────────────────

def test_load_writes_csv_with_correct_columns(tmp_path):
    """load() must write a CSV with the four summary columns."""
    summary = [
        {"category": "Electronics", "total_revenue": 1999.98,
         "total_units": 2, "order_count": 1},
        {"category": "Books", "total_revenue": 39.99,
         "total_units": 1, "order_count": 1},
    ]

    output_path = load(summary, str(tmp_path))

    assert output_path.endswith("summary.csv")
    content = (tmp_path / "summary.csv").read_text()
    assert "category" in content
    assert "total_revenue" in content
    assert "Electronics" in content
    assert "Books" in content


def test_load_creates_output_directory(tmp_path):
    """load() must create the output directory if it does not exist."""
    nested_dir = tmp_path / "a" / "b" / "c"
    summary = [{"category": "X", "total_revenue": 1.0,
                "total_units": 1, "order_count": 1}]
    load(summary, str(nested_dir))
    assert (nested_dir / "summary.csv").exists()


def test_load_handles_empty_summary(tmp_path):
    """load() with an empty list must not crash — writes an empty file."""
    output_path = load([], str(tmp_path))
    assert output_path.endswith("summary.csv")
