from enum import StrEnum


class ApiModes(StrEnum):
    START = "START"
    STOP = "STOP"
    NOT_RUN = "NOT_RUN"
    RESTART = "RESTART"


class ApiModeNames(StrEnum):
    START = "API is running"
    STOP = "API is stopped"
    NOT_RUN = "API is not running"
