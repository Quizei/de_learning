# Concept 01: Normalization (1NF Through BCNF, and When to Stop)

**Covers:**
- Functional dependency, candidate key, partial dependency, transitive dependency — the vocabulary the rest of this file is built on
- The three classic anomalies normalization exists to prevent: insertion, update, deletion
- 1NF, 2NF, 3NF, and BCNF, each demonstrated by fixing the specific problem in a real ORDER system, one step at a time
- When to stop normalizing and denormalize instead — the OLTP vs. OLAP framing that the rest of this course lives inside

*All SQL below is real, runnable SQLite (`sqlite3` module, Python 3, no external dependencies) — copy any block into a `python3` shell and it runs exactly as shown.*

---

## 1. The Vocabulary: Functional Dependencies

A **functional dependency** `A -> B` means: for any given value of `A`, there is exactly one value of `B`. Everything about normalization is just "find functional dependencies that don't respect the primary key, and pull them into their own table."

- **Candidate key**: the minimal set of columns that uniquely identifies a row.
- **Partial dependency**: a non-key column depends on only *part* of a composite primary key (only possible when the key has more than one column).
- **Transitive dependency**: `A -> B -> C`, where `C` depends on `A` only *through* `B` — `C` isn't really about `A` at all, it's about `B`.

Normalization prevents three concrete anomalies, demonstrated below against a single flat `orders_flat` table that stores order, customer, product, and supplier data all in one place — the way data often arrives from a CSV export or a legacy system:

```sql
CREATE TABLE orders_flat (
    order_id        INTEGER,
    order_date      TEXT,
    customer_id     INTEGER,
    customer_name   TEXT,
    customer_city   TEXT,
    customer_state  TEXT,
    product_ids     TEXT,       -- comma-separated! violates 1NF
    product_names   TEXT,       -- comma-separated!
    product_prices  TEXT,       -- comma-separated!
    supplier_name   TEXT,
    supplier_phone  TEXT
);

INSERT INTO orders_flat VALUES
    (1, '2025-01-15', 101, 'Alice', 'Portland', 'OR',
     'P1,P2', 'Widget,Gadget', '9.99,24.99', 'Acme Corp', '555-0100'),
    (2, '2025-01-16', 102, 'Bob', 'Seattle', 'WA',
     'P1', 'Widget', '9.99', 'Acme Corp', '555-0100'),
    (3, '2025-01-17', 101, 'Alice', 'Portland', 'OR',
     'P3', 'Doohickey', '14.50', 'Beta LLC', '555-0200');
```

**Insertion anomaly**: you cannot record a new supplier, "Gamma Inc," until it has at least one order — supplier data has no independent existence in this table.

**Update anomaly**: Alice moves from Portland to Bend. Because her city is repeated on every one of her order rows, you must update *every row that mentions her*, not one row:

```sql
UPDATE orders_flat SET customer_city = 'Bend' WHERE customer_id = 101;
-- SELECT order_id, customer_city FROM orders_flat WHERE customer_id = 101;
```
**Output:**
```text
(1, 'Bend'), (3, 'Bend')
```
Two rows changed for what is conceptually one fact ("Alice lives in Bend now"). Miss one row during a partial update and the table becomes self-contradictory.

**Deletion anomaly**: deleting order 3 is the *only* record of supplier "Beta LLC" anywhere in the table — deleting the order silently deletes the supplier too.

```sql
DELETE FROM orders_flat WHERE order_id = 3;
-- SELECT * FROM orders_flat WHERE supplier_name = 'Beta LLC';
```
**Output:**
```text
(no rows)
```

All three anomalies have the same root cause: this one table is trying to be four things at once (orders, customers, products, suppliers), and normalization is the systematic process of giving each "thing" its own table.

---

## 2. First Normal Form (1NF): Atomic Values, No Repeating Groups

**Rule:** every column holds a single, indivisible value; no comma-separated lists in a cell; every row is uniquely identifiable.

The `product_ids` / `product_names` / `product_prices` columns above each pack multiple values into one cell — a repeating group. Fix: one row per (order, product) pair, with a composite primary key.

```sql
CREATE TABLE orders_1nf (
    order_id        INTEGER,
    order_date      TEXT,
    customer_id     INTEGER,
    customer_name   TEXT,
    customer_city   TEXT,
    customer_state  TEXT,
    product_id      TEXT,
    product_name    TEXT,
    product_price   REAL,
    supplier_name   TEXT,
    supplier_phone  TEXT,
    PRIMARY KEY (order_id, product_id)
);

INSERT INTO orders_1nf VALUES
    (1, '2025-01-15', 101, 'Alice', 'Portland', 'OR', 'P1', 'Widget',    9.99,  'Acme Corp', '555-0100'),
    (1, '2025-01-15', 101, 'Alice', 'Portland', 'OR', 'P2', 'Gadget',   24.99,  'Acme Corp', '555-0100'),
    (2, '2025-01-16', 102, 'Bob',   'Seattle',  'WA', 'P1', 'Widget',    9.99,  'Acme Corp', '555-0100'),
    (3, '2025-01-17', 101, 'Alice', 'Portland', 'OR', 'P3', 'Doohickey', 14.50, 'Beta LLC',  '555-0200');
```

