# Deliverable 3 — Production Hardening

The prototype proves the concept. These are the five things that stand between it and a system a Ministry depends on quarterly. Ordered by what fails first and costs most.

---

### 1. Silent failure — the pipeline must refuse to produce a plausible-looking wrong bulletin

**Concern.** The most dangerous failure mode is not a crash; it is the run that completes successfully and produces a well-formatted bulletin built on a partial extract. I hit exactly this during the build: a type mismatch caused every indicator to be suppressed and the pipeline exited 0 with a complete, empty, professional-looking document. In production that reaches a Director. A crash gets fixed in an hour; a quietly wrong bulletin gets circulated to 47 districts.

**How I would address it.**
- Hard assertion gates between stages: expected row-count ranges, expected facility counts, expected period coverage. Fail loudly and exit non-zero rather than degrade.
- Run-over-run comparison: if total facilities reporting, or any headline indicator, moves more than a configured threshold versus the prior quarter, the run halts and requires explicit human acknowledgement.
- A `--strict` mode used for scheduled production runs where any suppressed core indicator blocks publication rather than rendering as SUPPRESSED.
- Every run writes a manifest: source file hashes, row counts, config version, git SHA, timestamp. A bulletin that cannot be reproduced from its manifest is not publishable.

---

### 2. Provenance and reproducibility — every published figure must be defensible six months later

**Concern.** A district disputes a figure in the Q4 bulletin in March. Nobody can reconstruct what the data looked like in January, because DHIS2 has been back-corrected in the interim. The Ministry cannot defend its own published document, and the credibility loss lands on the system, not on the data.

**How I would address it.**
- Immutable snapshot of the raw extract, stored with the manifest at run time. The bulletin is reproducible from its snapshot forever, independently of DHIS2's current state.
- Append-only run history table: who ran it, against which snapshot, which config, what was suppressed and why.
- Drill-down from every published figure to contributing org units and periods — currently aggregated away in the prototype.
- Publish a stated back-correction policy with the MoH: DHIS2 data changes after publication, so the bulletin must declare its extract date on the document itself. This is a governance decision the Ministry owns; my job is to force the decision rather than let it be discovered during a dispute.

---

### 3. Data quality detection — from naive heuristics to something a district officer will accept

**Concern.** The prototype's duplicate detection is string normalisation and will miss transpositions, genuine renames and merged facilities. Outlier detection is MAD across six periods, which is too short a window to distinguish seasonality from error and will flag legitimate outbreak surges as data defects. False positives here are expensive in a specific way: a district officer who is wrongly told their data is bad twice will stop reading the quality register, and the register is the most valuable thing the system produces.

**How I would address it.**
- Fuzzy matching on facility names within parent district, combined with geographic proximity where coordinates exist, with a human confirmation step. Never auto-merge org units — surface candidates and let the MoH HMIS officer decide.
- Extend the outlier baseline to 24 months to separate seasonal pattern from anomaly, and exclude known outbreak periods from the baseline.
- Move detection rules into dbt tests so they run as part of the transformation and produce a machine-readable failure log rather than a printed summary.
- Add a feedback loop: when the MoH marks a flag as a false positive, that decision is recorded and tunes the threshold. Without this the register decays into noise.

---

### 4. Scheduling, orchestration and recovery under real infrastructure

**Concern.** The prototype is a manual invocation on a laptop. Production runs quarterly on infrastructure with 4–6 hours of power per day in rural sites and intermittent connectivity. A run that begins and is interrupted at 70% must not leave a half-written bulletin or a partially loaded warehouse.

**How I would address it.**
- Idempotent, resumable stages with checkpointed state, so an interrupted run resumes rather than restarts.
- Retry with exponential backoff on every DHIS2 API call; the national instance is itself a shared resource that goes down.
- Transactional load: the new bulletin becomes visible only on successful completion of every stage. No partial publication.
- Scheduled execution on server infrastructure the MoH controls, not an FDE's machine — with a documented manual fallback the analyst can run.
- Alerting to a named MoH owner on failure, not to me. If I am the alert recipient in month six, the handover failed.

---

### 5. Access control, secrets and PII posture

**Concern.** Currently: no authentication, credentials would sit in config, output is a world-readable HTML file. This sprint is aggregate-only so patient data is not in scope — but facility-level performance data is politically sensitive, a public ranking of worst-performing facilities has consequences for the people named in it, and the architecture must be ready for Problem C, which is patient-level and protected.

**How I would address it.**
- DHIS2 credentials into a secrets manager, never in `config.yaml`, with a service account scoped to read-only on the specific datasets required.
- Role-based access on the output: national view, district view scoped to own district, facility view. A district officer should not be browsing another county's performance ranking by default.
- Audit logging on every access to generated outputs — who viewed which bulletin, when. This is the control that will matter most when patient-level data enters scope, and establishing the pattern now on non-sensitive data is far easier than retrofitting it under governance pressure later.
- Explicit data classification of every output, agreed with the MoH data governance lead, before the first publication rather than after the first incident.
- Suppression of small-cell counts in any facility-level breakdown that could become identifying at low volumes.

