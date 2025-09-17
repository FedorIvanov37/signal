from PyQt6.QtGui import QUndoCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_views.TreeView import TreeView
from common.gui.core.json_items.Item import Item


class InsertItemCommand(QUndoCommand):
    def __init__(self, tree: TreeView, item: Item, row: int):
        super().__init__()

        self.row = row
        self.tree = tree
        self.item = item

        if self.item is not self.tree.root:
            self.parent_item = self.item.parent()

    def redo(self):
        if self.item is self.tree.root:
            return

        with SignalsBlocker(self.tree):
            self.parent_item.insertChild(self.row, self.item)

    def undo(self):
        if self.item is self.tree.root:
            return

        with SignalsBlocker(self.tree):
            self.item = self.parent_item.takeChild(self.row)
