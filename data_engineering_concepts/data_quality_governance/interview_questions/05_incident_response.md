# 5. Responding to a Data Incident

Part of the [Interview Questions](README.md) series.

Every other file in this folder drills *preventing* bad data — checks, contracts, monitoring. This file exists because a large fraction of real data quality interviews (and nearly all senior-level ones) also probe the opposite half of the job: something is *already* wrong in production right now, people are asking questions, and the checks that should have caught it either didn't exist yet or didn't fire. That's a different skill from designing a framework in the abstract — it's triage under uncertainty and time pressure, with incomplete information and a stakeholder who wants an answer sooner than you have one.

Each question below is a short scenario followed by "what do you actually do, in what order" — the format that reveals whether you have a real mental checklist for this, or are inventing one on the spot.

---

## 1. The first five minutes

**Q: You get paged: "revenue on the dashboard looks way off, starting about an hour ago." What do you do in the first five minutes — before you've looked at a single table?**

<details>
<summary>Answer</summary>

Three things, in this order, before touching any data: (1) confirm the report itself, in one sentence, back to whoever raised it — "off by how much, compared to what, since when" — because "way off" can mean anything from a 2% wobble to a zeroed-out column, and the investigation looks completely different depending on which. (2) Check whether this is isolated or systemic — is it one dashboard, or does the same underlying number look wrong anywhere else that draws on the same pipeline? That single check massively narrows the search space before you've run a single query. (3) Decide, out loud, whether this needs to be escalated as an active incident (a status update to stakeholders that you're looking into it) versus quietly investigated — a revenue number moving during a live earnings-adjacent period is a different urgency than the same symptom on a Tuesday afternoon dashboard nobody's watching live. None of this involves opening a lineage graph yet — that's step two, covered in question 2 — because acting before scoping the actual complaint risks chasing the wrong thing entirely.

</details>

---

## 2. Localizing the problem fast

**Q: You've confirmed it's real and isolated to one metric. You have a lineage graph, but it has eleven tables in the chain from raw source to dashboard. How do you decide where to look first, instead of checking all eleven in order?**

<details>
<summary>Answer</summary>

Two moves that both beat checking eleven tables in source-to-target order. First, check the two ends before the middle: is raw source volume/freshness normal (`concepts/05_anomaly_detection_and_monitoring.md`'s row-count and freshness checks), and does the dashboard's *immediate* source table look right? If the raw end is fine and the dashboard's direct source is already wrong, the problem is somewhere in the middle — narrowed from eleven candidates to whatever's between those two checkpoints. Second, binary-search the remaining chain rather than walking it linearly: check the table roughly in the middle of the remaining candidates: if it's fine, the problem is downstream of it; if it's already wrong, the problem is at or upstream of it. This turns an eleven-table linear walk into roughly `log2(11)` ≈ 4 checks. The underlying reasoning — this is exactly `interview_questions/01_worked_scenarios.md`, scenario B's approach, generalized: use lineage to make the search structured, not to check every hop out of habit.

</details>

---

## 3. Stop the bleeding vs. find the root cause

**Q: Twenty minutes in, you haven't found the root cause yet, but you've confirmed a specific mart table is producing wrong numbers. Do you keep investigating, or do something about the table right now?**

<details>
<summary>Answer</summary>

Contain first if containment is cheap and low-risk, then keep investigating — the two aren't mutually exclusive and shouldn't be treated as a single decision. A reasonable containment action at this point: mark the affected dashboard or table with a visible "known issue, investigating" annotation so nobody makes a decision on a number you already know is wrong, and, if the pipeline is scheduled to run again before you'll have a root cause, consider pausing that next scheduled run so it doesn't compound the problem or overwrite evidence you still need to look at. What you should *not* do at this point is start "fixing" the data by hand — patching values directly in the warehouse before you understand why they're wrong risks destroying the evidence that would have told you the actual root cause, and a hand-patch with no understanding of the mechanism has a real chance of being wrong itself. Containment buys time and prevents harm; it isn't a substitute for finding the actual cause.

</details>

---

## 4. Deciding whether to backfill history

**Q: You've found the root cause: a join was silently dropping about 8% of rows for the last 6 hours due to a schema rename upstream (this exact bug is worked in `01_worked_scenarios.md`, scenario B). You've fixed the join. Do you backfill the affected 6 hours of history, and how do you decide?**

<details>
<summary>Answer</summary>

Yes, and the decision of *how* follows directly from whether the affected fact table's load is idempotent (`etl_elt_patterns/concepts/06_idempotency_reliability.md`, if that folder's been covered) — if the load path is a proper upsert/merge keyed on a stable identifier, re-running the pipeline for the affected window is safe and simply corrects the wrong rows in place, no special-case cleanup required. If the load path is append-only or otherwise not idempotent, a naive re-run would double-count instead of correcting, and the fix needs an explicit delete-and-reload for exactly the affected window before re-running. Either way, this is also the moment to decide *visibly* rather than silently: does the correction happen quietly, or does the affected report carry a visible annotation that a specific window was restated? That's a stakeholder communication decision (question 5), not a purely technical one — silently rewriting a number a VP already saw and possibly acted on is a worse outcome than the original bug, even once the data itself is correct again.

