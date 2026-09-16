# Capstone Project: Build a SchemaDesigner Tool

## Scenario

You're asked to build a small internal tool that automates the
mechanical parts of the data modeling work covered in `concepts/`:
decomposing a flat table toward 3NF given a set of functional
dependencies, standing up a star schema from a set of dimension/fact
definitions, applying SCD Type 2 changes without hand-writing the
expire-then-insert SQL every time, and running a handful of sanity
checks against whatever schema currently exists. This is the kind of
tool a data platform team actually builds and reuses — not a one-off
script — and building it forces you to turn "I understand normalization
and SCD Type 2" into "I can express that understanding as reusable code
that handles cases I didn't originally think of."

## Learning Goal

Implement a `SchemaDesigner` class against the interface specified below,
backed by an in-memory SQLite database. This exercises grain discipline,
normalization mechanics, star schema construction, SCD Type 2's
expire-then-insert pattern, and basic schema validation, all in one
project — the same concepts from `concepts/01_normalization.md` through
`concepts/04_slowly_changing_dimensions.md`, expressed as a general-purpose
tool rather than one-off examples.

This brief gives you the class interface, the expected behavior of each
method, and a worked example of what running the finished tool should
produce — build the implementation yourself before checking your design
against the notes at the end.

---

## The Interface

