"""
Sample ETL Pipeline — Sales Data Aggregation
=============================================
A realistic ETL pipeline used as the CI/CD demo project.

Pipeline flow:
  Extract  → read sales_data.csv (generate sample data if absent)
  Transform → parse dates, calculate totals per category, filter nulls
  Load     → write summary to output/summary.csv

Configuration via environment variables:
  INPUT_FILE   path to the input CSV  (default: data/sales_data.csv)
  OUTPUT_DIR   directory for outputs  (default: output)

Usage:
  python pipeline.py                  # run with defaults
  INPUT_FILE=custom.csv python pipeline.py
"""

import os
import csv
import random
import logging
from datetime import date, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Configuration (read from env with sensible defaults) ──────────────────────

INPUT_FILE = os.environ.get("INPUT_FILE", "data/sales_data.csv")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")

# ── Column names ──────────────────────────────────────────────────────────────

COLUMNS = ["date", "order_id", "category", "product", "quantity", "unit_price"]


# ─────────────────────────────────────────────────────────────────────────────
# GENERATE SAMPLE DATA  (only used when INPUT_FILE doesn't exist)
# ─────────────────────────────────────────────────────────────────────────────

def generate_sample_data(path: str, n_rows: int = 200) -> None:
    """Write a synthetic sales CSV so the demo works without real data."""
    logger.info("Generating sample data: %s (%d rows)", path, n_rows)

    categories = ["Electronics", "Clothing", "Food", "Books", "Furniture"]
    products = {
        "Electronics": ["Laptop", "Headphones", "Keyboard", "Monitor"],
        "Clothing":    ["T-Shirt", "Jeans", "Jacket", "Shoes"],
        "Food":        ["Coffee", "Tea", "Snacks", "Juice"],
        "Books":       ["Python Guide", "Data Engineering", "SQL Mastery"],
        "Furniture":   ["Desk", "Chair", "Shelf", "Lamp"],
    }

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    start_date = date(2024, 1, 1)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for i in range(n_rows):
            category = random.choice(categories)
            row_date = start_date + timedelta(days=random.randint(0, 364))
            row = {
                "date":       row_date.isoformat(),
                "order_id":   f"ORD-{10000 + i:05d}",
                "category":   category,
                "product":    random.choice(products[category]),
                "quantity":   random.randint(1, 20) if random.random() > 0.05 else "",
                "unit_price": round(random.uniform(5.0, 500.0), 2) if random.random() > 0.05 else "",
            }
            writer.writerow(row)

    logger.info("Sample data written: %s", path)


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACT
# ─────────────────────────────────────────────────────────────────────────────

def extract(filepath: str) -> list[dict]:
    """
    Read sales data from a CSV file.

    Parameters
    ----------
    filepath : str
        Path to the input CSV.

    Returns
    -------
    list[dict]
        Each row as a dictionary keyed by column name.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    rows: list[dict] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))

    logger.info("Extracted %d rows from %s", len(rows), filepath)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORM
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> date | None:
    """Parse ISO date string. Return None on failure."""
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _to_float(value: str) -> float | None:
    """Convert string to float. Return None on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def transform(rows: list[dict]) -> list[dict]:
    """
    Clean and aggregate sales rows.

    Steps:
      1. Parse date strings to date objects.
      2. Parse quantity and unit_price to numeric types.
      3. Drop rows where quantity or unit_price is null/invalid.
      4. Calculate total_revenue = quantity * unit_price per row.
      5. Aggregate totals by category:
         - total_revenue
         - total_units
         - order_count

    Parameters
    ----------
    rows : list[dict]
        Raw rows from extract().

    Returns
    -------
    list[dict]
        One summary dict per category with keys:
        category, total_revenue, total_units, order_count
    """
    if not rows:
        logger.warning("Transform received empty dataset")
        return []

    # ── Step 1-4: parse and filter ────────────────────────────────────────────
    cleaned: list[dict] = []
    null_count = 0

    for row in rows:
        parsed_date = _parse_date(row.get("date", ""))
        qty = _to_float(row.get("quantity", ""))
        price = _to_float(row.get("unit_price", ""))

        if qty is None or price is None:
            null_count += 1
            continue  # filter out incomplete rows

        cleaned.append(
            {
                "date":          parsed_date,
                "order_id":      row.get("order_id", ""),
                "category":      row.get("category", "Unknown"),
                "product":       row.get("product", ""),
                "quantity":      qty,
                "unit_price":    price,
                "total_revenue": round(qty * price, 2),
            }
        )

    logger.info(
        "Transform: %d rows cleaned, %d null rows dropped",
        len(cleaned),
        null_count,
    )

    # ── Step 5: aggregate by category ────────────────────────────────────────
    aggregates: dict[str, dict] = {}

    for row in cleaned:
        cat = row["category"]
        if cat not in aggregates:
            aggregates[cat] = {
                "category":      cat,
                "total_revenue": 0.0,
                "total_units":   0,
                "order_count":   0,
            }
        aggregates[cat]["total_revenue"] += row["total_revenue"]
        aggregates[cat]["total_units"]   += int(row["quantity"])
        aggregates[cat]["order_count"]   += 1

    # Round totals
    for agg in aggregates.values():
        agg["total_revenue"] = round(agg["total_revenue"], 2)

    summary = sorted(aggregates.values(), key=lambda x: x["total_revenue"], reverse=True)
    logger.info("Transform: produced %d category summaries", len(summary))
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# LOAD
# ─────────────────────────────────────────────────────────────────────────────

def load(summary: list[dict], output_dir: str) -> str:
    """
    Write the summary to output_dir/summary.csv.

    Parameters
    ----------
    summary : list[dict]
        Transformed summary rows.
    output_dir : str
        Directory to write output. Created if absent.

    Returns
    -------
    str
        Absolute path of the written file.
    """
    out_path = Path(output_dir) / "summary.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not summary:
        logger.warning("Load received empty summary — writing empty file")
        out_path.write_text("")
        return str(out_path.resolve())

    fieldnames = ["category", "total_revenue", "total_units", "order_count"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    logger.info("Loaded %d rows to %s", len(summary), out_path)
    return str(out_path.resolve())


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(input_file: str = INPUT_FILE, output_dir: str = OUTPUT_DIR) -> str:
    """Run the full ETL pipeline. Returns the output file path."""
    logger.info("Pipeline starting")

    # Generate sample data if needed
    if not Path(input_file).exists():
        logger.info("Input file not found — generating sample data")
        generate_sample_data(input_file)

    # ETL
    raw_rows = extract(input_file)
    summary = transform(raw_rows)
    output_path = load(summary, output_dir)

    logger.info("Pipeline complete. Output: %s", output_path)
    return output_path


if __name__ == "__main__":
    run_pipeline()
