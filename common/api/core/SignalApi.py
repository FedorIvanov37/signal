from contextlib import suppress
from http import HTTPStatus
from time import sleep
from datetime import datetime
from copy import deepcopy
from typing import Any
from loguru import logger
from fastapi import HTTPException
from threading import Lock
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtNetwork import QTcpSocket
from common.gui.enums.GuiFilesPath import GuiFiles
from common.api.enums.ApiFiles import ApiFiles
from common.lib.core.Parser import Parser
from common.lib.exceptions.exceptions import DataValidationError, DataValidationWarning
from common.lib.enums.TextConstants import TextConstants, ReleaseDefinition
from common.lib.core.Terminal import Terminal
from common.lib.data_models.Config import Config
from common.lib.core.SpecFilesRotator import SpecFilesRotator
from common.lib.data_models.Transaction import Transaction
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel
from common.lib.core.FieldsGenerator import FieldsGenerator
from common.api.data_models.TransValidationErrors import TransValidationErrors
from common.api.data_models.Connection import Connection
from common.api.enums.ApiModes import ApiModes
from common.api.data_models.ApiRequests import ApiTransactionRequest, ApiRequest, ConfigAction, ReversalRequest
from common.api.enums.ApiUrl import ApiUrl
from common.api.enums.DataCoversionFormats import DataConversionFormats
from common.api.data_models.ApiRequests import ApiRequestType
from common.api.exceptions.TerminalApiError import TerminalApiError
from common.api.data_models.TransactionResp import TransactionResp
from common.api.enums.TransTypes import TransTypes
from common.api.core.Api import Api


