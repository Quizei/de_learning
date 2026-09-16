# Data Modeling — Practice Exercises

Fifteen exercises covering: normalization (identify violations, decompose to 2NF/3NF), fact vs. dimension identification, fact table type classification, star schema design and querying, SCD Types 1/2/hybrid, and — extending past the original set — bridge tables for many-to-many relationships, non-additive/semi-additive measure bugs, and One Big Table vs. star schema trade-offs.

How to use this file: read the exercise, write down your own answer — genuinely commit to one before looking — and only then expand the reference solution to check yourself. Each solution includes working SQLite code where relevant, exactly as it would run in a `python3` shell with the `sqlite3` module.

---

## Exercise 1: Identify the Normal Form Violation

```text
student_courses
+-----------+--------------+--------------------+
| student_id| student_name | courses            |
+-----------+--------------+--------------------+
| 1         | Alice        | Math, Physics      |
| 2         | Bob          | Chemistry          |
| 3         | Carol        | Math, CS, Biology  |
+-----------+--------------+--------------------+
```

**Your task:** which normal form is violated, and how would you fix it?

<details>
<summary>Reference answer</summary>

**Violation: 1NF.** The `courses` column holds a comma-separated list — not an atomic value, and effectively a repeating group in one cell.

**Fix:** split into one row per (student, course) pair via a junction table.

```sql
CREATE TABLE students (student_id INTEGER PRIMARY KEY, student_name TEXT);
CREATE TABLE student_courses (student_id INTEGER, course TEXT, PRIMARY KEY (student_id, course));

INSERT INTO students VALUES (1,'Alice'), (2,'Bob'), (3,'Carol');
INSERT INTO student_courses VALUES
    (1,'Math'), (1,'Physics'), (2,'Chemistry'), (3,'Math'), (3,'CS'), (3,'Biology');
```

*(See `concepts/01_normalization.md`, section 2.)*

</details>

---

## Exercise 2: Normalize to 2NF

```text
order_products   PK: (order_id, product_id)
+----------+------------+-----------+----------+---------------+
| order_id | product_id | order_date| prod_name| prod_category |
+----------+------------+-----------+----------+---------------+
| 1        | P1         | 2025-01-01| Widget   | Electronics   |
| 1        | P2         | 2025-01-01| Gadget   | Electronics   |
| 2        | P1         | 2025-01-02| Widget   | Electronics   |
+----------+------------+-----------+----------+---------------+
```

**Your task:** identify the partial dependencies and decompose into 2NF.

<details>
<summary>Reference answer</summary>

Composite PK is `(order_id, product_id)`.

- `order_date` depends only on `order_id` → partial dependency.
- `prod_name`, `prod_category` depend only on `product_id` → partial dependency.

```sql
CREATE TABLE orders (order_id INTEGER PRIMARY KEY, order_date TEXT);
CREATE TABLE products (product_id TEXT PRIMARY KEY, prod_name TEXT, prod_category TEXT);
CREATE TABLE order_products (order_id INTEGER, product_id TEXT, PRIMARY KEY (order_id, product_id));

INSERT INTO orders VALUES (1,'2025-01-01'), (2,'2025-01-02');
INSERT INTO products VALUES ('P1','Widget','Electronics'), ('P2','Gadget','Electronics');
INSERT INTO order_products VALUES (1,'P1'), (1,'P2'), (2,'P1');
```

*(See `concepts/01_normalization.md`, section 3.)*

</details>

---

## Exercise 3: Normalize to 3NF

```text
employees (already 2NF)     PK: emp_id
+--------+-------+-------------+-----------+
| emp_id | name  | dept_id     | dept_name |
+--------+-------+-------------+-----------+
| 1      | Alice | D10         | Marketing |
| 2      | Bob   | D20         | Sales     |
| 3      | Carol | D10         | Marketing |
+--------+-------+-------------+-----------+
```

**Your task:** identify the transitive dependency and decompose into 3NF.

<details>
<summary>Reference answer</summary>

Transitive dependency: `emp_id -> dept_id -> dept_name` — `dept_name` depends on `dept_id`, a non-key column, not directly on `emp_id`.

```sql
CREATE TABLE departments (dept_id TEXT PRIMARY KEY, dept_name TEXT);
CREATE TABLE employees (emp_id INTEGER PRIMARY KEY, name TEXT, dept_id TEXT REFERENCES departments(dept_id));

INSERT INTO departments VALUES ('D10','Marketing'), ('D20','Sales');
INSERT INTO employees VALUES (1,'Alice','D10'), (2,'Bob','D20'), (3,'Carol','D10');
```

