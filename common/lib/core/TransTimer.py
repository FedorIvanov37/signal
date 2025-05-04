from re import search
from loguru import logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from common.lib.enums import KeepAlive


class TransactionTimer(QObject):
    _trans_loop_timer: QTimer = QTimer()
    _send_transaction: pyqtSignal = pyqtSignal()
    _interval_was_set: pyqtSignal = pyqtSignal(str, str)

    @property
    def send_transaction(self):
        return self._send_transaction

    @property
    def interval_was_set(self):
        return self._interval_was_set

    def __init__(self, trans_type: str):
        super().__init__()
        self.trans_type = trans_type

    def activate_transaction_loop(self, interval: int):
        self._trans_loop_timer.stop()
        self._trans_loop_timer = QTimer()
        self._trans_loop_timer.timeout.connect(self.send_transaction)
        self._trans_loop_timer.start(int(interval) * 1000)

    def set_trans_loop_interval(self, interval_name: str):
        if interval_name == KeepAlive.IntervalNames.KEEP_ALIVE_ONCE:
            self.send_transaction.emit()
            return

        if interval_name == KeepAlive.IntervalNames.KEEP_ALIVE_STOP:
            self._trans_loop_timer.stop()
            self.interval_was_set.emit(interval_name, self.trans_type)
            logger.info(f"{self.trans_type} loop is deactivated")
            return

        try:
            interval: int = KeepAlive.IntervalTimes[interval_name]

        except KeyError:

            if not (interval_from_name := search(r"^\d+", interval_name)):
                return

            interval: int = int(interval_from_name.group())

        self.activate_transaction_loop(interval)

        self.interval_was_set.emit(interval_name, self.trans_type)

        logger.info(f"{self.trans_type} loop set to {interval_name}")
