# フロントエンド コンポーネント・API仕様書 (詳細設計図)

本書は、システムを構成する各コンポーネントの責務、プロパティ(Props)、および API 通信を担うカスタムフックの詳細について定義したドキュメントです。

---

## 1. カスタムフック (データアクセス・ビジネスロジック)

### 1.1 `useExperiments`
実験データの取得、作成、削除を行うためのフック。内部で `useQuery`, `useMutation` を使用。

- **取得データ:** `experiments` (`components["schemas"]["Model"][]`)
- **提供メソッド:**
  - `createExperiment(req: CreateExperimentRequest): Promise<void>`: 新しい実験を作成
  - `deleteExperiments(ids: number[], options?: object): void`: 複数の実験を並列で削除
  - `refetch()`: データを再取得
- **状態:** `loading` (boolean), `error` (Error | null), `isCreating` (boolean), `isDeleting` (boolean)

### 1.2 `useTasks`
タスクデータの取得、削除を行うためのフック。

- **取得データ:** `tasks` (`components["schemas"]["Task"][]`)
- **提供メソッド:**
  - `deleteTasks(ids: string[], options?: object): void`: 複数のタスクを並列で削除
  - `refetch()`: データを再取得
- **状態:** `loading`, `error`, `isDeleting`

### 1.3 `useFilters`
フィルタ画像の一覧取得、アップロード、削除を行うためのフック。multipart アップロードのため `fetch` を直接使用。

- **取得データ:** `filters` (`FilterSummary[]`)
- **提供メソッド:**
  - `uploadFilter({ id, file }, options?)`: `POST /api/filters/{id}` で PNG をアップロード
  - `deleteFilter(id, options?)`: `DELETE /api/filters/{id}` で削除
  - `refetch()`: データを再取得
- **状態:** `loading`, `error`, `isUploading`, `isDeleting`
- **エラー:** `FilterApiError`（`status` プロパティ付き）。409 は ID 衝突時に UI 側で手動 ID 入力へ誘導

### 1.4 `useDynamicColumns`
辞書型プロパティ（JSONオブジェクト）からキーを動的に抽出し、TanStack Table 用のカラム定義（`ColumnDef`）を生成するユーティリティフック。

- **引数:**
  - `data: TData[]`: 展開対象のデータ配列
  - `dictionaryConfigs`: `{ key: keyof TData, prefix: string, renderCell?: (ctx) => ReactNode }[]`（展開するプロパティ名、ヘッダー用プレフィックス、任意のセルカスタム描画）
- **戻り値:**
  - `dynamicColumns`: 生成された `ColumnDef[]`
  - `defaultHiddenColumns`: 生成されたカラムのIDをキーとし、`false` を値に持つオブジェクト（初期非表示設定用）

`renderCell` を指定した辞書はセル表示を上書きし、`meta: { align: "left" }` を付与して配置を固定します（例: 実験一覧の `files` 列で PNG インライン表示・リンク）。

各動的列には `sortingFn` が付与され、値は文字列化（オブジェクトは `JSON.stringify`）したうえで `localeCompare`（`numeric: true`）により比較されます。`renderCell` 未指定の動的列は、列の生値がすべて数値のとき `DataTable` 側で右寄せになります。

### 1.5 `useTablePreferences`
`DataTable` の UI 設定（表示カラム・列順・ソート）を管理し、任意で `localStorage` に永続化するフック。

- **引数:**
  - `storageKey`: 永続化キーの識別子（例: `"experiments"`, `"tasks"`）。未指定時はメモリ内のみ
  - `defaults`: ストレージ未ヒット時および新規カラム追加時のフォールバック
    - `columnVisibility`, `columnOrder`, `sorting`
  - `columnIds`: 現在のカラム ID 一覧（動的カラムの増減検知用）
- **戻り値:**
  - `columnVisibility`, `columnOrder`, `sorting`: マージ済みの表示用状態
  - `onColumnVisibilityChange`, `onColumnOrderChange`, `onSortingChange`: TanStack Table 用の更新ハンドラ
- **永続化:** `tablePreferences.ts` の純粋関数が `localStorage` に JSON 保存。パース失敗時は `defaults` にフォールバック

---

## 2. UIコンポーネント (src/components/ui/)

### 2.1 `DataTable`
`@tanstack/react-table` をラップし、一貫したテーブルUIと追加機能を提供する基盤コンポーネント。

