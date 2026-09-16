# Concept 05: Kimball vs. Inmon vs. Data Vault — Warehouse Architecture Philosophy

**Covers:**
- Kimball's bottom-up, dimensional-marts-first philosophy — and its real risk
- Inmon's top-down, normalized-enterprise-warehouse-first philosophy — and its real cost
- Data Vault as a third *architectural* option built to decouple "start loading" from "agree on the business rules" — not just a modeling pattern
- The bus matrix as the practical tool that makes Kimball's bottom-up approach avoid Kimball's classic failure mode
- A decision framework: which philosophy for which organization, stated as trade-offs an interviewer can push back on

> **Scope note:** this file is about warehouse architecture as an organizational/methodological choice — *how you build and roll out* a warehouse across an organization. `data_modeling/concepts/06_data_vault_modeling.md` already covers Data Vault's hub/link/satellite table design in full mechanical depth (with runnable SQL); this file does not repeat that. Read that file for "how do you write a Data Vault schema"; read this one for "why would an organization choose Data Vault at all, and how does that choice compare to choosing Kimball or Inmon."

---

## 1. Kimball: Bottom-Up, Dimensional Marts First

Ralph Kimball's approach builds one **data mart** at a time — a star schema (`data_modeling/concepts/02_dimensional_modeling.md` and `03_star_snowflake_schema.md`) scoped to one business process (sales, shipments, support tickets) — and ships it fast, before attempting anything enterprise-wide.

```text
   Sales mart          Marketing mart         Support mart
  (star schema)         (star schema)        (star schema)
       |                     |                     |
       +---------------------+---------------------+
                             |
              (ideally) shares conformed dimensions:
                 dim_customer, dim_date, dim_product
```

**Why teams choose it:** a single mart can be designed, built, and delivering value in weeks, not months — a fast-growing startup with three teams (sales, marketing, product), no existing warehouse, and a CEO who wants a dashboard by end of quarter is the textbook Kimball scenario. Star schemas are also simply easier for business users and analysts to reason about than a fully normalized enterprise model.

**Its real risk, stated precisely (not just "it's less consistent"):** if each mart is built independently without an upfront agreement on what shared dimensions mean, two marts can each define "customer" or "product category" slightly differently, and there's no single place that agreement was supposed to live. This is the exact failure mode worked through mechanically in `data_modeling/interview_questions/03_critique_and_debug.md`, Case 8 (two teams' One Big Tables silently disagreeing on customer segment) and `data_modeling/interview_questions/04_curveballs_tradeoffs.md`'s bus-matrix curveball — Kimball doesn't force this failure, but it doesn't prevent it either unless something else does.

**The fix Kimball itself prescribes:** the **bus matrix** — a planning artifact filled in *before* any mart is built, with business processes as rows and shared dimensions as columns, marking which processes use which dimensions. Any dimension used by more than one process gets built once, centrally, as a **conformed dimension**, and every mart references that one definition rather than re-deriving its own. A bus matrix is what turns "bottom-up, fast, and risky" into "bottom-up, fast, and still consistent" — it's the one piece of process discipline that makes Kimball's speed advantage sustainable at more than one mart.

```text
                    dim_date   dim_customer   dim_product   dim_employee
Sales process           X            X              X
Shipments process       X            X              X            X
Support tickets         X            X                            X

-- Any column with more than one X: build that dimension ONCE, centrally,
-- before either mart is built. This is the artifact that prevents the
-- "two marts silently disagree" failure mode.
```

---

## 2. Inmon: Top-Down, Normalized Enterprise Warehouse First

Bill Inmon's approach inverts the order: build one **normalized (3NF), enterprise-wide warehouse** first, as the single source of truth, and derive dimensional data marts *from* it afterward, only once the central model exists.

```text
        All source systems
               |
               v
   Enterprise Data Warehouse (3NF, normalized,
   subject-oriented, integrated, non-volatile)
               |
       +-------+-------+
       |       |       |
  Sales mart  Marketing mart  Support mart
  (derived, dimensional, built AFTER the EDW)
```

**Why organizations choose it:** a large bank with 50+ departments and strict regulatory requirements needs "what is a customer" to mean one thing enterprise-wide, non-negotiably, before any department starts building on it — the upfront normalization *is* the mechanism that enforces that consistency, not a best-effort agreement layered on after the fact. This trades speed for structural guarantees: with a dedicated data team and an 18-month timeline, that trade is often the correct one.

**Its real cost, stated precisely:** the enterprise warehouse has to be designed and built before *any* department gets value from it, and because everything downstream depends on this shared normalized core, changes to it ripple outward — adding or restructuring an entity in the EDW can require touching every mart derived from it. This is the direct trade-off against Kimball's "add a new mart without re-touching the others" flexibility.

---

