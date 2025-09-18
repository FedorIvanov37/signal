from PyQt6.QtGui import QUndoCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_views.TreeView import TreeView
from common.gui.core.json_items.Item import Item


class InsertItemCommand(QUndoCommand):
    def __init__(self, tree: TreeView, item: Item, parent: Item, index: int, callback: callable = None):
        super().__init__()

        self.tree = tree
        self.item = item
        self.index = index
        self.parent = parent
        self.callback = callback

    def redo(self):
        with SignalsBlocker(self.tree):
            self.parent.insertChild(self.index, self.item)

        if self.callback is not None:
            self.callback(self.item)

    def undo(self):
        with SignalsBlocker(self.tree):
            self.item = self.parent.takeChild(self.index)
