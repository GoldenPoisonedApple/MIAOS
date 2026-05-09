backend/
├── Cargo.toml
├── Dockerfile
└── src/
    ├── main.rs          # アプリケーションのエントリポイント（DB接続、サーバー起動）
    ├── config.rs        # 環境変数 (DATABASE_URLなど) の読み込み・管理
    ├── error.rs         # アプリケーション共通のエラー定義 (カスタムエラーとHTTPステータスコードの紐付け)
    ├── routes/          # ルーティング設定
    │   ├── mod.rs
    │   └── tracking.rs  # /api/v1/tracking に関するルーティング
    ├── handlers/        # リクエストを受け取り、レスポンスを返す処理 (コントローラー層)
    │   ├── mod.rs
    │   └── tracking.rs  # POST処理の入り口
    ├── models/          # データベースのテーブルに対応する構造体や、リクエストJSONの構造体
    │   ├── mod.rs
    │   ├── experiment.rs # experiments テーブル用
    │   ├── details.rs    # details_offline_lira, details_shokri テーブル用
    │   └── payload.rs   # ワーカーから送られてくるJSONをパースするための構造体
    └── repositories/    # データベースとの通信（SQLの実行）をカプセル化する層
        ├── mod.rs
        └── tracking.rs  # INSERT文を実行するロジック