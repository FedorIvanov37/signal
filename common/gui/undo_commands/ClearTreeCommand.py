from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QCheckBox
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker


class ClearTreeCommand(QUndoCommand):
    def __init__(self, tree, mti=None):
        super().__init__('Clear table')
        self.tree = tree
        self.root = tree.root
        self.mti = mti
        self.mti_index = mti.currentIndex() if mti is not None else None
        self.current = tree.currentItem()
        self.items = []
        self.states = []
        def capture(item):
            checkbox = item.get_checkbox() if hasattr(item, 'get_checkbox') else None
            checked = checkbox.isChecked() if isinstance(checkbox, QCheckBox) else None
            self.states.append((item, item.isExpanded(), item.isHidden(), item.isSelected(), checked))
            for index in range(item.childCount()):
                capture(item.child(index))
        for index in range(self.root.childCount()):
            capture(self.root.child(index))

    def refresh(self):
        if hasattr(self.root, 'set_length'):
            self.root.set_length()
        self.tree.field_changed.emit()

    def redo(self):
        with SignalsBlocker(self.tree):
            self.items = self.root.takeChildren()
            if self.mti is not None:
                self.mti.setCurrentIndex(-1)
        self.refresh()

    def undo(self):
        with SignalsBlocker(self.tree):
            if self.mti is not None:
                self.mti.setCurrentIndex(self.mti_index)
            self.root.addChildren(self.items)
            for item, expanded, hidden, selected, checked in self.states:
                if checked is not None:
                    item.set_checkbox(checked)
                item.setExpanded(expanded)
                item.setHidden(hidden)
                item.setSelected(selected)
            if self.current is not None:
                self.tree.setCurrentItem(self.current)
        self.refresh()
