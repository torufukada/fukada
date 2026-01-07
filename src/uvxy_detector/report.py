from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .types import BacktestMetrics, StateRow


def _format_metrics(metrics: BacktestMetrics) -> str:
    return f"""
    <ul>
      <li>Precision: {metrics.precision:.3f}</li>
      <li>Recall: {metrics.recall:.3f}</li>
      <li>F1: {metrics.f1:.3f}</li>
      <li>False Positives / month: {metrics.false_positives_per_month:.3f}</li>
      <li>Miss rate: {metrics.miss_rate:.3f}</li>
      <li>Average lead days: {metrics.avg_lead_days if metrics.avg_lead_days == metrics.avg_lead_days else 'NA'}</li>
    </ul>
    """


def _states_table(states: Iterable[StateRow]) -> str:
    records = []
    for row in states:
        records.append(
            {
                "date": row.date.date(),
                "state": row.state,
                "llr": round(row.llr, 3),
                "confidence": round(row.confidence, 1),
                "M": round(row.m_value, 3),
                "T": round(row.t_value, 3),
                "C": round(row.c_value, 3),
                "friction": row.categories.friction,
                "temperature": row.categories.temperature,
                "credit": row.categories.credit,
                "label": row.label,
            }
        )
    df = pd.DataFrame.from_records(records)
    return df.to_html(index=False, escape=False)


def render_html_report(states: Iterable[StateRow], metrics: BacktestMetrics, output_path: str | Path) -> Path:
    """Render an HTML report showing backtest metrics and daily state outputs."""
    ts = datetime.utcnow().isoformat()
    html_body = f"""
    <html>
      <head>
        <meta charset="utf-8">
        <title>UVXY Early Crisis Detection Report</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 1.5rem; }}
          table {{ border-collapse: collapse; width: 100%; }}
          th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: center; }}
          th {{ background: #f4f4f4; }}
        </style>
      </head>
      <body>
        <h1>UVXY Early Crisis Detection Backtest</h1>
        <p>Generated at {html.escape(ts)} UTC</p>
        <h2>Metrics</h2>
        {_format_metrics(metrics)}
        <h2>State Timeline</h2>
        {_states_table(states)}
      </body>
    </html>
    """

    output_path = Path(output_path)
    output_path.write_text(html_body, encoding="utf-8")
    return output_path
