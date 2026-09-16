# Interview Questions: Design It, Then Operate It

Workflow orchestration interviews test two different things, and most candidates are only
ready for one of them: **can you design a DAG** (dependencies, scheduling, failure modes),
and **have you actually operated one in production** (a DAG paging on-call at 3am, a
backfill that has to run without doubling compute, a sensor quietly eating a worker pool
for hours). This folder is built to drill both.

Every file here is **deliberately code-free** — no DAG definitions, no Python. The
`concepts/` and `practice/` folders one level up cover the implementation; this folder
covers the *conversation* — the reasoning an interviewer is actually scoring when they ask
an orchestration question out loud.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Scenarios](01_worked_scenarios.md) | "Design the DAG for X" / "walk me through what you'd do" — full mock-interview walkthroughs |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions, no scenario attached |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "What's wrong with this DAG?" — diagnose a flawed design or a bad on-call symptom from a plain-English description |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed |
| 5 | [On-Call & Incident Triage](05_oncall_incident_triage.md) | The operational-maturity drill: a DAG just paged you — what do you actually do, in order, before you've even opened the code |

## How to Use This

- **First pass:** read file 1 straight through once, including every hidden debrief, to
  see the reasoning modeled end to end across different scenario shapes.
- **Drilling:** come back to files 3, 4, and 5 and actually answer out loud (or write it
  down) before expanding the hidden debrief — the value is in producing the reasoning
  yourself, not recognizing it once it's written.
- **Quick review before an interview:** file 2 alone is a fast pass over every term; file 5
  alone is a fast pass specifically for "have you operated this for real" questions, which
  come up disproportionately often once a role is titled senior or has any on-call
  expectation attached.

## Question Types This Covers

- Open-ended design prompts ("design the DAG for...") — file 1
- Definitional/vocabulary checks ("what's the difference between...") — file 2
- Debugging/critique ("what's wrong with this DAG / why did this fail silently") — file 3
- Trade-off follow-ups that push on an assumption mid-conversation — file 4
- Operational/incident-response reasoning (triage order, rollback vs. fix-forward, when to
  page someone else) — file 5

If a question you've actually been asked doesn't fit cleanly into any of these five files,
that's worth noting — it likely means a sixth shape worth adding here.
