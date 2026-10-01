"""
quality.py — data quality assessment. Runs BEFORE any indicator is computed.

The stated problem is "automate the bulletin". The actual risk is that automation
publishes a wrong number faster than a human would have. In a Ministry, one figure
a district successfully disputes makes every subsequent correct number arguable.

So this module runs first and its findings are Section 1 of the bulletin, not an
appendix. Six defect classes, each with a named owner and a stated impact on the
figures published downstream.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def duplicate_report(f: dict, cfg: dict) -> dict:
    """Quantify the (facility, month) duplication and its effect on volume."""
    raw, clean, dups = f["clinical_raw"], f["clinical"], f["duplicates"]
    key = cfg["dedupe"]["key"]

    conflicting = 0
    for _, g in dups.groupby(key):
        if g.drop_duplicates().shape[0] > 1:
            conflicting += 1

    raw_deliv, clean_deliv = raw["total_deliveries"].sum(), clean["total_deliveries"].sum()
    return {
        "rows_raw": len(raw),
        "rows_clean": len(clean),
        "duplicate_rows": len(raw) - len(clean),
        "affected_pairs": conflicting,
        "affected_months": sorted(dups["reporting_month"].unique().tolist()),
        "affected_facilities": int(dups["facility_id"].nunique()),
        "volume_inflation_pct": round(100 * (raw_deliv / clean_deliv - 1), 1),
        "deliveries_raw": int(raw_deliv),
        "deliveries_clean": int(clean_deliv),
    }


def coverage_report(f: dict) -> dict:
    """Which months are actually present. The extract is not a complete year."""
    months = sorted(f["clinical"]["reporting_month"].unique())
    expected = [f"2024-{m:02d}" for m in range(1, 13)]
    return {"months_present": months, "n_months": len(months),
            "months_missing": [m for m in expected if m not in months]}


def sentinel_report(f: dict, cfg: dict) -> dict:
    """'Never' and 'None' are meaningful values, not missing data.

    THIS IS THE FINDING THAT MATTERS MOST. Read with pandas defaults, the 'None'
    category in night_shift_coverage becomes NaN — silently deleting the 63
    facilities with no night cover, which are also the worst performers. Any
    analysis built on a default read describes a better country than exists.
    """
    hw, gv = f["workers"], f["governance"]
    nc = hw["night_shift_coverage"].value_counts(dropna=False).to_dict()
    return {
        "night_shift_none": int((hw["night_shift_coverage"] == "None").sum()),
        "night_shift_distribution": {str(k): int(v) for k, v in nc.items()},
        "never_trained": int((hw["last_neonatal_training_date"] == "Never").sum()),
        "protocol_never_updated": int((gv["protocol_last_updated"] == "Never").sum()),
        "no_protocol": int((gv["newborn_protocol_exists"] == "No").sum()),
        "total_facilities": len(hw),
    }


def logical_violations(panel: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Internal-consistency checks. Each hit is a conversation with a data officer."""
    cl = f["clinical"]
    cl = cl.assign(deaths=cl["neonatal_deaths_0_7d"] + cl["neonatal_deaths_8_28d"],
                   cause_sum=cl[["death_birth_asphyxia", "death_prematurity", "death_sepsis",
                                 "death_congenital", "death_other"]].sum(axis=1))
    v = []

    def add(mask, rule, frame=cl):
        for _, r in frame[mask].head(50).iterrows():
            v.append(dict(facility_id=r["facility_id"],
                          period=r.get("reporting_month", "-"), rule=rule))

    add(cl["live_births"] > cl["total_deliveries"], "live births > deliveries")
    add(cl["deaths"] > cl["live_births"], "neonatal deaths > live births")
    add(cl["cause_sum"] != cl["deaths"], "cause-of-death sum != total deaths")
    add(cl["birth_weight_less_2500g"] > cl["live_births"], "LBW count > live births")
    add((cl["preterm_births_28_32w"] + cl["preterm_births_32_37w"]) > cl["total_deliveries"],
        "preterm count > deliveries")

    fa = f["facilities"]
    add(fa["incubators_functional"] > fa["incubators_total"],
        "functional incubators > total incubators", fa)
    return pd.DataFrame(v)


def outliers(f: dict, threshold: float) -> pd.DataFrame:
    """MAD-based outlier detection on monthly delivery volume, per facility.

    MAD not standard deviation: a single order-of-magnitude typo inflates the SD
    enough to conceal itself. MAD is robust to exactly the defect being hunted.
    """
    cl = f["clinical"]
    res = []
    for fid, g in cl.groupby("facility_id"):
        if len(g) < 4:
            continue
        med = g["total_deliveries"].median()
        mad = (g["total_deliveries"] - med).abs().median()
        if mad == 0:
            continue
        z = 0.6745 * (g["total_deliveries"] - med) / mad
        hit = g[z.abs() > threshold]
        if len(hit):
            res.append(hit.assign(median_deliveries=med, mod_z=z[z.abs() > threshold]))
    if not res:
        return pd.DataFrame(columns=["facility_id", "reporting_month",
                                     "total_deliveries", "median_deliveries", "mod_z"])
    return (pd.concat(res)[["facility_id", "reporting_month", "total_deliveries",
                            "median_deliveries", "mod_z"]]
            .sort_values("mod_z", key=abs, ascending=False))


def suppression(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Flag facilities whose rates should not be published or ranked.

    A facility with 40 live births and 3 deaths has an NMR of 75 per 1,000 — a
    figure driven entirely by small-denominator noise. Ranking it alongside a
    referral hospital with 5,000 births is statistically meaningless and, published,
    is an accusation against a named facility.
    """
    q = cfg["quality"]
    d = panel.copy()
    d["suppressed"] = ((d["live_births"] < q["min_live_births_to_rank"]) |
                       (d["months_reported"] < q["min_months_reported"]))
    d["suppression_reason"] = np.where(
        d["live_births"] < q["min_live_births_to_rank"],
        "denominator below " + str(q["min_live_births_to_rank"]) + " live births",
        np.where(d["months_reported"] < q["min_months_reported"],
                 "fewer than " + str(q["min_months_reported"]) + " months reported", ""))
    return d


def hmis_completeness(f: dict) -> dict:
    """Self-reported HMIS completeness from the governance extract."""
    g = f["governance"]["hmis_reporting_completeness"]
    return {"mean": round(float(g.mean()), 1), "min": float(g.min()), "max": float(g.max()),
            "below_80": int((g < 80).sum()), "n": len(g)}


def run_all(f: dict, panel: pd.DataFrame, cfg: dict) -> dict:
    return {
        "duplicates": duplicate_report(f, cfg),
        "coverage": coverage_report(f),
        "sentinels": sentinel_report(f, cfg),
        "violations": logical_violations(panel, f),
        "outliers": outliers(f, cfg["quality"]["outlier_mad_threshold"]),
        "hmis": hmis_completeness(f),
    }
