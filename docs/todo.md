# 統計的アプローチを追加

シャドウのペアの差分 IN - OUT
重みw:  平均/(分散 + λ): λは正規化項

バイアスb: IN/OUT境界を作成
ペアの中点m=(IN+OUT)/2、を全てのペアで平均
この平均中点を通る境界線は wm + b = 0 より b = -wm

最終的に
score = wx+b

```python
# 1. ペア特徴の取得: (n_pairs, NUM_CLASSES)
# LF_MIA では 1枚、LF_Mult 系では K枚平均の特徴が返る
in_feats, out_feats = self._collect_shadow_pair_features(shadow_models)
# 2. ペア差分と中点
diffs = in_feats - out_feats                    # (n_pairs, C)
midpoints = 0.5 * (in_feats + out_feats)        # (n_pairs, C)
# 3. 対角LDAによる重みとバイアスの算出
mean_diff = diffs.mean(axis=0)                  # (C,)
var_diff = diffs.var(axis=0, ddof=1) + reg_lambda    # (C,) 正則化項 λ=1e-3
w = mean_diff / var_diff                        # (C,)
b = - float(w @ midpoints.mean(axis=0))         # スカラー
# 4. ターゲット推論 (target_feat: (C,) または (K, C) の平均)
logit = float(w @ target_feat + b)
score = 1.0 / (1.0 + np.exp(-logit))
```


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


# というか今の攻撃モデル
ROC-AUC見れるんじゃないのか？
統計的アプローチとの比較もしたいので、
本番データでのROC図を作成

それぞれのターゲットでの点を図に表示(ターゲット適応割合毎に色分けしたそれぞれ100枚の合成画像の結果のヒストグラム)



all_scoresがdbに保存するには値が多すぎるのでmetricsで返すのを止め、グラフにしてファイルを返すようにする。
一つのグラフにターゲット毎のヒストグラムを描画。それぞれ色分けをする。INは赤、OUTは青。
適応割合が1のターゲットは最も彩度の高い赤、適応割合が下がるにつれて彩度が下がるようにして。OUT(適応割合が0)は全部同じ色(青)で良い。
凡例ラベルもちゃんと書いて
それぞれについて、meanの縦棒を描画。varの正規分布線も、色分けの色と同様の色でそれぞれ描画する。
うーん。やっぱり見ずらいだろうから、それに加えてFacet(小さなサブプロット)で6×4で描画したグラフも出力するようにして。
うーん。あと一枚で見れるようにバイオリンプロットも出力して。

また、all_scoresで、mia_attack.pyと同じようにROC曲線の描画をして欲しい。fraction>0のターゲットのデータはIN(1)、fraction=0のターゲットのデータはOUT(0)でよろしく

あと、comprehensive_evaluateでもROC曲線の描画をよろしく。fraction>0がINでfraction=0がOUTね

聞くべき事があれば色々要件が確定するまで何度でも聞いていいよ

# Todo

とりあえず、平均での結果をだしてるが、結果によっては中央値は最頻値も検討
と言うかK枚毎で結果が出てるのが間違いで、K枚で1つの結果まで圧縮するのが一番いいのでそうするようにする

現時点で最後のFPRは24データのみなのでFPRとかは当てにならん