# `hyperparameters` 仕様（Worker）

`CreateExperimentRequest.hyperparameters`（自由形式の JSON オブジェクト）のうち、Worker が実際に参照するキーの仕様。
ここに記載のないキーは Worker では参照されず、**エラーにもならずに無視される**（キー名の誤記に注意）。

`CreateExperimentRequest.watermark`（トップレベル）は Worker では参照しない。装飾は `hyperparameters` のみで指定する。

---

## キー一覧

| キー | 型 | 既定値 | 対象手法 | 参照箇所 |
| ---- | -- | ------ | -------- | -------- |
| `target_train_decoration` | 装飾オブジェクト | なし（装飾しない） | 全手法（LF_MIA 系は**必須**） | `data/decorations/config.py`, `dataset.get_target_dataloaders`, `LF_MIA.train_target_model` |
| `eval_decoration` | 装飾オブジェクト | なし | `OfflineLira` / `OnlineLira` / `Shokri` | `dataset.get_eval_target_dataloaders` / `get_eval_shadow_dataloader` / `get_eval_decorated_sample` |
| `shadow_decoration` | 装飾オブジェクト | なし | LF_MIA 系 | `dataset.get_shadow_dataloader(decoration_spec=)`, `LF_MIA.train_shadow_models` |
| `shadow_fraction_sweep` | bool（`true` / `false`。文字列も可） | `false` | LF_MIA 系 | `attacks/shadow_fraction_sweep.py`, `LF_MIA.train_shadow_models` |
| `attack_decoration` | 装飾オブジェクト（`watermark` のみ） | なし | LF_MIA 系（**必須**） | `dataset.get_attack_watermark_dataloader` / `get_attack_composite_dataloaders` |
| `attack_num_images` | int (>= 1) | なし | `LfMultMia` / `LfMultDiffMia`（**必須**） | `LF_Mult_MIA._num_images` |
| `membership_scorer` | str | `neural` | LF_MIA 系 | `attacks/membership_scorers/__init__.py` |
| `significant_class_selection` | str | `none` | LF_MIA 系（`diagonal_lda` / `flat_diagonal_lda` / `gaussian_lr`） | `attacks/membership_scorers/class_selection.py` |
| `attack_model_batch_size` | int | `64`（`cfg.ATTACK_MODEL_BATCH_SIZE`） | LF_MIA 系（`membership_scorer=neural` / `neural_regularized`） | 同上 |
| `attack_model_epochs` | int | `100`（`cfg.ATTACK_MODEL_EPOCHS`） | LF_MIA 系（`membership_scorer=neural`） | 同上 |
| `cv_objective` | str | `auc` | LF_MIA 系（`neural_regularized` / `lightgbm` / `svm` / `flat_svm`） | `attacks/membership_scorers/pair_cv.py` |
| `cv_n_folds` | int (>= 2, <= n_pairs) | `10` | 同上 | 同上 |
| `cv_val_ratio` | float (0 < x < 1) | `0.2` | 同上 | 同上 |
| `cv_n_trials` | int (>= 1) | `50` | 同上 | 同上 |
| `cv_stability_lambda` | float (>= 0) | `0.5` | 同上 | 同上 |
| `neural_regularized_patience` | int (>= 1) | `20` | LF_MIA 系（`neural_regularized`） | `attacks/membership_scorers/neural_regularized.py` |
| `neural_regularized_max_epochs` | int (>= 1) | `500` | 同上 | 同上 |
| `neural_regularized_standardize` | bool（`true` / `false`。文字列も可） | `true` | 同上 | 同上 |
| `lightgbm_patience` | int (>= 1) | `50` | LF_MIA 系（`lightgbm`） | `attacks/membership_scorers/lightgbm_scorer.py` |
| `lightgbm_max_rounds` | int (>= 1) | `1000` | 同上 | 同上 |
| `svm_kernel` | str | `linear` | LF_MIA 系（`svm`） | `attacks/membership_scorers/svm_scorer.py` |
| `svm_standardize` | bool（`true` / `false`。文字列も可） | `true` | 同上 | 同上 |
| `svm_rbf_n_components` | int (>= 1) | `1000` | 同上（`svm_kernel=rbf`） | 同上 |
| `svm_max_iter` | int (>= 1) | `10000` | 同上 | 同上 |
| `flat_svm_kernel` | str | `linear` | LF_MIA 系（`flat_svm`） | `attacks/membership_scorers/flat_svm_scorer.py` |
| `flat_svm_standardize` | bool（`true` / `false`。文字列も可） | `true` | 同上 | 同上 |
| `diagonal_lda_reg_lambda` | float | `1e-3` | LF_MIA 系（`diagonal_lda` / `flat_diagonal_lda`） | 同上 |
| `diagonal_lda_variance` | str | `pair_diff` | LF_MIA 系（`diagonal_lda`） | 同上 |
| `flat_diagonal_lda_variance` | str | `within_class` | LF_MIA 系（`flat_diagonal_lda`） | 同上 |
| `gaussian_lr_variance` | str | `per_class` | LF_MIA 系（`gaussian_lr`） | 同上 |
| `gaussian_lr_var_floor` | float (> 0) | `1e-3` | LF_MIA 系（`gaussian_lr`） | 同上 |

