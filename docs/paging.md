# 実験一覧ページング仕様

実験件数が 200 件を超え、一覧の初回読み込みと描画が重くなったため、**サーバー側ページング**を導入する。個人の実験用途に限定し、スコープは最小限とする。

本書は方針・決定事項・変更仕様の単一の参照元とする。

---

## 1. 背景と目的

| 現状 | 問題 |
| ---- | ---- |
| `GET /api/experiments` が `find_all()` で全行を返す | ペイロード・JSON パース・DOM が件数に比例して増大 |
| フロントが全件を `DataTable` に渡す | 行数 × 列数（動的列含む）の描画コスト |
| TanStack Table のクライアントソート | 未使用。ページングと併用すると全件ソートが必要になりコストが高い |

**目的**: 1 回の取得を **最大 100 件**に抑え、総件数は `total` でページ UI に渡す。一覧用の軽量 DTO・無限スクロール・仮想化・フィルタは **今回やらない**。

---

## 2. 決定事項

| #   | 項目             | 決定                                                                                                                                                                                                                                 |
| --- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | 一覧の固定順         | ユーザー指定は `id DESC` だったが、**ページ境界の定義（下記 §2.1）と両立するのは古い順**のため、**取得・表示は** `ORDER BY id ASC`**（古い → 新しい）** とする。ユーザーが列ヘッダーで順序を変える機能は付けない。                                                                                                 |
| 2〜5 | ソート            | **全面廃止・削除**（クライアントソート、▲▼ UI、`sortingFn`、`initialSorting`、動的列のソート用比較、実験一覧のソート関連のみでなく **フロント全体**）                                                                                                                                    |
| 6   | `find_all`     | **テスト用にリポジトリに残す**。一覧 HTTP ハンドラからは呼ばない。                                                                                                                                                                                             |
| 7   | ページサイズと offset | **100 件固定**。全実験を **古い順（**`id ASC`**）** に並べたときの **0 始まりの通し番号**で区切る。ページ `p`（1 始まり）はインデックス `(p-1)×100` ～ `p×100-1` に相当する行（最終ページは 100 件未満になりうる）。例: ページ 1 = 0〜99 番目、ページ 2 = 100〜199 番目（いずれも **通し番号**であり、主キー `id` が 0,1,2… と連番である必要はない）。 |
| 8   | 一括操作           | 削除・再実行は **現在表示ページの選択行のみ**。ページ跨ぎ選択はしない。                                                                                                                                                                                             |
| 9   | 将来             | **ソート機能は戻さない**（API の `order_by` も導入しない）。                                                                                                                                                                                           |
| 10  | 初回表示           | **最新の実験が見えるように、最初のロードは最終ページ**（ページ番号最大）を表示する。ページ内の行順は §2.1 の `id ASC` のままなので、**最終ページの末尾行が直近の実験**。                                                                                                                              |

### 2.1 ページ番号と SQL の対応

- `page`: 1 始まり（クエリまたはフロント状態）
- `limit`: **100**（固定。クエリで変えない想定でも、サーバー側で上限 100 を守る）
- `offset`: `(page - 1) × 100`
- 取得:

```sql
SELECT ... FROM experiments
ORDER BY id ASC
LIMIT 100 OFFSET :offset;

SELECT COUNT(*) FROM experiments;  -- total
```

- **最終ページ**: `total` が 250 なら 3 ページ。ページ 3 は 50 件のみ。

**最終ページ番号**（1 始まり）:

```text
page_max = total == 0 ? 1 : ceil(total / limit)
```

（`limit = 100` 固定のとき、例: `total = 250` → `page_max = 3`）

### 2.2 初回ロードで最終ページを開く

| 項目 | 仕様 |
| ---- | ---- |
| 目的 | 一覧を開いた直後に **新しい実験**（大きい `id`）を見る |
| 表示するページ | `page_max`（§2.1） |
| 再訪問 | 同一タブ内では **ユーザーが移動したページ**を維持（React state）。リロード時の挙動は実装で選ぶ（下記） |

**リロード・再入場時のページ復元**（推奨）:

- `sessionStorage` などに `experimentsListPage` を保存し、**値があるときはそれを優先**
- **キーがないときだけ** `page_max` を初回表示（= 実験一覧への「初めての入場」は常に最新側）

**初回 1 リクエストで最終ページを取る**（推奨）:

`page` クエリに **送信専用の sentinel** `0` を許可する（「最終ページを返す」意味。OpenAPI 上は integer のまま）。

