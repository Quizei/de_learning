# Interview Questions: Design It, Diagnose It, Then Defend It

Streaming and real-time system questions show up in mid-to-senior data engineering interviews in two distinct flavors: "design a real-time pipeline for X" (an open-ended design conversation) and "here's a broken/slow/duplicating streaming system, what's wrong with it" (a diagnosis conversation). Both get scored on the same underlying thing: whether you actually understand event time, windowing, delivery guarantees, and partitioning well enough to reason about a *specific* scenario, not just recite Kafka vocabulary.

Every file here is **deliberately code-free** — no `CREATE` statements, no Python, no Kafka config blocks. The `concepts/` and `practice/` folders one level up cover the implementation; this folder covers the *conversation* — the reasoning an interviewer is actually scoring when they ask a streaming question.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Design Scenarios](01_worked_scenarios.md) | "Design a real-time pipeline for X" and "here's a broken system, diagnose it live" — full mock-interview walkthroughs with hidden debriefs |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast definitional questions with no scenario attached — a phone-screen drill |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "What's wrong with this?" — classic streaming bugs described in plain prose |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of whatever you just designed |
| 5 | [Does This Even Need to Be Real-Time?](05_does_this_need_to_be_real_time.md) | The meta-question underneath most streaming interviews: recognizing when the right answer is "no, batch is fine" |

## How to Use This

- **First pass:** read file 1 straight through once, including every hidden debrief, to see the full reasoning modeled end to end across several scenario types.
- **Drilling:** come back to file 1's scenarios, file 3, and file 4 and actually answer out loud (or write it down) before expanding the hidden debrief — the value is in producing the reasoning yourself, not in recognizing it when you read it.
- **Quick review before an interview:** file 2 alone is a fast pass over every term; file 3 is a fast pass over every classic streaming bug; file 5 is a five-minute read on the single most common trap in this whole topic — over-engineering a batch problem into a streaming one.

## Question Types This Covers

- Open-ended design prompts ("design a real-time pipeline that...") — file 1
- Live diagnosis of a described symptom (a rebalancing consumer group, a stuck pipeline) — file 1
- Definitional/vocabulary checks ("what's the difference between...") — file 2
- Debugging/critique ("what's wrong with this consumer/this aggregation") — file 3
- Trade-off follow-ups that push on an assumption mid-conversation — file 4
- Recognizing when a "streaming" requirement is actually a batch problem in disguise — file 5

If a question you've actually been asked doesn't fit cleanly into any of these five files, that's worth noting — it likely means a sixth shape worth adding here.
