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
│   └── useDynamicColumns.ts # JSON型の動的キー抽出・カラム生成ロジック
│
├── components/      # 汎用コンポーネント層
│   ├── layout/      # 画面の共通レイアウト (Header, Navigation 等)
│   └── ui/          # 画面に依存しない再利用可能なUI部品
│       ├── Badge/   # ステータス表示バッジ
│       ├── Button/  # 共通ボタン
│       ├── ConfirmModal/ # 削除確認等の共通モーダル
│       ├── DataTable/    # TanStack Tableをラップした高機能テーブル
│       ├── KeyValueEditor/ # 辞書型(JSON)編集用エディタ
│       └── Modal/   # モーダル基底コンポーネント
│
├── pages/           # 画面（ルーティング）層
│   ├── Experiments/ # 実験一覧・管理画面
│   │   ├── ExperimentList.tsx
│   │   └── components/
│   │       └── CreateExperimentModal.tsx # 実験作成モーダル
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
- **動的カラムの展開**: JSON（辞書型）のプロパティ（例: `hyperparameters`）は、`useDynamicColumns` フックにより内部のキーを抽出し、テーブルのフラットなカラムとして動的に展開されます。
- **カラムの制御**: カラムの表示/非表示の切り替え、および `@dnd-kit` を用いたヘッダーのドラッグ＆ドロップによる並び替えが実装されています。

### 3.3 コンポーネントのカプセル化
スタイリングには **CSS Modules** (`*.module.css`) を採用しています。クラス名のスコープが各コンポーネント内に閉じられるため、他のコンポーネントへの意図しないスタイルの影響を防ぎ、保守性を高めています。

## 4. ルーティング設計

`react-router-dom` を用いて、URLベースの画面遷移を実現しています。

- `/` : `/experiments` へリダイレクト
- `/experiments` : 実験一覧画面 (`<ExperimentList />`)
- `/tasks` : タスク一覧画面 (`<TaskList />`)

共通レイアウト (`<Layout />`) が全画面をラップし、ヘッダーのタブナビゲーションを提供します。