*(See `concepts/01_normalization.md`, section 4.)*

</details>

---

## Exercise 4: Fact vs. Dimension Identification

A hospital system tracks patient visits. Classify each as **FACT** or **DIMENSION**:

```text
a) Patient   (patient_id, name, date_of_birth, blood_type)
b) Doctor    (doctor_id, name, specialty, department)
c) Visit     (visit_id, patient_id, doctor_id, visit_date,
              diagnosis_code, treatment_cost, duration_minutes)
d) Diagnosis (diagnosis_code, description, category)
e) Date      (date_key, full_date, day_of_week, month, quarter, year)
```

For the fact table, name the grain, dimensions, and measures.

<details>
<summary>Reference answer</summary>

```text
a) Patient    -> DIMENSION (descriptive, who)
b) Doctor     -> DIMENSION (descriptive, who)
c) Visit      -> FACT      (event with measures)
d) Diagnosis  -> DIMENSION (descriptive, what)
e) Date       -> DIMENSION (descriptive, when)
```

**`fact_visit`** — Grain: one row per patient visit. Dimensions: patient, doctor, diagnosis, date. Measures: `treatment_cost` (additive), `duration_minutes` (additive, though usually reported as an average).

*(See `concepts/02_dimensional_modeling.md`, section 1.)*

</details>

---

## Exercise 5: Identify Fact Table Type

Classify each as **Transaction**, **Periodic Snapshot**, or **Accumulating Snapshot**:

```text
a) Every ATM withdrawal, with timestamp and amount.
b) One row per student per semester, cumulative GPA.
c) A loan application tracked through stages: applied, reviewed,
   approved, funded — with a date for each milestone.
d) Daily closing stock prices per ticker symbol.
e) Every web page click, with user_id and timestamp.
```

<details>
<summary>Reference answer</summary>

```text
a) ATM withdrawals           -> TRANSACTION FACT (one row per discrete event)
b) Student GPA per semester  -> PERIODIC SNAPSHOT (one row per entity per period)
c) Loan application stages   -> ACCUMULATING SNAPSHOT (one row per process, updated at each milestone)
d) Daily stock prices        -> PERIODIC SNAPSHOT (one row per ticker per day)
e) Web page clicks           -> TRANSACTION FACT (one row per discrete event)
```

*(See `concepts/02_dimensional_modeling.md`, section 3.)*

</details>

---

## Exercise 6: Design a Star Schema

A university wants to analyze course enrollment:
- How many students enrolled per department per semester?
- What is the average class size by instructor?
- Which courses have the highest drop rates?

**Your task:** (1) state the grain, (2) list dimensions with key attributes, (3) list fact table columns (FKs + measures), then implement it.

<details>
<summary>Reference answer</summary>

**Grain:** one row per student per course per semester.

```sql
CREATE TABLE dim_student (
    student_key INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE, name TEXT, major TEXT, class_year INTEGER
);
CREATE TABLE dim_course (
    course_key INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id TEXT UNIQUE, course_name TEXT, department TEXT, credits INTEGER
);
CREATE TABLE dim_instructor (
    instructor_key INTEGER PRIMARY KEY AUTOINCREMENT,
    instructor_id TEXT UNIQUE, name TEXT, department TEXT, rank TEXT
);
CREATE TABLE dim_semester (
    semester_key INTEGER PRIMARY KEY AUTOINCREMENT,
    semester_id TEXT UNIQUE, term TEXT, year INTEGER
);
CREATE TABLE fact_enrollment (
    enrollment_key INTEGER PRIMARY KEY AUTOINCREMENT,
    student_key INTEGER REFERENCES dim_student(student_key),
    course_key INTEGER REFERENCES dim_course(course_key),
    instructor_key INTEGER REFERENCES dim_instructor(instructor_key),
    semester_key INTEGER REFERENCES dim_semester(semester_key),
    enrollment_status TEXT,  -- Enrolled, Completed, Dropped
    credits INTEGER
);
```

Loaded with a handful of students/courses/instructors across two semesters, this is enough to answer all three business questions in Exercise 7.

*(See `concepts/02_dimensional_modeling.md`, section 3.)*

</details>

---

## Exercise 7: Star Schema Query Challenge

