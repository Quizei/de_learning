# Interview Questions: Detect It, Govern It, Then Handle It Breaking Anyway

Data quality and governance questions show up in almost every mid-level and senior data engineering interview loop, often as a single dedicated round ("how do you know your pipeline didn't silently break?") and just as often folded into a system-design question as a follow-up nobody warned you was coming. This folder drills every shape that question tends to take.

`concepts/` and `practice/` one level up cover the implementation — how to write a completeness check, how a data contract's schema-diff logic works, how anomaly detection compares a run against its own history. This folder covers the *conversation* — the reasoning an interviewer is actually scoring when they hand you an open-ended prompt, a broken check, or a stakeholder who's already upset. Once that reasoning is solid, the checks and code are the easy part.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Design Scenarios](01_worked_scenarios.md) | "Design a data quality framework / investigate this / fix this process" — full worked walkthroughs (a from-zero quality framework for 200 tables, a "why is this dashboard wrong" investigation, a schema contract negotiation with an upstream team), two with a self-practice companion scenario |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions with no scenario attached — a phone-screen drill, cross-referenced back to `concepts/` and file 1 |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "What's wrong with this check / this process?" — diagnose a flawed validation, contract, or monitoring setup from a plain-English description |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed — hard-gating every check, contract friction, catalog ROI, monitoring coverage gaps, dimension ownership, a single quality score |
| 5 | [Responding to a Data Incident](05_incident_response.md) | The question every other file assumes you'd prevented: something is *already* wrong in production right now — triage, containment, root-cause search, the backfill decision, stakeholder communication, and the postmortem that actually leads to a fix |

## How to Use This

- **First pass:** read file 1 straight through once, including every hidden debrief, to see the full reasoning modeled end to end across three realistic scenarios.
- **Drilling:** come back to file 1's "Now You Try" scenarios, file 3, file 4, and file 5, and actually answer out loud (or write it down) before expanding the hidden debrief/model answer — the value is in producing the reasoning yourself, not in recognizing it when you read it.
- **Quick review before an interview:** file 2 alone is a fast pass over every term; files 3 and 4 are a fast pass over every "gotcha" shape; file 5 is worth a dedicated read the night before, since it's the one shape candidates prepare for least and get asked about most in any role with real on-call exposure.

## Question Types This Covers

- Open-ended design prompts ("design a quality framework / a contract process for...") — file 1
- Definitional/vocabulary checks ("what's the difference between...") — file 2
- Debugging/critique ("what's wrong with this check / this report") — file 3
- Trade-off follow-ups that push on an assumption mid-conversation — file 4
- Live-incident reasoning ("this is already broken in production, what do you do right now") — file 5

If a question you've actually been asked doesn't fit cleanly into any of these five files, that's worth noting — it likely means a sixth shape worth adding here.
