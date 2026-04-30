from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QFrame
from PyQt6.QtGui import QFont


def create_button(name: str) -> QPushButton:
    push_button: QPushButton = QPushButton()
    push_button.setText(name)
    push_button.setFont(QFont("Arial", 10))
    push_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    font = push_button.font()
    # font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    push_button.setFont(font)
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
