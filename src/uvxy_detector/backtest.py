from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import DetectionConfig
from .features import FeatureResult, compute_features
from .state import DetectionState, compute_states
from .types import BacktestMetrics, StateRow


@dataclass(frozen=True)
class BacktestResult:
    states: List[StateRow]
    metrics: Optional[BacktestMetrics]
    feature_result: FeatureResult


def _label_events(feature_result: FeatureResult, horizon: int) -> pd.Series:
    # Positive if s or carry_eff crosses <= 0 within horizon
    s = feature_result.raw["s"]
    carry = feature_result.raw["carry_eff"]
    forward_min_s = s.shift(-1).rolling(window=horizon, min_periods=1).min()
    forward_min_carry = carry.shift(-1).rolling(window=horizon, min_periods=1).min()
    label = ((forward_min_s <= 0) | (forward_min_carry <= 0)).astype(int)
    return label


def _compute_metrics(states: Iterable[StateRow]) -> BacktestMetrics:
    df = pd.DataFrame(
        {
            "date": [row.date for row in states],
            "state": [row.state for row in states],
            "label": [row.label for row in states],
            "llr": [row.llr for row in states],
        }
    )
    df = df.dropna(subset=["label"])
    if df.empty:
        return BacktestMetrics(
            precision=0.0,
            recall=0.0,
            f1=0.0,
            false_positives_per_month=0.0,
            miss_rate=1.0,
            avg_lead_days=np.nan,
        )

    df["is_confirm"] = df["state"] == DetectionState.CONFIRM

    tp = int(((df["is_confirm"]) & (df["label"] == 1)).sum())
    fp = int(((df["is_confirm"]) & (df["label"] == 0)).sum())
    fn = int(((~df["is_confirm"]) & (df["label"] == 1)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    miss_rate = fn / (tp + fn) if (tp + fn) > 0 else 1.0

    if len(df) > 1:
        days_span = (df["date"].iloc[-1] - df["date"].iloc[0]).days
        months = max(1.0, days_span / 30.0)
    else:
        months = 1.0
    false_positives_per_month = fp / months

    # Lead time: distance between first Confirm in a positive episode and event window
    lead_days: List[int] = []
    for idx, row in df[df["label"] == 1].iterrows():
        if row["is_confirm"]:
            lead_days.append(0)
        else:
            # Find next confirm within horizon window
            future_confirms = df.loc[idx :, :]
            future_dates = future_confirms.loc[future_confirms["is_confirm"], "date"]
            if not future_dates.empty:
                lead_days.append(int((future_dates.iloc[0] - row["date"]).days))
    avg_lead_days = float(np.nanmean(lead_days)) if lead_days else np.nan

    return BacktestMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        false_positives_per_month=false_positives_per_month,
        miss_rate=miss_rate,
        avg_lead_days=avg_lead_days,
    )


def backtest(df: pd.DataFrame, config: Optional[DetectionConfig] = None) -> BacktestResult:
    cfg = config or DetectionConfig()
    feature_result = compute_features(df, cfg)
    label_series = _label_events(feature_result, cfg.label_horizon)

    states = compute_states(feature_result, cfg)
    for row in states:
        object.__setattr__(row, "label", int(label_series.get(row.date, np.nan)))

    metrics = _compute_metrics(states) if len(states) else None
    return BacktestResult(states=states, metrics=metrics, feature_result=feature_result)
