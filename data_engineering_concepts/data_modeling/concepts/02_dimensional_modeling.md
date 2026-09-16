# Concept 02: Dimensional Modeling (Kimball Methodology)

**Covers:**
- Facts vs. dimensions, and why that split is the whole idea
- Grain — the single most important design decision, and why you declare it before naming a table
- The three classic fact table types: transaction, periodic snapshot, accumulating snapshot
- Surrogate keys vs. natural keys, and the concrete reasons to bother with surrogates
- Degenerate dimensions and junk dimensions

*All SQL below is real, runnable SQLite — copy any block into a `python3` shell and it runs as shown.*

---

## 1. Facts and Dimensions: The Core Split

Dimensional modeling — popularized by Ralph Kimball — organizes a warehouse around two kinds of tables:

- **Dimension tables** answer *who, what, where, when* — the descriptive context you filter and group by.
- **Fact tables** hold the *numeric measurements* of a business event or state, plus foreign keys pointing out to the dimensions that describe it.

Every dimension table gets both a **surrogate key** (a warehouse-generated integer, meaningless outside the warehouse) and a **natural key** (the business identifier from the source system):

```sql
CREATE TABLE dim_product (
    product_key     INTEGER PRIMARY KEY AUTOINCREMENT,  -- surrogate
    product_id      TEXT NOT NULL UNIQUE,                -- natural key
    product_name    TEXT NOT NULL,
    category        TEXT,
    subcategory     TEXT,
    unit_cost       REAL
);
INSERT INTO dim_product (product_id, product_name, category, subcategory, unit_cost) VALUES
    ('SKU-001', 'Laptop Pro 15',  'Electronics', 'Computers',   899.00),
    ('SKU-002', 'Wireless Mouse', 'Electronics', 'Peripherals',  25.00),
    ('SKU-003', 'Standing Desk',  'Furniture',   'Desks',       450.00),
    ('SKU-004', 'Ergonomic Chair','Furniture',   'Chairs',      350.00),
    ('SKU-005', 'USB-C Hub',      'Electronics', 'Peripherals',  45.00);
```

A `dim_date` table is the one dimension nearly every fact table joins to, and it's typically pre-generated for years into the future rather than computed on the fly:

```sql
CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,   -- surrogate key: YYYYMMDD
    full_date       TEXT NOT NULL,
    year            INTEGER,
    quarter         INTEGER,
    month           INTEGER,
    month_name      TEXT,
    day_of_week     TEXT,
    is_weekend      INTEGER
);
-- one row per calendar day, generated ahead of time in a load job
-- e.g. (20250101, '2025-01-01', 2025, 1, 1, 'January', 'Wednesday', 0)
```

---

## 2. Grain: The Decision Everything Else Follows

**Grain** is the answer to one sentence: *"what does one row in this table represent?"* It is the single most important design decision in a dimensional model, and it must be stated explicitly, in English, before you name a single column.

```text
  Table                     Grain                                          Dimensions                        Facts
  fact_sales                One row per product per order (line item)      date, product, customer, store    quantity_sold, unit_price, discount, line_total
  fact_inventory_daily      One row per product per store per day          date, product, store               qty_on_hand, qty_on_order, days_of_supply
  fact_order_fulfillment    One row per order (lifecycle)                  customer, multiple date roles      order_total, lag measures
```

Why this matters in practice: every dimension, every measure, and every query-correctness question traces back to the grain. If a fact table silently mixes two grains — say, an `order_total` that belongs at the order level sitting on a table whose actual grain is one row per line item — summing that column double- or triple-counts it. (This exact bug is worked through end to end in `interview_questions/03_critique_and_debug.md`, Case 1.) Declaring the grain first is what prevents it from ever being written in the first place.

---

## 3. The Three Classic Fact Table Types

### Transaction Fact — one row per discrete event

The most common shape: append-only, one row per event, never updated after it lands.

