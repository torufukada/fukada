"""
UVXY early crisis detection toolkit.

This package provides feature engineering, sequential probability ratio testing
logic, a state machine for Watch/Confirm signaling, backtesting utilities, and
an HTML report generator.
"""

from .config import DetectionConfig, DistributionParams, GateThresholds, WindowConfig
from .backtest import BacktestResult, backtest
from .report import render_html_report
from .state import DetectionState, compute_states

__all__ = [
    "BacktestResult",
    "DetectionConfig",
    "DetectionState",
    "DistributionParams",
    "GateThresholds",
    "WindowConfig",
    "backtest",
    "compute_states",
    "render_html_report",
]