---

# Deliverable 4 — Handover & Deployment

---

## The three things I would document for the MoH IT team

Deliberately three, and deliberately not "documentation" in general. Comprehensive documentation is written once, read never, and stale within a quarter. These three are chosen because each answers a question that will actually be asked, by someone under time pressure, when I am not there.

### 1. The runbook — "it broke, what do I do"

Not architecture. Failure-mode driven, written for someone at 4pm on the day the bulletin is due.

- How to run it, on schedule and manually
- The five failures that will actually happen — DHIS2 unreachable, credentials expired, a data element UID changed, extract returned fewer rows than expected, disk full — each with the exact symptom, the diagnosis and the fix
- How to read the manifest to tell which stage failed
- How to roll back to the previous quarter's output
- **Who to call, in escalation order, with the last entry being Sand rather than the first**

### 2. The configuration guide — "the Ministry changed something, how do I follow"

This is the document that determines whether the system survives its first metadata change without me. `config.yaml` is designed so that the most likely changes are configuration, not code.

- How to add a new indicator to the bulletin
- What to do when a DHIS2 data element UID changes — the single most likely breakage
- How to adjust the suppression threshold, and the reasoning behind the current 60% so that whoever changes it understands what they are trading
- How to add a district or facility type
- How to change the performance score weights

### 3. The decision record — "why is it built like this"

Short, and the one most teams skip. Its purpose is to stop a future maintainer from removing a safeguard because they cannot see what it is for.

- Why suppression exists rather than caveats, and what happens if it is disabled
- Why the system reads from DHIS2 and never writes back
- Why Health Insight Engine was not deployed, and what has to be true before it can be
- What is explicitly out of scope and why — so scope creep is a conscious decision rather than a drift
- Known limitations, stated plainly: reporting-base contamination in trends, naive duplicate detection, institutional-only mortality

---

## Who needs training, and on what

Three audiences with genuinely different needs. Training all of them on the same material is the most common handover failure I have seen.

| Audience | Sessions | Content | What success looks like |
|---|---|---|---|
| **MoH IT team** (2–3 people) | 4 × 2 hrs, pairing at a keyboard from Week 3 — not a Week 6 event | Running the pipeline, reading the manifest, the runbook failure modes, editing `config.yaml`, where the code lives, how to escalate | **One of them runs the full quarterly cycle unaided while I watch and say nothing** |
| **Bulletin analyst / HMIS officer** | 3 × 90 min | Reading the quality register and acting on it, the review-and-sign-off workflow, what suppression means and when to override, how to explain a suppressed figure to a district that asks | They stop compiling manually and start reviewing. They can defend any figure in the document |
| **District health officers** (sample, then cascade) | 1 × 60 min + a one-page guide | How to read the bulletin, what the performance score means, what to do about their own facilities on the follow-up list | They can name an action they took because of it. **This is the audience most often skipped, and the reason automated reports get produced and never read** |

**Training principle:** the IT team is paired with from Week 3, not trained in Week 6. A handover event at the end of a sprint is a transfer of documents. Capability transfer has to be built into the delivery itself, and if the MoH team has not touched the system before the final week, the handover has already failed regardless of how good the training session is.

---

## Exit criteria — how I know I can transition out

I would agree these in writing with the Director in Week 2, not negotiate them in Week 6.

**Hard gates. All must be true:**

1. **One full quarterly cycle produced by MoH staff, start to finish, with zero FDE involvement.** Not observed, not assisted. I am not in the room. This is the only criterion that actually proves handover — every other metric can be satisfied by an engineer who has made himself indispensable.
2. **A named individual owns the system**, with a named backup, both of whom have run it. Owned by "the IT team" means owned by nobody.
3. **Two consecutive bulletins published on schedule**, the second without me.
4. **The three documents exist, and have been used** — the runbook has been opened during a real failure at least once. Untested documentation is an assumption.
5. **The data quality register has an owner and a working queue**, with evidence that at least some flagged issues have been resolved at district level. Otherwise the register is a report about problems rather than a mechanism for fixing them.
6. **Escalation path agreed and tested**, with Sand as the last resort rather than the first call.

**Soft signals I would look for:**
- The MoH team has changed something themselves — added an indicator, adjusted a threshold — without asking me
- Someone other than me has explained the suppression logic to a third party, correctly
- A district has disputed a figure and the analyst resolved it using the provenance data without escalating

**What transitioning out is not.** It is not the end of the engagement — this is a permanently embedded role, and Problems B and C follow. It is the point at which the bulletin stops being a thing I do and becomes a thing the Ministry does, which is what frees me to start the next problem. The measure of the first sprint is not the bulletin. It is whether the Ministry can now run a system it could not run before, and whether that earns the access needed for the harder work that follows.