- ハンドラ / サービス: `page == 0` のとき内部で `count` → `page_max` を算出し、その `offset` で `find_page` する
- レスポンスの `page` フィールドは **実際に返したページ番号**（`page_max`）をエコーする（`0` は返さない）

フロントの初回 `queryFn`: `GET /api/experiments?page=0&limit=100` → 以降は通常の `page=1..page_max`。

**代替（非推奨）**: `page=1` で一度取って `total` だけ見てから `page=page_max` を再取得（2 RTT）。sentinel を使わない場合のみ。

`total == 0` のとき: `page_max = 1`、`items` は空配列。

---

## 3. API 変更仕様

### 3.1 エンドポイント

既存の `GET /api/experiments` を **ページング対応**に変更する（パスは維持。Worker は一覧 GET を使っていない）。

#### クエリパラメータ

| 名前 | 型 | 必須 | 既定 | 説明 |
| ---- | -- | ---- | ---- | ---- |
| `page` | integer | 否 | （フロント初回は `0`、API 単体の既定は `1` でよい） | 1 始まりのページ番号。**`0` = 最終ページ**（§2.2）。`page < 0` は 400。`page >= 1` かつ総ページ超過は空 `items`（§3.2） |
| `limit` | integer | 否 | `100` | 今回は **100 固定**でよい。送られても **最大 100 にクランプ** |

`offset` はクエリに出さず、サーバー内部で `(page - 1) * limit` とする。

#### レスポンスボディ

新規 DTO（名称例: `ExperimentPageResponse`）:

| フィールド | 型 | 説明 |
| ---------- | -- | ---- |
| `items` | `Model[]` | 当該ページの実験（既存 `Model` と同内容。一覧 DTO 化はしない） |
| `total` | `integer` (i64) | 全件数 |
| `page` | `integer` | 返却したページ番号（エコー） |
| `limit` | `integer` | 返却した limit（エコー、実質 100） |

**破壊的変更**: レスポンスが `Model[]` から上記オブジェクトになる。フロントの `openapi-typescript` 再生成が必須。

#### OpenAPI / utoipa

- `get_all_experiments` の response body を `ExperimentPageResponse` に更新
- クエリパラメータ `page`, `limit` を追加

### 3.2 バックエンドレイヤー

| レイヤー | 変更 |
| -------- | ---- |
| `ExperimentRepositoryTrait` | `find_page(limit, offset) -> Result<Vec<Model>>` を追加。`find_all` は **残す**（テスト・既存テスト用） |
| `ExperimentRepository` | `find_page`: `Entity::find().order_by_asc(Column::Id).limit(limit).offset(offset).all(...)`。`count` は `Entity::find().count(...)` または同等 |
| `ExperimentService` | `get_experiments_page(page, limit)` を追加（バリデーション・offset 計算。**`page == 0` なら `count` 後に `page_max` に置換**）。`get_all_experiments` はハンドラから外すか deprecated（テストからは `find_all` 経由で可） |
| `handlers/experiment.rs` | `get_all_experiments` がクエリを読み、ページレスポンスを返す |

エラーハンドリング:

- `page` が総ページ数を大きく超える場合: `items: []`, `total` は正値、`page` は要求値のまま（空ページを返す）

---

## 4. フロントエンド変更仕様

### 4.1 データ取得

- `useExperiments`（または同等）:
  - `queryKey`: `["experiments", page]`（`limit` 固定なら key に含めなくてよい）
  - `queryFn`: `GET /api/experiments?page={page}&limit=100`（**初回のみ** `page=0` で最終ページを取得、§2.2）
  - 返却: `items`, `total`, `page`, `limit` を保持。初回 `page=0` の応答後は state を **`response.page`（= `page_max`）** に揃える
  - **初回ページ決定**: `sessionStorage` に保存済みページがなければ `page=0` で取得。あればそのページ番号
- mutation 成功後: `invalidateQueries({ queryKey: ["experiments"] })` で **現在ページを再取得**（全ページを順次取りに行かない）
  - 削除で **現在ページが空**になった場合: `page` を `min(現在, page_max)` に下げて再取得（`page_max` は新しい `total` から再計算）

### 4.2 実験一覧 UI

- `ExperimentList`: `data={items}`。全件 `experiments` 配列は持たない
- **ページング UI**: 前へ / 次へ、現在ページ、総ページ数（`Math.ceil(total / limit)`）など最小構成
- 初回 `loading`: ページ単位のローディングでよい（全件ブロックはしない）
- `useDynamicColumns`: 引数は **当該ページの** `items` **のみ**（全件キー union はしない）

