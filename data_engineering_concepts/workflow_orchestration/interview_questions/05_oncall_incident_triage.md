# 5. On-Call & Incident Triage

Part of the [Interview Questions](README.md) series.

Orchestration interviews for anything senior or on-call-adjacent increasingly probe
**operational maturity** specifically — not "do you know what a trigger rule is" but "have
you actually been paged, and do you know what to do in what order before you've even
opened the code." This file drills that directly, as a dedicated fifth shape distinct from
design ([file 1](01_worked_scenarios.md)) and diagnosis-from-a-description
([file 3](03_critique_and_debug.md)): each case here is a live incident, and the thing
being scored is your **triage sequence**, not just your eventual diagnosis.

---

## The General Triage Framework

Before the specific incidents below, the sequence worth having ready as a default, for any
page, regardless of what turns out to be wrong:

```text
1. SCOPE       Is this one task, one DAG, or systemic (scheduler/infra/shared dependency)?
               Check whether OTHER unrelated DAGs are also failing right now.

2. READ        Open the actual failure -- logs, error message -- before assuming a cause.
               Is this the FIRST failure, or a flaky task finally exhausting its retries?

3. DECIDE      Rerun (if transient + idempotent) / fix forward / roll back / escalate --
               and be able to say WHY you picked that option, not just which one.

4. COMMUNICATE Say something before you're fully done, not after. Silence during an
               incident is its own failure mode, independent of resolution speed.

5. FOLLOW UP   Once green: is this a first-time failure or a recurring one? A recurring
               "successful" 3am rerun of the same root cause is a deferred problem, not
               a solved one.
```

Every case below is scored against this same shape — read the symptom, work through your
own version of steps 1-5, then expand the debrief.

---

## Incident 1: A Task Is Stuck in `queued` and Never Starts

**Symptom:** A task instance has been sitting in `queued` state for 40 minutes. The DAG's
other tasks are running fine. There's no error — it's just not starting.

<details>
<summary>Triage</summary>

**Scope:** check whether *other* queued tasks across the instance are also stuck, or just
this one. If many are stuck, this is a worker-capacity problem, not a task-specific one.

**Likely causes, in order of how common they actually are:** (1) the worker pool this
task's `pool` parameter points to is fully occupied — check what else is holding those
slots (a long-poking sensor in poke mode is the classic offender, see
`interview_questions/03_critique_and_debug.md`, Case 2); (2) the scheduler itself is
under-provisioned or lagging; (3) a resource/priority-weight misconfiguration is placing
this task behind others that shouldn't outrank it.

**Decide:** if it's pool exhaustion from a specific offending task/sensor, the immediate
mitigation is freeing capacity (killing or rescheduling the offender) rather than waiting —
waiting doesn't resolve a structurally full pool. The follow-up fix is the sensor's `mode`
or the pool's sizing, not a one-time unblock.

**The tell:** distinguishing "the task itself is broken" from "the task is fine but there's
nowhere to run it" — a `queued` state with no logs at all is a strong signal it's the
latter, and jumping straight into the task's own code/logs wastes time on the wrong layer.

</details>

---

## Incident 2: The Same Task Has Auto-Retried Successfully Every Night for Two Weeks

**Symptom:** Reviewing the DAG's run history, you notice `extract_billing_api` fails on its
first attempt almost every single night, then succeeds on retry #2. Nobody has been paged,
because the task ultimately succeeds. You weren't specifically looking for this — you
noticed it while investigating something else.

<details>
<summary>Triage</summary>

**Scope:** this isn't an active page, so there's no "is this systemic" step in the urgent
sense — but the same reflex applies: is this ONE task doing this, or is it a pattern across
several tasks that call the same downstream API?

**Read:** what's the actual first-attempt error? "Connection reset," a specific rate-limit
response code, and a generic timeout all point to different root causes and different
fixes, and "it eventually succeeds" has made nobody bother checking which one it is.

**Decide:** a task that reliably fails-then-succeeds every night is not "working as
intended" just because the DAG stays green — it's a real, recurring problem that retries
are quietly masking. If it's a rate limit, the fix is respecting it (backing off the first
call's timing, or reducing call frequency), not more retries. If it's the API's own
intermittent instability, that's worth raising with whoever owns that API, with this DAG's
two weeks of data as evidence, rather than treating it as this DAG's problem to keep
absorbing indefinitely.

**The tell:** flagging this at all. A candidate who says "it's not paging anyone, so it's
not a problem" is missing that a retry policy successfully hiding a real, consistent
failure is a bigger operational risk than an occasional loud failure — the day it fails on
attempt 2 as well, this becomes a genuine incident with zero prior visibility, instead of
one it was possible to see coming.

</details>

---

## Incident 3: A Backfill You Kicked Off Is Slowing Down Production

**Symptom:** You started a 90-day backfill an hour ago to fix a bad metric. Twenty minutes
in, the on-call channel lights up: today's live DAG runs are running unusually slowly, and
a separate team's dashboard-refresh DAG just missed its SLA.

<details>
<summary>Triage</summary>

