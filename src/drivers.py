"""
drivers.py — which modifiable facility factors are associated with mortality.

THIS MODULE EXISTS TO STOP THE OBVIOUS ANALYSIS FROM BEING PUBLISHED
--------------------------------------------------------------------
Run a naive correlation of facility characteristics against neonatal mortality on
this dataset and you get a very compelling story:

    cpap_machines                     rho = -0.67
    nicu_available                    rho = -0.57
    staff_trained_on_protocol_pct     rho = -0.57
    bag_mask_ventilation_competency   rho = -0.55

Read at face value: buy CPAP machines and mortality falls by two thirds. A Ministry
would act on that. A donor would fund it.

It is confounded. Facility tier drives both sides — referral hospitals have CPAP
AND lower mortality, health centres have neither. Median NMR by tier runs 14.7
(Referral) to 68.2 (District). The correlation is mostly measuring tier.

Stratify by tier — compare each facility only with its own peers — and the signal
collapses to |r| < 0.2, with several "drivers" changing sign.

So this module computes BOTH and shows them side by side. The bulletin publishes
the adjusted column as the finding and the unadjusted column as a warning about
what the naive analysis would have said. Publishing the unadjusted version alone
would be the single most damaging thing this pipeline could do: it would send
scarce Ministry capital at a spurious cause, and when mortality did not move, the
credibility of every subsequent analysis would go with it.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def _spearman(x: pd.Series, y: pd.Series) -> float:
    m = x.notna() & y.notna()
    if m.sum() < 30 or x[m].nunique() < 3:
        return np.nan
    return float(x[m].rank().corr(y[m].rank()))


def _within_stratum_corr(d: pd.DataFrame, col: str, outcome: str, strat: str) -> float:
    """Rank-correlation after removing stratum means from both sides.

    Equivalent to a fixed-effects correlation: it asks whether, among facilities of
    the SAME tier, higher values of `col` go with lower mortality. That is the only
    version of the question a Ministry can act on, because tier is not a lever.
    """
    x, y = d[col].astype(float), d[outcome].astype(float)
    m = x.notna() & y.notna()
    if m.sum() < 30 or x[m].nunique() < 3:
        return np.nan
    df = pd.DataFrame({"x": x[m].rank(pct=True), "y": y[m].rank(pct=True), "s": d.loc[m, strat]})
    df["xd"] = df["x"] - df.groupby("s")["x"].transform("mean")
    df["yd"] = df["y"] - df.groupby("s")["y"].transform("mean")
    if df["xd"].std() == 0 or df["yd"].std() == 0:
        return np.nan
    return float(np.corrcoef(df["xd"], df["yd"])[0, 1])


def driver_table(panel: pd.DataFrame, cfg: dict, outcome: str = "nmr") -> pd.DataFrame:
    """Unadjusted vs tier-adjusted association for every candidate driver."""
    dcfg = cfg["drivers"]
    strat = dcfg["stratify_by"]
    d = panel[~panel["suppressed"]].copy()

    rows = []
    for c in dcfg["candidates"]:
        if c not in d.columns:
            continue
        raw = _spearman(d[c].astype(float), d[outcome])
        adj = _within_stratum_corr(d, c, outcome, strat)
        if np.isnan(raw):
            continue
        rows.append(dict(
            driver=c, unadjusted=round(raw, 3),
            tier_adjusted=round(adj, 3) if not np.isnan(adj) else np.nan,
            attenuation_pct=round(100 * (1 - abs(adj) / abs(raw)), 0)
                if raw and not np.isnan(adj) and raw != 0 else np.nan,
            sign_flip=bool(not np.isnan(adj) and raw * adj < 0),
            n=int(d[c].notna().sum())))
    t = pd.DataFrame(rows)
    return t.reindex(t["unadjusted"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def case_mix_check(panel: pd.DataFrame, cfg: dict, outcome: str = "nmr") -> pd.DataFrame:
    """Do sicker babies explain the variation? Checked, not assumed.

    If case-mix correlated strongly with mortality, the excess-mortality model in
    metrics.py would need to adjust for it. On this extract it does not — which is
    itself a reportable finding, because it means the mortality gradient is not
    explained by which facilities receive the most fragile newborns.
    """
    d = panel[~panel["suppressed"]]
    rows = [dict(factor=c, unadjusted=round(_spearman(d[c], d[outcome]), 3),
                 tier_adjusted=round(_within_stratum_corr(d, c, outcome,
                                     cfg["drivers"]["stratify_by"]), 3))
            for c in cfg["drivers"]["case_mix"] if c in d.columns]
    return pd.DataFrame(rows)


def capability_gradient(panel: pd.DataFrame) -> pd.DataFrame:
    """The finding that survives adjustment: capability tracks tier, and so does
    mortality. Shown as a descriptive gradient rather than a causal claim."""
    d = panel.copy()
    g = d.groupby("tier_level").agg(
        facilities=("facility_id", "count"),
        nmr=("nmr", "median"),
        cpap=("cpap_machines", "median"),
        neo_nurses=("neonatal_trained_nurses", "median"),
        night_cover=("night_shift_coverage_ord", "mean"),
        bag_mask=("bag_mask_ventilation_competency", "median"),
        stockout_days=("essential_drugs_stockouts_days", "median")).reset_index()
    order = ["Referral", "Provincial", "District", "Health Center"]
    g["_o"] = g["tier_level"].apply(lambda t: order.index(t) if t in order else 99)
    return g.sort_values("_o").drop(columns="_o").round(2).reset_index(drop=True)


def night_cover_analysis(panel: pd.DataFrame) -> pd.DataFrame:
    """Isolated because it is the group that pandas' default CSV parsing deletes.

    'None' is a real category — 63 of 117 facilities have no overnight cover. Read
    with default na_values it becomes NaN and drops out of every groupby, taking
    the worst-performing majority of the estate with it.
    """
    g = panel.groupby("night_shift_coverage").agg(
        facilities=("facility_id", "count"), live_births=("live_births", "sum"),
        deaths=("neonatal_deaths", "sum"), median_nmr=("nmr", "median")).reset_index()
    g["pooled_nmr"] = (1000 * g["deaths"] / g["live_births"]).round(1)
    order = {"None": 0, "Partial": 1, "Full": 2}
    return (g.assign(_o=g["night_shift_coverage"].map(order)).sort_values("_o")
            .drop(columns="_o").round(1).reset_index(drop=True))


def intervention_shortlist(panel: pd.DataFrame, cfg: dict, n: int = 10) -> pd.DataFrame:
    """Facilities with the largest excess mortality, and the modifiable gaps they have.

    DELIBERATELY NOT PRESENTED AS "FIX THESE AND MORTALITY FALLS". The driver
    analysis does not support a causal claim. What this table supports is a
    prioritised supervision visit list: these facilities have more deaths than
    their tier predicts, and these specific capability gaps are present. The
    diagnosis happens in the facility, not in the spreadsheet.
    """
    from metrics import expected_deaths_model
    d = expected_deaths_model(panel, cfg)
    d = d[~d["suppressed"]].sort_values("excess_deaths", ascending=False).head(n)

    def gaps(r) -> str:
        out = []
        if r.get("night_shift_coverage") == "None":         out.append("no night cover")
        if r.get("never_trained") == 1:                     out.append("staff never trained")
        if r.get("newborn_protocol_exists") == "No":        out.append("no newborn protocol")
        if r.get("protocol_never_updated") == 1:            out.append("protocol never updated")
        if pd.notna(r.get("bag_mask_ventilation_competency")) and r["bag_mask_ventilation_competency"] < 30:
            out.append(f"bag-mask competency {r['bag_mask_ventilation_competency']:.0f}%")
        if r.get("cpap_machines", 0) == 0:                  out.append("no CPAP")
        if r.get("incubator_functional_ratio") == 0:        out.append("no working incubator")
        if r.get("essential_drugs_stockouts_days", 0) > 20: out.append(
            f"{int(r['essential_drugs_stockouts_days'])} stockout days")
        if r.get("quality_improvement_active") == "No":     out.append("no QI programme")
        return "; ".join(out[:4]) or "no flagged capability gaps"

    d["modifiable_gaps"] = d.apply(gaps, axis=1)
    cols = ["facility_name", "district", "tier_level", "live_births",
            "neonatal_deaths", "expected_deaths", "excess_deaths", "modifiable_gaps"]
    return d[cols].round({"expected_deaths": 0, "excess_deaths": 0}).reset_index(drop=True)
