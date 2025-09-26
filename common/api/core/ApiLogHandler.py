from loguru import logger
from logging import Handler, LogRecord
from re import search


class ApiLogHandler(Handler):
    pid = ""
    api = "Signal API"

    def emit(self, record: LogRecord) -> None:

        try:
            level = logger.level(record.levelname).name

        except Exception as err:

            level = record.levelno

        message = record.getMessage()

        if message.startswith("Uvicorn running on") and message.endswith("Press CTRL+C to quit)"):
            message = message.replace("Uvicorn", self.api)
            message = message.replace(" (Press CTRL+C to quit)", "")
            message = message.replace("http://0.0.0.0:", "port ")
            message = f"{message}. Process ID: {self.pid}"

        if message.startswith("Started server process"):
            if pid := search(r"\d+", message):
                self.pid = pid.group()
                return

        if message.startswith("Waiting for application startup"):
            return

        if message.startswith("Application startup complete"):
            return

        if message.startswith("Shutting down"):
            return

        if message.startswith("Waiting for application shutdown"):
            return

        if message.startswith("Application shutdown complete"):
            return

        if message.startswith("Finished server process"):
            if pid := search(r"\d+", message):
                if pid.group() == self.pid:
                    message = f"{self.api} stopped. Process ID: {self.pid}"
                    self.pid = ""

        logger.opt(depth=6, exception=record.exc_info).log(level, message)
