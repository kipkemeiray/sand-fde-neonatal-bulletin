# Deliverable 1 — Problem Decomposition & Scoping

---

## Section 1: Discovery Process

### 1.1 What "our data is a mess" actually means

The Director's sentence is a symptom report, not a problem statement. In my experience it decomposes into four failure classes, and they need completely different responses. Week 1 is spent working out which ones are actually present and in what proportion.

| Class | What it looks like | Test I would run in Week 1 |
|---|---|---|
| **Coverage** — data not captured | 175 paper facilities; whole catchments invisible | Count facilities submitting ≥1 report per month over the last 6 periods, split by facility type |
| **Latency** — captured, arrives too late | 2–3 week DHIS2 delay; decisions made on stale figures | Distribution of `days_after_period_end` per submission, by district and facility type |
| **Trust** — arrives, nobody believes it | Two systems give different numbers for the same facility | Reconcile 5 facilities across DHIS2 vs HealthTrack for one month; measure variance |
| **Usability** — trusted, but unusable | 40 hrs/month of Excel to make it readable | Watch the bulletin get compiled. Count the manual steps |

The reason this decomposition matters: **all four are called "our data is a mess", but only Usability and Latency are addressable in six weeks.** Coverage requires changing what 175 facilities physically do. Trust requires reconciling three source systems. Framing this back to the Director in Week 2 is the single most valuable thing I do — it converts an unbounded complaint into a scoped commitment.

### 1.2 Who I would talk to, and what I would ask

Ordered deliberately. I want the mechanics before the politics, because I want to arrive at the Director's office already knowing the answers to half of what he tells me.

| # | Who | The question that actually matters | What I am really testing |
|---|---|---|---|
| 1 | **The person who compiles the bulletin** (likely an M&E or HMIS officer) | "Can you show me the last one being made? Don't explain it — open the spreadsheet and do it." | Where the 40 hours actually go. My hypothesis is that most of it is *reconciliation and chasing*, not formatting — and if so, automating the formatting saves 8 hours, not 40 |
| 2 | **DHIS2 / HMIS system administrator** | "Who has API access, what's the instance version, when were analytics tables last generated, and who owns org unit metadata?" | Whether I can get data out at all in Week 1. This is the hardest blocker and the one most likely to be political rather than technical |
| 3 | **2–3 District Health Officers** | "Walk me through the last decision you made using this data. What did you actually look at?" | Whether the bulletin is *used* or merely *produced*. If DHOs have never opened it, automating it saves labour but changes nothing |
| 4 | **A facility data clerk / HRIO** (in person, at a facility) | "Show me the register. What happens to this book at the end of the month?" | The origin of every number in the system. Non-negotiable — see 1.3 |
| 5 | **MoH Director** | "When this is working, what decision will you make differently?" | The actual success criterion. If he cannot answer, the bulletin is a compliance artefact and I should scope for reliability, not insight |
| 6 | **Sand Solutions Manager & Country Director** | "What did we commit to in the MoU, and what does the MoH think we committed to?" | Gap between signed scope and expected scope. This gap is where FDE engagements die |
| 7 | **Central FDEs** | "Which country has solved bulletin automation already, and what broke?" | Reuse. I should not be first — see Deliverable 2 build-vs-buy |

### 1.3 What I would observe directly, not hear about

Reported process and actual process diverge, and the divergence is always where the data quality problem lives.

1. **The bulletin being compiled, in one sitting, over the analyst's shoulder.** I time each step and note every point where they leave Excel — to email someone, to check a figure, to correct something they know is wrong. Those exits are the real 40 hours.
2. **One facility's paper register, physically.** How a tally sheet becomes a monthly total. Whether the register matches what was keyed into DHIS2. This is where I find out if the national dataset is built on arithmetic done by hand under a deadline.
3. **A district officer opening the current bulletin.** Do they know where it is? What do they look at first? Do they trust it? If they immediately cross-check a number against something else, that cross-check is my real requirement.
4. **A HealthTrack server room.** "Buggy, local servers" is a sentence that hides a wide range of realities — from a flaky application to a machine that is powered off half the day. Which one determines whether Problem B is even possible.
5. **The DHIS2 instance itself.** Org unit tree depth, how many facilities are marked active vs. actually reporting, when analytics tables last ran, whether category combinations are consistent across programmes.

