from PyQt6.QtGui import QUndoCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_views.TreeView import TreeView
from common.gui.core.json_items.Item import Item
from common.gui.enums.MainFieldSpec import ColumnsOrder


class InsertSubItemCommand(QUndoCommand):
    def __init__(self, tree: TreeView, item: Item, sub_item, callback: callable = None):
        super().__init__()

        self.tree = tree
        self.item = item
        self.sub_item = sub_item
        self.callback = callback
        self.item_data = self.item.text(ColumnsOrder.VALUE)

    def redo(self):
        with SignalsBlocker(self.tree):
            self.item.insertChild(int(), self.sub_item)

            if self.callback is not None:
                self.callback(self.item, self.sub_item, undo=False)

    def undo(self):
        with SignalsBlocker(self.tree):
            self.sub_item = self.item.takeChild(int())

        if self.callback is not None:
            self.item.setText(ColumnsOrder.VALUE, self.item_data)
            self.callback(self.item, self.sub_item)
