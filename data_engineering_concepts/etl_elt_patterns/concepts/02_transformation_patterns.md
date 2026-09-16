# Concept 02: Transformation Patterns

**Covers:**
- Data cleaning: nulls, whitespace, type casting
- Deduplication: exact match, key-based ("keep the latest"), and fuzzy matching
- Enrichment: joining reference/lookup data to add business context
- Derived/computed columns
- Standardization: dates, phone numbers, addresses
- Validation during transform, and routing bad records instead of crashing
- Chaining transform steps into a pipeline

*All Python below is real, runnable stdlib — copy any block into a `python3` shell and it runs as shown.*

---

## 1. Data Cleaning: The Unavoidable First Step

Real source data is never clean. Every transformation stage starts here: trim whitespace, normalize null-like values (`""`, `"null"`, `"N/A"` are all "no value", not three different values), and cast types explicitly rather than trusting the source's.

```python
raw_rows = [
    {"id": "1", "name": "  Alice  ", "age": "30"},
    {"id": "2", "name": "Bob",        "age": ""},
    {"id": "3", "name": " Charlie ",  "age": "null"},
]

def clean_string(val):
    if val is None:
        return None
    val = val.strip()
    return None if val == "" or val.lower() == "null" else val

def safe_int(val, default=None):
    cleaned = clean_string(val)
    if cleaned is None:
        return default
    try:
        return int(cleaned)
    except ValueError:
        return default

cleaned = [
    {"id": int(r["id"]), "name": clean_string(r["name"]) or "UNKNOWN", "age": safe_int(r["age"])}
    for r in raw_rows
]
print(cleaned)
# [{'id': 1, 'name': 'Alice', 'age': 30}, {'id': 2, 'name': 'Bob', 'age': None}, {'id': 3, 'name': 'Charlie', 'age': None}]
```

Row 2's empty string and row 3's literal `"null"` both correctly become Python `None` — a cleaning function that only checks `if val is None` would miss both, and the resulting warehouse column would silently mix three different spellings of "missing" as if they were meaningfully different values.

## 2. Deduplication: Three Different Problems Wearing One Name

"Deduplicate this" is underspecified until you know *which* kind of duplicate you're removing.

**Exact-match dedup** — identical rows, safe to collapse with no judgment call:

```python
rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, {"id": 1, "name": "Alice"}]
seen, deduped = set(), []
for r in rows:
    key = tuple(sorted(r.items()))
    if key not in seen:
        seen.add(key)
        deduped.append(r)
print(f"{len(rows)} -> {len(deduped)}")   # 3 -> 2
```

**Key-based dedup ("keep the latest")** — several *different* versions of the same business entity arrived; you need a rule for which one wins, not just "are they identical":

```python
events = [
    {"user_id": 1, "ts": "2024-01-01T10:00:00"},
    {"user_id": 1, "ts": "2024-01-01T10:05:00"},   # later — should win
    {"user_id": 2, "ts": "2024-01-01T09:00:00"},
]
latest = {}
for e in events:
    uid = e["user_id"]
    if uid not in latest or e["ts"] > latest[uid]["ts"]:
        latest[uid] = e
print({uid: e["ts"] for uid, e in latest.items()})
# {1: '2024-01-01T10:05:00', 2: '2024-01-01T09:00:00'}
```

**Fuzzy dedup** — the records aren't identical and don't share a clean key, but they plausibly describe the same real-world entity ("John Smith" / "Jon Smith" / "John Smyth"). This needs a similarity function and a clustering step, not just a dict lookup — worked in full, with a runnable Jaccard-similarity + union-find implementation, in `practice/coding_problems.md`, Problem 2.

A cheap middle ground — normalizing case/whitespace before comparing — catches a large share of real-world "duplicates" without needing fuzzy matching at all:

```python
names = ["Alice Smith", "alice smith", "ALICE  SMITH", "Bob Jones"]
def normalize(n): return " ".join(n.lower().split())
unique = {}
for n in names:
    unique.setdefault(normalize(n), n)
print(list(unique.values()))
# ['Alice Smith', 'Bob Jones']
```

## 3. Enrichment: Joining in Business Context

Enrichment adds context the raw record didn't carry on its own — usually by joining against a reference/lookup table:

```python
orders = [
    {"order_id": 101, "customer_id": 1, "amount": 299.99},
    {"order_id": 102, "customer_id": 99, "amount": 10.00},   # customer_id not in lookup
]
customers = {1: {"name": "Alice", "tier": "gold"}}

enriched = []
for o in orders:
    cust = customers.get(o["customer_id"], {"name": "UNKNOWN", "tier": "UNKNOWN"})
    enriched.append({**o, "customer_name": cust["name"], "customer_tier": cust["tier"]})
print(enriched[1])
# {'order_id': 102, 'customer_id': 99, 'amount': 10.0, 'customer_name': 'UNKNOWN', 'customer_tier': 'UNKNOWN'}
```

