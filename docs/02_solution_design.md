# Deliverable 2 — Rapid Prototyping

Built against the provided dataset: **117 Rwandan facilities, 1,404 facility-month clinical records, four facility-characteristic tables.**

---

## Section 0: What the data turned out to be

The brief describes Problem A as *"Quarterly Health Bulletin automation from DHIS2 Excel exports."* The provided extract is narrower and more interesting than that: **facility-level neonatal outcomes joined to facility capability** — infrastructure, staffing, governance and operations, one row per facility, joined on `facility_id`.

That changes the deliverable in a way worth stating explicitly, because it is the kind of scope adjustment an FDE has to make in Week 2 rather than pretend away.

| The brief implies | The data supports |
|---|---|
| Descriptive bulletin from routine aggregate reporting | Descriptive bulletin **plus** facility-level performance comparison |
| "Top 10 facilities by patient volume" | Same, but volume is corrupted by duplication (below) |
| "Maternal health indicators" | Neonatal indicators — deliveries, live births, mortality by age band, cause of death, preterm, LBW |
| "Facility performance scores (reporting completeness, timeliness)" | No timeliness field exists. Self-reported `hmis_reporting_completeness` does. Performance is better expressed as **risk-adjusted excess mortality** |
| "Trend vs previous quarters" | Possible, but the extract is 10 months, not 12 |

I built the bulletin the data supports, and flagged each divergence rather than fabricating a field to match the spec.

**The single most consequential thing in this dataset:** the four characteristic tables are not decoration. They make it possible to move from *"which facilities have high mortality"* to *"what is different about them"* — which is the difference between situational awareness and a decision-support system. Section 5 below is where that goes, and where it gets uncomfortable.

---

## Section 1: Solution Design & Architecture

### 1.1 Data flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  SOURCES  — 5 CSV extracts, joined on facility_id                        │
│                                                                          │
│   clinical_neonatal.csv   1,404 rows   facility × month outcomes         │
│   facilities.csv            117 rows   tier, GPS, NICU, equipment        │
│   healthcare_workers.csv    117 rows   staffing, training, night cover   │
│   governance.csv            117 rows   protocols, audits, HMIS, competency│
│   operations.csv            117 rows   referrals, oxygen, drugs, stockouts│
└────────────┬─────────────────────────────────────────────────────────────┘
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. INGEST                     src/ingest.py                             │
│     • NA inference DISABLED — "None" is a real category (see 1.2)        │
│     • Deduplicate (facility, month) — 234 conflicting rows               │
│     • "63%" → 63.0 · ordinal encoding · "Never" preserved as a value     │
│     • Collapse to one row per facility, join all four characteristic sets │
└────────────┬─────────────────────────────────────────────────────────────┘
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  2. QUALITY                    src/quality.py     ◀── RUNS FIRST         │
│     Duplication impact · month coverage · sentinel audit · logical checks │
│     MAD outliers · small-denominator suppression                          │
│     → Section 9 of the bulletin, and the suppression decisions            │
└────────────┬─────────────────────────────────────────────────────────────┘
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3. METRICS                    src/metrics.py                            │
│     National position vs WHO SDG 3.2 · cause of death · Top-10 volume     │
│     Tier/province roll-up · risk-adjusted excess mortality · quarterly    │
└────────────┬─────────────────────────────────────────────────────────────┘
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  4. DRIVERS                    src/drivers.py                            │
│     Unadjusted vs tier-adjusted association · case-mix check ·            │
│     capability gradient · supervision priority list                       │
└────────────┬─────────────────────────────────────────────────────────────┘
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  5. SERVE                      src/render.py                             │
│     Self-contained HTML (no server, no CDN, printable) + 13 CSV tables    │
│     PRODUCTION: same marts → Superset via Analytics Template Toolkit;     │
│     GPS columns → Health Atlas                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Three defects that would each produce a confidently wrong bulletin

These are the findings from Week-1 discovery, done for real against the extract.

**① `None` is a real category that pandas deletes.**
`healthcare_workers.night_shift_coverage` takes the values `Full`, `Partial`, `None`. **63 of 117 facilities record `None`** — no overnight staffing at all. Read with pandas' default settings, `None` is coerced to `NaN`. No error, no warning. Every `groupby` silently drops the majority of the estate — and, since these are also the lowest-capability facilities, drops the worst performers. **A default read produces a bulletin describing a better country than the one that exists.** The pipeline sets `keep_default_na: false` and declares sentinels explicitly.

**② 234 duplicate facility-month rows with conflicting values.**
Every facility is duplicated in `2024-01` and `2024-03`, with different figures in each copy (e.g. BUG066 January appears as both 129 and 191 deliveries). Left in, national delivery volume inflates by **19.9%** — 220,969 against a true 184,340. Rates survive, because numerator and denominator inflate together. **Counts do not** — which means "Top 10 facilities by patient volume", a required bulletin section, is wrong and mis-ordered under a naive implementation.

**③ The extract is 10 months, not 12.** `2024-02` and `2024-12` are absent, so Q1 holds two months and Q4 holds two. Quarter totals are not comparable as levels; rates are. The bulletin prints the month count beside every quarter rather than quietly comparing a two-month quarter to a three-month one.

