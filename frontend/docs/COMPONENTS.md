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

### 1.3 `useDynamicColumns`
辞書型プロパティ（JSONオブジェクト）からキーを動的に抽出し、TanStack Table 用のカラム定義（`ColumnDef`）を生成するユーティリティフック。

- **引数:**
  - `data: TData[]`: 展開対象のデータ配列
  - `dictionaryConfigs`: `{ key: keyof TData, prefix: string, renderCell?: (ctx) => ReactNode }[]`（展開するプロパティ名、ヘッダー用プレフィックス、任意のセルカスタム描画）
- **戻り値:**
  - `dynamicColumns`: 生成された `ColumnDef[]`
  - `defaultHiddenColumns`: 生成されたカラムのIDをキーとし、`false` を値に持つオブジェクト（初期非表示設定用）

`renderCell` を指定した辞書のみセル表示を上書きできます（例: 実験一覧の `files` 列でオブジェクトキーをクリック可能にする）。

各動的列には `sortingFn` が付与され、値は文字列化（オブジェクトは `JSON.stringify`）したうえで `localeCompare`（`numeric: true`）により比較されます。

---

## 2. UIコンポーネント (src/components/ui/)

### 2.1 `DataTable`
`@tanstack/react-table` をラップし、一貫したテーブルUIと追加機能を提供する基盤コンポーネント。

- **機能:**
  - 行の複数選択機能 (チェックボックス)
  - カラムの表示・非表示の切り替え (`ColumnVisibilityMenu` を内包)
  - カラムヘッダーのドラッグ＆ドロップによる並び替え (`@dnd-kit` 統合)
  - 列ソート: `getSortedRowModel` によりソート済み行を表示。チェック列以外のヘッダーに **昇順（▲）・降順（▼）** ボタンがあり、クリックした列のみが `SortingState` に反映される（タスクマネージャ風の単一キーソート）。
- **Props:**
  - `columns`: テーブルのカラム定義 (`ColumnDef[]`)
  - `data`: 表示するデータ配列
  - `rowSelection`: 現在の行選択ステート
  - `onRowSelectionChange`: 行選択ステートの更新関数
  - `initialColumnVisibility`: 初回マウント時のカラム表示状態
  - `initialSorting` (任意): 初回マウント時の `SortingState`（例: 実験一覧は `id` 昇順）
  - `getRowId` (任意): 行の安定 ID（データ上の主キー文字列）。ソート後も `rowSelection` のキーが行インデックスに依存しないようにするために指定する（実験は `String(id)`、タスクは UUID の `id`）

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
  - `DataTable` に `initialSorting={[{ id: "id", desc: false }]}`（**ID 昇順**）と `getRowId={(row) => String(row.id)}` を渡す。行選択のキーは実験 ID 文字列であり、列ソート後も一括削除が正しい ID に紐づく。
  - `files` 列: セル値はファイル名のみを想定。MinIO オブジェクトキーは `` `${row.id}/${ファイル名}` `` で組み立てる。ファイル名をクリックすると `FilePreviewModal` が開く。横の **⧉** リンクは `fileApiPath` で組み立てた同一オリジン URL を **別タブ** で開く（`GET /api/files/{key}`、`key` はパス用に `encodeURIComponent`）。
  - `FilePreviewModal` 内でもフェッチは `openapi-fetch` の `parseAs: "blob"`。プレビュー下部に「別タブで開く」（API 直リンク）と blob ベースの「ダウンロード」を配置。
  - `DataTable` に静的カラム（ID, 名前, ステータス等）と動的カラムを結合して表示。選択列は `enableSorting: false`。`id` 列は `sortingFn: "basic"` で数値ソート。
  - ヘッダー部に「新しい実験を作成」ボタンと、選択項目がある場合のみ「選択した項目を削除」ボタンを表示。

### 3.2 `CreateExperimentModal`
実験一覧ページ内に配置される、新規実験作成用フォーム。

- **構成:**
  - `useState` で `CreateExperimentRequest` 型に基づくフォーム状態を管理。
  - 基本的な設定は標準の `<input>` や `<select>` を使用。
  - `hyperparameters` プロパティの入力には、`KeyValueEditor` を使用し、安全なJSON生成を実現。

### 3.3 `TaskList`
タスクデータの一覧を表示するページコンポーネント。

- **構成:**
  - `useTasks` でデータを取得。
  - `useDynamicColumns` を用いて、`args_control`, `args_keyword`, `args_positional` を動的カラムとして展開。
  - `DataTable` に `getRowId={(row) => row.id}`（タスクの UUID）を渡し、列ソート後も行選択・一括削除が正しいタスク ID に紐づく。選択列は `enableSorting: false`。
  - 実験一覧と同様のヘッダーソート（▲▼）と選択・一括削除 UI を提供。

### 3.4 `FilePreviewModal` (`src/pages/Experiments/components/FilePreviewModal.tsx`)
実験一覧から開くファイルプレビュー用モーダル。

- **Props:** `objectKey`（MinIO キー全文、`null` で閉じる扱い）、`onClose`
- **取得:** `apiClient.GET("/api/files/{key}", { params: { path: { key: objectKey } }, parseAs: "blob" } })`
- **表示分岐:** `Content-Type` およびサイズ上限に応じて画像（`createObjectURL`）、テキスト（`<pre>`）、その他はバイナリ案内＋ダウンロードリンク。アンマウント時に `revokeObjectURL`。
- **別タブ:** `fileApiPath(objectKey)` を `href` にしたリンク（モーダル内の一覧アクションと同じ URL 方針）。

---

## 4. 共通ユーティリティ

### 4.1 `fileApiPath` (`src/utils/fileApiPath.ts`)
MinIO ファイル取得 API への相対パスを返す。

- **シグネチャ:** `fileApiPath(objectKey: string): string`
- **戻り値:** `` `/api/files/${encodeURIComponent(objectKey)}` ``（`objectKey` に `/` を含めても 1 パスセグメントとしてエンコードされる）

実験一覧の `files` 列（別タブ ⧉）および `FilePreviewModal` の「別タブで開く」から利用する。
