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
| `shadow_decoration` | 装飾オブジェクト | なし | LF_MIA 系 | `dataset.get_shadow_dataloader(is_decoration=True)` |
| `attack_decoration` | 装飾オブジェクト（`watermark` のみ） | なし | LF_MIA 系（**必須**） | `dataset.get_attack_watermark_dataloader` / `get_attack_composite_dataloaders` |
| `attack_num_images` | int (>= 1) | なし | `LfMultMia` / `LfMultDiffMia`（**必須**） | `LF_Mult_MIA._num_images` |
| `membership_scorer` | str | `neural` | LF_MIA 系 | `attacks/membership_scorers/__init__.py` |
| `attack_model_batch_size` | int | `16`（`cfg.ATTACK_MODEL_BATCH_SIZE`） | LF_MIA 系（`membership_scorer=neural`） | 同上 |
| `attack_model_epochs` | int | `100`（`cfg.ATTACK_MODEL_EPOCHS`） | LF_MIA 系（`membership_scorer=neural`） | 同上 |
| `diagonal_lda_reg_lambda` | float | `1e-3` | LF_MIA 系（`diagonal_lda` / `flat_diagonal_lda`） | 同上 |
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
| `shadow_decoration` | LF_MIA 系の **IN シャドー**の学習データとテストデータ。OUT シャドーには適用しない |
| `attack_decoration` | LF_MIA 系の攻撃プローブ。`LfMia` は黒背景に透かしを合成した 1 枚、`LfMultMia` / `LfMultDiffMia` はターゲットのテスト画像 K 枚に透かしを合成したもの。`filter_id` のみを使い、`fraction` / `seed_offset` は使わない。`display_mask` を指定すると `ValueError` |

各装飾の見た目は `work_dir/decoration_preview.png`（左から plain / target / eval / shadow / attack）で確認できる。プレビューは `fraction` に関係なく装飾を適用して描画する。

---

## LF_MIA 系の攻撃設定

### `attack_num_images`

`LfMultMia` / `LfMultDiffMia` で、透かしを合成するターゲットのテスト画像の枚数 K。`RandomState(seed)` でターゲットのテストデータから非復元抽出する。

- `1 <= K <= target_test_size` を満たさない場合は `ValueError`。
- `config.py` に既定値はない。

### membership scorer

LF_MIA 系の攻撃モデル。詳細は `SPECIFICATION.md` の「Membership scorer」を参照。

| `membership_scorer` | 手法 | 使用するキー | スコアのスケール |
| ------------------- | ---- | ------------ | ---------------- |
| `neural` | `AttackNet` で画像ごとに IN/OUT を分類し、IN 確率を平均する | `attack_model_batch_size`, `attack_model_epochs` | `probability` |
| `diagonal_lda` | K 枚を平均した特徴に対する対角 LDA（分母はペア差分の分散） | `diagonal_lda_reg_lambda` | `log_odds` |
| `flat_diagonal_lda` | `(K·C)` に平坦化した対角 LDA | `diagonal_lda_reg_lambda`, `flat_diagonal_lda_variance` | `log_odds` |
| `gaussian_lr` | (k, c) ごとの正規分布による尤度比検定 | `gaussian_lr_variance`, `gaussian_lr_var_floor` | `log_odds` |

| キー | 取り得る値 | 意味 |
| ---- | ---------- | ---- |
| `flat_diagonal_lda_variance` | `within_class`（既定） | 重みの分母を IN / OUT のクラス内分散のプールにする。データの異なる単体モデルに汎化させる場合の標準 |
| | `pair_diff` | 重みの分母をペア差分 IN−OUT の分散にする。データ分割由来の分散がペア内で相殺される |
| `gaussian_lr_variance` | `per_class`（既定） | IN / OUT で別々の分散を使う |
| | `pooled` | IN / OUT の分散の平均を共通に使う（シャドーが少ないとき向け） |

- 文字列の値は前後の空白を除き、小文字に正規化してから解釈する。取り得る値以外は `ValueError`。
- スコアのスケールは metrics の `membership_score_scale` に出力され、`attack_score` / `threshold_at_*` の単位を表す。

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