LF_MIA 系 = `LfMia` / `LfMultMia` / `LfMultDiffMia`。

### 手法ごとの要否

| キー | `OfflineLira` | `OnlineLira` | `Shokri` | `LfMia` | `LfMultMia` / `LfMultDiffMia` |
| ---- | :-----------: | :----------: | :------: | :-----: | :---------------------------: |
| `target_train_decoration` | 任意 | 任意 | 任意 | 必須 | 必須 |
| `eval_decoration` | 任意 | 任意 | 任意 | 不使用 | 不使用 |
| `shadow_decoration` | 不使用 | 不使用 | 不使用 | 実質必須 | 実質必須 |
| `attack_decoration` | 不使用 | 不使用 | 不使用 | 必須 | 必須 |
| `attack_num_images` | 不使用 | 不使用 | 不使用 | 不使用 | 必須 |
| `shadow_fraction_sweep` | 不使用 | 不使用 | 不使用 | 任意 | 任意 |
| membership scorer 系 | 不使用 | 不使用 | 不使用 | 任意 | 任意 |

「実質必須」: 未指定でもエラーにはならないが、IN シャドーが装飾なしで学習され IN / OUT シャドーが区別できなくなる（下記「注意事項」）。

`Shokri` の攻撃モデルのエポック数は `cfg.ATTACK_MODEL_EPOCHS` 固定であり、`attack_model_epochs` は参照しない。

---

## 装飾オブジェクト

`*_decoration` キーの値。単一のオブジェクトで指定する（配列は `ValueError`）。`null` / 省略時は装飾しない。

### 共通フィールド

| フィールド | 型 | 既定値 | 制約 | 意味 |
| ---------- | -- | ------ | ---- | ---- |
| `type` | str | なし（必須） | `watermark` / `display_mask` | 装飾の種類。それ以外は `ValueError` |
| `fraction` | float | `1.0` | `0.0 <= fraction <= 1.0` | 対象データのうち装飾を適用する割合 |
| `seed_offset` | int | `0` | — | 適用サンプル選定の乱数シードのオフセット |

適用サンプルの選定は `train_test_split(pool, train_size=fraction, random_state=seed + seed_offset)` で行う（`data/decorations/apply_policy.py`）。

- `fraction <= 0.0` のときは装飾しない。`fraction >= 1.0` のときは全件に適用する。
- 同じ `fraction` / `seed_offset` / 対象データであれば、`type` が異なっても同じサンプルが選ばれる。
- `fraction` / `seed_offset` はオブジェクトの直下に書く（`apply` などでネストしない）。

### `type: "watermark"`

| フィールド | 型 | 既定値 | 制約 | 意味 |
| ---------- | -- | ------ | ---- | ---- |
| `filter_id` | str | なし（必須） | 空文字不可 | MinIO `filters/{filter_id}.png` の透かしフィルタ。RGBA の alpha で元画像にブレンドする |

### `type: "display_mask"`

指定矩形の外側を黒で塗りつぶす（画像左上が原点）。

| フィールド | 型 | 既定値 | 制約 | 意味 |
| ---------- | -- | ------ | ---- | ---- |
| `width` | int | `16` | `1..32` | 表示領域の幅 |
| `height` | int | `16` | `1..32` | 表示領域の高さ |
| `position` | `[x, y]` または `{"x": x, "y": y}` | — | `0..31` | 表示領域の左上座標 |
| `x` / `y` | int | `0` | `0..31` | `position` を省略したときの左上座標 |

`x + width <= 32` かつ `y + height <= 32` を満たさない場合は `ValueError`（デコレータ生成時に検証）。`position` と `x` / `y` の両方がある場合は `position` を優先する。

### 各キーの適用先

| キー | 適用先 |
| ---- | ------ |
| `target_train_decoration` | ターゲットモデルの**学習データ**（`target_train_idx`）。ターゲットのテストデータには適用しない。LF_MIA 系では種類（`filter_id` 等）のベースとして使い、`fraction` は `LF_MIA_TARGET_FRACTIONS`（`1.0` から `0.001`、および `0.0` × 12）で上書きされる。指定した `fraction` は使われない |
| `eval_decoration` | LiRA / Shokri の評価・特徴抽出時のクエリデータ（ターゲットの学習データ・テストデータ）と、Shokri のシャドー評価データ。`OfflineLira` / `OnlineLira` のサンプル可視化の画像にも使う |
| `shadow_decoration` | LF_MIA 系の **IN シャドー**の学習データとテストデータ。OUT シャドーには適用しない。`shadow_fraction_sweep=true` のときは種類（`filter_id` 等）と `seed_offset` のベースとして使い、`fraction` は IN シャドーごとの適用率で上書きされる |
| `attack_decoration` | LF_MIA 系の攻撃プローブ。`LfMia` は黒背景に透かしを合成した 1 枚、`LfMultMia` / `LfMultDiffMia` はターゲットのテスト画像 K 枚に透かしを合成したもの。`filter_id` のみを使い、`fraction` / `seed_offset` は使わない。`display_mask` を指定すると `ValueError` |

