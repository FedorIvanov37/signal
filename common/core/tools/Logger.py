from sys import stdout
from loguru import logger
from functools import wraps
from warnings import filterwarnings
from logging import getLogger, NullHandler, CRITICAL
from common.api.tools.ApiLogHandler import ApiLogHandler
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.data_models.Config import Config
from common.core.constants import LogDefinition


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

        handler_id = logger.add(
            stdout,
            format=self.format,
            level=self.config.debug.level,
            backtrace=False,
            diagnose=False,
        )

        return handler_id

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
