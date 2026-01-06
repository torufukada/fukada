from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .config import GateConfig, SprtConfig, SystemConfig
from .features import compute_features, llr_from_norm


def build_indicator_frame(
    raw: pd.DataFrame,
    config: SystemConfig,
    regime_column: Optional[str] = None,
) -> pd.DataFrame:
    features = compute_features(raw, config.features)

    # Category flags based on quantiles and thresholds
    features["friction_met"] = (
        (features["s_flat_q"] >= config.features.quantile_high)
        | (features["ivts_q"] >= config.features.quantile_high)
        | (features["carry_eff"] <= config.features.carry_eff_floor)
    )
    features["temperature_met"] = (features["vrp_q"] <= config.features.quantile_low) | (
        features["vvix_alt_q"] >= config.features.quantile_high
    )
    features["credit_met"] = (features["credit_q"] >= config.features.quantile_high) | (
        features["credit_z"] >= config.gates.credit_z_threshold
    )

    # SPRT parameters: allow estimation from labelled data when available
    if regime_column and regime_column in raw.columns:
        features = _apply_regime_params(features, raw[regime_column], config.sprt)
    else:
        features = _apply_default_llr(features, config.sprt)

    return features


def _apply_default_llr(df: pd.DataFrame, sprt: SprtConfig) -> pd.DataFrame:
    df = df.copy()
    df["llr"] = (
        llr_from_norm(df["m_composite"], sprt.mu0, sprt.sigma0, sprt.mu1, sprt.sigma1)
        + llr_from_norm(df["t_composite"], sprt.mu0, sprt.sigma0, sprt.mu1, sprt.sigma1)
        + llr_from_norm(df["c_composite"], sprt.mu0, sprt.sigma0, sprt.mu1, sprt.sigma1)
    )
    return df


def _apply_regime_params(
    df: pd.DataFrame,
    regimes: pd.Series,
    sprt: SprtConfig,
) -> pd.DataFrame:
    df = df.copy()
    normal_mask = regimes == "normal"
    crisis_mask = regimes == "precrisis"

    def _estimate(series: pd.Series, mask: pd.Series) -> tuple[float, float]:
        subset = series[mask].dropna()
        if subset.empty:
            return sprt.mu0, sprt.sigma0
        return subset.mean(), max(subset.std(ddof=0), 1e-6)

    mu0_m, sigma0_m = _estimate(df["m_composite"], normal_mask)
    mu1_m, sigma1_m = _estimate(df["m_composite"], crisis_mask)
    mu0_t, sigma0_t = _estimate(df["t_composite"], normal_mask)
    mu1_t, sigma1_t = _estimate(df["t_composite"], crisis_mask)
    mu0_c, sigma0_c = _estimate(df["c_composite"], normal_mask)
    mu1_c, sigma1_c = _estimate(df["c_composite"], crisis_mask)

    df["llr"] = (
        llr_from_norm(df["m_composite"], mu0_m, sigma0_m, mu1_m, sigma1_m)
        + llr_from_norm(df["t_composite"], mu0_t, sigma0_t, mu1_t, sigma1_t)
        + llr_from_norm(df["c_composite"], mu0_c, sigma0_c, mu1_c, sigma1_c)
    )
    return df


def run_detection(
    indicator_df: pd.DataFrame,
    config: SystemConfig,
) -> pd.DataFrame:
    df = indicator_df.copy()
    df["categories_met"] = df[["friction_met", "temperature_met", "credit_met"]].fillna(False).sum(
        axis=1
    )
    df["gate1"] = df["categories_met"] >= 2

    gate2_condition = (
        (df["categories_met"] == 3)
        & (df["llr"] >= config.sprt.llr_threshold_a)
        & df[["m_composite", "t_composite", "c_composite"]].notna().all(axis=1)
    )

    states = []
    confidence = []
    streak = 0
    current_state = "Normal"
    for idx, row in df.iterrows():
        if gate2_condition.loc[idx]:
            streak += 1
        else:
            streak = 0

        if streak >= config.gates.consecutive_confirm_days:
            current_state = "Pre-crisis Confirm"
        elif row["gate1"]:
            current_state = "Pre-crisis Watch"
        if (row["llr"] <= config.sprt.llr_threshold_b) or (row["categories_met"] <= 1):
            current_state = "Normal"
            streak = 0

        states.append(current_state)
        llr_value = row["llr"]
        if pd.isna(llr_value):
            conf = 0.0
        else:
            conf = max(0.0, min(1.0, llr_value / config.sprt.llr_threshold_a)) * 100.0
        confidence.append(conf)

    df["state"] = states
    df["confidence"] = confidence
    return df