各装飾の見た目は `work_dir/decoration_preview.png`（左から plain / target / eval / shadow / attack）で確認できる。プレビューは `fraction` に関係なく装飾を適用して描画する。

---

## LF_MIA 系の攻撃設定

### `attack_num_images`

`LfMultMia` / `LfMultDiffMia` で、透かしを合成するターゲットのテスト画像の枚数 K。`RandomState(seed)` でターゲットのテストデータから非復元抽出する。

- `1 <= K <= target_test_size` を満たさない場合は `ValueError`。
- `config.py` に既定値はない。

### `shadow_fraction_sweep`

IN シャドーの装飾適用率を複数段階に振るモード。ターゲットは適用率 `1.0`〜`0.001` で学習されるため、IN シャドーも適用率を振ることで、scorer が「適用率が 1.0 でない IN」も学習できるようにする。

| 値 | 挙動 |
| -- | ---- |
| `false`（既定） | 全 IN シャドーに `shadow_decoration.fraction` をそのまま使う（従来どおり） |
| `true` | ペア i（IN シャドー i と OUT シャドー i）の IN シャドーに、適用率 `[1.0, 0.9, ..., 0.1][i % 10]` を割り当てる。各段階のペア数は同数（`n_pairs / 10`） |

- `true` のとき、ペア数 `n_pairs = num_shadow_models / 2` が 10 の倍数（`num_shadow_models` が 20 の倍数）でなければ `ValueError`。`shadow_decoration` が未指定でも `ValueError`。
- `true` のとき、`shadow_decoration.fraction` は使われない（`filter_id` / `seed_offset` 等は使う）。
- scorer の学習ラベルは適用率によらず IN=1 / OUT=0。適用率は CV 探索の分割の層化に使う（下記「CV 探索の共通設定」）。
- `true` / `false`（文字列は大文字小文字を問わない）以外は `ValueError`。
- 適用率は設定から決定的に求めるため、`load_shadow_model` でシャドーを読み込む場合も、学習時と同じ設定を指定すれば同じ値になる。

metrics:

| キー | 意味・解説 |
| ---- | ---------- |
| `shadow_fraction_sweep` | このモードの有無 |
| `shadow_in_fractions` | IN シャドーごとの装飾適用率（長さ `n_pairs` のリスト。i 番目が IN シャドー i）。無効時は全要素が `shadow_decoration.fraction`（未指定なら `0.0`） |

### membership scorer

LF_MIA 系の攻撃モデル。詳細は `SPECIFICATION.md` の「Membership scorer」を参照。

| `membership_scorer` | 手法 | 使用するキー | スコアのスケール |
| ------------------- | ---- | ------------ | ---------------- |
| `neural` | `AttackNet` で画像ごとに IN/OUT を分類し、IN 確率を平均する | `attack_model_batch_size`, `attack_model_epochs` | `probability` |
| `neural_regularized` | 1 出力 MLP をペア単位 k-fold CV + 早期停止 + Optuna で探索し、最良 trial の fold モデルのアンサンブルで画像ごとの IN 確率を平均する | `attack_model_batch_size`, `cv_*`, `neural_regularized_*` | `probability` |
| `lightgbm` | 画像単位の LightGBM をペア単位 k-fold CV + 早期停止 + Optuna で探索し、最良 trial の fold モデルのアンサンブルで画像ごとの IN 確率を平均する | `cv_*`, `lightgbm_*` | `probability` |
| `svm` | 画像単位の SVM（linear / Nystroem 近似の rbf）をペア単位 k-fold CV + validation での Platt 較正 + Optuna で探索し、最良 trial の fold モデルのアンサンブルで画像ごとの IN 確率を平均する | `cv_*`, `svm_*` | `probability` |
| `flat_svm` | シャドーの特徴を `(K·C)` に平坦化した SVM（linear / rbf の厳密な SVC）をペア単位 k-fold CV + validation での Platt 較正 + Optuna で探索し、最良 trial の fold モデルのアンサンブルでターゲット単位の IN 確率を出す | `cv_*`, `flat_svm_*` | `probability` |
| `diagonal_lda` | K 枚を平均した特徴に対する対角 LDA（分母は既定でペア差分の分散） | `diagonal_lda_reg_lambda`, `diagonal_lda_variance`, `significant_class_selection` | `log_odds` |
| `flat_diagonal_lda` | `(K·C)` に平坦化した対角 LDA | `diagonal_lda_reg_lambda`, `flat_diagonal_lda_variance`, `significant_class_selection` | `log_odds` |
| `gaussian_lr` | (k, c) ごとの正規分布による尤度比検定 | `gaussian_lr_variance`, `gaussian_lr_var_floor`, `significant_class_selection` | `log_odds` |

