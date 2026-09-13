from types import SimpleNamespace


def test_banner_does_not_inherit_error_color(runtime):
    from PyQt6.QtWidgets import QTextEdit
    from PyQt6.QtGui import QTextCursor, QTextFormat
    from common.gui.windows.main_window import MainWindow
    log = QTextEdit()
    log.append('<span style="color: #FF7070">Error</span>')
    cursor = log.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    log.setTextCursor(cursor)
    window = SimpleNamespace(LogArea=log)
    MainWindow.set_log_data(window, 'SIGNAL', data_format='SIGNAL')
    fragment = log.document().firstBlock().begin().fragment()
    assert not fragment.charFormat().hasProperty(QTextFormat.Property.ForegroundBrush)
    log.deleteLater()
