# Interview Questions: Design It, Then Query It

Data modeling is the single most-tested topic in mid-level data engineering
interviews — every company that runs a warehouse asks some version of
"design a data model for X," and the follow-ups that come after your
design are where most candidates actually lose points. This folder is
built to drill both halves.

Every file here is **deliberately code-free** — no `CREATE` statements, no
SQL, no Python. The `concepts/` and `practice/` folders one level up cover
the implementation; this folder covers the *conversation* — the reasoning
an interviewer is actually scoring when they ask a data modeling question.
Once that reasoning is solid, writing the SQL for it is the easy part.

Data modeling interview questions come in a handful of recognizably
different shapes. Each file below drills one shape:

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Design Scenarios](01_worked_scenarios.md) | "Design a data model for X" — full worked walkthroughs (clarifying questions → grain → dimensions/facts → schema shape → SCD choice → querying it out loud) across nine industries, several with a self-practice companion scenario |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions with no scenario attached — a phone-screen drill, cross-referenced back to the moment each term showed up in file 1 |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "What's wrong with this?" / "Why is this report wrong?" — diagnose a flawed model or a bad number from a plain-English description |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed — mini-dimensions, conformed dimensions, partitioning, real-time, testing, the bus matrix, schema evolution |
| 5 | [Whiteboarding & Stakeholder Communication](05_whiteboarding_and_stakeholder_communication.md) | The meta-skills: budgeting a 45-minute design interview under time pressure, and explaining a design decision to someone who doesn't know what a fact table is |

## How to Use This

- **First pass:** read file 1 straight through once, including every
  hidden debrief, to see the full reasoning modeled end to end across
  nine different industries.
- **Drilling:** come back to file 1's "Now You Try" scenarios, file 3,
  and file 4 and actually answer out loud (or write it down) before
  expanding the hidden debrief/model answer — the value is in producing
  the reasoning yourself, not in recognizing it when you read it.
- **Quick review before an interview:** file 2 alone is a fast pass over
  every term; files 3 and 4 are a fast pass over every "gotcha" shape;
  file 5 is a five-minute read right before you walk in.

## Question Types This Covers

- Open-ended design prompts ("design a data model for...") — file 1
- Definitional/vocabulary checks ("what's the difference between...") — file 2
- Debugging/critique ("what's wrong with this schema / this number") — file 3
- Trade-off follow-ups that push on an assumption mid-conversation — file 4
- Query reasoning against a schema you just designed (narrated, not
  written) — embedded in every scenario in file 1
- Interview-format mechanics (time budgeting, explaining to a
  non-technical stakeholder) — file 5

If a question you've actually been asked doesn't fit cleanly into any of
these five files, that's worth noting — it likely means a sixth shape
worth adding here.
