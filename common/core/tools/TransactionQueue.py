from common.core.tools.DebugTrace import trace_operation
from loguru import logger
from collections import deque
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtCore import QTimer
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.data_models.Transaction import Transaction
from common.core.tools.Parser import Parser
from common.core.interfaces.ConnectorInterface import ConnectionInterface


class TransactionQueue(QObject):
    spec: EpaySpecification = EpaySpecification()
    queue: deque[Transaction] = None
    incoming_transaction: pyqtSignal = pyqtSignal(Transaction)
    outgoing_transaction: pyqtSignal = pyqtSignal(Transaction)
    transaction_timeout: pyqtSignal = pyqtSignal(Transaction, float)
    ready_to_send: pyqtSignal = pyqtSignal(str, bytes)
    socket_error: pyqtSignal = pyqtSignal(Transaction)
    parsing_error: pyqtSignal = pyqtSignal(str)

    def __init__(self, connector: ConnectionInterface):
        QObject.__init__(self)
        self.connector = connector
        self.timers: dict[str, QTimer] = {}
        self.queue = deque(maxlen=10000)
        self.ready_to_send.connect(self.connector.send_transaction_data)
        self.connector.incoming_transaction_data.connect(self.receive_transaction_data)
        self.connector.transaction_sent.connect(self.request_was_sent)
        self.connector.sending_error.connect(self.set_sending_error)

    def set_sending_error(self, trans_id, error_message):
        logger.debug("Queue send failure: trans_id={} queue_size={}", trans_id, len(self.queue))
        if not (transaction := self.get_transaction(trans_id)):
            logger.error(error_message)
            return

        transaction.success = False
        transaction.error = error_message
        self.socket_error.emit(transaction)
        logger.error(error_message)

    @trace_operation
    def send_transaction_data(self, request: Transaction):
        try:
            transaction_dump: bytes = Parser.create_dump(request)
        except (ValueError, TypeError) as parsing_error:
            self.set_sending_error(request.trans_id, f"Parsing error: {parsing_error}")
            return

        self.ready_to_send.emit(request.trans_id, transaction_dump)

    @trace_operation
    def receive_transaction_data(self, transaction_data: bytes):
        try:
            transactions: list[Transaction] = Parser.parse_raw_data(
                transaction_data, flat=True, config=self.connector.config.model_copy(deep=True))

        except Exception as parsing_error:
            logger.error(f"Incoming transaction parsing error: {parsing_error}")
            self.parsing_error.emit(str(parsing_error))
            return

        for transaction in transactions:
            self.put_transaction(transaction, send=False)

    @trace_operation
    def put_transaction(self, transaction, send=True):
        transaction.direction = 'outgoing' if send else 'incoming'
        transactions_to_delete = []

        if send and any([transaction.match_id, transaction.matched]):
            logger.warning("Transaction request is already matched before")

        for old_transaction in self.queue:
            if transaction.trans_id not in (old_transaction.trans_id, old_transaction.match_id):
                continue

            if transaction.trans_id == old_transaction.trans_id:
                logger.warning(f"Transaction with ID [{transaction.trans_id}] already exists. "
                               f"The transaction will be rewritten")

            if transaction.trans_id == old_transaction.match_id:
                logger.warning(f"Transaction with match ID [{transaction.trans_id}] already exists. The transaction "
                               f"will be rewritten")

            transactions_to_delete.append(old_transaction)

        for old_transaction in transactions_to_delete:
            self.remove_from_queue(old_transaction)

        transaction.is_request = self.spec.is_request(transaction)
        if len(self.queue) == self.queue.maxlen:
            self._discard_timer(self.queue[0].trans_id)
        self.queue.append(transaction)
        logger.debug("Queue insertion: trans_id={} mti={} direction={} is_request={} queue_size={}",
                     transaction.trans_id, transaction.message_type, transaction.direction,
                     transaction.is_request, len(self.queue))

        if send:
            transaction.sending_time = datetime.now()
            self.send_transaction_data(transaction)
            return

        self.put_response(transaction)

    @trace_operation
    def put_response(self, response: Transaction):
        if not self.match_transaction(response):
            logger.debug("Queue response unmatched: trans_id={} mti={} candidates={}",
                         response.trans_id, response.message_type, len(self.queue))
            self.incoming_transaction.emit(response)
            return

        response.utrnno = Parser.get_field_data(response.data_fields, self.spec.utrnno_path)
        response.resp_time_seconds = self.stop_transaction_timer(response)
        request = self.get_transaction(response.match_id)
        self.merge_trans_data(request, response)
        logger.debug("Queue response completed: request_id={} response_id={} success={} elapsed_seconds={}",
                     request.trans_id, response.trans_id, response.success, response.resp_time_seconds)
        self.incoming_transaction.emit(response)

    def add_logical_fields(self, transaction: Transaction) -> Transaction:
        transaction.is_request = self.spec.is_request(transaction)
        transaction.is_reversal = self.spec.is_reversal(transaction.message_type)

        if transaction.direction != 'incoming':
            return transaction

        if transaction.data_fields.get(self.spec.FIELD_SET.FIELD_039_AUTHORIZATION_RESPONSE_CODE) == "00":
            transaction.success = True

        return transaction

    def merge_trans_data(self, request: Transaction, response: Transaction):
        for message in (request, response):
            self.add_logical_fields(message)

        request.utrnno = response.utrnno
        request.success = response.success
        request.resp_time_seconds = response.resp_time_seconds
        response.generate_fields = request.generate_fields
        response.is_keep_alive = request.is_keep_alive
        response.is_reversal = request.is_reversal

    def start_transaction_timer(self, transaction: Transaction, timeout=60):
        logger.debug("Transaction timer starting: trans_id={} timeout_seconds={}", transaction.trans_id, timeout)
        self._discard_timer(transaction.trans_id)
        timer: QTimer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.process_timeout(transaction))
        self.timers[transaction.trans_id] = timer
        timer.start(timeout * 1000)

    def stop_transaction_timer(self, response):
        timer: QTimer

        timer = self.timers.get(response.match_id)
        if timer is None or not timer.isActive():
            self._discard_timer(response.match_id)
            if not (request := self.get_transaction(response.match_id)):
                return

            if not request.sending_time:
                return

            time_spend: timedelta = datetime.now() - request.sending_time
            time_spend: float = round(time_spend.total_seconds(), 3)

            return time_spend

        time_spend = (timer.interval() - timer.remainingTime()) / 1000
        self._discard_timer(response.match_id)

        logger.debug("Transaction timer stopped: trans_id={} elapsed_seconds={}", response.match_id, time_spend)
        return time_spend

    def _discard_timer(self, trans_id):
        timer = self.timers.pop(trans_id, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def process_timeout(self, transaction):
        timer: QTimer

        if not (timer := self.timers.get(transaction.trans_id)):
            return

        timeout_secs = int(timer.interval() / 1000)
        self._discard_timer(transaction.trans_id)
        logger.debug("Transaction timer expired: trans_id={} timeout_seconds={}", transaction.trans_id, timeout_secs)
        self.transaction_timeout.emit(transaction, timeout_secs)

    def request_was_sent(self, trans_id):
        if not (request := self.get_transaction(trans_id)):
            return

        if request.direction != 'outgoing':
            return
        if self.spec.get_resp_mti(request.message_type):
            self.start_transaction_timer(request)
        self.outgoing_transaction.emit(request)

    def get_last_reversible_transaction_id(self) -> str:
        if reversible_transactions := self.get_reversible_transactions():
            return max(transaction.trans_id for transaction in reversible_transactions)

    def get_reversible_transactions(self) -> list[Transaction]:
        transactions: list[Transaction] = []

        transaction: Transaction

        for transaction in self.queue:
            if transaction.direction != 'outgoing':
                continue
            if not self.spec.get_reversal_mti(transaction.message_type):
                continue

            transactions.append(transaction)

        return transactions

    def remove_from_queue(self, transaction):
        transactions_to_remove = [
            trans for trans in self.queue if transaction.trans_id in (trans.trans_id, trans.match_id)
        ]

        for transaction in transactions_to_remove:
            self._discard_timer(transaction.trans_id)
            self.queue.remove(transaction)
        logger.debug("Queue removal completed: removed={} remaining={}", len(transactions_to_remove), len(self.queue))

    def get_transaction(self, trans_id: str) -> Transaction | None:
        transaction = None

        for trans in self.queue:
            if trans_id == trans.trans_id:
                transaction = trans
                break

        return transaction

    @trace_operation
    def get_original_transaction(self, reversal: Transaction):
        if not reversal.is_reversal:
            return

        reversal_fields: list[str] = list(self.spec.get_reversal_fields())
        reversal_fields.sort()

        for transaction in self.queue:
            matched_fields = list()

            if transaction.direction != 'outgoing':
                continue

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
        if request.direction != 'outgoing' or response.direction != 'incoming':
            return False
        if request.matched or response.matched:
            return False

        if response.message_type not in (request.message_type, self.spec.get_resp_mti(request.message_type)):
            return False

        for field in self.spec.get_match_fields():
            if request.data_fields.get(field) != response.data_fields.get(field):
                return False

        return True

    @trace_operation
    def match_transaction(self, response: Transaction) -> bool:
        matched_request: Transaction | None = None

        for request in self.queue:
            if not self.is_matched(request, response):
                continue

            matched_request = request
            break

        if not matched_request:
            logger.debug("Response matching finished without a match: response_id={} candidates={}", response.trans_id, len(self.queue))
            return False

        matched_request.matched = True
        response.matched = True
        response.match_id = matched_request.trans_id
        matched_request.match_id = response.trans_id
        logger.debug("Response matched: request_id={} response_id={}", matched_request.trans_id, response.trans_id)

        return True
