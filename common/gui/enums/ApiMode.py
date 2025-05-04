from enum import StrEnum


class ApiModes(StrEnum):
    START = "START"
    STOP = "STOP"
    NOT_RUN = "NOT_RUN"


class ApiModeNames(StrEnum):
    START = "API is started"
    STOP = "API is stopped"
    NOT_RUN = "API is not started"
