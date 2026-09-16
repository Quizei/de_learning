# 1. Worked Design Scenarios

Part of the [Interview Questions](README.md) series — see that index for
the full taxonomy of question types and how the files fit together.

This file is deliberately **code-free** — no `CREATE` statements, no SQL,
no Python. The point is to rehearse the *reasoning* an interviewer is
actually scoring: how you scope the problem, name your grain, justify
your schema, and talk through queries out loud. Once the reasoning is
solid, the SQL is easy — that's what `concepts/` and `practice/` are for.

Nine industries are covered below, in three pairs plus three flagship
additions. Each pair introduces new schema-shape vocabulary and pairs a
fully worked example with a "Now You Try" companion scenario (hidden
debrief); the three additions at the end are each a full worked
walkthrough in their own right, chosen specifically because they force
patterns the first six don't: weighted/rollup-of-rollup measures, a
dynamic-weight bridge table, and a huge snowflaked dimension plus an
identity-merge problem.

Read the first six once straight through as worked examples, including
the hidden debriefs. Then use every "Now You Try" and the three new
scenarios to run the same process yourself before checking the answer.

---

## A. Ride-Sharing & Food Delivery

### Worked Scenario: Ride-Sharing Trip Analytics

**Interviewer prompt:**
> "Design a data model that lets analysts report on rides taken through
> our platform — revenue, driver performance, rider behavior. Then tell
> me how you'd answer a few business questions against it."

#### Step 1 — Ask clarifying questions before designing anything

A candidate who starts drawing tables immediately is a red flag. The
questions themselves are part of the signal:

- **Who consumes this?** BI dashboards and monthly finance reports, not
  the live dispatch system. → This is an analytical (OLAP) model, not the
  transactional (OLTP) system that runs the app.
- **What's the grain of the core event?** One row per completed ride, or
  per ride *leg* (some rides have stops)? → Interviewer says: one row per
  completed ride, cancellations tracked separately.
- **What changes over time that we need history for?** Driver's home
  city and vehicle type change occasionally; rider's subscription tier
  changes. → Signals we'll need slowly changing dimensions.
- **Scale?** ~2M rides/day, 5 years of history expected. → Rules out
  anything that requires full-table rewrites; favors partitioning by
  date.
- **Freshness?** Next-day is fine, not real-time. → Confirms batch ETL,
  not a streaming design (see `04_curveballs_tradeoffs.md`'s real-time
  curveball for when this assumption gets pushed on).

Stating these questions out loud, and stating *why each answer matters*,
is worth more than a perfect schema — it shows you know a data model is a
negotiated answer to specific questions, not a universal artifact.

#### Step 2 — Declare the grain before naming a single table

> "The fact table grain is: one row per completed ride."

Everything else follows from this sentence. If later a question needs a
grain the model doesn't support (e.g. "revenue per minute of the ride"),
that's a sign either the grain needs to change or the question needs a
derived/aggregate table — not that you should silently break the grain
by mixing row types into one fact table.

#### Step 3 — Name the dimensions and the measures

Talk through *why* each one is a dimension (descriptive, answers who/what/
when/where) versus a measure (numeric, additive, describes the event).

