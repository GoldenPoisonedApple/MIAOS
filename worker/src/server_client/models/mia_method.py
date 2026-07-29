from enum import Enum


class MiaMethod(str, Enum):
    OFFLINELIRA = "OfflineLira"
    ONLINELIRA = "OnlineLira"
    SHOKRI = "Shokri"

    def __str__(self) -> str:
        return str(self.value)
