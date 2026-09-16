# Concept 06: Data Vault Modeling (Hubs, Links, Satellites)

> **Added — not from a single canonical source.** Data Vault is the third major data-warehouse methodology alongside Kimball (dimensional, this whole course) and Inmon (top-down normalized enterprise warehouse). It rarely comes up as "design me a data vault" in an analytics-facing interview, but "Kimball vs. Inmon vs. Data Vault — what's the difference" is a very common rapid-fire question, and understanding *why* Data Vault exists makes that answer sound like knowledge instead of a memorized flashcard.

**Covers:**
- The problem Data Vault actually solves: loading, not querying
- Hubs, links, and satellites — the three table types, with a worked example
- Why Data Vault insert-only loading enables massive load parallelism
- Where Data Vault fits relative to Kimball: normally *underneath* it, not instead of it
- Why this is rarely the right answer for an analytics-facing interview question, and when it is

---

## 1. The Problem Data Vault Solves: Loading, Not Querying

Kimball dimensional modeling (concepts 01-05) is optimized for **query-time** experience — an analyst or BI tool joining a handful of tables to answer a business question quickly. Data Vault is optimized for a completely different moment: **load time**, at very large scale, with many source systems landing data in parallel, and business rules that change faster than a rigid dimensional model can be redesigned.

The core problem: in a large enterprise, dozens of source systems each have their own idea of "customer," "product," or "account," and they don't agree, don't all update at the same cadence, and sometimes disappear and get replaced. A star schema's dimension tables assume a settled, agreed-upon shape. Data Vault assumes exactly the opposite — that agreement, if it comes at all, comes later — and designs the *loading* layer to never need to change no matter how the business rules evolve on top of it.

---

## 2. The Three Table Types

```text
        HUB                         LINK                         SATELLITE
  business key only            relationship only            all descriptive attributes,
  (the "who/what exists")      (the "these things            with LOAD DATE + SOURCE
                                relate to each other")        (the "what do we know,
                                                               and when did we learn it")

  hub_customer                 link_customer_order          sat_customer_details
    customer_hub_key (PK)        link_key (PK)                 customer_hub_key (FK)
    customer_id (business key)   customer_hub_key (FK)          load_date (part of PK)
    load_date                    order_hub_key (FK)              record_source
    record_source                 load_date                      name, email, address, ...
```

- **Hub**: holds *only* the business key (e.g. `customer_id`) plus load metadata (`load_date`, `record_source`) — never any descriptive attribute. Its entire job is to say "this business key exists, and we first saw it from this source on this date."
- **Link**: holds *only* the relationship between two or more hubs (e.g. "this customer placed this order") — again, no descriptive attributes, just foreign keys to the hubs involved plus load metadata.
- **Satellite**: holds the actual descriptive attributes (name, email, address, price, status) attached to a hub or a link, versioned by `load_date` — this is where change-over-time tracking lives, and it looks structurally like a Type 2 SCD row, keyed by the hub/link key plus the load date instead of `effective_date`/`expiration_date`/`is_current`.

**Worked example:** a customer places an order.

```sql
-- HUB: the business key alone
CREATE TABLE hub_customer (
    customer_hub_key TEXT PRIMARY KEY,   -- typically a hash of the business key
    customer_id      TEXT NOT NULL,      -- the natural/business key
    load_date        TEXT NOT NULL,
    record_source    TEXT NOT NULL
);

CREATE TABLE hub_order (
    order_hub_key    TEXT PRIMARY KEY,
    order_id         TEXT NOT NULL,
    load_date        TEXT NOT NULL,
    record_source    TEXT NOT NULL
);

-- LINK: the relationship, and nothing else
CREATE TABLE link_customer_order (
    link_key          TEXT PRIMARY KEY,
    customer_hub_key  TEXT REFERENCES hub_customer(customer_hub_key),
    order_hub_key     TEXT REFERENCES hub_order(order_hub_key),
    load_date         TEXT NOT NULL,
    record_source     TEXT NOT NULL
);

-- SATELLITE: descriptive attributes, versioned by load_date
CREATE TABLE sat_customer_details (
    customer_hub_key  TEXT REFERENCES hub_customer(customer_hub_key),
    load_date         TEXT NOT NULL,
    record_source     TEXT NOT NULL,
    customer_name     TEXT,
    email             TEXT,
    city              TEXT,
    PRIMARY KEY (customer_hub_key, load_date)
);
```