| キー | 取り得る値 | 意味 |
| ---- | ---------- | ---- |
| `significant_class_selection` | `none`（既定） | 全クラスを使う |
| | `bh_fdr` | shadow_pair 分析で BH-FDR 有意なクラスのみ使う（`alpha=0.05`）。`flat_diagonal_lda` / `gaussian_lr` ではクラス c が有意なら全画像 k の `(k, c)` を使う。有意クラスが 0 件なら警告を出して全クラスを使う |
| | `bonferroni` | 同上で、判定を Bonferroni にする |
| `flat_diagonal_lda_variance` | `within_class`（既定） | 重みの分母を IN / OUT のクラス内分散のプールにする。データの異なる単体モデルに汎化させる場合の標準 |
| | `pair_diff` | 重みの分母をペア差分 IN−OUT の分散にする。データ分割由来の分散がペア内で相殺される |
| | `none` | 分散で割らず、重みを IN / OUT の平均差そのものにする。`diagonal_lda_reg_lambda` は使わない |
| `diagonal_lda_variance` | `pair_diff`（既定） / `within_class` / `none` | `flat_diagonal_lda_variance` と同じ意味（既定のみ異なる） |
| `gaussian_lr_variance` | `per_class`（既定） | IN / OUT で別々の分散を使う |
| | `pooled` | IN / OUT の分散の平均を共通に使う（シャドーが少ないとき向け） |
| `svm_kernel` | `linear`（既定） | `LinearSVC` による線形 SVM |
| | `rbf` | `Nystroem` 近似の RBF 特徴写像 + `LinearSVC`。厳密な RBF-SVC は学習サンプル数 n に対して O(n²)〜O(n³) のため近似を使う |
| `cv_objective` | `auc`（既定） | シャドー単位（K 枚の IN 確率平均）の AUC。CV の fold 指標と早期停止の監視に使う |
| | `tpr_at_1_fpr` | 画像単位の TPR@FPR=0.01。テスト fold・validation の OUT 画像数（ペア数 × K）が 100 以上必要（満たさない場合 `ValueError`） |

- 文字列の値は前後の空白を除き、小文字に正規化してから解釈する。取り得る値以外は `ValueError`。
- スコアのスケールは metrics の `membership_score_scale` に出力され、`attack_score` / `threshold_at_*` の単位を表す。
- 以下の「metrics」は、各 scorer が metrics に追加するキー（スコアラーの diagnostics）。全 scorer 共通で `membership_scorer`（scorer 名）と `membership_score_scale` も出力される。

#### CV 探索の共通設定（`neural_regularized` / `lightgbm` / `svm` / `flat_svm`）

シャドー IN/OUT ペアを単位に k-fold CV を行い、fold 指標の `mean − λ·std` を Optuna（TPE + MedianPruner）で最大化する。各 fold の学習側ペアの一部を validation に回して早期停止し（`svm` / `flat_svm` は早期停止の代わりに Platt 較正に使う）、最良 trial の k 個の fold モデルの IN 確率の平均でターゲットを推論する。

IN シャドーの適用率が複数ある場合（`shadow_fraction_sweep=true`）は、テスト fold と validation を適用率で層化する。適用率の段階ごとのペア数が `cv_n_folds` より少なくてもエラーにはせず、各 fold に段階ができるだけ散らばるように割り当てる（例: 20 ペア・k=10 では、各テスト fold は異なる 2 段階のペアで構成される）。適用率が 1 種類のときは従来の分割と完全に同じ。各 fold のペアの適用率は `folds.json` の `train_fractions` / `val_fractions` / `test_fractions` に記録される。

ハイパーパラメータ:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `cv_objective` | `auc` | fold 指標・早期停止で最大化する指標（上表）。ターゲットの評価で重視する指標に合わせる |
| `cv_n_folds` | `10` | シャドーペア単位の k-fold の k。`n_pairs`（`num_shadow_models / 2`）を超えると `ValueError`。大きいほど学習側が増えるが、テスト fold が小さくなり fold 指標の分散が増える |
| `cv_val_ratio` | `0.2` | 各 fold の学習側ペアのうち早期停止用 validation に回す割合（最低 1 ペア、学習側に最低 1 ペア残す） |
| `cv_n_trials` | `50` | Optuna の試行回数。1 trial = k fold 分の学習。途中の fold 平均が過去 trial の中央値を下回ると枝刈りされる（最初の 5 trial と fold 0 は対象外） |
| `cv_stability_lambda` | `0.5` | trial のスコア `mean − λ·std` の λ。大きいほど fold 間のばらつきが小さい（未知のターゲットに安定な）設定を優先する |

metrics:

