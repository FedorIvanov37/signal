from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtGui import QIcon, QIconEngine, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtWidgets import QApplication


class FieldActionIcon(QIconEngine):
    def __init__(self, action):
        super().__init__()
        self.action = action

    def clone(self):
        return FieldActionIcon(self.action)

    def pixmap(self, size, mode, state):
        result = QPixmap(size)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        self.paint(painter, result.rect(), mode, state)
        painter.end()
        return result

    def scaledPixmap(self, size, mode, state, scale):
        result = self.pixmap(QSize(round(size.width() * scale), round(size.height() * scale)), mode, state)
        result.setDevicePixelRatio(scale)
        return result

    def paint(self, painter, rect, mode, state):
        palette = QApplication.palette()
        group = QPalette.ColorGroup.Disabled if mode == QIcon.Mode.Disabled else QPalette.ColorGroup.Active
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(rect.center())
        painter.scale(rect.width() / 16, rect.height() / 16)
        painter.setPen(QPen(palette.color(group, QPalette.ColorRole.ButtonText), 1.6,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if self.action in ('add', 'remove'):
            painter.drawLine(QPointF(-5, 0), QPointF(5, 0))
            if self.action == 'add':
                painter.drawLine(QPointF(0, -5), QPointF(0, 5))
        elif self.action in ('up', 'down', 'left', 'right'):
            painter.rotate({'right': 0, 'down': 90, 'left': 180, 'up': -90}[self.action])
            painter.drawLine(QPointF(-5, 0), QPointF(5, 0))
            painter.drawLine(QPointF(1, -4), QPointF(5, 0))
            painter.drawLine(QPointF(5, 0), QPointF(1, 4))
        else:
            painter.drawLine(QPointF(-5, -5), QPointF(-5, 3))
            painter.drawLine(QPointF(-5, 3), QPointF(5, 3))
            painter.drawLine(QPointF(2, 0), QPointF(5, 3))
            painter.drawLine(QPointF(5, 3), QPointF(2, 6))
        painter.restore()


def set_field_action_icon(button, action, label):
    button.setText('')
    button.setIcon(QIcon(FieldActionIcon(action)))
    button.setIconSize(QSize(16, 16))
    button.setAccessibleName(label)
    button.setToolTip(label)
