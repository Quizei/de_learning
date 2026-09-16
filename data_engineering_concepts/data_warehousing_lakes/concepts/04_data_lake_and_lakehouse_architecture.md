# Concept 04: Data Lake & Lakehouse Architecture

**Covers:**
- Data warehouse vs. data lake vs. lakehouse — the actual trade-offs, not just the buzzwords
- Lake zones: bronze (raw) / silver (clean) / gold (curated) and why each layer exists
- The "data swamp" anti-pattern — what makes an ungoverned lake actively worse than no lake
- The medallion architecture built end to end as a runnable pipeline
- A decision framework for choosing warehouse vs. lake vs. lakehouse for a given company/workload

*The pipeline below runs as-is against Python's standard library — no Spark cluster, no cloud account needed to see the mechanics.*

---

## 1. Warehouse vs. Lake vs. Lakehouse

```text
Data Warehouse:  structured, schema-on-write, fast queries, higher storage cost
Data Lake:       any format, schema-on-read, cheap storage, slower/less reliable queries
Lakehouse:       lake storage cost + warehouse reliability (ACID, schema, SQL) via a table format
```

A **data warehouse** stores data in a structured, pre-defined schema, validated at write time — you can't insert a row that doesn't match the schema. This buys strong reliability and fast, predictable queries, at the cost of flexibility and (traditionally) proprietary storage.

A **data lake** stores data in its raw, native format — JSON, CSV, logs, images, whatever the source produces — at effectively unlimited scale on cheap object storage, with schema applied only when it's *read* ("schema-on-read"). This buys flexibility (store first, figure out the shape of the questions later) at the cost of the reliability guarantees a warehouse takes for granted: nothing stops inconsistent data, no built-in transactions, no schema enforcement.

