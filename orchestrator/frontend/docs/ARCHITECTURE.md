# フロントエンド アーキテクチャ仕様書 (俯瞰設計図)

本書は、本プロジェクト（React + TypeScript + Vite）の全体的なフロントエンド・アーキテクチャ、ディレクトリ構成、およびデータフローの全体像を俯瞰するための設計ドキュメントです。

## 1. システム全体図

本システムは、バックエンドの OpenAPI (Swagger) 定義を基に、フロントエンドの型定義および API クライアントを自動生成し、React Query で状態管理を行うモダンな SPA (Single Page Application) アーキテクチャを採用しています。

```mermaid
graph TD
    subgraph "Backend (Rust + utoipa)"
        API[REST API]
        Schema[OpenAPI Schema (openapi.json)]
    end

    subgraph "Frontend (React + Vite)"
        GenType[Type Generation (openapi-typescript)]
        Client[API Client (openapi-fetch)]
        Query[State Management (React Query)]
        UI[UI Components]
    end

    Schema -->|Generate Types| GenType
    GenType --> Client
    API <-->|HTTP GET/POST/DELETE| Client
    Client <--> Query
    Query <-->|Render & Mutate| UI
```

## 2. ディレクトリ構成

システムは責務ごとにディレクトリが分割されており、高い凝集度と低い結合度を維持しています。

```text
/app/src/
├── api/             # API通信層
│   ├── client.ts    # openapi-fetchのクライアント初期化
│   └── schema.d.ts  # OpenAPIから自動生成された型定義ファイル
│
├── hooks/           # ビジネスロジック・状態管理層 (カスタムフック)
│   ├── useExperiments.ts    # 実験データの取得(Query)と操作(Mutation)
│   ├── useTasks.ts          # タスクデータの取得(Query)と操作(Mutation)
│   ├── useFilters.ts        # フィルタ画像の一覧取得・アップロード・削除
│   ├── useDynamicColumns.ts # JSON型の動的キー抽出・カラム生成（列ソート用 sortingFn を含む）
│   └── useTablePreferences.ts # テーブル UI 設定の状態管理と localStorage 永続化
│
├── utils/           # 画面横断の小さな純関数
│   ├── fileApiPath.ts       # MinIO オブジェクトキー → /api/files/... 相対パス
│   ├── filterId.ts          # ファイル名からフィルタ ID を導出する純関数
│   └── tablePreferences.ts  # テーブル設定の読み書き・マージ・バリデーション
│
├── components/      # 汎用コンポーネント層
│   ├── layout/      # 画面の共通レイアウト (Header, Navigation 等)
│   └── ui/          # 画面に依存しない再利用可能なUI部品
│       ├── Badge/   # ステータス表示バッジ
│       ├── Button/  # 共通ボタン
│       ├── ConfirmModal/ # 削除確認等の共通モーダル
│       ├── DataTable/    # TanStack Table（ソート・行選択・D&D列順・列表示切替）
│       ├── KeyValueEditor/ # 辞書型(JSON)編集用エディタ
│       └── Modal/   # モーダル基底コンポーネント
│
├── pages/           # 画面（ルーティング）層
│   ├── Experiments/ # 実験一覧・管理画面
│   │   ├── ExperimentList.tsx
│   │   └── components/
│   │       ├── CreateExperimentModal.tsx # 実験作成モーダル
│   │       └── FilePreviewModal.tsx      # MinIO ファイルのプレビュー（blob 取得・別タブ用 URL）
│   ├── Filters/       # フィルタ画像の管理画面
│   │   ├── FilterList.tsx
│   │   └── components/
│   │       └── FilterManager.tsx         # アップロード・一覧・削除
│   └── Tasks/       # タスク一覧画面
│       └── TaskList.tsx
│
├── App.tsx          # アプリケーションのルーティング定義
├── index.css        # グローバルスタイル (CSS Variables定義)
└── main.tsx         # エントリーポイント (QueryClientProvider等の注入)
```

## 3. 主要な設計方針

### 3.1 状態管理とデータフェッチ
`@tanstack/react-query` と `openapi-fetch` の組み合わせにより、APIリクエストの状態（`loading`, `error`, `data`）を自動的に管理します。
これにより、UIコンポーネント内での `useEffect` を使った手動データフェッチを排除し、カスケードレンダリングを防いでいます。

