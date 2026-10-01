"""render.py — self-contained HTML bulletin. No server, no CDN, printable."""

from __future__ import annotations
import pandas as pd
from jinja2 import Template


def recs(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notna(df), None).to_dict("records")


TPL = Template("""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{{ t.title }} — {{ t.country }} {{ t.period_label }}</title><style>
 :root{--ink:#12263a;--mut:#5b6b7c;--ln:#e3e8ee;--ok:#1a7f5a;--warn:#b25e09;
       --bad:#b3261e;--acc:#5b2d8e}
 *{box-sizing:border-box} body{font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",
   Roboto,sans-serif;color:var(--ink);margin:0;background:#f7f9fb}
 .wrap{max-width:1120px;margin:0 auto;padding:40px 30px 80px;background:#fff;
       box-shadow:0 0 0 1px var(--ln)}
 h1{font-size:27px;margin:0 0 4px;letter-spacing:-.4px}
 h2{font-size:19px;margin:46px 0 8px;padding-bottom:7px;border-bottom:2px solid var(--acc)}
 h3{font-size:13px;margin:26px 0 8px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px}
 .sub{color:var(--mut);font-size:14px;margin:0 0 6px}
 .alert{background:#fdeceb;border-left:4px solid var(--bad);padding:14px 17px;margin:22px 0;font-size:13.5px}
 .warn{background:#fff8e6;border-left:4px solid var(--warn);padding:13px 16px;margin:18px 0;font-size:13.5px}
 .note{background:#f2f5f8;border-left:4px solid var(--mut);padding:12px 16px;margin:14px 0;
       font-size:13px;color:#44576b}
 table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}
 th{text-align:left;background:#f2f5f8;padding:9px 10px;border-bottom:2px solid var(--ln);
    font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--mut)}
 td{padding:8px 10px;border-bottom:1px solid var(--ln)} tr:hover td{background:#fafcfe}
 .num{text-align:right;font-variant-numeric:tabular-nums}
 .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:13px;margin:16px 0}
 .card{border:1px solid var(--ln);border-radius:7px;padding:14px 16px}
 .card.hero{border-color:var(--bad);background:#fdf6f5}
 .card .lbl{font-size:11.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
 .card .val{font-size:28px;font-weight:600;margin:6px 0 2px;font-variant-numeric:tabular-nums}
 .card.hero .val{color:var(--bad)}
 .card .prov{font-size:11.5px;color:var(--mut);border-top:1px dashed var(--ln);padding-top:7px;margin-top:8px}
 .bad{color:var(--bad);font-weight:600} .ok{color:var(--ok);font-weight:600}
 .flip{background:#fdeceb;font-weight:600;color:var(--bad)}
 .bar{height:7px;background:#e3e8ee;border-radius:4px;overflow:hidden;min-width:60px}
 .bar>i{display:block;height:100%;background:var(--acc)}
 .foot{margin-top:52px;padding-top:18px;border-top:1px solid var(--ln);font-size:12px;color:var(--mut)}
 code{background:#f2f5f8;padding:1px 5px;border-radius:3px;font-size:12px}
</style></head><body><div class="wrap">

<h1>{{ t.title }}</h1>
<p class="sub"><b>{{ t.ministry }}, {{ t.country }}</b> &nbsp;·&nbsp; {{ t.period_label }}
 &nbsp;·&nbsp; Generated {{ generated }} &nbsp;·&nbsp; <b>Automated draft — not for publication without sign-off</b></p>

<div class="alert">
<b>Read this before any figure below.</b>
The source extract contains <b>{{ q.duplicates.duplicate_rows }} duplicate facility-month rows</b>
across {{ q.duplicates.affected_months|join(" and ") }}, with conflicting values.
Uncorrected they inflate national delivery volume by
<b>{{ q.duplicates.volume_inflation_pct }}%</b>
({{ "{:,}".format(q.duplicates.deliveries_raw) }} vs {{ "{:,}".format(q.duplicates.deliveries_clean) }}).
All figures here are deduplicated. The extract also covers
<b>{{ q.coverage.n_months }} months, not 12</b> — {{ q.coverage.months_missing|join(", ") }} are absent.
</div>

<h2>1. National Position</h2>
<div class="cards">
 <div class="card hero"><div class="lbl">Neonatal mortality rate</div>
  <div class="val">{{ n.nmr }}</div>
  <div class="prov">per 1,000 live births · <b>{{ n.multiple_of_target }}× the WHO SDG 3.2 target of {{ n.who_target }}</b></div></div>
 <div class="card"><div class="lbl">Facilities above target</div>
  <div class="val">{{ n.facilities_above_target }}<span style="font-size:15px;color:var(--mut)">/{{ n.facilities }}</span></div>
  <div class="prov">every facility in the extract</div></div>
 <div class="card"><div class="lbl">Neonatal deaths</div>
  <div class="val">{{ "{:,}".format(n.neonatal_deaths) }}</div>
  <div class="prov">{{ "{:,}".format(n.excess_deaths_vs_target) }} above the SDG target rate</div></div>
 <div class="card"><div class="lbl">Live births</div>
  <div class="val">{{ "{:,}".format(n.live_births) }}</div>
  <div class="prov">{{ "{:,}".format(n.deliveries) }} deliveries, {{ n.facilities }} facilities</div></div>
 <div class="card"><div class="lbl">Early neonatal (0–7d)</div>
  <div class="val">{{ n.early_nmr }}</div>
  <div class="prov">{{ n.early_share_pct }}% of all neonatal deaths — the first week dominates</div></div>
 <div class="card"><div class="lbl">Stillbirth rate</div>
  <div class="val">{{ n.stillbirth_rate }}</div><div class="prov">per 1,000 deliveries</div></div>
 <div class="card"><div class="lbl">Low birth weight</div>
  <div class="val">{{ n.lbw_rate_pct }}%</div><div class="prov">&lt;2,500g</div></div>
 <div class="card"><div class="lbl">Preterm</div>
  <div class="val">{{ n.preterm_rate_pct }}%</div><div class="prov">&lt;37 weeks gestation</div></div>
</div>

<h3>Cause of death composition</h3>
<table><thead><tr><th>Cause</th><th class="num">Deaths</th><th class="num">Share</th><th style="width:32%"></th></tr></thead><tbody>
{% for r in causes %}<tr><td>{{ r.cause }}</td><td class="num">{{ "{:,}".format(r.deaths) }}</td>
<td class="num">{{ r.share_pct }}%</td><td><div class="bar"><i style="width:{{ r.share_pct*2.2 }}%"></i></div></td></tr>{% endfor %}
</tbody></table>

<h2>2. Mortality by Tier and Province</h2>
<div class="note"><b>Tier is the strongest single predictor in this dataset</b> — and the
reason no league table below is presented on raw mortality alone. A health centre and a
referral hospital do not receive the same newborns.</div>
<table><thead><tr><th>Tier</th><th class="num">Facilities</th><th class="num">Deliveries</th>
<th class="num">Live births</th><th class="num">Deaths</th><th class="num">NMR</th></tr></thead><tbody>
{% for r in tiers %}<tr><td><b>{{ r.tier_level }}</b></td><td class="num">{{ r.facilities }}</td>
<td class="num">{{ "{:,}".format(r.deliveries|int) }}</td><td class="num">{{ "{:,}".format(r.live_births|int) }}</td>
<td class="num">{{ "{:,}".format(r.deaths|int) }}</td>
<td class="num {{ 'bad' if r.nmr>40 else '' }}">{{ r.nmr }}</td></tr>{% endfor %}
</tbody></table>

<h3>By province</h3>
<table><thead><tr><th>Province</th><th class="num">Facilities</th><th class="num">Live births</th>
<th class="num">Deaths</th><th class="num">NMR</th></tr></thead><tbody>
{% for r in provinces %}<tr><td>{{ r.province }}</td><td class="num">{{ r.facilities }}</td>
<td class="num">{{ "{:,}".format(r.live_births|int) }}</td><td class="num">{{ "{:,}".format(r.deaths|int) }}</td>
<td class="num">{{ r.nmr }}</td></tr>{% endfor %}
</tbody></table>

<h2>3. Top {{ t.top_n_facilities }} Facilities by Delivery Volume</h2>
<div class="warn"><b>This is the section the duplicate rows break.</b> Volume is a count, so
duplication inflates it directly and unevenly — which reorders the ranking. Rates are
unaffected because numerator and denominator inflate together. Figures below are deduplicated.</div>
<table><thead><tr><th>#</th><th>Facility</th><th>District</th><th>Tier</th>
<th class="num">Deliveries</th><th class="num">Live births</th><th class="num">Deaths</th>
<th class="num">NMR</th></tr></thead><tbody>
{% for r in top %}<tr><td>{{ loop.index }}</td><td>{{ r.facility_name }}</td><td>{{ r.district }}</td>
<td>{{ r.tier_level }}</td><td class="num"><b>{{ "{:,}".format(r.deliveries|int) }}</b></td>
<td class="num">{{ "{:,}".format(r.live_births|int) }}</td><td class="num">{{ r.neonatal_deaths|int }}</td>
<td class="num {{ 'bad' if r.nmr>40 else '' }}">{{ r.nmr }}</td></tr>{% endfor %}
</tbody></table>

<h2>4. Facility Performance — Risk-Adjusted Excess Mortality</h2>
<div class="note">Each facility is compared with <b>its own tier</b>, not the national average.
Expected deaths = the tier's pooled mortality rate applied to that facility's live births.
SMR above 1.0 means more deaths than tier-peers would predict. Facilities with fewer than
{{ min_lb }} live births are suppressed — at small denominators a league table is noise,
and publishing it is an accusation against a named facility.</div>
<table><thead><tr><th>Facility</th><th>District</th><th>Tier</th><th class="num">Live births</th>
<th class="num">Observed</th><th class="num">Expected</th><th class="num">Excess</th>
<th class="num">SMR</th></tr></thead><tbody>
{% for r in perf %}<tr><td>{{ r.facility_name }}</td><td>{{ r.district }}</td><td>{{ r.tier_level }}</td>
<td class="num">{{ "{:,}".format(r.live_births|int) }}</td><td class="num">{{ r.neonatal_deaths|int }}</td>
<td class="num">{{ r.expected_deaths|int }}</td>
<td class="num bad">+{{ r.excess_deaths|int }}</td><td class="num">{{ r.smr }}</td></tr>{% endfor %}
</tbody></table>

<h2>5. Driver Analysis — and Why the Obvious Reading Is Wrong</h2>
<div class="alert"><b>The most important finding in this bulletin is a negative one.</b>
Unadjusted, facility capability appears to explain most of the mortality variation —
CPAP availability alone correlates at {{ top_raw }}. That reading is <b>confounded by tier</b>.
Compare facilities only with their own peers and the associations collapse below
|r| = 0.2, and {{ n_flips }} change sign entirely. <b>This dataset does not support a causal
intervention list.</b> Acting on the unadjusted column would direct scarce capital at a
spurious cause.</div>
<table><thead><tr><th>Candidate driver</th><th class="num">Unadjusted ρ</th>
<th class="num">Tier-adjusted r</th><th class="num">Attenuation</th><th>Reading</th></tr></thead><tbody>
{% for r in drv %}<tr><td>{{ r.driver }}</td>
<td class="num">{{ "%+.3f"|format(r.unadjusted) }}</td>
<td class="num {{ 'flip' if r.sign_flip else '' }}">{{ r.tier_adjusted is none and "—" or "%+.3f"|format(r.tier_adjusted) }}</td>
<td class="num">{{ r.attenuation_pct is none and "—" or "%.0f"|format(r.attenuation_pct) ~ "%" }}</td>
<td style="font-size:12px;color:var(--mut)">{{ "sign flips — association reverses within tier" if r.sign_flip else ("survives adjustment, weakly" if r.tier_adjusted is not none and r.tier_adjusted|abs > 0.15 else "explained by tier") }}</td>
</tr>{% endfor %}
</tbody></table>

<h3>Case-mix check — do sicker babies explain it?</h3>
<div class="note">No. Low birth weight and preterm rates are effectively uncorrelated with
facility mortality here, which is why the excess-mortality model adjusts for tier only.
Checked on every run rather than assumed.</div>
<table><thead><tr><th>Case-mix factor</th><th class="num">Unadjusted ρ</th><th class="num">Tier-adjusted r</th></tr></thead><tbody>
{% for r in cmix %}<tr><td>{{ r.factor }}</td><td class="num">{{ "%+.3f"|format(r.unadjusted) }}</td>
<td class="num">{{ "%+.3f"|format(r.tier_adjusted) }}</td></tr>{% endfor %}
</tbody></table>

<h3>Capability gradient across tiers (descriptive, not causal)</h3>
<table><thead><tr><th>Tier</th><th class="num">Median NMR</th><th class="num">CPAP</th>
<th class="num">Neonatal nurses</th><th class="num">Night cover (0–2)</th>
<th class="num">Bag-mask competency</th><th class="num">Stockout days</th></tr></thead><tbody>
{% for r in grad %}<tr><td><b>{{ r.tier_level }}</b></td><td class="num">{{ r.nmr }}</td>
<td class="num">{{ r.cpap }}</td><td class="num">{{ r.neo_nurses }}</td>
<td class="num">{{ r.night_cover }}</td><td class="num">{{ r.bag_mask }}%</td>
<td class="num">{{ r.stockout_days }}</td></tr>{% endfor %}
</tbody></table>

<h2>6. Overnight Staffing — the Group a Default CSV Read Deletes</h2>
<div class="alert"><b>{{ q.sentinels.night_shift_none }} of {{ q.sentinels.total_facilities }} facilities
have no overnight staffing cover.</b> In the source file this is recorded as the literal
string <code>None</code> — a real category, not a missing value. Read with pandas' default
settings it is silently converted to <code>NaN</code>, dropping the majority of the estate,
and the worst-performing part of it, out of every grouped analysis. No error is raised.
The pipeline disables default NA inference for exactly this reason.</div>
<table><thead><tr><th>Night shift coverage</th><th class="num">Facilities</th>
<th class="num">Live births</th><th class="num">Deaths</th><th class="num">Pooled NMR</th>
<th class="num">Median NMR</th></tr></thead><tbody>
{% for r in night %}<tr><td><b>{{ r.night_shift_coverage }}</b></td><td class="num">{{ r.facilities }}</td>
<td class="num">{{ "{:,}".format(r.live_births|int) }}</td><td class="num">{{ "{:,}".format(r.deaths|int) }}</td>
<td class="num {{ 'bad' if r.pooled_nmr>50 else '' }}">{{ r.pooled_nmr }}</td>
<td class="num">{{ r.median_nmr }}</td></tr>{% endfor %}
</tbody></table>
<div class="note">Note the same caution as Section 5: night cover also tracks tier. The
gradient is real and worth investigating; it is not on its own evidence that adding night
staff would move mortality.</div>

<h2>7. Supervision Priority List</h2>
<div class="note">Facilities with the largest excess mortality against their own tier, and the
modifiable capability gaps recorded at each. <b>This is a supervision visit list, not a
procurement list.</b> The driver analysis does not support "fix these and mortality falls".
What it supports is: these facilities have more deaths than their peers predict, these
specific gaps are present, and someone should go and find out why.</div>
<table><thead><tr><th>Facility</th><th>District</th><th>Tier</th><th class="num">Live births</th>
<th class="num">Excess deaths</th><th>Recorded capability gaps</th></tr></thead><tbody>
{% for r in shortlist %}<tr><td>{{ r.facility_name }}</td><td>{{ r.district }}</td>
<td>{{ r.tier_level }}</td><td class="num">{{ "{:,}".format(r.live_births|int) }}</td>
<td class="num bad">+{{ r.excess_deaths|int }}</td>
<td style="font-size:12.5px">{{ r.modifiable_gaps }}</td></tr>{% endfor %}
</tbody></table>

<h2>8. Trend Across Quarters</h2>
<div class="warn">Quarter <b>totals are not comparable</b> — the extract is missing
{{ q.coverage.months_missing|join(" and ") }}, so quarters contain different numbers of
months. Rates are comparable; levels are not. Month counts are shown.</div>
<table><thead><tr><th>Quarter</th><th class="num">Months</th><th class="num">Deliveries</th>
<th class="num">Deliveries/month</th><th class="num">Live births</th><th class="num">Deaths</th>
<th class="num">NMR</th><th class="num">Δ NMR</th></tr></thead><tbody>
{% for r in trend %}<tr><td><b>{{ r.quarter }}</b></td><td class="num">{{ r.months }}</td>
<td class="num">{{ "{:,}".format(r.deliveries|int) }}</td>
<td class="num">{{ "{:,}".format(r.deliveries_per_month|int) }}</td>
<td class="num">{{ "{:,}".format(r.live_births|int) }}</td><td class="num">{{ r.deaths|int }}</td>
<td class="num">{{ r.nmr }}</td>
<td class="num {{ 'ok' if r.nmr_change and r.nmr_change<0 else ('bad' if r.nmr_change else '') }}">
{{ r.nmr_change is none and "—" or "%+.1f"|format(r.nmr_change) }}</td></tr>{% endfor %}
</tbody></table>

<h2>9. Data Quality Register</h2>
<table><thead><tr><th>Issue</th><th class="num">Count</th><th>Effect on this bulletin</th><th>Owner</th></tr></thead><tbody>
{% for r in defects %}<tr><td><b>{{ r.issue }}</b></td><td class="num">{{ r.count }}</td>
<td>{{ r.impact }}</td><td>{{ r.owner }}</td></tr>{% endfor %}
</tbody></table>

<div class="foot">
<b>Provenance.</b> Built from {{ "{:,}".format(q.duplicates.rows_clean) }} deduplicated
facility-month records across {{ n.facilities }} facilities and {{ q.coverage.n_months }}
months ({{ q.coverage.months_present[0] }} to {{ q.coverage.months_present[-1] }}).
{{ q.duplicates.duplicate_rows }} duplicate rows removed using the
<code>{{ dedupe_strategy }}</code> strategy — a placeholder pending an MoH ruling on which
submission is authoritative. Facility rates suppressed below {{ min_lb }} live births.
Self-reported HMIS completeness averages {{ q.hmis.mean }}% across the estate,
with {{ q.hmis.below_80 }} facilities below 80%.
<br><br>
<b>Not for publication without Ministry sign-off.</b> Figures are facility-based and cover
institutional deliveries only; they are not population-level estimates and are not
comparable to WHO country statistics. No causal claim is made anywhere in this document.
<br><br>SHOS Neonatal Bulletin Pipeline · generated {{ generated }}
</div></div></body></html>""")


def render(ctx: dict) -> str:
    return TPL.render(**ctx)
