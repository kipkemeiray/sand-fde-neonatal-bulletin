"""
run.py — single entrypoint.  `python src/run.py`

Order is deliberate: ingest -> quality -> metrics -> drivers -> render.
Quality runs before anything is computed, because if the extract is unusable I want
to know before I have built a bulletin on top of it.
"""

from __future__ import annotations
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest, quality, metrics, drivers, render  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    t0 = datetime.now()
    cfg = ingest.load_config()
    print("=" * 70)
    print(f"  {cfg['bulletin']['title']} — {cfg['bulletin']['country']} "
          f"{cfg['bulletin']['period_label']}")
    print("=" * 70)

    # ---- ingest ------------------------------------------------------------
    f = ingest.load_all(cfg)
    print(ingest.profile(f))
    panel = ingest.build_facility_panel(f, cfg)

    # ---- quality (first, by design) ----------------------------------------
    q = quality.run_all(f, panel, cfg)
    panel = quality.suppression(panel, cfg)

    print("\n" + "=" * 70 + "\nDATA QUALITY\n" + "=" * 70)
    d = q["duplicates"]
    print(f"  Duplicate facility-month rows      {d['duplicate_rows']:>6}   "
          f"({', '.join(d['affected_months'])}, all conflicting)")
    print(f"  Volume inflation if uncorrected    {d['volume_inflation_pct']:>5}%   "
          f"{d['deliveries_raw']:,} -> {d['deliveries_clean']:,} deliveries")
    print(f"  Months present                     {q['coverage']['n_months']:>6}   "
          f"missing: {', '.join(q['coverage']['months_missing'])}")
    print(f"  'None' night cover (real category) {q['sentinels']['night_shift_none']:>6}   "
          f"of {q['sentinels']['total_facilities']} facilities")
    print(f"  Staff never trained                {q['sentinels']['never_trained']:>6}")
    print(f"  Protocol never updated             {q['sentinels']['protocol_never_updated']:>6}")
    print(f"  No newborn protocol at all         {q['sentinels']['no_protocol']:>6}")
    print(f"  Logical violations                 {len(q['violations']):>6}")
    print(f"  Volume outliers (MAD z>5)          {len(q['outliers']):>6}")
    print(f"  Facilities suppressed from ranking {int(panel['suppressed'].sum()):>6}")

    defects = [
        dict(issue="Duplicate facility-month rows", count=d["duplicate_rows"],
             impact=f"Inflate volume {d['volume_inflation_pct']}% if uncorrected; reorder Top-10",
             owner="MoH HMIS officer — rule on authoritative submission"),
        dict(issue="Missing reporting months", count=len(q["coverage"]["months_missing"]),
             impact="Quarter totals not comparable as levels", owner="MoH HMIS officer"),
        dict(issue="Facilities with no night cover", count=q["sentinels"]["night_shift_none"],
             impact="Deleted entirely by a default CSV read", owner="MoH HR / data steward"),
        dict(issue="Staff never trained on newborn care", count=q["sentinels"]["never_trained"],
             impact="Capability gap; feeds supervision list", owner="MoH training unit"),
        dict(issue="Newborn protocol absent", count=q["sentinels"]["no_protocol"],
             impact="Governance gap", owner="MoH quality unit"),
        dict(issue="Logical violations in clinical data", count=len(q["violations"]),
             impact="Invalidate affected facility-months", owner="District data officer"),
        dict(issue="Volume outliers (MAD z>5)", count=len(q["outliers"]),
             impact="Distort volume ranking and trend", owner="District data officer"),
        dict(issue="Facilities below reporting threshold", count=int(panel["suppressed"].sum()),
             impact="Suppressed from ranking — small-denominator noise", owner="MoH HMIS officer"),
    ]

    # ---- metrics -----------------------------------------------------------
    nat = metrics.national_indicators(panel, cfg)
    causes = metrics.cause_of_death(panel)
    top = metrics.top_facilities_by_volume(panel, cfg)
    perf = metrics.facility_performance(panel, cfg)
    tiers = metrics.tier_summary(panel)
    provs = metrics.province_summary(panel)
    trend = metrics.quarterly_trend(f, cfg)

    print("\n" + "=" * 70 + "\nNATIONAL POSITION\n" + "=" * 70)
    print(f"  NMR {nat['nmr']} per 1,000 live births — {nat['multiple_of_target']}x "
          f"the WHO SDG target of {nat['who_target']}")
    print(f"  {nat['facilities_above_target']}/{nat['facilities']} facilities above target; "
          f"{nat['excess_deaths_vs_target']:,} deaths above target rate")
    print(f"  Early neonatal (0-7d) accounts for {nat['early_share_pct']}% of deaths")

    # ---- drivers -----------------------------------------------------------
    drv = drivers.driver_table(panel, cfg)
    cmix = drivers.case_mix_check(panel, cfg)
    grad = drivers.capability_gradient(panel)
    night = drivers.night_cover_analysis(panel)
    shortlist = drivers.intervention_shortlist(panel, cfg)

    n_flips = int(drv["sign_flip"].sum())
    top_raw = f"{drv.iloc[0]['unadjusted']:+.2f}"
    print("\n" + "=" * 70 + "\nDRIVER ANALYSIS\n" + "=" * 70)
    print(f"  Strongest unadjusted association   {drv.iloc[0]['driver']} "
          f"rho={drv.iloc[0]['unadjusted']:+.3f}")
    print(f"  Same driver, adjusted for tier     r={drv.iloc[0]['tier_adjusted']:+.3f}  "
          f"({drv.iloc[0]['attenuation_pct']:.0f}% attenuation)")
    print(f"  Drivers that change sign on adjustment: {n_flips}")
    print(f"  Max |r| surviving adjustment: {drv['tier_adjusted'].abs().max():.3f}")
    print("  => dataset does NOT support a causal intervention list")

    # ---- render ------------------------------------------------------------
    ctx = dict(
        t=cfg["bulletin"], generated=datetime.now().strftime("%d %b %Y, %H:%M"),
        n=nat, q=q, causes=render.recs(causes), top=render.recs(top),
        perf=render.recs(perf), tiers=render.recs(tiers), provinces=render.recs(provs),
        drv=render.recs(drv.head(16)), cmix=render.recs(cmix), grad=render.recs(grad),
        night=render.recs(night), shortlist=render.recs(shortlist),
        trend=render.recs(trend), defects=defects,
        min_lb=cfg["quality"]["min_live_births_to_rank"],
        dedupe_strategy=cfg["dedupe"]["strategy"], n_flips=n_flips, top_raw=top_raw,
    )
    out = ROOT / cfg["output"]["html_path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render.render(ctx))

    tdir = ROOT / cfg["output"]["csv_dir"]
    tdir.mkdir(parents=True, exist_ok=True)
    for name, df in [("top_facilities", top), ("facility_performance", perf),
                     ("driver_analysis", drv), ("case_mix_check", cmix),
                     ("capability_gradient", grad), ("night_cover", night),
                     ("supervision_shortlist", shortlist), ("tier_summary", tiers),
                     ("province_summary", provs), ("quarterly_trend", trend),
                     ("cause_of_death", causes),
                     ("data_quality_register", pd.DataFrame(defects))]:
        df.to_csv(tdir / f"{name}.csv", index=False)
    panel.to_csv(tdir / "facility_panel_full.csv", index=False)

    print("\n" + "=" * 70)
    print(f"  Bulletin  -> {out.relative_to(ROOT)}")
    print(f"  Tables    -> {tdir.relative_to(ROOT)}/ (13 CSVs)")
    print(f"  Runtime   -> {(datetime.now()-t0).total_seconds():.2f}s")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
