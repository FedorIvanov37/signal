from sys import stdout
from loguru import logger
from functools import wraps
from warnings import filterwarnings
from logging import getLogger, NullHandler, CRITICAL
from common.api.core.ApiLogHandler import ApiLogHandler
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.data_models.Config import Config
from common.lib.constants import LogDefinition

from logfire import (
    configure as configure_logfire,
    log as logfire_log,
    LogfireLoggingHandler
)


def process_notset_log_level(function):

    # Remove all the handlers and stop processing when debug level is NOTSET

    @wraps(function)
    def wrapper(self, *args, **kwargs):

        if self.config.debug.level != LogDefinition.DebugLevels.NOTSET:
            return function(self, *args, **kwargs)

        return self.remove()

    return wrapper


class Logger:
    rotation = f"{LogDefinition.LOG_MAX_SIZE_MEGABYTES} MB"
    format = LogDefinition.LOGFILE_DATE_FORMAT
    compression = LogDefinition.COMPRESSION
    _config: Config

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    def __init__(self, config: Config):
        self.config = config
        self.setup()

    @process_notset_log_level
    def setup(self, wireless_handler=None, filename=TermFilesPath.LOG_FILE_NAME):
        self.remove()
        self.add_file_handler(filename=filename)
        self.add_logfire_handler()
        self.add_api_handler()

        if wireless_handler:
            self.add_wireless_handler(wireless_handler)

    @staticmethod
    def remove():
        logger.remove()

    @process_notset_log_level
    def add_api_handler(self):
        handler = ApiLogHandler()

        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            log = getLogger(name)
            log.handlers = [handler]
            log.propagate = False
            log.setLevel(self.config.debug.level)

    @process_notset_log_level
    def add_logfire_handler(self):

        if not self.config.debug.logfire_integration:
            return

        try:
            filterwarnings(
                "ignore",
                message=r"Logfire API is unreachable, you may have trouble sending data\..*",
                category=UserWarning,
            )

            loggers = [
                "opentelemetry",
                "opentelemetry.exporter.otlp",
                "opentelemetry.sdk",
                "logfire._internal.exporters.wrapper"
            ]

            for logger_name in loggers:
                getLogger(logger_name).setLevel(CRITICAL)

            configure_logfire(console=False)

        except Exception:
            return

        logger.add(
            LogfireLoggingHandler(fallback=NullHandler()),
            format=self.format,
            level=self.config.debug.level,
        )

    @process_notset_log_level
    def add_file_handler(self, filename=TermFilesPath.LOG_FILE_NAME):

        logger.add(
            filename,
            format=self.format,
            level=self.config.debug.level,
            rotation=self.rotation,
            compression=self.compression,
            backtrace=False,
            diagnose=False,
            retention=self.config.debug.backup_storage_depth if self.config.debug.backup_storage_depth_exists else 0,
        )

    @process_notset_log_level
    def add_stdout_handler(self):

        logger.add(
            stdout,
            format=self.format,
            level=self.config.debug.level,
            backtrace=False,
            diagnose=False,
        )

    @process_notset_log_level
    def add_wireless_handler(self, wireless_handler) -> int:

        handler_id = logger.add(
            wireless_handler,
            format=LogDefinition.DISPLAY_DATE_FORMAT,
            level=self.config.debug.level,
            backtrace=False,
            diagnose=False,
        )

        return handler_id
