from contextlib import suppress
from PyQt6.QtCore import QEventLoop, QTimer, QCoreApplication
from common.lib.data_models.TransStatus import TransStatus
from common.core.data_models.Transaction import Transaction
from common.core.tools.Terminal import Terminal
from common.core.data_models.Config import Config
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.tools.Parser import Parser
from common.core.enums.DataFormats import OutputFilesFormat
from common.core.tools.FieldsGenerator import FieldsGenerator


class TerminalClient:
    """
    Public Python facade for working with Signal

    This class provides high-level operations and hides Qt event loop, signal handling, queues, parser setup, logging
    setup, and terminal lifecycle details from the caller

    Direct access to internal tools is available through properties for advanced scenarios
    """

    @property
    def specification(self):
        return self._specification

    @property
    def transaction_queue(self):
        return self.terminal.trans_queue

    @property
    def logger(self):
        return self.terminal.logger

    @property
    def terminal(self):
        return self._terminal

    @property
    def connector(self):
        return self.terminal.connector

    @property
    def fields_generator(self):
        return self._fields_generator

    @property
    def parser(self):
        return self._parser

    @property
    def config(self):
        return self._config

    def __init__(self):
        self.app = QCoreApplication.instance() or QCoreApplication(list())
        self._config = Config(TermFilesPath.CONFIG)
        self._parser = Parser(self.config)
        self._terminal = Terminal(self.config)
        self._fields_generator = FieldsGenerator()
        self._specification: EpaySpecification = EpaySpecification()
        self.console_log_handler_id = None

    def connect(self):
        self.connector.connect_sv()

    def disconnect(self):
        self.connector.disconnect_sv()

    def is_connected(self) -> bool:
        return self.connector.is_connected()

    def enable_console_log(self, enable: bool = True):
        if self.console_log_handler_id is not None:
            self.logger.removeHandler(self.console_log_handler_id)

        if enable:
            self.console_log_handler_id = self.terminal.logger.add_stdout_handler()

    def parse_file(self, file_path: str) -> Transaction:
        return self.parser.parse_file(file_path)

    def get_sv_dump(self, transaction: Transaction) -> str:
        return self.parser.create_sv_dump(transaction)

    def reverse_transaction(self, original_trans_id: str) -> Transaction:
        original_transaction: Transaction = self.transaction_queue.get_transaction(original_trans_id)

        if not original_transaction:
            raise LookupError(f"Transaction with id {original_trans_id} not found")

        reversal: Transaction = self.terminal.build_reversal(original_transaction)

        if not reversal:
            raise RuntimeError("Cannot reverse transaction, unexpected exception")

        response: Transaction = self.send_transaction(reversal)

        return response

    def echo_test(self) -> Transaction:
        request: Transaction = Transaction(TermFilesPath.ECHO_TEST)
        response: Transaction = self.send_transaction(request)
        return response

    def keep_alive(self) -> Transaction:
        request: Transaction = Transaction(TermFilesPath.KEEP_ALIVE)
        response: Transaction = self.send_transaction(request)
        return response

    def parse_dump(self, dump: str) -> Transaction:
        return self.parser.parse_dump(dump)

    def validate_transaction(self, transaction: Transaction):
        return self.terminal.trans_validator.validate_transaction(transaction)

    def save_transaction(self, transaction: Transaction, data_format: OutputFilesFormat, file_name: str = None):
        self.terminal.save_transaction(transaction, data_format, file_name)

    def send_transaction(self, transaction: Transaction, wait_for_response: bool = True, timeout_ms: int = 60_000) -> Transaction | None:
        if not wait_for_response:
            self.terminal.send(transaction)
            return None

        return self._send_and_wait(transaction, timeout_ms)

    def _send_and_wait(self, transaction: Transaction, timeout_ms: int = 60_000) -> Transaction:
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)

        transaction_data = TransStatus()

        def on_response(response: Transaction):
            transaction_data.done = True
            transaction_data.response = response
            loop.quit()

        def on_timeout():
            transaction_data.timeout = True
            loop.quit()

        def do_send():
            self.terminal.send(transaction)
            timer.start(timeout_ms)

        self.transaction_queue.incoming_transaction.connect(on_response)
        timer.timeout.connect(on_timeout)

        try:
            QTimer.singleShot(0, do_send)
            loop.exec()

            if transaction_data.timeout:
                raise TimeoutError(f"Transaction timeout after {timeout_ms} ms")

            return transaction_data.response

        finally:
            with suppress(TypeError):
                self.transaction_queue.incoming_transaction.disconnect(on_response)

            timer.stop()
