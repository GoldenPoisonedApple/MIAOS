# MIAOS
Membership Infference Attack Orchestration System


実験はidで管理することに
<- わざわざ名前にしなくても良い、idでも一意性が付く、検索容易性がある、覚えやすく入力しやすい

次はリポジトリ全部一つにまとめた方がいいな...
その方が統合テスト楽だし、開発環境でもできるし...

sudo chown -R $USER:$USER .

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
http://localhost:3000/api-docs/openapi.json


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
	"gen:api": "openapi-typescript http://backend:3000/api-docs/openapi.json -o src/api/schema.d.ts",
	"gen:api:local": "openapi-typescript ./openapi.json -o src/api/schema.d.ts"
	...
}
```

- 生成
```bash
npm run gen:api
```

生成も、どうせ変更を加えた時にするので、gitignoreに入れない方がいいらしい

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
Apache License 2.0ライセンス
- ライセンスのコピーを残す: LICENSEが入ってるので消さなければよい
- 著作権表示を残す: Copyrightが入っているので消さなければよい
- 変更を明記: // Modified by []みたいな感じ

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


## TODO
### 優先度: 高
CI作る: テストの時はワーカー動かしてるとできないから、ワーカー閉じないとね
いや違う、redisだけは外部依存だからモックでテストするようにしないといけない taskのreposityでデフォルトテストはしない方向で
CIはMakefile作ろう
テストのタスクはタスク名を変えてあげた方がいいな(repository)

フィルタ、順番情報をバックエンドに記録


### 優先度: 中

多分 色んな所でMakefile作った方がいいな

タスクの中に条件ぶち込まなくてもClaimの返り値で条件取得できるから、タスクにはidだけ入れておけばいいのでは？

### 優先度: 低

CORS設定とか


こういうの見れたらいいよね
[Pending]  12件
[Running]   3件
[Success] 120件
[Failed]    2件


Pythonの型だとidが振ってこんぞ(正確には振ってくるけど型にした時に落ちる)
この実験から生成(同じ条件がセットされる)、ボタンがあると参照がらく


認証を入れられたらいいいね

## 疑問
ワーカーからのアクセスもフロントエンドのところからリバースプロキシでやった方がいいのだろうか
3000番を公開するのはあまりよくないのかな
でもどのみちフロントから同じ所に経由するもんな....
でも一か所に固めた方が制御が楽か？

-> フロント、バック共に制御するリバースプロキシ(APIゲートウェイの層)を用意してやるという解決策が多いっぽい