```python
import sqlite3


class SchemaDesigner:
    """
    A data warehouse schema designer that automates common modeling tasks.

    Usage:
        sd = SchemaDesigner()
        sd.normalize(table_name, flat_rows, columns, dependencies)
        sd.create_star_schema(fact_name, fact_measures, dimensions, fact_data)
        sd.apply_scd_type2(dim_table, natural_key_col, natural_key_val, updates, change_date)
        ddl = sd.generate_ddl()
        issues = sd.validate_schema()
    """

    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        # TODO: whatever internal bookkeeping you need (e.g. a registry
        # of table -> {columns, pk, fks} to support generate_ddl/validate_schema)

    def close(self):
        self.conn.close()

    # -----------------------------------------------------------------
    # 1. NORMALIZE
    # -----------------------------------------------------------------
    def normalize(self, table_name, flat_rows, columns, dependencies):
        """
        Decompose a flat table into normalized sub-tables based on
        declared functional dependencies.

        Args:
            table_name:   Name for the source flat table.
            flat_rows:    List of tuples matching `columns`.
            columns:      List of column names.
            dependencies: Dict mapping determinant column(s) to a list of
                          dependent columns, e.g.
                          {"customer_id": ["customer_name", "city"],
                           "product_id": ["product_name", "price"]}
                          A composite determinant is a comma-separated
                          string, e.g. "order_id,product_id".

        Returns:
            Dict of {new_table_name: [rows]} for each decomposed table,
            including a "core"/remaining table for whatever columns
            weren't claimed by any dependency group.

        Requirements:
            - Each determinant becomes its own table, keyed on the
              determinant column(s), holding only DISTINCT (determinant,
              dependents) combinations -- this IS the 2NF/3NF extraction
              from concepts/01_normalization.md, sections 3-4.
            - Whatever original columns aren't consumed by any
              dependency group become a remaining "core" table that ties
              the pieces back together.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 2. CREATE STAR SCHEMA
    # -----------------------------------------------------------------
    def create_star_schema(self, fact_name, fact_measures, dimensions, fact_data=None):
        """
        Build a complete star schema: one dimension table per entry in
        `dimensions`, plus a fact table referencing all of them by
        surrogate key.

        Args:
            fact_name:      Name of the fact table.
            fact_measures:  List of measure column names.
            dimensions:     Dict of {dim_table_name: {
                                "columns": {col_name: col_type, ...},
                                "natural_key": "col_name",
                                "data": [list of dicts]
                            }}
            fact_data:      List of dicts with dim natural keys + measure values
                            -- natural keys must be resolved to surrogate
                            keys during the insert, not stored directly.

        Returns:
            Dict summarizing created tables (fact name + dimension names).

        Requirements:
            - Every dimension table gets an AUTOINCREMENT surrogate key
              column named f"{dim_name}_key" (see concepts/02, section 1) --
              never let the fact table store the natural key directly.
            - The fact table gets one FK column per dimension
              (f"{dim_name}_key"), plus one REAL column per measure.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 3. APPLY SCD TYPE 2
    # -----------------------------------------------------------------
    def apply_scd_type2(self, dim_table, natural_key_col, natural_key_val,
                         updates, change_date):
        """
        Apply an SCD Type 2 change to a dimension table.

        Requires the table to already have effective_date, expiration_date,
        and is_current columns (see concepts/04_slowly_changing_dimensions.md,
        section 3).

        Args:
            dim_table:        Table name.
            natural_key_col:  Column name of the natural/business key.
            natural_key_val:  Value of the natural key to update.
            updates:          Dict of {column: new_value} for changed attributes.
            change_date:      Date string (YYYY-MM-DD) when the change
                              takes effect.

        Returns:
            Tuple of (expired_surrogate_key, new_surrogate_key), or None
            if no current row was found for that natural key.

        Requirements:
            - Expire the CURRENT row: set expiration_date = change_date,
              is_current = 0 -- do not delete it.
            - Insert a NEW row: copy every column from the expired row
              except apply `updates`, set effective_date = change_date,
              expiration_date = '9999-12-31', is_current = 1.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 4. GENERATE DDL
    # -----------------------------------------------------------------
    def generate_ddl(self):
        """
        Return the CREATE TABLE DDL for every table this designer has
        built, in a stable (e.g. alphabetical) order.

        Requirements:
            - Read straight from sqlite_master rather than trying to
              reconstruct DDL from your own bookkeeping -- sqlite_master
              already has the exact SQL each table was created with.
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # 5. VALIDATE SCHEMA
    # -----------------------------------------------------------------
    def validate_schema(self):
        """
        Run sanity checks on the current schema and return a list of
        issue strings (empty list = all good).

        Required checks:
            1. Every table has a primary key.
            2. Every foreign key (via PRAGMA foreign_key_list) references
               a table that actually exists.
            3. [WARNING, not ERROR] any table with zero rows.
            4. Any table with an `is_current` column also has
               `effective_date` and `expiration_date` -- catches a
               half-implemented SCD Type 2 table.

        Requirements:
            - TODO: implement
        """
        raise NotImplementedError

    # -----------------------------------------------------------------
    # UTILITIES (given, not part of the graded interface)
    # -----------------------------------------------------------------
    def show_table(self, table_name, limit=20):
        """Print contents of a table -- useful while developing/debugging."""
        rows = self.conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,)).fetchall()
        for r in rows:
            print(f"    {tuple(r)}")

    def query(self, sql):
        """Execute a query and return results as a list of dicts."""
        return [dict(r) for r in self.conn.execute(sql).fetchall()]
```

---

## Worked Example: What the Finished Tool Should Do

This is the acceptance test for your implementation — build toward
producing exactly this behavior.

### 1. Normalize a flat dataset

```python
sd = SchemaDesigner()

flat_columns = [
    "order_id", "order_date", "customer_id", "customer_name", "customer_city",
    "product_id", "product_name", "product_price", "supplier_id", "supplier_name",
]
flat_rows = [
    ("O1", "2025-01-15", "C1", "Alice", "Portland", "P1", "Widget", "9.99", "S1", "Acme Corp"),
    ("O1", "2025-01-15", "C1", "Alice", "Portland", "P2", "Gadget", "24.99", "S1", "Acme Corp"),
    ("O2", "2025-01-16", "C2", "Bob",   "Seattle",  "P1", "Widget", "9.99",  "S1", "Acme Corp"),
    ("O3", "2025-01-17", "C1", "Alice", "Portland", "P3", "Gizmo",  "14.50", "S2", "Beta LLC"),
]
dependencies = {
    "customer_id": ["customer_name", "customer_city"],
    "product_id":  ["product_name", "product_price", "supplier_id"],
    "supplier_id": ["supplier_name"],
}

normalized = sd.normalize("orders_flat", flat_rows, flat_columns, dependencies)
for tbl_name in normalized:
    sd.show_table(tbl_name)
```

