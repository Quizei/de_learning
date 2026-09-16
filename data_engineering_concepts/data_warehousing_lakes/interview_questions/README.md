# Interview Questions: Design the Storage, Then Defend It

Data warehousing and data lake questions show up in mid-level data
engineering interviews in a narrower but no less common shape than data
modeling: "design the storage layout for X," "warehouse or lakehouse,
and why," or "here's a slow query — what's wrong with the physical
layout." This folder drills that conversation specifically — the
`concepts/` and `practice/` folders one level up cover the vocabulary
(partitioning, file formats, table formats, lake zones); this folder
covers the reasoning an interviewer is actually scoring when they ask
about it out loud.

Every file here is **deliberately code-free** — no `CREATE` statements,
no SQL, no Python. The point is to rehearse describing a storage layout,
a format choice, and a trade-off in plain language, the way you'd
actually do it in an interview room or on a call.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Scenarios](01_worked_scenarios.md) | "Design the storage layout for X" / "warehouse or lakehouse, and why" — full worked walkthroughs, including diagnosing a slow query from its physical layout |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions with no scenario attached |
| 3 | [Critique & Debug](03_critique_and_debug.md) | Classic warehousing/lake bugs — over-partitioning, wrong partition column, bucketing chosen for the wrong join — diagnosed from a plain-English description |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed |
| 5 | [Lakehouse Table Format Trade-offs](05_lakehouse_table_format_tradeoffs.md) | A dedicated drill on Iceberg/Delta/Hudi — how often this specific comparison comes up on its own now |

## How to Use This

- **First pass:** read file 1 straight through once, including the
  hidden debriefs, to see the reasoning modeled end to end.
- **Drilling:** come back to files 3 and 4 and actually answer out loud
  (or write it down) before expanding the hidden answer — the value is
  in producing the diagnosis yourself, not recognizing it when you read
  it.
- **Quick review before an interview:** file 2 is a fast pass over every
  term; file 5 is a fast, focused pass over the one topic (lakehouse
  table formats) that comes up disproportionately often relative to how
  recently it became standard interview material.

## Question Types This Covers

- Open-ended storage/architecture design ("design the layout for...",
  "warehouse or lakehouse for...") — file 1
- Definitional/vocabulary checks — file 2
- Debugging/critique of a physical layout or a slow query — file 3
- Trade-off follow-ups that push on an assumption mid-conversation —
  file 4
- A focused drill on one increasingly common sub-topic — file 5

If a question you've actually been asked doesn't fit cleanly into any of
these five files, that's worth noting — it likely means a sixth shape
worth adding here.
