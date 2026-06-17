# MIAOS
Membership Inference Attack Orchestration System

実験はidで管理することに
<- わざわざ名前にしなくても良い、idでも一意性が付く、検索容易性がある、覚えやすく入力しやすい

git ls-files | tree --fromfile
sudo chown -R $USER:$USER .


## compose
composeは基本的にcontainer_nameはつけないほうがいいかと: 一貫性が無くなる, スケールできなくなる, ネットワーク解決が名前依存になってしまって困る
ctl+shift+P
>Dev Containers: Open Folder in Container
で.devcontainerが存在する場所を開く
選択して実行
.devcontainerはそれぞれのコンテナのrootに設置してもいいかもしれない

ビルドはDockerfileでcomposeは起動や依存関係管理なのね

logはプロジェクト名が同じなら、共有されるらしい。

yamlのブロックスカラー
```yaml
- >
	hoge
	fuga
# ["hoge fuga\n"] スペース変換
- |
	hoge
	fuga
# ["hoge\nfuga\n"] 改行のまま
```

## バックエンド
なんかcargoが効かないので応急処置
```bash
export PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:$PATH"
```

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

- テスト
```bash
# DBのテストは順次実行にしたい
cargo test -- --test-threads=1
# 特定のものだけ実行 ログも見る
cargo test repositories::task -- --nocapture
```
なんと#[sqlx::test]にするとテストごとに独立したトランザクションを実施し終了時にロールバックで戻すので並列で行うことが可能になる

色々考えたがいい方法が無かったので
noteが backend_test のデータはテスト用とするカスの手法
削除されるので注意

リポジトリのこの処理はserviceかなと一瞬考えたが、sea_ormの知識をrepository以外に流出させるのは良くないのでそのままに
```rust
// DTOをActiveModelに変換
let active_model = ActiveModel::from(request);
```

本当はテスト用の環境と本番用の環境を分けたいよ

- トランザクション
推奨設計1: 補償トランザクション（Sagaパターン / Undo）
異なるデータストア（PostgreSQLとRedis）をまたぐ処理の場合、単一のDBトランザクションでロールバックすることはできません。そのため、**後続の処理が失敗した場合は、先行して成功した処理を取り消す（Undoする）**というアプローチが一般的です。
らしいので補償トランザクション

// createの処理については idがないのでどうしようもない 新規作成時に複雑なビジネスロジックがないのでDTOをそのままrepositoryにねじ込む構造
// 複雑なロジックがある場合は、serviceとrepositoryの間のDTOを作成するのが良いかと

- sea_ormのせいで綺麗なアーキテクチャにできない
ActiveModelをサービスに流出させられないし、Rich Domain modelにしようとしたら、Updateの所で変更を通知しないとUpdateされないとかいう謎仕様があるので、専用にModel -> ActiveModel変換仕様を作ってるし、結局Serviceに流出させなくてもEntityがやられてるから意味ない
綺麗にしようとしても良いがボイラープレートが大量に発生するので、変更が多いと考えるとやらないほうが良い
Rich Domain Modelの痕跡
entities/experimentのcomplete

- エクストラクタ
URLのパスから？（例: /experiments/123） → Path<i64> を使う
URLのクエリ文字列から？（例: /experiments?id=123） → Query<T> を使う
リクエストのボディ（JSON）から？（例: {"id": 123}） → Json<T> を使う
HTTPヘッダーから？ → HeaderMap などを使い

- ハンドラーのテスト
将来的にしたいときのために、ServiceをTraitにしても良いが、最適化の問題だったり、面倒だったりするので、E2Eテストと割り切ることもできる。
まぁモックいらん側の考えでやれば、今回は外部が存在しないのでモックいらんからそのままやればいいんだけどさ

- サーバー動作確認
```bash
# 取得
curl -X GET http://localhost:3000/api/experiments
# 作成
curl -X POST http://localhost:3000/api/experiments -H "Content-Type: application/json" -d '{"name":"test"}'
# 取得
curl -X GET http://localhost:3000/api/tasks
```

- ルーティング
"/api/experiments",
"/api/experiments/claim"
など個別対応にも関わらず、内部Jsonのidでやってるのあまりよくない設計な気がする
ちゃんとidは外部に出してあげた方が内部の処理が綺麗