| キー | 意味・解説 |
| ---- | ---------- |
| `cv_objective` | 使用した目的指標 |
| `cv_score` | 最良 trial の `mean − λ·std`。最良 trial を選んだ値そのものなので選択バイアスで楽観側に偏る（診断値として扱う） |
| `cv_fold_mean` / `cv_fold_std` | 最良 trial の fold 指標の平均 / 母標準偏差 |
| `best_trial_number` | 最良 trial の番号（`trials.csv` の行と対応） |
| `n_trials_completed` / `n_trials_pruned` | 完了した trial 数 / 枝刈りされた trial 数 |

#### `neural`

`AttackNet`（C → 64 → 2）で画像ごとに IN/OUT を分類し、K 枚の IN 確率を平均する。全シャドーで学習し、検証データを持たない。

ハイパーパラメータ:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `attack_model_batch_size` | `64` | ミニバッチサイズ |
| `attack_model_epochs` | `100` | 学習 epoch 数（早期停止なし） |

metrics:

| キー | 意味・解説 |
| ---- | ---------- |
| `w1_relative_change` | 第 1 層重みの相対変化量 `‖ΔW1‖ / ‖W1_init‖`。1 を大きく下回るなら、学習で得た成分が初期化ノイズに埋もれている |
| `attack_model_train_acc` / `attack_model_train_loss` | 学習データ上の正解率 / 平均 cross entropy。学習データでの値なので汎化性能ではない |
| `attack_model_train_in_acc` / `attack_model_train_out_acc` | 学習データ上の IN / OUT 別の正解率。片方だけ高い場合は一方のクラスへの偏りを示す |

#### `neural_regularized`

1 出力 MLP（`BinaryAttackNet`）を CV 探索の共通設定（上記）で探索する。各 fold は AdamW + `BCEWithLogitsLoss` で学習し、validation の目的指標（同値時は validation BCE が小さい方）で早期停止して best の重みを復元する。

ハイパーパラメータ（`cv_*` に加えて）:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `attack_model_batch_size` | `64` | ミニバッチサイズ |
| `neural_regularized_patience` | `20` | validation の目的指標が改善しないまま許容する epoch 数 |
| `neural_regularized_max_epochs` | `500` | epoch の上限 |
| `neural_regularized_standardize` | `true` | `true` で各 fold の学習側で fit した z-score 標準化を入力に適用する。`false` では生の特徴を入力する（`true` / `false` 以外は `ValueError`） |

探索空間（コード定数で固定）:

| パラメータ | 範囲 | 意味 |
| ---------- | ---- | ---- |
| `lr` | 1e-5〜1e-3（log） | AdamW の学習率 |
| `weight_decay` | 1e-5〜1e-1（log） | AdamW の重み減衰（L2 正則化） |
| `n_hidden` | {0, 1} | 隠れ層数。0 はロジスティック回帰と同じ線形モデル |
| `hidden_dim` | 8〜128（log） | 隠れ層の幅（`n_hidden=1` のみ） |
| `dropout` | 0〜0.5 | 隠れ層の dropout 率（`n_hidden=1` のみ） |

metrics（CV 共通の metrics に加えて）:

| キー | 意味・解説 |
| ---- | ---------- |
| `standardize` | 標準化の有無 |
| `best_lr` / `best_weight_decay` / `best_n_hidden` / `best_hidden_dim` / `best_dropout` | 最良 trial のハイパーパラメータ。`best_hidden_dim` は 0 層時 `null` |
| `best_epoch_median` | 最良 trial の各 fold で早期停止が採用した epoch 数の中央値。`neural_regularized_max_epochs` に近いなら上限で打ち切られており、上限か学習率を上げる余地がある |

#### `lightgbm`

画像単位（特徴 C 次元）の LightGBM 二値分類を CV 探索の共通設定（上記）で探索する。各 fold は validation の目的指標（同値時は validation logloss が小さい方）で早期停止し、best のラウンドまでの木で推論する。木モデルは特徴の単調変換で分割が変わらないため、標準化は行わない。

ハイパーパラメータ（`cv_*` に加えて）:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `lightgbm_patience` | `50` | validation の目的指標が改善しないまま許容するブースティングラウンド数 |
| `lightgbm_max_rounds` | `1000` | ブースティングラウンド（木の本数）の上限。実際の本数は早期停止で決まるため、`n_estimators` は探索しない |

探索空間（コード定数で固定）:

| パラメータ | 範囲 | 意味 |
| ---------- | ---- | ---- |
| `learning_rate` | 1e-3〜0.3（log） | 各木の寄与の縮小率。小さいほど必要なラウンド数が増え、汎化しやすい |
| `num_leaves` | 4〜64（log） | 1 本の木の葉の数の上限。モデルの複雑さを決める主要パラメータ |
| `limit_depth` / `max_depth` | {False, True} / 3〜8 | 木の深さを制限するか / 制限時の深さ上限。False では無制限（`-1`） |
| `min_child_samples` | 5〜100（log） | 1 つの葉に必要な最小サンプル（画像）数。大きいほど過学習を抑える。同一シャドーの K 枚は独立でないため、実効サンプル数より楽観的に効く点に注意 |
| `feature_fraction` | 0.3〜1.0 | 各木で使う特徴（クラス次元）の割合 |
| `bagging_fraction` | 0.5〜1.0 | 各ラウンドで使うサンプルの割合（非復元抽出）。`bagging_freq=1` 固定で毎ラウンド再抽出する |
| `lambda_l1` / `lambda_l2` | 1e-8〜10（log） | 葉の値に対する L1 / L2 正則化 |

