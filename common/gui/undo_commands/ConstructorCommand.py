from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import QSignalBlocker
from common.gui.undo_commands.ClearTreeCommand import ClearTreeCommand


class ConstructorState:
    def __init__(self, window):
        self.index = window.FieldNumber.currentIndex()
        self.text = window.TextData.toPlainText()
        self.tree = ClearTreeCommand(window.JsonView)
        self.tree.items = list(window.JsonView.root.get_children())

    def restore(self, window):
        with QSignalBlocker(window.FieldNumber), QSignalBlocker(window.TextData):
            window.FieldNumber.setCurrentIndex(self.index)
            window.TextData.setPlainText(self.text)
        window.JsonView.clean()
        self.tree.undo()


class ConstructorCommand(QUndoCommand):
    def __init__(self, window, before, after, label):
        super().__init__(label)
        self.window, self.before, self.after = window, before, after
        self.first = True

    def apply(self, state):
        self.window._history_busy = True
        try:
            state.restore(self.window)
            self.window._constructor_state = ConstructorState(self.window)
        finally:
            self.window._history_busy = False

    def redo(self):
        if self.first:
            self.first = False
        else:
            self.apply(self.after)

    def undo(self):
        self.apply(self.before)