**Problem remaining:** the primary key is now `(order_id, product_id)`, but `customer_name` depends only on `order_id` (via `customer_id`) — it has nothing to do with `product_id`. That's a **partial dependency**, and it's exactly what 2NF removes next.

---

## 3. Second Normal Form (2NF): No Partial Dependencies

**Rule:** must already be 1NF, plus every non-key column depends on the *whole* composite key, not just part of it.

- `customer_name`, `customer_city`, `customer_state` depend only on `customer_id` (part of the key) → partial dependency.
- `product_name`, `product_price`, `supplier_name`, `supplier_phone` depend only on `product_id` (the other part) → partial dependency.

Fix: extract customers and products into their own tables, leaving only the true order-line association behind.

```sql
CREATE TABLE customers_2nf (
    customer_id     INTEGER PRIMARY KEY,
    customer_name   TEXT NOT NULL,
    customer_city   TEXT,
    customer_state  TEXT
);
INSERT INTO customers_2nf VALUES
    (101, 'Alice', 'Portland', 'OR'),
    (102, 'Bob',   'Seattle',  'WA');

CREATE TABLE products_2nf (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    product_price   REAL,
    supplier_name   TEXT,
    supplier_phone  TEXT
);
INSERT INTO products_2nf VALUES
    ('P1', 'Widget',    9.99,  'Acme Corp', '555-0100'),
    ('P2', 'Gadget',   24.99,  'Acme Corp', '555-0100'),
    ('P3', 'Doohickey', 14.50, 'Beta LLC',  '555-0200');

CREATE TABLE order_items_2nf (
    order_id    INTEGER,
    order_date  TEXT,
    customer_id INTEGER REFERENCES customers_2nf(customer_id),
    product_id  TEXT    REFERENCES products_2nf(product_id),
    PRIMARY KEY (order_id, product_id)
);
INSERT INTO order_items_2nf VALUES
    (1, '2025-01-15', 101, 'P1'),
    (1, '2025-01-15', 101, 'P2'),
    (2, '2025-01-16', 102, 'P1'),
    (3, '2025-01-17', 101, 'P3');
```

**Problem remaining:** inside `products_2nf`, `supplier_phone` depends on `supplier_name`, not on `product_id` directly — `product_id -> supplier_name -> supplier_phone`. That's a **transitive dependency**, and 3NF removes it.

---

## 4. Third Normal Form (3NF): No Transitive Dependencies

**Rule:** must already be 2NF, plus no non-key column depends on another non-key column.

Fix: extract suppliers into their own table, and split `order_items_2nf` back into a clean `orders` header plus an `order_items` association carrying only foreign keys and a quantity.

```sql
CREATE TABLE suppliers_3nf (
    supplier_id     INTEGER PRIMARY KEY,
    supplier_name   TEXT NOT NULL,
    supplier_phone  TEXT
);
INSERT INTO suppliers_3nf VALUES (1, 'Acme Corp', '555-0100'), (2, 'Beta LLC', '555-0200');

CREATE TABLE products_3nf (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    product_price   REAL,
    supplier_id     INTEGER REFERENCES suppliers_3nf(supplier_id)
);
INSERT INTO products_3nf VALUES
    ('P1', 'Widget',    9.99,  1),
    ('P2', 'Gadget',   24.99,  1),
    ('P3', 'Doohickey', 14.50, 2);

CREATE TABLE orders_3nf (
    order_id    INTEGER PRIMARY KEY,
    order_date  TEXT,
    customer_id INTEGER REFERENCES customers_2nf(customer_id)
);
INSERT INTO orders_3nf VALUES (1, '2025-01-15', 101), (2, '2025-01-16', 102), (3, '2025-01-17', 101);

CREATE TABLE order_items_3nf (
    order_id    INTEGER REFERENCES orders_3nf(order_id),
    product_id  TEXT    REFERENCES products_3nf(product_id),
    quantity    INTEGER DEFAULT 1,
    PRIMARY KEY (order_id, product_id)
);
INSERT INTO order_items_3nf VALUES (1, 'P1', 2), (1, 'P2', 1), (2, 'P1', 5), (3, 'P3', 3);
```

**Confirm zero redundancy** by reconstructing the original flat view with joins — every fact now lives in exactly one place:

```sql
SELECT o.order_id, o.order_date, c.customer_name, c.customer_city,
       p.product_name, p.product_price, s.supplier_name
FROM order_items_3nf oi
JOIN orders_3nf o    ON oi.order_id   = o.order_id
JOIN customers_2nf c ON o.customer_id = c.customer_id
JOIN products_3nf p  ON oi.product_id = p.product_id
JOIN suppliers_3nf s ON p.supplier_id = s.supplier_id;
```
**Output (first row):**
```text
(1, '2025-01-15', 'Alice', 'Portland', 'Widget', 9.99, 'Acme Corp')
```

Alice's city now lives in exactly one row of `customers_2nf` — moving her means one `UPDATE`, not a search-and-replace across every order she's ever placed.

