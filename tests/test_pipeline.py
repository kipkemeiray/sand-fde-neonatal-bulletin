"""
test_pipeline.py — regression tests.

Not coverage-driven. Each test pins a specific way this dataset can silently
produce a wrong bulletin. The first three are the defects that make this extract
dangerous; all three fail silently under a naive implementation.

Run:  make test
"""

from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import ingest, quality, metrics, drivers  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return ingest.load_config(ROOT / "config.yaml")


@pytest.fixture(scope="module")
def frames(cfg):
    return ingest.load_all(cfg)


@pytest.fixture(scope="module")
def panel(frames, cfg):
    return quality.suppression(ingest.build_facility_panel(frames, cfg), cfg)


# ══════════════════════════ the three silent killers ══════════════════════════

def test_none_is_a_category_not_missing_data(frames):
    """THE most dangerous defect in this dataset.

    'None' in night_shift_coverage means the facility has NO overnight cover —
    63 of 117 facilities. pandas' default na_values converts it to NaN, deleting
    the worst-performing majority of the estate from every grouped analysis, with
    no error raised.
    """
    hw = frames["workers"]
    assert (hw["night_shift_coverage"] == "None").sum() == 63
    assert hw["night_shift_coverage"].isna().sum() == 0, \
        "'None' was swallowed as NaN — default NA inference is back on"
    assert set(hw["night_shift_coverage"].unique()) == {"None", "Partial", "Full"}
    assert (hw["night_shift_coverage_ord"] == 0).sum() == 63


def test_naive_read_would_lose_the_worst_facilities():
    """Demonstrates the failure this pipeline avoids, so the guard is never removed."""
    naive = pd.read_csv(ROOT / "data/raw/healthcare_workers.csv")   # pandas defaults
    assert naive["night_shift_coverage"].isna().sum() == 63, \
        "if this changes, the na_values guard in ingest may no longer be needed"
    assert "None" not in set(naive["night_shift_coverage"].dropna().unique())


def test_duplicate_months_are_removed_and_quantified(frames, cfg):
    """234 conflicting duplicate rows across 2024-01 and 2024-03 inflate every
    volume figure by ~20% — including 'Top 10 facilities by volume'."""
    rep = quality.duplicate_report(frames, cfg)
    assert rep["duplicate_rows"] == 234
    assert rep["affected_months"] == ["2024-01", "2024-03"]
    assert rep["affected_facilities"] == 117
    assert 19 < rep["volume_inflation_pct"] < 21
    assert not frames["clinical"].duplicated(cfg["dedupe"]["key"]).any()


def test_extract_is_ten_months_not_twelve(frames):
    """Quarter totals are not comparable as levels. Missing months must be surfaced."""
    cov = quality.coverage_report(frames)
    assert cov["n_months"] == 10
    assert cov["months_missing"] == ["2024-02", "2024-12"]


# ══════════════════════════ analytical honesty ══════════════════════════

def test_tier_confounding_is_detected(panel, cfg):
    """The centrepiece. Unadjusted, capability appears to explain most mortality
    variation. Adjusted for tier it collapses. If this test ever fails, the
    bulletin's central caveat is no longer true and the narrative must change."""
    t = drivers.driver_table(panel, cfg)
    top = t.iloc[0]
    assert abs(top["unadjusted"]) > 0.5, "expected a strong naive correlation"
    assert abs(top["tier_adjusted"]) < 0.2, "tier adjustment failed to attenuate"
    assert top["attenuation_pct"] > 60
    assert t["tier_adjusted"].abs().max() < 0.25, \
        "a driver now survives adjustment — revisit the 'no causal claim' framing"


def test_some_drivers_flip_sign_under_adjustment(panel, cfg):
    assert drivers.driver_table(panel, cfg)["sign_flip"].sum() >= 5


def test_case_mix_does_not_explain_mortality(panel, cfg):
    """Justifies adjusting for tier only. Re-checked every run rather than assumed."""
    c = drivers.case_mix_check(panel, cfg)
    assert (c["unadjusted"].abs() < 0.25).all(), \
        "case-mix now correlates with NMR — the excess-mortality model needs it"


def test_excess_mortality_is_tier_relative(panel, cfg):
    """Expected deaths must sum to observed within each tier, or the model is biased."""
    d = metrics.expected_deaths_model(panel, cfg)
    for tier, g in d.groupby("tier_level"):
        assert abs(g["expected_deaths"].sum() - g["neonatal_deaths"].sum()) < 1e-6, \
            f"expected != observed within {tier}"
    assert abs(d["excess_deaths"].sum()) < 1e-6


# ══════════════════════════ arithmetic and guards ══════════════════════════

def test_national_indicators_reconcile(panel, cfg):
    n = metrics.national_indicators(panel, cfg)
    assert n["neonatal_deaths"] == int(panel["deaths_0_7d"].sum() + panel["deaths_8_28d"].sum())
    assert abs(n["nmr"] - 1000 * n["neonatal_deaths"] / n["live_births"]) < 0.05
    assert n["facilities"] == 117
    assert n["live_births"] <= n["deliveries"]


def test_cause_of_death_sums_to_total(panel):
    c = metrics.cause_of_death(panel)
    assert c["deaths"].sum() == int(panel["neonatal_deaths"].sum())
    assert abs(c["share_pct"].sum() - 100) < 0.5


def test_suppression_threshold_actually_fires(panel, cfg):
    """The guard must work even though no facility currently trips it."""
    strict = {**cfg, "quality": {**cfg["quality"], "min_live_births_to_rank": 10_000}}
    s = quality.suppression(panel.drop(columns=["suppressed", "suppression_reason"]), strict)
    assert s["suppressed"].sum() > 0
    assert s.loc[s["suppressed"], "suppression_reason"].str.len().gt(0).all()


def test_percentages_parsed_from_strings(frames):
    g = frames["governance"]
    for c in ["hmis_reporting_completeness", "bag_mask_ventilation_competency"]:
        assert pd.api.types.is_numeric_dtype(g[c])
        assert g[c].between(0, 100).all()


def test_never_sentinels_preserved(frames):
    """'Never' means never happened, not unknown. 48 facilities, not 48 nulls."""
    assert (frames["workers"]["last_neonatal_training_date"] == "Never").sum() == 48
    assert (frames["governance"]["protocol_last_updated"] == "Never").sum() == 14


def test_all_facilities_join_cleanly(panel):
    assert len(panel) == 117
    assert panel["facility_id"].nunique() == 117
    assert panel["tier_level"].notna().all()
    assert panel["nmr"].notna().all()


def test_top_facilities_ranked_on_deduplicated_volume(panel, cfg):
    top = metrics.top_facilities_by_volume(panel, cfg)
    assert len(top) == cfg["bulletin"]["top_n_facilities"]
    assert top["deliveries"].is_monotonic_decreasing
    assert top["deliveries"].sum() < 100_000, "looks like duplicated volume leaked in"


def test_quarterly_trend_reports_month_counts(frames, cfg):
    t = metrics.quarterly_trend(frames, cfg)
    assert "months" in t.columns
    assert t["months"].min() < 3, "a short quarter should be visible, not hidden"
    assert t["months"].sum() == 10
