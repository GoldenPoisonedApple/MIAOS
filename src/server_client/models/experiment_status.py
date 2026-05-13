from enum import Enum


class ExperimentStatus(str, Enum):
    FAILED = "Failed"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    WAITING = "Waiting"

    def __str__(self) -> str:
        return str(self.value)
