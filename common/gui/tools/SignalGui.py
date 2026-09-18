from common.gui.toolkit.clipboard import copy_text
from common.core.tools.DebugTrace import trace_operation
from os import getcwd, startfile
from os.path import basename, normpath, abspath
from json import loads, dumps
from typing import Callable
from loguru import logger
from functools import wraps
from pydantic import ValidationError
from webbrowser import open as open_url
from pathlib import Path
import sys
from common.core.enums.ApplicationResources import ResourceNames
from PyQt6.QtWidgets import QApplication, QFileDialog, QStyleFactory
from PyQt6 import sip
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtNetwork import QTcpSocket
from PyQt6.QtCore import pyqtSignal, QTimer, QDir, QThreadPool
from common.gui.undo_commands.SetDisabledCommand import SetDisabledCommand
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.gui.windows.settings_window import SettingsWindow
from common.gui.windows.main_window import MainWindow
from common.gui.windows.reversal_window import ReversalWindow
from common.gui.windows.spec_window import SpecWindow
from common.gui.windows.hotkeys_hint_window import HotKeysHintWindow
from common.gui.windows.complex_fields_window import ComplexFieldsParser
from common.gui.windows.license_window import LicenseWindow
from common.gui.tools.ConnectionThread import ConnectionThread
from common.gui.tools.json_views.JsonView import JsonView
from common.gui.enums import ButtonActions
from common.gui.enums.Colors import Colors
from common.gui.enums.GuiFilesPath import GuiDirs
from common.gui.tools.WirelessHandler import WirelessHandler
from common.gui.tools.ShortcutLogging import ShortcutLogging
from common.core.enums import KeepAlive
from common.core.enums.TermFilesPath import TermFilesPath, TermDirs
from common.core.enums.MessageLength import MessageLength
from common.core.enums.TextConstants import TextConstants
from common.core.tools.TransTimer import TransactionTimer
from common.core.tools.SpecFilesRotator import SpecFilesRotator
from common.core.tools.Terminal import Terminal
from common.core.tools.ConfigManager import ConfigManager
from common.core.tools.ErrorReporting import report_error
from common.core.data_models.Config import Config
from common.core.data_models.Transaction import Transaction, TypeFields
from common.core.data_models.EpaySpecificationModel import EpaySpecModel
from common.api.tools.SignalApi import SignalApi
from common.api.enums.ApiModes import ApiModes

from common.core.enums.DataFormats import (
    DataFormats,
    PrintDataFormats,
    OutputFilesFormat,
    InputFilesFormat
)

from common.core.exceptions.exceptions import (
    LicenceAlreadyAccepted,
    LicenseDataLoadingError,
    DataValidationWarning,
    DataValidationError
)


