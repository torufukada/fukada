# 早期危機検知（UVXY反転初期）システム総合ドキュメント

## 1. 目的と到達目標

### 目的
- SPXが日次で2〜5%動く本格暴落に入る前段階で、擬陽性を極小化し「UVXYの反転初期」を検知する。
- コンタンゴによる負キャリーの緩み（摩擦低下）と、ボラの温度上昇、信用・相関の結合度上昇が同時に起きる局面を検知条件とする。

### 実務KPI（この範囲を満たせば「可能」と判定）
- 擬陽性（月）：0.5回以下
- 見逃し率：30%以下
- 平均リード：2〜7営業日（Pre-crisis Confirmから`s ≤ 0`または`carry_eff ≤ 0`まで）
- Precision（的中率）：0.7以上
- 検知後UVXYの翌1〜3営業日平均リターンが正で統計的有意

## 2. スコープ

### 対象資産と指標
- SPX（またはSPY）、VIX、VIX3M、VIX先物期近（VX1）・次限（VX2）、SKEW、HY OAS、IG OAS

### 更新頻度
- 日次EODが基本。可能なら場中60分で`s`（VX傾き）とVIX短期EWMの補助を追加。

### 出力
- 状態（Normal / Pre-crisis Watch / Pre-crisis Confirm）
- LLR（逐次検定スコア）、各カテゴリの成立状況、推定信頼度（0〜100）
- 簡易アクションガイド（検知は取引トリガではなく「警戒強化」を目的）

## 3. アーキテクチャ

### データ取得
- 価格系: Yahoo/Stooq（SPX/SPY、VIX）、Cboe（VIX、VIX3M、SKEW）
- 先物: CFE（VX1/VX2終値。TOS順守）、代替サイトの終値フォールバック
- クレジット: FRED（HY OAS、IG OAS）

### ETL・処理
- 休日・タイムゾーン整列、分割調整不要（指数中心）。欠損は保守側で扱う。
- 平滑化はEWM、標準化はローリング分位またはzスコア。

### 推定・判定
- Gate1（3カテゴリのうち2/3成立）→ Watch
- Gate2（3/3成立＋SPRT LLR ≥ A）→ Confirm
- Gate2は連続2本で確定（擬陽性抑制）。

### ストレージ・配信
- 時系列DB（PostgreSQL/TimescaleDB）または軽量CSV/Parquet
- ジョブ管理（cron/Airflow）で日次更新、アラートをメール/Slackへ

### 監査
- Pre-run log（ソース・TOS確認・レート制限・更新窓）を毎回記録

## 4. データ仕様

### 取得項目
- SPX/SPY: close, high, low, volume
- VIX, VIX3M, SKEW: index close（SKEWは日次）
- VX1, VX2: settle（終値）
- HY OAS, IG OAS: 日次が無ければ週次

### テーブル例
- `prices(date, symbol, close, high, low, volume)`
- `vix_futures(date, vx1, vx2)`
- `credit(date, hy_oas, ig_oas)`
- `indicators(date, name, value)`
- `states(date, state, llr, confidence, components_json)`
- `logs(timestamp, run_id, level, message)`

## 5. 特徴量と数式

### 平滑化
- `EWM_n(x)` with `α = 2 / (n + 1)` または半減期指定

### 標準化
- `z_t = (x_t − mean_roll) / std_roll` または分位標準化 `q_t = quantile_rank(x_t)`

### リターンと実現ボラ
- `r_SPX_t = ln(C_t / C_{t−1})`
- `RV20_t = sqrt(252) * std(r_SPX over 20)`

### ターム構造（摩擦）
- `s_t = (VX2_t − VX1_t) / VX1_t`（傾き）
- `s_flat_t = −ΔEWM(s_t)`（平坦化速度、正なら緩み）
- 一定満期インデックス近似: `w1_t = (T2 − τ) / (T2 − T1)`, `w2_t = 1 − w1_t`（`τ ≈ 30日`）
  - `I_t ≈ w1_t * VX1_t + w2_t * VX2_t`
  - `carry_eff_t ≈ Δw_t * (VX2_t − VX1_t) / I_t`（ロールの実効キャリー）
- `IVTS_t = VIX_t / VIX3M_t`（短期IV優勢で上昇）

### ボラ系（温度）
- `VRP_t = VIX_t − RV20_t`（圧縮で0〜負）
- `vvix_alt_t = EWM( (VIX_high − VIX_low) / VIX_close )` のz（VVIX代替）
- `SKEW_z_t = z(SKEW_t)`

### 信用・結合度
- `credit_raw_t = HY_OAS_t − IG_OAS_t`
- `credit_z_t = z(Δcredit_raw over 5〜10)`

