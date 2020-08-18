import functools
import logging
import time
from pprint import pformat

from loguru import logger
from loguru._defaults import LOGURU_FORMAT


# https://github.com/tiangolo/fastapi/issues/1276#issuecomment-615877177
class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentaion.
    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def format_record(record: dict) -> str:
    """
    Custom format for loguru loggers.
    Uses pformat for log any data like request/response body during debug.
    Works with logging if loguru handler it.
    Example:
    >>> payload = [{"users":[{"name": "Nick", "age": 87, "is_active": True}, {"name": "Alex", "age": 27, "is_active": True}], "count": 2}]
    >>> logger.bind(payload=).debug("users payload")
    >>> [   {   'count': 2,
    >>>         'users': [   {'age': 87, 'is_active': True, 'name': 'Nick'},
    >>>                      {'age': 27, 'is_active': True, 'name': 'Alex'}]}]
    """
    format_string = LOGURU_FORMAT

    if record["extra"].get("payload") is not None:
        record["extra"]["payload"] = pformat(
            record["extra"]["payload"], indent=4, compact=True, width=88
        )
        format_string += "\n<level>{extra[payload]}</level>"

    if record["exception"] is not None:
        record["extra"]["stack"] = pformat(
            record["exception"], indent=4, compact=True, width=88
        )
        format_string += "\n{extra[stack]}"

    format_string += "\n"
    return format_string


def log(*, level="DEBUG"):
    def wrapper(func):
        name = func.__name__

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            start = time.time()
            logger_ = logger.opt(depth=1)
            logger_.log(level, "Entering '{}'", name, start)
            result = func(*args, **kwargs)
            end = time.time()
            logger_.log(
                level, "Exiting '{}'. Completion time: '{:f}'", name, end - start
            )
            return result

        return wrapped

    return wrapper
