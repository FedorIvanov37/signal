from PyQt6.QtGui import QUndoCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_views.TreeView import TreeView
from common.gui.core.json_items.Item import Item


class RemoveItemCommand(QUndoCommand):
    def __init__(self, tree: TreeView, item: Item):
        super().__init__()

        self.tree = tree
        self.item = item
        self.parent = item.parent()

        if self.item is not self.tree.root:
            self.row = self.parent.indexOfChild(item)

    def redo(self):
        if self.item is self.tree.root:
            return

        with SignalsBlocker(self.tree):
            self.parent.takeChild(self.row)
            self.tree.process_item_remove(parent=self.parent, item=self.item)

    def undo(self):
        if self.item is self.tree.root:
            return

        with SignalsBlocker(self.tree):
            self.parent.insertChild(self.row, self.item)
            self.tree.set_new_item(self.item)
            self.item.set_checkbox()
            self.tree.root.set_length()
