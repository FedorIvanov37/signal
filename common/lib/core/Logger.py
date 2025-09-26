from sys import stdout
from loguru import logger
from logging import getLogger
from common.api.core.ApiLogHandler import ApiLogHandler
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.data_models.Config import Config
from common.lib.constants import LogDefinition
from common.gui.core.WirelessHandler import WirelessHandler


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

    def setup(self):
        self.remove()
        self.add_file_handler()

    @staticmethod
    def remove():
        logger.remove()

    def add_api_handler(self):
        handler = ApiLogHandler()

        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            log = getLogger(name)
            log.handlers = [handler]
            log.propagate = False
            log.setLevel(self.config.debug.level)

    def add_file_handler(self, filename=TermFilesPath.LOG_FILE_NAME):
        logger.add(
            filename,
            format=self.format,
            level=self.config.debug.level,
            rotation=self.rotation,
            compression=self.compression,
            backtrace=False,
            diagnose=False,
        )

    def add_stdout_handler(self):
        logger.add(
            stdout,
            format=self.format,
            level=self.config.debug.level,
            backtrace=False,
            diagnose=False,
        )

    def add_wireless_handler(self, log_browser, wireless_handler: WirelessHandler | None = None) -> int:
        if wireless_handler is None:
            wireless_handler = WirelessHandler()

        wireless_handler.new_record_appeared.connect(log_browser.append)

        handler_id = logger.add(
            wireless_handler,
            format=LogDefinition.DISPLAY_DATE_FORMAT,
            level=self.config.debug.level,
            backtrace=False,
            diagnose=False,
        )

        return handler_id
