from __future__ import annotations

from PIL import Image

from src.data.decorations.watermark.filter import CIFAR_IMAGE_SIZE


class DisplayMaskDecorator:
    """指定矩形以外を黒塗りにする表示マスクデコレータ

    position は画像左上を原点とした、表示領域左上の (x, y) 座標。
    対象選定は FractionalDecorator が担当。
    """

    # 初期化
    def __init__(self, width: int, height: int, x: int, y: int):
        """表示領域の幅、高さ、x座標、y座標を指定"""
        if not 0 < width <= CIFAR_IMAGE_SIZE or not 0 < height <= CIFAR_IMAGE_SIZE:
            raise ValueError(
                f"width and height must be in 1..{CIFAR_IMAGE_SIZE}, "
                f"got width={width}, height={height}"
            )
        if not 0 <= x < CIFAR_IMAGE_SIZE or not 0 <= y < CIFAR_IMAGE_SIZE:
            raise ValueError(
                f"x and y must be in 0..{CIFAR_IMAGE_SIZE - 1}, got x={x}, y={y}"
            )
        if x + width > CIFAR_IMAGE_SIZE or y + height > CIFAR_IMAGE_SIZE:
            raise ValueError(
                f"mask region exceeds image bounds: "
                f"x={x}, y={y}, width={width}, height={height}"
            )

        self._width = width
        self._height = height
        self._x = x
        self._y = y

    def apply(
        self, image: Image.Image, *, global_idx: int, local_idx: int
    ) -> Image.Image:
        # 画像モードがRGBでない場合はRGBに変換
        if image.mode != "RGB":
            image = image.convert("RGB")

        # 黒塗りの新しい画像を作成
        masked = Image.new("RGB", image.size, (0, 0, 0))
        # 指定矩形切り出し（表示領域）
        left, top = self._x, self._y
        cropped = image.crop((left, top, left + self._width, top + self._height))
        # 切り出した画像を同じ位置に貼り付け
        masked.paste(cropped, (left, top))
        return masked