Notice what's conspicuously absent from the hub and link tables: no descriptive attribute is ever mixed in with a business key or a relationship. That separation is deliberate, and it's the entire mechanism behind the next section.

---

## 3. Why This Enables Massive Load Parallelism

Because hubs, links, and satellites are **insert-only** (nothing is ever updated or deleted — a changed attribute is just a new satellite row with a later `load_date`), and because a hub never contains anything that could conflict with another hub's load, **every hub, link, and satellite can be loaded independently and in parallel**, from any number of source systems, without needing to coordinate or lock against each other. A new source system that has its own idea of "customer" just writes its own satellite rows against the same hub — it doesn't need to renegotiate the shape of `hub_customer` or wait for another team's load to finish. This is the load-time property Kimball dimensional models don't have: a conformed dimension (`interview_questions/04_curveballs_tradeoffs.md`) requires the *business rule* for what a customer is to be agreed and centralized before loading; Data Vault defers that agreement to query time instead, by design.

---

## 4. Where It Fits Relative to Kimball

Data Vault is not a replacement for the star schemas in concepts 01-05 — in the architectures that actually use it, it sits **underneath** them:

```text
Source systems (many, disagreeing, evolving)
        |
        v
  DATA VAULT layer  <- hubs/links/satellites, insert-only, parallel-loadable,
        |               source of truth, never redesigned when business rules change
        v
  Kimball star schemas  <- built ON TOP of the vault by a separate transformation
  (dim_*/fact_*)            step, once business rules ARE agreed — this is the
        |                    layer analysts and BI tools actually query
        v
   BI tools / analysts
```

The star schema is still where query-time simplicity lives; Data Vault just insulates the *loading* layer from having to be redesigned every time a source system changes or a new one is onboarded.

---

## 5. When (Rarely) This Is the Right Interview Answer

For nearly every "design a data model for X" prompt in `interview_questions/01_worked_scenarios.md`, Data Vault is the wrong answer to lead with — it solves a large-enterprise, many-source-systems, fast-changing-business-rules loading problem that most interview prompts don't describe. Leading with hubs/links/satellites when asked to design a ride-sharing analytics schema reads as pattern-matching a fancy term onto a problem that doesn't have it, which is a worse signal than not knowing the term at all.

The right moment to bring it up unprompted is a **curveball that specifically describes the problem it solves** — e.g., "we have twelve source systems that all disagree about what a customer is, and the business rules for reconciling them change every quarter" (a variant of the conformed-dimension curveball in `interview_questions/04_curveballs_tradeoffs.md`). There, naming Data Vault as "how you'd insulate the loading layer while a separate, slower-moving process builds the conformed dimension on top" is a strong, senior-level answer. Otherwise, the one-sentence definition — "hubs for business keys, links for relationships, satellites for attributes and history, all insert-only for load parallelism, sitting underneath a Kimball layer rather than replacing it" — is enough to show you know it exists and why, without over-indexing on it.

---

## Key Takeaways

- Data Vault optimizes for load-time flexibility and parallelism across many disagreeing, evolving source systems; Kimball dimensional modeling optimizes for query-time simplicity. They solve different problems and are usually layered, not competing.
- Hubs hold only business keys; links hold only relationships between hubs; satellites hold the descriptive attributes and history, versioned by load date — never mix a business key or relationship with a descriptive attribute.
- Because hubs/links/satellites are insert-only and never mix concerns, every piece can be loaded independently and in parallel, without needing a settled, agreed-upon business rule first.
- In practice, a Data Vault (if present) sits underneath a Kimball star schema — the vault is the resilient loading/source-of-truth layer; the star schema on top is what analysts and BI tools actually query.
- Reach for this term only when a prompt specifically describes its problem (many disagreeing source systems, fast-changing reconciliation rules) — otherwise, naming it briefly when asked "what else is out there" is enough.