| Dimension       | Answers          | Key attributes (describe, don't script)                     | Change behavior |
|-----------------|------------------|-----------------------------------------------------------------|------------------|
| `dim_date`      | When             | calendar date, day of week, month, quarter, is_holiday        | static           |
| `dim_rider`     | Who requested    | rider_id, signup_date, home_market, subscription_tier         | tier changes → track history (SCD Type 2) |
| `dim_driver`    | Who fulfilled    | driver_id, onboarding_date, home_city, vehicle_type            | city/vehicle change → track history (SCD Type 2) |
| `dim_vehicle_type` | Product tier  | economy / premium / XL, base rate multiplier                  | rarely changes → overwrite (SCD Type 1) |
| `dim_location`  | Where            | pickup/dropoff zone, city, market                              | static reference data |

| Measure              | Additive? | Notes |
|----------------------|-----------|-------|
| `fare_amount`        | Yes       | sums correctly across any dimension |
| `distance_miles`     | Yes       | |
| `duration_minutes`   | Yes       | |
| `driver_payout`      | Yes       | |
| `surge_multiplier`   | No (non-additive) | can't sum across rides — only makes sense per-row or averaged |

Calling out `surge_multiplier` as non-additive is exactly the kind of
detail that separates a strong answer from a merely correct one — it
shows you'd catch a wrong report ("total surge multiplier for the
region") before it shipped.

#### Step 4 — Describe the schema shape, not its DDL

> "This is a star schema: `fact_rides` in the center, with foreign keys
> out to `dim_date`, `dim_rider`, `dim_driver`, `dim_vehicle_type`, and
> two roles of `dim_location` — one for pickup, one for dropoff (a
> **role-playing dimension**, so it's the same physical table joined
> twice under two aliases, not two separate tables)."

```
                    dim_date
                       |
dim_rider ---- fact_rides ---- dim_driver
                 |      |
        dim_location   dim_location
        (pickup)       (dropoff)
```

The shape above is what you sketch first. The moment the interviewer
asks "what columns, and what joins to what," walk through it table by
table — this is also exactly the level of detail that turns a hand-wavy
diagram into something you could hand to an engineer:

```
dim_date                          dim_rider  (Type 2)
  date_key            PK            rider_key           PK, surrogate
  full_date                         rider_id                 natural key
  day_of_week                       signup_date
  month, quarter                    home_market
  is_holiday                        subscription_tier
                                     valid_from / valid_to / is_current

dim_driver  (Type 2)               dim_vehicle_type  (Type 1)
  driver_key          PK, surrogate  vehicle_type_key   PK
  driver_id                natural key  vehicle_type_name
  onboarding_date                    base_rate_multiplier
  home_city
  vehicle_type
  valid_from / valid_to / is_current

dim_location
  location_key        PK
  zone
  city
  market

fact_rides                                     grain: one row per completed ride
  ride_key                  PK
  date_key                  FK -> dim_date.date_key
  rider_key                 FK -> dim_rider.rider_key            (row current when the ride happened)
  driver_key                FK -> dim_driver.driver_key          (row current when the ride happened)
  vehicle_type_key          FK -> dim_vehicle_type.vehicle_type_key
  pickup_location_key       FK -> dim_location.location_key      (role: pickup)
  dropoff_location_key      FK -> dim_location.location_key      (role: dropoff)
  fare_amount, distance_miles, duration_minutes, driver_payout, surge_multiplier
```

Two things worth narrating out loud from this layout: `fact_rides` has
*two* foreign keys pointing at the same `dim_location` table
(`pickup_location_key` and `dropoff_location_key`) — that's the
role-playing dimension made concrete, one physical table, two joins,
two aliases. And `rider_key`/`driver_key` join to *whichever dimension
row was current at ride time*, not necessarily today's row — that's
what makes the Type 2 history in Step 5 actually load-bearing rather
than decorative.

Say out loud *why* star over snowflake here: the location hierarchy
(zone → city → market) is small and low-cardinality, so flattening it
into `dim_location` costs almost nothing in storage and saves every
analyst a join. If a hierarchy were huge and frequently queried at only
one level (e.g. a product catalog with 50,000 SKUs, or the diagnosis
hierarchy in the healthcare scenario later in this file), that's when
snowflaking part of it earns its keep — see `concepts/03_star_snowflake_schema.md`
for the fully worked storage/query trade-off.

#### Step 5 — Call out the SCD decision explicitly

> "`dim_rider.subscription_tier` and `dim_driver.home_city` are Type 2 —
> new row per change, with `valid_from`/`valid_to`/`is_current` — because
> finance needs to attribute historical rides to the tier or city that
> was true *at the time of the ride*, not today. Everything else that
> changes rarely and doesn't need history (e.g. a corrected typo in a
> driver's name) is Type 1 — overwrite in place."

This is the single most commonly-probed follow-up in these interviews —
have the answer ready before they ask.

#### Step 6 — Now query it (out loud, no SQL required)

The interviewer follows up with business questions. For each, describe
the *joins, filters, and aggregation* in plain language — that's what's
being scored, not syntax.

**Q1: "Total revenue by market, last quarter."**
> Start at `fact_rides`, join to `dim_location` on the pickup key to get
> market, join to `dim_date` and filter to the quarter, sum
> `fare_amount`, group by market. Two joins, one filter, one aggregate —
> this is the shape a star schema is built for.

**Q2: "Which drivers had the biggest drop in completed rides month over
month?"**
> This needs the fact table aggregated twice — once per driver per month
> — then compared against itself one month offset. Talk through it as:
> build a driver-month summary (rides count, grouped by driver and
> month), then join that summary to itself shifted by one month to
> compute the delta. Flag that this is a self-join / window-function
> shaped problem, not a simple filter.

**Q3: "Revenue per rider, attributed to the subscription tier they had
at the time of each ride, not their current tier."**
> This is exactly why `dim_rider` is Type 2. Explain that the fact table
> stores the surrogate key pointing at the dimension *row that was
> current when the ride happened*, so summing `fare_amount` grouped by
> `subscription_tier` naturally reflects historical tier, with no extra
> logic — the SCD design did the work upfront. Point out the alternative
> failure mode: if `dim_rider` were Type 1, this report would silently
> misattribute all historical revenue to the rider's *current* tier.

**Q4 (curveball): "A rider's home_market was recorded wrong for the first
month and got corrected. Does that break our monthly revenue-by-market
report?"**
> Good answer distinguishes: if `home_market` is Type 1 (probably right —
> it's a correction, not a real change), the fix retroactively updates
> all historical rows to the correct value, which is *desired* here —
> unlike the subscription-tier case, this wasn't a real change over time,
> it was bad data. Recognizing when Type 1's blanket rewrite is the
> correct behavior (fixing an error) versus the wrong one (losing real
> history) is the tell of someone who understands SCDs rather than just
> memorizing the types.

#### Step 7 — Close by naming the trade-offs you made

A strong finish, unprompted:
> "I flattened the location hierarchy but kept driver and rider as
> proper SCD Type 2 dimensions because those histories are load-bearing
> for finance. If storage or ETL complexity were a real constraint here,
> the vehicle-type dimension is small enough that it wouldn't matter
> either way — that's a place I'd take the simpler option without a
> second thought."

---

### Now You Try: Food Delivery Order Analytics

**Interviewer prompt:**
> "Design a data model for reporting on food delivery orders — order
> volume, restaurant performance, delivery times. Then walk me through
> how you'd answer the questions below."

Work through Steps 1–7 yourself, out loud, before reading the debrief.

**Questions to answer once you have a schema:**
1. Average delivery time by restaurant category, last 30 days.
2. Which restaurants had the highest cancellation rate this month?
3. Revenue by customer loyalty tier, attributed to the tier the customer
   held *at the time of the order*.
4. Curveball: a restaurant's `cuisine_type` was miscategorized for six
   months and just got fixed. Should that retroactively change last
   quarter's "revenue by cuisine" report?

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **Grain:** one row per completed or cancelled order (state it
  explicitly — cancelled orders belong in the fact table with a status
  flag, not a separate model, since "cancellation rate" needs them
  counted alongside completed orders).
- **Dimensions:** `dim_date`, `dim_customer` (loyalty tier → Type 2),
  `dim_restaurant` (cuisine_type → Type 1, since a miscategorization is
  an error, not a real change — the fix *should* rewrite history, same
  reasoning as the ride-share `home_market` curveball above), `dim_driver`,
  `dim_delivery_zone`.
- **Measures:** `order_total` (additive), `delivery_minutes` (additive,
  but reported as an average — flag that summing it is meaningless,
  averaging is what matters), `is_cancelled` (additive as a 0/1 count).
- **Columns and join keys**, in the same shape as the ride-share example:

  ```
  dim_customer  (Type 2)             dim_restaurant  (Type 1)
    customer_key       PK, surrogate   restaurant_key      PK
    customer_id             natural key  restaurant_name
    signup_date                        cuisine_type
    loyalty_tier                       delivery_zone_key
    valid_from / valid_to / is_current

  dim_driver                          dim_delivery_zone
    driver_key         PK               delivery_zone_key   PK
    driver_id                           zone_name
    vehicle_type                        city

  fact_orders                                    grain: one row per completed or cancelled order
    order_key                PK
    date_key                 FK -> dim_date.date_key
    customer_key             FK -> dim_customer.customer_key   (row current at order time)
    restaurant_key           FK -> dim_restaurant.restaurant_key
    driver_key                FK -> dim_driver.driver_key
    order_total, delivery_minutes, is_cancelled
  ```

- **Q1** joins fact → `dim_restaurant` → filter category, `dim_date` →
  filter last 30 days, average `delivery_minutes`, group by category.
- **Q2** aggregates the fact table by restaurant and month, computing
  cancelled-count over total-count as a ratio — same shape as the
  ride-share drop-rate question.
- **Q3** relies on the Type 2 `dim_customer` history exactly as the
  ride-share subscription tier did.
- **Q4** — because `cuisine_type` is Type 1, correcting it updates all
  historical rows, so last quarter's report *changes* when re-run after
  the fix. That's correct: it was bad data, not a real change over time.
  Contrast this explicitly with a *real* re-categorization (a restaurant
  genuinely pivots from "Pizza" to "Italian Fine Dining") — that case
  would argue for Type 2 instead, so the reasoning is about **why** the
  value changed, not just which column it is.

</details>

---

## B. E-Commerce & Subscription Retail

### Worked Scenario: E-Commerce Order & Browsing Analytics

This scenario introduces three shapes the ride-sharing example didn't
need: a **many-to-many relationship** (a product can sit in several
categories), a **factless fact table** (an event with no numeric
measure, like a page view), and a **degenerate dimension** (an order
number that lives on the fact table with no dimension table behind it).

**Interviewer prompt:**
> "Design a data model for our e-commerce platform covering orders,
> returns, and on-site browsing behavior. Then answer some business
> questions against it."

#### Step 1 — Clarifying questions

- **One model, or several?** Orders and browsing events are fundamentally
  different grains and different volumes (browsing is 100x the row
  count of orders) — treat them as two fact tables sharing conformed
  dimensions, not one. → Confirmed.
- **Do returns get their own fact table, or live inside the orders
  fact?** → Interviewer says: returns can happen weeks after the
  original order, against a subset of line items, so they need their
  own grain. Model them separately and let analysts join back to the
  original order when needed.
- **Can a product belong to more than one category?** → Yes — "Running
  Shoes" might sit under both "Footwear" and "Sale Items"
  simultaneously. This is the many-to-many signal.
- **Do we need to know a shopper browsed but bought nothing?** → Yes,
  cart-abandonment analysis is a stated goal. That's a fact table with
  no natural numeric measure — a **factless fact table**.
- **Scale/freshness?** 500K orders/day, browsing events next-day batch
  is fine.

#### Step 2 — Declare the grains (plural, this time)

> "I have three fact tables here, each with its own grain:
> `fact_order_lines` — one row per product line item per order.
> `fact_returns` — one row per returned line item.
> `fact_browsing_events` — one row per page-view/add-to-cart/checkout-
> start event."

Naming three grains explicitly, instead of trying to force everything
into one fact table, is itself the answer to a very common follow-up:
*"when would you use more than one fact table?"* — whenever the
business processes genuinely happen at different grains and different
times, forcing them together produces fan-out or nulls, not simplicity.

#### Step 3 — Dimensions, including the two new shapes

| Dimension          | Notes |
|---------------------|-------|
| `dim_date`          | standard |
| `dim_customer`      | loyalty tier → Type 2 (same reasoning as the ride-share rider tier) |
| `dim_product`       | product_id, name, brand, price — **does not** hold category directly |
| `dim_category`      | category_id, category_name |
| `bridge_product_category` | **bridge table**: (product_id, category_id) — one row per product-per-category it belongs to |
| `dim_page`          | for browsing events: page_type (PDP, cart, checkout), page_url |
| `dim_event_type`    | view / add_to_cart / begin_checkout / purchase |

The many-to-many between product and category is resolved with a
**bridge table** instead of forcing it into `dim_product` (which would
mean either repeating a product row per category, breaking the "one row
per product" grain of the dimension, or collapsing categories into a
comma-separated string, which breaks filtering/joining). Say this
distinction out loud — it's the single most common data-modeling
curveball after SCDs.

`fact_order_lines` also carries an **order_number** column directly —
a **degenerate dimension**: it's dimension-like (you group and filter
by it) but there's no attribute beyond the number itself, so it doesn't
warrant its own table.

#### Step 4 — Schema shape

```
fact_order_lines:  dim_date, dim_customer, dim_product, order_number (degenerate)
                    -> measures: quantity, unit_price, line_total, discount_amount

fact_returns:       dim_date, dim_customer, dim_product, original_order_number (degenerate)
                     -> measures: quantity_returned, refund_amount

fact_browsing_events: dim_date, dim_customer, dim_page, dim_event_type
                       -> factless (no measure column at all — the row's
                          existence IS the fact; you count rows)

dim_product <--- bridge_product_category ---> dim_category
```

Same shape, walked through table by table with actual columns and the
keys each join runs on:

```
dim_customer  (Type 2)              dim_product
  customer_key      PK, surrogate     product_key         PK
  customer_id            natural key  product_id               natural key
  loyalty_tier                        product_name
  valid_from / valid_to / is_current  brand, price
                                       (no category column — see bridge below)

dim_category                        bridge_product_category
  category_key       PK               product_key    FK -> dim_product.product_key
  category_name                       category_key   FK -> dim_category.category_key
                                       -- one row per (product, category) pairing;
                                          a product with 2 categories = 2 rows here

dim_page                            dim_event_type
  page_key           PK               event_type_key      PK
  page_type (PDP/cart/checkout)       event_type_name (view/add_to_cart/
  page_url                              begin_checkout/purchase)

fact_order_lines                            grain: one row per product line item per order
  order_line_key         PK
  date_key                FK -> dim_date.date_key
  customer_key            FK -> dim_customer.customer_key   (row current at order time)
  product_key              FK -> dim_product.product_key
  order_number             degenerate — no dimension table, lives here directly
  quantity, unit_price, line_total, discount_amount

fact_returns                                grain: one row per returned line item
  return_key               PK
  date_key                  FK -> dim_date.date_key
  customer_key              FK -> dim_customer.customer_key
  product_key                FK -> dim_product.product_key
  original_order_number      degenerate
  quantity_returned, refund_amount

fact_browsing_events                        grain: one row per page-view/cart/checkout event
  event_key                 PK
  date_key                   FK -> dim_date.date_key
  customer_key                FK -> dim_customer.customer_key
  page_key                     FK -> dim_page.page_key
  event_type_key                FK -> dim_event_type.event_type_key
  (no measure column — factless)
```

To get from a product to its categories (or vice versa) you always go
*through* the bridge — `dim_product.product_key` →
`bridge_product_category.product_key`, then
`bridge_product_category.category_key` → `dim_category.category_key` —
never a direct foreign key between the two, because a direct FK could
only point at one row.

Point out that `fact_order_lines`, `fact_returns`, and
`fact_browsing_events` all reference `dim_date` and `dim_customer` —
these are **conformed dimensions**, shared across fact tables so a
customer or a date means exactly the same thing everywhere, letting
analysts eventually combine insights across all three (e.g. "did
browsing behavior predict a return?") without redefining anything.

#### Step 5 — Additive vs. non-additive measures, again

| Measure           | Additive?              |
|--------------------|-------------------------|
| `line_total`       | Yes |
| `quantity`         | Yes |
| `refund_amount`    | Yes |
| discount **rate**  | if this existed as a %, it would be non-additive — always prefer storing `discount_amount` (a dollar figure) over a rate, precisely so it stays additive |

#### Step 6 — Now query it

**Q1: "Revenue by category, last month, accounting for a product being
in multiple categories."**
> Join `fact_order_lines` → `bridge_product_category` → `dim_category`,
> filter `dim_date` to last month, sum `line_total`, group by category.
> Flag the consequence out loud: because of the bridge table, a single
> order line can now contribute to *two* categories' totals — so
> "revenue by category" summed across all categories will legitimately
> exceed total company revenue. That's expected and correct for a
> many-to-many rollup, but it's the kind of thing that panics a
> stakeholder if you don't warn them first.

**Q2: "Return rate by product, last quarter."**
> Two separate aggregates over two fact tables at compatible grain
> (product + quarter): total quantity ordered from `fact_order_lines`,
> total quantity returned from `fact_returns`, joined together on
> product and date-quarter, divide. Call out that this only works
> cleanly because both facts share the conformed `dim_product` and
> `dim_date` — mismatched dimensions between fact tables is exactly what
> breaks reports like this in practice.

**Q3: "Cart abandonment rate — sessions that hit checkout but never
purchased."**
> This is the payoff for modeling browsing as a factless fact: count
> distinct sessions with an `event_type = begin_checkout` row, count
> distinct sessions that also have an `event_type = purchase` row, the
> gap is abandonment. No numeric measure was ever needed — just counting
> occurrences of the row, filtered by the event-type dimension.

**Q4 (curveball): "Marketing wants to change a product's category from
'Everyday' to 'Premium' — should that rewrite history?"**
> Ask back: is this a real re-positioning (Type 2 — future orders'
> reports should reflect Premium, past orders stay attributed to
> Everyday) or a correction of a mis-tag (Type 1 on the bridge table
> row — rewrite history because it was always wrong)? Same
> disambiguation principle as the ride-share SCD curveball above: ask
> *why* the value is changing before picking the fix.

#### Step 7 — Trade-offs, stated unprompted

> "I split browsing out as its own factless fact rather than trying to
> tack a 'browsed but didn't buy' flag onto the orders fact — that would
> force a row into a table whose grain is 'a completed order line,'
> which doesn't exist for a pure browse. Keeping them separate cost one
> extra fact table but kept every grain honest."

---

### Now You Try: Subscription Box Retailer

**Interviewer prompt:**
> "Design a data model for a subscription box company — customers pay
> monthly for a curated box, can pause or cancel, and boxes contain
> multiple products sourced from multiple suppliers."

**Questions to answer once you have a schema:**
1. Monthly recurring revenue (MRR) by plan tier, for each of the last 12
   months.
2. Churn rate by signup cohort month.
3. Which suppliers' products appear most often in boxes that later got
   a subscription cancellation within 30 days?
4. Curveball: a customer pauses for two months then resumes — does that
   count as churn in month 2?

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **Grain:** this needs an **accumulating/periodic snapshot** flavor,
  not a pure transaction fact: `fact_subscription_status` — one row per
  customer per month, capturing status (active/paused/cancelled) and
  the MRR that month. A separate `fact_box_contents` — one row per
  product per box shipped — handles the supplier question, joined to
  `dim_product` → `dim_supplier` (another bridge if a product can have
  multiple suppliers).
- **Columns and join keys:**

  ```
  dim_customer  (Type 2)              dim_plan
    customer_key       PK, surrogate    plan_key            PK
    customer_id             natural key  plan_tier
    signup_date                          monthly_price
    valid_from / valid_to / is_current

  dim_product                         dim_supplier
    product_key         PK              supplier_key        PK
    product_name                        supplier_name

  bridge_product_supplier             (only needed if a product has >1 supplier)
    product_key   FK -> dim_product.product_key
    supplier_key  FK -> dim_supplier.supplier_key

  fact_subscription_status                    grain: one row per customer per month
    customer_key         FK -> dim_customer.customer_key
    plan_key              FK -> dim_plan.plan_key
    month_key              FK -> dim_date.date_key   (month-end)
    status (active/paused/cancelled), mrr

  fact_box_contents                           grain: one row per product per box shipped
    box_key                PK
    customer_key             FK -> dim_customer.customer_key
    product_key                FK -> dim_product.product_key
    ship_date_key                FK -> dim_date.date_key
  ```

- **Why not just a transaction fact of subscription events
  (start/pause/resume/cancel)?** You could — that's a valid alternative
  design (an **accumulating snapshot** or event-stream style). Stating
  both options and picking one with a reason ("monthly snapshot makes
  MRR trivially a straight sum with no state-machine logic replayed at
  query time") is what's being scored, not which one you pick.
- **Q1** is a straight sum of the snapshot's MRR column filtered to
  `status = active`, grouped by month and plan tier — cheap precisely
  *because* the grain already bakes in "as of this month."
- **Q2** needs `dim_customer.signup_date` truncated to month as the
  cohort key, then for each cohort, tracking what fraction of that
  cohort's snapshot rows are still active N months later.
- **Q3** joins `fact_box_contents` → `dim_supplier`, and separately
  identifies customers whose `fact_subscription_status` shows
  `cancelled` within 30 days of a box ship date, then intersects.
- **Q4 (curveball):** this is a business-definition question disguised
  as a modeling question — the schema needs a `status` value expressive
  enough to distinguish `paused` from `cancelled` (not a single
  boolean!), so the *data model* doesn't force the churn definition —
  it lets whoever defines churn decide later whether "paused" counts.
  Flagging that a coarse boolean would have silently baked in a wrong
  answer is exactly the kind of foresight interviewers reward.

</details>

---

## C. SaaS Billing & Social Engagement

### Worked Scenario: SaaS Subscription Billing Analytics

This scenario's new shapes: the **accumulating snapshot fact table**
(a row that gets updated in place as an entity moves through a
lifecycle), the **periodic snapshot fact table** and why its measures
are only *semi-additive*, and a **self-referencing / ragged hierarchy**
(a comment that replies to a comment, in the companion scenario below).

**Interviewer prompt:**
> "Design a data model for a B2B SaaS company's billing and account
> lifecycle — trials, conversions, upgrades, churn — and answer some
> questions about revenue and conversion."

#### Step 1 — Clarifying questions

- **What does the business actually want to track: the lifecycle of an
  account, or its revenue over time?** → Both, and interviewer clarifies
  they're different questions needing different fact shapes: "how long
  does it take accounts to convert from trial" is a *lifecycle*
  question; "what was our MRR in March" is a *point-in-time* question.
- **Can an account move backward** (e.g. downgrade from paid back to
  trial)? → No, milestones are one-directional: trial → activated →
  paying → churned (an account can re-subscribe later, but that starts
  a *new* lifecycle row, it doesn't rewind the old one).
- **How often does MRR get reported?** → Monthly, as of the last day of
  the month.

#### Step 2 — Two fact tables, two different update patterns

> "`fact_account_lifecycle` is an **accumulating snapshot** — one row
> per account, with a column for *each* milestone date
> (`trial_start_date`, `activated_date`, `converted_date`,
> `churned_date`), and that row gets **updated in place** as the
> account passes each milestone — unlike a transaction fact, which
> only ever gets appended to.
>
> `fact_mrr_snapshot` is a **periodic snapshot** — one row per account
> per month, capturing MRR *as of* that month-end. It's appended once
> per month per account and never changed after the fact."

Naming the difference between "a row that gets revised as reality
progresses" (accumulating) and "a row that's a frozen point-in-time
measurement, append-only" (periodic) is exactly the vocabulary
interviewers are listening for when they ask "what fact table types do
you know?"

#### Step 3 — Dimensions and measures

| Dimension        | Notes |
|-------------------|-------|
| `dim_date`        | one row per calendar day, reused as multiple **roles** (trial_start, activated, converted, churned — see below) |
| `dim_account`     | account_id, industry, company_size_band, signup_channel |
| `dim_plan`        | plan tier, monthly_price — Type 2, since an account's plan changes over time and past MRR should reflect the plan *then* |

`fact_account_lifecycle` measures: `days_to_activate`,
`days_trial_to_paid` (both **derived/computed** measures — worth
mentioning that not everything in a fact table needs to come straight
from a source system; some columns are pre-computed at load time
specifically because "average days to convert" is asked constantly and
recomputing it from four date columns in every single query is wasteful
and error-prone).

`fact_mrr_snapshot` measure: `mrr` — **semi-additive**. Explicitly walk
through why: summing `mrr` across *accounts* for a given month is
correct (that's total company MRR). Summing `mrr` across *months* for
one account is meaningless (you'd get a number with no business
interpretation — MRR isn't consumed and replenished like a count of
sales, it's a balance that already represents "as of this moment").
This is the same family of caution as `surge_multiplier` in the
ride-share scenario, generalized: **snapshot measures are additive
across the dimension being snapshotted (accounts), never across time.**

#### Step 4 — Schema shape, with role-playing dimensions called out

> "`fact_account_lifecycle` references `dim_date` four separate times —
> once per milestone — under four aliases:
> `trial_start_date_key`, `activated_date_key`, `converted_date_key`,
> `churned_date_key`. Same pattern as pickup/dropoff location in the
> ride-share example: one physical dimension table, multiple **roles**."

```
fact_account_lifecycle:
    dim_account, dim_plan,
    dim_date AS trial_start, dim_date AS activated,
    dim_date AS converted,   dim_date AS churned
    -> measures: days_to_activate, days_trial_to_paid (nullable until milestone reached)

fact_mrr_snapshot:
    dim_date (month-end), dim_account, dim_plan
    -> measure: mrr
```

Same shape, with every column and every join key named:

```
dim_date                            dim_account
  date_key            PK              account_key         PK, surrogate
  full_date                           account_id               natural key
  month, quarter                      industry
  (row -1 = "unknown member",         company_size_band
   for milestones not yet reached)    signup_channel

dim_plan  (Type 2)
  plan_key            PK, surrogate
  plan_id                  natural key
  plan_tier
  monthly_price
  valid_from / valid_to / is_current

fact_account_lifecycle                      grain: one row per account lifecycle (updated in place)
  account_key              FK -> dim_account.account_key
  plan_key                  FK -> dim_plan.plan_key             (row current when milestone hit)
  trial_start_date_key       FK -> dim_date.date_key   (role: trial_start)
  activated_date_key          FK -> dim_date.date_key   (role: activated)
  converted_date_key           FK -> dim_date.date_key   (role: converted; -1 if not yet)
  churned_date_key               FK -> dim_date.date_key   (role: churned; -1 if not yet)
  days_to_activate, days_trial_to_paid

fact_mrr_snapshot                           grain: one row per account per month-end
  account_key              FK -> dim_account.account_key
  plan_key                   FK -> dim_plan.plan_key            (row current at that month-end)
  month_end_date_key           FK -> dim_date.date_key
  mrr
```

`dim_date` gets joined into `fact_account_lifecycle` four separate
times under four different foreign-key columns, all pointing at the
same physical table — the role-playing pattern again, this time on the
dimension the whole schema otherwise treats as the most generic one.

Note the nullability point out loud: an account still in trial has
`converted_date_key` and `churned_date_key` pointing at an **unknown
member** row in `dim_date` (a placeholder row meaning "not yet
happened"), rather than a database NULL — this keeps every foreign key
valid and every join behaving the same way, whether or not the
milestone has occurred yet. This is a standard Kimball technique and a
strong thing to mention unprompted.

#### Step 5 — Now query it

**Q1: "Trial-to-paid conversion rate by signup channel, for trials
started in Q1."**
> Filter `fact_account_lifecycle` on `trial_start_date` in Q1 (joining
> `dim_date` via the trial-start role), join `dim_account` for channel,
> count rows where `converted_date_key` is *not* the unknown-member
> placeholder over count of all rows, grouped by channel.

**Q2: "MRR trend for the last 12 months, broken down by plan tier."**
> Straight from `fact_mrr_snapshot`: filter the last 12 month-end dates,
> group by month and plan tier, sum `mrr`. Note explicitly this is safe
> because we're summing across accounts *within* a month, never across
> months — the semi-additive rule from Step 3.

**Q3: "Net revenue retention — this month's MRR from accounts that were
already paying customers last month, divided by last month's MRR."**
> Requires joining `fact_mrr_snapshot` to itself, one copy filtered to
> this month, one filtered to last month, matched on account, only
> keeping accounts present in both. Flag this as a self-join over a
> periodic snapshot — a very common "now design the query" follow-up
> once the snapshot table exists.

**Q4 (curveball): "An account churns, then resubscribes 6 months later.
Same account, same lifecycle row, or a new one?"**
> New row. Overwriting the original `fact_account_lifecycle` row would
> destroy the fact that a real churn event happened — you'd lose the
> "days as a paying customer before churning" history. A second
> lifecycle row (same `dim_account`, new milestone dates) preserves
> both stories. This is the accumulating-snapshot analog of the
> Type 1-vs-Type 2 disambiguation: don't let an update erase something
> that was genuinely, historically true.

#### Step 6 — Trade-offs, stated unprompted

> "I picked a fixed set of milestone columns for the accumulating
> snapshot because the lifecycle here has a small, known number of
> stages. If the lifecycle had an open-ended number of stages (e.g. a
> multi-step approval workflow with a variable number of steps), a
> fixed-column accumulating snapshot stops working and you'd want an
> event-log transaction fact instead, computing stage durations at
> query time. Fixed stages, small in number, known in advance — that's
> the litmus test for reaching for this pattern."

---

### Now You Try: Social Media Engagement

**Interviewer prompt:**
> "Design a data model for a social platform's engagement analytics —
> posts, likes, follows, and comment threads (comments can reply to
> other comments). Then answer the questions below."

**Questions to answer once you have a schema:**
1. Daily active engagers (users who liked, commented, or posted) by
   week.
2. Follower growth by week for a given account.
3. Average reply depth of comment threads on posts from verified
   accounts.
4. Curveball: an account is deleted and its 50,000 posts need to
   disappear from all historical reports. Does that change last year's
   "posts per day" number?

<details>
<summary>Debrief — expand only after you've attempted it</summary>

- **Grain:** three factless fact tables — `fact_likes` (one row per
  like), `fact_follows` (one row per follow *event*, with a
  `follow`/`unfollow` type so you can compute net followers over time),
  `fact_comments` (one row per comment). None of these need a numeric
  measure — existence of the row is the fact, same principle as
  cart-abandonment browsing in the e-commerce scenario above.
- **Columns and join keys:**

  ```
  dim_account                         dim_post
    account_key         PK              post_key            PK
    account_id               natural key  account_key           FK -> dim_account.account_key
    is_verified                          posted_date_key         FK -> dim_date.date_key

  dim_comment  (self-referencing / ragged hierarchy)
    comment_key         PK
    post_key              FK -> dim_post.post_key
    account_key             FK -> dim_account.account_key   (who wrote it)
    parent_comment_key        FK -> dim_comment.comment_key  (NULL/-1 if top-level;
                                                               points at another row in
                                                               this same table otherwise)

  fact_likes                          fact_follows
    date_key    FK -> dim_date.date_key    date_key      FK -> dim_date.date_key
    account_key FK -> dim_account.account_key  follower_account_key FK -> dim_account.account_key
    post_key    FK -> dim_post.post_key         followed_account_key FK -> dim_account.account_key
    (factless)                              event_type (follow/unfollow)  (factless)

  fact_comments
    comment_key   FK -> dim_comment.comment_key
    date_key      FK -> dim_date.date_key
    (factless — the comment's existence is dim_comment's row; this
     fact table exists mainly to give comments a queryable date grain)
  ```

  `dim_comment.parent_comment_key` pointing back at `dim_comment`'s own
  primary key — not at a separate table — is exactly what makes this a
  self-referencing hierarchy rather than a normal dimension join.
  `fact_follows` also has two foreign keys into the *same* `dim_account`
  table (`follower_account_key`, `followed_account_key`) — another
  role-playing pair, same pattern as pickup/dropoff and the four
  `dim_date` roles in the SaaS example above.
- **The comment-reply structure is a self-referencing (parent-child)
  hierarchy**, not a separate dimension: `dim_comment` (or the comment
  row itself) has a `parent_comment_id` pointing back to another
  comment. Call this out as a **ragged hierarchy** — reply depth is
  unbounded and uneven (some threads are 2 deep, others 30), which is
  exactly the case where you don't try to flatten it into fixed
  `reply_level_1`, `reply_level_2`, ... columns the way a fixed
  category hierarchy might be flattened — you'd need a recursive
  traversal at query time instead (or a precomputed `depth` measure at
  load time, cheaper to query, recomputed at load).
- **Follower "count" is a derived semi-additive-style measure**, not
  stored directly — it's `running count of follow events minus unfollow
  events up to a point in time`, which argues for a periodic snapshot
  (`fact_follower_count_daily`, one row per account per day) *precomputed*
  at load time specifically so Q2 doesn't require summing an unbounded
  event history at query time — the same "precompute what's asked
  constantly" reasoning as `days_to_activate` in the SaaS example.
- **Q1** unions distinct users appearing in any of the three factless
  facts per day, then counts distinct users per week.
- **Q3** requires walking the `parent_comment_id` chain per post
  (recursive) to compute max depth, filtered to posts by accounts where
  `dim_account.is_verified` is true — flag this explicitly as a
  recursive-query shape, unusual among these examples, and worth
  naming as such rather than glossing over it.
- **Q4 (curveball):** the honest answer is "it depends on the reporting
  contract, and that's a business decision, not just a technical one" —
  a **hard delete** (removing the rows) *would* retroactively change
  last year's numbers, which is often *not* desired for audited metrics;
  a **soft delete** (flagging the account/posts as deleted but keeping
  the historical fact rows, filtered out of *current* views by default)
  preserves history while still letting "active platform state" queries
  exclude deleted content. Recognizing that this is the same "correction
  vs. real change" family of question as the SCD curveballs — but now
  applied to whether rows should vanish at all — is the tell of someone
  generalizing the pattern rather than memorizing five separate answers.

</details>

---

## D. IoT / Sensor Telemetry (New)

### Worked Scenario: Industrial Equipment Telemetry

This scenario is chosen specifically because raw event volume makes the
"just append every reading" instinct actively wrong, and it forces the
**rollup-of-a-rollup** trap: an average that was already an average
cannot be safely re-averaged.

**Interviewer prompt:**
> "Design a data model for monitoring industrial equipment across
> several manufacturing sites — thousands of sensors reporting
> temperature, vibration, and pressure readings. Analysts need
> dashboards on equipment health, and ops needs to know when a sensor
> or a piece of equipment is having problems."

#### Step 1 — Clarifying questions

- **What's the raw ingestion rate?** Each sensor reports every 5-10
  seconds; ~50,000 sensors across all sites. → That's roughly half a
  billion raw readings a day — far too much row volume for a
  dimensional warehouse to hold at native grain forever.
- **Does the warehouse need every raw reading, or a rollup?** →
  Interviewer clarifies: the warehouse is for trend dashboards and
  historical reporting, not real-time alerting — alerting runs off a
  separate stream-processing/time-series system that already handles
  raw readings and fires alarms directly. This is the key scoping
  question: it moves "store every raw point forever" off the table
  before you design a single column.
- **What changes over time that needs history?** Sensor firmware
  version changes calibration behavior; a sensor can be physically
  moved from one piece of equipment to another. → Signals SCD Type 2.
- **Retention?** Minute-level rollups for 13 months, daily rollups
  indefinitely.

#### Step 2 — Declare the grain

> "The core fact table's grain is: one row per sensor per one-minute
> interval, pre-aggregated at ingestion — not one row per raw reading.
> A second, factless fact table tracks equipment fault/alarm events at
> their own grain: one row per fault event."

This is the scenario's central lesson stated as a sentence: the grain
decision here is inseparable from a volume/cost decision. Raw
per-second readings live in a cheaper time-series store or object
storage upstream; only the rollup that analysts actually query lands in
the dimensional warehouse.

#### Step 3 — Dimensions and measures

| Dimension          | Notes |
|---------------------|-------|
| `dim_sensor`        | sensor_id, sensor_type, firmware_version — Type 2, since firmware version changes the calibration curve and historical readings must be interpreted against the firmware that was active *then* |
| `dim_equipment`     | equipment_id, equipment_type, install_date |
| `dim_site`          | site_id, site_name, region |
| `dim_date` / `dim_time` | standard, at minute grain for the rollup |

| Measure                | Additive?        | Notes |
|-------------------------|-------------------|-------|
| `reading_count`         | Yes               | how many raw readings fed this minute's rollup |
| `sum_temperature`       | Yes               | store the SUM, not just the average |
| `avg_temperature`       | **No** (derived)  | `sum_temperature / reading_count` — never store a bare average as if it were additive |
| `max_temperature`       | No (non-additive) | max of a max across a wider window is valid; sum of maxes is not |
| `min_vibration`         | No (non-additive) | same reasoning as max |

This is the scenario's second core lesson, and it's a sharper version of
the semi-additive caution from the SaaS billing scenario: **an average
of averages is not the same number as the true average**, unless every
group being averaged has exactly equal weight. If minute 1 had 6
readings averaging 70° and minute 2 had 6 readings averaging 90°,
`AVG(avg_temperature)` across the two minutes correctly gives 80°
*only* because both minutes happened to have equal reading counts — the
moment reading counts differ (a sensor drops some readings, a minute is
partial), naively averaging the pre-aggregated averages silently gives
the wrong answer. Storing `sum_temperature` and `reading_count`
separately, and always deriving the average as
`SUM(sum_temperature) / SUM(reading_count)` at query time, is the fix —
and it's exactly the kind of design decision that prevents a whole
class of "why does our dashboard's average not match the raw data"
bugs before they ship.

#### Step 4 — Schema shape

```
dim_sensor  (Type 2)                dim_equipment
  sensor_key         PK, surrogate    equipment_key       PK
  sensor_id               natural key  equipment_id            natural key
  sensor_type                         equipment_type
  firmware_version                    install_date
  valid_from / valid_to / is_current  site_key              FK -> dim_site.site_key

dim_site
  site_key           PK
  site_name
  region

fact_sensor_readings_1min                   grain: one row per sensor per one-minute interval
  reading_key              PK
  minute_key                FK -> dim_date.date_key (+ minute component)
  sensor_key                 FK -> dim_sensor.sensor_key      (row current at reading time)
  equipment_key                FK -> dim_equipment.equipment_key
  reading_count, sum_temperature, max_temperature, min_temperature,
  sum_vibration, max_vibration

fact_equipment_faults                       grain: one row per fault/alarm event (factless)
  fault_key                 PK
  date_key                    FK -> dim_date.date_key
  equipment_key                 FK -> dim_equipment.equipment_key
  sensor_key                      FK -> dim_sensor.sensor_key
  fault_type (dimension-like attribute, small fixed set — kept directly
              on the fact table rather than its own dimension, see
              `04_curveballs_tradeoffs.md`'s "does this need a whole
              dimension" curveball)
```

#### Step 5 — SCD decision, stated explicitly

> "`dim_sensor.firmware_version` is Type 2, because a firmware update
> changes how raw voltage gets converted into a temperature or vibration
> reading — a historical reading needs to be interpreted against the
> firmware that was active when it was taken, exactly like the ride-share
> rider's subscription tier. If a sensor is physically reassigned from
> one piece of equipment to another, that's also Type 2 on the
> equipment/sensor relationship, for the same reason: a fault six months
> ago should stay attributed to the equipment it was actually mounted on
> then, not wherever it happens to be mounted today."

#### Step 6 — Now query it

**Q1: "Average temperature by equipment type, last 7 days."**
> The rollup-of-a-rollup trap in action: this is **not**
> `AVG(avg_temperature)` grouped by equipment type. It's
> `SUM(sum_temperature) / SUM(reading_count)`, joined from
> `fact_sensor_readings_1min` through `dim_equipment`, filtered to the
> last 7 days, grouped by equipment type — recomputing the true average
> from the stored sums rather than averaging pre-aggregated averages.

**Q2: "Count of faults per site per month."**
> Straightforward factless-fact count: join `fact_equipment_faults` →
> `dim_equipment` → `dim_site`, group by site and month, count rows.

**Q3 (curveball): "Which sensors went silent — stopped reporting
entirely — in the last 24 hours?"**
> This is an anti-join / absence question, structurally different from
> every other query in this file: you're looking for sensors that
> *should* have rows in `fact_sensor_readings_1min` for the last 24
> hours (one row per minute, per active sensor) but don't. Solve it by
> generating the expected (sensor, minute) grid from `dim_sensor` ×
> a minute-level date spine, then left-joining against the actual fact
> table and filtering to unmatched rows — flag this explicitly as a
> different query shape (expected-vs-actual, not filter-and-aggregate)
> from anything else in this file.

#### Step 7 — Trade-offs, stated unprompted

> "The single biggest modeling decision here happened before the star
> schema even started: pre-aggregating to one-minute rollups at
> ingestion, rather than trying to land every raw reading in the
> warehouse. That cost real-time granularity in the warehouse itself —
> which is fine, because true real-time alerting is handled by a
> separate stream-processing layer, not this reporting schema. If the
> business ever needs second-level historical granularity in the
> warehouse directly, that's a genuinely new requirement, not a tuning
> tweak — worth naming as its own conversation rather than quietly
> trying to shoehorn it into the existing rollup grain."

---

## E. Marketing Attribution (New)

### Worked Scenario: Multi-Touch Marketing Attribution

This scenario is chosen because it needs a bridge table with a *weight*
column that's populated by whatever attribution algorithm the business
picks — the schema has to support the business logic changing without
itself being redesigned every time marketing changes its mind about how
credit should be split.

**Interviewer prompt:**
> "Design a data model for marketing attribution — a customer sees ads,
> clicks emails, and visits organically across several channels before
> eventually converting. Marketing wants to know which channels
> actually drive conversions, under more than one attribution model."

#### Step 1 — Clarifying questions

- **What counts as a "touchpoint"?** An ad impression, an ad click, an
  email open, an email click, an organic site visit. → Confirmed; each
  is a distinct, timestamped interaction.
- **Single-touch or multi-touch attribution?** → Interviewer clarifies:
  marketing currently uses last-touch, but wants the schema to support
  first-touch, linear, and time-decay models too, without a redesign
  every time they change their mind. → This is the signal that
  attribution weighting needs to live in *data*, not be hard-coded into
  the schema or the query logic.
- **Cross-device identity resolution?** → Assume a resolved
  `customer_key` is already available (identity resolution itself is a
  separate upstream problem, out of scope for this design).
  **Attribution window?** → 30 days: only touchpoints within 30 days
  before a conversion are eligible for credit.

#### Step 2 — Declare the grain

> "Two fact tables: `fact_touchpoints` — one row per touchpoint per
> customer (factless for organic channels, with a `spend` measure for
> paid channels). `fact_conversions` — one row per conversion event,
> with `conversion_value`. A bridge table,
> `bridge_conversion_touchpoints`, connects the two — one row per
> (conversion, touchpoint) pair that falls inside the attribution
> window, carrying a `credit_weight` column."

#### Step 3 — Dimensions and the attribution bridge

| Dimension       | Notes |
|-----------------|-------|
| `dim_channel`   | paid_search, organic_search, email, paid_social, direct |
| `dim_campaign`  | campaign_id, campaign_name, channel_key — Type 1, campaign metadata rarely needs history |
| `dim_customer`  | Type 2 for lifecycle stage; `acquisition_channel` is Type 0 — the very first channel that ever brought the customer in is immutable by definition, it can never legitimately be overwritten |

The bridge table is the new pattern this scenario exists to teach:

```
bridge_conversion_touchpoints
  conversion_key   FK -> fact_conversions.conversion_key
  touchpoint_key   FK -> fact_touchpoints.touchpoint_key
  attribution_model TEXT  -- 'last_touch', 'linear', 'time_decay', ...
  credit_weight    REAL   -- e.g. 1.0 for the credited touch under
                            last-touch; 0.25 each under linear with 4
                            touchpoints; a decayed fraction under
                            time-decay
  PRIMARY KEY (conversion_key, touchpoint_key, attribution_model)
```

This is a **bridge table with a payload** — unlike
`bridge_product_category` in the e-commerce scenario, which only
recorded *that* a relationship existed, this bridge also records *how
much* credit that relationship carries, and does so once per
attribution model, so several models' credit assignments can coexist
side by side without overwriting each other.

#### Step 4 — Schema shape

```
dim_channel                         dim_campaign  (Type 1)
  channel_key        PK               campaign_key       PK
  channel_name                        campaign_name
                                       channel_key           FK -> dim_channel.channel_key

dim_customer  (Type 2, acquisition_channel Type 0)
  customer_key       PK, surrogate
  customer_id             natural key
  acquisition_channel   (Type 0 -- never overwritten)
  lifecycle_stage       (Type 2)
  valid_from / valid_to / is_current

fact_touchpoints                            grain: one row per touchpoint per customer
  touchpoint_key           PK
  date_key                  FK -> dim_date.date_key
  customer_key                FK -> dim_customer.customer_key
  channel_key                   FK -> dim_channel.channel_key
  campaign_key                    FK -> dim_campaign.campaign_key
  spend  (NULL/0 for organic channels, a real cost for paid)

fact_conversions                            grain: one row per conversion event
  conversion_key            PK
  date_key                    FK -> dim_date.date_key
  customer_key                  FK -> dim_customer.customer_key
  conversion_value

bridge_conversion_touchpoints                (see Step 3 above)
```

#### Step 5 — SCD/immutability decision, stated explicitly

> "`dim_customer.acquisition_channel` is Type 0 — it's set once, on the
> customer's very first touchpoint, and never changes again, by
> definition: 'the channel that first acquired this customer' can only
> ever refer to one historical fact. `lifecycle_stage` (lead, trial,
> customer, churned) is Type 2, because marketing genuinely needs to
> know what stage a customer was in *when* a given touchpoint or
> conversion happened, not their stage today."

#### Step 6 — Now query it

**Q1: "Revenue by channel, under last-touch attribution."**
> Join `fact_conversions` → `bridge_conversion_touchpoints` (filtered to
> `attribution_model = 'last_touch'`, where every conversion has exactly
> one row with `credit_weight = 1.0`) → `fact_touchpoints` → `dim_channel`,
> sum `conversion_value * credit_weight`, group by channel.

**Q2: "Revenue by channel, under linear attribution — same conversions,
different answer."**
> The exact same query shape as Q1, with the filter changed to
> `attribution_model = 'linear'` instead. This is the entire payoff of
> designing the bridge table this way: switching attribution models is
> a `WHERE` clause change, not a schema change or a rewritten ETL
> pipeline, because the weighting logic already lives in data rather
> than being hard-coded into a specific query.

**Q3: "Customer acquisition cost (CAC) by channel."**
> Total `spend` from `fact_touchpoints` for paid channels, divided by
> count of conversions attributed to that channel (via whichever
> attribution model is in use) — flag that this ties `fact_touchpoints`'
> spend measure and the bridge table's credit-weighted conversion count
> together across two different fact tables, joined through the
> conformed `dim_channel`.

**Q4 (curveball): "Marketing wants to switch to a data-driven
attribution model where a machine learning model outputs a custom
weight per touchpoint per conversion. Does the schema support that?"**
> Yes, without any schema change: the ML model's output is just another
> value of `attribution_model` in the bridge table, with whatever
> `credit_weight` values the model computes. The schema was designed
> from the start to keep "how attribution weights are computed" a
> pluggable, data-driven concern rather than something baked into table
> structure — this is worth stating explicitly as the reason the bridge
> table has an `attribution_model` column at all, not just a
> `credit_weight`.

#### Step 7 — Trade-offs, stated unprompted

> "The attribution window (30 days) is a business rule that gets baked
> into the ETL process that *populates* the bridge table — deciding
> which touchpoints are even eligible to be linked to a conversion — not
> something the schema itself enforces at query time. If marketing
> changes the window from 30 to 14 days, that's a re-run of the bridge
> table's population logic with a different parameter, not a schema
> redesign. Worth naming that boundary explicitly, the same way the
> real-time curveball elsewhere separates 'what changes about the model'
> from 'what changes about the pipeline that populates it.'"

---

## F. Healthcare / Clinical Encounters (New)

### Worked Scenario: Clinical Encounter Analytics

This scenario is chosen for two patterns nothing else in this file
forces: a dimension large and hierarchical enough that flattening it is
the wrong default (a genuine case for snowflaking, not just a
textbook aside), and an **identity-merge** problem — the mirror image of
the ID-reuse bug covered in `03_critique_and_debug.md`.

**Interviewer prompt:**
> "Design a data model for a hospital network's clinical encounter
> analytics — visit volume, length of stay, readmissions, revenue by
> insurance plan. Then answer some questions against it."

#### Step 1 — Clarifying questions

- **PII/compliance handling?** → Patient identity is tokenized upstream;
  the warehouse only ever sees a de-identified patient key, but still
  needs full historical accuracy for demographics and insurance.
- **Grain of the core event?** One row per encounter (a visit), or per
  billable procedure line within an encounter? → Interviewer says: both
  are needed — encounter-level for length-of-stay and readmission
  questions, procedure-line-level for billing/revenue questions. Two
  fact tables, same discipline as the e-commerce order-header/order-line
  split.
- **Does insurance matter historically?** → Yes — a claim must be
  attributed to the insurance plan active *at the time of the
  encounter*, not whatever plan the patient has today. Strong SCD Type 2
  signal.
- **Scale?** Tens of thousands of diagnosis codes (ICD-10 has roughly
  70,000), a few hundred facilities, millions of encounters a year.

#### Step 2 — Declare the grains

> "`fact_encounters` — one row per patient encounter/visit.
> `fact_procedures` — one row per billable procedure line item within an
> encounter. Same relationship as an order header and its order lines
> in the e-commerce scenario — don't collapse the two grains into one
> table, or a line-item measure repeated across an encounter's rows will
> get double-counted exactly like Case 1 in `03_critique_and_debug.md`."

#### Step 3 — Dimensions, including the large-hierarchy case

| Dimension            | Notes |
|------------------------|-------|
| `dim_patient`         | Type 2 for `insurance_plan` and `address` (claims need historical accuracy); Type 0 for `date_of_birth`, `blood_type` — but see the curveball in Step 6 |
| `dim_provider`        | the treating doctor — Type 1, provider metadata corrections are rare and not history-sensitive here |
| `dim_facility`        | facility_id, facility_name, region |
| `dim_diagnosis`       | ICD-10 code, description — **snowflaked**: see below |
| `dim_diagnosis_category` | the ~20-25 top-level ICD-10 chapter categories |
| `dim_encounter_flags` | junk dimension: `is_emergency`, `is_telehealth`, `is_readmission_flagged` bundled together, same pattern as `dim_order_flags` in `concepts/02_dimensional_modeling.md` |

**Why `dim_diagnosis` is snowflaked, not flattened:** ICD-10 has on the
order of 70,000 codes, organized into roughly two dozen chapter-level
categories. Flattening the category name onto all 70,000 diagnosis rows
(the star-schema default) means that if a category's *definition* is
ever administratively revised, tens of thousands of rows need updating.
Because "revenue/encounters by diagnosis category" is a extremely common
report queried largely at the category level, and the category
hierarchy itself is small (a few dozen rows) and rarely changes,
splitting it into its own `dim_diagnosis_category` table — one extra
join — is exactly the trade-off `concepts/03_star_snowflake_schema.md`
describes as the case where snowflaking earns its keep: a huge,
deep-ish hierarchy, frequently queried at an intermediate level on its
own.

#### Step 4 — Schema shape

```
dim_patient  (Type 2: insurance_plan, address; Type 0: date_of_birth, blood_type)
  patient_key         PK, surrogate
  patient_token             natural key (de-identified)
  date_of_birth, blood_type   (Type 0)
  insurance_plan, address     (Type 2)
  valid_from / valid_to / is_current

dim_diagnosis_category              dim_diagnosis
  category_key       PK               diagnosis_key       PK
  category_name                       icd10_code               natural key
                                       description
                                       category_key          FK -> dim_diagnosis_category.category_key

dim_provider                        dim_facility
  provider_key       PK               facility_key        PK
  provider_name                       facility_name
  specialty                           region

dim_encounter_flags   (junk dimension)
  flag_key           PK
  is_emergency, is_telehealth, is_readmission_flagged

fact_encounters                             grain: one row per patient encounter/visit
  encounter_key             PK
  admit_date_key              FK -> dim_date.date_key    (role: admit)
  discharge_date_key            FK -> dim_date.date_key  (role: discharge)
  patient_key                     FK -> dim_patient.patient_key       (row current at encounter time)
  provider_key                      FK -> dim_provider.provider_key
  facility_key                        FK -> dim_facility.facility_key
  primary_diagnosis_key                 FK -> dim_diagnosis.diagnosis_key
  flag_key                                FK -> dim_encounter_flags.flag_key
  length_of_stay_days

fact_procedures                             grain: one row per billable procedure line
  procedure_line_key        PK
  encounter_key                FK -> fact_encounters.encounter_key
  date_key                       FK -> dim_date.date_key
  patient_key                      FK -> dim_patient.patient_key
  procedure_cost, insurance_paid_amount, patient_owed_amount
```

`admit_date_key` and `discharge_date_key` are another role-playing pair
against `dim_date` — the same pattern as pickup/dropoff and the four
SaaS milestone dates, applied here to compute `length_of_stay_days`.

#### Step 5 — SCD decision, including the sharper Type 0 nuance

> "`insurance_plan` and `address` on `dim_patient` are Type 2 — a claim's
> revenue must be attributed to the plan active when the encounter
> happened, exactly like the SaaS `dim_plan` history. `date_of_birth`
> and `blood_type` are Type 0 by default, since they shouldn't change —
> **but** if a data-entry error is later discovered (a birthdate was
> mistyped at intake), the fix is a Type 1-style overwrite of that one
> wrong value, not a rejection of the correction on the grounds that
> 'Type 0 means never touch it.' Type 0 means the *business* value
> doesn't change over time, not that a data-quality bug in it can never
> be fixed — the same 'was the old value ever true, or was it just
> wrong' question from `concepts/04_slowly_changing_dimensions.md`
> applies even to a nominally Type 0 column."

#### Step 6 — Now query it

**Q1: "30-day readmission rate by diagnosis category."**
> Requires a self-join of `fact_encounters` against itself, matched on
> `patient_key`, looking for a second encounter within 30 days of a
> first encounter's discharge date (excluding the encounter matching
> itself) — the same self-join-over-a-fact-table shape as the SaaS
> net-revenue-retention query, but on encounters instead of MRR
> snapshots. Group the result by `dim_diagnosis_category` (via the
> snowflaked join) to get the rate per category.

**Q2: "Average length of stay by facility, last quarter."**
> Straightforward: join `fact_encounters` → `dim_facility`, filter
> `dim_date` (via the admit-date role) to last quarter, average
> `length_of_stay_days`, group by facility.

**Q3: "Revenue by insurance plan, attributed to the plan active at time
of encounter."**
> Sum `insurance_paid_amount` from `fact_procedures`, joined to
> `dim_patient` on the surrogate key that was current *when the
> procedure happened* — exactly the Type 2 "as of" payoff from
> `concepts/04_slowly_changing_dimensions.md`, applied to claims instead
> of ride-share fares.

**Q4 (curveball): "Two medical record numbers turn out to be the same
real patient — a duplicate registration gets discovered and merged. How
do you handle that in the dimension?"**
> This is the **identity-merge** problem — the mirror image of the
> ID-reuse bug in `03_critique_and_debug.md`, Case 6 (there, one natural
> key was wrongly *split* across two different real people over time;
> here, two natural keys need to be *merged* into one real person). The
> fix: assign one of the two patients' surrogate-key histories as the
> canonical one (or mint a new canonical surrogate key for the merged
> identity), and re-point every fact row that referenced the
> now-deprecated patient key at the canonical one going forward, while
> preserving — not deleting — the fact that two records existed
> historically, typically via a small `patient_merge_log` mapping table
> so the merge itself is auditable. This is meaningfully harder than the
> split case because it requires rewriting historical fact-table foreign
> keys rather than just correctly assigning new ones, and it's exactly
> the kind of question that separates "recited the surrogate-key
> slogan" from "has actually thought about what master data management
> failure modes look like in practice."

#### Step 7 — Trade-offs, stated unprompted

> "Snowflaking `dim_diagnosis` was a deliberate exception to defaulting
> to star schema everywhere else in this model — I made that call
> specifically because the diagnosis hierarchy is both huge (tens of
> thousands of codes) and commonly queried one level up, at the category
> grain. Every other dimension here stays flat, because none of them
> come close to that scale or that access pattern — I wouldn't reach for
> snowflaking as a general habit, only where the specific trade-off
> clearly wins, which is the same discipline `concepts/03_star_snowflake_schema.md`
> argues for."

---

## What Interviewers Are Actually Scoring

- Did you ask clarifying questions before designing?
- Did you state the grain explicitly, in one sentence, before naming
  tables?
- Can you justify star vs. snowflake for *this* case, not just recite
  the trade-off table?
- Do you pick SCD Type 1 vs. Type 2 based on *whether the old value was
  ever true* (Type 2) *or was just wrong* (Type 1) — not by pattern-
  matching the column name?
- When asked a business question, do you narrate joins/filters/
  aggregations in plain language, tying each one back to a specific
  table and key you already named?
- Do you flag non-additive and semi-additive measures (like
  `surge_multiplier`, `mrr`, or a rollup's `avg_temperature`) before
  someone builds a wrong report on top of them?

If you can do all of the above without writing a line of SQL, writing
the SQL afterward (see `concepts/` and `practice/`) is the easy part.

---

**Next:** [02 — Rapid-Fire Q&A](02_rapid_fire_qna.md)
