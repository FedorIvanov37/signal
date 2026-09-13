from common.gui.toolkit.clipboard import copy_text
from common.core.tools.DebugTrace import trace_operation
from loguru import logger
from copy import deepcopy
from pathlib import Path
from common.gui.tools.spec_document import parse_spec_document
from common.core.tools.ErrorReporting import report_error
from pydantic import ValidationError
from contextlib import suppress
from PyQt6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, pyqtSignal, QPersistentModelIndex, QModelIndex, QEvent
from PyQt6.QtWidgets import QFileDialog, QMenu, QDialog, QPushButton, QApplication, QSizePolicy
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.tools.Logger import Logger
from common.core.tools.SpecFilesRotator import SpecFilesRotator
from common.core.data_models.EpaySpecificationModel import EpaySpecModel, IsoField
from common.core.data_models.Config import Config
from common.gui.tools.json_items import SpecItem
from common.gui.windows.spec_unsaved import SpecUnsaved
from common.gui.windows.mti_spec_window import MtiSpecWindow
from common.gui.windows.field_validator_window import FieldDataSet
from common.gui.forms.spec import Ui_SpecificationWindow
from common.gui.tools.json_views.SpecView import SpecView
from common.gui.enums.KeySequences import KeySequences
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.gui.enums import ButtonActions, SpecFieldDef, Buttons
from common.core.enums.TermFilesPath import TermFilesPath, TermDirs
from common.core.enums.TextConstants import TextConstants
from common.gui.toolkit.create_gui_elements import create_button
from common.gui.tools.WirelessHandler import WirelessHandler


