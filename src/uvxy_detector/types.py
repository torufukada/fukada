from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass(frozen=True)
class CategoryFlags:
    friction: bool
    temperature: bool
    credit: bool


@dataclass(frozen=True)
class StateRow:
    date: pd.Timestamp
    state: str
    llr: float
    confidence: float
    categories: CategoryFlags
    m_value: float
    t_value: float
    c_value: float
    components: Dict[str, float]
    label: Optional[int] = None


@dataclass(frozen=True)
class BacktestMetrics:
    precision: float
    recall: float
    f1: float
    false_positives_per_month: float
    miss_rate: float
    avg_lead_days: float
