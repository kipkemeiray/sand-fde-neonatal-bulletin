"""
ingest.py — load the five source extracts, normalise types, deduplicate.

Everything dangerous about this dataset is handled at this boundary, on purpose.
Downstream modules should never have to defend against source quirks.

THE THREE THINGS THIS LAYER EXISTS TO PREVENT
---------------------------------------------
1. "None" being read as missing data. In healthcare_workers.night_shift_coverage,
   "None" means the facility has NO night cover — 63 of 117 facilities. pandas'
   default na_values silently converts that to NaN, which deletes the worst-
   performing group from every downstream analysis. Nothing errors. The bulletin
   just quietly describes a better country than the one that exists.

2. Duplicate (facility, month) rows. 234 of them, in 2024-01 and 2024-03, with
   conflicting values. Summing inflates national delivery volume by 19.9%.

3. Percentages stored as strings ("63%") and dates carrying "Never" as a value.
"""

from __future__ import annotations
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | Path | None = None) -> dict:
    with open(path or ROOT / "config.yaml") as fh:
        return yaml.safe_load(fh)


def _read_csv(path: Path, cfg: dict) -> pd.DataFrame:
    """Read one CSV with NA inference disabled — see module docstring, point 1."""
    p = cfg["parsing"]
    df = pd.read_csv(ROOT / path,
                     keep_default_na=p["keep_default_na"],
                     na_values=p["na_values"])
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:                      # strip CRLF residue from the last column
        if pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].str.strip()
    return df


def parse_percent(s: pd.Series) -> pd.Series:
    """'63%' -> 63.0. Returns float, NaN where unparseable."""
    return pd.to_numeric(s.astype(str).str.rstrip("%").str.strip(), errors="coerce")


def deduplicate(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resolve duplicate (facility, month) rows. Returns (clean, the_duplicates).

    DECISION: 'first' rather than sum or mean. Summing is definitively wrong — it
    invents deliveries that did not happen. Mean is defensible but fabricates a
    value that appears in no source record, which is hard to defend to a district
    that queries it. 'first' is a reversible, explainable placeholder, and the
    duplicates are surfaced in the bulletin as an issue the MoH must rule on.
    Strategy is config, not code, so that ruling costs one line.
    """
    key, strat = cfg["dedupe"]["key"], cfg["dedupe"]["strategy"]
    dup_mask = df.duplicated(key, keep=False)
    dups = df[dup_mask].sort_values(key)
    if strat == "mean":
        clean = df.groupby(key, as_index=False).mean(numeric_only=True)
    else:
        clean = df.drop_duplicates(key, keep=strat)
    return clean.reset_index(drop=True), dups


def load_all(cfg: dict) -> dict:
    s = cfg["sources"]
    clinical_raw = _read_csv(s["clinical"]["path"], cfg)
    clinical, duplicates = deduplicate(clinical_raw, cfg)

    fa = _read_csv(s["facilities"]["path"], cfg)
    hw = _read_csv(s["workers"]["path"], cfg)
    gv = _read_csv(s["governance"]["path"], cfg)
    op = _read_csv(s["operations"]["path"], cfg)

    # percentages -> numeric
    for df in (gv, op, fa, hw):
        for c in cfg["columns"]["percent_fields"]:
            if c in df.columns:
                df[c] = parse_percent(df[c])

    # ordinal encodings, kept alongside the original categorical
    maps = cfg["ordinal_maps"]
    for df in (fa, hw, gv, op):
        for col, mapname in cfg["columns"]["ordinal_fields"].items():
            if col in df.columns:
                df[col + "_ord"] = df[col].map(maps[mapname])

    return {"clinical": clinical, "clinical_raw": clinical_raw, "duplicates": duplicates,
            "facilities": fa, "workers": hw, "governance": gv, "operations": op}


def build_facility_panel(f: dict, cfg: dict) -> pd.DataFrame:
    """Collapse monthly clinical data to one row per facility and join the four
    characteristic tables. This is the analysis unit for everything downstream."""
    cl = f["clinical"].copy()
    cl["neonatal_deaths"] = cl["neonatal_deaths_0_7d"] + cl["neonatal_deaths_8_28d"]

    agg = cl.groupby("facility_id").agg(
        months_reported=("reporting_month", "nunique"),
        deliveries=("total_deliveries", "sum"),
        live_births=("live_births", "sum"),
        neonatal_deaths=("neonatal_deaths", "sum"),
        deaths_0_7d=("neonatal_deaths_0_7d", "sum"),
        deaths_8_28d=("neonatal_deaths_8_28d", "sum"),
        stillbirths=("stillbirths", "sum"),
        d_asphyxia=("death_birth_asphyxia", "sum"),
        d_prematurity=("death_prematurity", "sum"),
        d_sepsis=("death_sepsis", "sum"),
        d_congenital=("death_congenital", "sum"),
        d_other=("death_other", "sum"),
        preterm_28_32=("preterm_births_28_32w", "sum"),
        preterm_32_37=("preterm_births_32_37w", "sum"),
        low_birth_weight=("birth_weight_less_2500g", "sum"),
        apgar_low=("apgar_less_7_at_5min", "sum"),
        mean_gestational_age=("avg_gestational_age", "mean"),
    ).reset_index()

    d = (agg.merge(f["facilities"], on="facility_id", how="left")
            .merge(f["workers"], on="facility_id", how="left")
            .merge(f["governance"], on="facility_id", how="left")
            .merge(f["operations"], on="facility_id", how="left"))

    # --- derived measures -----------------------------------------------------
    d["nmr"] = 1000 * d["neonatal_deaths"] / d["live_births"]
    d["early_nmr"] = 1000 * d["deaths_0_7d"] / d["live_births"]
    d["stillbirth_rate"] = 1000 * d["stillbirths"] / d["deliveries"]
    d["low_birth_weight_rate"] = d["low_birth_weight"] / d["live_births"]
    d["preterm_rate"] = (d["preterm_28_32"] + d["preterm_32_37"]) / d["live_births"]
    d["very_preterm_rate"] = d["preterm_28_32"] / d["live_births"]
    d["asphyxia_rate"] = d["apgar_low"] / d["live_births"]

    d["incubator_functional_ratio"] = (d["incubators_functional"] / d["incubators_total"]).where(
        d["incubators_total"] > 0)
    d["neonatal_nurses_per_100_deliveries"] = 100 * d["neonatal_trained_nurses"] / d["deliveries"]

    never = cfg["parsing"]["never_sentinels"]
    d["never_trained"] = d["last_neonatal_training_date"].isin(never).astype(int)
    d["protocol_never_updated"] = d["protocol_last_updated"].isin(never).astype(int)
    return d


def profile(f: dict) -> str:
    """What did we actually load. Printed on every run — an FDE's first question."""
    out = ["SOURCE PROFILE", "=" * 68]
    for name in ["clinical", "facilities", "workers", "governance", "operations"]:
        df = f[name]
        out.append(f"  {name:<12} {len(df):>6,} rows x {len(df.columns):>2} cols")
    out.append(f"  {'duplicates':<12} {len(f['duplicates']):>6,} rows removed from clinical")
    return "\n".join(out)


if __name__ == "__main__":
    cfg = load_config()
    frames = load_all(cfg)
    print(profile(frames))
    print("\n" + build_facility_panel(frames, cfg).head().to_string())
