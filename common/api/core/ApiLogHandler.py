from loguru import logger
from logging import Handler, LogRecord


class ApiLogHandler(Handler):
    def emit(self, record: LogRecord) -> None:

        try:
            level = logger.level(record.levelname).name

        except Exception as err:

            level = record.levelno

        message = record.getMessage()

        if message.startswith("Uvicorn running on") and message.endswith("Press CTRL+C to quit)"):
            message = message.replace("Uvicorn", "Signal API")
            message = message.replace("(Press CTRL+C to quit)", "")

        logger.opt(depth=6, exception=record.exc_info).log(level, message)