</details>

---

## 5. Talking to the stakeholder who's waiting

**Q: The VP who flagged this is asking for an update while you're still mid-investigation. What do you actually tell them?**

<details>
<summary>Answer</summary>

Give a status, not a guess — what you know for certain, what you're still checking, and a realistic time estimate for the next update, explicitly separating "confirmed" from "suspected." Something like: "confirmed the dashboard's revenue number is undercounting by roughly 8% since around 2pm; still isolating exactly which upstream step is responsible; next update in 30 minutes or sooner if I find the cause before then" is a genuinely useful update even with zero root cause yet, because it tells the VP the size and scope of the problem and that it's actively being worked, without fabricating a cause you haven't verified. The failure mode to avoid in both directions: don't go silent for an hour because you don't have a complete answer yet (that reads as nothing is happening), and don't guess at a root cause out loud before you've verified it (a wrong guess relayed further up the chain is now itself a piece of bad information you'll have to walk back).

</details>

---

## 6. The postmortem: what actually needs to change

**Q: The incident is resolved, history is backfilled, the VP has been told. What goes in the postmortem, and how do you make sure this doesn't just become a document nobody acts on?**

<details>
<summary>Answer</summary>

A postmortem worth writing has exactly one non-negotiable output: a small number of *specific, owned, dated* follow-up actions, not a narrative alone. For this incident (the schema-rename join failure), that's concretely: a data contract on the upstream team's event schema enforced in their CI (`concepts/03_data_contracts.md`), so this exact class of rename can't ship silently again, and a monitoring check on the join's match rate or the affected table's row count (`concepts/05_anomaly_detection_and_monitoring.md`) so if a similar failure recurs from an entirely different cause, it's caught by an alert instead of a VP noticing a dashboard looks off. Each action needs an owner and a date, or it reliably becomes a document that gets written once, read once, and never referenced again — the single most common way postmortems fail to prevent a recurrence isn't a bad diagnosis, it's a good diagnosis with no one actually accountable for the fix landing.

</details>

---

## 7. A rapid gut-check: what's the very next action?

For each situation below, name the single next action — not a full plan, just what you'd actually do first.

<details>
<summary>Answer</summary>

```text
Paged about a wrong number, know nothing yet:
    -> Confirm scope with whoever reported it (what, since when, compared to what) before touching data.

Confirmed wrong, root cause unknown, pipeline runs again in 10 minutes:
    -> Decide whether to pause that run; annotate the dashboard as under investigation either way.

Root cause found, fix identified, history needs correcting:
    -> Check whether the load is idempotent before deciding how to backfill.

Fix shipped, VP asks "did this affect last month's numbers too":
    -> Don't guess -- run the same check that caught this incident against the wider historical
       window before answering either way.

Incident fully resolved, everyone's moved on:
    -> Write the postmortem with owned, dated follow-ups now, while the mechanism is still fresh --
       not "when there's time," which is exactly how a real fix never lands.
```

The common thread across every row: at each point, the next action is the cheapest thing that either narrows the problem or prevents it from getting worse — never a leap straight to "fix everything" before the scope of "everything" is actually known.

</details>
