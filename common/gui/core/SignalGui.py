from sys import exit as sys_exit
from os import getcwd, kill, getpid
from os.path import basename, normpath
from typing import Callable
from loguru import logger
from pydantic import ValidationError
from webbrowser import open as open_url
from PyQt6.QtWidgets import QApplication, QFileDialog
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
from common.gui.core.ConnectionThread import ConnectionThread
from common.gui.enums import ButtonActions
from common.gui.enums.Colors import Colors
from common.gui.enums.GuiFilesPath import GuiDirs
from common.lib.enums import KeepAlive
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.enums.DataFormats import DataFormats, PrintDataFormats, OutputFilesFormat, InputFilesFormat
from common.lib.enums.MessageLength import MessageLength
from common.lib.enums.TextConstants import TextConstants
from common.lib.core.TransTimer import TransactionTimer
from common.lib.core.SpecFilesRotator import SpecFilesRotator
from common.lib.core.Terminal import Terminal
from common.lib.data_models.Config import Config
from common.lib.data_models.Transaction import Transaction, TypeFields
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel
from common.api.core.SignalApi import SignalApi
from common.api.enums.ApiModes import ApiModes
from common.lib.exceptions.exceptions import (
    LicenceAlreadyAccepted,
    LicenseDataLoadingError,
    DataValidationWarning,
    DataValidationError
)


"""
The core of the GUI backend
 
Performs all the management and control. The main purpose is to receive a validated data-processing request from 
MainWindow or TransactionQueue and manage this using the other low-level modules such as Parser for data transformation
TransactionQueue for interaction with the target system, Connector for TCP integration, and so on. 
 
Always tries not to do the work itself, managing corresponding modules instead

SignalGui is a basic executor for all user requests. Inherited from Terminal class, which does not interact 
with GUI anyhow. Low-level data processing performs using the basic Terminal class.

Usually get data in the Transaction format. In any other case targeting to transform data into the Transaction and 
proceed to work with this. The Transaction is a common I/O format for SignalGui. 
 
Starts MainWindow when starting its work, being a kind of low-level adapter between the GUI and the system's core
"""