固定値: `objective=binary`, `bagging_freq=1`, `deterministic=True`, `force_col_wise=True`（同じ seed で結果を再現させるため）。

metrics（CV 共通の metrics に加えて）:

| キー | 意味・解説 |
| ---- | ---------- |
| `best_learning_rate` / `best_num_leaves` / `best_max_depth` / `best_min_child_samples` / `best_feature_fraction` / `best_bagging_fraction` / `best_lambda_l1` / `best_lambda_l2` | 最良 trial のハイパーパラメータ。`best_max_depth` は深さ無制限のとき `-1` |
| `best_iteration_median` | 最良 trial の各 fold で早期停止が採用したラウンド数の中央値。`lightgbm_max_rounds` に近いなら上限で打ち切られている。極端に小さい（数ラウンド）なら、少数の木ですぐ validation に過適合している |

#### `svm`

画像単位（特徴 C 次元）の SVM 二値分類を CV 探索の共通設定（上記）で探索する。各 fold は `Pipeline(StandardScaler | 恒等変換, Nystroem | なし, LinearSVC)` を学習側ペアで学習し、学習済みモデルは固定したまま、validation ペアの `decision_function` で Platt scaling（`svm_common.PlattScaling`。IN の logit = `a·f + b`）を学習して IN 確率を得る。早期停止は行わない。

Platt scaling は Platt (1999) の目標値の平滑化（正例 `(N₊+1)/(N₊+2)`、負例 `1/(N₋+2)`）付きの交差エントロピー最小化で、sklearn の `CalibratedClassifierCV(method="sigmoid")` と同じ手法。較正後の logit を可視化に使うため自前で実装している。

ハイパーパラメータ（`cv_*` に加えて）:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `svm_kernel` | `linear` | カーネル（上表） |
| `svm_standardize` | `true` | `true` で各 fold の学習側で fit した z-score 標準化を入力に適用する。SVM は特徴のスケールに敏感なため、通常は `true` のままにする（`true` / `false` 以外は `ValueError`） |
| `svm_rbf_n_components` | `1000` | `rbf` の Nystroem 近似の次元数（探索しない）。大きいほど厳密な RBF に近づくが、学習時間とメモリが増える。学習サンプル数を超える場合は学習サンプル数に切り詰める |
| `svm_max_iter` | `10000` | `LinearSVC` のソルバの反復上限。不足すると `ConvergenceWarning` が出る |

探索空間（コード定数で固定）:

| パラメータ | 範囲 | 意味 |
| ---------- | ---- | ---- |
| `C` | 1e-4〜1e2（log） | 誤分類のペナルティ。小さいほど正則化が強い |
| `gamma_factor` | 1e-3〜1e2（log） | `rbf` のみ。RBF の `gamma = gamma_factor / (n_features · X.var())`。基準値は sklearn の `gamma="scale"` と同じで、標準化後（`svm_standardize=false` では生）の学習側特徴から fold ごとに計算する |

metrics（CV 共通の metrics に加えて）:

| キー | 意味・解説 |
| ---- | ---------- |
| `svm_kernel` | 使用したカーネル |
| `standardize` | 標準化の有無 |
| `best_C` / `best_gamma_factor` | 最良 trial のハイパーパラメータ。`best_gamma_factor` は `linear` のとき `null` |

注意: Platt 較正は validation ペアのみで行うため、`cv_val_ratio` が小さいと較正パラメータの推定がばらつく。

#### `flat_svm`

シャドーの特徴 `(K, C)` を `K·C` 次元に平坦化して 1 サンプルとする（サンプル数 `n_pairs × 2`）SVM 二値分類を CV 探索の共通設定（上記）で探索する。`flat_diagonal_lda` と同じく画像間の (k, c) の組み合わせを直接学習する。サンプル数が少ないため近似を使わず、各 fold は `Pipeline(StandardScaler | 恒等変換, SVC(kernel=linear | rbf))` を学習側ペアで学習し、validation ペアで Platt 較正する（`svm` と同じ）。

ハイパーパラメータ（`cv_*` に加えて）:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `flat_svm_kernel` | `linear` | `linear`: `SVC(kernel="linear")` / `rbf`: `SVC(kernel="rbf")`（それ以外の値は `ValueError`） |
| `flat_svm_standardize` | `true` | `svm_standardize` と同じ |

