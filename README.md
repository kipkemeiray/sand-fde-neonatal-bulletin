# Neonatal Health Bulletin — SHOS Prototype

**Sand Technologies · Forward Deployed Engineer · Recruitment Assignment**
Raymond Kipkemei · kipkemei.ray@gmail.com

Automated quarterly neonatal bulletin for the Ministry of Health, built on the provided
Rwanda extract: **117 facilities, 1,404 facility-month clinical records, four
facility-characteristic tables.**

```bash
pip install -r requirements.txt
make all
open output/neonatal_bulletin.html
```

Runs in 0.5s. No database, no server, no network access. `make test` → 16 tests.

---

## Headline findings

| | |
|---|---|
| **NMR 50.4** per 1,000 live births | **4.2× the WHO SDG 3.2 target** of 12 |
| **117/117** facilities above target | 6,885 deaths above the target rate |
| **72.6%** of deaths in the first 7 days | Points at intrapartum and immediate newborn care |
| Referral 14.7 → District 68.2 | A district hospital is ~4.6× as lethal for a newborn |
| **Driver analysis: negative result** | The obvious intervention list is confounded — see below |

---

## Three defects that would each produce a confidently wrong bulletin

All three are silent. None raises an error.

**① `None` is a real category that pandas deletes.**
`night_shift_coverage` takes `Full` / `Partial` / `None`. **63 of 117 facilities have no
overnight cover.** Read with pandas defaults, `None` becomes `NaN` and the majority of the
estate — its worst-performing majority — vanishes from every `groupby`. The pipeline sets
`keep_default_na: false`.

**② 234 duplicate facility-month rows, all conflicting.**
Every facility duplicated in `2024-01` and `2024-03` with different values. Uncorrected,
national delivery volume inflates **19.9%** (220,969 vs 184,340). Rates survive; counts do
not — so "Top 10 facilities by volume", a required section, is wrong and mis-ordered.

**③ The extract is 10 months, not 12.** `2024-02` and `2024-12` absent. Quarter totals are
not comparable as levels. The bulletin prints month counts beside every quarter.

Also handled: 7 percentage fields stored as strings, `"Never"` as a legitimate value in two
date fields (48 never-trained, 14 never-updated protocols), 12 ordinal categoricals.

---

## The analytical centrepiece — a negative result

Naive correlation of facility capability against mortality looks decisive:

```
cpap_machines                    rho = -0.665
nicu_available                   rho = -0.567
staff_trained_on_protocol_pct    rho = -0.565
```

*Buy CPAP machines, mortality falls by two thirds.* A Ministry would act on that.

**It is confounded by facility tier.** Compare facilities only with their own tier and:

- CPAP falls from **−0.665 to −0.020** — **97% attenuation**
- **11 of 23 drivers change sign**
- **No driver survives at |r| > 0.20**
- Case-mix does not rescue it: LBW rate ρ = −0.14, preterm ρ = −0.01

So the bulletin publishes both columns and states that **this data does not support a
causal intervention list.** What it supports is a *supervision priority list* — facilities
with more deaths than their tier-peers predict, annotated with recorded capability gaps,
for someone to investigate in person.

An honest negative result with a defensible next step beats a ranked intervention table
that spends a Ministry's budget on a spurious cause.

---

## Layout

```
├── config.yaml              ← all environment-specific assumptions
├── Makefile
├── data/raw/                ← the five provided extracts
├── src/
│   ├── ingest.py            parsing guards, dedupe, ordinal encoding, facility panel
│   ├── quality.py           defect detection — runs BEFORE metrics, by design
│   ├── metrics.py           national position, volume, risk-adjusted excess mortality
│   ├── drivers.py           confounding control — the analytical core
│   ├── render.py            self-contained HTML
│   └── run.py               entrypoint
├── tests/test_pipeline.py   16 regression tests
├── docs/                    Deliverables 1–4
└── output/                  bulletin + 13 CSV tables
```

| Target | Does |
|---|---|
| `make all` | Build the bulletin |
| `make profile` | Inspect `data/raw` before trusting it |
| `make test` | Regression suite |
| `make clean` | Remove artefacts |

---

## Design decisions

**Quality runs before metrics.** If the extract is unusable, know it before building a
bulletin on top of it.

**Risk adjustment is tier-relative.** Expected deaths = the tier's own pooled rate applied
to that facility's live births. Raw NMR would rank referral hospitals best and health
centres worst — a statement about case-mix, not care quality. Publishing that raw league
table would name and shame facilities for the patients they receive.

**Case-mix adjustment is checked, not assumed.** LBW and preterm rates are effectively
uncorrelated with facility NMR here, so tier-only adjustment is sufficient. Re-checked on
every run; a regression test fails if that stops being true.

**Small denominators are suppressed.** At 40 live births, one death moves NMR by 25 per
1,000. Ranking that against a 5,000-birth referral hospital is noise — and publishing it
is an accusation against a named facility.

**No causal claim appears anywhere in the output.**

---

## Known limitations

- **Not reconciled against a published MoH bulletin.** Until figures match or the gap is
  explained, nothing here is trustworthy. This is the Week 4 job
- Dedupe rule (`first`) is a placeholder pending an MoH ruling on the authoritative submission
- No timeliness field exists — the brief's "reporting timeliness" section cannot be built
  from this extract without a new field or a scope change
- `hmis_reporting_completeness` is self-reported and used descriptively only
- NMR 50.4 is facility-based institutional data, **not** a population estimate, and is not
  comparable to Rwanda's published national statistics
- Two months absent with no stated explanation
- Rank-based confounding control, not a mixed-effects model — transparent but no confidence intervals

---

Python 3.10+ · pandas, PyYAML, Jinja2 · no network access required.
