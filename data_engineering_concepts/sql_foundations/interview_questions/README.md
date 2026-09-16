# Interview Questions: Query It Live

Every SQL interview is, in the end, a live-coding round: someone hands you
a schema and a business question and watches you think. The four files
here drill the four recognizably different shapes that round takes.
`concepts/` and `practice/` one level up teach the underlying material —
this folder is where you rehearse *performing* it under the exact
conditions of a real interview: talking while you type, catching your own
mistakes, and reasoning out loud about trade-offs you didn't choose.

| # | File | Question shape |
|---|------|-----------------|
| 1 | [Worked Scenarios](01_worked_scenarios.md) | "Write this query live" — a shared schema, five fully narrated business questions each with a realistic wrong-first-attempt, plus one self-practice scenario with a hidden debrief |
| 2 | [Rapid-Fire Q&A](02_rapid_fire_qna.md) | Fast conceptual questions with no schema attached — a phone-screen drill across joins, window functions, aggregation, subqueries/CTEs, NULLs, indexing, and transactions |
| 3 | [Critique & Debug](03_critique_and_debug.md) | "Here's a query — its output is wrong / it's slow, find the bug or the missing index" — six cases against a correct schema (unlike data modeling's schema critiques, the schema here is never the problem) |
| 4 | [Curveballs & Trade-offs](04_curveballs_tradeoffs.md) | Mid-conversation follow-ups that push on one assumption of a query you just wrote — duplicate sort keys, pagination at scale, concurrent writes, skew, cycle detection |

## How this differs from data modeling's interview practice

If you've already been through
[`data_modeling/interview_questions/`](../../data_modeling/interview_questions/),
this folder will feel familiar in shape (worked scenario / rapid-fire /
critique / curveballs) — deliberately so, since it's the same four
question modes a SQL round uses. The difference is what's being tested:
data modeling's files are almost entirely code-free, scoring how you
**design** a schema and reason about grain, SCDs, and fact table types.
This folder assumes the schema already exists and is correct — every file
here is about **querying** it: writing real SQL, reading real (simulated)
output, and debugging real query mistakes, not schema mistakes. If a
question is really about "what table should this be," that's data
modeling's territory, not this one.

## How to use this

- **First pass:** read [file 01](01_worked_scenarios.md) straight through
  once, including its "wrong first attempt" narrations, to see what a
  strong live-coding answer actually sounds like out loud.
- **Drilling:** come back to file 01's "Now You Try" scenario, and to
  files 3 and 4, and actually write the query / answer out loud before
  expanding the hidden solution — the value is in producing the query
  yourself under a little pressure, not in recognizing a correct one when
  you read it.
- **Quick review before an interview:** file 2 alone is a fast pass over
  every term; files 3 and 4 are a fast pass over every "gotcha" shape.

## Question types this covers

- Live query-writing against a given schema, narrated, including
  recovering from a realistic wrong first attempt — [file 01](01_worked_scenarios.md)
- Fast definitional/vocabulary checks — [file 02](02_rapid_fire_qna.md)
- Debugging a wrong-output or slow query someone else wrote — [file 03](03_critique_and_debug.md)
- Trade-off follow-ups that push on an assumption mid-conversation — [file 04](04_curveballs_tradeoffs.md)

If a question you've actually been asked doesn't fit cleanly into any of
these four files, that's worth noting — it likely means a fifth shape
worth adding here.