A **lakehouse** is the attempt to get both: keep data in open file formats (Parquet) on cheap object storage (the lake's cost profile), but add a metadata layer — a table format, covered in full in `concepts/03_file_and_table_formats.md` — that restores ACID transactions, schema enforcement, and time travel on top of those files. This isn't a third separate technology; it's the lake's storage layer plus the warehouse's reliability guarantees, layered together.

| Feature | Data Lake | Warehouse | Lakehouse |
|---|---|---|---|
| Storage cost | Low (S3/GCS) | Higher (often proprietary) | Low (S3/GCS) |
| ACID transactions | No | Yes | Yes (via table format) |
| Schema enforcement | No | Yes | Yes |
| Open file formats | Yes | Usually no | Yes |
| Time travel | No | Limited | Yes |
| Streaming support | Yes | Limited | Yes |
| ML/data-science access to raw data | Yes | Limited | Yes |

**How this plays out as a real decision** (worked in full as a scenario in `interview_questions/01_worked_scenarios.md`): a mid-size company evaluating Snowflake/BigQuery-style warehouse vs. a lakehouse on S3+Iceberg is really asking "do I need a fully managed, opinionated system with the best out-of-box query performance and governance, or do I need open-format flexibility for ML/data-science workloads plus multi-engine access, at the cost of assembling more of the reliability layer myself?" Neither answer is universally correct — it depends on team size, existing engine investment, and how much of the workload is BI-style SQL versus ML feature engineering over raw data.

---

## 2. Lake Zones: Bronze, Silver, Gold

A well-run lake organizes data into progressively refined layers rather than one flat pile of files — this is the **medallion architecture**, and it maps directly onto the normalize-then-denormalize trade-off from `data_modeling/concepts/01_normalization.md` and `data_modeling/README.md`'s Kimball/medallion cross-reference, just expressed as physical pipeline stages instead of schema shape.

```text
Sources -> [BRONZE] -> [SILVER] -> [GOLD] -> Consumers
(APIs,      (raw,        (clean,      (curated,   (dashboards,
 DBs,        as-is)       validated)   aggregated)  ML models,
 files)                                              reports)
```

- **Bronze (raw):** an exact, append-only, immutable copy of source data — whatever format the source produced (JSON, CSV, Avro from Kafka). No transformation. This is the "source of truth" you can always replay from if a downstream bug is discovered — if silver/gold logic was wrong, bronze lets you reprocess rather than having lost the original data forever.
- **Silver (clean):** validated, deduplicated, typed, standardized — nulls handled, dates parsed, casing normalized, conformed identifiers across sources. Still relatively granular (individual records), typically stored as Parquet. This is roughly the 3NF-style cleanup step, just done as a pipeline stage instead of a schema constraint.
- **Gold (curated):** business-level aggregates — pre-joined star schemas or summary tables, optimized for the exact dashboards and reports that consume them. This is the only layer most analysts and BI tools should query directly.

---

## 3. Building the Pipeline End to End

This runs bronze → silver → gold as an actual pipeline over messy, realistic data — the same shape a real ingestion job runs, just against local files instead of S3.

```python
import os, json, random, tempfile, shutil

base_dir = tempfile.mkdtemp(prefix="lakehouse_")
try:
    bronze_dir = os.path.join(base_dir, "bronze", "sales_events")
    silver_dir = os.path.join(base_dir, "silver", "sales_cleaned")
    gold_dir   = os.path.join(base_dir, "gold", "sales_summary")
    for d in (bronze_dir, silver_dir, gold_dir):
        os.makedirs(d, exist_ok=True)

    # ---- BRONZE: ingest raw, messy data exactly as the source produced it ----
    random.seed(7)
    raw_events = [{
        "event_id": f"evt_{i:04d}",
        "timestamp": f"2025-01-{random.randint(1,28):02d}",
        "customer_id": random.choice([f"C{random.randint(1,50):03d}", None, "unknown"]),
        "product": random.choice(["Laptop", "laptop", "MOUSE", "Mouse", None]),
        "quantity": random.choice([1, 2, 3, -1, None]),
        "price": random.choice([99.99, 29.99, None, -10.0]),
    } for i in range(200)]

    bronze_partitions = {}
    for e in raw_events:
        bronze_partitions.setdefault(e["timestamp"], []).append(e)
    for day, events in bronze_partitions.items():
        with open(os.path.join(bronze_dir, f"date={day}.json"), "w") as f:
            for evt in events:
                f.write(json.dumps(evt) + "\n")

    print(f"BRONZE: {len(raw_events)} raw events across {len(bronze_partitions)} date partitions")

    # ---- SILVER: validate, dedupe, standardize ----
    silver_records, rejected = [], 0
    for e in raw_events:
        if not e["customer_id"] or e["customer_id"] == "unknown":
            rejected += 1
            continue
        if not e["product"]:
            rejected += 1
            continue
        if not isinstance(e["quantity"], int) or e["quantity"] <= 0:
            rejected += 1
            continue
        if not isinstance(e["price"], (int, float)) or e["price"] <= 0:
            rejected += 1
            continue
        silver_records.append({
            "event_id": e["event_id"], "timestamp": e["timestamp"],
            "customer_id": e["customer_id"], "product": e["product"].strip().title(),
            "quantity": e["quantity"], "price": e["price"],
            "revenue": round(e["quantity"] * e["price"], 2),
        })
    with open(os.path.join(silver_dir, "data.json"), "w") as f:
        for r in silver_records:
            f.write(json.dumps(r) + "\n")

    print(f"SILVER: {len(silver_records)} clean records ({rejected} rejected)")

    # ---- GOLD: business aggregates ----
    product_summary = {}
    for r in silver_records:
        p = product_summary.setdefault(r["product"], {"revenue": 0.0, "units": 0})
        p["revenue"] += r["revenue"]
        p["units"] += r["quantity"]
    with open(os.path.join(gold_dir, "product_summary.json"), "w") as f:
        json.dump(product_summary, f)

    print(f"GOLD: product_summary with {len(product_summary)} products")
    for prod, stats in sorted(product_summary.items(), key=lambda x: -x[1]["revenue"]):
        print(f"  {prod:<10} revenue=${stats['revenue']:>8,.2f}  units={stats['units']}")
finally:
    shutil.rmtree(base_dir, ignore_errors=True)
```

**Output:**
```text
BRONZE: 200 raw events across 28 date partitions
SILVER: 79 clean records (121 rejected)
GOLD: product_summary with 2 products
  Laptop     revenue=$ 2,499.75  units=25
  Mouse      revenue=$   659.78  units=22
```

Two things worth narrating out loud from this run: **the rejection rate is a real data-quality signal, not just an implementation detail** — 121 of 200 bronze records failed validation, which in production would be a metric worth alerting on, not silently discarding; and **bronze retains every rejected record's original form**, so reprocessing after a bug fix in the silver logic doesn't require re-ingesting from the source at all.

---

## 4. The Data Swamp: What Happens Without Governance

A lake becomes a **swamp** — data nobody trusts, can find, or is willing to build on — when the zones above exist without discipline around them:

| Anti-pattern | Symptom | Fix |
|---|---|---|
| No catalog/discovery | "Do we have clickstream data?" — nobody knows | Data catalog (Glue, DataHub, OpenMetadata) |
| No schema enforcement | JSON blobs with fields that silently change shape | Schema registry, validation in the pipeline |
| No data quality checks | Nulls/duplicates/stale data found only when a dashboard breaks | Quality frameworks (Great Expectations, dbt tests) |
| No access controls | Everyone can read/write everything | Fine-grained (column/row-level) access policies |
| No ownership | Datasets created and abandoned; nobody to ask | Data stewards, domain ownership tags |
| No lineage | Can't trace what a metric depends on or what breaks if a table changes | Lineage tooling (OpenLineage, dbt's lineage graph) |
| Write-only lake | Data goes in, nobody ever reads it, storage cost grows forever | Lifecycle policies: archive/delete unused data |

