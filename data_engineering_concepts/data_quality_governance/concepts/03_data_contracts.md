# Concept 03: Data Contracts

**Covers:**
- What a data contract is, and the API analogy that motivates it
- The parts of a contract: schema, quality SLAs, semantics, change policy
- Schema evolution rules: additive-safe changes vs. breaking changes
- Backward, forward, and full compatibility, defined precisely
- How a contract actually gets enforced: a CI check and a schema registry
- Contract versioning and rejecting a breaking change before it ships

*All code below is real, runnable Python + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. The API Analogy

A REST API publishes an OpenAPI/Swagger spec: consumers know the shape of every request and response without reading the server's source code, and the server can't silently change that shape without breaking every client that depends on it. A **data contract** is the same idea applied to a table: instead of a consumer discovering a table's shape by querying it and hoping nothing changed since yesterday, the producer publishes a formal specification — schema, freshness, quality guarantees — and commits to it.

Without a contract, "what does this table look like" is answered by `SELECT *` and reading the results; with one, it's answered by a document that's checked into version control, versioned, and enforced in CI *before* a breaking change ever reaches the table consumers actually query.

```python
EXAMPLE_CONTRACT = {
    "contract_name": "user_events",
    "version": "1.2.0",
    "owner": "analytics-team",
    "schema": {
        "columns": [
            {"name": "event_id", "type": "TEXT", "required": True, "unique": True},
            {"name": "user_id", "type": "INTEGER", "required": True},
            {"name": "event_type", "type": "TEXT", "required": True,
             "allowed_values": ["click", "view", "purchase", "signup"]},
            {"name": "timestamp", "type": "TEXT", "required": True},
            {"name": "amount", "type": "REAL", "required": False, "min_value": 0.0},
        ]
    },
    "quality_slas": {
        "completeness": {"threshold": 99.0, "columns": ["event_id", "user_id", "event_type"]},
        "uniqueness": {"threshold": 100.0, "columns": ["event_id"]},
        "freshness_max_hours": 2,
    },
    "semantics": {
        "grain": "One row per user interaction event",
        "update_frequency": "Real-time (streaming), batch consolidated hourly",
    },
    "change_policy": {"compatibility": "backward", "notification_channel": "#data-contracts-alerts"},
}
```

Every field earns its place by answering a question a consumer would otherwise have to ask a human: what columns exist and what are their types (`schema`), how fresh will this be and how good is it (`quality_slas`), what does a row actually mean (`semantics`), and what happens when something changes (`change_policy`).

---

## 2. Schema Evolution: Additive-Safe vs. Breaking

The single most valuable thing a contract does is turn "did this change break anything downstream" from a question someone finds out the hard way into a question answered mechanically, before the change ships. That requires a precise, non-negotiable classification of every possible schema change:

```text
NON-BREAKING (additive-safe):
  - adding an optional column
  - widening a type (INTEGER -> REAL, VARCHAR(10) -> VARCHAR(50))
  - making a required column optional
  - expanding an allowed-values set
  - adding a required column WITH a default value

BREAKING:
  - removing a required column
  - narrowing a type (REAL -> INTEGER)
  - making an optional column required
  - shrinking an allowed-values set
  - adding a required column with NO default (existing writers can't populate it)
```

The underlying test for "is this breaking" is always the same question, asked from the consumer's point of view: **can code written against the old schema keep working, unmodified, against the new one?** Adding an optional column passes that test trivially — old code never looked at it and still won't. Removing a required column fails it immediately — any query, model, or dashboard that referenced it now errors.

```python
class SchemaEvolution:
    @staticmethod
    def compare_schemas(old_schema, new_schema):
        old_cols = {c["name"]: c for c in old_schema["columns"]}
        new_cols = {c["name"]: c for c in new_schema["columns"]}
        changes = []

        for name, col in old_cols.items():
            if name not in new_cols:
                is_required = col.get("required", False)
                changes.append({"column": name, "breaking": is_required,
                                 "detail": f"Column '{name}' removed" + (" (was required)" if is_required else "")})

        for name, col in new_cols.items():
            if name not in old_cols:
                is_required = col.get("required", False)
                has_default = "default" in col
                breaking = is_required and not has_default
                changes.append({"column": name, "breaking": breaking,
                                 "detail": f"Column '{name}' added (required={is_required}, has_default={has_default})"})

        for name in old_cols:
            if name not in new_cols:
                continue
            old_col, new_col = old_cols[name], new_cols[name]
            if not old_col.get("required") and new_col.get("required"):
                changes.append({"column": name, "breaking": True, "detail": f"'{name}' changed optional -> required"})
            old_allowed, new_allowed = set(old_col.get("allowed_values", [])), set(new_col.get("allowed_values", []))
            if old_allowed - new_allowed:
                changes.append({"column": name, "breaking": True,
                                 "detail": f"Removed allowed values: {old_allowed - new_allowed}"})
            if new_allowed - old_allowed:
                changes.append({"column": name, "breaking": False,
                                 "detail": f"Added allowed values: {new_allowed - old_allowed}"})
        return changes

    @staticmethod
    def is_backward_compatible(changes):
        return not any(c["breaking"] for c in changes)


old_schema = {"columns": [
    {"name": "event_id", "type": "TEXT", "required": True},
    {"name": "user_id", "type": "INTEGER", "required": True},
    {"name": "event_type", "type": "TEXT", "required": True, "allowed_values": ["click", "view", "purchase"]},
]}
new_schema = {"columns": [
    {"name": "event_id", "type": "TEXT", "required": True},
    {"name": "user_id", "type": "INTEGER", "required": True},
    {"name": "event_type", "type": "TEXT", "required": True, "allowed_values": ["click", "view", "purchase", "signup"]},
    {"name": "session_id", "type": "TEXT", "required": False},  # new, optional
]}

changes = SchemaEvolution.compare_schemas(old_schema, new_schema)
for c in changes:
    print(("BREAKING" if c["breaking"] else "safe"), c["detail"])
print("Backward compatible:", SchemaEvolution.is_backward_compatible(changes))
# safe Column 'session_id' added (required=False, has_default=False)
# safe Added allowed values: {'signup'}
# Backward compatible: True
```

