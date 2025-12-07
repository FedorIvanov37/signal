from loguru import logger
from typing import Union
from os import getcwd
from os.path import normpath
from uuid import uuid4
from http import HTTPStatus
from threading import Thread
from warnings import filterwarnings
from fastapi import FastAPI, APIRouter, Response
from fastapi.staticfiles import StaticFiles
from uvicorn import Config as UvicornConfig, Server as UvicornServer
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse, HTMLResponse
from PyQt6.QtCore import QObject, pyqtSignal
from common.lib.data_models.Config import Config
from common.lib.data_models.Transaction import Transaction
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel
from common.gui.enums.ApiMode import ApiModes
from common.api.data_models.TransValidationErrors import TransValidationErrors
from common.api.data_models.ExceptionContent import ExceptionContent
from common.api.enums.ApiUrl import ApiUrl
from common.api.data_models.Connection import Connection
from common.api.data_models.TransactionResp import TransactionResp
from common.api.enums.ApiRequestType import ApiRequestType
from common.api.exceptions.TerminalApiError import TerminalApiError
from common.api.enums.DataCoversionFormats import DataConversionFormats
from common.gui.enums.GuiFilesPath import GuiFilesPath

from common.api.data_models.ApiRequests import (
    ApiRequest,
    ApiTransactionRequest,
    ConfigAction,
    ReversalRequest,
    SpecAction,
    ConnectionAction,
)

from asyncio import (
    AbstractEventLoop,
    new_event_loop,
    set_event_loop,
    get_running_loop,
    Queue,
    Future,
    wait_for,
)


"""

Signal Application Program Interface (API) 

This is an API for processing transaction requests, configuration, and a toolkit for working with transactions 

The Signal API is bundled with a Postman collection. Call the API using the GET method using the 
mapping {{api}}/api/documentation for more information

The API must be started through the graphical user interface or the command line interface, not directly

Command line run command: signal.exe --console --api-mode

"""


