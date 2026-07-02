from torch.utils.data import Dataset


# 動的にTransformを適応するSubset
class TransformedSubset(Dataset):
    """
    Transromを動的に適応したSubset
    画像変形などを適応するトレーニングデータと、それらを適応しないテストデータで混在を防ぐ
    Args:
        dataset: データセット
        indices: インデックス
        transform: 変換
        sample_decorator: Normalize 前の PIL 段階で適用するサンプル装飾
    """

    def __init__(
        self,
        dataset,
        indices,
        transform=None,
        sample_decorator=None,
    ):
        self.dataset = dataset
        self.indices = indices
        self.transform = transform
        self.sample_decorator = sample_decorator

	# for文で回されたときに呼ばれる
    def __getitem__(self, idx):
        # インデックスを取得
        global_idx = self.indices[idx]
        # データセットから画像とラベルを取得
        x, y = self.dataset[global_idx]
        # 装飾がある場合は適用
        if self.sample_decorator is not None:
            x = self.sample_decorator.apply(x, global_idx=global_idx, local_idx=idx)
        # 変換がある場合は適用
        if self.transform:
            x = self.transform(x)
        return x, y

    def __len__(self):
        return len(self.indices)