Now the breaking version:

```python
breaking_schema = {"columns": [
    {"name": "event_id", "type": "TEXT", "required": True},
    {"name": "event_type", "type": "TEXT", "required": True, "allowed_values": ["click", "view", "purchase"]},
    # user_id removed entirely
]}
breaking_changes = SchemaEvolution.compare_schemas(old_schema, breaking_schema)
for c in breaking_changes:
    print(("BREAKING" if c["breaking"] else "safe"), c["detail"])
print("Backward compatible:", SchemaEvolution.is_backward_compatible(breaking_changes))
# BREAKING Column 'user_id' removed (was required)
# Backward compatible: False
```

## 3. Backward, Forward, and Full Compatibility

These three terms get used loosely; precisely, they describe *which direction* old and new can cross:

```text
BACKWARD compatible:  code written against the NEW schema can read data written by the OLD schema.
                      (safe: add optional columns, widen types -- new readers tolerate old, narrower data)

FORWARD compatible:   code written against the OLD schema can read data written by the NEW schema.
                      (safe: remove optional columns -- old readers just ignore fields they don't expect)

FULL compatible:      both directions hold at once.
```

The direction that matters in practice depends on *deployment order*. If consumers upgrade before producers (a BI tool adds support for a new field ahead of the pipeline ever populating it), forward compatibility is what's being relied on. If producers ship before every consumer has caught up (the far more common case for a warehouse table with many downstream dashboards, none of which redeploy in lockstep with the pipeline), **backward compatibility is the one that matters almost all the time** — which is why `change_policy.compatibility` in the contract above defaults to `"backward"`.

---

## 4. Enforcing a Contract: CI Check and Schema Registry

A contract that lives only as documentation is a promise with no teeth. Two mechanisms turn it into something actually enforced:

```text
1. CI CHECK (enforced at commit/PR time):
   Every PR that touches a producing pipeline's output schema runs
   SchemaEvolution.compare_schemas(current_contract, proposed_schema).
   A breaking change against a "backward" policy FAILS the build --
   the PR cannot merge until the change is reclassified as intentional
   (a major version bump, with consumers notified) or reverted to
   an additive-safe form.

2. SCHEMA REGISTRY (enforced at write/publish time):
   A central service (e.g. Confluent Schema Registry for Kafka, or an
   internal warehouse-side equivalent) that a producer must register a
   new schema version with BEFORE writing data under it. The registry
   itself runs the same compatibility check and refuses the write if it
   violates policy -- this catches a breaking change even from a
   producer that skipped or bypassed the CI check entirely.
```

The CI check catches the problem earliest (before the change is even merged) but only if every producing pipeline actually runs it. The schema registry is the backstop that can't be skipped, because it sits between the producer and the act of writing data at all — the trade-off is it catches the problem later, at write time rather than review time. A mature setup runs both: CI for fast feedback to the engineer making the change, a registry as the enforcement point that doesn't depend on anyone remembering to run a check.

