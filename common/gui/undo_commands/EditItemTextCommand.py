from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import Qt, pyqtSignal
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.tools.json_views.TreeView import TreeView
from common.gui.tools.json_items.Item import Item


class EditItemTextCommand(QUndoCommand):
    def __init__(self, tree: TreeView, item: Item, column: int, old_text: str, new_text: str, signal: pyqtSignal = None):
        super().__init__()

        self.tree = tree
        self.item = item
        self.column = column
        self.old_text = old_text
        self.new_text = new_text
        self.signal = signal

    def _apply(self, text):
        from common.gui.tools.json_items.FIeldItem import FieldItem
        from common.gui.enums.MainFieldSpec import ColumnsOrder

        field_value = isinstance(self.item, FieldItem) and self.column == ColumnsOrder.VALUE
        with SignalsBlocker(self.tree):
            if field_value:
                # Discard the cached value before restoring history. Otherwise
                # field_data and masking keep returning the previous secret.
                self.item._secret = ""
                self.item.masked = False
            self.item.setData(self.column, Qt.ItemDataRole.EditRole, text)

        try:
            if isinstance(self.item, FieldItem):
                self.tree.set_item_length(text, self.column, item=self.item)
            elif self.signal is not None:
                self.signal.emit(text, self.column)
            self.tree.itemChanged.emit(self.item, self.column)
        finally:
            if field_value:
                self.item.hide_secret()

    def redo(self):
        self._apply(self.new_text)

    def undo(self):
        self._apply(self.old_text)
