from PyQt6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton, QStylePainter


class FieldCheckBox(QCheckBox):
    """Keep keyboard interaction without the native frame around the label."""

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.state &= ~QStyle.StateFlag.State_HasFocus
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_CheckBox, option)