class SignalGui(SignalApi):
    connector: ConnectionThread
    trans_timer: TransactionTimer = TransactionTimer(KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION)
    set_remote_spec: pyqtSignal = pyqtSignal()
    _run_timer = QTimer()
    _generated_echo_test_transactions: list[Transaction] = []

    def set_json_view_focus(function: callable):

        # This decorator sets focus on the self.window.json_view after the decorated function execution is finished

        def wrapper(self, *args, **kwargs):
            try:
                return function(self, *args, **kwargs)

            finally:
                self.window.set_focus()

        return wrapper

    def __init__(self, config: Config):
        self.connector: ConnectionThread = ConnectionThread(config)
        super(SignalGui, self).__init__(config=config, connector=self.connector)
        self.window: MainWindow = MainWindow(self.config)
        self.thread_pool: QThreadPool = QThreadPool()
        self.connect_widgets()
        self.setup()

    def setup(self) -> None:
        QDir.addSearchPath(GuiDirs.STYLE_DIR.name, GuiDirs.STYLE_DIR)
        self._run_timer.setSingleShot(True)
        self._run_timer.start(int())
        self.logger.add_wireless_handler(self.window.log_browser)

    def on_startup(self) -> None:  # Runs on startup to make all the preparation activity, then shows MainWindow
        self.show_license_dialog()

        self.log_printer.print_startup_info()

        self.print_data(DataFormats.TERM)

        if self.config.terminal.process_default_dump:
            self.set_default_values()

        if self.config.host.keep_alive_mode:
            interval: int = self.config.host.keep_alive_interval
            self.keep_alive_timer.set_trans_loop_interval(KeepAlive.IntervalNames.KEEP_ALIVE_DEFAULT % interval)

        if self.config.terminal.load_remote_spec:
            self.set_remote_spec.emit()

        if self.config.specification.backup_storage:
            rotator: SpecFilesRotator = SpecFilesRotator()
            rotator.clear_spec_backup(self.config)

        if self.config.terminal.connect_on_startup:
            self.reconnect()

        if self.config.terminal.run_api:
            self.process_change_api_mode(state=ApiModes.START)

        self.window.json_view.enable_json_mode_checkboxes(enable=not self.config.specification.manual_input_mode)

        self.window.show()

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
            window.hotkeys: lambda: HotKeysHintWindow().exec(),
            window.specification: self.run_specification_window,
            window.about: lambda: self.settings(about=True),
            window.keep_alive: self.keep_alive_timer.set_trans_loop_interval,
            window.repeat: self.trans_timer.set_trans_loop_interval,
            window.validate_message: lambda force: self.validate_main_window(force=force),
            window.parse_complex_field: lambda: ComplexFieldsParser(self.config, self).exec(),
            window.api_mode_changed: self.process_change_api_mode,
            window.exit: sys_exit,
            window.show_document: self.show_document,
            window.show_license: lambda: self.show_license_dialog(force=True),
            window.disable_item: lambda: self.disable_item(disable=True),
            window.enable_item: lambda: self.disable_item(disable=False),
            window.enable_all_items: lambda: self.disable_item(False, self.window.json_view.root, go_next=False),
            window.files_dropped: self.process_files_drop,
            window.undo: window.undo_changes,
            window.redo: window.redo_changes,
            self.connector.stateChanged: self.set_connection_status,
            self.set_remote_spec: self.connector.get_remote_spec,
            self.connector.got_remote_spec: self.load_remote_spec,
            self.trans_timer.send_transaction: window.send,
            self.trans_timer.interval_was_set: window.process_transaction_loop_change,
            self.keep_alive_timer.interval_was_set: window.process_transaction_loop_change,
            self.api.api_started: window.process_api_mode_change,
            self.api.api_stopped: window.process_api_mode_change,
            self._run_timer.timeout: self.on_startup,
        }

        for signal, slot in terminal_connections_map.items():
            signal.connect(slot)

    def read_config(self, config_file: str | None = None):
        Terminal.read_config(self, config_file)

        for tool in self.window, self.connector:
            tool.config = self.config

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
        doc_path = normpath(f"{getcwd()}/{GuiFilesPath.DOC}")
        open_url(doc_path)

    def show_license_dialog(self, force: bool = False) -> None:
        try:
            license_window: LicenseWindow = LicenseWindow(self.config, force=force)
            license_window.exec()
            self.config.terminal.show_license_dialog = license_window.license_info.show_agreement

        except LicenseDataLoadingError as license_data_loading_error:
            logger.error(license_data_loading_error)
            exit(100)

        except LicenceAlreadyAccepted:
            return

    @set_json_view_focus
    def run_specification_window(self) -> None:
        old_spec = self.spec.spec.json()

        self.logger.remove()
        spec_window = SpecWindow(self.connector, self.config)
        spec_window.exec()
        self.logger.add_wireless_handler(self.window.log_browser)

        if self.config.fields.hide_secrets:
            self.window.json_view.hide_secrets()

        specification_changed = old_spec != self.spec.spec.json()

        if specification_changed and self.config.validation.validation_enabled:
            if self.config.validation.validate_window:
                logger.info("Validate message after spec settings")
                self.validate_main_window()

            if self.config.specification.manual_input_mode:
                self.modify_fields_data()
                self.window.json_view.refresh_fields(Colors.BLACK)

    def modify_fields_data(self):  # Set extended data modifications, set in field params
        self.window.json_view.modify_all_fields_data()

    def load_remote_spec(self, spec_data: str) -> None:
        try:
            epay_spec: EpaySpecModel = EpaySpecModel.model_validate_json(spec_data)
        except (ValidationError, ValueError) as spec_parsing_error:
            logger.error(f"Remote spec processing error: {spec_parsing_error}")
            logger.warning("Local specification will be used instead")
            return

        try:
            self.spec.reload_spec(spec=epay_spec, commit=self.config.specification.rewrite_local_spec)
        except Exception as spec_reload_error:
            logger.error(spec_reload_error)
            logger.warning("Local specification will be used instead")
            return

        logger.info(f"Remote specification loaded: {epay_spec.name}")

    def validate_main_window(self, force: bool = False) -> None:
        self.window.validate_fields(force=force)
        self.window.json_view.refresh_fields()

        logger.info("Transaction data validated")

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
    def settings(self, about=False) -> None:
        try:
            old_config: Config = self.config.model_copy(deep=True)
            settings_window: SettingsWindow = SettingsWindow(self.config, about=about)
            settings_window.accepted.connect(lambda: self.process_config_change(old_config))
            settings_window.open_user_guide.connect(self.show_document)
            settings_window.exec()
            
        except Exception as settings_error:
            logger.error(settings_error)

    def process_config_change(self, old_config: Config) -> None:
        Terminal.process_config_change(self, old_config)
        self.api.config = self.config

        if self.config.debug.level != old_config.debug.level:
            self.logger.remove()
            self.logger.add_wireless_handler(self.window.log_browser)

        self.window.json_view.enable_json_mode_checkboxes(enable=self.config.validation.validate_window)

        validation_conditions = [
            old_config.validation.validate_window != self.config.validation.validate_window,
            old_config.validation.validation_mode != self.config.validation.validation_mode,
        ]

        if self.config.validation.validation_enabled and any(validation_conditions):

            if self.config.validation.validate_window:
                self.modify_fields_data()
                self.validate_main_window()

            if not self.config.validation.validate_window:
                self.window.json_view.refresh_fields(color=Colors.BLACK)

        if old_config.specification.manual_input_mode != self.config.specification.manual_input_mode:
            self.window.json_view.refresh_fields(color=Colors.BLACK)

        if old_config.fields.json_mode != self.config.fields.json_mode:
            self.window.json_view.switch_json_mode(self.config.fields.json_mode)

        if old_config.fields.hide_secrets != self.config.fields.hide_secrets:
            self.window.json_view.hide_secrets()

        spec_loading_conditions: list[bool] = [
            self.config.specification.remote_spec_url,
            old_config.specification.remote_spec_url != self.config.specification.remote_spec_url,
        ]

        if all(spec_loading_conditions):
            try:
                self.data_validator.validate_url(self.config.specification.remote_spec_url)

            except (ValidationError, DataValidationError, DataValidationWarning) as url_validation_error:
                logger.error(f"Remote spec URL validation error: {url_validation_error}")

            else:
                self.set_remote_spec.emit()

        keep_alive_change_conditions: list[bool] = [
            old_config.host.keep_alive_mode != self.config.host.keep_alive_mode,
            old_config.host.keep_alive_interval != self.config.host.keep_alive_interval
        ]

        if any(keep_alive_change_conditions):
            interval_name: str = KeepAlive.IntervalNames.KEEP_ALIVE_STOP

            if self.config.host.keep_alive_mode:
                interval_name: str = KeepAlive.IntervalNames.KEEP_ALIVE_DEFAULT % self.config.host.keep_alive_interval

            self.keep_alive_timer.set_trans_loop_interval(interval_name)

        logger.info("Settings applied")

    def stop_signal(self) -> None:
        self.connector.stop_thread()
        kill(getpid(), 3)

    def reconnect(self) -> None:
        Terminal.reconnect(self)

    def set_connection_status(self) -> None:
        self.window.set_connection_status(self.connector.state())

        if self.connector.state() is QTcpSocket.SocketState.ConnectingState:
            self.window.block_connection_buttons()
            return

        self.window.unblock_connection_buttons()

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

    def send(self, transaction: Transaction | None = None, is_api_call=False) -> None:
        if self.connector.connection_in_progress():
            transaction.success = False
            transaction.error = "Cannot send the transaction while the host connection is in progress"
            logger.error(transaction.error)
            return

        if transaction is None:
            try:
                transaction: Transaction = self.parse_main_window_tab()

                if not transaction:
                    raise ValueError

            except Exception as building_error:
                [logger.error(err) for err in str(building_error).splitlines()]
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
        file_name_filters = [f"{data_format} (*.{data_format.lower()})" for data_format in InputFilesFormat]
        file_name_filters.append("Any (*.*)")
        file_name_filter = ";;".join(file_name_filters)

        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_function = file_dialog.getOpenFileNames

        if not multiple_files:
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            file_function = file_dialog.getOpenFileName

        file_data = file_function(filter=file_name_filter, initialFilter=InputFilesFormat.JSON)

        if not (file_name := file_data[int()]):
            return

        return file_name

    def save_transaction_to_file(self, mode: ButtonActions.SaveMenuActions | None = None,
                                 file_format: OutputFilesFormat | None = None) -> None:

        if not file_format:
            file_format = OutputFilesFormat.JSON

        file_name: str | None = None
        file_format: OutputFilesFormat = file_format.lower()
        transactions: dict[str, Transaction] = dict()

        if not (file_data := self.get_output_filename(mode == ButtonActions.SaveMenuActions.ALL_TABS)):
            logger.warning("No output filename or directory recognized")
            return

        if mode == ButtonActions.SaveMenuActions.CURRENT_TAB:
            file_name, file_format = file_data

            if not all([file_name, file_format]):
                logger.warning("No output filename or directory recognized")
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
            logger.error(f"Wrong data format for printing: {data_format}")
            return

        try:
            self.window.set_log_data(function())

        except AttributeError:
            logger.error("Cannot construct message: lost field specification."
                         " Correct spec or turn field validation off")

        except Exception as validation_error:
            logger.error(f"Cannot construct message: {validation_error}")

    def copy_log(self) -> None:
        self.set_clipboard_text(self.window.get_log_data())

    def copy_bitmap(self) -> None:
        self.set_clipboard_text(self.window.get_bitmap_data())
        logger.info("The bitmap copied")

    @staticmethod
    def set_clipboard_text(data: str = str()) -> None:
        QApplication.clipboard().setText(data)

    def show_reversal_window(self) -> str | None:
        reversible_transactions_list: list[Transaction] = self.trans_queue.get_reversible_transactions()
        reversible_transactions_list.sort(key=lambda transaction: transaction.trans_id, reverse=True)

        reversal_window: ReversalWindow = ReversalWindow(reversible_transactions_list)
        accepted: int = reversal_window.exec()

        if bool(accepted):
            try:
                return reversal_window.reversal_id

            except AttributeError:
                logger.error("Cannot create reversal. Wrong or empty transaction ID")
                return ""

        logger.warning("Reversal sending is cancelled")

    def copy_current_field(self):
        if not (field_data := self.window.tab_view.get_current_field_data()):
            field_data = str()

        self.set_clipboard_text(field_data)

    @set_json_view_focus
    def set_default_values(self, log=True) -> None:
        try:
            self.parse_file(str(TermFilesPath.DEFAULT_FILE), log=False, new_tab=False)

        except Exception as parsing_error:
            logger.error(f"Default file parsing error! Exception: {parsing_error}")

        else:
            logger.info("Default file parsed") if log else ...

    def process_files_drop(self, incoming_files: list[str]):
        for incoming_file in incoming_files:
            self.parse_file(incoming_file, new_tab=True)

    @set_json_view_focus
    def parse_file(self, incoming_filename: str | None = None, log=True, new_tab: bool = False) -> None:
        filenames: list[str] = []

        if incoming_filename:
            filenames.append(incoming_filename)

        if not filenames and not (filenames := self.get_input_filename(multiple_files=True)):
            logger.warning("No input filename(s) recognized")
            return

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
                self.set_default_values(log=False)
                self.window.set_tab_name(basename(filename))

            try:
                self.parse_transaction(transaction)
            except Exception as fields_setting_error:
                logger.error(fields_setting_error)
                continue

            if log:
                logger.info(f"File parsed: {filename}")

    @set_json_view_focus
    def parse_transaction(self, transaction: Transaction, generate_trans_id=True) -> None:
        # transaction: Transaction = self.sort_transaction_fields(transaction)

        try:
            self.window.tab_view.set_mti_value(transaction.message_type)
            self.window.tab_view.set_transaction_fields(transaction, generate_trans_id=generate_trans_id)
            self.set_bitmap()

        except DataValidationWarning as validation_warning:
            [logger.warning(warn) for warn in str(validation_warning).splitlines()]

        except Exception as transaction_parsing_error:
            logger.error(f"Cannot set transaction fields: {transaction_parsing_error}")
            return

        if self.config.validation.validation_enabled and self.config.validation.validate_window:
            self.modify_fields_data()

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
