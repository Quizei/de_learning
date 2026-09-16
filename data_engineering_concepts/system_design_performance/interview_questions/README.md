# Interview Questions: System Design & Performance

This is the flagship interview folder in this course. "Design a data pipeline
for X" is *the* signature senior/mid-level data engineering system-design
question — it's usually the last, and hardest, round in a DE interview loop,
and it's explicitly where the interviewer checks whether you can combine
everything else you claimed to know (data modeling, ETL/ELT, warehousing,
streaming) into one coherent, defensible design under time pressure.

Every file here is **deliberately code-free** where the reasoning is being
tested — no CREATE statements, no Spark code, no Python. `../concepts/` and
`../practice/` cover the mechanics; this folder covers the *conversation*: how
you scope a problem, justify an architecture, narrate trade-offs, and survive
a curveball follow-up. Get the reasoning solid here and reaching for a real
config (which this folder still shows plenty of, inline, exactly as an
interviewer would expect you to name real technologies) is the easy part.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Scenarios](01_worked_scenarios.md) | Full mock interviews — "design a pipeline for X" — clarifying questions → architecture → component trade-offs → narrated data flow → how it scales/fails, with a hidden debrief. Three fully worked plus one "now you try." |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions, no scenario attached — a phone-screen drill across every concept in this folder |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "Here's an architecture — what's wrong with it, or what breaks at 10x scale?" |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed |

## How to use this

- **First pass:** read file 1 straight through, including the hidden debriefs, to see the full reasoning modeled end to end — this is the format every other file assumes you've internalized.
- **Drilling:** come back to file 1's "now you try" scenario, and files 3 and 4, and actually answer out loud (or write it down) before expanding the hidden answer.
- **Quick review before an interview:** file 2 alone is a fast pass over every term; files 3 and 4 are a fast pass over every "gotcha" shape you're likely to hit.

## Prerequisites

This topic assumes and combines four others — if any of these feel shaky, the
worked scenarios in file 1 will expose it fast:

- `data_modeling` — every design here needs a defensible schema (star schema,
  grain, SCD choice) as its data-model layer.
- `etl_elt_patterns` — the batch/transform side of any pipeline you design.
- `data_warehousing_lakes` — where the data lands and how it's queried.
- `streaming_real_time` — the mechanics behind any "real-time" requirement
  (Kafka, windowing, watermarks) that a scenario here will assume you know
  rather than re-teach.

## Question types this covers

- Open-ended design prompts ("design a pipeline for...") — file 1
- Definitional/vocabulary checks ("what's the difference between...") — file 2
- Debugging/critique ("what's wrong with this architecture / why does this
  break at scale") — file 3
- Trade-off follow-ups that push on an assumption mid-conversation — file 4
- Capacity estimation and cost reasoning (`../concepts/04_capacity_planning_and_cost.md`)
  woven through every worked scenario in file 1, since a design without
  numbers behind it doesn't read as senior-level

If a question you've actually been asked doesn't fit cleanly into any of
these four files, that's worth noting — it likely means a fifth shape worth
adding here.