- **機能:**
  - 行の複数選択機能 (チェックボックス)
  - カラムの表示・非表示の切り替え (`ColumnVisibilityMenu` を内包)
  - カラムヘッダーのドラッグ＆ドロップによる並び替え (`@dnd-kit` 統合)
  - 列ソート: `getSortedRowModel` によりソート済み行を表示。チェック列以外のヘッダーに **昇順（▲）・降順（▼）** ボタンがあり、クリックした列のみが `SortingState` に反映される（タスクマネージャ風の単一キーソート）。
  - 列の配置: `resolveColumnAlign` により `th` / `td` の `text-align` を決定。数値列は右寄せ、選択列は中央、それ以外は左寄せ（詳細は `columnAlign.ts`）。
  - 設定の永続化: `storageKey` 指定時、表示カラム・列順・ソートを `localStorage` に自動保存・復元（`useTablePreferences` 経由）
- **Props:**
  - `columns`: テーブルのカラム定義 (`ColumnDef[]`)
  - `data`: 表示するデータ配列
  - `rowSelection`: 現在の行選択ステート
  - `onRowSelectionChange`: 行選択ステートの更新関数
  - `initialColumnVisibility`: ストレージ未ヒット時・新規動的カラムのフォールバック表示状態
  - `initialSorting` (任意): ストレージ未ヒット時のフォールバック `SortingState`（例: 実験一覧は `id` 昇順）
  - `getRowId` (任意): 行の安定 ID（データ上の主キー文字列）。ソート後も `rowSelection` のキーが行インデックスに依存しないようにするために指定する（実験は `String(id)`、タスクは UUID の `id`）
  - `storageKey` (任意): 永続化用識別子。例: `"experiments"`, `"tasks"`。未指定時はリロードで設定がリセットされる

### 2.2 `KeyValueEditor`
辞書型データを動的に Key-Value 形式で編集するためのコンポーネント。

- **機能:**
  - 行の追加、削除、編集
  - 入力値の型（数値、真偽値、JSON文字列）の自動推論とキャスト
- **Props:**
  - `value`: 現在の辞書型オブジェクト (`Record<string, unknown>`)
  - `onChange`: 値が変更された際のコールバック関数
  - `disabled`: 編集ロックフラグ

### 2.3 `Modal` / `ConfirmModal`
- **`Modal`**: オーバーレイと基本的なウィンドウの枠組みを提供する基底モーダル。コンテンツ領域（`.content`）は `text-align: left` で本文・見出しを左揃えにしている。
- **`ConfirmModal`**: `Modal` をベースに作成された、削除操作などの最終確認（はい/いいえ）用ダイアログ。

---

## 3. ページコンポーネント (src/pages/)

### 3.1 `ExperimentList`
実験データの一覧を表示するページコンポーネント。

- **構成:**
  - `useExperiments` でデータを取得。
  - `useDynamicColumns` を用いて、`hyperparameters`, `other_metrics`, `files` を動的カラムとして展開。
  - `DataTable` に `storageKey="experiments"` を渡し、表示カラム・列順・ソートをブラウザに永続化。
  - `DataTable` に `initialSorting={[{ id: "id", desc: false }]}`（**ID 昇順**）と `getRowId={(row) => String(row.id)}` を渡す。行選択のキーは実験 ID 文字列であり、列ソート後も一括削除が正しい ID に紐づく。
  - `files` 列: セル値は MinIO オブジェクトキー（例: `results/42/roc_curve.png`）。`isPngObjectKey` で PNG と判定し、PNG は高さ 160px の `<img>` をセル内表示し、画像クリック（`<a target="_blank">`）で別タブを開く。非 PNG はファイル名リンク（`fileApiPath`、`target="_blank"`）のみ。
  - 一部静的列は表示用に変換（例: AUC・TPR を `%` 表示、`total_time` を分単位、真偽値フラグを `○`）。ソート・配置推論は `accessorKey` の生値（数値）に基づくため、数値列は右寄せとなる。
  - `DataTable` に静的カラム（ID, 名前, ステータス等）と動的カラムを結合して表示。選択列は `enableSorting: false`。`id` 列は `sortingFn: "basic"` で数値ソート。
  - ヘッダー部に「新しい実験を作成」ボタンと、選択項目がある場合のみ「選択した項目を削除」ボタンを表示。フィルタ管理は `/filters` タブで行う（本画面には含めない）。

### 3.2 `CreateExperimentModal`
実験一覧ページ内に配置される、新規実験作成用フォーム。

- **構成:**
  - `useState` で `CreateExperimentRequest` 型に基づくフォーム状態を管理。
  - 基本的な設定は標準の `<input>` や `<select>` を使用。
  - `hyperparameters` プロパティの入力には、`KeyValueEditor` を使用し、安全なJSON生成を実現。
  - 透かし設定: `useFilters` で取得したフィルタ一覧から `filter_id` を `<select>` で選択。`CreateExperimentRequest.watermark` に `enabled`, `filter_id`, `apply`, `seed_offset` をトップレベルで送信。

