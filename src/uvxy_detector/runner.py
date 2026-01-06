from __future__ import annotations

import argparse
import pathlib

import pandas as pd

from .config import SystemConfig
from .pipeline import build_indicator_frame, run_detection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run UVXY early crisis detection on a CSV dataset.",
    )
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        required=True,
        help="Input CSV containing columns: date, spx_close, vix, vix3m, vx1, vx2, "
        "vix_high, vix_low, vix_close, hy_oas, ig_oas.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        required=True,
        help="Destination CSV for detection results.",
    )
    parser.add_argument(
        "--regime-column",
        type=str,
        default=None,
        help="Optional column name in the input that labels rows as 'normal' or 'precrisis' "
        "for on-the-fly SPRT parameter estimation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = pd.read_csv(args.input, parse_dates=["date"])
    raw = raw.set_index("date").sort_index()

    config = SystemConfig()
    indicators = build_indicator_frame(raw, config, regime_column=args.regime_column)
    results = run_detection(indicators, config)
    results.reset_index().to_csv(args.output, index=False)
    print(f"Wrote detection results to {args.output}")


if __name__ == "__main__":
    main()
