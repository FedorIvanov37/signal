from common.core.tools.DebugTrace import trace_operation
from pathlib import Path
from loguru import logger
from typing import Callable
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtNetwork import QTcpSocket
from common.core.tools.SpecFilesRotator import SpecFilesRotator
from common.core.interfaces.ConnectorInterface import ConnectionInterface
from common.core.tools.Parser import Parser
from common.core.tools.Logger import Logger
from common.core.tools.TransactionQueue import TransactionQueue
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.tools.FieldsGenerator import FieldsGenerator
from common.core.tools.validators.TransValidator import TransValidator
from common.core.tools.validators.DataValidator import DataValidator
from common.core.data_models.Config import Config
from common.core.data_models.Transaction import Transaction
from common.core.tools.Connector import Connector
from common.core.tools.ConfigStore import save_config
from common.core.tools.ConfigManager import ConfigManager, ConfigView
from common.core.tools.ErrorReporting import log_error
from common.core.exceptions.exceptions import SignalError
from common.core.tools.LogPrinter import LogPrinter
from common.core.tools.TransTimer import TransactionTimer
from common.core.data_models.Currencies import Currencies
from common.core.data_models.Countries import Countries
from common.core.enums.DataFormats import DataFormats
from common.core.enums import KeepAlive
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.data_models.License import LicenseInfo
from common.core.enums.ConnectionStatus import ConnectionStatus


