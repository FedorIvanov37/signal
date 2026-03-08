from uuid import uuid4
from functools import wraps
from typing import Callable
from loguru import logger


# This decorator reports to the log about decorated API function call start and finish


def log_api_call(function: Callable):

    @wraps(function)
    def wrapper(*args, **kwargs):
        request_id = uuid4()
        request_type = " ".join(function.__name__.split("_")).title()

        logger.info(
            f'API got incoming request. '
            f'Request type: "{request_type}"; '
            f'Request ID: "{request_id}"'
        )

        result = function(*args, **kwargs)

        logger.info(f'API request "{request_id}" processing finished')

        return result

    return wrapper
