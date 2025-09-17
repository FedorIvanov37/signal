from PyQt6.QtGui import QUndoCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_views.TreeView import TreeView
from common.gui.core.json_items.Item import Item


class InsertSubItemCommand(QUndoCommand):
    def __init__(self, tree: TreeView, current_item: Item, item: Item):
        super().__init__()

        self.tree = tree
        self.item = item
        self.current_item = current_item
        self.current_item_data = self.current_item.text(1)

        if self.current_item is not self.tree.root:
            self.parent_current_item = current_item.parent()

        self.current_item_index = self.parent_current_item.indexOfChild(current_item) + 1

    def redo(self):
        if self.item is self.tree.root:
            return

        with SignalsBlocker(self.tree):
            self.current_item.insertChild(int(), self.item)

    def undo(self):
        if self.item is self.tree.root:
            return

        with SignalsBlocker(self.tree):
            self.item = self.current_item.takeChild(int())
            self.parent_current_item.insertChild(self.current_item_index, self.current_item)
            self.current_item.setText(1, self.current_item_data)
            self.tree.set_new_item(self.current_item)
            self.current_item.set_length()
            self.current_item.set_checkbox()
