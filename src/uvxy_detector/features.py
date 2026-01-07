from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .config import DetectionConfig


REQUIRED_COLUMNS = [
    "date",
    "spx_close",
    "spx_high",
    "spx_low",
    "vix_close",
    "vix_high",
    "vix_low",
    "vix3m_close",
    "vx1_settle",
    "vx2_settle",
    "hy_oas",
    "ig_oas",
]


@dataclass(frozen=True)
class FeatureResult:
    raw: pd.DataFrame
    standardized: pd.DataFrame
    components: pd.DataFrame


def _zscore(series: pd.Series, window: int) -> pd.Series:
    rolling = series.rolling(window=window, min_periods=max(10, window // 3))
    mean = rolling.mean()
    std = rolling.std(ddof=0)
    z = (series - mean) / std
    return z.replace([np.inf, -np.inf], np.nan)


def _quantile_rank(series: pd.Series, window: int) -> pd.Series:
    def ranker(x: pd.Series) -> float:
        if x.empty:
            return np.nan
        last = x.iloc[-1]
        return (x <= last).mean()

    return (
        series.rolling(window=window, min_periods=max(10, window // 3))
        .apply(ranker, raw=False)
        .clip(0, 1)
    )


def _realized_vol(log_returns: pd.Series, window: int) -> pd.Series:
    return log_returns.rolling(window=window, min_periods=max(10, window // 3)).std(ddof=0) * np.sqrt(
        252
    )


def compute_features(df: pd.DataFrame, config: DetectionConfig) -> FeatureResult:
    """
    Compute raw and standardized features required by the detector.

    Expected columns (all lowercase):
        date, spx_close, spx_high, spx_low, vix_close, vix_high, vix_low,
        vix3m_close, vx1_settle, vx2_settle, hy_oas, ig_oas
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").set_index("date")

    windows = config.windows

    # Core metrics
    data["s"] = (data["vx2_settle"] - data["vx1_settle"]) / data["vx1_settle"]
    data["s_ewm"] = data["s"].ewm(halflife=windows.ewm_halflife_term, adjust=False).mean()
    data["s_flat"] = -(data["s_ewm"].diff())

    weight1 = (config.vx2_days - config.target_vix_days) / (config.vx2_days - config.vx1_days)
    weight2 = 1 - weight1
    index_approx = weight1 * data["vx1_settle"] + weight2 * data["vx2_settle"]
    delta_w = -1 / (config.vx2_days - config.vx1_days)
    data["carry_eff"] = delta_w * (data["vx2_settle"] - data["vx1_settle"]) / index_approx

    data["ivts"] = data["vix_close"] / data["vix3m_close"]

    data["spx_ret"] = np.log(data["spx_close"] / data["spx_close"].shift(1))
    data["rv20"] = _realized_vol(data["spx_ret"], windows.realized_vol_window)
    data["vrp"] = data["vix_close"] - data["rv20"]

    vix_range = (data["vix_high"] - data["vix_low"]) / data["vix_close"]
    data["vvix_alt"] = vix_range.ewm(halflife=windows.ewm_halflife_vol, adjust=False).mean()

    data["credit_raw"] = data["hy_oas"] - data["ig_oas"]
    data["credit_diff"] = data["credit_raw"].diff(periods=windows.credit_diff_window)

    # Standardization
    standardized: Dict[str, pd.Series] = {
        "s_flat_z": _zscore(data["s_flat"], windows.zscore_window),
        "carry_eff_z": _zscore(data["carry_eff"], windows.zscore_window),
        "ivts_z": _zscore(data["ivts"], windows.zscore_window),
        "vrp_z": -_zscore(data["vrp"], windows.zscore_window),  # invert: compression => high z
        "vvix_z": _zscore(data["vvix_alt"], windows.zscore_window),
        "credit_z": _zscore(data["credit_diff"], windows.zscore_window),
    }

    quantiles: Dict[str, pd.Series] = {
        "s_flat_q": _quantile_rank(data["s_flat"], windows.zscore_window),
        "ivts_q": _quantile_rank(data["ivts"], windows.zscore_window),
        "vrp_q": _quantile_rank(data["vrp"], windows.zscore_window),
        "vvix_q": _quantile_rank(data["vvix_alt"], windows.zscore_window),
        "credit_q": _quantile_rank(data["credit_diff"], windows.zscore_window),
    }

    components = pd.DataFrame({**standardized, **quantiles}, index=data.index)

    m = pd.concat(
        [components["s_flat_z"], components["carry_eff_z"], components["ivts_z"]], axis=1
    ).mean(axis=1)
    t = pd.concat([components["vrp_z"], components["vvix_z"]], axis=1).mean(axis=1)
    c = components["credit_z"]

    standardized_df = pd.DataFrame(
        {
            "M": m,
            "T": t,
            "C": c,
        },
        index=data.index,
    )

    raw = pd.DataFrame(
        {
            "s": data["s"],
            "s_flat": data["s_flat"],
            "carry_eff": data["carry_eff"],
            "ivts": data["ivts"],
            "vrp": data["vrp"],
            "vvix_alt": data["vvix_alt"],
            "credit_diff": data["credit_diff"],
        },
        index=data.index,
    )

    return FeatureResult(raw=raw, standardized=standardized_df, components=components)