Using the schema from Exercise 6, write queries for:
a) Total credits enrolled per department for Fall 2024.
b) Number of students per instructor, sorted descending.
c) Drop rate (% of enrollments with `status='Dropped'`) per course.

<details>
<summary>Reference answer</summary>

```sql
-- a) Total credits per department, Fall 2024
SELECT c.department, SUM(f.credits) AS total_credits
FROM fact_enrollment f
JOIN dim_course c ON f.course_key = c.course_key
JOIN dim_semester s ON f.semester_key = s.semester_key
WHERE s.semester_id = 'F24'
GROUP BY c.department;

-- b) Students per instructor
SELECT i.name, COUNT(DISTINCT f.student_key) AS num_students
FROM fact_enrollment f
JOIN dim_instructor i ON f.instructor_key = i.instructor_key
GROUP BY i.name ORDER BY num_students DESC;

-- c) Drop rate per course
SELECT c.course_name,
       ROUND(100.0 * SUM(CASE WHEN f.enrollment_status='Dropped' THEN 1 ELSE 0 END)
             / COUNT(*), 1) AS drop_pct
FROM fact_enrollment f
JOIN dim_course c ON f.course_key = c.course_key
GROUP BY c.course_name;
```

</details>

---

## Exercise 8: Implement SCD Type 1

An employee dimension: `emp_key, emp_id, name, department, salary`. Employee `E-100` (John, Marketing, 75000) transfers to Sales.

**Your task:** implement the Type 1 update, then explain what happens to historical reports.

<details>
<summary>Reference answer</summary>

```sql
CREATE TABLE dim_employee (
    emp_key INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id TEXT UNIQUE, name TEXT, department TEXT, salary REAL
);
INSERT INTO dim_employee (emp_id,name,department,salary) VALUES ('E-100','John','Marketing',75000);

-- BEFORE: (1, 'E-100', 'John', 'Marketing', 75000)
UPDATE dim_employee SET department='Sales' WHERE emp_id='E-100';
-- AFTER:  (1, 'E-100', 'John', 'Sales', 75000)
```

**Impact:** every historical fact row referencing `emp_key = 1` now shows John in Sales — including facts from when he was genuinely in Marketing. That's the defining trade-off of Type 1: correct going forward, retroactively wrong for anything that happened before the change, if the change was real rather than a correction. *(See `concepts/04_slowly_changing_dimensions.md`, section 2.)*

</details>

---

## Exercise 9: Implement SCD Type 2

A product dimension: `product_key, product_id, name, category, price, effective_date, expiration_date, is_current`. Product `P-500` (Headphones, Electronics, $79.99) is repriced to $99.99 on `2025-07-01`.

**Your task:** implement the Type 2 change, then find the price as of `2025-05-01` and as of `2025-08-01`.

<details>
<summary>Reference answer</summary>

```sql
CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT, name TEXT, category TEXT, price REAL,
    effective_date TEXT, expiration_date TEXT DEFAULT '9999-12-31', is_current INTEGER DEFAULT 1
);
INSERT INTO dim_product (product_id,name,category,price,effective_date)
VALUES ('P-500','Headphones','Electronics',79.99,'2024-01-01');

UPDATE dim_product SET expiration_date='2025-07-01', is_current=0
WHERE product_id='P-500' AND is_current=1;

INSERT INTO dim_product (product_id,name,category,price,effective_date)
VALUES ('P-500','Headphones','Electronics',99.99,'2025-07-01');

-- Price as of 2025-05-01:
SELECT price FROM dim_product
WHERE product_id='P-500' AND effective_date <= '2025-05-01' AND expiration_date > '2025-05-01';
-- $79.99

-- Price as of 2025-08-01:
SELECT price FROM dim_product
WHERE product_id='P-500' AND effective_date <= '2025-08-01' AND expiration_date > '2025-08-01';
-- $99.99
```

</details>

---

## Exercise 10: Hybrid SCD Design

Design a customer dimension where `customer_name` and `email` are Type 1, `city`/`state`/`loyalty_tier` are Type 2, and `original_signup_date` is Type 0. Simulate: (1) a name correction "Jon" → "John", (2) a city change "Portland" → "Bend".

<details>
<summary>Reference answer</summary>

