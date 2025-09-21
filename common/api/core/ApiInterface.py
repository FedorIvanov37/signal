from contextlib import suppress
from PyQt6.QtCore import QObject, pyqtSignal
from common.lib.enums.TermFilesPath import TermFilesPath
from common.api.data_models.ApiRequests import Transaction, Connection, ApiRequest
from common.api.enums.ApiRequestType import ApiRequestType
from common.lib.core.SpecFilesRotator import SpecFilesRotator
from common.lib.data_models.Config import Config
from common.gui.enums.ApiMode import ApiModes


class ApiInterface(QObject):
    api_tasks = {}
    api_started: pyqtSignal = pyqtSignal(ApiModes)
    api_stopped: pyqtSignal = pyqtSignal(ApiModes)
    api_transaction_request: pyqtSignal = pyqtSignal(ApiRequest)

    def __init__(self, config: Config = None, terminal=None, api_server=None):
        super().__init__()

        if api_server is not None:
            self.api_server = api_server

        if terminal is not None:
            self.terminal = terminal

        if api_server is not None:
            self.config = config

        self.api_transaction_request.connect(self.process_api_call)

    def prepare_api_transaction_resp(self, transaction: Transaction):
        for request_id, request in self.api_tasks.items():
            conditions = (
                request.transaction.trans_id == transaction.trans_id,
                request.transaction.trans_id == transaction.match_id
            )

            if not any(conditions):
                continue

            request.transaction = transaction

            self.delivery_api_response(request)

            break

    def delivery_api_response(self, response: ApiRequest):
        if not self.api_server.api_started():
            return

        with suppress(KeyError):
            self.api_tasks.pop(response.request_id)

        self.api_server.process_signal_response(response)

    def process_api_call(self, request: ApiRequest):
        self.api_tasks[request.request_id] = request

        match request.request_type:
            case ApiRequestType.GET_CONNECTION:
                request.connection = self.terminal.get_connection()
                self.delivery_api_response(request)

            case ApiRequestType.RECONNECT:
                if self.terminal.connector.connection_in_progress():
                    request.error = "connection is in progress"
                    self.delivery_api_response(request)
                    return

                if not self.terminal.connector.is_connected():
                    try:

                        if error := self.terminal.connector.connect_sv(host=request.connection.host, port=request.connection.port):
                            raise ConnectionError(error.name)

                    except Exception as connection_error:
                        request.error = connection_error
                        self.delivery_api_response(request)
                        return

                    request.connection = self.terminal.get_connection()
                    self.delivery_api_response(request)
                    return

                if self.terminal.connector.is_connected():
                    try:
                        self.terminal.connector.disconnect_sv()

                    except Exception as disconnection_error:
                        request.error = disconnection_error
                        self.delivery_api_response(request)
                        return

                if not self.terminal.connector.is_connected():
                    try:

                        if error := self.terminal.connector.connect_sv(host=request.connection.host, port=request.connection.port):
                            raise ConnectionError(error.name)

                    except Exception as connection_error:
                        request.error = connection_error
                        self.delivery_api_response(request)
                        return

                request.connection = self.terminal.get_connection()
                self.delivery_api_response(request)

            case ApiRequestType.DISCONNECT:
                if self.terminal.connector.connection_in_progress():
                    request.error = "connection is in progress"
                    self.delivery_api_response(request)
                    return

                if not self.terminal.connector.is_connected():
                    request.connection = self.terminal.get_connection()
                    request.error = "The host is already disconnected"
                    self.delivery_api_response(request)
                    return

                try:
                    self.terminal.connector.disconnect_sv()
                    request.connection = self.terminal.get_connection()

                except Exception as disconnection_error:
                    request.error = disconnection_error

                self.delivery_api_response(request)

            case ApiRequestType.CONNECT:
                if self.terminal.connector.connection_in_progress():
                    request.error = "connection is in progress"
                    self.delivery_api_response(request)
                    return

                if self.terminal.connector.is_connected():
                    connection: Connection = self.terminal.get_connection()
                    request.error = f"The host is connected already to {connection.host}:{connection.port}. Close connection first"
                    self.delivery_api_response(request)

                if not request.connection.host:
                    request.connection.host = self.config.host.host

                if not request.connection.port:
                    request.connection.port = self.config.host.port

                try:
                    if error := self.terminal.connector.connect_sv(host=request.connection.host, port=request.connection.port):
                        raise ConnectionError(error.name)

                except Exception as connection_error:
                    request.error = connection_error
                    self.delivery_api_response(request)
                    return

                request.connection = self.terminal.get_connection()
                self.delivery_api_response(request)

            case ApiRequestType.UPDATE_SPEC:

                try:
                    SpecFilesRotator().backup_spec()
                    self.terminal.spec.reload_spec(request.spec, commit=True)

                except Exception as spec_update_error:
                    request.error = spec_update_error

                request.spec = self.terminal.spec.spec

                self.delivery_api_response(request)

            case ApiRequestType.GET_SPEC:
                request.spec = self.terminal.spec.spec
                self.delivery_api_response(request)

            case ApiRequestType.GET_TRANSACTIONS:
                for transaction in self.terminal.trans_queue.queue:
                    request.transactions[transaction.trans_id] = transaction

                self.delivery_api_response(request)

            case ApiRequestType.OUTGOING_TRANSACTION:
                self.terminal.send(request.transaction)

            case ApiRequestType.REVERSE_TRANSACTION:
                original_transaction: Transaction

                if not (original_transaction := self.terminal.get_transaction(trans_id=request.original_trans_id)):
                    request.error = "No original transaction found"
                    self.delivery_api_response(request)
                    return

                request.transaction = self.terminal.build_reversal(original_transaction)

                try:
                    self.terminal.send(request.transaction)
                except Exception as reversal_generate_error:
                    request.error = str(reversal_generate_error)
                    self.delivery_api_response(request)

            case ApiRequestType.GET_TRANSACTION:
                if not (transaction := self.terminal.trans_queue.get_transaction(request.trans_id)):
                    request.error = "Transaction was not found"
                    self.delivery_api_response(request)
                    return

                request.transaction = transaction
                self.delivery_api_response(request)

            case ApiRequestType.GET_CONFIG:
                request.config = self.config
                self.delivery_api_response(request)

            case ApiRequestType.UPDATE_CONFIG:
                try:
                    old_config = self.config.model_copy(deep=True)

                    with open(TermFilesPath.CONFIG, "w") as file:
                        file.write(request.config.model_dump_json(indent=4))

                    self.terminal.read_config()

                    self.terminal.process_config_change(old_config)

                    request.config = self.config

                except Exception as config_update_error:
                    request.error = str(config_update_error)

                self.delivery_api_response(request)
