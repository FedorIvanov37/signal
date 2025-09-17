from contextlib import nullcontext
from PyQt6.QtGui import QUndoCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.core.json_items.Item import Item


class SetDisabledCommand(QUndoCommand):

    def __init__(self, item: Item, disabled: bool):
        super().__init__()

        self.item = item
        self.tree = item.treeWidget()
        self.old = item.is_disabled
        self.new = disabled

    def _apply(self, disabled: bool):
        ctx = SignalsBlocker(self.tree) if self.tree else nullcontext()

        with ctx:
            self.item.set_disabled(disabled)

    def redo(self):
        self._apply(self.new)

    def undo(self):
        self._apply(self.old)
