from enum import Enum

class MiaMethod(str, Enum):
    OFFLINELIRA = "OfflineLira"
    SHOKRI = "Shokri"

    def __str__(self) -> str:
        return str(self.value)
