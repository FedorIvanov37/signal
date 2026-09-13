from PyQt6.QtGui import QUndoCommand


class ChangeMtiCommand(QUndoCommand):
    def __init__(self, combo, before, after):
        super().__init__('Change MTI')
        self.combo = combo
        self.before = before
        self.after = after

    def undo(self):
        self.combo.setCurrentIndex(self.combo.findText(self.before))

    def redo(self):
        self.combo.setCurrentIndex(self.combo.findText(self.after))
