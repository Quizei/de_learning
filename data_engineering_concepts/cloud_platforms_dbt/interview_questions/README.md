# Interview Questions: Platforms, Pipelines, and dbt by Name

dbt is one of the few tools in data engineering interviews that gets
asked about *by name* — "have you used dbt," "walk me through a dbt
project you built," "what's your incremental strategy" — often before
the interviewer even asks which warehouse you've worked with. Cloud
platform questions ("Snowflake vs. BigQuery for X," "why is this query
scanning so much data") are just as common, and the two topics show up
together constantly, since almost every real dbt project runs against
exactly one of these three warehouses.

Every file here is **deliberately code-free** — no `CREATE` statements,
no SQL, no Jinja. The `concepts/` and `practice/` folders one level up
cover the implementation; this folder covers the *conversation* — the
reasoning an interviewer is actually scoring when they ask "design a
dbt project" or "why is this warehouse bill so high." Once that
reasoning is solid, writing the SQL/YAML for it is the easy part.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Scenarios](01_worked_scenarios.md) | "Design/diagnose X" — full worked walkthroughs: structuring a dbt project, choosing a warehouse for a specific workload, and diagnosing a slow, expensive nightly run |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions with no scenario attached — a phone-screen drill, cross-referenced back to `concepts/` and file 1 |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "What's wrong with this?" — classic dbt/warehouse bugs: a broken `is_incremental()` condition, a missing `unique_key`, unconfigured auto-suspend, a clustering key chosen for the wrong query pattern |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed — environments/targets, schema changes mid-incremental, CI cost, PII handling, dbt Cloud vs. Core |
| 5 | [dbt Project Structure & Testing Strategy](05_dbt_project_structure_and_testing.md) | A dedicated drill on the single most common practical dbt question — how you'd actually organize and test a real project, end to end |

## How to Use This

- **First pass:** read file 1 straight through once, including every
  hidden debrief, to see the full reasoning modeled end to end across
  three different scenario shapes.
- **Drilling:** come back to files 3 and 4 and actually answer out loud
  (or write it down) before expanding the hidden debrief/model answer —
  the value is in producing the reasoning yourself, not in recognizing
  it when you read it.
- **Quick review before an interview:** file 2 alone is a fast pass over
  every term; file 5 is a five-minute read specifically for "how do you
  structure a dbt project," which comes up in some form in nearly every
  dbt-adjacent interview.

## Question Types This Covers

- Open-ended design/diagnosis prompts ("structure a project," "choose a
  platform," "diagnose this slow run") — file 1
- Definitional/vocabulary checks ("what's the difference between...") — file 2
- Debugging/critique ("what's wrong with this model / this bill") — file 3
- Trade-off follow-ups that push on an assumption mid-conversation — file 4
- Project-structure and testing-strategy mechanics, asked on their own
  often enough to warrant a dedicated file — file 5

If a question you've actually been asked doesn't fit cleanly into any of
these five files, that's worth noting — it likely means a sixth shape
worth adding here.
