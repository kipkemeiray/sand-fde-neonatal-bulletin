"""
metrics.py — the bulletin sections, computed on the deduplicated facility panel.

Sections:
  1. National neonatal indicators, benchmarked against the WHO SDG 3.2 target
  2. Top-N facilities by delivery volume  (the section the duplicates break)
  3. Facility performance: risk-adjusted excess mortality
  4. Trend across the quarters present in the extract
  5. Cause-of-death composition
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def national_indicators(panel: pd.DataFrame, cfg: dict) -> dict:
    p, target = panel, cfg["bulletin"]["who_sdg_nmr_target"]
    lb, dl = p["live_births"].sum(), p["deliveries"].sum()
    dth = p["neonatal_deaths"].sum()
    nmr = 1000 * dth / lb

    return {
        "facilities": len(p),
        "deliveries": int(dl),
        "live_births": int(lb),
        "neonatal_deaths": int(dth),
        "stillbirths": int(p["stillbirths"].sum()),
        "nmr": round(nmr, 1),
        "early_nmr": round(1000 * p["deaths_0_7d"].sum() / lb, 1),
        "late_nmr": round(1000 * p["deaths_8_28d"].sum() / lb, 1),
        "early_share_pct": round(100 * p["deaths_0_7d"].sum() / dth, 1),
        "stillbirth_rate": round(1000 * p["stillbirths"].sum() / dl, 1),
        "lbw_rate_pct": round(100 * p["low_birth_weight"].sum() / lb, 1),
        "preterm_rate_pct": round(100 * (p["preterm_28_32"].sum() + p["preterm_32_37"].sum()) / lb, 1),
        "who_target": target,
        "multiple_of_target": round(nmr / target, 1),
        "facilities_above_target": int((p["nmr"] > target).sum()),
        "excess_deaths_vs_target": int(dth - (target * lb / 1000)),
    }


def cause_of_death(panel: pd.DataFrame) -> pd.DataFrame:
    causes = {"Prematurity": "d_prematurity", "Birth asphyxia": "d_asphyxia",
              "Sepsis": "d_sepsis", "Congenital": "d_congenital", "Other": "d_other"}
    tot = panel["neonatal_deaths"].sum()
    rows = [dict(cause=k, deaths=int(panel[v].sum()),
                 share_pct=round(100 * panel[v].sum() / tot, 1)) for k, v in causes.items()]
    return pd.DataFrame(rows).sort_values("deaths", ascending=False).reset_index(drop=True)


def top_facilities_by_volume(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Required bulletin section — and the one the duplicate rows silently break.

    Volume is a count, so duplication inflates it directly (~20% nationally, and
    unevenly across facilities, which reorders the ranking). Rates survive
    duplication because numerator and denominator inflate together; counts do not.
    """
    n = cfg["bulletin"]["top_n_facilities"]
    cols = ["facility_name", "district", "province", "tier_level",
            "deliveries", "live_births", "neonatal_deaths", "nmr"]
    return (panel.sort_values("deliveries", ascending=False).head(n)[cols]
            .round({"nmr": 1}).reset_index(drop=True))


def expected_deaths_model(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Risk-adjusted expected deaths, stratified by facility tier.

    WHY ADJUST AT ALL: raw NMR ranks referral hospitals as the best performers and
    health centres as the worst. That is largely a statement about which facilities
    receive complicated deliveries, not about quality of care. Publishing a raw
    league table would name and shame facilities for their case-mix.

    THE MODEL, STATED PLAINLY: expected deaths = the tier's own pooled mortality
    rate applied to the facility's live births. So each facility is compared with
    its peers, not with the national average.

    WHAT THIS DELIBERATELY DOES NOT DO: it does not adjust for clinical case-mix
    beyond tier. In this extract, low-birth-weight and preterm rates correlate with
    NMR at rho = -0.14 and -0.01 — effectively zero — so a case-mix adjustment
    would add complexity and change almost nothing. That is an empirical finding
    from this dataset, not a general rule, and it is re-checked on every run.
    """
    strat = cfg["drivers"]["stratify_by"]
    d = panel.copy()
    tier_rate = d.groupby(strat).apply(
        lambda g: g["neonatal_deaths"].sum() / g["live_births"].sum(), include_groups=False)
    d["tier_nmr"] = d[strat].map(tier_rate) * 1000
    d["expected_deaths"] = d[strat].map(tier_rate) * d["live_births"]
    d["excess_deaths"] = d["neonatal_deaths"] - d["expected_deaths"]
    d["smr"] = d["neonatal_deaths"] / d["expected_deaths"]      # standardised mortality ratio
    return d


def facility_performance(panel: pd.DataFrame, cfg: dict, worst_n: int = 12) -> pd.DataFrame:
    d = expected_deaths_model(panel, cfg)
    d = d[~d["suppressed"]]
    cols = ["facility_name", "district", "tier_level", "live_births", "neonatal_deaths",
            "expected_deaths", "excess_deaths", "smr", "nmr", "tier_nmr"]
    return (d.sort_values("excess_deaths", ascending=False).head(worst_n)[cols]
            .round({"expected_deaths": 0, "excess_deaths": 0, "smr": 2,
                    "nmr": 1, "tier_nmr": 1}).reset_index(drop=True))


def tier_summary(panel: pd.DataFrame) -> pd.DataFrame:
    g = panel.groupby("tier_level").agg(
        facilities=("facility_id", "count"), deliveries=("deliveries", "sum"),
        live_births=("live_births", "sum"), deaths=("neonatal_deaths", "sum")).reset_index()
    g["nmr"] = (1000 * g["deaths"] / g["live_births"]).round(1)
    order = ["Referral", "Provincial", "District", "Health Center"]
    g["_o"] = g["tier_level"].apply(lambda t: order.index(t) if t in order else 99)
    return g.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def province_summary(panel: pd.DataFrame) -> pd.DataFrame:
    g = panel.groupby("province").agg(
        facilities=("facility_id", "count"), deliveries=("deliveries", "sum"),
        live_births=("live_births", "sum"), deaths=("neonatal_deaths", "sum")).reset_index()
    g["nmr"] = (1000 * g["deaths"] / g["live_births"]).round(1)
    return g.sort_values("nmr", ascending=False).reset_index(drop=True)


def quarterly_trend(f: dict, cfg: dict) -> pd.DataFrame:
    """Trend across the quarters actually present in the extract.

    CAVEAT SURFACED, NOT BURIED: the extract covers 10 months, and 2024-02 and
    2024-12 are absent. Q1 therefore contains two months, not three, and Q4
    contains two. Quarter totals are NOT comparable as levels — rates are. Both
    are shown, with the month count against each quarter.
    """
    cl = f["clinical"].copy()
    cl["deaths"] = cl["neonatal_deaths_0_7d"] + cl["neonatal_deaths_8_28d"]
    cl["quarter"] = "Q" + ((cl["reporting_month"].str[5:7].astype(int) - 1) // 3 + 1).astype(str)

    g = cl.groupby("quarter").agg(
        months=("reporting_month", "nunique"), deliveries=("total_deliveries", "sum"),
        live_births=("live_births", "sum"), deaths=("deaths", "sum"),
        stillbirths=("stillbirths", "sum")).reset_index()
    g["nmr"] = (1000 * g["deaths"] / g["live_births"]).round(1)
    g["deliveries_per_month"] = (g["deliveries"] / g["months"]).round(0)
    g["nmr_change"] = g["nmr"].diff().round(1)
    return g