class SignalApi(QObject):
    api_started: pyqtSignal = pyqtSignal()
    api_stopped: pyqtSignal = pyqtSignal()
    send_transaction: pyqtSignal = pyqtSignal(Transaction)
    incoming_transaction: pyqtSignal = pyqtSignal(Transaction)
    terminal_response: pyqtSignal = pyqtSignal(ApiRequest)
    change_api_mode: pyqtSignal = pyqtSignal(ApiModes)
    error_type = str | None | Exception
    open_connection: pyqtSignal = pyqtSignal(str, str)

    def __init__(self, config: Config, terminal: Terminal):
        super().__init__()
        self.api_tasks = {}
        self.lock = Lock()
        self.config = config
        self.terminal = terminal
        self.api = Api(self)
        self.terminal.logger.add_api_handler()
        self.requests: dict[str, ApiRequest] = dict()
        self.parser = Parser(self.config)

        # Connect all

        api = self.api

        connection_map = {
            api.api_request: self.process_api_call,
            api.api_started: self.api_started,
            api.api_stopped: self.api_stopped,
            self.terminal.trans_queue.incoming_transaction: self.process_incoming_transaction,
            self.terminal.trans_queue.socket_error: self.process_sending_error,
            self.terminal_response: lambda resp: logger.info(f'API request "{resp.request_id}" processing finished')
        }

        for signal, slot in connection_map.items():
            signal.connect(slot)

    def start(self):
        self.api.start()

    def stop(self):
        self.api.stop()

    def restart(self):
        self.api.restart()

    def process_api_call(self, request: ApiRequest):
        logger.info(
            f'API got incoming request. Request type: "{request.request_type}"; Request ID: "{request.request_id}"'
        )

        with self.lock:
            self.api_tasks[request.request_id] = request

        processor_map = {
            ApiRequestType.OUTGOING_TRANSACTION: self.process_api_trans_request,
            ApiRequestType.RECONNECT: self.process_api_reconnect,
            ApiRequestType.DISCONNECT: self.process_api_disconnect,
            ApiRequestType.CONNECT: self.process_api_connect,
            ApiRequestType.UPDATE_SPEC: self.process_api_update_spec,
            ApiRequestType.REVERSE_TRANSACTION: self.process_api_reverse_transaction,
            ApiRequestType.UPDATE_CONFIG: self.process_api_update_config,
        }

        if not (processor := processor_map.get(request.request_type)):
            raise TerminalApiError(
                http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=f"Cannot process API call, unknown request type: {request.request_type}"
            )

        processor(request)

        if request.request_type not in (ApiRequestType.OUTGOING_TRANSACTION, ApiRequestType.REVERSE_TRANSACTION):
            return

        if self.config.api.wait_remote_host_response:
            return

        request.http_status = HTTPStatus.OK
        request.response_data = TransactionResp()
        request.response_data.status = request.response_data.status % request.request_id
        self.api.process_backend_response(request)

    def get_predefined_transaction(self, trans_type: TransTypes) -> Transaction:
        match trans_type:
            case TransTypes.ECHO_TEST:
                trans_file = ApiFiles.ECHO_TEST

            case TransTypes.EPOS_PURCHASE:
                trans_file = ApiFiles.PURCHASE

            case TransTypes.KEEP_ALIVE:
                trans_file = ApiFiles.KEEP_ALIVE

            case TransTypes.PAYOUT:
                trans_file = ApiFiles.PAYOUT

            case _:
                raise ValueError(f"Unknown predefined transaction type: {trans_type}")

        try:
            return self.parser.parse_file(trans_file)
        except Exception as parsing_error:
            raise RuntimeError(f"Cannot parse predefined transactions file {trans_file}. {parsing_error}")

    def is_api_transaction(self, transaction: Transaction) -> bool:
        with self.lock:
            api_tasks = deepcopy(self.api_tasks)

        for request in api_tasks.values():
            if type(request) not in (ApiTransactionRequest, ReversalRequest):
                continue

            if request.transaction.trans_id == transaction.trans_id:
                return True

        return False

    def process_sending_error(self, transaction: Transaction):
        if transaction is None:
            return

        if not self.is_api_transaction(transaction):
            return

        resp = self.prepare_api_transaction_resp(transaction)

        self.send_response(resp, resp.http_status, error=self.terminal.connector.errorString())

    def process_incoming_transaction(self, transaction: Transaction) -> None:
        if transaction is None:
            return

        if not (resp := self.prepare_api_transaction_resp(transaction)):
            return

        self.send_response(resp, resp.http_status, message=resp.response_data)

    def prepare_api_transaction_resp(self, transaction: Transaction) -> ApiTransactionRequest:
        with self.lock:
            tasks = deepcopy(self.api_tasks)

        for request_id, request in tasks.items():
            if request.request_type not in (ApiRequestType.OUTGOING_TRANSACTION, ApiRequestType.REVERSE_TRANSACTION):
                continue

            if request.transaction is None:
                continue

            conditions = (
                request.transaction.trans_id == transaction.trans_id,
                request.transaction.trans_id == transaction.match_id,
            )

            if not any(conditions):
                continue

            transaction_error = transaction.error

            if transaction.match_id == request.transaction.trans_id and transaction.matched:
                request.response_data = self.clean_transaction(transaction)
                request.http_status = HTTPStatus.OK

            else:
                request.error = transaction_error
                request.http_status = HTTPStatus.BAD_GATEWAY

            return request

    def validate_transaction(self, transaction: Transaction):

        try:
            self.terminal.trans_validator.validate_transaction(transaction)

        except (DataValidationError, DataValidationWarning) as validation_error:
            return TransValidationErrors(validation_errors=str(validation_error).split("\n"))

        return TransValidationErrors()

    def get_connection(self) -> Connection:
        return Connection(
            status=self.terminal.get_connection_status(),
            host=self.terminal.connector.get_connected_host(),
            port=self.terminal.connector.get_connected_port()
        )

    def get_spec(self) -> EpaySpecModel:
        return self.terminal.spec.spec

    def get_transactions(self) -> dict[str, Transaction]:
        transactions: dict[str, Transaction] = dict()

        for transaction in self.terminal.trans_queue.queue:
            transactions[transaction.trans_id] = self.clean_transaction(transaction)

        return transactions

    def get_transaction(self, trans_id: str) -> Transaction:
        if not (transaction := self.terminal.trans_queue.get_transaction(trans_id)):
            raise LookupError("Transaction was not found")

        return self.clean_transaction(transaction)

    def get_config(self) -> Config:
        return self.config

    def convert_to(self, transaction: Transaction, to_format: DataConversionFormats):
        transaction: Transaction = FieldsGenerator().set_generated_fields(transaction)

        match to_format:

            case DataConversionFormats.DUMP:
                return self.terminal.parser.create_sv_dump(transaction)

            case DataConversionFormats.INI:
                return self.terminal.parser.transaction_to_ini_string(transaction)

            case DataConversionFormats.JSON:
                return self.clean_transaction(transaction)

            case _:
                raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, detail=f"Unknown data format {to_format}")

    def process_api_update_config(self, request: ConfigAction):
        logger.info("")
        logger.info("Processing incoming request to update the config")
        logger.info("")

        self.terminal.log_printer.print_config(request.config)

        try:
            old_config = self.config.model_copy(deep=True)

            with open(TermFilesPath.CONFIG, "w") as file:
                file.write(request.config.model_dump_json(indent=4))

            self.terminal.read_config()
            self.terminal.process_config_change(old_config)
            self.config = self.terminal.config

            config = self.config

        except Exception as config_update_error:
            self.send_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, error=config_update_error)
            return

        self.api.config = self.config

        self.send_response(request, HTTPStatus.OK, message=config)

    def process_api_reverse_transaction(self, request: ApiRequest):
        original_transaction: Transaction

        if not (original_transaction := self.terminal.trans_queue.get_transaction(trans_id=request.original_trans_id)):
            self.send_response(request, HTTPStatus.NOT_FOUND, error="No original transaction found")
            return

        try:
            request.transaction = self.terminal.build_reversal(original_transaction)

        except LookupError as reversal_building_error:
            self.send_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, error=reversal_building_error)
            return

        self.send_transaction.emit(request.transaction)

    def process_api_update_spec(self, request: ApiRequest):
        SpecFilesRotator(self.config).backup_spec()
        self.terminal.spec.reload_spec(request.spec, commit=True)
        self.send_response(request, HTTPStatus.OK, message=self.terminal.spec.spec)

    def process_api_connect(self, request: ApiRequest):
        if self.terminal.connector.connection_in_progress():
            self.send_response(request, HTTPStatus.SERVICE_UNAVAILABLE, error="Connection is in progress")
            return

        if self.terminal.connector.is_connected():
            connection: Connection = self.get_connection()

            self.send_response(
                request, HTTPStatus.NOT_ACCEPTABLE,
                error=f"The host is already connected to {connection.host}:{connection.port}. Close connection first"
            )

            return

        if not request.connection.host:
            request.connection.host = self.config.host.host

        if not request.connection.port:
            request.connection.port = self.config.host.port

        self.open_connection.emit(request.connection.host, str(request.connection.port))

        connection_started = datetime.now()

        while not self.terminal.connector.is_connected():
            self.terminal.pyqt_application.processEvents()

            if (datetime.now() - connection_started).seconds > 30:
                self.send_response(request, HTTPStatus.GATEWAY_TIMEOUT, error="Connection timeout")
                return

            if self.terminal.connector.error():
                if self.terminal.connector.error() is not QTcpSocket.SocketError.UnknownSocketError:
                    break

            sleep(0.01)

        if not self.terminal.connector.is_connected():
            self.send_response(request, HTTPStatus.BAD_GATEWAY, error=self.terminal.connector.errorString())
            return

        self.send_response(request, HTTPStatus.OK, message=self.get_connection())

    def process_api_trans_request(self, request: ApiTransactionRequest):
        try:
            self.terminal.trans_validator.validate_transaction(request.transaction)

        except DataValidationWarning as validation_warning:
            logger.warning(validation_warning)

        except DataValidationError as validation_error:
            logger.error(validation_error)
            self.send_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, error=f"Validation error: {validation_error}")
            return

        if self.terminal.connector.connection_in_progress():
            self.send_response(
                request,
                HTTPStatus.SERVICE_UNAVAILABLE,
                error="Cannot send the transaction while the host connection is in progress"
            )

        with self.lock:
            self.api_tasks[request.request_id] = request

        self.send_transaction.emit(request.transaction)

    def send_response(self, request: ApiRequest, status: HTTPStatus, message: Any = None, error: error_type = None):
        if isinstance(request, TransactionResp):
            self.terminal_response.emit(request)
            return

        request.http_status = status
        request.response_data = message

        if error is not None:
            request.error = str(error)

        with suppress(KeyError), self.lock:
            self.api_tasks.pop(request.request_id)

        self.terminal_response.emit(request)

    def process_api_reconnect(self, request: ApiRequest):
        logger.info("[Re]connecting...")

        if self.terminal.connector.connection_in_progress():
            self.send_response(request, HTTPStatus.NOT_ACCEPTABLE, error="Connection is in progress")
            return

        for _ in range(0, 3):
            if self.terminal.connector.is_connected():
                self.process_api_disconnect(request, send_resp=False)

            if not self.terminal.connector.is_connected():
                self.process_api_connect(request)
                return

        self.send_response(
            request, HTTPStatus.BAD_GATEWAY, message=f"Cannot reconnect: {self.terminal.connector.error()}"
        )

    def process_api_disconnect(self, request: ApiRequest, send_resp: bool = True):
        if self.terminal.connector.connection_in_progress():
            self.send_response(request, HTTPStatus.NOT_ACCEPTABLE, error="Connection is in progress")
            return

        if not self.terminal.connector.is_connected():
            self.send_response(request, HTTPStatus.NOT_ACCEPTABLE, error="The host is already disconnected")
            return

        self.terminal.connector.disconnect_sv()

        if send_resp:
            self.send_response(request, HTTPStatus.OK, message=self.get_connection())

    def process_change_api_mode(self, state: ApiModes) -> None:
        match state:

            case ApiModes.START:
                self.start()

            case ApiModes.STOP:
                self.stop()

            case ApiModes.RESTART:
                self.restart()

            case _:
                logger.error(f"Cannot run API, unknown command: {state}")
                return

    @staticmethod
    def get_signal_info():
        elements = (
            f"<pre>{TextConstants.HELLO_MESSAGE}</pre>",
            "️Use only on test environment",
            f"Version {ReleaseDefinition.VERSION}",
            f"Released in {ReleaseDefinition.RELEASE}",
            f"See user reference guide <a href=\"{ApiUrl.DOCUMENT}\">here</a>",
            f"Developed by {ReleaseDefinition.AUTHOR}",
            f"Contact author {ReleaseDefinition.CONTACT}"
        )

        message = "\n\n  ".join(elements)

        message = f"""<head>
                        <title>Signal {ReleaseDefinition.VERSION} | About </title>
                        <link rel="icon" type="image/png" href="static/{GuiFiles.MAIN_LOGO}"> 
                        <link rel="stylesheet" href="static/octicons/octicons.css" />
                      </head>
                        <body style="font-size:20px; background-color: #012e4f; color: #ffffff; padding: 10px; 
                        border-radius: 6px;">
                         <pre>
                           <code>{message}</code>
                         </pre>
                       </body>"""

        return message

    def clean_transaction(self, transaction: Transaction) -> Transaction:
        transaction: Transaction = transaction.model_copy(deep=True)

        with suppress(Exception):
            transaction = self.terminal.parser.hide_secret_fields(transaction) if self.config.api.hide_secrets else transaction

        with suppress(Exception):
            transaction = self.terminal.parser.parse_complex_fields(transaction, split=self.config.api.parse_subfields)

        del (
            transaction.json_fields,
            transaction.matched,
            transaction.success,
            transaction.error,
            transaction.sending_time,
            transaction.is_request,
            transaction.is_reversal,
            transaction.is_keep_alive,
            transaction.generate_fields,
            transaction.max_amount,
        )

        return transaction
