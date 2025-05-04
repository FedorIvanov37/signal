from typing import Final
from enum import StrEnum


class DebugLevels(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    NOTSET = "NOTSET"


DISPLAY_DATE_FORMAT: Final[str] = "{time:HH:mm:ss} [{level}] {message}"
LOGFILE_DATE_FORMAT: Final[str] = "{time:DD.MM.YYYY HH:mm:ss} [{level}] {message}"
LOG_MAX_SIZE_MEGABYTES: Final[int] = 10
COMPRESSION = "zip"


LOG_LEVEL = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET"]