## 3. Data Vault: Decoupling "Start Loading" From "Agree on the Rules"

Data Vault (Dan Linstedt) is neither purely bottom-up nor purely top-down — it exists to solve a problem that shows up regardless of which of the above two philosophies an organization otherwise favors: **what do you do when data needs to start loading from several source systems today, but the business rules for reconciling those sources into one canonical definition aren't finalized yet, and can't be, without stalling ingestion for months?**

The mechanical answer (full DDL and worked examples: `data_modeling/concepts/06_data_vault_modeling.md`) is to split entities into three kinds of tables — **hubs** (business keys only), **links** (relationships between hubs), and **satellites** (descriptive attributes, versioned by load date) — structured so that loading from a new source is purely additive: new hub rows, new satellite rows, tagged by source, with no requirement to agree on a single canonical definition before the load can happen at all.

```text
   CRM A  ---\
   CRM B  ----+--> hub_customer + sat_customer_details (per source, in parallel)
   CRM C  ---/          |
                         |  (once reconciliation rules ARE agreed)
                         v
              conformed dim_customer  <-- a Kimball star-schema layer,
              (one canonical customer)     built ON TOP of the vault
```

**Why this is an architecture-level choice, not just a schema pattern:** the organizational consequence is that ingestion and business-rule agreement become two *decoupled* workstreams. Three source systems that each define "customer" differently can all start loading today, in parallel, with no source blocked waiting on another — and once the reconciliation rules are eventually agreed, a separate transformation step builds the conformed dimensional layer (the Kimball star schema business users actually query) on top of the vault, without having to re-ingest anything. This is precisely the scenario worked through in `data_modeling/interview_questions/04_curveballs_tradeoffs.md`'s Data Vault curveball and `data_modeling/practice/exercises.md`, Exercise 15.

**Its real cost:** a Data Vault layer is rarely queried directly by analysts — it's a loading/integration layer, not a reporting layer, so most organizations that adopt it are explicitly committing to building and maintaining *two* modeling layers (the vault, plus a Kimball star-schema layer derived from it), not one. That's a real, ongoing engineering cost that only pays off at a scale (many fast-changing, disagreeing source systems) where the alternative — blocking ingestion on a fully agreed schema, or letting inconsistent marts multiply — is worse.

---

## 4. The Decision, as a Table

| | Kimball | Inmon | Data Vault |
|---|---|---|---|
| Direction | Bottom-up (marts first) | Top-down (EDW first) | Neither — decouples loading from modeling |
| Schema style | Dimensional (star) throughout | Normalized (3NF) core, dimensional marts derived | Hub/link/satellite loading layer + a Kimball layer on top |
| Time to first value | Weeks (one mart) | Months (full EDW) | Fast to *start loading*; conformed reporting layer still takes time |
| Consistency risk | Marts can silently disagree without a bus matrix | Enforced structurally by the normalized core | Loading layer never disagrees (it doesn't reconcile); the derived reporting layer inherits the risk of whichever conforming logic builds it |
| Best fit | Agile teams, fast delivery, willing to run a bus matrix | Large enterprises, strict governance, dedicated long-timeline team | Many fast-changing/disagreeing source systems, reconciliation rules not yet finalized, ingestion can't wait |
| Modern relevance | Standard default for most cloud warehouses/marts | Enterprise DW layers, regulated industries | Large-scale integration layers feeding a Kimball reporting layer |

**How this gets asked, and how to answer it well:** an interviewer asking "Kimball vs. Inmon vs. Data Vault" is rarely testing whether you can recite three definitions — they're testing whether you can match a philosophy to an organizational constraint (team size, timeline, number of disagreeing source systems, regulatory pressure) and name the real trade-off, not just the real benefit, of whichever one you pick. "I'd default to Kimball with a bus matrix unless X" is a stronger answer than naming any one methodology as universally correct.

---

## Key Takeaways

- Kimball builds dimensional marts bottom-up, fast — its real risk is marts silently disagreeing on shared dimensions, and the fix (not just an ideal) is a bus matrix agreed before marts are built.
- Inmon builds a normalized enterprise warehouse top-down first — its real cost is a longer time-to-first-value and ripple effects when the shared normalized core changes.
- Data Vault decouples "start loading data" from "agree on reconciliation rules" via hubs/links/satellites, letting multiple disagreeing source systems load in parallel today, with a conformed Kimball layer built on top once rules are finalized — at the ongoing cost of maintaining two modeling layers instead of one.
- None of the three is universally correct; the interview-strong answer names the organizational constraint that decides it (team size, timeline, governance requirements, number of disagreeing sources) rather than picking a favorite.
- For Data Vault's actual hub/link/satellite table design and SQL, see `data_modeling/concepts/06_data_vault_modeling.md` — this file is the "why choose this architecture" companion to that file's "how do you build it."
