from PyQt6.QtWidgets import QTreeWidget
from PyQt6.QtGui import QUndoStack, QFont, QPalette, QColor
from PyQt6.QtCore import pyqtSignal
from common.gui.decorators.void_qt_signals import void_qt_signals
from common.gui.enums.Colors import Colors
from common.gui.enums import MainFieldSpec


class TreeView(QTreeWidget):
    field_removed: pyqtSignal = pyqtSignal()
    field_changed: pyqtSignal = pyqtSignal()
    field_added: pyqtSignal = pyqtSignal()
    root = None

    def __init__(self, parent=None):
        super(TreeView, self).__init__(parent=parent)
        self.undo_stack = QUndoStack(self)
        self.setup()

    def setup(self):
        self.setFont(QFont("Calibri", 12))
        self.setAllColumnsShowFocus(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(self.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(False)

        palette = QPalette()
        palette.setColor(palette.ColorRole.AlternateBase, QColor(Colors.LIGHT_GREY))
        self.setPalette(palette)

    def resize_all(self, exceptions: list[int] | None = None):
        if exceptions is None:
            exceptions = []

        for column in range(self.columnCount()):
            if column in exceptions:
                continue

            self.resizeColumnToContents(column)

    def make_order(self):
        self.collapseAll()
        self.expandAll()
        self.resize_all(exceptions=[MainFieldSpec.ColumnsOrder.DESCRIPTION])

    def setFocus(self) -> None:
        if not (item := self.currentItem()):
            item = self.root

        if item.isHidden():
            item = self.root

        self.setCurrentItem(item)
        self.scrollToItem(item)

        QTreeWidget.setFocus(self)

    def edit_column(self, column: int):
        if not self.hasFocus():
            self.setFocus()

        if not (item := self.currentItem()):
            return

        self.editItem(item, column)

    def search(self, text: str, parent = None) -> None:
        if not text:
            self.unhide_all()
            return

        if parent is None:
            parent = self.root

        text = text.strip()

        for item in parent.get_children():
            if item.childCount():
                self.search(text, parent=item)

            item_found: bool = self.value_in_item(text, item)

            item.setHidden(not item_found)
            item.setExpanded(item_found)

            if item.childCount() and self.value_in_item(text, item, check_subfields=False):
                self.unhide_all(item)

    def unhide_all(self, parent=None):
        if parent is None:
            parent = self.root

        for item in parent.get_children():
            if item.childCount():
                self.unhide_all(item)

            item.setHidden(False)

    @void_qt_signals
    def clean(self):
        self.root.takeChildren()

    def undo(self):
        self.undo_stack.undo()
        self.field_changed.emit()

    def redo(self):
        self.undo_stack.redo()
        self.field_changed.emit()

    def value_in_item(self, value: str, item, check_subfields=True):
        if value in item.field_number:
            return True

        if value.lower() in item.description.lower():
            return True

        try:
            if value.lower() in item.field_data.lower():
                return True

        except AttributeError:
            pass

        if check_subfields:
            for child in item.get_children():
                if not self.value_in_item(value, child):
                    continue

                return True

        return False
