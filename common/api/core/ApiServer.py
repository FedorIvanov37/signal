import threading, asyncio, uvicorn
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from http import HTTPStatus
from PyQt6.QtCore import QObject
from common.lib.data_models.Config import Config
from common.gui.enums.ApiMode import ApiModes
from common.lib.data_models.Transaction import Transaction
from loguru import logger
from common.api.data_models.ApiRequests import ApiRequest, ApiTransactionRequest, ConfigAction, ReversalRequest, GetTransactionRequest, GetTransactionsRequest, SpecAction, ConnectionAction
from common.api.data_models.Connection import Connection
from common.api.enums.ApiRequestType import ApiRequestType
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel
from common.api.core.ApiInterface import ApiInterface
from common.api.exceptions.api_exceptions import (
    TransactionSendingError,
)


class ApiServer(QObject):
    _interface: ApiInterface = None

    @property
    def interface(self):
        return self._interface

    @interface.setter
    def interface(self, interface):
        self._interface = interface

    def __init__(self, config: Config):
        super().__init__()

        self.config = config
        self._thread = None
        self._server = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None

        self.app = self._build_app()
        self.pending_jobs: dict[str, asyncio.Future] = {}

    def api_started(self):
        return self._thread and self._thread.is_alive()

    def restart(self):
        if not self.api_started():
            self.start()
            return

        if self.api_started():
            self.stop()
            self.start()

    def start(self):
        if self.api_started():
            logger.warning("Unable to start API mode, because it is already started")
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout=5.0):
        if not self.api_started():
            logger.warning("Unable to stop API mode, because it is not started")
            return

        if self._server and not self._server.should_exit:
            self._server.should_exit = True

        self._thread.join(timeout=timeout)

        if self._thread.is_alive() and self._server:
            self._server.force_exit = True
            self._thread.join(timeout=timeout)

        self._thread = self._server = self._loop = self._queue = None

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._queue = asyncio.Queue()

        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.config.api.port, log_config=None, access_log=True)

        self._server: uvicorn.Server = uvicorn.Server(config)

        self.interface.api_started.emit(ApiModes.START)

        try:
            loop.run_until_complete(self._server.serve())

        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            self.interface.api_stopped.emit(ApiModes.STOP)

    async def send_signal_request(self, request: ApiRequest):
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self.pending_jobs[request.request_id] = future
        self.interface.api_transaction_request.emit(request)

        try:
            return await asyncio.wait_for(future, timeout=self.config.api.waiting_timeout_seconds)

        except asyncio.TimeoutError:
            raise HTTPException(HTTPStatus.GATEWAY_TIMEOUT, "request processing timeout")

        except TransactionSendingError as sending_error:
            raise HTTPException(HTTPStatus.BAD_GATEWAY, str(sending_error))

        except LookupError as lost_data_error:
            raise HTTPException(HTTPStatus.NOT_FOUND, str(lost_data_error))

        except Exception as sending_error:
            raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, str(sending_error))

        finally:
            self.pending_jobs.pop(request.request_id)

    def process_signal_response(self, request: ApiRequest):
        if not self._loop:
            return

        def _finish():
            future = self.pending_jobs.get(request.request_id)

            if not future or future.done():
                return

            match request.request_type:
                case ApiRequestType.RECONNECT:
                    if request.error:
                        future.set_exception(ValueError(f"Reconnection error: {request.error}"))
                        return

                    future.set_result(request.connection)

                case ApiRequestType.DISCONNECT:
                    if request.error:
                        future.set_exception(ValueError(f"Disconnection error: {request.error}"))
                        return

                    future.set_result(request.connection)

                case ApiRequestType.CONNECT:
                    if request.error:
                        future.set_exception(ValueError(f"Connection error: {request.error}"))
                        return

                    future.set_result(request.connection)

                case ApiRequestType.GET_CONNECTION:
                    future.set_result(request.connection)

                case ApiRequestType.UPDATE_SPEC:
                    if request.error:
                        future.set_exception(ValueError(f"Specification setting error: {request.error}"))
                        return

                    future.set_result(request.spec)

                case ApiRequestType.GET_SPEC:
                    if request.error:
                        future.set_exception(ValueError(f"Specification getting error: {request.error}"))
                        return

                    future.set_result(request.spec)

                case ApiRequestType.GET_TRANSACTIONS:
                    future.set_result(request.transactions)

                case ApiRequestType.GET_TRANSACTION:
                    if request.error:
                        future.set_exception(LookupError(f"Cannot process request: {request.error}"))
                        return

                    if not request.transaction:
                        future.set_exception(LookupError(f"Cannot process request: {request.error}"))

                    future.set_result(request.transaction)

                case ApiRequestType.OUTGOING_TRANSACTION | ApiRequestType.REVERSE_TRANSACTION:
                    if request.error:
                        future.set_exception(TransactionSendingError(f"Cannot process request: {request.error}"))
                        return

                    if request.transaction.error:
                        future.set_exception(TransactionSendingError(f"Cannot process request: {request.transaction.error}"))
                        return

                    if not request.transaction.error:
                        future.set_result(request.transaction)

                case ApiRequestType.GET_CONFIG:
                    future.set_result(request.config)

                case ApiRequestType.UPDATE_CONFIG:
                    if request.error:
                        future.set_exception(HTTPException(HTTPStatus.BAD_REQUEST, request.error))

                    if not request.error:
                        future.set_result(request.config)

        self._loop.call_soon_threadsafe(_finish)

    def _build_app(self) -> FastAPI:
        api = FastAPI()

        @api.put("/api/connection/restart", response_model=Connection)
        async def reconnect(connection: Connection | None = None):
            if connection is None:
                connection = Connection()

            return await self.send_signal_request(ConnectionAction(request_type=ApiRequestType.RECONNECT, connection=connection))

        @api.put("/api/connection/close", response_model=Connection)
        async def disconnect():
            return await self.send_signal_request(ConnectionAction(request_type=ApiRequestType.DISCONNECT))

        @api.put("/api/connection/open", response_model=Connection)
        async def connect(connection: Connection | None = None):
            if connection is None:
                connection = Connection()

            return await self.send_signal_request(ConnectionAction(request_type=ApiRequestType.CONNECT, connection=connection))

        @api.get("/api/connection", response_model=Connection)
        async def get_connection():
            return await self.send_signal_request(ConnectionAction())

        @api.put("/api/specification", response_model=EpaySpecModel)
        async def update_spec(spec: EpaySpecModel):
            return await self.send_signal_request(SpecAction(request_type=ApiRequestType.UPDATE_SPEC, spec=spec))

        @api.get("/api/specification", response_model=EpaySpecModel)
        async def get_specification():
            return await self.send_signal_request(SpecAction())

        @api.post("/api/transactions", response_model=Transaction)
        async def create_transaction(request: Transaction):
            logger.info("API got transaction sending request. POST /api/transactions")

            return await self.send_signal_request(ApiTransactionRequest(transaction=request))

        @api.get("/api/transactions", response_model=dict[str, Transaction])
        async def get_transactions():
            return await self.send_signal_request(GetTransactionsRequest())

        @api.get("/api/transactions/{trans_id}", response_model=Transaction)
        async def get_transaction(trans_id: str):
            return await self.send_signal_request(GetTransactionRequest(trans_id=trans_id))

        @api.post("/api/transactions/{trans_id}/reverse", response_model=Transaction)
        async def reverse_transaction(trans_id: str):
            return await self.send_signal_request(ReversalRequest(original_trans_id=trans_id))

        @api.get("/api/config", response_model=Config)
        async def get_config():
            return await self.send_signal_request(ConfigAction())

        @api.put("/api/config", response_model=Config)
        async def update_config(config: Config):
            return await self.send_signal_request(ConfigAction(request_type=ApiRequestType.UPDATE_CONFIG, config=config))

        return api
