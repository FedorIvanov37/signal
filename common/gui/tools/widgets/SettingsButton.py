from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QIcon, QPainter, QPalette
from PyQt6.QtWidgets import QPushButton
from common.gui.enums.GuiFilesPath import GuiFilesPath


class SettingsButton(QPushButton):
    def refresh_icon(self):
        gear = QIcon(GuiFilesPath.SETTINGS).pixmap(self.iconSize())
        painter = QPainter(gear)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(gear.rect(), self.palette().color(QPalette.ColorRole.ButtonText))
        painter.end()
        self.setIcon(QIcon(gear))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self.refresh_icon()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_icon()
