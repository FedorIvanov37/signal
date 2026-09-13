"""Presentation at application boundaries; core operations still raise errors."""
import sys
import traceback
from pathlib import Path
from functools import wraps

from common.core.exceptions.exceptions import SignalError


def log_error(error, message):
    """Keep user-facing errors separate from DEBUG-only diagnostics."""
    from loguru import logger
    logger.error("{}", message)
    # Avoid Pydantic input values and local variables in diagnostic output.
    logger.opt(lazy=True).debug(
        "{}\n{}\nCause type: {}",
        lambda: message,
        lambda: "".join(traceback.format_tb(error.__traceback__)),
        lambda: type(error.__cause__).__name__ if error.__cause__ else type(error).__name__,
    )


def error_message(error, *, configuration=False, source_file=None):
    """Explain the failure without Pydantic's input dump or documentation links."""
    from pydantic import ValidationError
    from common.core.exceptions.exceptions import DataFileError
    cause = error.__cause__
    if isinstance(error, FileNotFoundError) or isinstance(cause, FileNotFoundError):
        path = error.path if isinstance(error, DataFileError) else getattr(error, 'filename', None)
        path = path or getattr(cause, 'filename', None)
        configuration = configuration or (path and Path(path).name in ('config.json', 'default_config.json'))
        if configuration:
            return f'Configuration file "{path}" not found' if path else 'Configuration file not found'
        return f'File not found: {path}' if path else 'File not found.'
    validation = error if isinstance(error, ValidationError) else cause
    if isinstance(validation, ValidationError):
        lines = []
        for item in validation.errors(include_url=False, include_input=False):
            location = '.'.join(map(str, item['loc'])) or 'JSON document'
            reason = item['msg']
            if item['type'] in ('model_type', 'dict_type'):
                reason = 'must contain an object with settings'
                lines.append(f'Section "{location}" {reason}.')
            else:
                lines.append(f'Field "{location}": {reason}')
        source = source_file or (error.path if isinstance(error, DataFileError) else getattr(validation, 'source_file', None))
        if source and (configuration or validation.title == 'Config'):
            prefix = f'Cannot load configuration file "{source}":\n'
        else:
            prefix = f'Invalid data in {source}:\n' if source else 'Validation failed:\n'
        return prefix + '\n'.join(lines)
    return str(error) if isinstance(error, (SignalError, OSError, ValueError)) else 'An unexpected error occurred. Open Trace for details.'


def specification_recovery_message(source_file, text):
    import json
    source = Path(source_file).absolute()
    if text is None:
        reason = 'Specification file could not be read.' if source.exists() else 'Specification file was not found.'
    elif not text.strip():
        reason = 'Specification file is empty.'
    else:
        try:
            json.loads(text)
        except json.JSONDecodeError as error:
            reason = f'Specification file contains invalid JSON (line {error.lineno}, column {error.colno}).'
        else:
            reason = 'Specification contains invalid fields or an unsupported document structure.'
    return f'{reason}\nFile: {source}'


_gui_error_handler = None


def set_gui_error_handler(handler):
    global _gui_error_handler
    _gui_error_handler = handler


def report_error(error, *, gui=False, parent=None, title="Signal error", configuration=False, source_file=None, action=None,
                 recovery_action=None, user_message=None, recovery_label='Restore', fix_action=None, exit_action=None):
    from pydantic import ValidationError
    from common.core.exceptions.exceptions import DataFileError
    configuration = configuration or (isinstance(error, ValidationError) and error.title == 'Config')
    configuration = configuration or (isinstance(error, DataFileError) and Path(error.path).name in ('config.json', 'default_config.json'))
    message = user_message if user_message is not None else error_message(error, configuration=configuration, source_file=source_file)
    if action:
        message = f'{message}\n\n{action}' if user_message is not None else f'{action}:\n{message}'
    if gui:
        try:
            if _gui_error_handler is not None:
                _gui_error_handler(message, error, parent=parent, recovery_action=recovery_action,
                                   recovery_label=recovery_label, fix_action=fix_action, exit_action=exit_action)
                return
        except Exception:
            pass
    try:
        log_error(error, f"{title}: {message}")
    except Exception:
        pass
    if sys.stderr is not None:
        print(f"{title}: {message}", file=sys.stderr)


def gui_action(function):
    """A failed user action leaves the event loop alive and reports its failure."""
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except Exception as error:
            report_error(error, gui=True, parent=getattr(self, "window", None))
    return wrapped


def install_exception_hook(gui=False):
    """Report failed GUI callbacks without terminating the event loop."""
    previous = sys.excepthook
    def hook(error_type, error, tb):
        if issubclass(error_type, (KeyboardInterrupt, SystemExit)):
            previous(error_type, error, tb)
            return
        report_error(error, gui=gui, title="Action failed" if gui else "Signal cannot continue safely")
        if gui:
            return
        from PyQt6.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app is not None:
            app.exit(100)
    sys.excepthook = hook
    return previous
