from enum import Enum


class MiaMethod(str, Enum):
    LFMIA = "LfMia"
    # 手編集で追加: 透かしを複数画像に合成して攻撃する LF_MIA 派生手法
    # `make openapi` で再生成すると消えるため、サーバ側スキーマにも同値を追加すること
    LFMULTDIFFMIA = "LfMultDiffMia"
    LFMULTMIA = "LfMultMia"
    OFFLINELIRA = "OfflineLira"
    ONLINELIRA = "OnlineLira"
    SHOKRI = "Shokri"

    def __str__(self) -> str:
        return str(self.value)
