# Concept 03: Star Schema vs. Snowflake Schema

**Covers:**
- Star schema: denormalized (flat) dimensions, fewer joins
- Snowflake schema: normalized dimensions, more joins, less redundancy
- Building the *same* e-commerce business case both ways, loading identical data, and running the same queries against both
- The concrete query-complexity difference (2 joins vs. 5 joins for the same question)
- When snowflaking actually earns its keep

*All SQL below is real, runnable SQLite — copy any block into a `python3` shell and it runs as shown.*

---

## 1. The Same Business Case, Two Ways

Both schemas put fact tables in the center with dimension tables radiating outward. The difference is entirely in how the *dimensions* are structured.

- **Star schema**: each dimension is one denormalized, wide table. Category and subcategory get flattened directly into `dim_product`; region and state get flattened directly into `dim_customer`.
- **Snowflake schema**: each dimension is broken into a chain of normalized sub-tables — `dim_product -> dim_subcategory -> dim_category`, `dim_customer -> dim_state -> dim_region`.

Both are built here from identical source data:

```sql
-- shared source data
CATEGORIES     = [('CAT-1','Electronics'), ('CAT-2','Furniture')]
SUBCATEGORIES  = [('SCAT-1','CAT-1','Computers'), ('SCAT-2','CAT-1','Peripherals'),
                   ('SCAT-3','CAT-2','Desks'),     ('SCAT-4','CAT-2','Chairs')]
PRODUCTS       = [('SKU-001','Laptop Pro 15','SCAT-1',899.00), ('SKU-002','Wireless Mouse','SCAT-2',25.00),
                   ('SKU-003','Standing Desk','SCAT-3',450.00), ('SKU-004','Ergo Chair','SCAT-4',350.00)]
REGIONS        = [('R-W','West'), ('R-S','South'), ('R-M','Midwest')]
STATES         = [('OR','R-W','Oregon'), ('WA','R-W','Washington'),
                   ('TX','R-S','Texas'), ('IL','R-M','Illinois')]
CUSTOMERS      = [('C-100','Alice Johnson','Consumer','Portland','OR'),
                   ('C-101','Bob Smith','Corporate','Seattle','WA'),
                   ('C-102','Carol Davis','Consumer','Austin','TX'),
                   ('C-103','DataTech Inc.','Corporate','Chicago','IL')]
```

### Star schema build

```sql
CREATE TABLE dim_product_star (
    product_key     INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      TEXT UNIQUE,
    product_name    TEXT,
    subcategory_id  TEXT,
    subcategory     TEXT,
    category_id     TEXT,
    category        TEXT,
    unit_price      REAL
);
-- category + subcategory baked directly into every product row:
-- (1, 'SKU-001', 'Laptop Pro 15', 'SCAT-1', 'Computers', 'CAT-1', 'Electronics', 899.0)

CREATE TABLE dim_customer_star (
    customer_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT UNIQUE,
    customer_name   TEXT,
    segment         TEXT,
    city            TEXT,
    state_code      TEXT,
    state_name      TEXT,
    region_id       TEXT,
    region_name     TEXT
);
-- region + state baked directly into every customer row

CREATE TABLE fact_sales_star (
    sale_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key        INTEGER,
    product_key     INTEGER REFERENCES dim_product_star(product_key),
    customer_key    INTEGER REFERENCES dim_customer_star(customer_key),
    quantity        INTEGER,
    unit_price      REAL,
    line_total      REAL
);
```

### Snowflake schema build

```sql
CREATE TABLE dim_category_snow (category_id TEXT PRIMARY KEY, category_name TEXT);

CREATE TABLE dim_subcategory_snow (
    subcategory_id   TEXT PRIMARY KEY,
    category_id      TEXT REFERENCES dim_category_snow(category_id),
    subcategory_name TEXT
);

CREATE TABLE dim_product_snow (
    product_key     INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      TEXT UNIQUE,
    product_name    TEXT,
    subcategory_id  TEXT REFERENCES dim_subcategory_snow(subcategory_id),
    unit_price      REAL
);

CREATE TABLE dim_region_snow (region_id TEXT PRIMARY KEY, region_name TEXT);

CREATE TABLE dim_state_snow (
    state_code  TEXT PRIMARY KEY,
    region_id   TEXT REFERENCES dim_region_snow(region_id),
    state_name  TEXT
);

CREATE TABLE dim_customer_snow (
    customer_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT UNIQUE,
    customer_name   TEXT,
    segment         TEXT,
    city            TEXT,
    state_code      TEXT REFERENCES dim_state_snow(state_code)
);

CREATE TABLE fact_sales_snow (
    sale_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key        INTEGER,
    product_key     INTEGER REFERENCES dim_product_snow(product_key),
    customer_key    INTEGER REFERENCES dim_customer_snow(customer_key),
    quantity        INTEGER,
    unit_price      REAL,
    line_total      REAL
);
```

