# from waitress import serve
import datetime
import logging
import sys
from os import getcwd
from os.path import normpath
from loguru import logger
# from flask import Flask, request, redirect, url_for
# from flask_pydantic import validate
from common.api.ApiInterface import ApiInterface
from fastapi import FastAPI, Form, status, HTTPException
from fastapi.responses import HTMLResponse
from uvicorn import run as run_fast_api
# from common.lib.core.Logger import Logger
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QCoreApplication
from PyQt6.QtNetwork import QTcpSocket
from common.lib.decorators.singleton import singleton
from common.lib.data_models.Transaction import Transaction
from common.api.data_models.types import ApiResponse
from common.lib.data_models.Config import Config
from common.lib.core.Parser import Parser
from http import HTTPStatus, HTTPMethod
from common.api.data_models.TransData import TransData
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel
from common.lib.core.EpaySpecification import EpaySpecification
from common.api.data_models.Connection import Connection
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.gui.enums.ConnectionStatus import ConnectionStatus
from common.api.enums.ConnectionActions import ConnectionActions
from common.api.enums.TransTypes import TransTypes
from common.api.data_models.ApiError import ApiError
from common.lib.enums.TermFilesPath import TermFilesPath
from common.api.decorators.log_api_call import log_api_call
from common.api.exceptions.api_exceptions import (
    TransactionTimeout,
    LostTransactionResponse,
    TransactionSendingError,
    HostConnectionTimeout,
    HostConnectionError,
    HostAlreadyConnected,
    HostAlreadyDisconnected,
)


class Api(QObject):
    app: FastAPI = FastAPI()
    signal: ApiInterface = ApiInterface()

    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    def stop(self):
        raise KeyboardInterrupt

    @staticmethod
    @app.get('/')
    def get_document(response_class=HTMLResponse):
        doc_path = normpath(f"{getcwd()}/{GuiFilesPath.DOC}")

        with open(doc_path, encoding="utf8") as html_file:
            return HTMLResponse(html_file.read())

    # @staticmethod
    # @app.route("/api/tools/transactions/validate", methods=[HTTPMethod.POST])
    # @log_api_call
    # @validate()
    # def validate_transaction(body: Transaction):
    #     transaction: Transaction = Api.signal.prepare_response(body)
    #     return transaction




    # @app.post("/api/transactions/<string:trans_type>", response_class=Transaction)
    # def create_predefined_transaction(trans_type: TransTypes, body: TransData):
    #     try:
    #         transaction_request: Transaction = Api.signal.get_transaction(trans_type)
    #
    #     except Exception as transaction_error:
    #         return ApiError(error=transaction_error), HTTPStatus.INTERNAL_SERVER_ERROR
    #
    #     response, status = Api.send_transaction(transaction_request)
    #
    #     return response, status

    # @staticmethod
    # @app.route("/api/connection/<string:action>", methods=[HTTPMethod.PUT])
    # @log_api_call
    # @validate()
    # def update_connection(action: ConnectionActions):
    #     try:
    #         connection: Connection = Api.signal.update_connection(action)
    #
    #     except HostAlreadyConnected as host_already_connected:
    #         connection_error = ApiError(error=str(host_already_connected)).dict()
    #         connection_error["connection"] = Api.signal.build_connection().dict()
    #
    #         return connection_error, HTTPStatus.BAD_REQUEST
    #
    #     except HostAlreadyDisconnected as host_already_connected:
    #         return ApiError(error=f"Disconnection error: {host_already_connected}"), HTTPStatus.BAD_REQUEST
    #
    #     except HostConnectionTimeout as host_connection_timeout:
    #         return ApiError(error=f"Connection error: {host_connection_timeout}"), HTTPStatus.REQUEST_TIMEOUT
    #
    #     except HostConnectionError as host_connection_error:
    #         return ApiError(error=f"Connection error: {host_connection_error}"), HTTPStatus.BAD_GATEWAY
    #
    #     return connection
    #
    # @staticmethod
    # @app.route("/api/connection", methods=[HTTPMethod.GET])
    # @log_api_call
    # @validate()
    # def get_connection():
    #     return Api.signal.build_connection()
    #

    @staticmethod
    @app.get("/api/specification", response_model=EpaySpecModel)
    def get_specification():
        signal: ApiInterface = ApiInterface()

        if not Api.signal.specification:
            raise HTTPException(HTTPStatus.NOT_FOUND, detail="Specification not found")

        return signal.specification.spec

    # @staticmethod
    # @app.route("/api/specification", methods=[HTTPMethod.PUT])
    # @log_api_call
    # @validate()
    # def update_specification(body: EpaySpecModel):
    #     Api.signal.specification.reload_spec(body, commit=False)
    #     return Api.signal.specification.spec
    #
    @staticmethod
    @app.put("/api/config", response_model=Config)
    def update_config(body: Config):
        Api.signal.update_config(body)
        return Api.signal.config

    @staticmethod
    @app.get("/api/config", response_model=Config)
    def get_config():
        if not Api.signal.config:
            raise HTTPException(HTTPStatus.NOT_FOUND, detail="Config not found")

        return Api.signal.config

    @staticmethod
    @app.get("/api/transactions/{trans_id}", response_model=Transaction)
    def get_transaction(trans_id: str):
        transactions: dict[str, Transaction] = Api.signal.build_transactions()

        if not (transaction_dict := transactions.get(trans_id)):
            raise HTTPException(HTTPStatus.NOT_FOUND, detail=f"Transaction {trans_id} not found in transactions queue")

        transaction: Transaction = Transaction.model_validate(transaction_dict)
        transaction: Transaction = Api.signal.prepare_response(transaction)

        return transaction

    @staticmethod
    @app.get("/api/transactions", response_model=dict[str, Transaction])
    def get_transactions():
        transactions = Api.signal.build_transactions()

        return transactions

    @staticmethod
    @app.post("/api/transactions/{trans_id}/reversal", response_model=Transaction)
    def reverse_transaction(trans_id: str):
        try:
            reversal: Transaction = Api.signal.build_reversal(trans_id)

        except (LookupError, LostTransactionResponse) as lookup_error:
            return ApiError(error=str(lookup_error)), HTTPStatus.NOT_FOUND

        except ValueError as processing_error:
            return ApiError(error=processing_error), HTTPStatus.UNPROCESSABLE_ENTITY

        except Exception as reversal_building_error:
            return ApiError(error=reversal_building_error), HTTPStatus.INTERNAL_SERVER_ERROR

        return Api.signal.send_transaction(reversal)

    @staticmethod
    @app.post("/api/transactions", response_model=Transaction)
    def create_transaction(body: Transaction):
        logger.info("API got transaction sending request. POST /api/transactions")

        try:
            response: Transaction = Api.signal.send_transaction(body)

        except TransactionTimeout as transaction_timeout:
            raise HTTPException(HTTPStatus.REQUEST_TIMEOUT, detail=str(transaction_timeout))

        except (LostTransactionResponse, TransactionSendingError) as sending_error:
            raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(sending_error))

        except Exception as unhandled_exception:
            raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(unhandled_exception))

        return response

    def run_api(self):
        run_fast_api(self.app, log_config=None, access_log=True,)