**Scope:** this one you already know the likely cause of, because you just took the action
— the question is confirming it, not searching blindly. Check whether the backfill's task
instances are running in the same worker pool as production traffic.

**Read:** confirm via the scheduler/pool view that the backfill's tasks are, in fact,
occupying slots that would otherwise serve live DAGs and the other team's dashboard DAG.

**Decide:** the fix is not "let it finish, it'll be done soon" — actively pause or throttle
the backfill immediately (reduce its concurrency, or pause it outright) to give live traffic
its capacity back, then restart the backfill properly isolated (a dedicated pool, a lower
`max_active_runs`) rather than let it continue degrading production. This is precisely the
isolation `concepts/05_backfills_and_catchup.md`, section 5, describes — the incident here
is what happens in the specific, common case where that isolation step was skipped.

**Communicate:** own it explicitly and immediately in the incident channel — "that's my
backfill, pausing it now" resolves the ambiguity for every other engineer confused about
why unrelated dashboards just started missing SLAs, and is far more useful than someone
else spending 20 minutes independently discovering the same cause.

**The tell:** the ownership/communication step matters as much as the technical fix here —
this incident is self-inflicted and immediately traceable, and saying so fast is itself
part of the correct response, not an afterthought after the fix.

</details>

---

## Incident 4: A Schema Change Upstream Broke the DAG, But Only Some Rows

**Symptom:** A source system added a new required field. The DAG's extract task doesn't
fail — it succeeds every day. But `validate_data`, several tasks downstream, has started
silently dropping about 15% of rows each run (a data-quality check that filters out
"malformed" records, working exactly as designed). Nobody noticed until a weekly report's
totals looked low.

<details>
<summary>Triage</summary>

**Scope:** confirm this is isolated to records that started including the new field's
absence-in-old-schema mismatch, versus a broader data-quality regression.

**Read:** the extract task's success is a red herring — go straight to `validate_data`'s
own rejection reasons/logs, since that's the task actually discarding rows, not the one
that looks broken.

**Decide:** this is not primarily an orchestration fix — the DAG did exactly what it was
told to do (validate, then drop what fails validation) and did it successfully, every run.
The real fix is a schema-compatibility layer upstream of validation (handle the new field
as optional, or explicitly reject the whole batch loudly rather than silently dropping 15%
of it row-by-row) — squarely `data_quality_governance` territory. The orchestration-specific
lesson: **a task quietly discarding a meaningful fraction of a batch should itself be a
first-class failure signal** (an assertion on the reject *rate*, not just a log line), the
same principle from `interview_questions/03_critique_and_debug.md`, Case 5 — a green run
proves "nothing threw an exception," not "the output is correct."

**The tell:** correctly identifying that the extract task succeeding is irrelevant to the
actual defect, and not spending triage time investigating the wrong task first.

</details>

---

## Incident 5: You're Asked to Roll Back a DAG Deploy Mid-Incident

**Symptom:** A DAG code change was deployed four hours ago. Since then, three of its runs
have failed in a way that doesn't look like the classic "flaky external dependency"
pattern — the error is inside logic that *did* change in the deploy. Someone asks: "can we
just roll back?"

<details>
<summary>Triage</summary>

**Scope/read:** confirm the failure is actually caused by the deploy (correlate the first
failed run's timestamp against the deploy timestamp) rather than assuming — a coincidental,
unrelated failure landing right after a deploy is a real possibility worth ten seconds of
checking before committing to "roll back" as the plan.

**Decide:** if it's confirmed, rolling back the DAG's code to the prior version is usually
the right immediate move — it's fast, well-understood, and buys time to fix the real issue
without pressure. The one thing to check *before* rolling back: did the new version already
write any data under a schema/format the OLD version can't correctly process going forward
(e.g., a new column the old code doesn't populate, that something downstream now expects)?
If so, "roll back the code" and "the data is now in a shape only the new code understands"
can conflict, and that has to be resolved as part of the rollback decision, not discovered
after.

**Communicate:** state the rollback plan and the reasoning out loud before executing it,
including the data-compatibility check above — a rollback executed silently, that turns out
to be incompatible with data already written, creates a second incident on top of the
first.

**The tell:** not treating "roll back" as a purely mechanical, always-safe action — the
strong answer names the one case (a data-shape change already partially in flight) where
rolling back code and rolling back data are two different problems that don't necessarily
resolve together.

</details>

---

## Key Takeaways

- The same five-step shape applies regardless of the specific incident: scope it (isolated
  vs. systemic), read the actual evidence before assuming a cause, decide with a stated
  reason, communicate early rather than only after resolution, and check afterward whether
  this was a first-time or recurring failure.
- A DAG staying green is not the same claim as a DAG doing the right thing — several of
  these incidents (2, 4) are cases where nothing ever paged anyone, and the operational
  skill being tested is noticing the gap yourself rather than waiting for an alert that was
  never going to fire.
- Communication and ownership are part of the technical answer, not a soft-skill footnote
  bolted on afterward — incident 3 and incident 5 are both scored partly on whether you say
  the right thing out loud at the right moment, independent of whether your technical fix
  is correct.
