from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import Qt, pyqtSignal
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_views.TreeView import TreeView
from common.gui.core.json_items.Item import Item


class EditItemTextCommand(QUndoCommand):
    def __init__(self, tree: TreeView, item: Item, column: int, old_text: str, new_text: str, signal: pyqtSignal = None):
        super().__init__()

        self.tree = tree
        self.item = item
        self.column = column
        self.old_text = old_text
        self.new_text = new_text
        self.signal = signal

    def redo(self):
        with SignalsBlocker(self.tree):
            self.item.setData(self.column, Qt.ItemDataRole.EditRole, self.new_text)

        if self.signal is not None:
            self.signal.emit(self.new_text, self.column)

        self.tree.itemChanged.emit(self.item, self.column)

    def undo(self):
        with SignalsBlocker(self.tree):
            self.item.setData(self.column, Qt.ItemDataRole.EditRole, self.old_text)

        if self.signal is not None:
            self.signal.emit(self.old_text, self.column)

        self.tree.itemChanged.emit(self.item, self.column)