class Terminal(QObject):
    spec: EpaySpecification = None
    keep_alive_timer: TransactionTimer
    currencies_dictionary: Currencies
    countries_dictionary: Countries
    trans_validator: TransValidator
    need_reconnect: pyqtSignal = pyqtSignal(str, str)

    def __init__(self, config: Config, connector: ConnectionInterface | None = None, application=None):
        super(Terminal, self).__init__()

        self.keep_alive_timer = TransactionTimer(KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE)
        self.pyqt_application = application if application is not None else QCoreApplication.instance() or QCoreApplication([])
        self.config_manager = config.manager if isinstance(config, ConfigView) else ConfigManager(config)
        self.config = self.config_manager.view

        if connector is None:
            connector: Connector = Connector(self.config)
        elif connector.config is not self.config:
            connector.config = self.config  # Bind an externally supplied connector once.

        self.trans_validator = TransValidator(self.config)
        self.data_validator = DataValidator(self.config)
        self.log_printer: LogPrinter = LogPrinter(self.config)
        self.connector: Connector = connector
        self.parser: Parser = Parser(self.config)
        self.generator: FieldsGenerator = FieldsGenerator()
        self.logger: Logger = Logger(self.config)
        self.trans_queue: TransactionQueue = TransactionQueue(self.connector)
        self.spec: EpaySpecification = EpaySpecification(Path(TermFilesPath.SPECIFICATION))
        self.connect_interfaces()
        self.config_manager.subscribe(lambda old, new: self.process_config_change(old))

    @trace_operation
    def run_application(self) -> int:
        return self.pyqt_application.exec()

    def connect_interfaces(self) -> None:
        self.connector.errorOccurred.connect(self.socket_error)
        self.need_reconnect.connect(self.connector.reconnect_sv)
        self.connector.connected.connect(self.sv_connected)
        self.connector.disconnected.connect(self.sv_disconnected)
        self.trans_queue.incoming_transaction.connect(self.transaction_received)
        self.trans_queue.outgoing_transaction.connect(self.transaction_sent)
        self.trans_queue.transaction_timeout.connect(self.got_timeout)
        self.keep_alive_timer.send_transaction.connect(self.keep_alive)

    @staticmethod
    def sort_transaction_fields(transaction: Transaction) -> Transaction:
        transaction.data_fields = {field: transaction.data_fields.get(field) for field in transaction.data_fields}
        return transaction

    def get_connection_status(self) -> ConnectionStatus:
        return ConnectionStatus[self.connector.state().name]

    def get_transaction(self, trans_id: str) -> Transaction:
        return self.trans_queue.get_transaction(trans_id)

    @staticmethod
    def sv_connected() -> None:
        logger.info("Connection ESTABLISHED")

    @staticmethod
    def sv_disconnected() -> None:
        logger.info("Connection DISCONNECTED")

    @staticmethod
    def got_timeout(transaction, timeout_secs) -> None:
        logger.error(
            f"Transaction [{transaction.trans_id}] timeout after {int(timeout_secs)} seconds of waiting answer"
        )

    def socket_error(self) -> None:
        if self.connector.error() == QTcpSocket.SocketError.UnknownSocketError:
            return

        logger.error(f"Received a socket error from host: {self.connector.errorString()}")

    def disconnect(self) -> None:
        self.connector.disconnect_sv()

    def reconnect(self, host: str | None = None, port: str | None = None) -> None:
        if self.connector.connection_in_progress():
            logger.warning("Cannot reconnect while a connection is in progress")
            return

        if host is None:
            host = self.config.host.host

        if port is None:
            port = self.config.host.port

        self.need_reconnect.emit(host, str(port))

    def save_config(self, config: Config | None = None):
        if config is None:
            config = self.config

        save_config(config, self.config_manager.filename)

    @trace_operation
    def update_config(self, config: Config, *, persist=True, expected_revision=None):
        return self.config_manager.replace(config, persist=persist, expected_revision=expected_revision)

    @trace_operation
    def send(self, transaction: Transaction) -> None:
        self.spec.require_ready()
        try:
            if transaction.generate_fields:
                transaction = self.generator.set_generated_fields(transaction)
            self.trans_queue.put_transaction(transaction)
        except Exception as error:
            # This method is also a Qt slot: report failure through the request channel.
            transaction.success = False
            transaction.error = str(error) if isinstance(error, (SignalError, ValueError)) else "Transaction preparation failed; see the diagnostic log"
            log_error(error, "Transaction preparation failed")
            self.trans_queue.socket_error.emit(transaction)

    @trace_operation
    def backup_spec(self):
        if not (backup_filename := SpecFilesRotator(self.config).backup_spec()):
            return

        logger.debug(f"Specification backup completed. Filename: {backup_filename}")

    @trace_operation
    def process_config_change(self, old_config: Config) -> None:
        # Consumers already share the live view. Only behavioral changes belong here.
        if old_config.debug.model_dump() != self.config.debug.model_dump():
            self.logger.setup(wireless_handler=getattr(self, "wireless_handler", None),
                              filename=getattr(getattr(self, "_cli_config", None), "log_file", TermFilesPath.LOG_FILE_NAME))
            if getattr(self, "_cli_config", None) is not None and not self._cli_config.no_print:
                self.logger.add_stdout_handler()
        if (old_config.host.keep_alive_mode, old_config.host.keep_alive_interval) != (
                self.config.host.keep_alive_mode, self.config.host.keep_alive_interval):
            interval = KeepAlive.IntervalNames.KEEP_ALIVE_STOP
            if self.config.host.keep_alive_mode:
                interval = KeepAlive.IntervalNames.KEEP_ALIVE_DEFAULT % self.config.host.keep_alive_interval
            self.keep_alive_timer.set_trans_loop_interval(interval)

        if "" in (self.config.host.host, self.config.host.port):
            logger.warning("Missing SV address or port. Check the configuration")

        try:
            if not self.config.host.port:
                raise ValueError

            if int(self.config.host.port) > 65535:
                raise ValueError

        except ValueError:
            logger.warning(
                f"Incorrect SV port value: {self.config.host.port}. Must be a number in the range of 0 to 65535"
            )

        if old_config.terminal.show_license_dialog == self.config.terminal.show_license_dialog:
            return

        try:
            license_info = LicenseInfo(TermFilesPath.LICENSE_INFO)
            license_info.show_agreement = self.config.terminal.show_license_dialog

            if not license_info.accepted:
                raise ValueError("License has not been accepted")

            with open(TermFilesPath.LICENSE_INFO, "w") as license_json:
                license_json.write(license_info.model_dump_json(indent=4))

        except ValueError as not_accepted:
            raise SignalError(f"Cannot apply settings: {not_accepted}") from not_accepted

        except Exception as license_error:
            logger.error(f"Cannot save license information: {license_error}")

    @trace_operation
    def read_config(self, config_file: str | None = None) -> None:

        filename = config_file if config_file is not None else self.config_manager.filename
        return self.update_config(Config(filename), persist=False)

    def transaction_sent(self, request: Transaction) -> None:
        try:
            self.log_printer.print_dump(request)
        except Exception as parsing_error:
            logger.error(f"Data parsing error: {parsing_error}")
            return

        try:
            self.log_printer.print_transaction(request)
        except Exception as print_error:
            logger.error(f"Transaction printing error: {print_error}")

        if not request.is_keep_alive:
            logger.info(f"Outgoing transaction ID [{request.trans_id}] sent")
            logger.info("")

    @trace_operation
    def transaction_received(self, response: Transaction) -> None:
        resp_trans_id = response.match_id if response.matched else response.trans_id

        if not response.is_keep_alive:
            logger.info(f"Incoming transaction ID [{resp_trans_id}] received")

        validation_conditions = (
            self.config.validation.validation_enabled,
            self.config.validation.validate_incoming,
            not response.is_keep_alive
        )

        if all(validation_conditions):
            try:
                self.trans_validator.validate_transaction(transaction=response)

            except Exception as validation_error:
                [logger.warning(warn) for warn in str(validation_error).splitlines()]

        try:
            self.log_printer.print_dump(response)
        except Exception as parsing_error:
            logger.debug(f"Cannot print transaction dump, data parsing error: {parsing_error}")

        if response.is_keep_alive and self.config.debug.reduce_keep_alive:
            return

        try:
            self.log_printer.print_transaction(response)
        except Exception as parsing_error:
            logger.error(f"Cannot print transaction, data parsing error: {parsing_error}")

        if response.matched and response.resp_time_seconds:

            if response.is_keep_alive:
                resp = response.data_fields.get(self.spec.FIELD_SET.FIELD_039_AUTHORIZATION_RESPONSE_CODE, 'Unknown')
                message: str = (
                    f'Keep Alive transaction [{response.match_id}] successfully done. Response code: "{resp}"'
                )

            if not response.is_keep_alive:
                message: str = f"Transaction ID [{response.match_id}] matched"

            message: str = f"{message}, response time seconds: {response.resp_time_seconds}"

            logger.info(message)

        if not response.matched:
            match_fields: list[str] = [field for field in self.spec.get_match_fields() if field in response.data_fields]
            match_fields: str = ', '.join(match_fields)
            logger.warning(f"Unmatched transaction received. Transaction ID [{response.trans_id}]")
            logger.warning(f"Fields {match_fields} from the response don't correspond to any requests in the current "
                           f"session or request was matched before")

    @trace_operation
    def keep_alive(self) -> None:
        if self.connector.connection_in_progress():
            return

        try:
            transaction: Transaction = self.parser.parse_file(TermFilesPath.KEEP_ALIVE)

        except Exception as transaction_building_error:
            logger.error(f"Cannot build keep-alive transaction: {transaction_building_error}")
            return

        transaction.generate_fields = []
        transaction.is_keep_alive = True

        message: str = (f"Trans ID: [{transaction.trans_id}], STAN: "
                        f"[{transaction.data_fields.get(self.spec.FIELD_SET.FIELD_011_SYSTEM_TRACE_AUDIT_NUMBER)}], "
                        f"Network management code: "
                        f"[{transaction.data_fields.get(self.spec.FIELD_SET.FIELD_070_NETWORK_MANAGEMENT_CODE)}]")

        if not self.config.debug.reduce_keep_alive:
            logger.info(f"Sending Keep Alive message - {message}")

        self.send(transaction)

    @trace_operation
    def save_transaction(self, transaction: Transaction, file_format: str, file_name) -> None:
        data_processing_map: dict[str, Callable] = {
            DataFormats.JSON: lambda _trans: _trans.model_dump_json(indent=4),
            DataFormats.INI: lambda _trans: self.parser.transaction_to_ini_string(_trans),
            DataFormats.DUMP: lambda _trans: self.parser.create_sv_dump(_trans)[1:]
        }

        if not (data_processing_function := data_processing_map.get(file_format.upper())):
            logger.error("Unknown output file format")
            return

        try:
            if not (file_data := data_processing_function(transaction)):
                logger.error("No data to save")
                return

        except Exception as data_processing_error:
            logger.error(f"Cannot save transaction: {data_processing_error}")
            return

        with open(file_name, "w") as file:
            file.write(file_data)

        logger.info(f"The transaction was saved successfully to {file_name}")

    @trace_operation
    def build_reversal(self, original_transaction: Transaction) -> Transaction:
        if not (original_transaction.matched and original_transaction.match_id):
            raise LookupError(f"Missing response for transaction {original_transaction.trans_id}. Cannot build reversal")

        reversal_trans_id: str = original_transaction.trans_id + "_R"
        existed_reversal: Transaction | None = self.trans_queue.get_transaction(reversal_trans_id)

        if existed_reversal:
            self.trans_queue.remove_from_queue(existed_reversal)
            transaction: Transaction = Transaction.model_validate(existed_reversal)
            transaction.matched = None
            transaction.generate_fields = []
            return transaction

        fields: dict = original_transaction.data_fields.copy()

        for field in self.spec.get_reversal_fields():
            fields[field]: str = original_transaction.data_fields.get(field)

        if self.config.fields.build_fld_90:
            field90 = self.generator.generate_original_data_elements(original_transaction)
            fields[self.spec.FIELD_SET.FIELD_090_ORIGINAL_DATA_ELEMENTS] = field90

        if not (reversal_mti := self.spec.get_reversal_mti(original_transaction.message_type)):
            raise LookupError(f"Original transaction has non-reversible MTI: {original_transaction.message_type}")
        
        reversal: Transaction = Transaction(
            message_type=reversal_mti,
            data_fields=fields,
            trans_id=reversal_trans_id,
            generate_fields=list(),
            utrnno=original_transaction.utrnno,
            is_reversal=True,
        )

        reversal: Transaction = self.generator.set_trans_id(reversal)

        return reversal