- utoipa APIの仕様書とかを勝手に書いてくれるやつ
人用
http://localhost:3000/docs/
機械用
http://localhost:3000/api/openapi.json


- CI用にOpenAPI仕様を書き出し
バイナリクレートに書き出し処理記述
```bash
cargo run --bin generate_openapi
```
バイナリクレート用意すると、cargo runでどれを起動すればいいかわからんって言われるから
Cargo.tomlに追記
```toml
default-run = "server"
```
でもよく考えたらURLでJSON取ってこれるからいらんかった

- ホスト側の環境構築
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# シェル再起動

# Dockerfileの rust:1.93 に固定
rustup toolchain install 1.93
rustup default 1.93

# 現在のバージョン確認
rustc --version
cargo --version
```


## フロントエンド
utoipaとの連携

- openapi-typescript + openapi-fetch: 堅実、人間多め
- orval + TanStack Query: 楽、自動化

どちらもかなり拮抗、かなり悩むところだが前者を
仕様変更が予想されるので前者を

- 導入
```bash
npm install openapi-fetch @tanstack/react-query
# npm install -D openapi-typescript が怒られたので
npm install -D typescript@~5.8.0 openapi-typescript
```
package.jsonのscripts追記
```json
"scripts": {
	# 追記
	"gen:api": "openapi-typescript http://backend:3000/api/openapi.json -o src/api/schema.d.ts",
	"gen:api:local": "openapi-typescript ./openapi.json -o src/api/schema.d.ts"
	...
}
```

- 生成
```bash
npm run gen:api
```

生成も、どうせ変更を加えた時にするので、gitignoreに入れない方がいいらしい
持ってきてそのまま実行可能だし
複数人開発となるとコンフリクトの温床となるため、やらんほうがいいらしい

## DB

テーブル設計

condisionとexecutionとresultを分割する案で2時間位悩んだが、結局1条件1実行の方針のため統合
ジョブキューパターン

IDはsignedなのでby_id指定はi64で良い、u64だとオーバーフローリスクも存在する
マイナス値が存在しないはずである場合は、id > 0 みたいな制約でやってあげればよい


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

## Redis

```bash
# redisのcli起動
redis-cli
# キー確認
KEYS *
# キューの中身確認 0(最初)から-1(最後まで)
LRANGE celery 0 -1
```

celeryはタスクを取得するときにBRPOPLPUSHでキューから処理中リスト(redisの内部)に移動する
そのためacks_late=Trueしても他のworkerが仕事を取ることは無い


#### なんと
Redisをブローカーとして使用した場合に、送信するメッセージに exchange キーを含め忘れると言うバグがあり、直されていない
似たようなことをやるならRabbitMQがよさそうではある

- RabbitMQ
ACK: 処理が成功した までqueueに残る
再送制御可能
routing設定可能
などよりどりみどり

### フォークして修正する
ただ、せっかくなので持ってきて自分で修正したのを使ってみようと思う
どこを修正すればいいかはPRが出ているので、それを参考に(PR出てるけど更新が止まってるので...)
https://github.com/rusty-celery/rusty-celery/pull/253
デメリットとして、更新が追えなくなるが、更新されてないので無問題

公式からフォーク、クローン、patchとして使用
```toml
# ビルド時に、公式の0.5.5を手元のlibs/rusty-celeryで上書きする 送信メッセージにexchangeキーがないためエラーとなる パッチコードで上書き
[patch.crates-io]
celery = { path = "libs/rusty-celery" }
```

### ライセンス
orchestrator/backendにて
rusty-celeryをフォーク、修正して使用しているため同様にApache License 2.0を採用

LICENSE の保持
著作権表示の保持
NOTICE の保持（存在する場合）

Apache License 2.0ライセンス
- ライセンスのコピーを残す: LICENSEが入ってるので消さなければよい
- 著作権表示を残す: Copyrightが入っているので消さなければよい
- 変更を明記: // Modified by []みたいな感じ
- NOTICEは存在しなかった
元の配布物に NOTICE が含まれていた場合その派生物を再配布するならNOTICE に含まれる内容を「読める形で」保持しなければならない

libs/にダウンロード
.gitignoreには含めず

/src/broker/redis: エラー修正
/src/protocol/mod.rs: exchangeキーが無くてエラーになる問題の解消

rust-analyzerではまだ問題と赤くなっていたり: 今のビルドで有効なfeatureの解釈、名前解決がコンパイラとずれることによるもの
統合テストが通っていなかったりするが: AMQPが起動していなくて、環境変数がないため怒られている。 --libのテストは全て成功してるので無問題



### Celery
基本的にbody(base64)部分の構造は以下
```rust
args = [
    Array [],	// positional args（位置引数）用スロット 通常の引数体系 現代ではあまり使わない
    Object { params: {...} }, // keyword用スロット key=value体系 辞書型
    Object { callbacks/chains... } // Celery制御情報
]
```
celery -A src.workers.celery_tasks inspect
で
active
reserved
scheduled
stats
registred
conf
とか見れるっぽいね


- 例
Tasks: [Task { id: 1107cc26-b460-4405-8b07-96ff7007f7d2, task: "mia_tasks.run_attack", args_positional: Array [], args_keyword: Object {"params": Object {"base_experiment_id": Null, "batch_size": Number(10), "experiment_id": Number(1), "hyperparameters": Object {}, "load_attack_model": Bool(false), "load_shadow_model": Bool(false), "load_target_model": Bool(false), "max_epochs": Number(10), "method": String("OfflineLira"), "name": String("test"), "notes": String("backend_test"), "num_shadow_models": Number(10), "seed": Number(10), "shadow_test_size": Number(10), "shadow_train_size": Number(10), "target_test_size": Number(10), "target_train_size": Number(10)}}, args_control: Object {"callbacks": Null, "chain": Null, "chord": Null, "errbacks": Null} }, Task { id: 676a5a77-8464-424f-bbad-19599fb20079, task: "mia_tasks.run_attack", args_positional: Array [], args_keyword: Object {"params": Object {"base_experiment_id": Null, "batch_size": Number(10), "experiment_id": Number(1), "hyperparameters": Object {}, "load_attack_model": Bool(false), "load_shadow_model": Bool(false), "load_target_model": Bool(false), "max_epochs": Number(10), "method": String("OfflineLira"), "name": String("test"), "notes": String("backend_test"), "num_shadow_models": Number(10), "seed": Number(10), "shadow_test_size": Number(10), "shadow_train_size": Number(10), "target_test_size": Number(10), "target_train_size": Number(10)}}, args_control: Object {"callbacks": Null, "chain": Null, "chord": Null, "errbacks": Null} }, Task { id: d2e8213d-6412-4b1f-9111-f3dfbaa805ef, task: "mia_tasks.run_attack", args_positional: Array [], args_keyword: Object {"params": Object {"base_experiment_id": Null, "batch_size": Number(10), "experiment_id": Number(1), "hyperparameters": Object {}, "load_attack_model": Bool(false), "load_shadow_model": Bool(false), "load_target_model": Bool(false), "max_epochs": Number(10), "method": String("OfflineLira"), "name": String("test"), "notes": String("backend_test"), "num_shadow_models": Number(10), "seed": Number(10), "shadow_test_size": Number(10), "shadow_train_size": Number(10), "target_test_size": Number(10), "target_train_size": Number(10)}}, args_control: Object {"callbacks": Null, "chain": Null, "chord": Null, "errbacks": Null} }]


## MINIO
結局Previewが.logや.jsonはできないらしいので、仕組みを整える
手法が2つ
- Presigned URL: バックエンドは署名だけを行う、CDN(キャッシュとの相性が良い(証明付きURLが毎回同じため))、大ファイルでもバックエンドのメモリを食わない
	MINIOがクライアントから到達可能であること、URLの失効が時間でのみしか管理できない、実装コストがかからない
- Backend Proxy: 全てのリクエストがバックエンドを経由、MINIOはクライアントから完全に分離されている、認証・認可が厳密に可能

ワーカーからのアップロードは直接MINIOでやっているが、フロントからとの経路が違うので分けて考える
アップロードはこのままで良い(無駄にバックエンドの容量を食う必要がない)

ブラウザは全てバックエンドを通っていて、MINIOが内部ネットワーク完結なので Backend Proxy の方向性で

## worker
CIのためruffを導入

uv導入
依存関係を記述可能

```bash
pip install uv
# pyproject.tomlに依存関係記述
# lockファイル生成
uv lock
# 依存関係インストール
uv sync --frozen
# uvの環境で実行
uv run 
```


# モノレポ化しました
仕様変更、CI/CDが楽になる

git subtreeが良い

1. 新しいリポジトリを作成
2. orchestratorを統合してマージ
	- git remote add orchestrator git@github.com:GoldenPoisonedApple/MIAOS.git
	- git fetch orchestrator
	- git subtree add --prefix=orchestrator orchestrator main
3. workerを統合してマージ
	- git remote add worker git@github.com:GoldenPoisonedApple/mia-test.git
	- git fetch worker
	- git subtree add --prefix=worker worker main

Turborepo: モノレポ用ビルドシステム(変更検知、再ビルド) 今回は使わないけどあってもいいね CIやbuild用の最適化ツールとして解釈している

これでテスト環境をまるまる簡単に構築できるようになったので、わざわざテスト用のワーカー作る必要が無くなった

# CI
それぞれの環境でのlint, format
OpenAPIでの整合性確保
- openapi.jsonはGit管理するのがベストプラクティスらしい
	APIの変更がgit管理で可視化される, CIの完全並列化, APIの仕様だけ先に変更することで他をブロックせずに開発可能

cargo auditを実行したいところだが、依存クレートの依存クレートが怒られていて非常に面倒くさいためやっていない

本番ビルドのテストまではするが、PushはCDで行う: CIの責務は壊れていないかどうかの確認であるため
ビルドのキャッシュは共有している: クリーンな方がいいのだろうけど重いので

# CD
GHCR(GitHub Container Registry)っていう成果物のコンテナ置き場にアップロード
各PCにssh接続して、pullしてくる方針に

本当はk3sとかでArgoCD (GitOps)でやるのが良いんだろうけど大変すぎる

digest運用とタグ運用
- degest: 完全固定 再現性 動的更新が不可能 本番リリース向け
- tag: 自動更新可能 手動更新可能 事故は発生する
tagで運用する

いくらやってもmatrixがうまくいかん
原因: Secretのマスキングは「登録されたSecret値がGITHUB_OUTPUTに現れたら伏字にする」という仕組み。つまり Secretのまま使う限り、どう書いてもGITHUB_OUTPUT経由では値が消える。
こいつが空文字列になる
```yaml
    outputs:
      # steps.set-matrixの出力結果をジョブ全体の出力として定義
      hosts: ${{ steps.set-matrix.outputs.hosts }}
    steps:
      # validate
      # JSON配列 かつ 要素数が0より大きいかどうかをチェック
      - run: |
          echo '${{ secrets.WORKER_HOSTS }}' | jq -e 'type == "array" and length > 0'
      - id: set-matrix
        # GITHUB_OUTPUT環境変数(出力ファイル)にキーと値のペアを追記し、後続ジョブに渡す
        run: echo "hosts=$(echo '${{ secrets.WORKER_HOSTS }}' | jq -c '.')" >> "$GITHUB_OUTPUT"