---

## 5. Boyce-Codd Normal Form (BCNF): The Stricter 3NF

3NF says every non-key column depends on the whole key and nothing but the key. **BCNF** tightens this: for *every* functional dependency `A -> B` in the table, `A` must be a superkey — even if `A` itself is a non-prime (non-key) attribute. 3NF has a loophole BCNF closes: it's possible to be in 3NF while still having a determinant that isn't a candidate key.

Classic example: a university table where one professor teaches exactly one subject, but a subject can be taught by several professors.

```sql
CREATE TABLE enrollment_pre_bcnf (
    student     TEXT,
    subject     TEXT,
    professor   TEXT,
    PRIMARY KEY (student, subject)
);
INSERT INTO enrollment_pre_bcnf VALUES
    ('Alice', 'Math',    'Prof. Adams'),
    ('Bob',   'Math',    'Prof. Adams'),
    ('Alice', 'Physics', 'Prof. Bell'),
    ('Carol', 'Physics', 'Prof. Bell'),
    ('Bob',   'Physics', 'Prof. Clark');   -- a second Physics professor
```

The candidate key is `(student, subject)`. But there's also a real functional dependency `professor -> subject` (each professor teaches one subject) — and `professor` alone is *not* a superkey. That violates BCNF even though the table is already in 3NF (there's no non-key column depending on another non-key column relative to the *declared* key).

**Fix:** decompose so the `professor -> subject` dependency lives in a table where `professor` really is the key.

```sql
CREATE TABLE professor_subject (
    professor   TEXT PRIMARY KEY,
    subject     TEXT NOT NULL
);
INSERT INTO professor_subject VALUES
    ('Prof. Adams', 'Math'), ('Prof. Bell', 'Physics'), ('Prof. Clark', 'Physics');

CREATE TABLE student_professor (
    student     TEXT,
    professor   TEXT REFERENCES professor_subject(professor),
    PRIMARY KEY (student, professor)
);
INSERT INTO student_professor VALUES
    ('Alice', 'Prof. Adams'), ('Bob', 'Prof. Adams'),
    ('Alice', 'Prof. Bell'),  ('Carol', 'Prof. Bell'), ('Bob', 'Prof. Clark');
```

In an interview, BCNF rarely needs its own worked example — naming it as "3NF's stricter cousin, for the rare case where a non-key determinant hides inside an otherwise-3NF table" is normally enough. What interviewers actually probe far more is the next section.

---

## 6. When to Denormalize

Normalization optimizes for **write consistency**: one fact, one place, one `UPDATE`. That's exactly right for the transactional (OLTP) system running the actual application. It is often exactly *wrong* for an analytics warehouse, where the dominant cost is **read** performance across millions of rows, and the data is loaded once and read thousands of times.

```text
                Normalized (3NF)              Denormalized
Write speed     Fast (update one place)       Slow (update many places)
Read speed      Slower (many joins)           Fast (pre-joined)
Storage         Less redundancy               More redundancy
Data integrity  High                          Risk of inconsistency
Best for        OLTP / transactional          OLAP / analytics / DW
```

A common, concrete denormalization move: a pre-joined summary table (or materialized view) built once from the normalized tables, then read many times without paying the join cost on every query.

```sql
CREATE TABLE order_summary AS
SELECT o.order_id, o.order_date, c.customer_name, c.customer_city,
       p.product_name, p.product_price * oi.quantity AS line_total,
       s.supplier_name
FROM order_items_3nf oi
JOIN orders_3nf o    ON oi.order_id   = o.order_id
JOIN customers_2nf c ON o.customer_id = c.customer_id
JOIN products_3nf p  ON oi.product_id = p.product_id
JOIN suppliers_3nf s ON p.supplier_id = s.supplier_id;
```
**Output (first row):**
```text
(1, '2025-01-15', 'Alice', 'Portland', 'Widget', 19.98, 'Acme Corp')
```

**Rule of thumb**, and the sentence that answers "normalize or denormalize?" in an interview in one breath: **OLTP → normalize to 3NF; OLAP → denormalize for read performance.** Everything in the rest of this topic — star schemas, One Big Table, even the choice to keep something in 3NF at all — is a variation on exactly this trade-off, applied deliberately rather than by default.

---

## Key Takeaways

- Normalization eliminates redundancy by ensuring every fact lives in exactly one place, preventing insertion, update, and deletion anomalies.
- 1NF: atomic values, no repeating groups. 2NF: 1NF + no partial dependencies (relevant only with a composite key). 3NF: 2NF + no transitive dependencies (no non-key column depends on another non-key column).
- BCNF tightens 3NF: for every functional dependency `A -> B`, `A` must be a superkey — closes the rare loophole where a non-key determinant survives inside an otherwise-3NF table.
- Every step of normalization is the same move: find a functional dependency that doesn't respect the primary key, and give it its own table.
- OLTP systems normalize to 3NF for write consistency; OLAP/analytics systems deliberately denormalize for read performance — this single trade-off is the entire justification for star schemas, covered next.
