# fukada

UVXY反転初期の検知システムを実装するためのリファレンス実装です。特徴量生成、SPRTベースの判定、連続成立を要求する状態遷移を含みます。

## クイックスタート

### セットアップ

```bash
python -m pip install -e .[dev]
```

### 入力データ

`date`列と以下のカラムを持つ日次CSVを前提としています。

- `spx_close`, `vix`, `vix3m`
- `vx1`, `vx2`（VIX先物期近・次限）
- `vix_high`, `vix_low`, `vix_close`
- `hy_oas`, `ig_oas`
- オプションで`regime`列（`normal` / `precrisis`）を付与するとSPRT分布をデータから推定します。

### 実行例

```bash
python -m uvxy_detector.runner \
  --input path/to/data.csv \
  --output path/to/results.csv \
  --regime-column regime
```

出力CSVにはGate判定、LLR、confidence、状態（Normal / Pre-crisis Watch / Pre-crisis Confirm）が含まれます。

### テスト

```bash
pytest
```

## Documentation

- [早期危機検知（UVXY反転初期）システム総合ドキュメント](docs/early_crisis_detection.md)
