from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import norm, percentileofscore

from .config import FeatureConfig


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    rolling_mean = series.rolling(window, min_periods=window).mean()
    rolling_std = series.rolling(window, min_periods=window).std(ddof=0)
    return (series - rolling_mean) / rolling_std


def percentile_rank(series: pd.Series, window: int) -> pd.Series:
    def _pct(x: np.ndarray) -> float:
        current = x[-1]
        return percentileofscore(x, current, kind="weak") / 100.0

    return series.rolling(window, min_periods=window).apply(_pct, raw=True)


def combine_standardized(values: Iterable[pd.Series]) -> pd.Series:
    stacked = pd.concat(values, axis=1)
    return stacked.mean(axis=1, skipna=True)


def compute_features(df: pd.DataFrame, cfg: FeatureConfig) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    # Returns and realized vol
    out["r_spx"] = np.log(df["spx_close"] / df["spx_close"].shift(1))
    out["rv20"] = out["r_spx"].rolling(20, min_periods=20).std(ddof=0) * np.sqrt(252)

    # Term structure and friction
    out["s"] = (df["vx2"] - df["vx1"]) / df["vx1"]
    s_ewm = out["s"].ewm(halflife=cfg.ewm_halflife_fast, adjust=False).mean()
    out["s_flat"] = -s_ewm.diff()

    out["ivts"] = df["vix"] / df["vix3m"]

    w1 = (cfg.maturity_back - cfg.maturity_target) / (cfg.maturity_back - cfg.maturity_front)
    w2 = 1.0 - w1
    i_t = w1 * df["vx1"] + w2 * df["vx2"]
    roll_speed = cfg.carry_eff_roll_speed
    out["carry_eff"] = roll_speed * (df["vx2"] - df["vx1"]) / i_t

    # Volatility temperature
    out["vrp"] = df["vix"] - out["rv20"]
    vix_range = (df["vix_high"] - df["vix_low"]) / df["vix_close"]
    vvix_smoothed = vix_range.ewm(halflife=cfg.ewm_halflife_fast, adjust=False).mean()
    out["vvix_alt"] = vvix_smoothed

    # Credit
    credit_raw = df["hy_oas"] - df["ig_oas"]
    credit_delta = credit_raw.diff()
    out["credit_z"] = rolling_zscore(credit_delta, cfg.standardize_window // 3 or 5)

    # Standardization and percentile ranks
    out["s_flat_q"] = percentile_rank(out["s_flat"], cfg.quantile_window)
    out["ivts_q"] = percentile_rank(out["ivts"], cfg.quantile_window)
    out["carry_eff_q"] = percentile_rank(out["carry_eff"], cfg.quantile_window)
    out["vrp_q"] = percentile_rank(out["vrp"], cfg.quantile_window)
    out["vvix_alt_q"] = percentile_rank(out["vvix_alt"], cfg.quantile_window)
    out["credit_q"] = percentile_rank(out["credit_z"], cfg.quantile_window)

    # Standardized composites for SPRT
    out["s_flat_z"] = rolling_zscore(out["s_flat"], cfg.standardize_window)
    out["ivts_z"] = rolling_zscore(out["ivts"], cfg.standardize_window)
    out["carry_eff_z"] = rolling_zscore(out["carry_eff"], cfg.standardize_window)
    out["vrp_z"] = rolling_zscore(out["vrp"], cfg.standardize_window)
    out["vvix_alt_z"] = rolling_zscore(out["vvix_alt"], cfg.standardize_window)

    out["m_composite"] = combine_standardized(
        [out["s_flat_z"], out["carry_eff_z"], out["ivts_z"]]
    )
    out["t_composite"] = combine_standardized([out["vrp_z"], out["vvix_alt_z"]])
    out["c_composite"] = out["credit_z"]

    return out


def llr_from_norm(
    series: pd.Series,
    mu0: float,
    sigma0: float,
    mu1: float,
    sigma1: float,
) -> pd.Series:
    log_p1 = norm.logpdf(series, loc=mu1, scale=sigma1)
    log_p0 = norm.logpdf(series, loc=mu0, scale=sigma0)
    return log_p1 - log_p0
