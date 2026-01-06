from dataclasses import dataclass
from dataclasses import field


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""

    ewm_halflife_fast: int = 10
    credit_halflife: int = 7
    standardize_window: int = 90
    quantile_window: int = 90
    quantile_high: float = 0.85
    quantile_low: float = 0.15
    carry_eff_roll_speed: float = 1.0 / 21.0
    maturity_front: float = 10.0
    maturity_back: float = 40.0
    maturity_target: float = 30.0
    carry_eff_floor: float = 0.0


@dataclass
class GateConfig:
    """Gate and category thresholds."""

    consecutive_confirm_days: int = 2
    credit_z_threshold: float = 1.0


@dataclass
class SprtConfig:
    """Sequential probability ratio test configuration."""

    alpha: float = 0.005
    beta: float = 0.2
    llr_threshold_a: float = 5.08
    llr_threshold_b: float = -1.61

    # Default distribution priors for standardized features
    mu0: float = 0.0
    sigma0: float = 1.0
    mu1: float = 1.0
    sigma1: float = 1.0


@dataclass
class SystemConfig:
    """Aggregated configuration."""

    features: FeatureConfig = field(default_factory=FeatureConfig)
    gates: GateConfig = field(default_factory=GateConfig)
    sprt: SprtConfig = field(default_factory=SprtConfig)
