テーブル設計

condisionとexecutionとresultを分割する案で2時間位悩んだが、結局1条件1実行の方針のため統合
ジョブキューパターン

## バックエンド
なんかcargoが効かないので応急処置
export PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:$PATH"

実験デフォルト値は
src/dto/experiment.rs
に記述

sqlx で生のsql書いていたらアホの長さになったのでormを採用
```bash
cargo install sea-orm-cli
# 使用 entity自動生成
sea-orm-cli generate entity -u postgres://user:password@localhost/db_name -o src/entities
```

- migrate機能もあるらしいが sqlx migrate と競合するので使用しない
```bash
# マイグレーションファイルの新規作成
sea-orm-cli migrate generate create_experiments_table

# マイグレーションの実行（DBにテーブルを作成）
sea-orm-cli migrate up

# 直前のマイグレーションを取り消し
sea-orm-cli migrate down
```


## DB
- 基本操作
- 基本操作
```postgreSQL
-- DB一覧
\l
-- DB切り替え
\c <db>
-- テーブル一覧
\dt
-- テーブル定義取得
\d <table>
-- 権限表示
\du
-- whoami
SELECT current_user;
```
