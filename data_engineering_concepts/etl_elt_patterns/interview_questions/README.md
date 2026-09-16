# Interview Questions: Design It, Then Defend It

ETL/ELT is the core job of a data engineer, and interview questions about it come in a recognizably different shape from data modeling's "design a schema" prompts: they're mostly about **pipeline architecture and reasoning under failure** — how you'd extract, how you'd make a load safe to re-run, what happens when data arrives late or a source changes shape underneath you. This folder drills that conversation.

Unlike `data_modeling/interview_questions/`, this folder is not fully code-free — ETL/ELT rounds are architecture/reasoning-heavy like data modeling, but a short snippet (a watermark query, a merge statement, a retry loop) is shown wherever it's the fastest way to make a pattern concrete. The `concepts/` and `practice/` folders one level up cover full implementations; this folder covers the conversation an interviewer is actually scoring.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Design Scenarios](01_worked_scenarios.md) | "Design a pipeline for X" — full worked walkthroughs (clarifying questions → extraction strategy → load strategy → failure handling → narrated trade-offs), with "Now You Try" companions |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions with no scenario attached |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "What's wrong with this pipeline?" — diagnose a flawed design or a wrong number from a plain-English description |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed |
| 5 | [Idempotency & Exactly-Once Reasoning](05_idempotency_and_exactly_once.md) | A dedicated drill on the single most commonly-misunderstood ETL concept: what "exactly-once" actually means, and where it breaks |

## How to Use This

- **First pass:** read file 1 straight through once, including every hidden debrief, to see the reasoning modeled end to end across several pipeline scenarios.
- **Drilling:** come back to file 1's "Now You Try" scenarios, file 3, and file 4, and actually answer out loud (or write it down) before expanding the hidden answer — the value is in producing the reasoning yourself, not recognizing it when you read it.
- **Quick review before an interview:** file 2 alone is a fast pass over every term; file 3 is a fast pass over every classic ETL bug; file 5 is worth a slow read once, since it's the concept most candidates can recite but few can reason about correctly under a follow-up.

## Question Types This Covers

- Open-ended design prompts ("design a pipeline that...") — file 1
- Definitional/vocabulary checks ("what's the difference between...") — file 2
- Debugging/critique ("what's wrong with this pipeline / this number") — file 3
- Trade-off follow-ups that push on an assumption mid-conversation — file 4
- Reasoning about failure semantics (exactly-once vs. at-least-once, idempotent side effects) — file 5

If a question you've actually been asked doesn't fit cleanly into any of these five files, that's worth noting — it likely means a sixth shape worth adding here.
