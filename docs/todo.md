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

0のみOUTでそれ以外INとなる。0をもう複数作っときゃ良かったなｧ...
まぁ別にTrain増やすくらいだったら問題ないな....。増やすか

それぞれのターゲットでの点を図に表示(ターゲット適応割合毎に色分けしたそれぞれ100枚の合成画像の結果のヒストグラム)