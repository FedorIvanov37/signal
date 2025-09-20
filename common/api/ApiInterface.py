# from waitress import serve
import datetime
import logging
import sys
from os import getcwd
from os.path import normpath
from loguru import logger
# from flask import Flask, request, redirect, url_for
# from flask_pydantic import validate

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


@singleton
class ApiInterface(QObject):
    _create_transaction: pyqtSignal = pyqtSignal(Transaction)
    _terminal = None
    _transaction_timer: QTimer = None
    _config: Config = None
    _spec: EpaySpecModel = None

    @property
    def specification(self):
        return self._spec

    @specification.setter
    def specification(self, specification):
        self._spec = specification

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = Config.model_validate(config)

    @property
    def terminal(self):
        return self._terminal

    @terminal.setter
    def terminal(self, terminal):
        self._terminal = terminal

    @property
    def transaction_timer(self):
        return self._transaction_timer

    @property
    def create_transaction(self):
        return self._create_transaction

    def __init__(self, config: Config = None, terminal=None):
        super().__init__()

        if config is not None:
            self.config = config

        if terminal is not None:
            self.terminal = terminal

    def prepare_response(self, transaction: Transaction) -> Transaction:
        response: Transaction = transaction.copy(deep=True)

        if self.config.api.hide_secrets:
            response: Transaction = Parser.hide_secret_fields(response)

        response: Transaction = Parser.parse_complex_fields(response, split=self.config.api.parse_subfields)

        return response

    # def build_connection(self) -> Connection:
    #     connection = Connection()
    #
    #     try:
    #         connection.status = ConnectionStatus[self.terminal.connector.state().name]
    #     except KeyError:
    #         connection.status = None
    #
    #     connection.host = self.terminal.connector.peerAddress().toString()
    #     connection.port = self.terminal.connector.peerPort()
    #
    #     return connection
    #
    # def connect(self, connection_params: Connection):
    #     self.terminal.connector.connect_sv(host=connection_params.host, port=connection_params.port)
    #
    # def disconnect(self):
    #     self.terminal.connector.disconnect_sv()
    #

    def build_transactions(self) -> dict[str, Transaction]:
        transactions: dict[str, Transaction] = dict()

        for transaction in self.terminal.trans_queue.queue:
            transactions[transaction.trans_id] = transaction

        return transactions

    def build_reversal(self, transaction_id):
        spec: EpaySpecification = EpaySpecification()

        if not (original_transaction := self.terminal.trans_queue.get_transaction(transaction_id)):
            raise LookupError(f"No transaction id '{transaction_id}' in transaction queue")

        if not original_transaction.matched:
            raise LostTransactionResponse(f"Cannot reverse transaction {transaction_id}. Lost response")

        if not original_transaction.is_request:
            if not (original_transaction := self.terminal.trans_queue.get_transaction(original_transaction.match_id)):
                raise LostTransactionResponse(f"Cannot reverse transaction {transaction_id}. Lost response")

        if not spec.get_reversal_mti(original_transaction.message_type):
            raise ValueError(f"Non-reversible MTI {original_transaction.message_type}")

        reversal: Transaction = self.terminal.build_reversal(original_transaction)

        return reversal

    # def get_reversible_transactions(self) -> list[Transaction]:
    #     return self.terminal.trans_queue.get_reversible_transactions()
    #

    def send_transaction(self, transaction: Transaction) -> Transaction | str:
        timeout = 10

        self.create_transaction.emit(transaction)

        if not self.config.api.wait_remote_host_response:
            return self.prepare_response(transaction)

        begin = datetime.datetime.now()

        while True:
            if transaction.matched:
                break

            if (datetime.datetime.now() - begin).seconds > timeout and not transaction.matched:
                raise TransactionTimeout(f"No remote host transaction response in {timeout} seconds")

            if transaction.error:
                raise TransactionSendingError(f"Cannot send transaction: {transaction.error}")

            QCoreApplication.processEvents()

        if not (response := self.terminal.trans_queue.get_transaction(transaction.match_id)):
            raise LostTransactionResponse("Lost transaction response")

        try:
            response: Transaction = self.prepare_response(response)
        except Exception as response_processing_error:
            raise TransactionSendingError(f"Cannot send transaction: {response_processing_error}")

        return response

    def update_config(self, config: Config) -> None:  # TODO emit signal about the change
        with open(TermFilesPath.CONFIG, 'w') as config_file:
            config_file.write(config.json())

        self.terminal.config = config
        self.config = config

    # @staticmethod
    # def get_transaction(trans_type: TransTypes) -> Transaction:
    #     transaction_files_map = {
    #         TransTypes.ECHO_TEST: TermFilesPath.ECHO_TEST,
    #         TransTypes.KEEP_ALIVE: TermFilesPath.KEEP_ALIVE,
    #         TransTypes.EPOS_PURCHASE: TermFilesPath.DEFAULT_FILE,
    #     }
    #
    #     if not (transaction_file := transaction_files_map.get(trans_type)):
    #         raise TypeError(f"Unknown transaction type '{trans_type}'")
    #
    #     with open(transaction_file) as transaction_file_data:
    #         transaction: Transaction = Transaction.model_validate_json(transaction_file_data.read())
    #
    #     if trans_type == TransTypes.KEEP_ALIVE:
    #         transaction.is_keep_alive = True
    #
    #     return transaction
    #
    # def update_connection(self, action: ConnectionActions):
    #     match action:
    #         case ConnectionActions.RECONNECT:
    #             target_state: QTcpSocket.SocketState = QTcpSocket.SocketState.ConnectedState
    #
    #             if self.terminal.connector.state() == target_state:
    #                 self.update_connection(ConnectionActions.DISCONNECT)
    #
    #             return self.update_connection(ConnectionActions.CONNECT)
    #
    #         case ConnectionActions.DISCONNECT:
    #             target_state: QTcpSocket.SocketState = QTcpSocket.SocketState.UnconnectedState
    #             connection: Connection = self.build_connection()
    #
    #             if self.terminal.connector.state() == target_state:
    #                 raise HostAlreadyDisconnected("The host is already disconnected")
    #
    #             self.disconnect()
    #
    #         case ConnectionActions.CONNECT:
    #             if self.terminal.connector.state() == QTcpSocket.SocketState.ConnectedState:
    #                 raise HostAlreadyConnected(
    #                     f"The host is already connected. "
    #                     f"Disconnect before open new connection or use {ConnectionActions.RECONNECT}"
    #                 )
    #
    #             target_state: QTcpSocket.SocketState = QTcpSocket.SocketState.ConnectedState
    #             connection: Connection = Connection(host=self.config.host.host, port=self.config.host.port)
    #
    #             if request.content_type == "application/json":
    #                 connection: Connection = Connection.model_validate(request.get_json())
    #
    #             self.connect(connection)
    #
    #         case _:
    #             raise HostConnectionError(f"Unknown connection action: {action}")
    #
    #     if self.terminal.connector.state() == target_state:
    #         connection.status = ConnectionStatus[self.terminal.connector.state().name]
    #         return connection
    #
    #     if self.terminal.connector.error() == QTcpSocket.SocketError.SocketTimeoutError:
    #         raise HostConnectionTimeout(self.terminal.connector.errorString())
    #
    #     raise HostConnectionError(self.terminal.connector.errorString())