```text
Star:                                 Snowflake:

  dim_product_star                    dim_category_snow
       |                                     |
       |                              dim_subcategory_snow
       |                                     |
  fact_sales_star -- dim_customer_star  dim_product_snow
                                             |
                                        fact_sales_snow -- dim_customer_snow
                                                                 |
                                                           dim_state_snow
                                                                 |
                                                           dim_region_snow
```

---

## 2. Same Question, Two Query Shapes

**Question:** "Total revenue by product category and customer region."

**Star schema — 2 joins:**
```sql
SELECT p.category, c.region_name, SUM(f.line_total) AS revenue
FROM fact_sales_star f
JOIN dim_product_star  p ON f.product_key  = p.product_key
JOIN dim_customer_star c ON f.customer_key = c.customer_key
GROUP BY p.category, c.region_name
ORDER BY revenue DESC;
```

**Snowflake schema — 5 joins, walking every hierarchy level:**
```sql
SELECT cat.category_name, reg.region_name, SUM(f.line_total) AS revenue
FROM fact_sales_snow f
JOIN dim_product_snow     p   ON f.product_key    = p.product_key
JOIN dim_subcategory_snow sc  ON p.subcategory_id = sc.subcategory_id
JOIN dim_category_snow    cat ON sc.category_id   = cat.category_id
JOIN dim_customer_snow    c   ON f.customer_key   = c.customer_key
JOIN dim_state_snow       st  ON c.state_code     = st.state_code
JOIN dim_region_snow      reg ON st.region_id     = reg.region_id
GROUP BY cat.category_name, reg.region_name
ORDER BY revenue DESC;
```

Both return **exactly the same result set** — `('Electronics', 'Midwest', 2697.0)`, etc. — the difference is entirely in how many tables you had to touch to get there.

Even a *simpler* question shows the same gap. "Revenue by subcategory" is 1 join in the star schema, 2 joins in the snowflake (you still have to walk from product to subcategory even though you never touch category at all):

```sql
-- Star (1 JOIN)
SELECT p.subcategory, SUM(f.line_total) AS revenue
FROM fact_sales_star f
JOIN dim_product_star p ON f.product_key = p.product_key
GROUP BY p.subcategory ORDER BY revenue DESC;

-- Snowflake (2 JOINs)
SELECT sc.subcategory_name, SUM(f.line_total) AS revenue
FROM fact_sales_snow f
JOIN dim_product_snow     p  ON f.product_key    = p.product_key
JOIN dim_subcategory_snow sc ON p.subcategory_id = sc.subcategory_id
GROUP BY sc.subcategory_name ORDER BY revenue DESC;
```

---

## 3. Comparison Summary

```text
+-------------------+------------------------------+------------------------------+
| Aspect            | Star Schema                  | Snowflake Schema             |
+-------------------+------------------------------+------------------------------+
| Dimension design  | Denormalized (flat)          | Normalized (sub-tables)      |
| Number of tables  | Fewer                        | More                         |
| Query complexity  | Simpler (fewer JOINs)        | More JOINs needed            |
| Query performance | Generally faster             | More joins = more overhead   |
| Storage           | More redundant data          | Less redundancy              |
| ETL complexity    | Simpler loads                | More complex loads            |
| BI tool support   | Excellent (industry default) | Good, but more setup         |
| Best for          | Analytics, dashboards, OLAP  | When storage is critical     |
+-------------------+------------------------------+------------------------------+
```

**Industry practice:** star schema is the default choice for a data warehouse — it's what Kimball methodology assumes and what every mainstream BI tool is optimized to query. Snowflake schema earns its keep specifically when a dimension's hierarchy is **large, deep, and frequently queried at an intermediate level on its own** — a 50,000-SKU product catalog where category-level reporting is common, for instance, where flattening the whole hierarchy into every product row would mean updating tens of thousands of rows every time a category gets renamed. Many real warehouses are **hybrid**: mostly star, with the one or two dimensions that are genuinely huge and hierarchical snowflaked deliberately, while everything else stays flat.

The interview framing that matters more than the trade-off table: don't just recite "star is simpler, snowflake saves storage" — say *why* a specific dimension in front of you would or wouldn't benefit. A three-level location hierarchy (zone → city → market) with a few hundred rows total costs nothing to flatten and saves every analyst a join forever. A 70,000-row diagnosis-code hierarchy (see `interview_questions/01_worked_scenarios.md`'s healthcare scenario) is the opposite case.

---

## Key Takeaways

- Star and snowflake schemas share the same fact-table-in-the-center structure; they differ only in whether dimension hierarchies are flattened (star) or normalized into sub-tables (snowflake).
- The same query against a star schema needs fewer joins than the identical query against an equivalent snowflake schema — the difference grows with how many hierarchy levels the question needs to walk.
- Star is the default for analytics/BI because of simpler queries and better tool support; snowflake is worth it specifically when a dimension is large, deep, and often queried at an intermediate level in isolation.
- Most real warehouses are hybrid — star by default, snowflaking only the specific dimensions where the trade-off clearly wins.
- Justify the choice for the dimension in front of you, not from a memorized rule — that's what separates a strong answer from a recited one.
