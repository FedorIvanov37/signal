from loguru import logger
from typing import Any
from fastapi import HTTPException
from contextlib import suppress
from http import HTTPStatus
from PyQt6.QtCore import pyqtSignal
from common.api.data_models.TransValidationErrors import TransValidationErrors
from common.gui.enums.GuiFilesPath import GuiFiles
from common.api.enums.ApiUrl import ApiUrl
from common.lib.exceptions.exceptions import DataValidationError, DataValidationWarning
from common.lib.enums.TextConstants import TextConstants, ReleaseDefinition
from common.lib.core.Terminal import Terminal
from common.lib.data_models.Config import Config
from common.api.data_models.Connection import Connection
from common.api.core.ApiInterface import ApiInterface
from common.api.enums.ApiModes import ApiModes
from common.api.data_models.ApiRequests import ApiTransactionRequest, ApiRequest
from common.lib.core.SpecFilesRotator import SpecFilesRotator
from common.lib.data_models.Transaction import Transaction
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel
from common.api.enums.DataCoversionFormats import DataConversionFormats
from common.lib.core.FieldsGenerator import FieldsGenerator


class SignalApi(Terminal):
    start_api: pyqtSignal = pyqtSignal()
    stop_api: pyqtSignal = pyqtSignal()
    restart_api: pyqtSignal = pyqtSignal()
    finish_api: pyqtSignal = pyqtSignal()
    terminal_response: pyqtSignal = pyqtSignal(ApiRequest)
    error_type = str | None | Exception

    def __init__(self, config: Config, connector=None):
        super().__init__(config=config, connector=connector)

        self.config = config
        self.api = ApiInterface(self, self.config)
        self.logger.add_api_handler()
        self.requests: dict[str, ApiRequest] = dict()

        # Connect all

        api = self.api

        connection_map = {
            api.api_trans_request: self.process_api_request,
            api.api_reconnect_request: self.process_api_reconnect,
            api.api_disconnect_request: self.process_api_disconnect,
            api.api_connect_request: self.process_api_connect,
            api.api_update_spec: self.process_api_update_spec,
            api.api_reverse_transaction: self.process_api_reverse_transaction,
            api.api_update_config: self.process_api_update_config,
        }

        for signal, slot in connection_map.items():
            signal.connect(slot)

    def validate_transaction(self, transaction: Transaction):

        try:
            self.trans_validator.validate_transaction(transaction)

        except (DataValidationError, DataValidationWarning) as validation_error:
            return TransValidationErrors(validation_errors=str(validation_error).split("\n"))

        return TransValidationErrors()

    def get_connection(self) -> Connection:
        return Connection(
            status=self.get_connection_status(),
            host=self.connector.get_connected_host(),
            port=self.connector.get_connected_port()
        )

    def get_spec(self) -> EpaySpecModel:
        return self.spec.spec

    def get_transactions(self) -> dict[str, Transaction]:
        transactions: dict[str, Transaction] = dict()

        for transaction in self.trans_queue.queue:
            transactions[transaction.trans_id] = self.clean_transaction(transaction)

        return transactions

    def get_transaction(self, trans_id: str) -> Transaction:
        if not (transaction := self.trans_queue.get_transaction(trans_id)):
            raise LookupError("Transaction was not found")

        return self.clean_transaction(transaction)

    def get_config(self) -> Config:
        return self.config

    def convert_to(self, transaction: Transaction, to_format: DataConversionFormats):
        transaction: Transaction = FieldsGenerator().set_generated_fields(transaction)

        match to_format:

            case DataConversionFormats.DUMP:
                return self.parser.create_sv_dump(transaction)

            case DataConversionFormats.INI:
                return self.parser.transaction_to_ini_string(transaction)

            case DataConversionFormats.JSON:
                return self.clean_transaction(transaction)

            case _:
                raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, detail=f"Unknown data format {to_format}")

    def process_api_update_config(self, request: ApiRequest):
        try:
            old_config = self.config.model_copy(deep=True)

            with open(TermFilesPath.CONFIG, "w") as file:
                file.write(request.config.model_dump_json(indent=4))

            self.read_config()
            self.process_config_change(old_config)

            config = self.config

        except Exception as config_update_error:
            self.sent_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, error=config_update_error)
            return

        self.api.config = self.config

        self.sent_response(request, HTTPStatus.OK, message=config)

    def process_api_reverse_transaction(self, request: ApiRequest):
        original_transaction: Transaction

        if not (original_transaction := self.trans_queue.get_transaction(trans_id=request.original_trans_id)):
            self.sent_response(request, HTTPStatus.NOT_FOUND, error="No original transaction found")
            return

        try:
            request.transaction = self.build_reversal(original_transaction)

        except LookupError as reversal_building_error:
            self.sent_response(request, HTTPStatus.UNPROCESSABLE_ENTITY, error=reversal_building_error)
            return

        self.send(request.transaction)

    def process_api_update_spec(self, request: ApiRequest):
        SpecFilesRotator().backup_spec()
        self.spec.reload_spec(request.spec, commit=True)
        self.sent_response(request, HTTPStatus.OK, message=self.spec.spec)

    def process_api_connect(self, request: ApiRequest):
        if self.connector.connection_in_progress():
            self.sent_response(request, HTTPStatus.NOT_ACCEPTABLE, error="connection is in progress")
            return

        if self.connector.is_connected():
            connection: Connection = self.get_connection()

            self.sent_response(
                request, HTTPStatus.NOT_ACCEPTABLE,
                error=f"The host is already connected to {connection.host}:{connection.port}. Close connection first"
            )

            return

        if not request.connection.host:
            request.connection.host = self.config.host.host

        if not request.connection.port:
            request.connection.port = self.config.host.port

        if error := self.connector.connect_sv(host=request.connection.host, port=request.connection.port):
            self.sent_response(request, HTTPStatus.BAD_GATEWAY, error=error)
            return

        self.sent_response(request, HTTPStatus.OK, message=self.get_connection())

    def process_api_request(self, request: ApiTransactionRequest):
        self.requests[request.request_id] = request
        self.send(request.transaction)

    def sent_response(self, request: ApiRequest, status: HTTPStatus, message: Any = None, error: error_type = None):
        request.http_status = status
        request.response_data = message

        if error is not None:
            request.error = str(error)

        self.terminal_response.emit(request)

    def process_api_reconnect(self, request: ApiRequest):
        if self.connector.connection_in_progress():
            self.sent_response(request, HTTPStatus.NOT_ACCEPTABLE, error="connection is in progress")
            return

        if not self.connector.is_connected():
            if error := self.connector.connect_sv(host=request.connection.host, port=request.connection.port):
                self.sent_response(request, HTTPStatus.BAD_GATEWAY, error=error)
                return

            self.sent_response(request, HTTPStatus.OK, message=self.get_connection())
            return

        if self.connector.is_connected():
            self.connector.disconnect_sv()

        if not self.connector.is_connected():
            if error := self.connector.connect_sv(host=request.connection.host, port=request.connection.port):
                self.sent_response(request, HTTPStatus.BAD_GATEWAY, error=error)

        self.sent_response(request, HTTPStatus.OK, message=self.get_connection())

    def process_api_disconnect(self, request: ApiRequest):
        if self.connector.connection_in_progress():
            self.sent_response(request, HTTPStatus.NOT_ACCEPTABLE, error="connection is in progress")
            return

        if not self.connector.is_connected():
            self.sent_response(request, HTTPStatus.NOT_ACCEPTABLE, error="The host is already disconnected")
            return

        self.connector.disconnect_sv()

        self.sent_response(request, HTTPStatus.OK, message=self.get_connection())

    def process_change_api_mode(self, state: ApiModes) -> None:
        signals_map = {
            ApiModes.START: self.start_api,
            ApiModes.STOP: self.stop_api,
            ApiModes.RESTART: self.restart_api,
        }

        if not (signal := signals_map.get(state)):
            logger.error(f"Cannot run API, unknown command: {state}")
            return

        signal.emit()

    @staticmethod
    def get_signal_info():
        elements = (
            TextConstants.HELLO_MESSAGE,
            f"<a href=\"{ApiUrl.DOCUMENT}\">User Reference Guide</a>",
            "Use only on test environment",
            f"Version {ReleaseDefinition.VERSION}",
            f"Released in {ReleaseDefinition.RELEASE}",
            f"Developed by {ReleaseDefinition.AUTHOR}",
            f"Contact {ReleaseDefinition.CONTACT}"
        )

        message = "\n\n  ".join(elements)

        message = f"""<head>
                        <title>Signal {ReleaseDefinition.VERSION} | About </title>
                        <link rel="icon" type="image/png" href="/static/{GuiFiles.MAIN_LOGO}">
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
            transaction = self.parser.hide_secret_fields(transaction) if self.config.api.hide_secrets else transaction

        with suppress(Exception):
            transaction = self.parser.parse_complex_fields(transaction, split=self.config.api.parse_subfields)

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