```python
import sqlite3

class DataContract:
    """Validates a live table against a contract's schema and completeness SLA."""
    def __init__(self, spec):
        self.spec = spec

    def validate(self, conn, table):
        results = []
        actual = {r[1]: r[2] for r in conn.execute(f"PRAGMA table_info({table})")}

        # 1. Schema checks: column exists, type matches
        for col in self.spec["schema"]["columns"]:
            exists = col["name"] in actual
            results.append({"check": f"column_exists.{col['name']}", "passed": exists})
            if exists:
                type_ok = actual[col["name"]].upper() == col.get("type", "").upper()
                results.append({"check": f"type.{col['name']}", "passed": type_ok})

        # 2. Completeness SLA: required columns must clear the declared threshold
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        completeness_sla = self.spec.get("quality_slas", {}).get("completeness", {})
        threshold = completeness_sla.get("threshold", 100)
        for col_name in completeness_sla.get("columns", []):
            non_null = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col_name} IS NOT NULL").fetchone()[0]
            pct = round(non_null / total * 100, 1) if total else 0
            results.append({"check": f"completeness.{col_name}", "passed": pct >= threshold, "detail": f"{pct}%"})

        passed = sum(1 for r in results if r["passed"])
        return {"contract": self.spec["contract_name"], "version": self.spec["version"],
                "compliant": passed == len(results), "passed": passed, "total": len(results), "checks": results}


conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE user_events (event_id TEXT, user_id INTEGER, event_type TEXT, timestamp TEXT, amount REAL)")
conn.executemany("INSERT INTO user_events VALUES (?,?,?,?,?)", [
    ("evt-001", 1, "click", "2024-06-01T10:00:00", None),
    ("evt-002", 2, "purchase", "2024-06-01T10:05:00", 29.99),
    ("evt-003", None, "view", "2024-06-01T10:10:00", None),  # null user_id
])
conn.commit()

result = DataContract(EXAMPLE_CONTRACT).validate(conn, "user_events")
print(f"{result['passed']}/{result['total']} checks passed, compliant={result['compliant']}")
for c in result["checks"]:
    if not c["passed"]:
        print(" FAIL:", c["check"], c.get("detail", ""))
# 12/13 checks passed, compliant=False
#  FAIL: completeness.user_id 66.7%
```

*(This is the same pattern `projects/quality_checker.md` builds out fully — schema checks first, quality SLA checks second, using every dimension check from `concepts/01_data_quality_dimensions.md`.)*

---

## 5. Contract Versioning

A contract registry rejects a proposed version outright if it violates the declared compatibility policy against the *previous* registered version — this is the mechanical version of the CI check, applied to the contract's own version history rather than to one PR.

```python
class ContractRegistry:
    def __init__(self):
        self.contracts = {}  # name -> [versions, in order]

    def register(self, spec):
        name, version = spec["contract_name"], spec["version"]
        history = self.contracts.setdefault(name, [])
        if history:
            prev = history[-1]
            policy = prev.get("change_policy", {}).get("compatibility", "none")
            changes = SchemaEvolution.compare_schemas(prev["schema"], spec["schema"])
            if policy == "backward" and not SchemaEvolution.is_backward_compatible(changes):
                return {"registered": False, "reason": "breaking change violates backward-compatibility policy",
                        "breaking_changes": [c for c in changes if c["breaking"]]}
        history.append(spec)
        return {"registered": True, "version": version}

registry = ContractRegistry()
v1 = {"contract_name": "user_events", "version": "1.0.0", "schema": old_schema,
      "change_policy": {"compatibility": "backward"}}
v1_1 = {**v1, "version": "1.1.0", "schema": new_schema}  # additive change from Section 2
v2_bad = {**v1, "version": "2.0.0", "schema": breaking_schema}  # removes user_id

print(registry.register(v1))      # {'registered': True, 'version': '1.0.0'}
print(registry.register(v1_1))    # {'registered': True, 'version': '1.1.0'}
result = registry.register(v2_bad)
print(result["registered"], result["reason"])
# False breaking change violates backward-compatibility policy
```

Rejecting `v2.0.0` here isn't a permanent block on removing `user_id` — it's a forcing function. The producer team now has to make that decision *explicitly*: either keep the field (reverting to additive-safe), or accept the break deliberately with a real major-version bump, a notification to every known consumer through the contract's `notification_channel`, and a migration window — exactly the kind of change that should never happen silently, which is the entire point of having a contract in the first place.

---

## Key Takeaways

- A data contract is the same idea as an API spec applied to a table: producers publish schema, freshness, and quality guarantees; consumers build against the contract instead of discovering the table's shape by querying and hoping.
- Every schema change classifies as additive-safe or breaking by one test: can code written against the old schema keep working, unmodified, against the new one? Adding an optional column passes; removing a required column, narrowing a type, or shrinking an allowed-values set does not.
- Backward compatible means new readers can handle old data; forward compatible means old readers can handle new data. Backward compatibility is the one that matters in the overwhelmingly common deployment order — producer ships first, consumers catch up later — which is why it's the default policy almost every contract declares.
- A contract only has teeth if it's enforced somewhere real: a CI check that fails a PR proposing a breaking change against policy, and/or a schema registry that refuses to accept a write under an incompatible schema version. CI catches it earliest but can be skipped; a registry is the backstop that can't be, at the cost of catching the problem later.
- Contract versioning applies the same compatibility check to the contract's own history: registering a new version that breaks the declared policy against the previous one is rejected outright, forcing the breaking change to become an explicit, versioned, communicated decision rather than a silent one.
