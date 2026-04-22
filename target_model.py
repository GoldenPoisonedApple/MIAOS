import torch.nn as nn

class TargetCNN(nn.Module):
    """CIFAR-100分類用のシンプルな畳み込みニューラルネットワーク"""
    def __init__(self):
        super(TargetCNN, self).__init__()
				# 1層目の畳み込み層
        # in_channels: 入力チャネル数 (RGBなので3)
        # out_channels: 出力チャネル数 フィルタ数=特徴マップ数
        # kernel_size: フィルタのサイズ (3x3)
        # padding: 画像の端の特徴を保持するための余白
        # (3, 32, 32) → (32, 32, 32)
        self.conv1 = nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, padding=1)
        # 1層目の最大プーリング層 プーリング: 画像サイズを縮小: 重要な特徴を抽出
        # MaxPool2d: 最大値を取る 今回は2×2の領域の最大値 画像サイズは半分
        # (32, 32, 32) → (32, 16, 16)
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)
        # 2層目の畳み込み層
        # (32, 16, 16) → (64, 16, 16)
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, padding=1)
        # 2層目の最大プーリング層
        # (64, 16, 16) → (64, 8, 8)
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)
        
        # 完全結合層 (Fully Connected Layer / Linear Layer)
        # CIFARの画像サイズは32x32。プーリングを2回(1/2 x 1/2 = 1/4)行うと、8x8になる。
        # 入力次元数: 64チャネル * 8 * 8 = 4096
        # (64, 8, 8) → (4096) → (128) → (100)
        self.fc1 = nn.Linear(in_features=64 * 8 * 8, out_features=128)
        self.fc2 = nn.Linear(in_features=128, out_features=100)
        
        # ReLU: 活性化関数 (Rectified Linear Unit)
        self.relu = nn.ReLU()
        
		# x: (バッチサイズ, 3, 32, 32)
    def forward(self, x):
        x = self.relu(self.conv1(x)) # 畳み込み層1 + 活性化関数
        x = self.pool1(x) # プーリング層1
        x = self.relu(self.conv2(x)) # 畳み込み層2 + 活性化関数
        x = self.pool2(x) # プーリング層2
        x = x.view(x.size(0), -1) # テンソルを1次元ベクトルに平坦化 3次元配列の枠を取っ払って1次元に変換する感じ (64, 8, 8) → (4096)
        # クラス分け
        x = self.relu(self.fc1(x)) # 完全結合層1 + 活性化関数
        x = self.fc2(x) # 注意: ここでSoftmaxは適用しない (CrossEntropyLossで処理するため)
        
        # (バッチサイズ, 100)
        return x