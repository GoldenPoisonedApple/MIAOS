

# モデル
1出力で、BCEWithLogitsLoss(純粋な2値分類のため、ONとOUTの2出力よりも 1出力で0～1の方が一般的)

# 過学習対策
Stratified(IN/OUT比維持) Group(シャドー)
(IN/OUTペア)シャドー単位でのLOOCV(Leave-One-Out Cross-Validation: 1件だけテストに回す交差検証)を汎化性能指標とする
と思っていたが、ちょっと100件でやるには多いので k-fold: kは10件とする
層化はするまでもない(学習とテストでINとOUTの比率は同じのため)

early stopping導入、これもシャドーペアで分割してTrain/Validation
これによりattachmodelのepoch数は廃止


optuna使うか....
使用するハイパーパラメータの査定は必要
- learning_rate(1e-5 - 1e-3)
- weight_decay（L2正則化強度）(1e-5 - 1e-1)
- 隠れ層数(0-1)
- 隠れ層サイズ(8-128)
- dropout率(0-0.5)


k-fold訓練でのテストデータを全て集めて、評価データの結果を用いる

score = k-foldのmean(accuracy) - λ std(accuracy): λ: 未知モデルへの安定性 0.5や1、2が多め
か、今回は低FPRでの性能を見たいので
score = mean(TPR@FPR=0.01) - λ std(TPR@FPR=0.01)
でも良い





平坦化した対角 LDAの分母　within_class の方が推奨っぽいなこれ

# Todo
とりあえず、平均での結果をだしてるが、結果によっては中央値は最頻値も検討
と言うかK枚毎で結果が出てるのが間違いで、K枚で1つの結果まで圧縮するのが一番いいのでそうするようにする

現時点で最後のFPRは24データのみなのでFPRとかは当てにならん
K枚だすタイプのやつはもうほとんど意味ないな～って思ったりした