**Time-boxing note:** I would spend Days 1–3 on 1–4 above and hold the Director meeting until Day 4. Arriving at that meeting with observed evidence rather than questions is what earns the scope conversation.

---

## Section 2: Problem Selection

### 2.1 The choice: **Problem A — Quarterly Health Bulletin automation**

Scored against what a first engagement actually has to achieve.

| Criterion | **A — Bulletin** | **B — Real-time status** | **C — TB/HIV unified view** |
|---|---|---|---|
| Data already exists | ✅ Entirely in DHIS2 | ❌ Needs new capture from 175 paper sites | ⚠️ Exists, but in CommCare + EMRs |
| Deliverable in 6 weeks | ✅ Yes | ❌ No — needs infrastructure | ❌ No — needs identity resolution |
| Named owner in pain | ✅ Yes, measurable in hours | ⚠️ Diffuse across districts | ⚠️ Clinical, not operational |
| Blocked by infrastructure | ✅ No | ❌ Power 4–6 hrs/day, spotty 3G | ⚠️ Partially |
| Blocked by governance | ✅ No — aggregate only | ⚠️ Some | ❌ **Yes** — patient-level linkage, consent, HIV status is protected data |
| Failure is recoverable | ✅ Manual process still exists | ❌ Officers may act on wrong status | ❌ Clinical harm possible |
| Creates reusable assets | ✅ **Yes — see below** | ⚠️ Some | ⚠️ Limited |

### 2.2 Why A is not the easy option — it is the enabling one

The weak argument for A is "it's the quickest win." That is true and insufficient. The real argument is structural:

**A produces the facility-level reporting completeness and timeliness baseline for every facility in the country.** That baseline is not a by-product — it is one of the four sections the MoH already asks for in the bulletin. And it is precisely the input Problem B requires. You cannot build "real-time facility status" until you know which facilities report, how late, and through which system. Solving A instrumentsally the entire estate as a side effect of a deliverable the client already wants.

Sequenced properly: **A produces the data quality baseline → B becomes scopeable because you now know which 60 facilities can actually support near-real-time → C becomes governable because you have an established provenance and access-control pattern the Ministry has already signed off on.**

Doing C first, by contrast, means beginning with the highest political and clinical risk in the portfolio while holding zero credibility with the client.

**Second-order reason:** A is a *shipping* problem, not a *discovery* problem. In an engagement whose first job is to establish that Sand delivers, the correct first move is one where the failure modes are known.

### 2.3 The measurable outcome

> **By end of Week 6, the Quarterly Health Bulletin is generated from DHIS2 by an automated pipeline, reviewed and published by MoH staff in under 4 hours of human effort (from ~40), with every published figure carrying its reporting-completeness provenance and no figure published below a 60% completeness threshold.**

### 2.4 Success metrics

| # | Metric | Baseline | Target (Wk 6) | Why it is the right measure |
|---|---|---|---|---|
| **1** | Human hours per bulletin cycle | ~40 hrs/month | **< 4 hrs review** | The client's stated pain, in the client's units |
| **2** | Figures traceable to source | 0% | **100%** | The trust metric. Determines whether output survives its first dispute |
| **3** | Bulletin produced by MoH staff **without FDE involvement** | n/a | **1 full cycle** | The only metric that proves handover. Metrics 1 and 2 can be hit by an FDE doing the work faster |
| **4** | Data quality issues surfaced and assigned an owner | 0 (invisible) | **> 20, with named owners** | Converts invisible data debt into a Ministry work queue — the thing that makes quality improve after we leave |

Metric 3 is the one I would actually be judged on. The other three can be satisfied by an engineer who has made himself indispensable.

### 2.5 Explicitly OUT of scope

Stating this in writing in Week 2, and having the Director acknowledge it, is what prevents the six-week sprint becoming a nine-month one.