### 3.3 `TaskList`
タスクデータの一覧を表示するページコンポーネント。

- **構成:**
  - `useTasks` でデータを取得。
  - `useDynamicColumns` を用いて、`args_control`, `args_keyword`, `args_positional` を動的カラムとして展開。
  - `DataTable` に `storageKey="tasks"` を渡し、表示カラム・列順・ソートをブラウザに永続化。
  - `DataTable` に `getRowId={(row) => row.id}`（タスクの UUID）を渡し、列ソート後も行選択・一括削除が正しいタスク ID に紐づく。選択列は `enableSorting: false`。
  - 実験一覧と同様のヘッダーソート（▲▼）と選択・一括削除 UI を提供。

### 3.4 `FilterList` / `FilterManager`
フィルタ画像の一覧・管理画面（`/filters`）。

- **`FilterList`**: ページコンテナ。`useFilters` のエラーを上部に表示し、`FilterManager` を配置。
- **`FilterManager`**:
  - 登録済みフィルタを 96×96 サムネイル（`image-rendering: pixelated`）で一覧表示。「プレビュー」リンクで別タブ、`ConfirmModal` 経由で削除。
  - PNG アップロード: `POST /api/filters/{id}`。ID は `deriveFilterId` でファイル名から自動導出。導出不可・既存 ID 衝突・409 時のみ ID 入力欄を表示。

---

## 4. 共通ユーティリティ

### 4.1 `fileApiPath` (`src/utils/fileApiPath.ts`)
MinIO ファイル取得 API への相対パスを返す。

- **`fileApiPath(objectKey: string): string`**: `` `/api/files/${encodeURIComponent(objectKey)}` ``（`objectKey` に `/` を含めても 1 パスセグメントとしてエンコードされる）
- **`isPngObjectKey(objectKey: string): boolean`**: オブジェクトキー末尾が `.png`（大文字小文字無視）かどうか

実験一覧の `files` 列およびフィルタ一覧のプレビューから利用する。

### 4.2 `columnAlign` (`src/utils/columnAlign.ts`)
`DataTable` の列 `text-align` を決定する純関数群。

- **`TableColumnAlign`:** `"left" | "right" | "center"`
- **`isNumericCellValue(value)`:** `number` かどうか（`null` / `undefined` は推論時に無視）
- **`inferAlignFromValues(values)`:** 非 null 値がすべて数値なら `"right"`、それ以外は `"left"`
- **`resolveColumnAlign(column, table)`:** `column.columnDef.meta?.align` を最優先。未指定時は `select` 列を中央、それ以外は全行の生値から `inferAlignFromValues` で推論

列定義の `meta: { align: "right" }` で明示上書き可能。型は `src/types/tanstack-table.d.ts` で拡張。

### 4.3 `filterId` (`src/utils/filterId.ts`)
フィルタ ID のバリデーションとファイル名からの導出。

- **`FILTER_ID_RE`:** `^[a-zA-Z0-9_-]+$`
- **`deriveFilterId(filename)`:** `.png` 拡張子を除いたベース名が正規表現に合致すれば ID を返す。不合致時は `null`
- **`isValidFilterId(id)`:** ID 文字列の妥当性チェック

### 4.4 `tablePreferences` (`src/utils/tablePreferences.ts`)
テーブル UI 設定の `localStorage` 読み書きとマージを担う純粋関数群。

- **ストレージキー:** `app:table-preferences:v1:{storageKey}`
- **スキーマ (`TablePreferencesV1`):**
  - `version`: `1`（将来のマイグレーション用）
  - `columnVisibility`: カラム表示/非表示
  - `columnOrder`: DnD による列順
  - `sorting`: ソート状態
- **主要関数:**
  - `loadTablePreferences(storageKey)`: 保存値を読み込み。パース・バリデーション失敗時は `null`
  - `saveTablePreferences(storageKey, prefs)`: JSON 保存（quota 超過等は握りつぶす）
  - `mergeTablePreferences(saved, defaults, columnIds)`: 保存値と現在のカラム一覧をマージ
  - `getColumnId(col)`: `ColumnDef` からカラム ID を抽出（`id` または `accessorKey`）
- **マージ方針:**
  - `columnVisibility`: 保存済み ID は保存値を優先。新規 ID は `defaults.columnVisibility` を適用
  - `columnOrder`: 保存順から存在しない ID を除去し、未登録の新規 ID を末尾に追加
  - `sorting`: ソート対象カラムが存在しなければ `defaults.sorting` にフォールバック
