import numpy as np
import pandas as pd

from uvxy_detector.config import FeatureConfig, GateConfig, SprtConfig, SystemConfig
from uvxy_detector.pipeline import build_indicator_frame, run_detection


def _sample_raw() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    # Normal then stressed regime
    spx_close = np.linspace(100, 111, len(dates))
    vix = np.concatenate([np.full(6, 18.0), np.full(6, 32.0)])
    vix3m = np.concatenate([np.full(6, 19.0), np.full(6, 25.0)])
    vx1 = np.concatenate([np.full(6, 20.0), np.full(6, 18.0)])
    vx2 = np.concatenate([np.full(6, 22.0), np.full(6, 17.0)])
    vix_high = vix + 1.0
    vix_low = vix - 1.0
    hy_oas = np.concatenate([np.full(6, 4.0), np.full(6, 6.5)])
    ig_oas = np.concatenate([np.full(6, 1.5), np.full(6, 1.2)])

    raw = pd.DataFrame(
        {
            "date": dates,
            "spx_close": spx_close,
            "vix": vix,
            "vix3m": vix3m,
            "vx1": vx1,
            "vx2": vx2,
            "vix_high": vix_high,
            "vix_low": vix_low,
            "vix_close": vix,
            "hy_oas": hy_oas,
            "ig_oas": ig_oas,
        }
    ).set_index("date")
    raw["regime"] = ["normal"] * 6 + ["precrisis"] * 6
    return raw


def test_detection_reaches_confirm_state():
    raw = _sample_raw()
    config = SystemConfig(
        features=FeatureConfig(
            ewm_halflife_fast=2,
            credit_halflife=3,
            standardize_window=3,
            quantile_window=3,
            quantile_high=0.7,
            quantile_low=0.3,
            carry_eff_floor=0.0,
        ),
        gates=GateConfig(consecutive_confirm_days=2, credit_z_threshold=0.2),
        sprt=SprtConfig(
            alpha=0.005,
            beta=0.2,
            llr_threshold_a=0.5,
            llr_threshold_b=-0.5,
            mu0=0.0,
            sigma0=1.0,
            mu1=1.5,
            sigma1=1.0,
        ),
    )

    indicators = build_indicator_frame(raw, config, regime_column="regime")
    results = run_detection(indicators, config)

    last_states = results["state"].tail(2).unique().tolist()
    assert "Pre-crisis Confirm" in last_states
    assert results["gate1"].iloc[-1] is True
    assert results["categories_met"].iloc[-1] == 3


def test_gate2_disabled_when_categories_missing():
    raw = _sample_raw()
    raw.loc[raw.index[-1], ["vx1", "vx2"]] = np.nan  # removes friction inputs
    config = SystemConfig(
        features=FeatureConfig(
            ewm_halflife_fast=2,
            credit_halflife=3,
            standardize_window=3,
            quantile_window=3,
            quantile_high=0.7,
            quantile_low=0.3,
            carry_eff_floor=0.0,
        ),
        gates=GateConfig(consecutive_confirm_days=2, credit_z_threshold=0.2),
        sprt=SprtConfig(
            llr_threshold_a=0.5,
            llr_threshold_b=-0.5,
            mu1=1.5,
        ),
    )

    indicators = build_indicator_frame(raw, config, regime_column="regime")
    results = run_detection(indicators, config)
    assert not results.loc[results.index[-1], "gate1"]
    assert results.loc[results.index[-1], "state"] == "Normal"