```sql
CREATE TABLE fact_sales (
    sale_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key        INTEGER REFERENCES dim_date(date_key),
    product_key     INTEGER REFERENCES dim_product(product_key),
    customer_key    INTEGER REFERENCES dim_customer(customer_key),
    store_key       INTEGER REFERENCES dim_store(store_key),
    flag_key        INTEGER REFERENCES dim_order_flags(flag_key),
    invoice_number  TEXT,       -- degenerate dimension, see section 5
    quantity_sold   INTEGER NOT NULL,
    unit_price      REAL NOT NULL,
    discount_amount REAL DEFAULT 0,
    line_total      REAL NOT NULL
);
```

**Grain: one row per product per order.** A typical analytical query needs only a couple of joins:

```sql
SELECT c.segment, SUM(f.line_total) AS revenue
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.segment
ORDER BY revenue DESC;
```

### Periodic Snapshot — one row per entity per fixed time interval

A frozen, point-in-time measurement, appended once per period and never changed afterward — inventory levels, account balances, daily stock prices.

```sql
CREATE TABLE fact_inventory_daily (
    date_key        INTEGER REFERENCES dim_date(date_key),
    product_key     INTEGER REFERENCES dim_product(product_key),
    store_key       INTEGER REFERENCES dim_store(store_key),
    qty_on_hand     INTEGER,
    qty_on_order    INTEGER,
    days_of_supply  REAL,
    PRIMARY KEY (date_key, product_key, store_key)
);
```

**Grain: one row per product per store per day.** Trend queries are a straight filter + group:

```sql
SELECT d.full_date, p.product_name, f.qty_on_hand
FROM fact_inventory_daily f
JOIN dim_date d    ON f.date_key    = d.date_key
JOIN dim_product p ON f.product_key = p.product_key
WHERE p.product_name = 'Laptop Pro 15' AND f.store_key = 2;
-- ('2025-01-15', 'Laptop Pro 15', 50)
-- ('2025-01-16', 'Laptop Pro 15', 49)
```

A periodic snapshot's measures are frequently **semi-additive**: safe to sum across the dimension being snapshotted (e.g., across products, or across accounts), never safe to sum across time for the same entity. `qty_on_hand` summed across all products on one day is a meaningful total; summed across all days for one product, it's meaningless. This distinction is worth internalizing now — it comes back constantly (see `interview_questions/02_rapid_fire_qna.md` and Case 5 in `interview_questions/03_critique_and_debug.md`).

### Accumulating Snapshot — one row per process instance, updated in place

Unlike the other two, this row gets **revised** as an entity moves through a lifecycle with a small, known number of milestones — an order moving through placed → paid → shipped → delivered.

```sql
CREATE TABLE fact_order_fulfillment (
    order_key           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_key        INTEGER REFERENCES dim_customer(customer_key),
    order_date_key      INTEGER REFERENCES dim_date(date_key),
    payment_date_key    INTEGER REFERENCES dim_date(date_key),
    ship_date_key       INTEGER REFERENCES dim_date(date_key),
    delivery_date_key   INTEGER REFERENCES dim_date(date_key),  -- NULL/placeholder until reached
    days_to_payment     INTEGER,
    days_to_ship        INTEGER,
    days_to_deliver     INTEGER,
    order_total         REAL
);

INSERT INTO fact_order_fulfillment
    (customer_key, order_date_key, payment_date_key, ship_date_key, delivery_date_key,
     days_to_payment, days_to_ship, days_to_deliver, order_total)
VALUES
    (1, 20250115, 20250115, 20250117, 20250121, 0, 2, 4, 944.00),   -- fully delivered
    (2, 20250116, 20250116, 20250118, NULL,     0, 2, NULL, 405.00), -- shipped, not delivered
    (3, 20250120, NULL,     NULL,     NULL,     NULL, NULL, NULL, 700.00); -- just placed
```

**Grain: one row per order lifecycle.** The same physical row is updated as each milestone is reached — this is the opposite append-only discipline of a transaction fact, and it's worth naming that difference unprompted in an interview. Finding orders still in flight is a simple filter:

```sql
SELECT order_key, order_total FROM fact_order_fulfillment WHERE delivery_date_key IS NULL;
-- Order 2: $405.00
-- Order 3: $700.00
```