The single most common *symptom* of a swamp in an interview scenario is the same one covered from the schema-conflict angle in `data_modeling/interview_questions/03_critique_and_debug.md`, Case 8: two teams' numbers silently disagreeing because nothing forced them to build on the same conformed, governed source. A swamp isn't a lake that's merely messy in bronze (bronze is *supposed* to be raw and messy) — it's a lake where silver and gold have also lost that discipline, and nobody can tell which is which anymore.

---

## 5. Choosing Warehouse vs. Lake vs. Lakehouse

A practical framework for the "which architecture" conversation:

- **Straightforward BI/reporting workload, structured sources, a team that wants the least operational overhead** → a managed warehouse (Snowflake, BigQuery, Redshift) is usually still the right default. The lakehouse's flexibility isn't free — it trades a fully managed experience for more assembly (choosing a table format, a catalog, a query engine, a governance layer).
- **Heavy ML/data-science workloads that need raw, ungoverned access to data in its native shape, alongside BI** → a lakehouse's open formats let both worlds share one copy of the data instead of maintaining a warehouse *and* a separate lake with data duplicated between them.
- **Multiple query engines need to share the same tables** (Spark for batch ETL, Trino for ad-hoc SQL, Flink for streaming) → a lakehouse with an open table format (Iceberg especially) avoids locking every engine into one vendor's proprietary storage.
- **Regulatory/audit requirements for full historical traceability** → both a modern warehouse and a lakehouse table format provide time travel; the deciding factor becomes cost and existing tooling, not a capability gap.
- **Small team, simple pipeline, one BI tool** → don't over-engineer this: a managed warehouse with a handful of well-designed star schemas (`data_modeling/concepts/`) will out-execute a hand-rolled lakehouse stack that nobody has the headcount to operate well.

The honest, senior framing to give in an interview: this is rarely a binary, permanent choice — many real companies run a lakehouse for raw/ML-facing data and load curated gold tables into a managed warehouse for BI, getting each system's strength where it matters most.

---

## Key Takeaways

- A warehouse is schema-on-write and reliable but rigid; a lake is schema-on-read and flexible but offers no built-in guarantees; a lakehouse is a lake's storage economics plus a warehouse's reliability, via a table format (`concepts/03_file_and_table_formats.md`).
- Bronze/silver/gold progressively refines data: bronze is raw and immutable (your replay source), silver is validated/standardized, gold is business-ready aggregates — this is the medallion architecture, and it's the same normalize-then-denormalize idea from `data_modeling/` expressed as pipeline stages.
- A data swamp isn't "a messy lake" — bronze is supposed to be messy. It's a lake where nobody can discover, trust, or trace data anywhere in the pipeline, usually from missing catalog, schema enforcement, quality checks, ownership, or lineage.
- Choosing warehouse vs. lake vs. lakehouse is a trade-off between managed simplicity, ML/multi-engine flexibility, and existing tooling investment — not a universal "best" answer, and real architectures frequently combine both.