class Api(QObject):

    api_started: pyqtSignal = pyqtSignal(ApiModes)
    api_stopped: pyqtSignal = pyqtSignal(ApiModes)
    api_request: pyqtSignal = pyqtSignal(ApiRequest)

    def __init__(self, backend):
        super().__init__()

        self.backend = backend
        self._thread = None
        self._server = None
        self._loop: AbstractEventLoop | None = None
        self._queue: Queue | None = None
        self.app = self._build_app()
        self.pending_jobs: dict[str, Future] = {}
        filterwarnings("ignore", message=".*Pydantic serializer warnings*", module="pydantic.*")

    def is_api_started(self):
        return self._thread and self._thread.is_alive()

    def restart(self):
        logger.debug("Restarting API")

        if not self.is_api_started():
            self.start()
            return

        if self.is_api_started():
            self.stop()
            self.start()

    def start(self):
        if self.is_api_started():
            logger.warning("Unable to start API mode, because it is already started")
            return

        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout=5.0):
        if not self.is_api_started():
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
        loop = new_event_loop()
        set_event_loop(loop)
        self._loop = loop
        self._queue = Queue()

        config = UvicornConfig(
            self.app, host="0.0.0.0", port=self.backend.config.api.port, log_config=None, access_log=True
        )

        self._server: UvicornServer = UvicornServer(config)

        self.api_started.emit(ApiModes.START)

        try:
            loop.run_until_complete(self._server.serve())

        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            self.api_stopped.emit(ApiModes.STOP)

    async def backend_request(self, request: ApiRequest):  # Use this to create long-time job
        request.request_id = uuid4()
        loop = get_running_loop()
        future: Future = loop.create_future()
        self.pending_jobs[request.request_id] = future
        self.api_request.emit(request)

        try:
            return await wait_for(future, timeout=self.backend.config.api.waiting_timeout_seconds)

        except TimeoutError:
            raise TerminalApiError(http_status=HTTPStatus.GATEWAY_TIMEOUT, detail="request processing timeout")

        except LookupError as lost_transaction:
            raise TerminalApiError(http_status=HTTPStatus.NOT_FOUND, detail=lost_transaction)

        finally:

            self.pending_jobs.pop(request.request_id)

    def process_backend_response(self, request: ApiRequest):
        if not self._loop:
            return

        def _finish():
            future = self.pending_jobs.get(request.request_id)

            if not future or future.done():
                return

            if request.http_status is not HTTPStatus.OK:
                future.set_exception(TerminalApiError(detail=request.error, http_status=request.http_status))
                return

            future.set_result(request.response_data)

        self._loop.call_soon_threadsafe(_finish)

    def _build_app(self) -> FastAPI:

        # The API endpoints builder. Builds HTTP API based on FastAPI

        app = FastAPI(docs_url=None, redoc_url=None)

        app.mount("/static", StaticFiles(directory="common/doc/static"), name="static")

        api = APIRouter(prefix=ApiUrl.API)

        @app.exception_handler(TerminalApiError)
        def terminal_api_errors_handler(request, exception: TerminalApiError):
            return JSONResponse(ExceptionContent(detail=exception.detail).dict(), exception.http_status)

        @app.get(ApiUrl.SIGNAL, response_class=HTMLResponse)
        def get_signal_info():
            return HTMLResponse(self.backend.get_signal_info())

        @app.get(ApiUrl.DOCUMENT, include_in_schema=False)
        def docs():
            return FileResponse("common/doc/signal_user_reference_guide.html", media_type="text/html")

        @api.post(ApiUrl.VALIDATE_TRANSACTION, response_model=TransValidationErrors)
        def validate_transaction(transaction: Transaction):
            return self.backend.validate_transaction(transaction)

        """
        Read-only API endpoints. Read data from PYQt application
        
        A simple way to retrieve data from a PyQt application using the API bridge directly, without involving an async 
        approach. Use for data-read functions only. In case of data modification, signals/slots required
        """

        @api.get(ApiUrl.GET_CONNECTION, response_model=Connection)
        def get_connection():
            return self.backend.get_connection()

        @api.get(ApiUrl.GET_SPECIFICATION, response_model=EpaySpecModel)
        def get_specification():
            return self.backend.get_spec()

        @api.get(ApiUrl.GET_TRANSACTIONS, response_model=dict[str, Transaction])
        def get_transactions():
            return self.backend.get_transactions()

        @api.get(ApiUrl.GET_TRANSACTION, response_model=Transaction)
        def get_transaction(trans_id: str):
            try:
                return self.backend.get_transaction(trans_id)
            except LookupError as transaction_lookup_error:
                raise TerminalApiError(http_status=HTTPStatus.NOT_FOUND, detail=transaction_lookup_error)

        @api.get(ApiUrl.GET_CONFIG, response_model=Config)
        def get_config():
            return self.backend.get_config()

        """
        Read-write API endpoints. Modify the PyQt application thread members
        
        Better, but not required to call asynchronously
        
        WARNING: these endpoints must trigger API bridge functions, which emit PyQt signals. Strongly not recommended 
        to use with the API bridge functions, which call PyQt application directly. The bridge must emit PyQt signal 
        to cover this endpoint. Otherwise, it can lead to unforeseen consequences such as lost data or the spontaneous 
        shutdown of the PyQt application
        """

        @api.post(ApiUrl.CREATE_TRANSACTION, response_model=Union[Transaction, TransactionResp])
        async def create_transaction(request: Transaction):
            return await self.backend_request(ApiTransactionRequest(transaction=request))

        @api.post(ApiUrl.REVERSE_TRANSACTION, response_model=Transaction)
        async def reverse_transaction(trans_id: str):
            return await self.backend_request(ReversalRequest(original_trans_id=trans_id))

        @api.put(ApiUrl.UPDATE_SPECIFICATION, response_model=EpaySpecModel)
        async def update_spec(spec: EpaySpecModel):
            return await self.backend_request(SpecAction(request_type=ApiRequestType.UPDATE_SPEC, spec=spec))

        @api.put(ApiUrl.RECONNECT, response_model=Connection)
        async def reconnect(connection: Connection | None = None):
            if connection is None:
                connection = Connection()

            return await self.backend_request(
                ConnectionAction(request_type=ApiRequestType.RECONNECT, connection=connection)
            )

        @api.put(ApiUrl.DISCONNECT, response_model=Connection)
        async def disconnect():
            return await self.backend_request(ConnectionAction(request_type=ApiRequestType.DISCONNECT))

        @api.put(ApiUrl.CONNECT, response_model=Connection)
        async def connect(connection: Connection | None = None):
            if connection is None:
                connection = Connection()

            return await self.backend_request(
                ConnectionAction(request_type=ApiRequestType.CONNECT, connection=connection)
            )

        @api.put(ApiUrl.UPDATE_CONFIG, response_model=Config)
        async def update_config(config: Config):
            return await self.backend_request(ConfigAction(request_type=ApiRequestType.UPDATE_CONFIG, config=config))

        @api.post(ApiUrl.CONVERT, response_model=Transaction, responses={200: {"content": {"text/plain": {}}}})
        def convert_transaction(transaction: Transaction, to_format: DataConversionFormats) -> Response:
            if to_format == DataConversionFormats.JSON:
                return self.backend.clean_transaction(transaction)

            return PlainTextResponse(self.backend.convert_to(transaction, to_format))

        @api.get(ApiUrl.DOCUMENT, response_class=FileResponse)
        def get_document():
            return normpath(f"{getcwd()}/{GuiFilesPath.DOC}")

        app.include_router(api)

        return app