### 4.3 ソート機能の削除（全体）

対象は **実験一覧に限らず**、`DataTable` 共通部分を含む。

| 削除・変更対象 | 内容 |
| -------------- | ---- |
| `DataTable.tsx` | `getSortedRowModel`、ヘッダー ▲▼、`sorting` state、`onSortingChange` |
| `useTablePreferences.ts` / `tablePreferences.ts` | `sorting` の保存・マージ・読み込みを削除 |
| `ExperimentList.tsx` | `EXPERIMENT_DEFAULT_SORTING`、`initialSorting`、列の `sortingFn` |
| `useDynamicColumns.ts` | 各列の `sortingFn` |
| `TaskList.tsx` | ソートに依存する記述があれば整理（`DataTable` 側削除で足りる想定） |
| ドキュメント | `orchestrator/frontend/docs/COMPONENTS.md`, `ARCHITECTURE.md` のソート記述を削除し、本仕様への参照を追加 |

**localStorage**: 既存 `app:table-preferences:v1:`* に `sorting` が残っていても **読み捨て**でよい（マージ処理ごと削除）。

### 4.4 TanStack Table

- `getCoreRowModel` のみ使用
- ページングは **サーバー側**。`getPaginationRowModel` で全件を slice しない（`manualPagination` はフック側で `pageCount = ceil(total/limit)` を渡す場合のみ。データは常に現在ページの `items` だけ）

---

## 5. スコープ外（明示）

- 一覧用 DTO（JSONB の省略）
- 無限スクロール・順次チャンク読み込み
- 行仮想化
- ステータス・日付などのフィルタ
- `order_by` クエリ・ソート復活
- ページ跨ぎの全選択・「フィルタ一致全件」操作

---

## 6. 実装チェックリスト

### バックエンド

- [ ] `find_page` + `count` 実装、`find_all` 維持
- [ ] DTO `ExperimentPageResponse`
- [ ] ハンドラ・サービス・utoipa 更新
- [ ] リポジトリテスト（`find_page` の境界: offset 0、最終ページ、空 DB）
- [ ] サービス / ハンドラ: `page=0` → 最終ページと同じ `items`・`page` エコー
- [ ] 既存 `test_find_all` はそのまま

### フロントエンド

- [ ] OpenAPI 再生成 → `useExperiments` ページ対応
- [ ] `ExperimentList` ページ UI + `items` 接続
- [ ] 初回 `page=0`（または session 復元）、`sessionStorage` でページ保持
- [ ] `DataTable` / preferences からソート完全削除
- [ ] フロントドキュメント更新

### 手動確認

- [ ] 200 件超で初回表示が軽くなること
- [ ] **初回表示が最終ページ**で、最新実験（最大 `id`）が含まれること
- [ ] ページ 1 が最古の 100 件（通し番号 0〜99）であること（「前へ」で遡れること）
- [ ] 最終ページの件数が `total % 100`（余り 0 なら 100）と一致すること
- [ ] 選択削除・再実行が当該ページの ID のみに効くこと
- [ ] 列表示・列順の localStorage が引き続き動作すること（ソート以外）

---

## 7. 関連ファイル（実装時の目安）

| 領域 | パス |
| ---- | ---- |
| 仕様（本書） | `docs/paging.md` |
| Repository | `orchestrator/backend/src/repositories/experiment.rs` |
| Service | `orchestrator/backend/src/services/experiment.rs` |
| Handler | `orchestrator/backend/src/handlers/experiment.rs` |
| DTO | `orchestrator/backend/src/dto/experiment.rs` |
| Hook | `orchestrator/frontend/src/hooks/useExperiments.ts` |
| 一覧画面 | `orchestrator/frontend/src/pages/Experiments/ExperimentList.tsx` |
| テーブル | `orchestrator/frontend/src/components/ui/DataTable/DataTable.tsx` |
| 設定永続化 | `orchestrator/frontend/src/hooks/useTablePreferences.ts`, `utils/tablePreferences.ts` |

---

## 8. 決定ログ（会話要約）

- 個人利用のため **ページング + 100 件**のみで十分と判断
- ソートは未使用のため **全削除**。将来も戻さない
- ページは **古い順の通し番号**で 100 件単位（ページ 1 = 0〜99 番目）
- **初回ロードは最終ページ**（新しい実験をすぐ見る）。API は `page=0` で 1 RTT 取得を推奨