Also handled: seven percentage fields stored as strings (`"63%"`), `"Never"` as a legitimate value in two date fields (48 facilities have never trained staff, 14 have never updated their protocol), and twelve ordinal categoricals requiring an explicit, stated ordering.

### 1.3 Which Sand products I use, and why

| Product | Decision | Reasoning |
|---|---|---|
| **HealthOS Data Models** | ✅ Use — foundational | Standard transformations exist; writing country-specific indicator definitions creates a dialect no other FDE can maintain. Config maps local fields onto them |
| **Analytics Template Toolkit** (Superset) | ✅ Use — production surface | Pre-built reporting templates are exactly this use case. The prototype renders standalone HTML because a Week-3 demo must not depend on a running BI stack in a room with bad wifi; the marts are Superset-shaped from the start |
| **Health Atlas** | ✅ Use — in-sprint, Phase 2 | `facilities.csv` carries `gps_lat` / `gps_lon` for all 117 sites. Mapping excess mortality against tier and equipment is high value to provincial officers and directly serves the brief's second use case |
| **Health Outcome Tracker** | ✅ Use — natural fit | Patient-outcome analytics is precisely what this dataset is. The strongest candidate for productising the excess-mortality model beyond this sprint |
| **Health Insight Engine** | ⛔ **Deliberately not this sprint** | AI-powered alerting on an extract with 20% volume inflation, a category the default parser deletes, and two missing months will generate confident, wrong alerts. More seriously: the driver analysis in Section 5 shows this data does **not** support causal inference. An alerting engine that fires "low CPAP availability → mortality risk" would be automating a spurious correlation at national scale. **Phase 3, gated on the quality baseline this sprint produces.** |

**The judgement being demonstrated:** knowing which product not to deploy is a larger part of the FDE role than knowing which to deploy. Health Insight Engine would demo brilliantly in Week 4 and misdirect Ministry capital by Week 12.

### 1.4 Build vs. buy

| Component | Decision | Justification |
|---|---|---|
| Extraction | **Buy** — standard client pattern | Solved. In production this is a DHIS2 API client; Central FDEs will have one |
| Warehouse | **Buy** — PostgreSQL | Assumed HOS substrate; no case for anything else at 1,404 rows |
| Transformations | **Buy** — HealthOS Data Models + dbt | dbt gives lineage and tests free; the quality checks become dbt tests |
| Serving | **Buy** — Superset templates + Health Atlas | See above |
| **Parsing & dedup guards** | 🔨 **Build** | Country-specific defects. Candidate for the central pattern library — the `None`-as-category trap will recur in any extract with categorical staffing fields |
| **Risk-adjusted excess mortality** | 🔨 **Build** | The analytical core. If a standard version exists centrally I would adopt it; if not, this is the reusable asset from this engagement |
| **Confounding control in driver analysis** | 🔨 **Build** | See Section 5. Should become a standard guard in any HOS driver analysis, not a bespoke thing I did once in Rwanda |

---

## Section 2: Working Prototype

