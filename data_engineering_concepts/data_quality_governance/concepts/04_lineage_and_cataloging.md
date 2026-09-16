# Concept 04: Lineage & Cataloging

**Covers:**
- What data lineage answers, and the three granularities it operates at
- Table-level lineage: building and walking a dependency graph
- Column-level lineage: why "where did this column come from" is a different, finer question
- Impact analysis: "if this changes, what breaks" — the operational payoff of lineage
- Data catalogs: making data discoverable, documented, and governed
- Tagging, classification, and PII discovery

*All code below is real, runnable Python + `sqlite3` — copy any block into a `python3` shell and it runs as shown.*

---

## 1. What Lineage Answers

**Lineage** tracks where data came from and where it goes. It exists to answer two questions that show up constantly in an incident, and are nearly impossible to answer reliably from memory or from reading pipeline code once a warehouse has more than a handful of tables:

```text
Root cause:      "This dashboard number looks wrong -- which upstream source could explain it?"
Impact analysis: "I'm about to change this column -- what downstream reports will break?"
```

Lineage operates at three granularities, each answering a related but distinct question:

```text
Table-level:  raw.clickstream -> staging.events -> mart.user_activity -> report.dashboard
              "which tables feed this one?"

Column-level: raw.clickstream.user_email -> staging.events.email -> mart.user_activity.email_hash
              "which SOURCE COLUMN produced this specific column, through what transformation?"

Job-level:    "which ETL job produced this table, and when did it last run?"
```

Table-level lineage is the cheapest to capture and the most commonly available (most orchestrators and warehouses can infer it from query logs almost for free). Column-level lineage is far more valuable for root-cause work but requires either parsing the actual transformation logic (SQL parsing, or explicit instrumentation) or hand-recording it — which is exactly why many organizations have solid table-level lineage but only partial column-level coverage.

---

## 2. Table-Level Lineage: Build and Walk the Graph

Lineage is a directed graph: datasets are nodes, transformations are edges. Once the edges are recorded, "what feeds this" and "what does this feed" are just graph traversals — upstream walks backward along edges, downstream (impact analysis) walks forward.

```python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("""
    CREATE TABLE lineage_edges (
        source_dataset TEXT, target_dataset TEXT, transformation TEXT, job_name TEXT
    )
""")
edges = [
    ("raw.clickstream", "staging.events", "clean + deduplicate", "etl_events_job"),
    ("raw.users", "staging.users", "normalize + validate", "etl_users_job"),
    ("staging.events", "mart.user_activity", "join + aggregate", "transform_activity"),
    ("staging.users", "mart.user_activity", "join", "transform_activity"),
    ("mart.user_activity", "mart.daily_metrics", "aggregate by day", "daily_rollup"),
    ("mart.daily_metrics", "report.executive_dashboard", "visualize", "dashboard_refresh"),
]
conn.executemany("INSERT INTO lineage_edges VALUES (?,?,?,?)", edges)
conn.commit()

def get_upstream(conn, dataset, depth=10):
    """BFS walk backward through the graph: everything that feeds `dataset`, directly or transitively."""
    visited, queue, upstream = set(), [dataset], []
    for _ in range(depth):
        if not queue:
            break
        next_queue = []
        for ds in queue:
            for src, xform in conn.execute(
                "SELECT source_dataset, transformation FROM lineage_edges WHERE target_dataset = ?", (ds,)
            ).fetchall():
                if src not in visited:
                    visited.add(src)
                    upstream.append({"dataset": src, "feeds_into": ds, "transformation": xform})
                    next_queue.append(src)
        queue = next_queue
    return upstream

def get_downstream(conn, dataset, depth=10):
    """Same walk, forward: everything `dataset` feeds, directly or transitively -- this IS impact analysis."""
    visited, queue, downstream = set(), [dataset], []
    for _ in range(depth):
        if not queue:
            break
        next_queue = []
        for ds in queue:
            for tgt, xform in conn.execute(
                "SELECT target_dataset, transformation FROM lineage_edges WHERE source_dataset = ?", (ds,)
            ).fetchall():
                if tgt not in visited:
                    visited.add(tgt)
                    downstream.append({"dataset": tgt, "fed_by": ds, "transformation": xform})
                    next_queue.append(tgt)
        queue = next_queue
    return downstream

for u in get_upstream(conn, "mart.user_activity"):
    print(f"  {u['dataset']} -> {u['feeds_into']} ({u['transformation']})")
# staging.events -> mart.user_activity (join + aggregate)
# staging.users -> mart.user_activity (join)
# raw.clickstream -> staging.events (clean + deduplicate)
# raw.users -> staging.users (normalize + validate)

impact = get_downstream(conn, "raw.clickstream")
print(f"If raw.clickstream changes, {len(impact)} datasets are affected:")
for d in impact:
    print(f"  {d['fed_by']} -> {d['dataset']}")
# raw.clickstream -> staging.events
# staging.events -> mart.user_activity
# mart.user_activity -> mart.daily_metrics
# mart.daily_metrics -> report.executive_dashboard
```

