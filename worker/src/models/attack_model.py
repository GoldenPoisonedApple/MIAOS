import torch.nn as nn

class AttackNet(nn.Module):
    def __init__(self, input_dim):
        super(AttackNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            # 出力層: 2クラス (メンバー=1, 非メンバー=0)
            nn.Linear(64, 2)
        )

    def forward(self, x):
        return self.net(x)