class SignalGui(Terminal):

    """
    The toolkit of the GUI backend

    Performs all the management and control. The main purpose is to receive a validated data-processing request from
    MainWindow or TransactionQueue and manage this using the other low-level modules such as Parser for data transformation
    TransactionQueue for interaction with the target system, Connector for TCP integration, and so on

    Always tries not to do the work itself, managing corresponding modules instead

    SignalGui is a basic executor for all user requests. Inherited from Terminal class, which does not interact
    with GUI anyhow. Low-level data processing performs using the basic Terminal class.

    Usually get data in the Transaction format. In any other case targeting to transform data into the Transaction and
    proceed to work with this. The Transaction is a common I/O format for SignalGui.

    Starts MainWindow when starting its work, being a kind of low-level adapter between the GUI and the system's toolkit
    """

    connector: ConnectionThread
    trans_timer: TransactionTimer
    set_remote_spec: pyqtSignal = pyqtSignal()
    _run_timer: QTimer
    _generated_echo_test_transactions: list[Transaction]

    def set_json_view_focus(function: callable):

        # This decorator sets focus on the self.window.json_view after the decorated function execution is finished

        @wraps(function)
        def wrapper(self, *args, **kwargs):
            try:
                return function(self, *args, **kwargs)

            finally:
                restore = getattr(self, "_json_view_restore_state", None)
                self.window.set_focus()
                if restore is not None:
                    view, item, vertical, horizontal = restore
                    self._json_view_restore_state = None
                    if item is not None and item.treeWidget() is view:
                        view.setCurrentItem(item)
                    view.verticalScrollBar().setValue(vertical)
                    view.horizontalScrollBar().setValue(horizontal)

        return wrapper

    def __init__(self, config: Config):
        from common.gui.tools.ErrorPresentation import install
        install()
        self._shutting_down = False
        application = QApplication.instance() or QApplication([])
        from common.gui.tools.GuiWatchdog import GuiWatchdog
        GuiWatchdog.install(application)
        manager = ConfigManager(config)
        self.connector: ConnectionThread = ConnectionThread(manager.view)
        super(SignalGui, self).__init__(config=manager.view, connector=self.connector, application=application)
        self._shortcut_logging = ShortcutLogging.install(application)
        self.api = SignalApi(self.config, terminal=self)
        self.window: MainWindow = MainWindow(self.config)
        self.window.destroyed.connect(self._begin_shutdown)
        self.pyqt_application.aboutToQuit.connect(self._begin_shutdown)
        self.trans_queue.parsing_error.connect(
            lambda message: self.window.statusBar().showMessage(f"Incoming message rejected: {message}", 15000))
        self.thread_pool: QThreadPool = QThreadPool()
        self.wireless_handler = WirelessHandler()
        self.trans_timer = TransactionTimer(KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION)
        self._generated_echo_test_transactions = list()
        self._run_timer = QTimer()
        self.connect_widgets()
        self.setup()

    def setup(self) -> None:
        QDir.addSearchPath(GuiDirs.STYLE_DIR.name, GuiDirs.STYLE_DIR)
        self._run_timer.setSingleShot(True)
        self._run_timer.start(int())
        self.logger.add_wireless_handler(self.wireless_handler)
        self.pyqt_application.setStyle(QStyleFactory.create("windowsvista"))
        palette = self.pyqt_application.palette()
        palette.setColor(QPalette.ColorRole.Accent, QColor(Colors.SELECTION_BLUE))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.SELECTION_BLUE))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Colors.WHITE))
        self.pyqt_application.setPalette(palette)
        self.pyqt_application.setStyleSheet(
            self.pyqt_application.styleSheet()
            + f"\nQTextEdit, QPlainTextEdit, QLineEdit {{ "
            f"selection-background-color: {Colors.SELECTION_BLUE}; "
            f"selection-color: {Colors.WHITE}; }}"

        )

        self.window._set_console_color(self.pyqt_application.property("signalConsoleColor"))

    @trace_operation
    def run_application(self) -> int:
        """Run the GUI and release background resources when it exits."""
        try:
            return self.pyqt_application.exec()
        finally:
            self._shutting_down = True
            self._run_timer.stop()
            self.keep_alive_timer._trans_loop_timer.stop()
            self.trans_timer._trans_loop_timer.stop()
            for timer in self.trans_queue.timers.values():
                timer.stop()
            if self.api.is_started():
                self.api.stop()
            self.connector.stop_thread()
            self.thread_pool.waitForDone()
            from PyQt6.QtCore import QCoreApplication, QEvent
            for widget in self.pyqt_application.topLevelWidgets():
                widget.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    @trace_operation
    def on_startup(self, resuming=False) -> None:  # Runs on startup to make all the preparation activity, then shows MainWindow
        if not resuming and not self.show_license_dialog():
            self.pyqt_application.exit(0)
            return

        if self.spec.recovery_error is not None:
            self._startup_waiting_for_spec = True
            self.window.show()
            from common.core.tools.ErrorReporting import report_error, specification_recovery_message
            has_backups = SpecWindow.has_backups()
            draft = None
            if self.spec.recovery_text is not None:
                from common.gui.tools.spec_document import parse_spec_document
                try:
                    draft = parse_spec_document(self.spec.recovery_text)
                except ValueError:
                    pass
            message = specification_recovery_message(self.spec.filename, self.spec.recovery_text)
            recovery_action = self.restore_specification_backup if has_backups else None
            fix_action = None
            action = ('Click Restore to select a backup.'
                      if has_backups else
                      'The file cannot be repaired here and no valid backups are available. A corrected specification file is required.')
            if draft is not None:
                message = f'Specification contains fields that need correction.\nFile: {abspath(self.spec.filename)}'
                action = ('Click Fix specification to correct this file, or Restore to select a backup.' if has_backups else
                          'Click Fix specification to correct this file.')
                fix_action = lambda: self.run_specification_window(draft=draft)
            report_error(self.spec.recovery_exception or ValueError(self.spec.recovery_error), gui=True, parent=self.window,
                         user_message=message,
                         action=action,
                         recovery_action=recovery_action, fix_action=fix_action,
                         exit_action=lambda: self.stop_signal())
            return

        self._startup_waiting_for_spec = False

        if not resuming:
            self.log_printer.print_startup_info()
            self.print_data(DataFormats.TERM)

        if warning := getattr(self, '_startup_config_warning', None):
            logger.warning(warning)
            self._startup_config_warning = None

        parsed = False
        if self.config.terminal.process_default_dump:
            parsed = self.set_default_values(log=not resuming)

        if self.config.host.keep_alive_mode:
            interval: int = self.config.host.keep_alive_interval
            self.keep_alive_timer.set_trans_loop_interval(KeepAlive.IntervalNames.KEEP_ALIVE_DEFAULT % interval)

        if self.config.specification.backup_storage:
            SpecFilesRotator(self.config).clear_spec_backup()

        if self.config.terminal.connect_on_startup:
            self.reconnect()

        if self.config.terminal.run_api:
            self.api.start()

        if self.config.specification.backup_on_startup:
            self.backup_spec()

        if self.config.terminal.load_remote_spec:
            self.set_remote_spec.emit()

        self.window.json_view.enable_json_mode_checkboxes(enable=not self.config.specification.manual_input_mode)

        self.window.show()
        return parsed

    def connect_widgets(self) -> None:
        window: MainWindow = self.window

        terminal_connections_map: dict[pyqtSignal, Callable] = {

            # Data processing request channels. Usually get the tasks from MainWindow or low-level Terminal

            window.clear_log: window.clean_window_log,
            window.send: self.send,
            window.reset: self.set_default_values,
            window.echo_test: self.echo_test,
            window.clear: self.clear_message,
            window.copy_log: self.copy_log,
            window.copy_bitmap: self.copy_bitmap,
            window.reconnect: self.reconnect,
            window.parse_file: lambda: self.parse_file(new_tab=True),
            window.window_close: self.stop_signal,
            window.reverse: self.make_reversal,
            window.print: self.print_data,
            window.save: self.save_transaction_to_file,
            window.field_changed: self.set_bitmap,
            window.field_removed: self.set_bitmap,
            window.field_added: self.set_bitmap,
            window.settings: self.settings,
            window.hotkeys: self.show_hotkeys,
            window.specification: self.run_specification_window,
            window.about: self.about,
            window.keep_alive: self.keep_alive_timer.set_trans_loop_interval,
            window.repeat: self.trans_timer.set_trans_loop_interval,
            window.validate_message: lambda force: self.validate_main_window(force=force),
            window.parse_complex_field: self.parse_complex_field,
            window.api_mode_changed: self.api.process_change_api_mode,
            window.exit: self.pyqt_application.quit,
            window.show_document: self.show_document,
            window.show_license: lambda: self.show_license_dialog(force=True),
            window.disable_item: lambda: self.disable_item(disable=True),
            window.enable_item: lambda: self.disable_item(disable=False),
            window.enable_all_items: lambda: self.disable_item(False, self.window.json_view.root, go_next=False),
            window.files_dropped: self.process_files_drop,
            window.text_dropped: self.process_text_drop,
            window.undo: window.undo_changes,
            window.redo: window.redo_changes,
            window.show_openapi_doc: self.show_openapi_doc,
            self.wireless_handler.formatted_record_appeared: window.log_browser.append,
            self.api.open_connection: lambda: self.reconnect(self.config.host.host, str(self.config.host.port)),
            self.connector.stateChanged: self.set_connection_status,
            self.set_remote_spec: self.connector.get_remote_spec,
            self.connector.got_remote_spec: self.load_remote_spec,
            self.trans_timer.send_transaction: window.send,
            self.trans_timer.interval_was_set: window.set_custom_repeat_interval,
            self.keep_alive_timer.interval_was_set: window.set_custom_repeat_interval,
            self.api.api_started: lambda: window.process_api_mode_change(ApiModes.START),
            self.api.api_stopped: lambda: window.process_api_mode_change(ApiModes.STOP),
            self.api.send_transaction: lambda transaction: self.send(transaction, is_api_call=True),
            self._run_timer.timeout: self.on_startup,

        }

        for signal, slot in terminal_connections_map.items():
            signal.connect(slot)

        self.window.reconnect.connect(lambda: logger.info("[Re]connecting..."))

    def read_config(self, config_file: str | None = None):
        return Terminal.read_config(self, config_file)

    def disable_item(self, disable: bool, item=None, go_next=True) -> None:
        if item is None and not (item := self.window.json_view.currentItem()):
            return

        self.window.json_view.undo_stack.push(SetDisabledCommand(item, disable))

        try:
            item.set_disabled(disable)

        except ValueError as err:
            logger.error(err)

        else:
            logger.debug(f"Field {item.get_field_path(string=True)} is {'disabled' if disable else 'enabled'}")

        self.set_bitmap()

        self.window.json_view.setFocus()

        if go_next:
            self.window.json_view.focusNextChild()

        self.window.json_view.setFocus()

    @staticmethod
    def show_document():  # Open the User guide in a default browser
        root = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
                else Path(__file__).resolve().parents[3])
        guide = root / "common" / "doc" / ResourceNames.USER_GUIDE
        if not guide.is_file():
            logger.error("User guide not found: {}", guide)
            return
        open_url(guide.as_uri())

    def show_openapi_doc(self):
        if not self.api.is_started():
            logger.error("Signal API is not running. Cannot open the API Specification page")
            return

        self.api.show_openapi_doc()

    @set_json_view_focus
    def show_license_dialog(self, force: bool = False) -> bool:
        try:
            license_window: LicenseWindow = LicenseWindow(self.config, force=force)
            license_window.exec()
            if license_window.rejected_by_user:
                return False
            if force:
                return True
            candidate = self.config.model_copy(deep=True)
            candidate.terminal.show_license_dialog = license_window.license_info.show_agreement
            self.update_config(candidate, persist=True)
            return True

        except LicenseDataLoadingError as license_data_loading_error:
            logger.error(license_data_loading_error)
            self.pyqt_application.exit(100)
            return False

        except LicenceAlreadyAccepted:
            return True
    
    @staticmethod
    def open_spec_backup_dir():
        startfile(abspath(TermDirs.SPEC_BACKUP_DIR))

    @set_json_view_focus
    @trace_operation
    def parse_complex_field(self):
        ComplexFieldsParser(self.config, self).exec()

    @set_json_view_focus
    def show_hotkeys(self):
        HotKeysHintWindow().exec()

    @set_json_view_focus
    @trace_operation
    def restore_specification_backup(self):
        backups = SpecWindow.valid_backups()
        if not backups:
            logger.warning('No valid specification backups are available.')
            return
        filename, _ = QFileDialog.getOpenFileName(self.window, 'Restore specification backup',
                                                 str(TermDirs.SPEC_BACKUP_DIR),
                                                 'Specification backups (' + ' '.join(path.name for path in backups) + ')')
        if not filename:
            return
        from pathlib import Path
        from common.gui.tools.spec_document import parse_spec_document
        try:
            draft = parse_spec_document(Path(filename).read_text(encoding='utf-8'))
        except (ValueError, OSError) as error:
            report_error(error, gui=True, parent=self.window, action='Cannot read this backup. Choose another backup.')
            return
        try:
            candidate = EpaySpecModel.model_validate(draft.model_dump(warnings=False))
            candidate.validate_for_use()
        except ValueError:
            self.run_specification_window(draft=draft)
            return
        try:
            self.spec.reload_spec(candidate, commit=True, config=self.config)
        except (ValueError, OSError) as error:
            report_error(error, gui=True, parent=self.window, action='Cannot save the restored specification')
            return
        self._resume_after_spec_recovery()

    @set_json_view_focus
    @trace_operation
    def run_specification_window(self, open_backup=False, draft=None) -> None:
        old_spec = self.spec.spec.json()

        self.logger.remove()
        spec_window = SpecWindow(self.connector, self.config, recover=not open_backup and draft is None)
        if draft is not None:
            spec_window.SpecView.parse_spec(draft)
            logger.warning('Correct the highlighted fields, then press Apply.')
            QTimer.singleShot(0, lambda: spec_window.LogArea.verticalScrollBar().setValue(
                spec_window.LogArea.verticalScrollBar().maximum()))
        if open_backup:
            QTimer.singleShot(0, spec_window.open_backup)
        spec_window.open_spec_backup_dir.connect(SignalGui.open_spec_backup_dir)
        spec_window.copy_specification.connect(lambda: self.copy_specification(spec_window))
        spec_window.spec_accepted.connect(
            lambda *args: spec_window.accept() if getattr(self, '_startup_waiting_for_spec', False)
            else self._resume_after_spec_recovery())
        self._spec_editor_open = True
        try:
            spec_window.exec()
        finally:
            self._spec_editor_open = False

        self.logger.setup(wireless_handler=self.wireless_handler)

        if getattr(self, '_startup_waiting_for_spec', False) and self.spec.recovery_error is None:
            self._resume_after_spec_recovery()
            return

        if self.config.fields.hide_secrets:
            self.window.json_view.hide_secrets()

        specification_changed = old_spec != self.spec.spec.json()

        if specification_changed and self.config.validation.validation_enabled:
            if self.config.validation.validate_window:
                logger.info("Validating message after specification changes")
                self.validate_main_window()

            if self.config.specification.manual_input_mode:
                self.modify_fields_data()
                self.window.json_view.refresh_fields(Colors.BLACK)

    def _resume_after_spec_recovery(self, *args):
        from common.gui.tools.tab_view.Widgets import ComboBox
        for selector in self.window.tab_view.findChildren(ComboBox):
            selector.refresh_specification()
        if getattr(self, '_startup_waiting_for_spec', False) and self.spec.recovery_error is None:
            logger.info('Specification recovery started.')
            parsed = self.on_startup(resuming=True)
            if not self.config.terminal.process_default_dump:
                logger.bind(recovery_success=True).info('Specification recovery completed successfully. Resuming normal operation.')
            elif parsed:
                logger.bind(recovery_success=True).info('Specification recovery completed successfully. Resuming normal operation.')
            else:
                logger.warning('Specification restored and valid, but the default transaction could not be loaded. Open a valid transaction file to continue.')

    def modify_fields_data(self):  # Set extended data modifications, set in field params
        self.window.json_view.modify_all_fields_data()

    @trace_operation
    def load_remote_spec(self, spec_data: str) -> None:
        if getattr(self, '_spec_editor_open', False):
            return  # The editor receives this response as a draft through the same connector.
        try:
            epay_spec: EpaySpecModel = EpaySpecModel.model_validate_json(spec_data)
        except (ValidationError, ValueError) as spec_parsing_error:
            logger.error(f"Remote spec processing error: {spec_parsing_error}")
            logger.warning("Local specification will be used instead")
            return

        try:
            self.backup_spec()
            self.spec.reload_spec(spec=epay_spec, commit=self.config.specification.rewrite_local_spec, config=self.config)
        except Exception as spec_reload_error:
            logger.error(spec_reload_error)
            logger.warning("Local specification will be used instead")
            return

        logger.info(f"Remote specification loaded: {epay_spec.name}")

    def validate_main_window(self, force: bool = False) -> None:
        self.window.validate_fields(force=force)
        self.window.json_view.refresh_fields()

        logger.info("Transaction data validated")

    @trace_operation
    def echo_test(self) -> None:
        try:
            echo_test: Transaction = self.parser.parse_file(TermFilesPath.ECHO_TEST)
            self._generated_echo_test_transactions.append(echo_test)
            self.send(echo_test)

        except ValidationError as validation_error:
            logger.error(validation_error.json())

        except Exception as sending_error:
            logger.error(sending_error)

    @set_json_view_focus
    def about(self):
        from common.gui.windows.about_window import AboutWindow
        window = AboutWindow(self.window)
        window.open_user_guide.connect(self.show_document)
        window.exec()

    @set_json_view_focus
    @trace_operation
    def settings(self) -> None:
        try:
            snapshot, revision = self.config_manager.read()
            def commit_settings(candidate, theme_only=False):
                nonlocal revision
                previous = getattr(self, '_applying_theme_only', False)
                self._applying_theme_only = theme_only
                try:
                    self.update_config(candidate, expected_revision=revision)
                    _, revision = self.config_manager.read()
                finally:
                    self._applying_theme_only = previous
            settings_window = SettingsWindow(snapshot,
                commit=commit_settings,
                commit_theme=lambda candidate: commit_settings(candidate, theme_only=True),
                change_colors=self.window.apply_theme_colors)
            settings_window.open_api_spec.connect(self.show_openapi_doc)
            settings_window.exec()
            
        except Exception as settings_error:
            report_error(settings_error, gui=True, parent=self.window)

    @trace_operation
    def process_config_change(self, old_config: Config) -> None:
        if old_config.fields.auto_sort != self.config.fields.auto_sort:
            from common.gui.tools.json_views.TreeView import TreeView
            for widget in QApplication.instance().allWidgets():
                if isinstance(widget, TreeView) and hasattr(widget, '_auto_sort_timer'):
                    widget.set_auto_sort(self.config.fields.auto_sort)
        if old_config.theme != self.config.theme.model_copy(deep=True):
            self.window.apply_theme_colors(self.config.theme.model_copy(deep=True).colors())
        Terminal.process_config_change(self, old_config)

        validation_conditions = [
            old_config.validation.validate_window != self.config.validation.validate_window,
            old_config.validation.validation_mode != self.config.validation.validation_mode,
            old_config.validation.validation_enabled != self.config.validation.validation_enabled,
        ]

        # Refresh presentation in all tabs; their parsers/validators already share the view.
        for view in self.window.tab_view.findChildren(JsonView):

            view.enable_json_mode_checkboxes(enable=self.config.validation.validate_window)

            if any(validation_conditions) or old_config.specification.manual_input_mode != self.config.specification.manual_input_mode:
                view.refresh_fields(color=Colors.BLACK)

            if old_config.fields.json_mode != self.config.fields.json_mode:
                view.switch_json_mode(self.config.fields.json_mode)

            if old_config.fields.hide_secrets != self.config.fields.hide_secrets:
                view.hide_secrets()

        if self.config.validation.validation_enabled and self.config.validation.validate_window and any(validation_conditions):
            self.modify_fields_data()
            self.validate_main_window()

        spec_loading_conditions: list[bool] = [
            self.config.specification.remote_spec_url,
            self.config.terminal.load_remote_spec,
            (old_config.specification.remote_spec_url, old_config.terminal.load_remote_spec) !=
            (self.config.specification.remote_spec_url, self.config.terminal.load_remote_spec),
        ]

        if all(spec_loading_conditions):
            try:
                self.data_validator.validate_url(self.config.specification.remote_spec_url)

            except (ValidationError, DataValidationError, DataValidationWarning) as url_validation_error:
                logger.error(f'Incorrect remote spec URL "{self.config.specification.remote_spec_url}"')
                logger.error(url_validation_error)

            else:
                self.set_remote_spec.emit()

        if (not getattr(self, '_applying_theme_only', False)
                and not self.window.property('signalTourCommit')):
            logger.info("Settings applied")

    def _begin_shutdown(self):
        self._shutting_down = True

    def stop_signal(self) -> None:
        self._shutting_down = True
        if self.config.specification.backup_on_shutdown:
            self.backup_spec()

        self.connector.stop_thread()

        self.pyqt_application.quit()

    def set_connection_status(self, state: QTcpSocket.SocketState) -> None:
        if self._shutting_down:
            return
        if isinstance(self.window, MainWindow) and (
            sip.isdeleted(self.window)
            or sip.isdeleted(self.window.ConnectionStatus)
            or sip.isdeleted(self.window.ConnectionStatusLabel)
        ):
            self._shutting_down = True
            return
        self.window.set_connection_status(state)

        if state == QTcpSocket.SocketState.ConnectingState:
            self.window.block_connection_buttons()
            return

        self.window.unblock_connection_buttons()

    @trace_operation
    def make_reversal(self, command: str) -> None:
        transaction_source_map: dict[str, Callable] = {
            ButtonActions.ReversalMenuActions.LAST: self.trans_queue.get_last_reversible_transaction_id,
            ButtonActions.ReversalMenuActions.OTHER: self.show_reversal_window,
            ButtonActions.ReversalMenuActions.SET_REVERSAL: self.show_reversal_window,
        }

        try:
            if not (transaction_source := transaction_source_map.get(command)):
                return

            if not (transaction_id := transaction_source()):
                return

            if not (original_trans := self.trans_queue.get_transaction(transaction_id)):
                raise LookupError("lost transaction response or non-reversible transaction")

            if not self.spec.get_reversal_mti(original_trans.message_type):
                raise LookupError("lost transaction response or non-reversible transaction")

            if not (reversal := self.build_reversal(original_trans)):
                raise LookupError("lost transaction response or non-reversible transaction")

        except Exception as reversal_building_error:
            logger.warning(f"Reversal building error: {reversal_building_error}")
            return

        match command:
            case ButtonActions.ReversalMenuActions.SET_REVERSAL:
                self.parse_transaction(reversal, generate_trans_id=False)

            case ButtonActions.ReversalMenuActions.LAST | ButtonActions.ReversalMenuActions.OTHER:
                try:
                    self.send(reversal)
                except Exception as sending_error:
                    logger.error(sending_error)

            case _:
                logger.error("Cannot reverse transaction")

    def parse_main_window_tab(self, tab_name: str | None = None, flat_fields: bool = True, clean: bool = False) -> \
            Transaction:

        if tab_name is None:
            tab_name = self.window.get_tab_name()

        trans_id: str | None = self.window.get_trans_id(tab_name)
        data_fields: TypeFields = self.window.parse_tab(tab_name, flat=flat_fields)

        if not data_fields:
            raise ValueError(f"No transaction data found on tab {tab_name}")

        if not (message_type := self.window.get_mti(tab_name=tab_name)):
            raise ValueError("Invalid MTI")

        transaction: Transaction = Transaction(
            trans_id=trans_id,
            generate_fields=self.window.get_fields_to_generate(),
            data_fields=data_fields,
            message_type=message_type,
            max_amount=self.config.fields.max_amount,
            is_reversal=self.spec.is_reversal(message_type)
        )

        if not clean:
            return transaction

        del (
            transaction.resp_time_seconds,
            transaction.match_id,
            transaction.utrnno,
            transaction.matched,
            transaction.success,
            transaction.is_request,
            transaction.is_reversal,
            transaction.is_keep_alive,
            transaction.json_fields,
            transaction.sending_time,
            transaction.error,
        )

        return transaction

    def parse_main_window(self, flat_fields: bool = True, clean: bool = False) -> dict[str, Transaction]:

        transactions: dict[str, Transaction] = dict.fromkeys(self.window.tab_view.get_tab_names())

        for tab_name in transactions:
            try:
                transaction = self.parse_main_window_tab(tab_name=tab_name, flat_fields=flat_fields, clean=clean)

            except ValidationError as validation_error:
                [logger.error(err.get("msg")) for err in validation_error.errors()]
                continue

            except Exception as parsing_error:
                logger.error(parsing_error)
                continue

            if not transaction:
                continue

            transactions[tab_name] = transaction

        return transactions

    @trace_operation
    def send(self, transaction: Transaction | None = None, is_api_call=False) -> None:
        try:
            self.spec.require_ready()
        except ValueError as error:
            logger.error(error)
            return
        if transaction is None:
            try:
                transaction: Transaction = self.parse_main_window_tab()

                if not transaction:
                    raise ValueError

            except Exception as building_error:
                [logger.error(err) for err in str(building_error).splitlines()]
                return

        if self.connector.connection_in_progress():
            try:
                transaction.success = False
                transaction.error = "Cannot send the transaction while the host connection is in progress"
                logger.error(transaction.error)
                return

            except AttributeError:
                return

        if self.config.debug.clear_log and not transaction.is_keep_alive and not is_api_call:
            self.window.clean_window_log()

        reversal_suffix_conditions = (
            self.spec.is_reversal(transaction.message_type),
            self.window.json_view.is_trans_id_generate_mode_on(),
            not transaction.trans_id.endswith("_R"),
        )

        if all(reversal_suffix_conditions):
            transaction.trans_id = f"{transaction.trans_id}_R"

        if not transaction.is_keep_alive:
            logger.info(f"Processing transaction ID [{transaction.trans_id}]")

        if self.config.fields.send_internal_id:
            transaction: Transaction = self.generator.set_trans_id(transaction)

        if transaction.generate_fields:
            transaction: Transaction = self.generator.set_generated_fields(transaction)

        if transaction not in self._generated_echo_test_transactions:
            self.set_generated_fields_to_gui(transaction)

        if transaction in self._generated_echo_test_transactions:
            self._generated_echo_test_transactions.remove(transaction)

        validation_conditions = (
            self.config.validation.validation_enabled,
            self.config.validation.validate_outgoing,
            not transaction.is_keep_alive,
        )

        if all(validation_conditions):
            try:
                self.trans_validator.validate_transaction(transaction)

            except DataValidationWarning as validation_warning:
                [logger.warning(warn) for warn in str(validation_warning).splitlines()]

            except Exception as validation_error:
                transaction.success = False
                transaction.error = str(validation_error)
                [logger.error(err) for err in transaction.error.splitlines()]
                return

        try:
            Terminal.send(self, transaction)  # Terminal always used to real data processing
        except Exception as sending_error:
            transaction.success = False
            transaction.error = f"Transaction sending error: {sending_error}"
            logger.error(transaction.error)
            return

    @staticmethod
    def get_output_filename(directory=False) -> tuple[str, str] | None:
        if directory:
            return QFileDialog.getExistingDirectory()

        file_name_filters = [f"{data_format} (*.{data_format.lower()})" for data_format in OutputFilesFormat]
        file_name_filter = ";;".join(file_name_filters)
        filename_data = list(QFileDialog.getSaveFileName(filter=file_name_filter))

        if not filename_data:
            return

        if not (file_format := filename_data.pop()):
            return

        if not (file_name := filename_data.pop()):
            return

        output_file_format: OutputFilesFormat | None = None

        for data_format in OutputFilesFormat:
            if directory:
                output_file_format = OutputFilesFormat.JSON
                break

            if data_format in file_format:
                output_file_format = data_format
                break

        if not output_file_format:
            return

        return file_name, output_file_format

    @staticmethod
    def get_input_filename(multiple_files=False) -> list[str] | str | None:
        any_file_mask = "Any (*.*)"

        file_name_filters = [f"{data_format} (*.{data_format.lower()})" for data_format in InputFilesFormat]
        file_name_filters.append(any_file_mask)
        file_name_filter = ";;".join(file_name_filters)

        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_function = file_dialog.getOpenFileNames

        if not multiple_files:
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            file_function = file_dialog.getOpenFileName

        file_data = file_function(filter=file_name_filter, initialFilter=any_file_mask)

        if not (file_name := file_data[int()]):
            return

        return file_name

    @trace_operation
    def save_transaction_to_file(
            self, mode: ButtonActions.SaveMenuActions | None = None, file_format: OutputFilesFormat | None = None
    ) -> None:

        if not file_format:
            file_format = OutputFilesFormat.JSON

        file_name: str | None = None
        file_format: OutputFilesFormat = file_format.lower()
        transactions: dict[str, Transaction] = dict()

        if not (file_data := self.get_output_filename(mode == ButtonActions.SaveMenuActions.ALL_TABS)):
            logger.warning("No output file or directory selected")
            return

        if mode == ButtonActions.SaveMenuActions.CURRENT_TAB:
            file_name, file_format = file_data

            if not all([file_name, file_format]):
                logger.warning("No output file or directory selected")
                return

        try:
            match mode:
                case ButtonActions.SaveMenuActions.ALL_TABS:
                    transactions = self.parse_main_window(clean=True, flat_fields=False)

                case ButtonActions.SaveMenuActions.CURRENT_TAB:
                    tab_name = self.window.get_tab_name()
                    transactions = {tab_name: self.parse_main_window_tab(clean=True, flat_fields=False)}

        except Exception as file_saving_error:
            logger.error(f"File saving error: {file_saving_error}")
            return

        for tab_name, transaction in transactions.items():
            for extension in OutputFilesFormat:
                if mode == ButtonActions.SaveMenuActions.CURRENT_TAB:
                    break

                if not tab_name.upper().endswith(f".{extension}"):
                    continue

                extension_len = len(extension) + 1
                tab_name = tab_name[:-extension_len]

                break

            if mode == ButtonActions.SaveMenuActions.ALL_TABS:
                file_name = f"{file_data}/{tab_name}"
                file_name = f"{file_name}.{file_format}" if not file_name.lower().endswith(file_format) else file_name

            try:
                self.trans_validator.validate_transaction(transaction)

            except DataValidationWarning as validation_warning:
                logger.warning(validation_warning)

            except Exception as validation_error:
                logger.error(validation_error)
                return

            Terminal.save_transaction(self, transaction, file_format, file_name)

    def print_data(self, data_format: PrintDataFormats) -> None:
        data_processing_map: dict[str, Callable] = {
            DataFormats.JSON: lambda: self.parse_main_window_tab(None, False, True).model_dump_json(indent=4),
            DataFormats.DUMP: lambda: self.parser.create_sv_dump(self.parse_main_window_tab()),
            DataFormats.INI: lambda: self.parser.transaction_to_ini_string(self.parse_main_window_tab()),
            DataFormats.TERM: lambda: TextConstants.HELLO_MESSAGE + "\n",
            DataFormats.SPEC: lambda: self.spec.spec.model_dump_json(indent=4),
            DataFormats.CONFIG: lambda: self.config.model_dump_json(indent=4),
        }

        if not (function := data_processing_map.get(data_format)):
            logger.error(f"Unsupported print format: {data_format}")
            return

        try:
            self.window.set_log_data(function(), data_format=data_format)

        except AttributeError:
            logger.error("Cannot construct message: missing field specification."
                         " Correct the specification or turn off field validation")

        except Exception as validation_error:
            logger.error(f"Cannot construct message: {validation_error}")

    def copy_log(self) -> None:
        self.set_clipboard_text(self.window.get_log_data())

    def copy_bitmap(self) -> None:
        if self.set_clipboard_text(self.window.get_bitmap_data()):
            logger.info("The bitmap was copied")

    def copy_specification(self, spec_window: SpecWindow):
        self.set_clipboard_text(dumps(loads(spec_window.spec.spec.json()), indent=2))
        logger.info("Specification JSON copied to clipboard")

    @staticmethod
    def set_clipboard_text(data: str = str()) -> bool:
        return copy_text(data)

    @set_json_view_focus
    def show_reversal_window(self) -> str | None:
        reversible_transactions_list: list[Transaction] = self.trans_queue.get_reversible_transactions()
        reversible_transactions_list.sort(key=lambda transaction: transaction.trans_id, reverse=True)

        reversal_window: ReversalWindow = ReversalWindow(reversible_transactions_list)
        accepted: int = reversal_window.exec()

        if not bool(accepted):
            logger.warning("Reversal canceled")
            return ""

        try:
            return reversal_window.reversal_id

        except AttributeError:
            logger.error("Cannot create reversal: invalid or missing transaction ID")
            return ""

    def copy_current_field(self):
        if not (field_data := self.window.tab_view.get_current_field_data()):
            field_data = str()

        self.set_clipboard_text(field_data)

    @set_json_view_focus
    def set_default_values(self, log=True) -> bool:
        try:
            parsed = self.parse_file(str(TermFilesPath.DEFAULT_FILE), log=False, new_tab=False)

        except Exception as parsing_error:
            logger.error(f"Cannot parse default file: {parsing_error}")
            return False

        else:
            if parsed and log:
                logger.debug('Default transaction successfully parsed using specification: {}', self.spec.name)
            return parsed

    @trace_operation
    def process_files_drop(self, incoming_files: list[str]):
        for incoming_file in incoming_files:
            self.parse_file(incoming_file, new_tab=True)

    def process_text_drop(self, text):
        try:
            transaction = self.parser.parse_text(text)
        except Exception as error:
            logger.error(f'Text parsing error: {error}')
            return
        self.window.tab_view.add_tab()
        self.window.set_tab_name('Dropped text')
        self.parse_transaction(transaction)

    @set_json_view_focus
    @trace_operation
    def parse_file(self, incoming_filename: str | None = None, log=True, new_tab: bool = False) -> bool:
        filenames: list[str] = []
        parsed_count = 0

        if incoming_filename:
            filenames.append(incoming_filename)

        if not filenames and not (filenames := self.get_input_filename(multiple_files=True)):
            logger.warning("No input files selected")
            return False

        for filename in filenames:

            try:
                transaction: Transaction = self.parser.parse_file(filename)

            except (DataValidationError, ValidationError, ValueError) as validation_error:
                logger.error(f"File parsing error: {validation_error}")
                continue

            except Exception as parsing_error:
                logger.error(f"File parsing error: {parsing_error}")
                continue

            if new_tab:
                self.window.tab_view.add_tab()
                self.window.set_tab_name(basename(filename))

            try:
                if not self.parse_transaction(transaction):
                    continue
            except Exception as fields_setting_error:
                logger.error(fields_setting_error)
                continue

            parsed_count += 1
            if log:
                logger.info(f"File parsed: {filename}")
        return parsed_count == len(filenames)

    @set_json_view_focus
    @trace_operation
    def parse_transaction(self, transaction: Transaction, generate_trans_id=True) -> bool:
        try:
            self.window.tab_view.set_mti_value(transaction.message_type)
            self.window.tab_view.set_transaction_fields(transaction, generate_trans_id=generate_trans_id)
            self.set_bitmap()

        except DataValidationWarning as validation_warning:
            [logger.warning(warn) for warn in str(validation_warning).splitlines()]

        except Exception as transaction_parsing_error:
            logger.error(f"Cannot set transaction fields: {transaction_parsing_error}")
            return False

        if self.config.validation.validation_enabled and self.config.validation.validate_window:
            self.modify_fields_data()
        return True

    def set_bitmap(self) -> None:
        bitmap: set[str] = set()

        for bit in self.window.json_view.get_top_level_field_numbers():
            if not bit.isdigit():
                continue

            if int(bit) not in range(1, MessageLength.SECOND_BITMAP_CAPACITY + 1):
                continue

            if not (self.window.json_view.field_has_data(bit) or bit in self.window.get_fields_to_generate()):
                continue

            if int(bit) > MessageLength.FIRST_BITMAP_CAPACITY:
                bitmap.add(self.spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY)

            bitmap.add(bit)

        self.window.set_bitmap(", ".join(sorted(bitmap, key=int)))

    @set_json_view_focus
    def clear_message(self) -> None:
        self.window.tab_view.clear_message()
        self.set_bitmap()

    def set_generated_fields_to_gui(self, transaction: Transaction) -> None:
        if transaction.is_keep_alive:
            return

        for field in transaction.generate_fields:

            if not self.spec.can_be_generated([field]):
                continue

            if not transaction.data_fields.get(field):
                transaction.data_fields[field]: str = self.generator.generate_field(field)

            self.window.json_view.set_field_value(field, transaction.data_fields.get(field))

        self.window.json_view.set_trans_id(transaction.trans_id)
