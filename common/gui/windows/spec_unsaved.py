from common.gui.forms.spec_unsaved import Ui_SpecUnsaved
from PyQt6.QtWidgets import QDialog, QMenu
from PyQt6.QtGui import QCloseEvent, QKeyEvent, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.gui.enums import ButtonActions


class SpecUnsaved(Ui_SpecUnsaved, QDialog):
    _save: pyqtSignal = pyqtSignal(bool)
    _return_to_spec: pyqtSignal = pyqtSignal()

    @property
    def return_to_spec(self):
        return self._return_to_spec

    @property
    def save(self):
        return self._save

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setup()

    @set_window_icon
    @has_close_button_only
    def setup(self) -> None:
        self.LogoLabel.setPixmap(QPixmap(GuiFilesPath.MAIN_LOGO))
        self.ButtonSave.setMenu(QMenu())
        self.ButtonSave.menu().addAction(
            ButtonActions.ApplySpecMenuActions.ONE_SESSION,
            lambda: self.need_apply(ButtonActions.ApplySpecMenuActions.ONE_SESSION)
        )
        self.ButtonSave.menu().addSeparator()
        self.ButtonSave.menu().addAction(
            ButtonActions.ApplySpecMenuActions.PERMANENTLY,
            lambda: self.need_apply(ButtonActions.ApplySpecMenuActions.PERMANENTLY)
        )
        self.ButtonReturn.clicked.connect(self.return_to_spec.emit)

    def need_apply(self, commit: str) -> None:
        self.save.emit(commit == ButtonActions.ApplySpecMenuActions.PERMANENTLY)
        self.accept()

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.return_to_spec.emit()
        a0.accept()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