Source: **[github.com/kipkemeiray/sand-fde-neonatal-bulletin](https://github.com/kipkemeiray/sand-fde-neonatal-bulletin)** · run with `make all` · 0.5s · 16 regression tests pass with `make test`.

| Requirement | Status |
|---|---|
| Reads the provided data | ✅ all 5 extracts, 1,404 clinical records + 117×4 characteristics |
| Calculates ≥ 3 bulletin metrics | ✅ **9 sections, 30+ indicators** |
| Output in a usable format | ✅ self-contained HTML + 13 CSV tables |
| Working code | ✅ 5 modules, commented with decision rationale, 16 tests |

### 2.1 Verified output

```
DATA QUALITY
  Duplicate facility-month rows         234   (2024-01, 2024-03, all conflicting)
  Volume inflation if uncorrected     19.9%   220,969 -> 184,340 deliveries
  Months present                         10   missing: 2024-02, 2024-12
  'None' night cover (real category)     63   of 117 facilities
  Staff never trained                    48
  Protocol never updated                 14
  No newborn protocol at all             14
  Volume outliers (MAD z>5)               5

NATIONAL POSITION
  NMR 50.4 per 1,000 live births — 4.2x the WHO SDG target of 12
  117/117 facilities above target; 6,885 deaths above target rate
  Early neonatal (0-7d) accounts for 72.6% of deaths
```

**Mortality gradient by tier:** Referral 14.7 · Provincial 32.4 · District 68.2 · Health Center 62.7 per 1,000 live births. A district hospital in this dataset is roughly **4.6× as lethal for a newborn** as a referral hospital.

**72.6% of neonatal deaths occur in the first seven days.** That single figure has more programmatic consequence than anything else in the bulletin: it points at intrapartum and immediate newborn care, not at post-discharge follow-up.

### 2.2 The analytical centrepiece — and why the obvious finding is wrong

This is the part I would lead the Week-3 demo with, and it is a negative result.

Correlate facility characteristics against neonatal mortality and the story is compelling:

| Candidate driver | Unadjusted ρ |
|---|---|
| CPAP machines | **−0.665** |
| NICU available | −0.567 |
| Staff trained on protocol | −0.565 |
| Bag-mask ventilation competency | −0.554 |
| Oxygen cylinders available | −0.550 |

Read at face value: *buy CPAP machines, mortality falls by two thirds.* A Ministry would act on that. A donor would fund it.

**It is confounded by tier.** Referral hospitals have CPAP *and* low mortality; health centres have neither. The correlation is largely measuring what kind of facility it is.

Compare each facility only with its own tier — remove tier means from both sides — and:

- The CPAP association falls from **−0.665 to −0.020**, a **97% attenuation**
- **11 of 23 candidate drivers change sign** entirely
- **No driver survives at |r| > 0.20**

And the case-mix check rules out the innocent explanation: low-birth-weight rate correlates with facility NMR at ρ = −0.14 and preterm rate at −0.01. **Sicker babies do not explain the gradient.** It tracks facility capability class, and capability class is not a variable a supervision visit can change.

**So the bulletin publishes both columns side by side and states plainly that the data does not support a causal intervention list.** What it supports is a *supervision priority list*: facilities with more deaths than their tier-peers predict, annotated with the capability gaps recorded at each, for someone to go and investigate in person.

I would rather hand a Ministry an honest negative result with a defensible next step than a ranked intervention table that spends their budget on a spurious cause. The second option demos better. The first one survives contact with reality — and when mortality fails to move after a CPAP procurement, it is the credibility of every subsequent analysis that pays.

---

## Section 3: Implementation Notes

### 3.1 Shortcuts taken to move fast

| Shortcut | Why it was right | What it costs |
|---|---|---|
| CSV ingest, not the DHIS2 API | The API client is a known pattern; the interesting work is downstream | ~1 day to swap, isolated to `ingest.py` |
| pandas in memory, no database | 1,404 rows | Breaks around 10M records; migration trigger documented |
| Jinja2 HTML, not Superset | Demo must run offline on any laptop | Not the production surface; marts already shaped for it |
| `first` as the dedupe rule | Summing is definitively wrong; mean fabricates a value in no source record | A placeholder. The MoH must rule on which submission is authoritative — surfaced in the bulletin, config-switchable |
| Tier-only risk adjustment | Case-mix empirically adds nothing here (ρ ≈ 0) | Would need revisiting on another country's data — the check runs every time |
| Rank-based confounding control, not a regression model | Transparent, explainable to a non-statistician, no distributional assumptions | A mixed-effects model would give confidence intervals. Correct next step, not a Week-3 one |
| No geospatial output yet | Health Atlas is Phase 2 | GPS is loaded and unused |

### 3.2 What I would show in Week 3

**Open with the data quality register, not the metrics.** The Ministry has never seen these three defects, and the 19.9% volume inflation is the fastest way to establish that the pipeline is doing something a spreadsheet was not.

**Then the 72.6% early-neonatal figure** — the most programmatically actionable number in the extract.

**Then the confounding result**, deliberately framed as *"here is the analysis you would have got from anyone else, and here is why we are not giving it to you."*

**What is broken, and I would say so unprompted:**
- **Not reconciled against a published bulletin.** Until my figures match the Ministry's, or the gap is explained, nothing here is trustworthy. This is the Week 4 job and I would not let it be skipped
- The dedupe rule is a placeholder awaiting an MoH ruling
- No timeliness data exists, so the required "reporting timeliness" section cannot be built from this extract — I would need either a new field or a scope change
- `hmis_reporting_completeness` is self-reported by facilities, which makes it the least trustworthy field in the dataset and it is used only descriptively
- NMR of 50.4 is far above Rwanda's published national figure; these are facility-based institutional data, not population estimates, and must never be quoted as a country statistic
- Two months absent with no explanation — I do not know whether that is an extract artefact or a genuine reporting gap, and the answer changes how the trend section should be read

### 3.3 What I learned from building this

1. **The dangerous defects were all silent.** None of the three raised an error. A pipeline that ran cleanly, exited zero and produced a professional-looking document would have deleted 54% of facilities, inflated volume by a fifth, and compared a two-month quarter against a three-month one. **Silent-wrong is the failure mode to engineer against**, which is why the quality module runs before anything is computed and why the first three regression tests exist.

2. **The most valuable output was the analysis I decided not to publish.** The naive driver table took twenty minutes and looked like the answer. Establishing that it was confounded took longer and produced a negative result. In a Ministry engagement the second is worth far more — but only if you have the standing to deliver bad news in Week 3, which is an argument for spending Week 1 on relationships rather than code.

3. **Structure of the data told me what the client actually wanted.** Nobody joins four capability tables to an outcome table for a descriptive bulletin. The extract was assembled by someone who wanted to know *why* mortality varies. Reading that intent from the schema changed the deliverable more than anything in the brief did.

4. **Config-driven parsing earned itself immediately.** `keep_default_na: false` is one line, and it is the difference between a correct bulletin and a confidently wrong one. It is in config rather than code specifically so the next FDE, in the next country, sees the decision instead of inheriting it invisibly.