Order 102 enriches to an explicit `"UNKNOWN"` rather than raising or silently dropping the row — the same "never let a foreign key resolve to nothing visible" instinct as the unknown-member dimension row in `data_modeling/concepts/02_dimensional_modeling.md`. A transform that crashes (or silently drops a row) the first time a lookup misses is a transform that hasn't been tested against real, messy data.

## 4. Derived and Computed Columns

Turning raw fields into analytically useful ones — tiering, date parts, flags — is transform work, not extraction work, because it encodes business logic rather than just moving data:

```python
from datetime import datetime

def revenue_tier(amount):
    if amount >= 1000: return "high"
    if amount >= 200:  return "medium"
    return "low"

sale = {"amount": 5000.0, "sale_date": "2024-11-23"}
dt = datetime.strptime(sale["sale_date"], "%Y-%m-%d")
sale.update({
    "revenue_tier": revenue_tier(sale["amount"]),
    "quarter": f"Q{(dt.month - 1) // 3 + 1}",
    "is_weekend": dt.weekday() >= 5,
})
print(sale)
# {'amount': 5000.0, 'sale_date': '2024-11-23', 'revenue_tier': 'high', 'quarter': 'Q4', 'is_weekend': True}
```

## 5. Standardization: One Canonical Format, Always

Dates, phone numbers, and addresses arrive from different sources in different shapes. Standardizing at transform time — not at query time, and not "whenever someone notices" — means every downstream consumer can assume one format forever.

```python
raw_dates = ["01/15/2024", "2024-03-20", "March 5, 2024"]
formats = ["%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"]

for raw in raw_dates:
    parsed = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(raw, fmt); break
        except ValueError:
            continue
    print(f"'{raw}' -> '{parsed.strftime('%Y-%m-%d') if parsed else 'PARSE_ERROR'}'")
# '01/15/2024' -> '2024-01-15'
# '2024-03-20' -> '2024-03-20'
# 'March 5, 2024' -> '2024-03-05'
```

```python
import re

def standardize_phone(phone):
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"+1-{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else "INVALID"

for p in ["(555) 123-4567", "555.123.4567", "+1 555 123 4567"]:
    print(f"'{p}' -> '{standardize_phone(p)}'")
# all three -> '+1-555-123-4567'
```

The date list above includes an implicit trap worth naming out loud: `"15-01-2024"` is genuinely ambiguous between `DD-MM-YYYY` and an invalid `MM-DD-YYYY` — standardization can only be as correct as the format assumption it's given, and a silently wrong assumption here (parsing day-first data as month-first) produces dates that are wrong by a swapped day/month, not obviously broken. When a source's date convention isn't documented, that's a clarifying question to ask before writing the transform, not a guess to bake in.

## 6. Validation During Transform: Don't Let Bad Data Through Silently

A transform stage is the natural place to check business rules and route violations somewhere visible, instead of loading bad data or crashing the whole batch over one row:

```python
records = [
    {"id": 1, "email": "alice@example.com", "amount": 100.0},
    {"id": 2, "email": "not-an-email",       "amount": 50.0},
    {"id": 3, "email": "charlie@test.com",   "amount": -10.0},
]

def validate(r):
    errors = []
    if "@" not in (r.get("email") or ""):
        errors.append("invalid_email")
    if r.get("amount", 0) < 0:
        errors.append("negative_amount")
    return errors

valid, invalid = [], []
for r in records:
    errs = validate(r)
    (invalid if errs else valid).append({**r, "errors": errs} if errs else r)

print(f"valid={len(valid)} invalid={len(invalid)}")
# valid=1 invalid=2
```

Route `invalid` to a dead-letter/error table rather than dropping it on the floor — the full pattern, including retry-ability of dead-lettered records, is in `concepts/06_idempotency_reliability.md`, section 5.

## 7. Chaining Transforms Into a Pipeline

Production transform logic is rarely one function — it's a sequence of small, named, independently testable steps applied in order:

```python
def step_clean(rows):
    return [{k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in rows]

def step_cast_amount(rows):
    for r in rows: r["amount"] = float(r["amount"]) if r["amount"] else 0.0
    return rows

def step_filter_named(rows):
    return [r for r in rows if r.get("name")]

pipeline = [step_clean, step_cast_amount, step_filter_named]
data = [{"name": "  Alice ", "amount": "750"}, {"name": "", "amount": "50"}]

for step in pipeline:
    data = step(data)
    print(f"after {step.__name__}: {len(data)} rows")
# after step_clean: 2 rows
# after step_cast_amount: 2 rows
# after step_filter_named: 1 rows
```

Naming each step and logging the row count after it is what makes a production transform debuggable — when a downstream report is short a row, "which step dropped it" is a one-line log scan instead of a re-run-and-print-statements exercise. `projects/mini_etl_pipeline.md` builds exactly this shape (`_clean` → `_deduplicate` → `_enrich` → `_validate`) as one class.

---

See `concepts/03_loading_strategies.md` for what happens to this transformed data once it's ready to write, and `interview_questions/03_critique_and_debug.md`, Case 3, for the classic bug where a transform silently breaks after the source adds a column.
