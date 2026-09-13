"""DEBUG-only operation traces, without dumping arguments or return values."""
from contextvars import ContextVar
from functools import wraps
from inspect import iscoroutinefunction, signature
from itertools import count
from time import perf_counter

from loguru import logger


_calls = count(1)
_parent_call = ContextVar("signal_debug_call", default=0)


def trace_operation(function):
    """Log entry/return/raise and duration. 'returned' does not imply business success."""
    operation = function.__qualname__
    positions = {name: index for index, name in enumerate(signature(function).parameters)}

    def correlation(args, kwargs):
        identifiers = {}
        for name in ("request", "transaction", "response", "trans_id"):
            index = positions.get(name)
            value = kwargs.get(name, args[index] if index is not None and index < len(args) else None)
            for attribute in ("request_id", "trans_id"):
                identifier = value if name == "trans_id" and attribute == "trans_id" else getattr(value, attribute, None)
                if isinstance(identifier, str):
                    identifiers[attribute] = identifier[:128].replace("\r", "\\r").replace("\n", "\\n")
        return " ".join(f"{key}={value}" for key, value in identifiers.items())

    def emit(event, call_id, parent, started, args, kwargs, error_type=""):
        logger.opt(lazy=True).debug(
            "operation={} event={} call={} parent={} elapsed_ms={:.3f} {} error_type={}",
            lambda: operation, lambda: event, lambda: call_id, lambda: parent,
            lambda: (perf_counter() - started) * 1000,
            lambda: correlation(args, kwargs), lambda: error_type,
        )

    if iscoroutinefunction(function):
        @wraps(function)
        async def asynchronous(*args, **kwargs):
            call_id, parent, started = next(_calls), _parent_call.get(), perf_counter()
            token = _parent_call.set(call_id)
            try:
                emit("entered", call_id, parent, started, args, kwargs)
                try:
                    result = await function(*args, **kwargs)
                except BaseException as error:
                    emit("raised", call_id, parent, started, args, kwargs, type(error).__name__)
                    raise
                emit("returned", call_id, parent, started, args, kwargs)
                return result
            finally:
                _parent_call.reset(token)
        return asynchronous

    @wraps(function)
    def synchronous(*args, **kwargs):
        call_id, parent, started = next(_calls), _parent_call.get(), perf_counter()
        token = _parent_call.set(call_id)
        try:
            emit("entered", call_id, parent, started, args, kwargs)
            try:
                result = function(*args, **kwargs)
            except BaseException as error:
                emit("raised", call_id, parent, started, args, kwargs, type(error).__name__)
                raise
            emit("returned", call_id, parent, started, args, kwargs)
            return result
        finally:
            _parent_call.reset(token)
    return synchronous
