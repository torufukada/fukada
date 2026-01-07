from __future__ import annotations

import math
from typing import List, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import DetectionConfig
from .features import FeatureResult
from .types import CategoryFlags, StateRow


class DetectionState(str):
    NORMAL = "Normal"
    WATCH = "Pre-crisis Watch"
    CONFIRM = "Pre-crisis Confirm"


def _llr(value: float, mu0: float, sigma0: float, mu1: float, sigma1: float) -> float:
    if any(math.isnan(x) or math.isinf(x) for x in (value, sigma0, sigma1)):
        return float("nan")
    return norm.logpdf(value, mu1, sigma1) - norm.logpdf(value, mu0, sigma0)


def _confidence(llr_value: float, threshold: float) -> float:
    if math.isnan(llr_value) or math.isnan(threshold) or threshold <= 0:
        return 0.0
    return float(max(0.0, min(1.0, llr_value / threshold))) * 100


def _category_flags(
    components: pd.Series, raw: pd.Series, config: DetectionConfig
) -> CategoryFlags:
    gates = config.gates
    friction = bool(
        (components["s_flat_q"] >= gates.quantile_upper)
        or (components["ivts_q"] >= gates.quantile_upper)
        or (raw["carry_eff"] >= gates.carry_eff_floor)
    )
    temperature = bool(
        (components["vrp_q"] <= gates.quantile_lower)
        or (components["vvix_q"] >= gates.quantile_upper)
    )
    credit = bool(components["credit_q"] >= gates.quantile_upper)
    return CategoryFlags(friction=friction, temperature=temperature, credit=credit)


def compute_states(features: FeatureResult, config: DetectionConfig) -> List[StateRow]:
    gates = config.gates
    m_dist = config.distributions_m
    t_dist = config.distributions_t
    c_dist = config.distributions_c

    rows: List[StateRow] = []
    consecutive_confirm = 0
    current_state = DetectionState.NORMAL

    # Align frames
    components_df = features.components
    raw_df = features.raw

    for date, m_val, t_val, c_val in features.standardized.itertuples():
        raw_row = raw_df.loc[date]
        comp_row = components_df.loc[date]

        categories = _category_flags(comp_row, raw_row, config)
        satisfied = sum([categories.friction, categories.temperature, categories.credit])

        llr_m = _llr(m_val, m_dist.mu0, m_dist.sigma0, m_dist.mu1, m_dist.sigma1)
        llr_t = _llr(t_val, t_dist.mu0, t_dist.sigma0, t_dist.mu1, t_dist.sigma1)
        llr_c = _llr(c_val, c_dist.mu0, c_dist.sigma0, c_dist.mu1, c_dist.sigma1)
        llr_total = llr_m + llr_t + llr_c

        gate1 = satisfied >= 2
        gate2 = satisfied == 3 and llr_total >= gates.llr_upper

        if math.isnan(llr_total) or np.isnan([m_val, t_val, c_val]).any():
            gate2 = False

        if gate2:
            consecutive_confirm += 1
        else:
            consecutive_confirm = 0

        if current_state == DetectionState.NORMAL:
            if gate1:
                current_state = DetectionState.WATCH
        elif current_state == DetectionState.WATCH:
            if gate2 and consecutive_confirm >= gates.consecutive_confirm:
                current_state = DetectionState.CONFIRM
        elif current_state == DetectionState.CONFIRM:
            if llr_total <= gates.llr_lower or satisfied <= 1:
                current_state = DetectionState.NORMAL

        confidence = _confidence(llr_total, gates.llr_upper)

        rows.append(
            StateRow(
                date=pd.to_datetime(date),
                state=current_state,
                llr=float(llr_total),
                confidence=confidence,
                categories=categories,
                m_value=float(m_val),
                t_value=float(t_val),
                c_value=float(c_val),
                components={
                    "s": float(raw_row["s"]),
                    "s_flat": float(raw_row["s_flat"]),
                    "carry_eff": float(raw_row["carry_eff"]),
                    "ivts": float(raw_row["ivts"]),
                    "vrp": float(raw_row["vrp"]),
                    "vvix_alt": float(raw_row["vvix_alt"]),
                    "credit_diff": float(raw_row["credit_diff"]),
                },
            )
        )

    return rows
