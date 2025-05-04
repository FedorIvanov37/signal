from sys import stdout
from loguru import logger
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.data_models.Config import Config
from common.lib.constants import LogDefinition
from common.gui.core.WirelessHandler import WirelessHandler


class Logger:
    rotation = f"{LogDefinition.LOG_MAX_SIZE_MEGABYTES} MB"
    format = LogDefinition.LOGFILE_DATE_FORMAT
    compression = LogDefinition.COMPRESSION

    def __init__(self, config: Config):
        self.config = config
        self.setup()

    def setup(self, filename=TermFilesPath.LOG_FILE_NAME):
        logger.remove()

        logger.add(
            filename,
            format=self.format,
            level=self.config.debug.level,
            rotation=self.rotation,
            compression=self.compression,
        )

    def add_stdout_handler(self):
        logger.add(
            stdout,
            format=self.format,
            level=self.config.debug.level,
        )

    def add_wireless_handler(self, log_browser, wireless_handler: WirelessHandler | None = None) -> int:
        if wireless_handler is None:
            wireless_handler = WirelessHandler()

        wireless_handler.new_record_appeared.connect(log_browser.append)

        handler_id = logger.add(
            wireless_handler,
            format=LogDefinition.DISPLAY_DATE_FORMAT,
            level=self.config.debug.level
        )

        return handler_id