- ❌ Real-time or near-real-time facility status *(Problem B — sequenced after)*
- ❌ TB/HIV patient-level record linkage *(Problem C — requires a governance track first)*
- ❌ Digitising the 175 paper facilities *(programme, not a sprint)*
- ❌ Fixing or replacing HealthTrack EMR *(vendor issue; I will document, not repair)*
- ❌ Changing DHIS2 data element definitions or the org unit hierarchy *(I surface defects; the MoH owns the metadata)*
- ❌ Retrospective correction of historical data *(pipeline reports from the quarter forward; back-correction is a separate decision the MoH must make)*
- ❌ Public-facing publication of the bulletin *(MoH sign-off remains a human gate — deliberately)*
- ❌ Custom mobile app for districts *(Health Atlas covers the mapped view)*

### 2.6 Key assumptions and Week-2 validation plan

| ID | Assumption | Risk if wrong | How I validate it in Week 2 |
|---|---|---|---|
| **A1** | I can get read API access to the national DHIS2 instance | 🔴 **Fatal** — no pipeline | Request Day 1, escalate via Country Director Day 3. Fallback: scheduled Excel/CSV exports, which is how the analyst already gets data |
| **A2** | All four bulletin sections derive from data already in DHIS2 | 🟠 High — scope grows | Reverse-engineer the last published bulletin figure by figure against the DHIS2 instance |
| **A3** | Data element UIDs are stable and consistently used across districts | 🟠 High — metrics wrong per district | Pull metadata, check category combination consistency across programmes; sample 5 districts |
| **A4** | The 40 hrs is mostly compilation, not chasing and reconciliation | 🟠 High — automation saves far less | Time-and-motion observation (Discovery step 1). **This is the assumption most likely to be wrong** |
| **A5** | Someone in the MoH IT team can maintain a Python/SQL pipeline | 🟠 High — no sustainable handover | Meet the team Week 2; assess skills honestly. If absent, this changes the architecture — see fallback |
| **A6** | The bulletin is read and used by districts | 🟡 Medium — we automate a compliance artefact | Ask 3 DHOs to show me where they keep it |
| **A7** | Aggregate-only data means no patient-privacy governance gate | 🟡 Medium — delays | Confirm with MoH data governance lead in Week 2 |

### 2.7 Fallback plan

Three tiers, decided at fixed checkpoints so the decision is not made under end-of-sprint pressure.

**Trigger 1 — No API access by end of Week 2 (A1 fails)**
→ Switch to scheduled CSV/Excel export ingestion. The pipeline's ingest layer is already a config-driven adapter precisely to make this a configuration change rather than a rewrite. Cost: manual export step remains; still cuts ~30 of the 40 hours.

**Trigger 2 — Data quality worse than expected, or A4 proves the 40 hours is reconciliation (end of Week 3)**
→ Re-scope from *"automate the bulletin"* to *"automate the three most reliable sections + ship the data quality worklist."* The worklist becomes the primary deliverable and the bulletin the secondary. This is a smaller promise but a more honest one, and the quality worklist is arguably worth more to the Ministry.

**Trigger 3 — No maintainer identified (A5 fails, end of Week 4)**
→ Simplify the stack deliberately: drop orchestration, ship a single documented Python entrypoint plus a scheduled job, and re-target training at the analyst rather than IT. **A simpler system that survives is worth more than a better one that does not.** Escalate the capacity gap to the Country Director as a staffing issue for the MoU, not an engineering problem.

**Standing fallback:** the manual process is never switched off during the sprint. Week 6 runs both in parallel and reconciles. The manual process is retired only after one clean cycle produced without me.

---

## Section 3: Stakeholder & Communication Plan

*Not requested, but an FDE engagement fails here more often than it fails technically.*

| Stakeholder | Cadence | Format | What they need from me |
|---|---|---|---|
| MoH Director | Weekly, 15 min | One page, no jargon | Progress against the 40-hour number; early warning on scope |
| Bulletin analyst | Daily, informal | Working alongside | To feel like co-author, not subject. This person can quietly kill adoption |
| MoH IT team | 2× weekly from Week 3 | Pairing at a keyboard | Hands on the system early — not a handover event in Week 6 |
| Sand Solutions Manager | Weekly | Written status + risks | Scope creep signals, MoU gaps |
| Country Director | On exception | Escalation | Access blockers (A1) that need political rather than technical resolution |