**Expected result:** four tables — `customer_id_dim` (2 rows: C1, C2),
`product_id_dim` (3 rows: P1, P2, P3), `supplier_id_dim` (2 rows: S1,
S2), and `orders_flat_core` (the remaining columns: `order_id`,
`order_date`, `product_id` — i.e. one row per original line item, tying
the pieces back together). No `customer_name` or `product_price`
appears more than once per distinct customer/product — that's the
normalization payoff.

### 2. Build a star schema for retail sales

```python
dimensions = {
    "dim_product": {
        "columns": {"product_id": "TEXT", "product_name": "TEXT", "category": "TEXT", "brand": "TEXT"},
        "natural_key": "product_id",
        "data": [
            {"product_id": "P1", "product_name": "Laptop", "category": "Electronics", "brand": "TechBrand"},
            {"product_id": "P2", "product_name": "Desk",   "category": "Furniture",   "brand": "OfficePro"},
            {"product_id": "P3", "product_name": "Mouse",  "category": "Electronics", "brand": "TechBrand"},
        ],
    },
    "dim_customer": {
        "columns": {
            "customer_id": "TEXT", "customer_name": "TEXT", "segment": "TEXT",
            "city": "TEXT", "state": "TEXT",
            "effective_date": "TEXT", "expiration_date": "TEXT", "is_current": "INTEGER",
        },
        "natural_key": "customer_id",
        "data": [
            {"customer_id": "C1", "customer_name": "Alice", "segment": "Consumer", "city": "Portland",
             "state": "OR", "effective_date": "2020-01-01", "expiration_date": "9999-12-31", "is_current": 1},
            {"customer_id": "C2", "customer_name": "Bob", "segment": "Corporate", "city": "Seattle",
             "state": "WA", "effective_date": "2019-06-01", "expiration_date": "9999-12-31", "is_current": 1},
        ],
    },
    "dim_store": {
        "columns": {"store_id": "TEXT", "store_name": "TEXT", "store_type": "TEXT"},
        "natural_key": "store_id",
        "data": [
            {"store_id": "S1", "store_name": "Online", "store_type": "Web"},
            {"store_id": "S2", "store_name": "Portland Retail", "store_type": "Retail"},
        ],
    },
}
fact_data = [
    {"product_id": "P1", "customer_id": "C1", "store_id": "S1", "quantity": 1, "revenue": 999.00, "discount": 0},
    {"product_id": "P3", "customer_id": "C1", "store_id": "S1", "quantity": 2, "revenue": 50.00, "discount": 5.0},
    {"product_id": "P2", "customer_id": "C2", "store_id": "S2", "quantity": 1, "revenue": 450.00, "discount": 45.0},
]

sd.create_star_schema(
    fact_name="fact_sales",
    fact_measures=["quantity", "revenue", "discount"],
    dimensions=dimensions,
    fact_data=fact_data,
)

results = sd.query("""
    SELECT p.category, SUM(f.revenue) AS total_revenue
    FROM fact_sales f
    JOIN dim_product p ON f.dim_product_key = p.dim_product_key
    GROUP BY p.category ORDER BY total_revenue DESC
""")
```

**Expected result:**
```python
[{'category': 'Electronics', 'total_revenue': 1049.0},
 {'category': 'Furniture',   'total_revenue': 450.0}]
```

### 3. Apply an SCD Type 2 change

