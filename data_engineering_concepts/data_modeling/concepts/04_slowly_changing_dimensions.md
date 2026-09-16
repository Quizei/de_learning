# Concept 04: Slowly Changing Dimensions (SCD Types 0, 1, 2, 3 — and 4/6)

**Covers:**
- Why dimension attributes changing over time is a real design problem, not an edge case
- Type 0 (retain original), Type 1 (overwrite), Type 2 (add new row), Type 3 (add column) — each demonstrated with before/after state
- "As of" point-in-time queries against a Type 2 dimension, including joining fact rows to the dimension row that was current *when the event happened*
- Types 4 and 6, briefly — enough to name them if asked "what else is out there"
- The one question that decides which type to use, every time

*All SQL below is real, runnable SQLite — copy any block into a `python3` shell and it runs as shown.*

---

## 0. Why This Is a Real Problem

A customer moves cities. An employee gets promoted. A product gets reclassified. The dimension row describing them needs to change — but a fact table loaded *before* that change already points at the old dimension row via a surrogate key. What happens to that fact row's meaning when the dimension changes underneath it depends entirely on which SCD strategy you picked, and picking wrong silently corrupts historical reports. This is, after grain, the second most commonly probed data-modeling topic in interviews — and the follow-up "why did you pick that type" question below is asked more often than "what are the types."

---

## 1. Type 0 — Retain Original

The attribute is loaded once and never changed again, even if the source system sends an update. Use for attributes that should be immutable by definition — a birthdate, an original signup date.

```sql
CREATE TABLE dim_customer_type0 (
    customer_key         INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id          TEXT UNIQUE,
    customer_name        TEXT,
    original_signup_date TEXT,   -- Type 0: never changes
    city                 TEXT    -- might change via Type 1 or 2 elsewhere
);
INSERT INTO dim_customer_type0 (customer_id, customer_name, original_signup_date, city)
VALUES ('C-100', 'Alice Johnson', '2020-03-15', 'Portland');
```

If the source system later sends `signup_date = '2024-01-01'` (say, from a bad backfill), the ETL simply **does not apply it** to `original_signup_date` — it's excluded from the set of columns the load process is allowed to touch, even though other columns on the same row (like `city`) update normally.

---

## 2. Type 1 — Overwrite

`UPDATE` the row in place. The previous value is gone.

**Use when:** the change is a correction (a typo fix), or historical tracking genuinely doesn't matter for that attribute, and simplicity is worth more than history.

```sql
CREATE TABLE dim_customer_type1 (
    customer_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT UNIQUE,
    customer_name   TEXT,
    city            TEXT,
    state           TEXT,
    segment         TEXT
);
INSERT INTO dim_customer_type1 (customer_id, customer_name, city, state, segment) VALUES
    ('C-100', 'Alice Johnson', 'Portland', 'OR', 'Consumer'),
    ('C-101', 'Bob Smith',     'Seattle',  'WA', 'Corporate');

-- Alice moves to Bend, OR
UPDATE dim_customer_type1 SET city = 'Bend' WHERE customer_id = 'C-100';
```
**Output:** `(1, 'C-100', 'Alice Johnson', 'Bend', 'OR', 'Consumer')` — Portland is gone forever. Any fact row already linked to `customer_key = 1` now shows Bend, **even for sales that happened while Alice actually lived in Portland.** That's the whole trade-off: simplicity, at the cost of retroactively rewriting history.

---

## 3. Type 2 — Add New Row (the gold standard)

When an attribute changes, expire the current row and insert a brand-new row with the updated value. Each row carries `effective_date`, `expiration_date`, and `is_current`. The surrogate key is unique **per version**; the natural key repeats across every version.