探索空間は `svm` と同じ（`C` / `gamma_factor`。`gamma` の基準値は `K·C` 次元の学習側特徴から計算する）。

metrics（CV 共通の metrics に加えて）:

| キー | 意味・解説 |
| ---- | ---------- |
| `flat_svm_kernel` | 使用したカーネル |
| `standardize` | 標準化の有無 |
| `best_C` / `best_gamma_factor` | 最良 trial のハイパーパラメータ。`best_gamma_factor` は `linear` のとき `null` |

注意:
- 入力次元 `K·C`（例: K=20, C=100 で 2000）に対してサンプル数が `n_pairs × 2` と少ない（p ≫ n）。linear はほぼ確実に完全分離でき、`C` は「IN/OUT 平均差に近い解（小さい C）」と「最大マージン解（大きい C）」の間を動かす。
- テスト fold が小さいため fold 指標のノイズが大きく、`cv_n_trials` を大きくすると選択バイアスが増える。小さめに設定する。
- `cv_objective=tpr_at_1_fpr` はテスト fold・validation に OUT シャドーが 100 以上必要で、通常の設定では `ValueError` になる。
- `per_image` はターゲット単位の値を K 個並べたもの。`attack_scores_vars` は常に 0、`roc_curve_all_scores` / `attack_score_distribution` はターゲット単位と同じ情報になる。

#### `svm` / `flat_svm` の可視化（`svm_decision_analysis/`）

学習済みモデルを `svm_decision_analysis/` に可視化する。単位は `svm` が画像（シャドー `n_pairs·2·K` 点、ターゲット `24·K` 点）、`flat_svm` がシャドー / ターゲット（`n_pairs·2` 点、24 点）。

| ファイル | 内容 |
| -------- | ---- |
| `pca_scatter.png` | シャドー全体で fit した z-score 標準化 + PCA(2) の平面にシャドー IN / OUT を描き、ターゲットを同じ変換で射影して重ねる（IN は適用率を対数カラーマップ、OUT は青の三角） |
| `decision_histogram.png` | Platt 較正後の logit の分布。シャドーは out-of-fold（そのペアがテストだった fold のモデル）の値、ターゲットは k 個の fold モデルの logit の平均。ターゲットの個々の値は下端の目盛りで示す |
| `summary.json` | `pca_explained_variance_ratio`、`shadow_oof_auc`（シャドーの OOF logit による AUC。単位は上記）、群（shadow_in / shadow_out / target_in / target_out）ごとの logit の `n` / `mean` / `std` |

- PCA は線形の 2 次元射影なので、RBF の判別境界や高次元での分離はこの平面に現れないことがある。
- ターゲットの logit（fold の logit の平均）は、`attack_score`（fold の確率の平均）と厳密には一致しない。
- シャドーの OOF logit が 0 付近に集中する fold は、validation で信号が見つからず Platt の傾き `a` がほぼ 0 になったことを示す。

#### `diagonal_lda`

K 枚を平均した特徴 `(C,)` に対する対角 LDA。クラス次元間の相関を無視し、次元ごとに `(IN 平均 − OUT 平均) / 分散` を重みとする線形判別。

ハイパーパラメータ:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `diagonal_lda_variance` | `pair_diff` | 重みの分母（取り得る値は上表） |
| `diagonal_lda_reg_lambda` | `1e-3` | 分散に加える正則化項。分散が 0 に近い次元で重みが発散するのを防ぐ（`variance=none` では不使用） |
| `significant_class_selection` | `none` | 使うクラスの選択（上表） |

metrics:

| キー | 意味・解説 |
| ---- | ---------- |
| `diagonal_lda_reg_lambda` / `diagonal_lda_variance` | 使用した設定 |
| `diagonal_lda_w_norm` | 重みベクトルの L2 ノルム。IN/OUT の平均差が分散に対して大きいほど大きい |
| `diagonal_lda_b` | バイアス。IN/OUT の平均の中点で logit が 0 になるように決まる |
| クラス選択の共通キー | 下記 |

#### `flat_diagonal_lda`

`(K·C)` に平坦化した特徴に対する対角 LDA。画像 k ごと・クラス c ごとに独立な重みを持ち、画像ごとの寄与 `w_k·x_k + b/K` の和をスコアとする。

ハイパーパラメータ:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `flat_diagonal_lda_variance` | `within_class` | 重みの分母（取り得る値は上表） |
| `diagonal_lda_reg_lambda` | `1e-3` | `diagonal_lda` と共用の正則化項 |
| `significant_class_selection` | `none` | 使うクラスの選択（上表） |

metrics:

| キー | 意味・解説 |
| ---- | ---------- |
| `flat_diagonal_lda_reg_lambda` / `flat_diagonal_lda_variance` | 使用した設定 |
| `flat_diagonal_lda_w_norm` / `flat_diagonal_lda_b` | 重み全体の L2 ノルム / バイアス |
| `flat_diagonal_lda_w_norm_per_image` | 画像ごとの重みノルム（K 要素のリスト）。どの画像の特徴がスコアに効いているかを示す |
| クラス選択の共通キー | 下記 |