```python
print("BEFORE:", sd.query("SELECT * FROM dim_customer WHERE customer_id = 'C1'"))

sd.apply_scd_type2(
    dim_table="dim_customer",
    natural_key_col="customer_id",
    natural_key_val="C1",
    updates={"city": "Bend"},
    change_date="2025-06-01",
)

print("AFTER:", sd.query(
    "SELECT * FROM dim_customer WHERE customer_id = 'C1' ORDER BY effective_date"
))

# Point-in-time check
before = sd.query("""
    SELECT customer_name, city FROM dim_customer
    WHERE customer_id = 'C1' AND effective_date <= '2024-12-01' AND expiration_date > '2024-12-01'
""")
after = sd.query("""
    SELECT customer_name, city FROM dim_customer
    WHERE customer_id = 'C1' AND effective_date <= '2025-07-01' AND expiration_date > '2025-07-01'
""")
```

**Expected result:** `AFTER` shows two rows for `C1` — the original
(now `is_current = 0`, `expiration_date = '2025-06-01'`, city
`Portland`) and a new one (`is_current = 1`, `expiration_date =
'9999-12-31'`, city `Bend`). The point-in-time checks return
`{'customer_name': 'Alice', 'city': 'Portland'}` for the December 2024
lookup and `{'customer_name': 'Alice', 'city': 'Bend'}` for the July
2025 lookup — exactly the "as of" query pattern from
`concepts/04_slowly_changing_dimensions.md`, section 3.

### 4. Generate DDL and validate

```python
ddl = sd.generate_ddl()      # prints every CREATE TABLE statement built so far
issues = sd.validate_schema()  # should print "All checks passed." if steps 1-3 above were done correctly
```

---

## Design Notes and Judgment Calls to Make Yourself

- **`normalize`**: decide how you name the extracted tables (e.g.
  `f"{determinant}_dim"`) and how you handle a composite determinant
  (comma-separated column names) — both are choices, not a single
  correct answer, as long as they're documented and consistent.
- **`create_star_schema`**: resolving natural keys to surrogate keys
  during the fact-data insert means building a lookup map per dimension
  first (natural key value → surrogate key) — don't try to do the
  lookup with a query per row if you can build the map once.
- **`apply_scd_type2`**: the trickiest part is copying every *unchanged*
  column from the current row into the new row while only applying the
  columns present in `updates` — introspect the current row's columns
  (e.g. via `sqlite3.Row.keys()`) rather than hardcoding a column list,
  so the method works against any dimension table, not just one you
  tested against.
- **`validate_schema`**: `PRAGMA table_info(table)` gives you each
  column's primary-key flag; `PRAGMA foreign_key_list(table)` gives you
  the tables a table's FKs point at — both are what you need for checks
  1 and 2 without hand-parsing DDL strings yourself.

## Stretch Goals

- Extend `validate_schema` to also flag a fact table whose declared
  grain columns (you decide how "declared" is represented) have
  duplicate combinations — the grain-uniqueness check named in
  `interview_questions/04_curveballs_tradeoffs.md`'s "how do you know
  your fact table is correct" curveball.
- Add a `build_obt(fact_name, dimensions)` method that materializes a
  One Big Table by pre-joining a fact table with all of its dimensions
  — the mechanical version of `concepts/05_one_big_table_and_lakehouse_modeling.md`,
  section 1.
- Add an `as_of(dim_table, natural_key_col, natural_key_val, as_of_date)`
  convenience method that wraps the point-in-time query pattern from
  step 3 above, so callers don't need to hand-write the
  `effective_date <= ? AND expiration_date > ?` predicate every time.

## Evaluation Criteria

- `normalize` correctly extracts one table per dependency group with
  distinct rows, and a remaining core table for unclaimed columns.
- `create_star_schema` never lets a fact table store a natural key
  directly — every dimension reference is resolved to a surrogate key.
- `apply_scd_type2` never mutates history — the old row is expired
  (not deleted, not overwritten), and the new row correctly carries
  forward every unchanged attribute.
- `validate_schema` catches all four required issue types against a
  deliberately broken test schema you construct yourself (e.g. a table
  with no primary key, a dangling foreign key, an empty table, a
  half-implemented SCD Type 2 table missing `effective_date`).
- The worked example above reproduces the stated expected results
  exactly when run against your implementation.
