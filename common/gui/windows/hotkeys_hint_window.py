from common.gui.forms.hotkeys import Ui_HotKeysHint
from common.gui.decorators.window_settings import has_close_button_only, set_window_icon
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt


class HotKeysHintWindow(Ui_HotKeysHint, QDialog):
    def __init__(self):
        super(HotKeysHintWindow, self).__init__()
        self.setupUi(self)
        self.setup()

    @set_window_icon
    @has_close_button_only
    def setup(self) -> None:
        header = self.HintTable.horizontalHeader()
        header.setSectionResizeMode(header.ResizeMode.Fixed)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