```sql
CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    customer_name TEXT,          -- Type 1
    email TEXT,                  -- Type 1
    city TEXT,                   -- Type 2
    state TEXT,                  -- Type 2
    loyalty_tier TEXT,           -- Type 2
    original_signup_date TEXT,   -- Type 0
    effective_date TEXT NOT NULL,
    expiration_date TEXT NOT NULL DEFAULT '9999-12-31',
    is_current INTEGER NOT NULL DEFAULT 1
);
INSERT INTO dim_customer
    (customer_id,customer_name,email,city,state,loyalty_tier,original_signup_date,effective_date)
VALUES ('C-200','Jon','jon@mail.com','Portland','OR','Silver','2022-05-10','2022-05-10');

-- Step 1: Type 1 correction -- overwrites ALL rows for this customer, no new row
UPDATE dim_customer SET customer_name='John' WHERE customer_id='C-200';

-- Step 2: Type 2 change -- expire current row, insert a new one
UPDATE dim_customer SET expiration_date='2025-03-01', is_current=0
WHERE customer_id='C-200' AND is_current=1;

INSERT INTO dim_customer
    (customer_id,customer_name,email,city,state,loyalty_tier,original_signup_date,effective_date)
VALUES ('C-200','John','jon@mail.com','Bend','OR','Silver','2022-05-10','2025-03-01');
```

