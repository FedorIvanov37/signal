import logging
import pytest


@pytest.mark.parametrize('level', ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
@pytest.mark.parametrize('light', [False, True])
def test_gui_log_colors_preserve_literal_text(runtime, level, light):
    from PyQt6.QtWidgets import QTextEdit, QApplication
    from PyQt6.QtGui import QTextCursor
    from common.gui.tools.WirelessHandler import WirelessHandler
    QApplication.instance().setProperty('signalConsoleColor', '#F0F0F0' if light else '#012E4F')
    handler = WirelessHandler()
    widget = QTextEdit()
    handler.formatted_record_appeared.connect(widget.append)
    plain = []
    handler.new_record_appeared.connect(plain.append)
    text = '  <field>& value\n    second line'
    record = logging.LogRecord('test', getattr(logging, level), __file__, 1, text, (), None)
    handler.emit(record)
    assert plain == [text]
    if level == 'WARNING':
        assert '[WARN]' in widget.toPlainText()
        assert '[WARNING]' not in widget.toPlainText()
        assert '[WARN]  |' in widget.toPlainText()
    if level == 'ERROR':
        assert '[ERROR] |' in widget.toPlainText()
    assert widget.toPlainText().endswith(text)
    cursor = QTextCursor(widget.document())
    cursor.movePosition(QTextCursor.MoveOperation.End)
    expected = {'DEBUG': '#005A9E', 'INFO': '#243447', 'WARNING': '#805500',
                'ERROR': '#B42318', 'CRITICAL': '#9C2670'} if light else handler.LEVEL_COLORS
    assert cursor.charFormat().foreground().color().name().upper() == expected[level]
    handler.emit(record)
    assert widget.toPlainText().count(text) == 2
    assert widget.toPlainText().count(' | ') >= 4
    widget.close()



def test_dialog_inherits_window_palette_while_table_selection_is_preserved(runtime, config):
    from PyQt6.QtWidgets import QLineEdit
    from PyQt6.QtGui import QPalette
    from common.gui.windows.main_window import MainWindow
    from common.gui.windows.settings_window import SettingsWindow
    main = MainWindow(config)
    dialog = SettingsWindow(config)
    selection = runtime.app.property('signalSelectionColor')
    for color in ('#102D28', '#3B202B', '#000000'):
        main._apply_dark_theme(color)
        runtime.app.processEvents()
        expected = runtime.app.property('signalSelectionColor')
        assert expected == selection  # Window themes preserve the table selection color.
        assert 'QLineEdit, QTextEdit' in runtime.app.styleSheet()
        assert dialog.palette().color(QPalette.ColorRole.Highlight) == runtime.app.palette().color(QPalette.ColorRole.Highlight)
    dialog.deleteLater(); main.deleteLater()
