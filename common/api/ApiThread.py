from logging import getLogger
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QCoreApplication
from common.api.Api import Api
from common.api.Api import ApiInterface
from common.lib.data_models.Transaction import Transaction
from common.gui.core.WirelessHandler import WirelessHandler
from common.lib.data_models.Config import Config
from common.lib.core.EpaySpecification import EpaySpecification


class ApiThread(QObject):
    _stop: bool = True
    _api_interface: ApiInterface = ApiInterface()
    _run_api: pyqtSignal = pyqtSignal()
    _create_transaction: pyqtSignal = pyqtSignal(Transaction)
    _log_record: pyqtSignal = pyqtSignal(str)
    _api_logger = None
    _wireless_handler = None
    _thread: QThread = None

    api = None

    @property
    def stop(self):
        return self._stop

    @property
    def log_record(self):
        return self._log_record

    @property
    def api_app(self):
        return self.api.app

    @property
    def create_transaction(self):
        return self._create_transaction

    @property
    def run_api(self):
        return self._run_api

    def __init__(self, config: Config):
        super(ApiThread, self).__init__()
        self.config = config
        self._thread = QThread()

    def setup(self, terminal):
        self._stop = False
        self.api = Api(self.config)
        self._api_interface.terminal = terminal
        self._api_interface.config = self.config
        self._api_interface.specification = EpaySpecification()
        self._api_interface.create_transaction.connect(self.create_transaction)
        self.start_thread()

    def set_loger(self):
        self._api_logger = getLogger()
        self._api_logger.setLevel(self.config.debug.level)
        self._wireless_handler = WirelessHandler()
        self._wireless_handler.new_record_appeared.connect(self.log_record)
        self._api_logger.addHandler(self._wireless_handler)

    def start_thread(self):
        self._thread.finished.connect(self.api.deleteLater)
        self.api.moveToThread(self._thread)
        self.run_api.connect(self.api.run_api)
        self._thread.started.connect(self.run)
        self._thread.start()

    def run(self):
        while not self._stop:  # Main endless cycle
            QCoreApplication.processEvents()  # Processes events instead of direct interaction
            QThread.msleep(10)

        self._thread.terminate()
        self._api_logger.removeHandler(self._wireless_handler)
        self._thread.wait()

        print("Closed ")

    def stop_thread(self):  # Once the self.stop become True the thread will be terminated
        self._stop = True