This is the mechanical form of **impact analysis**: before touching `raw.clickstream`'s schema, a `get_downstream` walk tells you, deterministically, that four other datasets — three intermediate tables and one executive dashboard — need to be checked or notified, instead of that discovery happening the hard way, after the dashboard breaks.

---

## 3. Column-Level Lineage: A Finer Question

Table-level lineage answers "which tables feed this one." It cannot answer "which specific *column* in `raw.users` produced `staging.users.first_name`" — for that, lineage needs to be tracked at the column grain, with the transformation recorded per pair of columns, not per pair of tables.

```python
conn.execute("""
    CREATE TABLE column_lineage (
        source_dataset TEXT, source_column TEXT, target_dataset TEXT, target_column TEXT, transformation TEXT
    )
""")
conn.executemany("INSERT INTO column_lineage VALUES (?,?,?,?,?)", [
    ("raw.clickstream", "user_email", "staging.events", "email", "lowercase + trim"),
    ("staging.events", "email", "mart.user_activity", "email_hash", "sha256 hash"),
    ("raw.users", "full_name", "staging.users", "first_name", "split on space [0]"),
    ("raw.users", "full_name", "staging.users", "last_name", "split on space [1]"),
])
conn.commit()

def get_column_lineage(conn, dataset, column):
    rows = conn.execute(
        "SELECT source_dataset, source_column, target_dataset, target_column, transformation "
        "FROM column_lineage WHERE (target_dataset=? AND target_column=?) OR (source_dataset=? AND source_column=?)",
        (dataset, column, dataset, column)
    ).fetchall()
    return [{"source": f"{r[0]}.{r[1]}", "target": f"{r[2]}.{r[3]}", "transformation": r[4]} for r in rows]

for cl in get_column_lineage(conn, "staging.events", "email"):
    print(f"  {cl['source']} -> {cl['target']} ({cl['transformation']})")
# raw.clickstream.user_email -> staging.events.email (lowercase + trim)
```

Notice that `raw.users.full_name` fans out into *two* target columns (`first_name` and `last_name`) via two different transformations of the same source column — a shape table-level lineage would have completely flattened into a single `raw.users -> staging.users` edge. This is why column-level lineage matters most specifically for **GDPR-style "right to erasure" and PII questions**: "where does this user's email actually end up, after every transformation" is a column-level question, and a table-level answer ("somewhere in `staging.events`") isn't precise enough to act on — it can't tell you the email was hashed one hop later and no longer needs erasing at all, versus a column that keeps the raw value all the way to a report.

---

## 4. Data Catalogs: Discoverability, Documentation, Governance

A **data catalog** is the metadata layer that sits on top of lineage: it's what makes a dataset *findable* and *self-documenting* in the first place, independent of whether anyone knows its lineage. Where lineage answers "how did this data get here," a catalog answers "does this data exist, what does it mean, who owns it, and am I allowed to use it."

