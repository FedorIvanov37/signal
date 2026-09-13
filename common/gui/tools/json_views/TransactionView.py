from PyQt6.QtWidgets import QAbstractItemDelegate

from common.gui.enums.MainFieldSpec import ColumnsOrder
from common.gui.tools.json_views.JsonView import JsonView


class TransactionView(JsonView):
    """Field editor shared by transaction tabs and the complex-field constructor."""

    def _editing_cells(self):
        pending = list(reversed(self.root.get_children()))
        while pending:
            item = pending.pop()
            if item.isHidden() or item.is_disabled:
                continue
            yield item, ColumnsOrder.FIELD
            if item.childCount():
                pending.extend(reversed(item.get_children()))
            else:
                yield item, ColumnsOrder.VALUE

    def closeEditor(self, editor, hint):
        hints = QAbstractItemDelegate.EndEditHint
        if hint not in (hints.EditNextItem, hints.EditPreviousItem):
            return super().closeEditor(editor, hint)

        current = self.currentItem(), self.currentColumn()
        # Qt has already committed the editor. Close without its default
        # all-column traversal, then open the next editable cell explicitly.
        super().closeEditor(editor, hints.NoHint)
        cells = list(self._editing_cells())
        if current not in cells:
            return
        step = 1 if hint == hints.EditNextItem else -1
        position = cells.index(current)
        position = max(0, min(position + step, len(cells) - 1))
        item, column = cells[position]
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.setCurrentItem(item, column)
        self.scrollToItem(item)
        self.editItem(item, column)