```sql
CREATE TABLE dim_customer_type2 (
    customer_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT NOT NULL,
    customer_name   TEXT,
    city            TEXT,
    state           TEXT,
    segment         TEXT,
    effective_date  TEXT NOT NULL,
    expiration_date TEXT NOT NULL DEFAULT '9999-12-31',
    is_current      INTEGER NOT NULL DEFAULT 1
);
INSERT INTO dim_customer_type2
    (customer_id, customer_name, city, state, segment, effective_date, expiration_date, is_current)
VALUES
    ('C-100', 'Alice Johnson', 'Portland', 'OR', 'Consumer', '2020-03-15', '9999-12-31', 1),
    ('C-101', 'Bob Smith',     'Seattle',  'WA', 'Corporate', '2019-07-01', '9999-12-31', 1);

-- Alice moves Portland -> Bend on 2025-02-01
UPDATE dim_customer_type2
SET expiration_date = '2025-02-01', is_current = 0
WHERE customer_id = 'C-100' AND is_current = 1;

INSERT INTO dim_customer_type2
    (customer_id, customer_name, city, state, segment, effective_date, expiration_date, is_current)
VALUES ('C-100', 'Alice Johnson', 'Bend', 'OR', 'Consumer', '2025-02-01', '9999-12-31', 1);
```

