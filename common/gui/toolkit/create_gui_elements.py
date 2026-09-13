from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QFrame, QAbstractButton, QCheckBox
from PyQt6.QtGui import QFont, QKeySequence
import re


CONTROL_FONT_STYLE = '''
QComboBox { padding-right: 22px; }
QComboBox::drop-down {
    border: none; background: transparent; width: 20px;
    subcontrol-origin: padding; subcontrol-position: top right;
}
QComboBox::down-arrow {
    image: url(common/data/style/combo_chevron.svg); width: 10px; height: 6px;
}
QLineEdit#SearchLine, QLineEdit#SearchLine:hover, QLineEdit#SearchLine:focus {
    border: none;
}
QCheckBox, QRadioButton, QTabBar,
QMenu, QMenuBar, QComboBox, QComboBox QAbstractItemView,
QDialog#SettingsWindow QLabel, QDialog#SettingsWindow QLineEdit,
QDialog#SettingsWindow QAbstractSpinBox, QDialog#SettingsWindow QGroupBox {
    font-family: "Calibri"; font-size: 12pt; font-weight: normal; font-style: normal;
}
QPushButton, QToolButton {
    font-family: "Arial"; font-size: 11pt; font-weight: normal; font-style: normal;
}
QPushButton[signalHistoryArrow="true"] {
    font-family: "Arial"; font-size: 14pt; font-weight: bold;
}
QPushButton::menu-indicator {
    image: url(common/data/style/menu_down.svg);
    width: 10px; height: 6px;
    subcontrol-position: right center;
    subcontrol-origin: padding;
}
'''


def set_button_hints(window):
    descriptions = {
        '✚': 'Add field', '━': 'Remove selected field', '🡾': 'Add subfield',
        '🡹': 'Move up', '🡻': 'Move down', '🡸': 'Move left', '🡺': 'Move right',
        '+': 'Add item', '-': 'Remove selected item', '−': 'Remove selected item',
        '↘': 'Add subfield', '↶': 'Undo', '↷': 'Redo',
        'Send': 'Send transaction', 'Reverse': 'Reverse transaction',
        'Repeat': 'Configure repeated transactions', 'Keep alive': 'Configure keep-alive messages',
        'Print': 'Print data to console', 'Log': 'Console actions',
        '[Re]connect': 'Connect or reconnect to host', 'Echo-Test': 'Send echo-test',
        'Disable': 'Disable selected field', 'Enable': 'Enable selected field',
        'Enable all': 'Enable all fields', 'Do Backup': 'Back up specification',
        'Backup Dir': 'Open specification backup folder', 'Field Params': 'Edit field validation rules',
        'Set MTI': 'Edit message types', 'Field Data': 'Load field data from main window',
        'API': 'API server actions', 'Help': 'Open help menu', 'Tools': 'Open tools menu',
        'Message': 'Message actions', 'Accept': 'Accept license agreement',
        'Reject': 'Reject license agreement',
    }
    for button in window.findChildren(QAbstractButton):
        if isinstance(button, QCheckBox):
            button.setToolTip("")
            continue
        if button.toolTip():
            continue
        label = ' '.join((button.accessibleName() or button.text()).replace('&', '').split())
        if button.objectName() == 'MusicOnOfButton':
            label = 'Play / stop music'
        if not label:
            label = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', button.objectName()).replace('Button', '').strip()
        if not label:
            label = 'Open menu' if getattr(button, 'menu', lambda: None)() else 'Activate'
        hint = descriptions.get(label, label)
        shortcut = button.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        button.setToolTip(f'{hint} ({shortcut})' if shortcut else hint)


def set_shortcut_hints(buttons, shortcuts):
    for button, action in buttons.items():
        keys = [QKeySequence(key).toString(QKeySequence.SequenceFormat.NativeText)
                for key, callback in shortcuts.items() if callback == action]
        if keys:
            hint = button.toolTip() or button.accessibleName() or button.text()
            button.setToolTip(f'{hint} ({", ".join(dict.fromkeys(keys))})')


def create_button(name: str) -> QPushButton:
    push_button: QPushButton = QPushButton()
    push_button.setText(name)
    push_button.setFont(QFont("Arial", 10))
    push_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    font = push_button.font()
    # font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    push_button.setFont(font)
    actions = {'✚': ('add', 'Add field'), '━': ('remove', 'Remove selected field'),
               '🡾': ('nested', 'Add subfield')}
    if name in actions:
        from common.gui.tools.widgets.FieldActionIcon import set_field_action_icon
        set_field_action_icon(push_button, *actions[name])
    directions = {'🡹': 'up', '🡻': 'down', '🡸': 'left', '🡺': 'right'}
    if name and name[0] in directions:
        from common.gui.tools.widgets.FieldActionIcon import set_field_action_icon
        label = name[1:].strip()
        set_field_action_icon(push_button, directions[name[0]], label)
        push_button.setText(label)
    if name in ("Undo", "Redo"):
        push_button.setProperty("signalHistoryArrow", True)
        font.setBold(False)
        push_button.setFont(font)
        # Use the standard hooked arrows: they read as undo/redo while matching
        # the simple directional symbols used by the neighboring controls.
        push_button.setText("⤶" if name == "Undo" else "⤷")
        undo_redo_font = push_button.font()
        undo_redo_font.setPointSize(undo_redo_font.pointSize() + 3)
        undo_redo_font.setBold(True)
        push_button.setFont(undo_redo_font)
        push_button.setAccessibleName(name)
        push_button.setToolTip(name)
    push_button.setStyleSheet("""
        QPushButton {
            padding: 6px 12px;      /* top/bottom, left/right */
        }
    """)

    return push_button


def create_vertical_line() -> QFrame:
    line: QFrame = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)

    return line
