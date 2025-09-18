from PyQt6.QtGui import QUndoCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_views.TreeView import TreeView
from common.gui.core.json_items.Item import Item


class RemoveItemCommand(QUndoCommand):
    def __init__(self, tree: TreeView, item: Item, callback: callable = None):
        super().__init__()

        self.tree = tree
        self.item = item
        self.parent = self.item.parent()
        self.callback = callback
        self.index = self.parent.indexOfChild(self.item)
        self.removed_item = None

    def redo(self):
        if self.item is self.tree.root:
            return

        with SignalsBlocker(self.tree):
            self.removed_item = self.parent.takeChild(self.index)

        if self.callback is not None:
            self.callback(self.parent, self.removed_item, undo=False)

    def undo(self):
        with SignalsBlocker(self.tree):
            self.parent.insertChild(self.index, self.removed_item)

        if self.callback is not None:
            self.callback(self.parent, self.item)