Both rows now show `'John'` (the Type 1 fix applies retroactively, since it's a correction), but the city history is preserved across two rows (Type 2), and `original_signup_date` is identical on both (Type 0, untouched). *(See `concepts/04_slowly_changing_dimensions.md`, sections 1-3 and 7.)*

</details>

---

## Exercise 11: Fix the Non-Additive Measure Bug

A `fact_order_lines` table stores `discount_percent` (e.g. `0.15` for 15% off) instead of a dollar discount. An analyst runs `SUM(discount_percent)` grouped by region to find "total discount given" and gets a number that means nothing (summed percentages, not summed dollars).

**Your task:** diagnose the modeling mistake and fix the schema, not just the query.

<details>
<summary>Reference answer</summary>

**Diagnosis:** `discount_percent` is a **non-additive** measure — a ratio only makes sense evaluated per-row or averaged, never summed. Summing percentages across rows produces a number with no business meaning, the same failure mode as summing `surge_multiplier` in `interview_questions/01_worked_scenarios.md`.

**Fix:** store `discount_amount` (a dollar figure, computed at load time as `unit_price * quantity * discount_percent` if the source only provides the percent) instead of, or alongside, the percent. `discount_amount` is additive — `SUM(discount_amount)` grouped by region is now a meaningful, correct "total discount given." If the percent is still needed for display, derive it at query time (`discount_amount / line_total`) rather than storing it as the thing that gets summed.

```sql
-- WRONG: discount_percent can't be summed meaningfully
SELECT region, SUM(discount_percent) FROM fact_order_lines GROUP BY region;  -- meaningless

-- RIGHT: store and sum the dollar amount
SELECT region, SUM(discount_amount) FROM fact_order_lines GROUP BY region;  -- correct
```

*(See `concepts/02_dimensional_modeling.md` and `interview_questions/02_rapid_fire_qna.md`, "Fact Table Types & Measures.")*

</details>

---

## Exercise 12: Design and Query a Bridge Table

A product can belong to more than one category (e.g. "Running Shoes" sits under both "Footwear" and "Sale Items"). `fact_order_lines` has one row per product line item per order.

**Your task:** design the schema so a product can have multiple categories without breaking `dim_product`'s grain, then write the query for "revenue by category, last month" and state one consequence of the design out loud.

<details>
<summary>Reference answer</summary>

```sql
CREATE TABLE dim_product (product_key INTEGER PRIMARY KEY, product_name TEXT);
CREATE TABLE dim_category (category_key INTEGER PRIMARY KEY, category_name TEXT);
CREATE TABLE bridge_product_category (
    product_key INTEGER REFERENCES dim_product(product_key),
    category_key INTEGER REFERENCES dim_category(category_key),
    PRIMARY KEY (product_key, category_key)
);
-- one row per (product, category) pairing -- a product in 2 categories = 2 rows here

SELECT cat.category_name, SUM(f.line_total) AS revenue
FROM fact_order_lines f
JOIN bridge_product_category bpc ON f.product_key = bpc.product_key
JOIN dim_category cat ON bpc.category_key = cat.category_key
JOIN dim_date d ON f.date_key = d.date_key
WHERE d.month = '2025-08'
GROUP BY cat.category_name;
```

**Consequence to flag out loud:** because of the bridge table, a single order line now contributes to *every* category its product belongs to — so summing "revenue by category" across all categories will legitimately exceed total company revenue. That's expected, correct behavior for a many-to-many rollup, not a bug — see Case 4 in `interview_questions/03_critique_and_debug.md` for the full stakeholder-panic version of this exact scenario.

</details>

---

## Exercise 13: Semi-Additive Measure Query Challenge

`fact_account_balance_daily` holds one row per account per day with a `balance` column (a snapshot, not a transaction). Write the correct query for "total balance across all accounts, as of yesterday," and separately explain why `SUM(balance)` grouped by account and then summed *across days* would be wrong.

<details>
<summary>Reference answer</summary>

```sql
-- CORRECT: sum across accounts, within ONE day
SELECT SUM(balance) AS total_balance
FROM fact_account_balance_daily
WHERE snapshot_date = DATE('now', '-1 day');
```

Summing `balance` **across accounts for one day** is correct — it's a real total, the sum of everyone's balance at one moment. Summing `balance` **across days for one account** (e.g. `SUM(balance)` over a month for one account) is meaningless: each day's row is a frozen point-in-time measurement of the same underlying quantity, not a new transaction — adding twenty-eight snapshots of "how much money is in this account" together doesn't produce a real-world number. This is the semi-additive rule from `concepts/02_dimensional_modeling.md`, section 3, and the exact bug pattern in Case 5 of `interview_questions/03_critique_and_debug.md` ("annual revenue off by 12x").

</details>

---

## Exercise 14: One Big Table vs. Star Schema

A BI team wants a single Looker/Tableau-friendly table with no joins for their `orders` dashboard. A separate data science team wants `dim_customer` centralized and consistent across `fact_orders`, `fact_returns`, and `fact_support_tickets`.

**Your task:** decide, for each team, whether OBT or a star schema is the right call, and justify it in one sentence each.

<details>
<summary>Reference answer</summary>

**BI team → OBT**, scoped to their one dashboard: pre-join `fact_orders` with all its dimensions into a single wide table so their tool needs zero joins, accepting the update cost and redundancy as worth it for a single, self-service consumer.

**Data science team → star schema with a conformed `dim_customer`**: because *three* fact tables need to agree on what a customer is, centralizing `dim_customer` once and referencing it from all three keeps "customer segment" meaning the same thing everywhere; building three separate OBTs would duplicate that dimension's logic three times and risk them quietly drifting apart.

The general rule: OBT is a valid, deliberate choice for a single fact/single consumer; a star schema wins the moment more than one fact table needs the same dimension to mean the same thing. *(See `concepts/05_one_big_table_and_lakehouse_modeling.md`, section 5.)*

</details>

---

## Exercise 15: Data Vault Mini-Design

A company is bringing on a third CRM system that has its own definition of "customer," in addition to two existing systems that already disagree with each other. Business rules for reconciling all three into one canonical customer aren't finalized yet, but loads from all three need to start immediately.

**Your task:** sketch a hub/link/satellite design that lets loading start today without waiting on the reconciliation rules, and say what happens once those rules are finalized.

<details>
<summary>Reference answer</summary>

```sql
CREATE TABLE hub_customer (
    customer_hub_key TEXT PRIMARY KEY,  -- hash of business key + source, since sources disagree
    customer_id TEXT NOT NULL,
    load_date TEXT NOT NULL,
    record_source TEXT NOT NULL          -- 'CRM_A', 'CRM_B', 'CRM_C'
);

CREATE TABLE sat_customer_details (
    customer_hub_key TEXT REFERENCES hub_customer(customer_hub_key),
    load_date TEXT NOT NULL,
    record_source TEXT NOT NULL,
    customer_name TEXT, email TEXT, city TEXT,
    PRIMARY KEY (customer_hub_key, load_date)
);
```

Each of the three CRMs loads its own hub rows and satellite rows independently and in parallel — nobody needs to wait on anybody else, and nothing needs to agree on a single "true" customer record yet. Once the reconciliation rules ARE finalized, a separate transformation step builds a conformed `dim_customer` (Kimball star schema layer) *on top of* the vault, applying the agreed matching logic to collapse the three sources' hub rows into one canonical customer per real-world person — without ever having blocked the original loads on that agreement. *(See `concepts/06_data_vault_modeling.md`, sections 3-4.)*

</details>
