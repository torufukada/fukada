from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WindowConfig:
    """Rolling window lengths and smoothing parameters."""

    zscore_window: int = 90
    ewm_halflife_vol: int = 10
    ewm_halflife_term: int = 10
    credit_diff_window: int = 5
    realized_vol_window: int = 20


@dataclass(frozen=True)
class GateThresholds:
    """Gate and quantile thresholds for category satisfaction."""

    quantile_upper: float = 0.85
    quantile_lower: float = 0.15
    carry_eff_floor: float = -0.02  # approaching 0 implies friction loss
    llr_upper: float = 5.08  # SPRT A
    llr_lower: float = -1.61  # SPRT B
    consecutive_confirm: int = 2


@dataclass(frozen=True)
class DistributionParams:
    """
    Gaussian parameters for SPRT under H0 and H1.

    Defaults favor a conservative separation; users are encouraged to
    recalibrate on in-sample data.
    """

    mu0: float = 0.0
    sigma0: float = 1.0
    mu1: float = 1.2
    sigma1: float = 1.0


@dataclass(frozen=True)
class DetectionConfig:
    """Top-level configuration for detection and backtesting."""

    windows: WindowConfig = WindowConfig()
    gates: GateThresholds = GateThresholds()
    distributions_m: DistributionParams = DistributionParams()
    distributions_t: DistributionParams = DistributionParams()
    distributions_c: DistributionParams = DistributionParams()
    target_vix_days: int = 30
    vx1_days: int = 20
    vx2_days: int = 50
    min_history: int = 120
    label_horizon: int = 3
    training_window: Optional[int] = 252
