# fukada

UVXY 反転初期（早期危機）検知のための実装雛形です。特徴量生成、SPRTベースの Gate 判定、バックテスト、HTML レポート出力までを一通り揃えています。

## フォルダ構成

- `src/uvxy_detector/` — コアライブラリ（特徴量、Gate/LLR 判定、バックテスト、HTML レポート）
- `scripts/` — CLI ツール (`run_backtest.py`)
- `docs/` — 仕様ドキュメント
- `requirements.txt` / `pyproject.toml` — 依存関係とパッケージ設定

## 使い方

1. 依存をインストール

   ```bash
   pip install -e .
   ```

2. データ CSV を用意（必須カラム）

   ```
   date, spx_close, spx_high, spx_low, vix_close, vix_high, vix_low,
   vix3m_close, vx1_settle, vx2_settle, hy_oas, ig_oas
   ```

   ※日付順にソートされていなくても自動で整列します。

3. バックテスト & HTML 出力（例）

   ```bash
   python scripts/run_backtest.py --input your_data.csv --output-html report.html --output-states states.csv
   ```

   - `report.html` にメトリクスと日次ステートを出力
   - `states.csv` に日次の判定結果を出力

## API（別 HTML への出力）

Python から直接利用する場合:

```python
import pandas as pd
from uvxy_detector import backtest, render_html_report

df = pd.read_csv("your_data.csv")
result = backtest(df)

if result.metrics:
    render_html_report(result.states, result.metrics, "report.html")
```

`render_html_report` に任意のパスを渡せば、別ファイルへの HTML 出力が可能です。

## Documents

- [早期危機検知（UVXY反転初期）システム設計書](docs/uvxy_early_crisis_detection.md)
