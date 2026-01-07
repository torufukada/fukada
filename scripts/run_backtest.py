#!/usr/bin/env python
"""
Run the UVXY early crisis detector backtest on a CSV input and export an HTML report.

Expected CSV columns:
date, spx_close, spx_high, spx_low, vix_close, vix_high, vix_low,
vix3m_close, vx1_settle, vx2_settle, hy_oas, ig_oas
"""

import argparse
from pathlib import Path

import pandas as pd

from uvxy_detector import DetectionConfig, backtest, render_html_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UVXY Early Crisis Detector Backtest")
    parser.add_argument("--input", required=True, help="Input CSV path with required columns")
    parser.add_argument("--output-html", default="backtest_report.html", help="Output HTML path")
    parser.add_argument(
        "--output-states", default="states.csv", help="Output CSV with daily state timeline"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)
    config = DetectionConfig()
    result = backtest(df, config)

    states_df = pd.DataFrame(
        [
            {
                "date": row.date,
                "state": row.state,
                "llr": row.llr,
                "confidence": row.confidence,
                "m": row.m_value,
                "t": row.t_value,
                "c": row.c_value,
                "friction": row.categories.friction,
                "temperature": row.categories.temperature,
                "credit": row.categories.credit,
                "label": row.label,
            }
            for row in result.states
        ]
    )
    states_path = Path(args.output_states)
    states_df.to_csv(states_path, index=False)

    if result.metrics:
        report_path = render_html_report(result.states, result.metrics, args.output_html)
        print(f"Wrote HTML report to {report_path}")
    else:
        print("Insufficient data to compute metrics. States CSV still generated.")


if __name__ == "__main__":
    main()