`days_to_payment`, `days_to_ship`, `days_to_deliver` are **derived measures** — precomputed at load time rather than recalculated from four date columns on every query, specifically because "average days to ship" gets asked constantly. Not every fact table column needs to come straight from a source system.

---

## 4. Surrogate Keys vs. Natural Keys

- **Natural key**: the business-meaningful identifier from the source system (`SKU-001`, an order number).
- **Surrogate key**: a warehouse-generated, meaningless integer (`product_key = 1`), assigned on load.

```sql
SELECT f.sale_key, f.product_key, p.product_id, p.product_name
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
LIMIT 3;
-- sale_key=1, product_key=1, natural_key=SKU-001, name=Laptop Pro 15
```

Why bother with a layer of indirection at all:

1. **Insulation from source-system changes.** If the source system renames `SKU-001` to `PROD-001`, the warehouse doesn't care — `fact_sales.product_key` still points at surrogate key `1`.
2. **SCD Type 2 requires it.** The same natural key needs *multiple* surrogate-keyed rows over time, one per historical version — a natural key alone can't be the primary key of a table that deliberately stores several versions of the "same" entity. (Full treatment in `concepts/04_slowly_changing_dimensions.md`.)
3. **Join performance.** A small integer joins faster than a wide text natural key.
4. **A place to put "unknown."** A reserved surrogate key value (commonly `-1` or `0`) can represent "not applicable / not yet known" without ever putting a `NULL` in a foreign key column — see the unknown-member pattern in `interview_questions/02_rapid_fire_qna.md`.

There's a sharp failure mode when this layer is skipped: if a fact table's foreign key *is* the natural key straight from the source, and that source later reuses a deleted customer's ID for a brand-new customer, the warehouse has no way to tell the two people apart — the new customer inherits the old one's entire history. Worked in full as a diagnosis exercise in `interview_questions/03_critique_and_debug.md`, Case 6.

---

## 5. Degenerate and Junk Dimensions

A **degenerate dimension** is a dimension-like value that lives directly on the fact table with no dimension table behind it, because it has no further attributes to describe — `invoice_number` above is exactly this. You group and filter by it like a dimension, but a whole table holding nothing but the invoice number itself would be pointless:

```sql
SELECT f.invoice_number, p.product_name, f.quantity_sold, f.line_total
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
WHERE f.invoice_number = 'INV-1001';
-- ('INV-1001', 'Laptop Pro 15', 1, 899.0)
-- ('INV-1001', 'Wireless Mouse', 2, 45.0)
```

A **junk dimension** bundles several small, low-cardinality flags that don't deserve their own tables and don't obviously belong on any single existing dimension — instead of `fact_sales` growing one foreign key per flag, they're collapsed into one small combined dimension:

```sql
CREATE TABLE dim_order_flags (
    flag_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    is_gift_wrapped INTEGER NOT NULL,
    is_expedited    INTEGER NOT NULL,
    payment_method  TEXT NOT NULL,
    UNIQUE (is_gift_wrapped, is_expedited, payment_method)
);
INSERT INTO dim_order_flags (is_gift_wrapped, is_expedited, payment_method) VALUES
    (0, 0, 'Credit Card'), (0, 1, 'Credit Card'), (1, 0, 'Credit Card'),
    (0, 0, 'PayPal'),      (1, 1, 'PayPal');
```

---

## Key Takeaways

- Dimension tables answer who/what/where/when; fact tables hold the numeric measurements of an event or state plus the foreign keys that describe it.
- Grain — "what does one row represent?" — must be declared in one sentence before any table is named; every downstream design and correctness question traces back to it.
- Transaction facts are append-only, one row per event. Periodic snapshots are append-only, one row per entity per fixed interval, and their measures are often semi-additive (safe across entities, not across time). Accumulating snapshots have a small number of known milestones and get updated in place as an entity progresses.
- Surrogate keys insulate the warehouse from source-system key changes, are required to make SCD Type 2 possible at all, join faster than text natural keys, and provide a safe place to represent "unknown."
- Degenerate dimensions live on the fact table directly when there's nothing left to describe; junk dimensions bundle several small flags into one table instead of one foreign key per flag.
