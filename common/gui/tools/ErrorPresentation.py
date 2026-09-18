"""GUI adapter for the core error reporter."""
import traceback
from contextlib import suppress
from PyQt6.QtWidgets import QApplication
from loguru import logger


def show_error(message, error, *, parent=None, recovery_action=None, recovery_label='Restore',
               fix_action=None, exit_action=None):
    from common.gui.windows.error_dialog import ErrorDialog
    app = QApplication.instance() or QApplication([])
    options = {'recovery_label': recovery_label} if recovery_action else {}
    if fix_action:
        options['fix_label'] = 'Fix specification'
    if exit_action:
        options['exit_label'] = 'Exit'
    trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    dialog = ErrorDialog(message, trace, parent, **options)
    with suppress(Exception):
        logger.error('{}', ' '.join(message.splitlines()))
        logger.debug('{}', trace)
    dialog.exec()
    if exit_action and dialog.exit_requested:
        exit_action()
    elif fix_action and dialog.fix_requested:
        fix_action()
    elif recovery_action and dialog.recovery_requested:
        recovery_action()


def install():
    from common.core.tools.ErrorReporting import set_gui_error_handler
    set_gui_error_handler(show_error)