```
どうしようもないのでbase64で入力、内部でデコードすることで違う値として伏字にされない

やったけど結局GitHubActionsの所に表示されちゃうからVariableで良かったかもな...

### GitHub
- Environmentsでssh情報とかのsecrets情報登録
- Actions -> General: Workflow permissions = Read and write permissions

## Release Please
- 必須設定
GitHub リポジトリ GoldenPoisonedApple/MIAOS で:

Settings → Actions → General
Workflow permissions で Read and write permissions を選択
その直下の Allow GitHub Actions to create and approve pull requests にチェック
Save


#### release-please-config.json
リリースバージョンの管理
- extra-files: リリース時に計算された新しいバージョン番号を自動で書き換えるファイル
.release-please-manifest.json のバージョンと同期
```json
"extra-files": [
  "orchestrator/backend/Cargo.toml",
  "worker/pyproject.toml"
]
```
- "release-type": "simple"
.release-please-manifest.jsonが必要
".": リポジトリルートのパッケージバージョンを指定
```json
{
  "version": "0.1.0"
}
```
feat, fix, chore, refactor, perf, docs, style, test
BREAKING CHANGE

```mermaid
sequenceDiagram
    participant Dev as 開発者
    participant Main as main
    participant CI as ci.yml
    participant RP as release-please.yml
    participant Build as cd-build.yml
    participant Retag as cd-retag.yml
    participant Deploy as cd-deploy.yml
    participant GHCR as GHCR
    participant Prod as 本番サーバー

    Dev->>Main: PR（feature → main）
    Main->>CI: pull_request
    CI->>CI: paths filter → 各コンポーネント検証

    Dev->>Main: Release PR merge
    Main->>RP: push
    RP->>Main: tag vX.Y.Z + GitHub Release（PAT）

    Main->>Build: tag push（v*.*.*）
    Build->>GHCR: push :SHORT_SHA, :latest

    par workflow_run（並行）
        Build->>Retag: completed
        Retag->>GHCR: retag :vX.Y.Z
    and
        Build->>Deploy: completed
        Deploy->>Prod: git checkout + deploy-*.sh
        Prod->>GHCR: pull :SHORT_SHA
    end
