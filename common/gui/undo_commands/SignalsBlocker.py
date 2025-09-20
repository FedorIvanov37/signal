from PyQt6.QtWidgets import QTreeWidget


class SignalsBlocker:
    def __init__(self, tree: QTreeWidget):
        self.tree = tree

    def __enter__(self):
        self.tree.blockSignals(True)

    def __exit__(self, exc_type, exc, tb):
        self.tree.blockSignals(False)
