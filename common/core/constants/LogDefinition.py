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
CONSOLE_FORMAT: Final[str] = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>[{level}]</level>{extra[level_padding]} | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
LOG_MAX_SIZE_MEGABYTES: Final[int] = 10
COMPRESSION = "zip"


LOG_LEVEL = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET"]


def console_format(record):
    """Only DEBUG records include the source location; all levels keep colors."""
    template = CONSOLE_FORMAT
    if record["level"].name != DebugLevels.DEBUG:
        template = template.replace(
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - ", ""
        )
    record["extra"]["level_padding"] = " " * (7 - len(record["level"].name))
    return template + "\n{exception}"
