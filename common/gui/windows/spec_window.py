from loguru import logger
from copy import deepcopy
from typing import Optional
from pydantic import ValidationError
from PyQt6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMenu, QDialog, QPushButton, QApplication
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.core.Logger import Logger
from common.lib.core.SpecFilesRotator import SpecFilesRotator
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel, IsoField
from common.lib.data_models.Config import Config
from common.gui.core.json_items import SpecItem
from common.gui.windows.spec_unsaved import SpecUnsaved
from common.gui.windows.mti_spec_window import MtiSpecWindow
from common.gui.windows.field_validator_window import FieldDataSet
from common.gui.forms.spec import Ui_SpecificationWindow
from common.gui.core.json_views.SpecView import SpecView
from common.gui.enums.KeySequences import KeySequences
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.gui.enums import ButtonActions, SpecFieldDef
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.enums.TextConstants import TextConstants


class SpecWindow(Ui_SpecificationWindow, QDialog):
    _read_only: bool = True
    _spec: EpaySpecification = EpaySpecification()
    _spec_accepted: pyqtSignal = pyqtSignal(str)
    _spec_rejected: pyqtSignal = pyqtSignal()
    _reset_spec: pyqtSignal = pyqtSignal(str)
    _load_remote_spec: pyqtSignal = pyqtSignal(bool)
    _clean_spec: EpaySpecModel = None

    @property
    def load_remote_spec(self):
        return self._load_remote_spec

    @property
    def reset_spec(self):
        return self._reset_spec

    @property
    def spec_accepted(self):
        return self._spec_accepted

    @property
    def spec_rejected(self):
        return self._spec_rejected

    @property
    def spec(self):
        return self._spec

    @property
    def read_only(self):
        return self._read_only

    @read_only.setter
    def read_only(self, checked):
        self._read_only = checked

    def __init__(self, connector, config: Config):
        super(SpecWindow, self).__init__()
        self.connector = connector
        self.config = config
        self.setupUi(self)
        self._setup()

    @set_window_icon
    @has_close_button_only
    def _setup(self):

        self.SpecView: SpecView = SpecView(self)
        self._clean_spec = deepcopy(self.SpecView.generate_spec())
        self.PlusButton: QPushButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_PLUS_SIGN)
        self.MinusButton: QPushButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_MINUS_SIGN)
        self.NextLevelButton: QPushButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_NEXT_LEVEL_SIGN)

        widgets_layouts_map = {
            self.PlusLayout: self.PlusButton,
            self.MinusLayout: self.MinusButton,
            self.NextLevelLayout: self.NextLevelButton,
            self.SpecTreeLayout: self.SpecView,
        }

        button_menu_structure = {
            self.ButtonApply: {
                ButtonActions.ApplySpecMenuActions.ONE_SESSION: lambda: self.apply(ButtonActions.ApplySpecMenuActions.ONE_SESSION),
                ButtonActions.ApplySpecMenuActions.PERMANENTLY: lambda: self.apply(ButtonActions.ApplySpecMenuActions.PERMANENTLY),
            },
            self.ButtonReset: {
                ButtonActions.SetSpecMenuActions.LOCAL_SPEC: lambda: self.reset_spec.emit(ButtonActions.SetSpecMenuActions.LOCAL_SPEC),
                ButtonActions.SetSpecMenuActions.REMOTE_SPEC: lambda: self.reset_spec.emit(ButtonActions.SetSpecMenuActions.REMOTE_SPEC),
            },
        }

        for button, button_actions in button_menu_structure.items():
            button.setMenu(QMenu())

            for name, action in button_actions.items():
                button.menu().addAction(name, action)
                button.menu().addSeparator()

        for layout, widget in widgets_layouts_map.items():
            layout.addWidget(widget)

        for box in (self.CheckBoxHideReverved, self.CheckBoxReadOnly):
            box.setChecked(bool(Qt.CheckState.Checked))

        self.logger = Logger(self.config)
        self.handler_id = self.logger.add_wireless_handler(self.LogArea)
        self.connect_all()
        self.set_read_only(self.CheckBoxReadOnly.isChecked())
        self.set_hello_message()

    def connect_all(self):

        connection_map = {
            self.SpecView.search_finished: self.hide_reserved_for_future,
            self.CheckBoxReadOnly.stateChanged: lambda state: self.set_read_only(bool(state)),
            self.CheckBoxHideReverved.stateChanged: self.hide_reserved_for_future,
            self.ParseFile.pressed: self.parse_file,
            self.spec_accepted: lambda name: logger.info(f"Specification applied - {name}"),
            self.SearchLine.textChanged: self.SpecView.search,
            self.SearchLine.editingFinished: self.SpecView.setFocus,
            self.reset_spec: self.reload_spec,
            self.connector.got_remote_spec: self.process_remote_spec,
            self.load_remote_spec: self.connector.get_remote_spec,
        }

        buttons_connection_map = {
            self.ButtonClearLog: self.clear_log,
            self.ButtonCopyLog: self.copy_log,
            self.PlusButton: self.SpecView.plus,
            self.MinusButton: self.SpecView.minus,
            self.NextLevelButton: self.SpecView.next_level,
            self.ButtonClose: self.close,
            self.ButtonReset: self.reload,
            self.ButtonClean: self.clean,
            self.ButtonSetMti: self.set_mti,
            self.ButtonBackup: self.backup,
            self.ButtonSetValidators: self.set_field_custom_validations,
        }

        keys_connection_map = {
            QKeySequence.StandardKey.Find: self.SearchLine.setFocus,
            QKeySequence.StandardKey.New: self.SpecView.plus,
            QKeySequence.StandardKey.Delete: self.SpecView.minus,
            QKeySequence.StandardKey.Open: self.parse_file,
            QKeySequence.StandardKey.Save: self.backup,
            KeySequences.CTRL_SHIFT_N: self.SpecView.next_level,
            KeySequences.CTRL_W: lambda: self.SpecView.edit_column(SpecFieldDef.ColumnsOrder.FIELD),
            KeySequences.CTRL_E: lambda: self.SpecView.edit_column(SpecFieldDef.ColumnsOrder.DESCRIPTION),
            KeySequences.CTRL_L: self.clear_log,
            KeySequences.CTRL_ALT_P: self.set_hello_message,
        }

        for signal, slot in connection_map.items():
            signal.connect(slot)

        for combination, function in keys_connection_map.items():  # Key sequences
            QShortcut(QKeySequence(combination), self).activated.connect(function)

        for button, function in buttons_connection_map.items():
            button.clicked.connect(function)

    @staticmethod
    def backup():
        rotator: SpecFilesRotator = SpecFilesRotator()
        backup_filename = rotator.backup_spec()
        logger.info(f"Backup done! Filename: {backup_filename}")

    def set_hello_message(self):
        self.LogArea.setText(f"{TextConstants.HELLO_MESSAGE}\n")

    def process_remote_spec(self, spec_data: str):
        spec: EpaySpecification = EpaySpecification()

        if self.config.specification.backup_storage:
            rotator: SpecFilesRotator = SpecFilesRotator()
            backup_filename: str = rotator.backup_spec()
            logger.debug(f"Backup local specification file name: {backup_filename}")

        try:
            spec_model_data: EpaySpecModel = EpaySpecModel.model_validate_json(spec_data)
            spec.reload_spec(spec=spec_model_data, commit=False)

        except Exception as loading_error:
            logger.error(f"Cannot load remote specification: {loading_error}")
            logger.warning("Local specification will be used instead")

        self.SpecView.parse_spec(self.spec.spec)

    def copy_log(self):
        self.set_clipboard_text(self.LogArea.toPlainText())

    def set_read_only(self, readonly: bool):
        self.read_only = readonly

        for button in (self.PlusButton, self.MinusButton, self.NextLevelButton):
            button.setDisabled(readonly)

        self.SpecView.set_read_only(readonly)

    def clean(self):
        self.SpecView.clean()

    def clear_log(self):
        self.LogArea.setText(str())

    def hide_reserved_for_future(self):
        if self.SearchLine.text():
            return

        self.SpecView.hide_reserved(bool(self.CheckBoxHideReverved.checkState().value))

    def reload_spec(self, spec_type: str):
        if spec_type == ButtonActions.SetSpecMenuActions.LOCAL_SPEC:
            self.parse_file(TermFilesPath.SPECIFICATION)
            self.apply(commit=False)

        if spec_type == ButtonActions.SetSpecMenuActions.REMOTE_SPEC:
            self.load_remote_spec.emit(False)

        self.reload()

    def set_mti_list(self, mti_list):
        self.spec.spec.mti = mti_list

    def set_mti(self):
        mti_window = MtiSpecWindow()
        mti_window.need_to_set_mti.connect(self.set_mti_list)
        mti_window.exec()

    def set_field_custom_validations(self):
        if not self.SpecView.hasFocus():
            self.SpecView.setFocus()

        item: SpecItem = self.SpecView.currentItem()

        if not item or item is self.SpecView.root:
            return

        if not (field_spec := item.get_field_spec()):
            logger.error(f"Cannot get field specification for {item.get_field_path(string=True)}")
            return

        validator_window = FieldDataSet(field_spec)
        validator_window.field_spec_accepted.connect(self.process_field_spec_acceptance)
        validator_window.exec()

    def process_field_spec_acceptance(self, field_spec: IsoField):
        try:
            self.spec.set_field_spec(field_spec)
            self.SpecView.parse_field_spec(field_spec)

        except (ValidationError, ValueError) as validation_error:
            logger.error(validation_error)

    @staticmethod
    def set_clipboard_text(data: str = str()) -> None:
        QApplication.clipboard().setText(data)

    def apply(self, commit: bool | str):
        if isinstance(commit, str):
            commit: bool = True if commit == ButtonActions.ApplySpecMenuActions.PERMANENTLY else False

        try:
            self.SpecView.reload_spec(commit)

        except Exception as apply_error:
            logger.error(apply_error)
            self.spec_rejected.emit()
            return

        self._clean_spec = deepcopy(self.SpecView.generate_spec())
        self.spec_accepted.emit(self.spec.name)
        self.accepted.emit()

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.process_close(a0)

    def parse_file(self, filename: Optional[str] = None) -> None:
        if filename is None:
            try:
                filename = QFileDialog.getOpenFileName()[0]
            except Exception as get_file_error:
                logger.error(f"Filename get error: {get_file_error}")
                return

        if not filename:
            logger.info("No input filename recognized")
            return

        try:
            with open(filename) as json_file:
                specification: EpaySpecModel = EpaySpecModel.model_validate_json(json_file.read())

        except ValidationError as validation_error:
            error_text = str(validation_error)
            logger.error(f"File validation error: {error_text}")

        except Exception as parsing_error:
            logger.error(f"File parsing error: {parsing_error}")

        else:
            self.SpecView.parse_spec(specification)

    def reload(self):
        self.SpecView.reload()
        self.CheckBoxHideReverved.setCheckState(Qt.CheckState.Checked)
        self.SpecView.hide_reserved()

    def process_close(self, close_event):
        try:
            current_spec = self.SpecView.generate_spec()

        except (ValidationError, ValueError) as spec_error:
            if isinstance(spec_error, ValidationError):
                logger.error(spec_error)

            logger.remove(self.handler_id)
            close_event.accept()
            return

        if current_spec == self._clean_spec:
            logger.remove(self.handler_id)
            close_event.accept()
            return

        window = SpecUnsaved()
        window.return_to_spec.connect(close_event.ignore)
        window.return_to_spec.connect(window.accept)
        window.save.connect(self.apply)

        self.spec_rejected.connect(close_event.ignore)

        window.exec()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
