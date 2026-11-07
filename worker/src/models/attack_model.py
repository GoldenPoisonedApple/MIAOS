import torch.nn as nn


class AttackNet(nn.Module):
    def __init__(self, input_dim):
        super(AttackNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            # 出力層: 2クラス (メンバー=1, 非メンバー=0)
            nn.Linear(64, 2),
        )

    def forward(self, x):
        return self.net(x)


class BinaryAttackNet(nn.Module):
    """
    IN/OUT の 2 値分類を 1 出力（IN の logit）で行う攻撃モデル。BCEWithLogitsLoss で学習する。
    hidden_dim=None のときは隠れ層なし（ロジスティック回帰）。
    """

    def __init__(self, input_dim: int, hidden_dim: int | None, dropout: float):
        super().__init__()
        if hidden_dim is None:
            self.net = nn.Linear(input_dim, 1)
        else:
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                # 出力層: IN の logit 1 つ
                nn.Linear(hidden_dim, 1),
            )

    def forward(self, x):
        # (N, 1) -> (N,)
        return self.net(x).squeeze(-1)
