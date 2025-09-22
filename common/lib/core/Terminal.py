from loguru import logger
from typing import Callable
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtNetwork import QTcpSocket
from common.lib.interfaces.ConnectorInterface import ConnectionInterface
from common.lib.core.Parser import Parser
from common.lib.core.Logger import Logger
from common.lib.core.TransactionQueue import TransactionQueue
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.core.FieldsGenerator import FieldsGenerator
from common.lib.core.validators.TransValidator import TransValidator
from common.lib.core.validators.DataValidator import DataValidator
from common.lib.data_models.Config import Config
from common.lib.data_models.Transaction import Transaction
from common.lib.core.Connector import Connector
from common.lib.core.LogPrinter import LogPrinter
from common.lib.core.TransTimer import TransactionTimer
from common.lib.data_models.Currencies import Currencies
from common.lib.data_models.Countries import Countries
from common.lib.enums.DataFormats import DataFormats
from common.lib.enums import KeepAlive
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.data_models.License import LicenseInfo
from common.lib.enums.ConnectionStatus import ConnectionStatus


class Terminal(QObject):
    spec: EpaySpecification = EpaySpecification(TermFilesPath.SPECIFICATION)
    keep_alive_timer: TransactionTimer = TransactionTimer(KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE)
    currencies_dictionary: Currencies
    countries_dictionary: Countries

    with open(TermFilesPath.CONFIG) as json_file:
        config: Config = Config.model_validate_json(json_file.read())

    trans_validator: TransValidator
    need_reconnect: pyqtSignal = pyqtSignal()

    def __init__(self, config: Config, connector: ConnectionInterface | None = None, application=QApplication([])):
        super(Terminal, self).__init__()

        self.pyqt_application = application
        self.config: Config = config

        if connector is None:
            connector: Connector = Connector(self.config)

        self.trans_validator = TransValidator(self.config)
        self.data_validator = DataValidator(self.config)
        self.log_printer: LogPrinter = LogPrinter(self.config)
        self.connector: Connector = connector
        self.parser: Parser = Parser(self.config)
        self.generator: FieldsGenerator = FieldsGenerator()
        self.logger: Logger = Logger(self.config)
        self.trans_queue: TransactionQueue = TransactionQueue(self.connector)
        self.connect_interfaces()

    def run(self) -> int:
        status: int = self.pyqt_application.exec()
        return status

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
        logger.error(f"Transaction [{transaction.trans_id}] timeout after {int(timeout_secs)} seconds of waiting answer")

    def socket_error(self) -> None:
        if self.connector.error() == QTcpSocket.SocketError.UnknownSocketError:  # TODO
            return

        logger.error(f"Received a socket error from host: {self.connector.errorString()}")

    def disconnect(self) -> None:
        self.connector.disconnect_sv()

    def reconnect(self) -> None:
        if self.connector.connection_in_progress():
            logger.warning("Unable to reconnect while connection in progress")
            return

        logger.info("[Re]connecting...")

        self.need_reconnect.emit()

    def save_config(self, config: Config | None = None):
        if config is None:
            config = self.config

        with open(TermFilesPath.CONFIG, "w") as file:
            file.write(config.model_dump_json(indent=4))

    def send(self, transaction: Transaction) -> None:
        self.trans_queue.put_transaction(transaction)

    def process_config_change(self, old_config: Config) -> None:
        self.read_config()

        if "" in (self.config.host.host, self.config.host.port):
            logger.warning("Lost SV address or SV port! Check the parameters")

        try:
            if not self.config.host.port:
                raise ValueError

            if int(self.config.host.port) > 65535:
                raise ValueError

        except ValueError:
            logger.warning(f"Incorrect SV port value: {self.config.host.port}. Must be a number in the range of 0 to 65535")

        try:
            with open(TermFilesPath.LICENSE_INFO, "r") as license_json:
                license_info = LicenseInfo.model_validate_json(license_json.read())
                license_info.show_agreement = self.config.terminal.show_license_dialog

            if not license_info.accepted:
                raise ValueError("License is not accepted")

            with open(TermFilesPath.LICENSE_INFO, "w") as license_json:
                license_json.write(license_info.model_dump_json(indent=4))

        except ValueError as not_accepted:
            logger.error(not_accepted)
            exit(100)

        except Exception as license_error:
            logger.error(f"Cannot save license params: {license_error}")

    def read_config(self, config_file: str | None = None) -> None:

        if config_file is None:
            config_file = TermFilesPath.CONFIG

        try:
            with open(config_file) as json_file:
                self.config: Config = Config.model_validate_json(json_file.read())
                
        except Exception as parsing_error:
            logger.error(f"Cannot parse configuration file: {parsing_error}")

    def transaction_sent(self, request: Transaction) -> None:
        try:
            self.log_printer.print_dump(request)
        except Exception as parsing_error:
            logger.error(f"Data parsing error: {parsing_error}")
            return

        try:
            self.log_printer.print_transaction(request)
        except Exception as print_error:
            logger.error(f"Transaction print error {print_error}")

        if not request.is_keep_alive:
            logger.info(f"Outgoing transaction ID [{request.trans_id}] sent")

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
                message: str = (f'Keep Alive transaction [{response.match_id}] sucessfully done. Response code: "{resp}"')

            if not response.is_keep_alive:
                message: str = f"Transaction ID [{response.match_id}] matched"

            message: str = f"{message}, response time seconds: {response.resp_time_seconds}"

            logger.info(message)

        if not response.matched:
            match_fields: list[str] = [field for field in self.spec.get_match_fields() if field in response.data_fields]
            match_fields: str = ', '.join(match_fields)
            logger.warning(f"Non-matched Transaction received. Transaction ID [{response.trans_id}]")
            logger.warning(f"Fields {match_fields} from the response don't correspond to any requests in the current "
                           f"session or request was matched before")

    def keep_alive(self) -> None:
        if self.connector.connection_in_progress():
            return

        try:
            transaction: Transaction = self.parser.parse_file(TermFilesPath.KEEP_ALIVE)
            transaction: Transaction = self.generator.set_generated_fields(transaction)

        except Exception as transaction_building_error:
            logger.error(f"Keep alive transaction building error: {transaction_building_error}")
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

    def build_reversal(self, original_transaction: Transaction) -> Transaction:
        if not (original_transaction.matched and original_transaction.match_id):
            raise LookupError(f"Lost response for transaction {original_transaction.trans_id}. Cannot build reversal")

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
