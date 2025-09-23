from http import HTTPStatus
from contextlib import suppress
from PyQt6.QtCore import QObject, pyqtSignal
from common.lib.data_models.Config import Config
from common.api.enums.ApiRequestType import ApiRequestType
from common.gui.enums.ApiMode import ApiModes
from common.api.core.Api import Api
from common.api.data_models.ApiRequests import ApiRequest
from common.lib.data_models.Transaction import Transaction
from common.api.exceptions.TerminalApiError import TerminalApiError
from common.api.data_models.TransactionResp import TransactionResp


"""
This is an API interface, a bridge between FastAPI and PyQt Terminal application e.g. SignalGUI or SignalCLI

Connected to FastAPI from one side and PyQt Terminal application from the other, supplies safe translation of API calls
to PyQt event loop
 
WARNING: data gathering tasks can call the PyQt application directly, for any data modification PyQt signals/slots
functionality is strongly required. If your call will change any PyQt object no way to call any method directly. Follow
this convenient to keep thread safety

More about PyQt signal/slot concept here: https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html

The ApiInterface should not store any data-objects directly, using the PyQt application access to ge data. E.g. use
self.terminal.config instead of self.config

"""


class ApiInterface(QObject):

    @property
    def get_connection(self):
        return self.terminal.get_connection

    @property
    def get_spec(self):
        return self.terminal.get_spec

    @property
    def get_transactions(self):
        return self.terminal.get_transactions

    @property
    def get_transaction(self):
        return self.terminal.get_transaction

    @property
    def get_config(self):
        return self.terminal.get_config

    @property
    def convert_to(self):
        return self.terminal.convert_to

    @property
    def clean_transaction(self):
        return self.terminal.clean_transaction

    api_tasks = {}
    api_started: pyqtSignal = pyqtSignal(ApiModes)
    api_stopped: pyqtSignal = pyqtSignal(ApiModes)
    api_trans_request: pyqtSignal = pyqtSignal(ApiRequest)
    api_reconnect_request: pyqtSignal = pyqtSignal(ApiRequest)
    api_disconnect_request: pyqtSignal = pyqtSignal(ApiRequest)
    api_connect_request: pyqtSignal = pyqtSignal(ApiRequest)
    api_update_spec: pyqtSignal = pyqtSignal(ApiRequest)
    api_reverse_transaction: pyqtSignal = pyqtSignal(ApiRequest)
    api_update_config: pyqtSignal = pyqtSignal(ApiRequest)

    def __init__(self, terminal, config: Config):
        super().__init__()

        self.config = config
        self.terminal = terminal
        self.api = Api(self, self.config)
        self.terminal.start_api.connect(self.start_api)
        self.terminal.stop_api.connect(self.stop_api)
        self.terminal.trans_queue.incoming_transaction.connect(self.prepare_api_transaction_resp)
        self.terminal.trans_queue.socket_error.connect(self.prepare_api_transaction_resp)
        self.terminal.terminal_response.connect(self.api.process_backend_response)
        self.api.api_started.connect(self.api_started)
        self.api.api_stopped.connect(self.api_stopped)
        self.api.api_request.connect(self.process_api_call)

    def start_api(self):
        self.api.start()

    def stop_api(self):
        self.api.stop()

    def prepare_api_transaction_resp(self, transaction: Transaction):
        for request_id, request in self.api_tasks.items():
            conditions = (
                request.transaction.trans_id == transaction.trans_id,
                request.transaction.trans_id == transaction.match_id
            )

            if not any(conditions):
                continue

            transaction: Transaction = self.terminal.clean_transaction(transaction)

            request.response_data = transaction
            request.http_status = HTTPStatus.OK

            self.delivery_api_response(request)

            return

    def process_api_call(self, request: ApiRequest):
        self.api_tasks[request.request_id] = request

        request_signal_map = {
            ApiRequestType.OUTGOING_TRANSACTION: self.api_trans_request,
            ApiRequestType.RECONNECT: self.api_reconnect_request,
            ApiRequestType.DISCONNECT: self.api_disconnect_request,
            ApiRequestType.CONNECT: self.api_connect_request,
            ApiRequestType.UPDATE_SPEC: self.api_update_spec,
            ApiRequestType.REVERSE_TRANSACTION: self.api_reverse_transaction,
            ApiRequestType.UPDATE_CONFIG: self.api_update_config,
        }

        if not (signal := request_signal_map.get(request.request_type, False)):
            raise TerminalApiError(
                http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=f"Cannot process API call, unknown request type: {request.request_type}"
            )

        signal.emit(request)

        if request.request_type not in (ApiRequestType.OUTGOING_TRANSACTION, ApiRequestType.REVERSE_TRANSACTION):
            return

        if not self.terminal.config.api.wait_remote_host_response:
            request.http_status = HTTPStatus.OK
            request.response_data = TransactionResp()
            self.delivery_api_response(request)

    def delivery_api_response(self, response: ApiRequest):
        if not self.api.is_api_started():
            return

        with suppress(KeyError):
            self.api_tasks.pop(response.request_id)

        self.api.process_backend_response(response)