A second, independent change (Alice's segment changes to Corporate on `2025-06-15`) follows the identical two-step pattern — expire, then insert — and now Alice has three historical versions on file:

```text
customer_key  customer_id  city      segment    effective_date  expiration_date  is_current
1             C-100        Portland  Consumer   2020-03-15      2025-02-01       0
3             C-100        Bend      Consumer   2025-02-01      2025-06-15       0
4             C-100        Bend      Corporate  2025-06-15      9999-12-31       1
```

### "As of" queries — the entire payoff of Type 2

With Type 2, fact rows are joined against the dimension row that was current **at the time the fact happened**, not today's row:

```sql
CREATE TABLE fact_sales_scd2 (
    sale_key     INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date    TEXT,
    customer_key INTEGER REFERENCES dim_customer_type2(customer_key),
    amount       REAL
);
INSERT INTO fact_sales_scd2 (sale_date, customer_key, amount) VALUES
    ('2024-06-01', 1, 500.00),   -- Alice was in Portland (customer_key=1)
    ('2025-03-01', 3, 750.00),   -- Alice was in Bend, still Consumer (customer_key=3)
    ('2025-08-01', 4, 1200.00);  -- Alice was in Bend, now Corporate (customer_key=4)

SELECT f.sale_date, f.amount, c.city, c.segment
FROM fact_sales_scd2 f
JOIN dim_customer_type2 c ON f.customer_key = c.customer_key
WHERE c.customer_id = 'C-100'
ORDER BY f.sale_date;
```
**Output:**
```text
sale_date=2024-06-01, amount=$500.00,  city=Portland, segment=Consumer
sale_date=2025-03-01, amount=$750.00,  city=Bend,     segment=Consumer
sale_date=2025-08-01, amount=$1200.00, city=Bend,     segment=Corporate
```

A point-in-time lookup with no fact table involved at all uses the same effective/expiration window:

```sql
SELECT customer_name, city, state, segment
FROM dim_customer_type2
WHERE customer_id = 'C-100' AND effective_date <= '2024-12-01' AND expiration_date > '2024-12-01';
-- ('Alice Johnson', 'Portland', 'OR', 'Consumer')

SELECT customer_name, city, state, segment
FROM dim_customer_type2
WHERE customer_id = 'C-100' AND effective_date <= '2025-04-01' AND expiration_date > '2025-04-01';
-- ('Alice Johnson', 'Bend', 'OR', 'Consumer')
```

If `dim_customer` had instead been Type 1, every one of the three sales above would show Alice's *current* city and segment — the 2024 sale would silently show "Bend, Corporate," a fact that wasn't true when it happened. This is precisely the mechanism behind the "category rename that rewrote history" bug in `interview_questions/03_critique_and_debug.md`, Case 2.

---

## 4. Type 3 — Add a "Previous" Column

Adds a `previous_<attribute>` column, tracking exactly one prior state alongside the current one. Rarely used — mainly for "current vs. immediately prior" comparisons where the full history of Type 2 would be overkill.

```sql
CREATE TABLE dim_customer_type3 (
    customer_key      INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id       TEXT UNIQUE,
    customer_name     TEXT,
    current_city      TEXT,
    previous_city     TEXT,
    city_change_date  TEXT,
    state             TEXT,
    segment           TEXT
);
INSERT INTO dim_customer_type3
    (customer_id, customer_name, current_city, previous_city, city_change_date, state, segment)
VALUES ('C-100', 'Alice Johnson', 'Portland', NULL, NULL, 'OR', 'Consumer');

-- Alice moves Portland -> Bend
UPDATE dim_customer_type3
SET previous_city = current_city, current_city = 'Bend', city_change_date = '2025-02-01'
WHERE customer_id = 'C-100';
-- (1, 'C-100', 'Alice Johnson', 'Bend', 'Portland', '2025-02-01', 'OR', 'Consumer')

-- Alice moves again, Bend -> Eugene
UPDATE dim_customer_type3
SET previous_city = current_city, current_city = 'Eugene', city_change_date = '2025-09-01'
WHERE customer_id = 'C-100';
-- (1, 'C-100', 'Alice Johnson', 'Eugene', 'Bend', '2025-09-01', 'OR', 'Consumer')
```

**Limitation, made concrete:** after the second move, "Portland" — the *original* city — is gone entirely. Only the immediately-prior value ever survives. This is why Type 3 is rare: it looks like it's tracking history, but it's only ever tracking one step of it.

---

## 5. Types 4 and 6, Briefly

Worth naming if asked "what other SCD types are there," even though they come up far less often than 1/2/3:

- **Type 4**: keep a small "current value" dimension table for fast, everyday queries, plus a separate, larger history table that only history-aware queries pay the cost of joining against.
- **Type 6** (a "1+2+3" hybrid): structure the dimension as Type 2 rows, but *also* keep a current-value column that's kept updated across every historical row for that entity — so a single row answers both "what was true then" (via its own Type 2 attributes) and "what's true now" (via the always-current column), without a second lookup.

---

## 6. Comparison Summary

```text
+--------+--------------------+-----------------------+-------------------+
| Type   | Strategy           | History preserved?    | Complexity        |
+--------+--------------------+-----------------------+-------------------+
| 0      | Retain original    | N/A (never changes)   | Minimal           |
| 1      | Overwrite          | No                    | Simple            |
| 2      | Add new row        | Full history          | Moderate          |
| 3      | Add prev. column   | One prior value only  | Low               |
+--------+--------------------+-----------------------+-------------------+
```

**ETL pattern for Type 2, stated as an algorithm** (this is worth being able to say out loud verbatim):
1. Look up the existing current row for the natural key.
2. Compare tracked attributes against the incoming values.
3. If changed: expire the current row (`expiration_date`, `is_current = 0`), then insert a new row (`effective_date = today`, `is_current = 1`).
4. If unchanged: do nothing (or apply any Type 1 attributes on the same row in place).

Most real dimensions are **hybrid**: some columns Type 1 (name corrections, email), some Type 2 (city, loyalty tier), one or two Type 0 (original signup date) — all living on the same physical table, each column governed by its own rule.

---

## 7. The One Question That Decides Which Type to Use

Every SCD-type decision — in every worked scenario in `interview_questions/01_worked_scenarios.md`, and every critique case in `interview_questions/03_critique_and_debug.md` — reduces to one question, asked about the *specific* value that changed:

> **Was the old value ever actually true, or was it simply wrong?**

- If it was true at the time (a real move, a real promotion, a real re-categorization) → **Type 2**. Overwriting it would retroactively misattribute real historical facts.
- If it was just wrong (a typo, a data-entry error, a miscategorization that was never correct) → **Type 1**. Preserving the wrong value as "history" would be preserving a bug, not a fact.

This is a sharper, more reliable rule than pattern-matching on the column name — the *same* column (`category`, `city`, `cuisine_type`) can legitimately be Type 1 in one scenario and Type 2 in another, depending on why it changed. Interviewers who ask a curveball here are listening for exactly this reasoning, not a memorized table of column names.

---

## Key Takeaways

- Type 0: never changes after initial load (birthdate). Type 1: overwrite in place, no history — correct for fixing an error. Type 2: insert a new row with `effective_date`/`expiration_date`/`is_current` — correct for a real change that historical reports must reflect. Type 3: one extra "previous value" column, rarely used, loses everything before the immediately-prior state.
- Type 2 is what makes "as of" queries possible at all — a fact row's surrogate key points at the dimension version that was true when the fact happened, not today's version.
- Types 4 and 6 exist (separate current/history tables; a Type 2 row that also carries an always-current column) — worth naming, rarely worth building from scratch in an interview answer.
- Most production dimensions are hybrid: different columns on the same table, each governed by a different SCD type.
- The deciding question is always "was the old value ever true, or was it just wrong" — Type 2 for the former, Type 1 for the latter — never decide from the column name alone.