#### `gaussian_lr`

(k, c) ごとに IN / OUT の特徴を正規分布で近似し、対数尤度比の和をスコアとする（LiRA の拡張）。次元間の相関を無視するため、`|value|` は K·C に比例して大きくなる（順位付けにのみ用いる）。

ハイパーパラメータ:

| キー | 既定値 | 意味・解説 |
| ---- | ------ | ---------- |
| `gaussian_lr_variance` | `per_class` | IN/OUT で分散を分けるか（取り得る値は上表） |
| `gaussian_lr_var_floor` | `1e-3` | 分散の下限。logit が全モデルで飽和して分散 0 になる次元で尤度比が発散するのを防ぐ |
| `significant_class_selection` | `none` | 使うクラスの選択（上表） |

metrics:

| キー | 意味・解説 |
| ---- | ---------- |
| `gaussian_lr_variance` / `gaussian_lr_var_floor` | 使用した設定 |
| `gaussian_lr_floored_ratio_in` / `gaussian_lr_floored_ratio_out` | IN / OUT の分散が下限に張り付いた次元の割合（クラス選択に依らず全次元で算出）。高いと特徴が飽和しており、尤度比が下限値に支配される |
| クラス選択の共通キー | 下記 |

#### クラス選択の共通 metrics（`diagonal_lda` / `flat_diagonal_lda` / `gaussian_lr`）

| キー | 意味・解説 |
| ---- | ---------- |
| `significant_class_selection` | 使用した選択方法 |
| `num_selected_classes` | 使ったクラス数 |
| `class_selection_fallback` | 有意クラスが 0 件だったため全クラスに戻したか（`n_pairs < 6` で p 値が出ない場合を含む） |

---

## 設定例

### `LfMultMia` + `gaussian_lr`

```json
{
  "target_train_decoration": {"type": "watermark", "filter_id": "circle"},
  "shadow_decoration": {"type": "watermark", "filter_id": "circle", "fraction": 1.0},
  "attack_decoration": {"type": "watermark", "filter_id": "circle"},
  "attack_num_images": 100,
  "membership_scorer": "gaussian_lr",
  "gaussian_lr_variance": "per_class",
  "gaussian_lr_var_floor": 1e-3
}
```

### `LfMultMia` + `neural_regularized`

```json
{
  "target_train_decoration": {"type": "watermark", "filter_id": "circle"},
  "shadow_decoration": {"type": "watermark", "filter_id": "circle", "fraction": 1.0},
  "attack_decoration": {"type": "watermark", "filter_id": "circle"},
  "attack_num_images": 100,
  "membership_scorer": "neural_regularized",
  "cv_objective": "tpr_at_1_fpr",
  "cv_n_trials": 50,
  "cv_stability_lambda": 0.5
}
```

### `LfMultMia` + `lightgbm` + IN シャドーの適用率スイープ

`num_shadow_models` は 20 の倍数にする。

```json
{
  "target_train_decoration": {"type": "watermark", "filter_id": "circle"},
  "shadow_decoration": {"type": "watermark", "filter_id": "circle"},
  "shadow_fraction_sweep": true,
  "attack_decoration": {"type": "watermark", "filter_id": "circle"},
  "attack_num_images": 100,
  "membership_scorer": "lightgbm",
  "cv_objective": "auc",
  "cv_n_trials": 50,
  "lightgbm_patience": 50,
  "lightgbm_max_rounds": 1000
}
```

### `OfflineLira` + 学習データの一部を部分表示

```json
{
  "target_train_decoration": {
    "type": "display_mask",
    "width": 16, "height": 16, "position": [0, 0],
    "fraction": 0.5, "seed_offset": 0
  },
  "eval_decoration": {
    "type": "display_mask",
    "width": 16, "height": 16, "position": [0, 0],
    "fraction": 1.0
  }
}
```

---

## 注意事項（現行実装の挙動）

- **未知のキーは無視される**: キー名を誤記してもエラーにならず、既定値で実行される。
- **`attack_num_images` の欠落**: `hyperparameters` 自体が未設定なら `ValueError` になる。一方、`hyperparameters` はあるが `attack_num_images` だけが欠けている場合は `int(None)` による `TypeError` になる。
- **LF_MIA 系で `shadow_decoration` を省略した場合**: IN シャドーが装飾なしで学習されるため、IN / OUT シャドーは装飾の有無で区別できなくなる。攻撃モデルは無意味な学習になるが、エラーにはならない。
- **LF_MIA 系の `target_train_decoration.fraction`**: 指定しても `LF_MIA_TARGET_FRACTIONS` で上書きされる。
- **シャドーモデルの装飾**: `OfflineLira` / `OnlineLira` / `Shokri` のシャドーの学習データには装飾を適用しない（`shadow_decoration` は LF_MIA 系専用）。