### 合成カテゴリ（LLR用の3変数）
- `M_t（摩擦）` = 標準化合成 of `s_flat_t`, `carry_eff_t`, `IVTS_t`
- `T_t（温度）` = 標準化合成 of `VRP_t`, `vvix_alt_t`（SKEWは補助）
- `C_t（信用）` = `credit_z_t`

### 逐次検定（SPRT）
- 仮説: `H0 = Normal`, `H1 = PreCrisis`
- 学習で各カテゴリの分布推定（`μ0, σ0`）と（`μ1, σ1`）
- `LLR_t = Σ_{i∈{M,T,C}} [ ln NormalPDF(x_i; μ1_i, σ1_i) − ln NormalPDF(x_i; μ0_i, σ0_i) ]`
- 閾値 `A, B` の初期設定
  - `α = 0.005`（Type I error/日）, `β = 0.2`（Type II error）
  - `A ≈ ln((1−β)/α) ≈ ln(0.8/0.005) ≈ 5.08`
  - `B ≈ ln(β/(1−α)) ≈ ln(0.2/0.995) ≈ −1.61`
- 判定: `LLR_t ≥ A → Gate2`成立、`LLR_t ≤ B → H0`確定

## 6. 判定ロジック

### Gate1（Watch）
- カテゴリ成立条件（ローリング分位やzで動的閾値）
  - 摩擦: `s_flat`が上位分位（例80〜90%）または`IVTS`が上位分位、`carry_eff`が0に接近
  - 温度: `VRP`が下位分位（圧縮）または`vvix_alt`が上位分位
  - 信用: `credit_z`が上位分位（拡大初動）
- 3カテゴリのうち2つ以上が同時成立でWatch

### Gate2（Confirm）
- 3カテゴリすべて成立＋`LLR ≥ A`でConfirm
- 連続2本（2営業日）成立で確定（擬陽性抑制）

### 信頼度
- `confidence = min(1, LLR / A)` を0〜100に線形変換

### 欠損日対応
- 任意カテゴリが欠損ならGate2発火禁止（Watchのみ）

## 7. 状態機械と表示

### 状態一覧
- Normal（平常、コンタンゴ下落継続）
- Pre-crisis Watch（前兆あり、警戒）
- Pre-crisis Confirm（危機初期確度高）

### 遷移
- Normal → Watch: Gate1成立
- Watch → Confirm: Gate2成立（`LLR ≥ A`）かつ次バーも成立で確定
- Confirm → Normal: `LLR ≤ B` またはカテゴリ成立が0〜1へ後退

### 表示項目
- 現在の状態、LLR、confidence
- M/T/C各カテゴリの成立状態（オン/オフ）、しきい値に対する位置（分位値）
- 参考: `s`（傾き）、`carry_eff`、`IVTS`、`VRP`、`vvix_alt`、`credit_z`

## 8. 実装手順

- 言語/ライブラリ: Python（pandas, numpy, scipy, scikit-learn, statsmodels）
- 取得モジュール: `requests`または既存API（`yfinance`はフォールバック扱い）
- 毎日EODで SPX/SPY, VIX, VIX3M, SKEW, VX1, VX2, HY OAS, IG OAS を取得
- 欠損・遅延のログ出力、フォールバックの切替
- 時系列整列、EWM平滑化、標準化（zまたはローリング分位）
- 特徴量生成: `s, s_flat, IVTS, carry_eff, VRP, vvix_alt, credit_z`
- 合成カテゴリ `M, T, C` を算出
- 学習期間で `M/T/C` の（`μ0, σ0`）,（`μ1, σ1`）を推定
- LLR更新とGate判定: 日次で累積（独立近似で各日ごとに算出）
- Gate1/2の成立、状態遷移を決定（Gate2は連続成立が必要）
- `states`テーブルに状態・LLR・confidence・構成値を保存し、Confirm確定時のみアラート送信
- 年次でμ/σ再推定、月次でAを微調整（擬陽性が目標を超えたらAを上げる方向）

## 9. 検証計画（ウォークフォワード）

### 時間分割
- 学習: 2011–2017
- 検証: 2018–2020/2022（コロナ、金利ショック含む）

### ラベル（陽性イベント）
- 3営業日以内に `s ≤ 0` または `carry_eff ≤ 0` の到来

### 評価指標
- 擬陽性/月、見逃し率、平均リード日数、F1スコア、Precision/Recall
- 実務KPI: Confirm後のUVXYの翌1〜3日の平均リターンと分布

### 手順
- 学習期でGate1分位・SPRT A/B校正
- 検証期で毎日LLR更新、状態判定、KPI算出
- 閾値は安全側（擬陽性抑制）に調整

## 10. 機能仕様

