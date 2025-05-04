from typing import Callable
from loguru import logger


def log_api_call(function: Callable):

    def wrapper(*args, **kwargs):

        logger.info(f'API got call "{function.__name__}"')

        return function(*args, **kwargs)

    wrapper.__name__ = function.__name__

    return wrapper
