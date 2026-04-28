from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtGui import QPixmap, QIcon
from common.gui.enums.GuiFilesPath import GuiFilesPath


class CheckableComboBox(QComboBox):
    _previous_text: str = ""
    _active_checks: set[int]

    def __init__(self):
        super().__init__()
        self._active_checks = set()

    def get_previous_text(self):
        return self._previous_text

    def mousePressEvent(self, e):
        self._previous_text = self.currentText()
        QComboBox.mousePressEvent(self, e)

    def addItem(self, item, state: bool=False):
        super(CheckableComboBox, self).addItem(item)
        item = self.model().item(self.count() -1, 0)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

    def set_validation_mark(self, mark=True, item=None):
        if item is None:
            item = self.currentIndex()

        icon_file = GuiFilesPath.GREY_CIRCLE

        try:
            self._active_checks.remove(item)
        except KeyError:
            pass

        if mark:
            icon_file = GuiFilesPath.GREEN_CIRCLE
            self._active_checks.add(item)

        self.setItemIcon(item, QIcon(QPixmap(icon_file)))

    def set_active_index(self):
        for index in range(self.count()):
            if index not in self._active_checks:
                continue

            self.setCurrentIndex(index)
            break