```

```mermaid
flowchart TB
    subgraph dev["開発フェーズ"]
        PR["PR → main"]
        PR --> CI["ci.yml<br/>paths filter"]
        CI --> B["Backend (Rust)"]
        CI --> F["Frontend (Node)"]
        CI --> W["Worker (Python)"]
    end

    subgraph release["リリースフェーズ"]
        Merge["Release PR merge"]
        Merge --> RP["release-please.yml"]
        RP --> Tag["tag vX.Y.Z 作成 (PAT)"]
        RP --> GHRel["GitHub Release 作成"]
    end

    subgraph cd["CD フェーズ（tag push トリガー）"]
        Tag --> Build["cd-build.yml"]
        Build --> GHCR1["GHCR push<br/>:SHORT_SHA, :latest"]
    end

    subgraph post_build["CD Build 完了後（workflow_run × 2、並行）"]
        Build --> Retag["cd-retag.yml"]
        Build --> Deploy["cd-deploy.yml"]
        Retag --> GHCR2["GHCR retag<br/>:SHORT_SHA → :vX.Y.Z"]
        Deploy --> Orch["SSH: orchestrator"]
        Deploy --> Workers["SSH: workers (matrix)"]
    end

    GHCR1 --> Retag
    GHCR1 --> Orch
    GHCR1 --> Workers
