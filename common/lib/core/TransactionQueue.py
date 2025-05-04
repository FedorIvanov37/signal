from loguru import logger
from collections import deque
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtCore import QTimer
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.core.FieldsGenerator import FieldsGenerator
from common.lib.data_models.Transaction import Transaction
from common.lib.core.Parser import Parser
from common.lib.interfaces.ConnectorInterface import ConnectionInterface


class TransactionQueue(QObject):
    spec: EpaySpecification = EpaySpecification()
    queue: deque[Transaction] = deque(maxlen=1024)
    incoming_transaction: pyqtSignal = pyqtSignal(Transaction)
    outgoing_transaction: pyqtSignal = pyqtSignal(Transaction)
    transaction_timeout: pyqtSignal = pyqtSignal(Transaction, float)
    ready_to_send: pyqtSignal = pyqtSignal(str, bytes)

    def __init__(self, connector: ConnectionInterface):
        QObject.__init__(self)
        self.connector = connector
        self.generator: FieldsGenerator = FieldsGenerator()
        self.timers: dict[str, QTimer] = {}
        self.ready_to_send.connect(self.connector.send_transaction_data)
        self.connector.incoming_transaction_data.connect(self.receive_transaction_data)
        self.connector.transaction_sent.connect(self.request_was_sent)
        self.connector.sending_error.connect(self.set_sending_error)

    def set_sending_error(self, trans_id, error_message):
        if not (transaction := self.get_transaction(trans_id)):
            logger.error(error_message)
            return

        transaction.success = False
        transaction.error = error_message
        logger.error(error_message)

    def send_transaction_data(self, request: Transaction):
        if not request.is_request:
            request.success = False
            request.error = "Wrong MTI"
            raise TypeError(request.error)

        try:
            transaction_dump: bytes = Parser.create_dump(request)
        except (ValueError, TypeError) as parsing_error:
            request.success = False
            request.error = f"Parsing error: {parsing_error}"
            logger.error(request.error)
            return

        self.ready_to_send.emit(request.trans_id, transaction_dump)

    def receive_transaction_data(self, transaction_data: bytes):
        try:
            transactions: list[Transaction] = Parser.parse_raw_data(transaction_data, flat=True)

        except Exception as parsing_error:
            logger.error(f"Incoming transaction parsing error: {parsing_error}")
            return

        for transaction in transactions:
            self.put_transaction(transaction)

    def put_transaction(self, transaction, send=True):
        transactions_to_delete = []

        for old_transaction in self.queue:
            if transaction.trans_id not in (old_transaction.trans_id, old_transaction.match_id):
                continue

            if transaction.trans_id == old_transaction.trans_id:
                logger.warning(f"Transaction with ID [{transaction.trans_id}] already exists. The transaction will be rewritten")

            if transaction.trans_id == old_transaction.match_id:
                logger.warning(f"Transaction with match ID [{transaction.trans_id}] already exists. The transaction will be rewritten")

            transactions_to_delete.append(old_transaction)

        for old_transaction in transactions_to_delete:
            self.remove_from_queue(old_transaction)

        transaction.is_request = self.spec.is_request(transaction)
        self.queue.append(transaction)

        if send and transaction.is_request:
            transaction.sending_time = datetime.now()
            self.send_transaction_data(transaction)
            return

        self.put_response(transaction)

    def put_response(self, response: Transaction):
        if response.is_request:
            raise TypeError("Wrong MTI")

        if not self.match_transaction(response):
            self.incoming_transaction.emit(response)
            return

        response = self.set_utrnno(response)
        response.resp_time_seconds = self.stop_transaction_timer(response)
        request = self.get_transaction(response.match_id)
        self.generator.merge_trans_data(request, response)
        self.incoming_transaction.emit(response)

    def set_utrnno(self, response: Transaction):
        if not (de047 := response.data_fields.get(self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD)):
            return response

        de047 = Parser.split_complex_field(self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD, de047)
        response.utrnno = de047.get("064") # TODO

        return response

    def start_transaction_timer(self, transaction: Transaction, timeout=60):
        timer: QTimer = QTimer()
        timer.timeout.connect(lambda: self.process_timeout(transaction))
        self.timers[transaction.trans_id] = timer
        timer.start(timeout * 1000)

    def stop_transaction_timer(self, response):
        timer: QTimer

        if not (timer := self.timers.get(response.match_id)):
            return

        if not timer.isActive():
            if not (request := self.get_transaction(response.match_id)):
                return

            if not request.sending_time:
                return

            time_spend: timedelta = datetime.now() - request.sending_time
            time_spend: float = round(time_spend.microseconds / 1000000, 3)

            return time_spend

        time_spend = (timer.interval() - timer.remainingTime()) / 1000
        timer.stop()

        return time_spend

    def process_timeout(self, transaction):
        timer: QTimer

        if not (timer := self.timers.get(transaction.trans_id)):
            return

        timeout_secs = int(timer.interval() / 1000)
        self.transaction_timeout.emit(transaction, timeout_secs)
        timer.stop()

    def request_was_sent(self, trans_id):
        if not (request := self.get_transaction(trans_id)):
            return

        self.start_transaction_timer(request)
        self.outgoing_transaction.emit(request)

    def get_last_reversible_transaction_id(self) -> str:
        if reversible_transactions := self.get_reversible_transactions():
            return max(transaction.trans_id for transaction in reversible_transactions)

    def get_reversible_transactions(self) -> list[Transaction]:
        transactions: list[Transaction] = []

        transaction: Transaction

        for transaction in self.queue:
            if not self.spec.get_reversal_mti(transaction.message_type):
                continue

            transactions.append(transaction)

        return transactions

    def remove_from_queue(self, transaction):
        transactions_to_remove = [
            trans for trans in self.queue if transaction.trans_id in (trans.trans_id, trans.match_id)
        ]

        for transaction in transactions_to_remove:
            self.queue.remove(transaction)

    def get_transaction(self, trans_id: str) -> Transaction | None:
        transaction = None

        for trans in self.queue:
            if trans_id == trans.trans_id:
                transaction = trans
                break

        return transaction

    def get_original_transaction(self, reversal: Transaction):
        if not reversal.is_reversal:
            return

        reversal_fields: list[str] = list(self.spec.get_reversal_fields())
        reversal_fields.sort()

        for transaction in self.queue:
            matched_fields = list()

            if transaction.is_reversal:
                continue

            for field in reversal_fields:
                if not (reversal_field := reversal.data_fields.get(field)):
                    break

                if not (transaction_field := transaction.data_fields.get(field)):
                    break

                if not reversal_field == transaction_field:
                    break

                matched_fields.append(field)

            matched_fields.sort()

            if matched_fields == reversal_fields:
                return transaction

    def is_matched(self, request: Transaction, response: Transaction) -> bool:
        if request.matched or response.matched:
            return False

        if response.message_type != self.spec.get_resp_mti(request.message_type):
            return False

        for field in self.spec.get_match_fields():
            if request.data_fields.get(field) != response.data_fields.get(field):
                return False

        return True

    def match_transaction(self, response: Transaction) -> bool:
        matched_request: Transaction | None = None

        for request in self.queue:
            if not self.is_matched(request, response):
                continue

            matched_request = request
            break

        if not matched_request:
            return False

        matched_request.matched = True
        response.matched = True
        response.match_id = matched_request.trans_id
        matched_request.match_id = response.trans_id

        return True