### 3.2 テーブル設計と動的カラム
カラム数が非常に多いデータ（実験一覧等）を扱うため、`@tanstack/react-table` を利用しています。
- **動的カラムの展開**: JSON（辞書型）のプロパティ（例: `hyperparameters`, `files`）は、`useDynamicColumns` フックにより内部のキーを抽出し、テーブルのフラットなカラムとして動的に展開されます。辞書単位で任意の `renderCell` を差し込める（実験の `files` はファイル名クリックでプレビューモーダル、⧉ で別タブ用 API URL を開く等）。
- **列ソート**: `getSortedRowModel` とヘッダー上の昇順・降順操作により、単一キーでソート状態を管理します。実験一覧は初期状態で **ID 昇順**。動的列には比較可能な文字列表現へ正規化する `sortingFn` を付与しています。
- **行 ID と行選択**: 列ソート後もチェックボックスの選択がデータ行と一致するよう、`DataTable` は任意の `getRowId`（実験は数値 `id` の文字列化、タスクは UUID）を TanStack Table に渡し、`rowSelection` のキーを行インデックスから切り離しています。
- **カラムの制御**: カラムの表示/非表示の切り替え、および `@dnd-kit` を用いたヘッダーのドラッグ＆ドロップによる**列の並び順**変更が実装されています（行の並び替えとは別レイヤー）。
- **テーブル設定の永続化**: 表示カラム・列順・ソートは `useTablePreferences` により `localStorage` に保存されます（キー: `app:table-preferences:v1:{storageKey}`）。実験一覧は `experiments`、タスク一覧は `tasks`。`storageKey` 未指定時は従来どおりエフェメラル。`rowSelection` やモーダル開閉は永続化しません。
- **動的カラムとのマージ**: 保存済み設定を復元する際、存在しないカラム ID は除去し、新規に出現した動的カラムには `defaultHiddenColumns`（初期非表示）を適用します。既存カラムのユーザー設定は維持されます。

### 3.3 コンポーネントのカプセル化
スタイリングには **CSS Modules** (`*.module.css`) を採用しています。クラス名のスコープが各コンポーネント内に閉じられるため、他のコンポーネントへの意図しないスタイルの影響を防ぎ、保守性を高めています。

### 3.4 実験付属ファイル（MinIO）の参照
実験レコードの `files` は「表示名（キー）→ MinIO オブジェクトキー（値）」のマップです。値（例: `results/42/roc_curve.png`）をそのまま `GET /api/files/{key}` に渡します。パス上の `key` はスラッシュを含み得るため、クライアントでは `encodeURIComponent` した相対パス（`fileApiPath`）で同一オリジンにリクエストします（開発時は Vite のプロキシ経由で API に到達）。

フィルタ画像はバケット直下の `filters/{id}.png` キーで参照します（`GET /api/filters` で一覧、`POST /api/filters/{id}` でアップロード、`DELETE /api/filters/{id}` で削除）。管理 UI は `/filters` タブの `FilterManager` で提供します。アップロード時の ID は基本ファイル名（拡張子除く）を自動使用し、既存 ID と衝突する場合のみ手動入力を促します。

- **別タブ / 直リンク**: ブラウザのナビゲーションとして開く場合は blob ではなく上記 URL を用い、サーバーが返す `Content-Type` に従い表示またはダウンロードとなります。
- **モーダル内プレビュー**: `openapi-fetch` の `parseAs: "blob"` でバイナリを取得し、`URL.createObjectURL` による画像・テキスト表示やダウンロード用一時 URL を組み立てます。閉じる・キー変更時に `revokeObjectURL` で解放します。

## 4. ルーティング設計

`react-router-dom` を用いて、URLベースの画面遷移を実現しています。

- `/` : `/experiments` へリダイレクト
- `/experiments` : 実験一覧画面 (`<ExperimentList />`)
- `/tasks` : タスク一覧画面 (`<TaskList />`)
- `/filters` : フィルタ管理画面 (`<FilterList />`)

共通レイアウト (`<Layout />`) が全画面をラップし、ヘッダーのタブナビゲーションを提供します。