```


#### PAT
PAT: Personal Access Token
- 個人のアカウントでGitHub Actionsを実行するためのトークン

全体Settings -> Developer settings -> Personal access tokens -> Fine-grained PAT で作成
権限
- Contents: Read and write permissions
- Pull requests: Write permissions
- Actions: Read and write permissions
で特定リポジトリのみに限定して発行

Repository secrets: リポジトリ固有のシークレット: GH_PATなど環境に依存しないもの
Environment secrets: 環境固有のシークレット: ORCHESTRATOR_HOSTなど環境に依存するもの

## TODO
### 優先度: 高
フィルタ、順番情報をバックエンドに記録


### 優先度: 中

タスクの中に条件ぶち込まなくてもClaimの返り値で条件取得できるから、タスクにはidだけ入れておけばいいのでは？

強制終了でタスクがちゃんと戻るか検証

リリースとかTagとかのGitHubやりたいね


### 優先度: 低
MIAOS APIへの送信失敗: Time zone offset must be 1, 3, 5 or 6 characters
datetimeとかなんとかだった気がする
明示的FAILEDとかできるね今なら ACKでredisにもどせる

compose多すぎやしないか？

CORS設定とか


Dependabot というものがあるらしい
依存ライブラリのアップデートを自動で提案してくれるGitHubのボット



Pythonの型だとidが振ってこんぞ(正確には振ってくるけど型にした時に落ちる)
この実験から生成(同じ条件がセットされる)、ボタンがあると参照がらく


認証を入れられたらいいいね


## その他メモ
ワーカーからのアクセスもフロントエンドのところからリバースプロキシでやった方がいいのだろうか
3000番を公開するのはあまりよくないのかな
でもどのみちフロントから同じ所に経由するもんな....
でも一か所に固めた方が制御が楽か？

-> フロント、バック共に制御するリバースプロキシ(APIゲートウェイの層)を用意してやるという解決策が多いっぽい

tmux: ターミナルの分割、ウィンドウの分割を行うことができる