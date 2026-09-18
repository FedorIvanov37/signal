import pytest
from loguru import logger


@pytest.mark.parametrize('level,ambiguous', [('DEBUG', False), ('DEBUG', True), ('INFO', False)])
def test_dynamic_shortcut_logging_does_not_consume_events(runtime, level, ambiguous):
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtGui import QKeySequence, QShortcut, QShortcutEvent
    from PyQt6.QtWidgets import QWidget
    from common.gui.tools.ShortcutLogging import ShortcutLogging
    observer = ShortcutLogging.install(runtime.app)
    assert ShortcutLogging.install(runtime.app) is observer
    window = QWidget()
    shortcut = QShortcut(QKeySequence('Ctrl+Shift+J'), window)
    shortcut.setObjectName('new_test_action')
    activated = []
    shortcut.activated.connect(lambda: activated.append('activated'))
    shortcut.activatedAmbiguously.connect(lambda: activated.append('ambiguous'))
    messages = []
    sink = logger.add(lambda message: messages.append(message.record['message']), level=level)
    try:
        QCoreApplication.sendEvent(shortcut, QShortcutEvent(shortcut.key(), shortcut, ambiguous))
        assert activated == ['ambiguous' if ambiguous else 'activated']
        matching = [message for message in messages if 'GUI hotkey:' in message]
        assert len(matching) == (1 if level == 'DEBUG' else 0)
        if matching:
            assert 'sequence=Ctrl+Shift+J' in matching[0]
            assert 'object=new_test_action' in matching[0]
            assert f'ambiguous={ambiguous}' in matching[0]
    finally:
        logger.remove(sink)
        window.close()
        window.deleteLater()