### ダッシュボード
- 状態バッジ（Normal / Watch / Confirm）とconfidence%
- LLRのタイムライン、M/T/Cメーター（分位値、成立状況）
- 参考チャート: `s`と`carry_eff`の推移、`IVTS`、`VRP`、`credit`の推移

### アラート
- Pre-crisis Confirm確定のみ通知（連続2本成立）
- 通知内容: 状態、LLR、confidence、主要構成値、簡易コメント

### 設定
- 窓長、分位閾値、SPRT A/B、連続成立本数、欠損時ポリシー

### ログ・監査
- Pre-run log（ソース、TOS、レート、更新窓）
- 取得失敗・閾値逸脱時のアラート

## 11. パラメータ仕様（初期値と範囲）

- EWM半減期
  - `s/IVTS/VRP/vvix_alt`: 10日
  - `credit`差分: 5〜10日
- 標準化窓
  - zまたは分位の窓長: 90営業日
- Gate1分位閾値（動的）
  - `s_flat`: 上位80〜90%で成立
  - `IVTS`: 上位80〜90%
  - `VRP`: 下位10〜20%（圧縮）
  - `vvix_alt`: 上位80〜90%
  - `credit_z`: 上位80〜90%
- SPRT
  - `α = 0.005`、`β = 0.2` → `A ≈ 5.08`、`B ≈ −1.61`
  - 月次でAを微調整（擬陽性/月 ≤ 0.5に収まるよう上げ方向）
- 連続成立
  - Gate2は連続2本（2営業日）必須
- 欠損対応
  - 任意カテゴリ欠損 → Gate2発火禁止、Watchのみ記録

## 12. 数理・物理の直感可視化（任意機能）

- 障壁（B）と温度（T）の概念
  - `B ~ f(s, carry_eff)`, `T ~ g(VRP, vvix_alt, credit)`
  - 危機ハザード `h ~ exp(−B/T)`
- UIメーターでB（摩擦高）とT（温度高）を表示、`h`の色分けで直感補助

## 13. 運用ガイドライン

- 本システムは検知専用。取引判断は別層でサイズ極小・固定時間ストップ・構造ストップを徹底。
- Confirmは「警戒強化」と「ヘッジ準備」に使う（例: SPXプットの見積もり、UVXYオプションの検討）。
- 擬陽性ゼロは不可能。見逃しを許容し、安全側の設計を維持する。

## 14. 品質監視・維持管理

- 月次レポート
  - 擬陽性/月、見逃し、平均リード、F1、KPI逸脱の有無
  - 逸脱時はA上げ、分位閾値の再調整
- 年次再学習
  - `μ/σ`の再推定（レジーム変化対応）
- 障害対応
  - データ欠損時はGate2停止、ログ出力、翌日再試行

## 15. 拡張計画

- 場中補助（推奨）
  - 60分の`s`符号とVIX短期EWM（陽性継続確認に有効）
- 追加センサー
  - 金利カーブ（2s10s）、クロスカレンシーベーシス、安全通貨強弱（JPY/CHF）
- モデル高度化
  - カルマンフィルタで潜在ドリフト（キャリー）、ボラ、ジャンプ強度の同時推定
  - EVT（極値理論）でジャンプ到来閾値補正

## 16. 擬似コード（最小構成）

```text
日次ジョブ
  fetch all sources
  compute EWM and standardize
  features: s, s_flat, IVTS, carry_eff, VRP, vvix_alt, credit_z
  compose M, T, C
  if first run of period: estimate μ/σ for H0/H1 on training set
  LLR_t = sum of log-likelihood differences for M, T, C
  Gate1 = count of categories satisfied ≥ 2
  Gate2 = Gate1 == 3 and LLR_t ≥ A
  state transition with consecutive requirement
  save state, LLR, confidence, components; alert on Confirm

欠損・フォールバック
  missing category → Gate2 disabled; log warning
```

## 17. 注意事項・法務

- 公式API/静的CSVを優先。スクレイピングはTOS・robots.txt順守、レート制限を実装。
- 本システムの出力は投資助言ではない。運用は限定損失を前提に自己責任で。

## 18. まとめ

- コンタンゴ下落の「摩擦」が緩み、ボラの「温度」が上がり、信用の「結合度」が高まる——この3系統の独立センサーの同時合意とSPRTの持続確認で、暴落前の反転初期を擬陽性ほぼゼロで抽出することは実務的に可能。
- 設計の肝は、分位ベースの動的閾値、3カテゴリの縮減合成、SPRT閾値の安全側校正、連続成立によるダメ押し。
- まずはこの最小構成で実装・検証し、月次でKPIを監視しながら安全方向に調整する。場中補助を足せば検知の鮮度と確度がさらに向上する。
