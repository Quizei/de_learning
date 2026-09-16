# 5. Whiteboarding Under Time Pressure & Explaining It to a Stakeholder

Part of the [Interview Questions](README.md) series.

Files 1-4 drill the *content* of a data modeling interview — grain,
schema shape, SCD choice, critique, trade-offs. This file drills two
adjacent skills that are scored just as heavily but rarely named
explicitly: **budgeting your time** in a live whiteboard/verbal design
interview so you don't run out of clock before reaching the interesting
parts, and **translating a design decision into plain language** for
someone who will never look at a schema diagram. Both come up in nearly
every senior/mid-level data engineering loop, and neither is something
`concepts/` or the worked scenarios in file 1 teach on their own — they
teach *what* to say; this file is about *how* and *when* to say it.

---

## Part A: Budgeting a Design Interview Under Time Pressure

A live "design a data model for X" round is usually 30-45 minutes,
shared between design and questions, and the single most common failure
mode isn't a wrong schema — it's running out of time while still asking
clarifying questions, or rushing the schema so badly that the query
walkthrough (where a lot of the scoring actually happens) gets cut.

### A rough time budget for a 45-minute round

```text
0:00 - 0:05   Restate the prompt, ask clarifying questions (Step 1 in
              every scenario in file 1). Don't skip this to "save time" —
              skipping it is a bigger loss than spending 5 minutes here.

0:05 - 0:08   State the grain(s) explicitly, out loud, before drawing
              anything. This is cheap and disproportionately scored.

0:08 - 0:20   Sketch the schema shape: dimensions, measures, fact
              table(s), the ASCII-diagram level of detail from file 1 —
              not full DDL. Narrate WHY as you draw, don't draw silently.

0:20 - 0:25   State the SCD decision(s) explicitly, unprompted, before
              being asked. This is the single most commonly-probed
              follow-up — volunteering it early buys you credit and
              often heads off a whole line of questioning.

0:25 - 0:38   Query walkthrough: 3-4 business questions, narrated in
              plain language (joins/filters/aggregations), not written
              as SQL unless explicitly asked to write SQL.

0:38 - 0:43   Trade-offs, stated unprompted (Step 7 in every scenario in
              file 1) — what you'd do differently under a different
              constraint, what you deliberately simplified and why.

0:43 - 0:45   Buffer / whatever the interviewer wants to push on.
```

The two phases candidates most often shortchange under pressure are the
**first 5 minutes** (skipping clarifying questions to look fast, which
reads as a red flag rather than as speed) and the **query walkthrough**
(rushing the schema so long that there's no time left to show you can
actually use it) — both are addressed explicitly in the budget above by
capping schema-drawing time and protecting the query section.

### If you're running out of time mid-interview

Say so, explicitly, rather than silently rushing or silently dropping
something: *"I'm going to keep the location dimension simple and flag
that I'd revisit it if we had more time, so I can get to the query
questions"* is a strong, senior thing to say — it demonstrates time
awareness as a skill in itself, which many interviewers are explicitly
watching for, separate from the schema's correctness.

### If a requirement is genuinely ambiguous and the interviewer won't clarify further

State your assumption out loud and move on, rather than freezing: *"I'll
assume returns can happen against a subset of an order's line items,
since that's the more general case — if that's wrong, the fix is
localized to `fact_returns`'s grain and doesn't ripple through the rest
of the design."* This shows you can make a defensible, reversible design
decision under uncertainty — a real skill, not a workaround — instead of
stalling until someone hands you every fact.

---

## Part B: Explaining a Design Decision to a Non-Technical Stakeholder

A separate, increasingly common interview format: "explain why you chose
[SCD Type 2 / a bridge table / a star schema] to a product manager who
doesn't know what a fact table is." This isn't a test of dumbing
something down — it's a test of whether you understand a decision well
enough to explain it *without* the jargon that was doing the explaining
for you.

### The pattern: name the business consequence, not the mechanism

