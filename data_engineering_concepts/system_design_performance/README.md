# System Design & Performance

## Why This Matters

"Design a data pipeline for X" is *the* signature senior/mid-level data
engineering interview question — and it's usually the **last, and hardest,
round** in the loop. By the time you reach it, an interviewer has already
checked whether you can write SQL, model a schema, and explain a
transformation. This round checks something different: can you combine
everything else into one coherent, defensible system under time pressure,
justify every choice with a real trade-off, and hold up when they push back
on an assumption mid-conversation?

This is one of two **flagship topics** in this course (the other is
`../data_modeling/`) — it goes deeper than a typical topic folder on purpose:
more fully worked mock interviews, more trade-off depth, because this is
where a candidate is actually won or lost.

---

## Prerequisites

This topic assumes and actively combines four others. If any feel shaky,
the worked scenarios in `interview_questions/01_worked_scenarios.md` will
expose it immediately — a design here constantly reaches for vocabulary from
all four rather than re-teaching it:

- **`../data_modeling/`** — every design needs a defensible schema (grain,
  star schema, SCD choice) as its data-model layer.
- **`../etl_elt_patterns/`** — the batch/transform mechanics behind any
  pipeline's "how does data actually move and change shape" question.
- **`../data_warehousing_lakes/`** — where data lands and how it's queried
  at the end of the pipeline.
- **`../streaming_real_time/`** — the mechanics (Kafka, windowing,
  watermarks, exactly-once) behind any "make it real-time" requirement a
  scenario here assumes rather than re-explains.

Do those four first if you haven't. This folder is where they all get used
together, under interview conditions.

---

## Folder Structure

- `concepts/` — one Markdown file per topic: architecture patterns,
  scalability patterns, optimization techniques, and capacity/cost
  planning — read top to bottom like notes, real config and worked
  arithmetic shown inline wherever it clarifies the point
- `practice/` — exercises (capacity estimation, architecture selection,
  sharding, skew, trade-off analysis) and one coding problem (an LRU query
  cache), both hidden-answer format
- `interview_questions/` — the heart of this folder: full worked mock
  interviews, rapid-fire definitional Q&A, critique-a-broken-architecture
  cases, and mid-conversation curveball follow-ups
- `projects/` — a design-doc-writing exercise: given a business scenario,
  produce the actual written artifact a senior DE interview is scoring you
  on, not runnable code

Every `concepts/*.md` file follows the same shape as the rest of this
course: a **Covers** list, one `##` section per sub-topic (prose "why," an
ASCII diagram where one helps, real config/commands, a worked example with
its output shown), and a closing **Key Takeaways** summary.

---

## How to Use This Folder

1. **Read `concepts/` first, in order** — architecture patterns, then
   scalability patterns, then optimization techniques, then capacity/cost
   planning. This is the vocabulary every interview question assumes.
2. **Read `interview_questions/01_worked_scenarios.md` straight through**,
   including the hidden debriefs — it's the model for the full reasoning
   process (clarifying questions → architecture → trade-offs → narrated
   data flow → scaling/failure → close). Then attempt its "now you try"
   scenario yourself before checking the debrief.
3. **Drill `interview_questions/02-04`** the way you'd cram before an actual
   interview: rapid-fire for vocabulary, critique-and-debug for spotting
   flaws, curveballs for staying composed when an assumption gets pulled out
   from under you.
4. **Do the `projects/pipeline_designer.md` exercise** last — write a full
   six-section design doc for a scenario you haven't seen the answer to yet,
   then grade yourself against the rubric. This is the closest rehearsal to
   the actual interview available in this course.

---

## Key Mental Models

### 1. The SPADE Framework

```
S - Scope:        Clarify requirements, quantify scale, before anything else
P - Pipeline:     Sources -> transformations -> sinks, drawn before detailed
A - Architecture: Batch / Streaming / Lambda / Kappa -- chosen AND justified
D - Data Model:   Schemas, partitioning, storage format
E - Edge Cases:   Failures, skew, late data, scale spikes, compliance
```

Every worked scenario in `interview_questions/01_worked_scenarios.md` and
every design doc in `projects/pipeline_designer.md` follows this shape,
narrated in prose rather than as five labeled headers — internalize the
ORDER (scope and quantify before architecture; architecture before data
model; edge cases last but never skipped) more than the acronym itself.

### 2. The Architecture Decision Matrix

```
Batch:     Freshness > 1 hour is fine        -> simplest, cheapest, default
Streaming: Sub-second/seconds freshness       -> real operational complexity
Lambda:    BOTH fast AND strictly-accurate    -> most expensive, two codepaths
           needed for the SAME metric            that WILL drift if not
                                                   watched
Kappa:     Everything's naturally an event,   -> simpler than Lambda, but
           want one codepath                     replay cost is real
```

The strongest interview answers name the latency requirement FIRST, then
pick the simplest architecture that satisfies it — not the most
sophisticated one available. See `concepts/01_pipeline_architectures.md`.

### 3. Where the Numbers Come From

```
Given rate/volume
      |
      v
events/sec  --------> sizes streaming compute (Flink TaskManagers, Kafka
                       partitions)
daily bytes --------> sizes storage (with retention + compression)
concurrency --------> sizes warehouse compute (NOT the same driver as
                       storage volume)
```

"Millions of events a day" is not a number an interviewer can evaluate —
convert every given rate into these three quantities before touching
architecture. See `concepts/04_capacity_planning_and_cost.md`.

---

## Practice Goals

- [ ] Walk through SPADE on a scenario you haven't seen before, out loud, in
      under 30 minutes
- [ ] Justify Batch vs. Streaming vs. Lambda vs. Kappa for a given scenario
      using ITS specific requirements, not the general trade-off table
- [ ] Convert a stated business volume into events/sec, daily storage, and a
      Kafka partition count, showing the arithmetic
- [ ] Spot the flaw in a described (not diagrammed) broken architecture,
      and name the fix's underlying category, not just the one-off patch
- [ ] Handle a mid-conversation curveball ("now make it real-time," "now
      it's multi-region," "the team just shrank to 2 people") without
      abandoning the design already on the table
- [ ] Write a full six-section design doc for a novel business scenario
      that a different engineer could actually start building from

---

## A Note on Provenance

The architecture patterns, scalability mechanisms, and optimization
techniques here are standard, well-established data engineering practice —
not tied to one specific course or playlist the way `../spark_course/` is.
The worked interview scenarios and critique cases are original material
written for this course, modeled on the same interviewer-simulation format
used throughout `interview_questions/` folders in this repo.