```python
import json

conn.execute("""
    CREATE TABLE catalog_datasets (
        dataset_id TEXT PRIMARY KEY, display_name TEXT, description TEXT,
        owner TEXT, domain TEXT, tags TEXT, classification TEXT, row_count INTEGER
    )
""")
conn.execute("""
    CREATE TABLE catalog_columns (
        dataset_id TEXT, column_name TEXT, column_type TEXT, description TEXT, is_pii INTEGER
    )
""")

def register_dataset(conn, dataset_id, display_name, description, owner, domain, tags, classification, row_count):
    conn.execute("INSERT OR REPLACE INTO catalog_datasets VALUES (?,?,?,?,?,?,?,?)",
                 (dataset_id, display_name, description, owner, domain, json.dumps(tags), classification, row_count))
    conn.commit()

def add_column(conn, dataset_id, column_name, column_type, description, is_pii=False):
    conn.execute("INSERT INTO catalog_columns VALUES (?,?,?,?,?)",
                 (dataset_id, column_name, column_type, description, int(is_pii)))
    conn.commit()

register_dataset(conn, "raw.users", "Raw Users", "Raw user profiles from the application database",
                  owner="data-eng", domain="identity", tags=["raw", "users", "pii"],
                  classification="confidential", row_count=500000)
add_column(conn, "raw.users", "email", "TEXT", "User email address", is_pii=True)
add_column(conn, "raw.users", "full_name", "TEXT", "User full name", is_pii=True)
add_column(conn, "raw.users", "user_id", "INTEGER", "Unique user identifier")

def find_pii_columns(conn):
    rows = conn.execute(
        "SELECT dataset_id, column_name, description FROM catalog_columns WHERE is_pii = 1"
    ).fetchall()
    return [{"dataset": r[0], "column": r[1], "description": r[2]} for r in rows]

for p in find_pii_columns(conn):
    print(f"  {p['dataset']}.{p['column']}: {p['description']}")
# raw.users.email: User email address
# raw.users.full_name: User full name
```

---

## 5. Tagging, Classification, and Search

The two catalog features that make governance operational rather than aspirational are **classification** (a sensitivity tier — `public` / `internal` / `confidential` / `restricted`, driving access control) and **PII tagging** at the column level (driving masking, encryption-at-rest requirements, and the erasure workflow that column-level lineage feeds into). Both need to be *searchable*, not just recorded, or they're documentation nobody finds:

```python
def search_catalog(conn, query=None, tags=None, domain=None):
    conditions, params = [], []
    if query:
        conditions.append("(display_name LIKE ? OR description LIKE ?)")
        params += [f"%{query}%", f"%{query}%"]
    if domain:
        conditions.append("domain = ?")
        params.append(domain)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(f"SELECT * FROM catalog_datasets WHERE {where}", params).fetchall()

    results = []
    for r in rows:
        ds_tags = json.loads(r[5])
        if tags and not set(tags) & set(ds_tags):
            continue
        results.append({"dataset_id": r[0], "name": r[1], "classification": r[6], "tags": ds_tags})
    return results

print(search_catalog(conn, tags=["pii"]))
# [{'dataset_id': 'raw.users', 'name': 'Raw Users', 'classification': 'confidential', 'tags': ['raw', 'users', 'pii']}]

def get_datasets_by_classification(conn, classification):
    rows = conn.execute(
        "SELECT dataset_id, owner FROM catalog_datasets WHERE classification = ?", (classification,)
    ).fetchall()
    return [{"dataset_id": r[0], "owner": r[1]} for r in rows]

print(get_datasets_by_classification(conn, "confidential"))
# [{'dataset_id': 'raw.users', 'owner': 'data-eng'}]
```

A "which datasets contain PII" or "which restricted-classification tables exist" query answered instantly by the catalog is the difference between a real compliance posture and a spreadsheet someone updates quarterly and forgets about. When lineage and catalog are combined — PII tags at the source, column-level lineage tracing where that tagged data actually flows — "find every place this user's email could still exist" becomes a graph query instead of an audit.

---

## Key Takeaways

- Lineage tracks where data came from and where it goes, at three granularities: table-level (cheapest, most available), column-level (most precise, needed for real root-cause and PII work), and job-level (which process produced a given table).
- Table-level lineage is a directed graph — datasets as nodes, transformations as edges — and "upstream" / "downstream" (impact analysis) are just backward and forward graph walks over it.
- Column-level lineage exists because table-level lineage can hide a fan-out (one source column producing several target columns via different transformations) that matters enormously for GDPR-style erasure and precise root-cause analysis, and table-level tracking alone can't answer those questions.
- A data catalog is the discoverability and governance layer: it answers "does this exist, what does it mean, who owns it, can I use it" — a different question from lineage's "how did this get here."
- Classification (a sensitivity tier) and PII tagging turn governance from documentation into something enforceable and searchable — access control keyed on classification, and masking/erasure workflows keyed on PII tags, both only useful if they're actually queryable rather than written down and forgotten.
- See `concepts/05_anomaly_detection_and_monitoring.md` for the complementary question lineage and cataloging don't answer: not "where does this data come from" but "is this data still arriving, on time, looking like it usually does."