| Technical framing | Stakeholder framing |
|---|---|
| "We're using SCD Type 2 on `dim_rider.subscription_tier`." | "When a rider's subscription tier changes, we keep a record of what tier they were on for every past ride — so if we ever ask 'how much revenue came from Premium riders last quarter,' the answer reflects who was actually Premium *at the time*, not who's Premium today." |
| "This is a star schema, not a snowflake." | "We keep the descriptive details — like a product's category — attached directly to the product, instead of splitting them into separate lookup tables. That means analysts get answers faster and don't need to understand a complicated map of tables to ask a question." |
| "We need a bridge table for the product-category many-to-many." | "A product can be in more than one category at once, like 'Running Shoes' being both 'Footwear' and 'On Sale.' If you ever see category totals that add up to more than total revenue, that's why — a sale gets counted once per category it's tagged with, which is expected, not a bug." |
| "`mrr` is semi-additive." | "You can add up this month's revenue across all our customers safely. You can't add up one customer's monthly revenue across 12 months and call it 'annual revenue' — that number wouldn't mean anything. If you need an annual figure, ask for it specifically and we'll build it the right way." |
| "We centralized `dim_customer` as a conformed dimension." | "Marketing and Billing used to have two different definitions of 'customer,' and their reports about the same customers didn't match. We fixed that once, centrally, so every team's numbers about a given customer now agree with each other." |

Notice the shape of every right-hand column: it states **what would go
wrong if the decision had gone the other way**, in terms the
stakeholder already cares about (a wrong number, a confusing dashboard,
two teams disagreeing) — not a definition of the technical term. That's
the actual skill being tested: can you reason all the way from "why does
this table look like this" to "here's the bad outcome this prevents,"
without stopping halfway at vocabulary.

### A concrete mini-script: explaining SCD Type 2 cold, in under 60 seconds

> "Say a customer moves from Portland to Seattle in March. If we just
> overwrote their city in our system, every report we've ever run about
> them — including reports from January and February, before they
> moved — would now say Seattle. That would be wrong; those were
> genuinely Portland sales. So instead, we keep both versions on file:
> 'Portland, until March' and 'Seattle, from March onward' — and every
> past sale stays linked to whichever version was true when it
> happened. It costs us a little extra storage and a slightly more
> complex load process, and it's worth it for anything finance or
> leadership actually reports on."

This script is deliberately reusable: the same shape (a concrete
example → what would go wrong without the decision → what it costs →
why it's worth it) works for nearly every design decision in files 1-4,
not just SCD Type 2. Practicing it once, generically, is more valuable
than memorizing five separate stakeholder-friendly explanations.

### When a stakeholder pushes back with "just make it simple"

A common, harder follow-up: the stakeholder says "this all sounds
complicated, can't we just keep one table with the current
information?" The strong answer names the trade-off honestly rather
than either caving or getting defensive: *"We can — that's a real,
valid choice if we're comfortable that historical reports will always
reflect today's information, not what was true at the time. For most of
what finance and leadership use this for, that's not an acceptable
trade, which is why we keep the history. If there's a specific report
where 'always current' is actually fine, we can absolutely simplify
just that piece."* This mirrors the Type 0/1/2 decision framework from
`concepts/04_slowly_changing_dimensions.md` — turn "make it simple" into
a scoped, specific trade-off conversation instead of an all-or-nothing
argument.

---

## Key Takeaways

- Budget a live design interview explicitly: protect the first few
  minutes for clarifying questions (skipping them reads worse than
  spending the time), cap schema-drawing time, and protect the query
  walkthrough — it's where a large share of the scoring actually
  happens, and it's the first thing rushed under pressure.
- If you're running low on time, say so and explicitly de-scope
  something rather than silently rushing or silently dropping a
  requirement — naming your own time management is itself a positive
  signal.
- Under genuine ambiguity, state an assumption and move forward rather
  than stalling — and note how localized the fix would be if the
  assumption turns out wrong.
- When explaining a design decision to a non-technical stakeholder, lead
  with the concrete bad outcome the decision prevents, not the technical
  term for the decision itself — "here's what would go wrong otherwise"
  beats a jargon definition every time.
- The same four-part script — concrete example, what breaks without it,
  what it costs, why it's worth it — generalizes across almost every
  decision in this course; practice it once as a pattern rather than
  memorizing a separate explanation per concept.