class SpecWindow(Ui_SpecificationWindow, QDialog):
    _read_only: bool = True
    _clean_spec: tuple | None = None
    _spec: EpaySpecification = EpaySpecification()
    spec_accepted: pyqtSignal = pyqtSignal(str)
    spec_rejected: pyqtSignal = pyqtSignal()
    reset_spec: pyqtSignal = pyqtSignal(str)
    load_remote_spec: pyqtSignal = pyqtSignal(bool)
    open_spec_backup_dir: pyqtSignal = pyqtSignal()
    copy_specification: pyqtSignal = pyqtSignal()

    @property
    def spec(self):
        return self._spec

    @property
    def read_only(self):
        return self._read_only

    @read_only.setter
    def read_only(self, checked):
        self._read_only = checked

    def __init__(self, connector, config: Config, recover=True):
        super(SpecWindow, self).__init__()
        self.connector = connector
        self.config = config
        self._recover = recover
        self.wireless_handler = WirelessHandler()
        self.setupUi(self)
        self._read_only_return_index = QPersistentModelIndex()
        self._setup()
        from common.gui.toolkit.panel_splitter import PanelSplitter
        self.main_splitter = PanelSplitter(self, self.SpecTreeLayout, self.horizontalLayout,
                                           self.LogArea, self.horizontalLayout_2, 2, 'specification')
        QApplication.instance().focusChanged.connect(self._remember_read_only_focus)

    def _remember_read_only_focus(self, previous, current):
        view = self.SpecView
        if current is self.CheckBoxReadOnly and (
            previous is view or (previous is not None and view.isAncestorOf(previous))
        ):
            self._read_only_return_index = QPersistentModelIndex(view.currentIndex())
        else:
            self._read_only_return_index = QPersistentModelIndex()

    @set_window_icon
    @has_close_button_only
    def _setup(self):

        self.SpecView: SpecView = SpecView(self)
        from common.gui.toolkit.document_drop import route_document_drops
        route_document_drops(self, self.SpecView)
        self._clean_spec = self.SpecView.draft_snapshot()
        self.PlusButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_PLUS_SIGN)
        self.MinusButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_MINUS_SIGN)
        self.NextLevelButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_NEXT_LEVEL_SIGN)
        self.UndoButton: QPushButton = create_button(Buttons.Buttons.UNDO)
        self.RedoButton: QPushButton = create_button(Buttons.Buttons.REDO)

        widgets_layouts_map = {
            self.PlusButton: self.JsonButtonLayout,
            self.MinusButton: self.JsonButtonLayout,
            self.NextLevelButton: self.JsonButtonLayout,
            self.UndoButton: self.JsonButtonLayout,
            self.RedoButton: self.JsonButtonLayout,
        }

        button_menu_structure = {
            self.ButtonApply: {
                ButtonActions.ApplySpecMenuActions.ONE_SESSION:
                    lambda: self.apply(ButtonActions.ApplySpecMenuActions.ONE_SESSION),

                ButtonActions.ApplySpecMenuActions.PERMANENTLY:
                    lambda: self.apply(ButtonActions.ApplySpecMenuActions.PERMANENTLY),
            },
            self.ButtonReset: {
                ButtonActions.SetSpecMenuActions.LOCAL_SPEC:
                    lambda: self.reset_spec.emit(ButtonActions.SetSpecMenuActions.LOCAL_SPEC),

                ButtonActions.SetSpecMenuActions.REMOTE_SPEC:
                    lambda: self.reset_spec.emit(ButtonActions.SetSpecMenuActions.REMOTE_SPEC),
            },
        }

        for button, button_actions in button_menu_structure.items():
            button.setMenu(QMenu())

            for name, action in button_actions.items():
                button.menu().addAction(name, action)
                button.menu().addSeparator()

        for widget, layout in widgets_layouts_map.items():
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignLeft)
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            widget.installEventFilter(self)

        for box in (self.CheckBoxHideReverved, self.CheckBoxReadOnly):
            box.setChecked(bool(Qt.CheckState.Checked))

        self.SpecTreeLayout.addWidget(self.SpecView)
        self.logger = Logger(self.config)
        self.handler_id = self.logger.add_wireless_handler(self.wireless_handler)
        self.connect_all()
        self.set_read_only(self.CheckBoxReadOnly.isChecked())
        self.set_hello_message()
        if self._recover and self.spec.recovery_error is not None:
            logger.error('Specification is unavailable. Open a valid specification file or a backup, then Apply.'
                         if self.spec.recovery_text is None else
                         'Specification is unavailable. Correct the highlighted fields or open a valid specification file, then Apply.')
            if self.spec.recovery_text is not None:
                self._load_spec_document(self.spec.recovery_text, f'file "{self.spec.filename}"')
        self.setAcceptDrops(True)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if watched in (self.PlusButton, self.MinusButton, self.NextLevelButton,
                           self.UndoButton, self.RedoButton) and self.read_only:
                self.SpecView.warn_blocked(watched)
                return True
        return super().eventFilter(watched, event)

    def connect_all(self):

        connection_map = {
            self.SpecView.search_finished: self.hide_reserved_for_future,
            self.CheckBoxReadOnly.stateChanged: lambda state: self.set_read_only(bool(state)),
            self.CheckBoxHideReverved.stateChanged: self.hide_reserved_for_future,
            self.spec_accepted: lambda name: logger.info(f"Specification applied - {name}"),
            self.SearchLine.textChanged: self.SpecView.search,
            self.SearchLine.editingFinished: self.SpecView.setFocus,
            self.reset_spec: self.reload_spec,
            self.connector.got_remote_spec: self.process_remote_spec,
            self.load_remote_spec: self.connector.get_remote_spec,
            self.wireless_handler.formatted_record_appeared: self.LogArea.append,
        }

        buttons_connection_map = {
            self.ParseFile: lambda: self.parse_file(log=True),
            self.ButtonCopySpec: self.copy_specification,
            self.ButtonOpenBackupDir: self.open_spec_backup_dir,
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
            self.UndoButton: self.SpecView.undo,
            self.RedoButton: self.SpecView.redo,
        }

        keys_connection_map = {
            QKeySequence.StandardKey.Find: self.SearchLine.setFocus,
            QKeySequence.StandardKey.New: self.SpecView.plus,
            QKeySequence.StandardKey.Delete: self.SpecView.minus,
            QKeySequence.StandardKey.Open: self.parse_file,
            QKeySequence.StandardKey.Save: self.backup,
            QKeySequence.StandardKey.Undo: self.SpecView.undo,
            QKeySequence.StandardKey.Redo: self.SpecView.redo,
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

        from common.gui.toolkit.create_gui_elements import set_button_hints, set_shortcut_hints
        set_button_hints(self)
        set_shortcut_hints(buttons_connection_map, keys_connection_map)
        self.ParseFile.setToolTip("Open specification file (Ctrl+O)")

        for button, function in buttons_connection_map.items():
            button.clicked.connect(function)

        for button in buttons_connection_map.keys():
            font = button.font()
            font.setPointSize(font.pointSize() + 1)
            button.setFont(font)

    @trace_operation
    def backup(self):
        if not (backup_filename := SpecFilesRotator(self.config).backup_spec()):
            return

        logger.info(f"Specification backup completed. Filename: {backup_filename}")

    def set_hello_message(self):
        self.LogArea.setText(f"{TextConstants.HELLO_MESSAGE}\n")

    def dragEnterEvent(self, event):
        if not (event.mimeData().hasUrls() or event.mimeData().hasText()):
            event.ignore()
            return

        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if not (event.mimeData().hasUrls() or event.mimeData().hasText()):
            event.ignore()
            return

        event.acceptProposedAction()

    @trace_operation
    def dropEvent(self, event):
        if not event.mimeData().hasUrls() and event.mimeData().hasText():
            self._load_spec_document(event.mimeData().text(), 'dropped text')
            event.acceptProposedAction()
            return
        files: list[str] = list()

        for url in event.mimeData().urls():
            files.append(url.toLocalFile())

        if not files:
            event.ignore()

        logger.debug(f"Spec files dropped: {files}")

        for file in files:

            try:
                self.parse_file(file, log=True)

            except Exception as parsing_error:
                logger.error(f"Spec file {file} parsing error: {parsing_error}")

        event.acceptProposedAction()

    @trace_operation
    def process_remote_spec(self, spec_data: str):
        self._load_spec_document(spec_data, 'HTTP response')

    def _load_spec_document(self, spec_data, source):
        try:
            document = parse_spec_document(spec_data)
            self.SpecView.parse_spec(document)
        except Exception as error:
            report_error(error, gui=True, parent=self,
                         action=f'Cannot load specification from {source}. Open a corrected file or a backup',
                         recovery_action=self.open_backup if self.has_backups() else None)

    @staticmethod
    def has_backups():
        return bool(SpecWindow.valid_backups())

    @staticmethod
    def valid_backups():
        backups = []
        for path in sorted(Path(TermDirs.SPEC_BACKUP_DIR).glob('spec_backup_*.json'), reverse=True):
            try:
                EpaySpecModel(str(path)).validate_for_use()
            except (ValueError, OSError):
                continue
            backups.append(path)
        return backups

    def open_backup(self):
        backups = self.valid_backups()
        if not backups:
            logger.warning('No valid specification backups are available. Open a corrected specification file.')
            return
        filename, _ = QFileDialog.getOpenFileName(self, 'Open specification backup',
                                                 str(TermDirs.SPEC_BACKUP_DIR),
                                                 'Valid specification backups (' + ' '.join(path.name for path in backups) + ')')
        if filename:
            try:
                EpaySpecModel(filename).validate_for_use()
            except (ValueError, OSError) as error:
                report_error(error, gui=True, parent=self, action='Cannot restore an invalid specification backup')
                return
            self.parse_file(filename, log=True)

    def copy_log(self):
        self.set_clipboard_text(self.LogArea.toPlainText())

    def set_read_only(self, readonly: bool):
        self.read_only = readonly

        for button in self.PlusButton, self.MinusButton, self.NextLevelButton, self.RedoButton, self.UndoButton:
            button.setDisabled(readonly)

        self.SpecView.set_read_only(readonly)
        index = self._read_only_return_index
        if not readonly and self.CheckBoxReadOnly.hasFocus() and index.isValid():
            item = self.SpecView.itemFromIndex(QModelIndex(index))
            self.SpecView._focus_cell(item, index.column())

    def clean(self):
        self.SpecView.clear_with_history()

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
        self.SpecView._draft_spec.mti = mti_list

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
            self.SpecView.parse_field_spec(field_spec)

        except (ValidationError, ValueError) as validation_error:
            logger.error(validation_error)

    @staticmethod
    def set_clipboard_text(data: str = str()) -> bool:
        return copy_text(data)

    @trace_operation
    def apply(self, commit: bool | str):
        if isinstance(commit, str):
            commit: bool = True if commit == ButtonActions.ApplySpecMenuActions.PERMANENTLY else False

        try:
            self.SpecView.finish_editing()
            self.SpecView.reload_spec(commit)

        except Exception as apply_error:
            for line in str(apply_error).splitlines():
                if line.strip():
                    logger.error(f"Cannot apply specification: {line}")
            self.spec_rejected.emit()
            return False

        self._clean_spec = self.SpecView.draft_snapshot()
        self.spec_accepted.emit(self.spec.name)
        self.accepted.emit()
        return True

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.process_close(a0)

    @trace_operation
    def parse_file(self, filename: str | None = None, log: bool = False) -> None:
        if filename is None:
            file_dialog = QFileDialog()
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            file_dialog.setDirectory(TermDirs.SPEC_BACKUP_DIR)

            filename, _ = file_dialog.getOpenFileName(filter="JSON (*.json);;Any(*.*)")

        if not filename:
            logger.info("No input file selected")
            return

        specification: EpaySpecModel | None = None

        try:
            specification = parse_spec_document(Path(filename).read_text(encoding='utf-8'))

        except ValidationError as validation_error:
            report_error(validation_error, gui=True, parent=self, action=f'Cannot load specification file "{filename}". Open a corrected file or a backup')

        except Exception as parsing_error:
            report_error(parsing_error, gui=True, parent=self, action=f'Cannot load specification file "{filename}". Open a corrected file or a backup')

        if not specification:
            return

        try:
            self.SpecView.parse_spec(specification)

        except Exception as parsing_error:
            logger.error(f"File parsing error: {parsing_error}")
            return

        if log:
            logger.info(f"Specification file parsed: {filename}")

    @trace_operation
    def reload(self):
        self.SpecView.reload()
        self.CheckBoxHideReverved.setCheckState(Qt.CheckState.Checked)
        self.SpecView.hide_reserved()

    @trace_operation
    def process_close(self, close_event):
        self.SpecView.finish_editing()
        if self.SpecView.draft_snapshot() == self._clean_spec:
            with suppress(Exception):
                logger.remove(self.handler_id)
            close_event.accept()
            return
        close_event.ignore()
        window = SpecUnsaved()
        saved = False

        def save(commit):
            nonlocal saved
            saved = self.apply(commit)

        window.return_to_spec.connect(window.accept)
        window.save.connect(save)
        result = window.exec()
        if saved or result == QDialog.DialogCode.Rejected:
            with suppress(Exception):
                logger.remove(self.handler_id)
            close_event.accept()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
