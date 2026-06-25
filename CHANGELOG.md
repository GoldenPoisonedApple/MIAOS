# Changelog

## [0.5.1](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.5.0...v0.5.1) (2026-06-25)


### Features

* Add watermark key to experiment metrics in ExperimentList ([53b0884](https://github.com/GoldenPoisonedApple/MIAOS/commit/53b0884aa0e96dfcbf463ebbcb058c0ba6e43027))


### Bug Fixes

* fillterのenabledを先に評価 ([f0641e4](https://github.com/GoldenPoisonedApple/MIAOS/commit/f0641e4dede2407ffa455f4d4141c6857b7918a2))
* task viewでマイレンダー新しい参照で再帰的に再計算される現象を修正 ([498a0a4](https://github.com/GoldenPoisonedApple/MIAOS/commit/498a0a448b9cfb0c22f3dfa04e2f6ccd3c019221))
* エラー修正 ([dca0a35](https://github.com/GoldenPoisonedApple/MIAOS/commit/dca0a35ac38a26512734880a1c4bbfbaccaef1d9))

## [0.5.0](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.4.0...v0.5.0) (2026-06-25)


### ⚠ BREAKING CHANGES

* offline liraの手法が間違えて居たので修正

### Features

* [#27](https://github.com/GoldenPoisonedApple/MIAOS/issues/27) backend filterのdelete実装 ([f57975b](https://github.com/GoldenPoisonedApple/MIAOS/commit/f57975bc649e6918255c10eab36ca46b75a43645))
* [#30](https://github.com/GoldenPoisonedApple/MIAOS/issues/30) 画像をそのまま表示するように変更 ([4e7bf01](https://github.com/GoldenPoisonedApple/MIAOS/commit/4e7bf01de84e6d60dcf5e1ff72aea5ed91a2b4c7))
* frontendをフィルタ対応 ([ff18202](https://github.com/GoldenPoisonedApple/MIAOS/commit/ff18202c80f6d6197b6fb9f150c56c991db2ff0a))
* Json 変更に伴う変更(worker) ([905233b](https://github.com/GoldenPoisonedApple/MIAOS/commit/905233b4461aa65e2d48fd6d8b3a048f5afc8c2c))
* Json変更に伴う変更反映 ([4b14d5d](https://github.com/GoldenPoisonedApple/MIAOS/commit/4b14d5d9faae95c076afda15462d5aa3330f702c))
* liraの出力グラフ追加 ([8d5665c](https://github.com/GoldenPoisonedApple/MIAOS/commit/8d5665c240c2da4b23a6109124db80dbe2403cdd))
* offline liraの手法が間違えて居たので修正 ([95cd0ea](https://github.com/GoldenPoisonedApple/MIAOS/commit/95cd0ea6bfcb4e68bfa23c831b25575c2b3be1d4))
* test作成 ([9abef34](https://github.com/GoldenPoisonedApple/MIAOS/commit/9abef34dcc55cb537bfdd19be46182cf83ffd66c))
* watermarkを独立(backend) ([2bbb710](https://github.com/GoldenPoisonedApple/MIAOS/commit/2bbb710772c12be179a78d38e9ccdaec5146face))
* 数値データは右寄せに ([4e85bc3](https://github.com/GoldenPoisonedApple/MIAOS/commit/4e85bc38c93e49e1f74d74686f3cd89ba48db51b))
* 表示見やすいように ([ec94500](https://github.com/GoldenPoisonedApple/MIAOS/commit/ec94500aa0d8a4dc0ad4c004a61091f284d49861))
* 透かし単体検証実験追加 ([a078f37](https://github.com/GoldenPoisonedApple/MIAOS/commit/a078f373cec532d308478f1c34581eafcd423bef))


### Bug Fixes

* Watermarkのデフォルト値が拒否されていたのでOptionにして記載しないように変更 ([77abb0d](https://github.com/GoldenPoisonedApple/MIAOS/commit/77abb0de10b0f0cd669106acab2601feec87ce60))

## [0.4.0](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.3.0...v0.4.0) (2026-06-21)


### ⚠ BREAKING CHANGES

* frontendとworkerを対応

### Features

* backendのフィルタ対応 ([6ea0459](https://github.com/GoldenPoisonedApple/MIAOS/commit/6ea04599d9ac6357bbbfdef3bf05b48fae470922))
* celeryのworkerの状態確認コマンド追加 ([2597f5c](https://github.com/GoldenPoisonedApple/MIAOS/commit/2597f5ca764e4895c1f0035cee140921f66c05a3))
* frontendとworkerを対応 ([952ba40](https://github.com/GoldenPoisonedApple/MIAOS/commit/952ba40dd3c91dc794d08a6a4f1b85496aacd1c2))
* フィルタ ([3230a43](https://github.com/GoldenPoisonedApple/MIAOS/commit/3230a4378f0c0899e8d93c39519c6a036ff5ba16))

## [0.3.0](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.2.2...v0.3.0) (2026-06-18)


### ⚠ BREAKING CHANGES

* 共通ホームディレクトリ用の直列ジョブを追加

### Features

* 共通ホームディレクトリ用の直列ジョブを追加 ([7f3d8df](https://github.com/GoldenPoisonedApple/MIAOS/commit/7f3d8dfc34bacc5b37898d569bb11fc82c0d4c3b))

## [0.2.2](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.2.1...v0.2.2) (2026-06-18)


### Features

* デプロイを走らせる ([182ec55](https://github.com/GoldenPoisonedApple/MIAOS/commit/182ec552afa7116604049ae118afb29e5d4ace33))

## [0.2.1](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.2.0...v0.2.1) (2026-06-17)


### Features

* cd-buildのキャッシュ改善 ([7edb3a0](https://github.com/GoldenPoisonedApple/MIAOS/commit/7edb3a06614a1aa9c8bbd19c41c0e66e8d4f7fac))

## [0.2.0](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.1.3...v0.2.0) (2026-06-17)


### ⚠ BREAKING CHANGES

* 表示カラムの設定永続化with localStorage

### Features

* 表示カラムの設定永続化with localStorage ([fc7a129](https://github.com/GoldenPoisonedApple/MIAOS/commit/fc7a1295cfda5a98a13e8b7db152e20b575b147a))

## [0.1.3](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.1.2...v0.1.3) (2026-06-17)


### Features

* ワークフローのテスト用 ([8455945](https://github.com/GoldenPoisonedApple/MIAOS/commit/8455945de0f77a5ab9b25d721ddd86b7bbe06750))
* ワークフローのテスト用 ([f93cca3](https://github.com/GoldenPoisonedApple/MIAOS/commit/f93cca38d563d4e1f5183cc84e2e8c24275c54f0))

## [0.1.2](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.1.1...v0.1.2) (2026-06-17)


### Features

* cdの分離、releaseの一本化 ([fb3319e](https://github.com/GoldenPoisonedApple/MIAOS/commit/fb3319e380f2ff98d2e1552acd15dd75475d1ec5))
* PATを使用してworkflowを起動するように変更 ([33142ba](https://github.com/GoldenPoisonedApple/MIAOS/commit/33142baa57ac95e8eb3532b32b8035a5af8d45da))
* releaseの時のみcdが走るように変更 ([0a4ce24](https://github.com/GoldenPoisonedApple/MIAOS/commit/0a4ce24b49e15bc9cbd5382a50a4400032a6fcdb))


### Bug Fixes

* cacheの保存をpermissionの問題で弾かれている問題を解消 ([3ff0c27](https://github.com/GoldenPoisonedApple/MIAOS/commit/3ff0c27e9ce609dcbe22adc20fdff9305035fab2))
* deployのタグ指定をShort SHAに変更 ([c1a54c5](https://github.com/GoldenPoisonedApple/MIAOS/commit/c1a54c525379ea4b0d8b73ec08ff2f234650540c))
* schema/openapi.jsonの変更によるビルド廃止 ([a76a477](https://github.com/GoldenPoisonedApple/MIAOS/commit/a76a477a65362601e24275f9b653e1e4071b3834))
* スペース2に修正 ([4d0e998](https://github.com/GoldenPoisonedApple/MIAOS/commit/4d0e998254553df2aaf077fba48737e8ece07f02))

## [0.1.1](https://github.com/GoldenPoisonedApple/MIAOS/compare/v0.1.0...v0.1.1) (2026-06-16)


### Features

* add release-please ([d53bb73](https://github.com/GoldenPoisonedApple/MIAOS/commit/d53bb73e002dd92f3994df8f3609f633ec5948fe))
* ciのキャッシュを強く ([ede7957](https://github.com/GoldenPoisonedApple/MIAOS/commit/ede7957a05d0b4814957c63fa2028d2674f3dfe7))

## Changelog
