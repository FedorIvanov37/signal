from PyQt6.QtCore import QObject, QThread, QCoreApplication
from common.lib.core.Connector import Connector
from common.lib.data_models.Config import Config
from common.lib.interfaces.ConnectorInterface import ConnectionInterface
from common.lib.interfaces.MetaClasses import QObjectAbcMeta


"""

 Separate thread for TCP socket. Should be used for GUI to not freeze the MainWindow while the connection is in progress
 Processes event loop in a while-true cycle until property self.stop will be set as True. For non-GUI mode better to use 
 a native connector, which blocks the work while the connection is in progress, otherwise, work will be continued when 
 the connection is not yet established.
 
 No direct interaction or call is possible. Using a separate stream the connector can interact through pyqtSignals only 

 The connector Implements ConnectionInterface - metaclass, which describes the functions kit. In case of changing the 
 code, change the interface first 

"""


class ConnectionThread(ConnectionInterface, QObject, metaclass=QObjectAbcMeta):
    thread: QThread
    stop: bool = False

    @property
    def peerAddress(self):
        return self.connector.peerAddress

    @property
    def peerPort(self):
        return self.connector.peerPort

    @property
    def sending_error(self):
        return self.connector.sending_error

    @property
    def connected(self):
        return self.connector.connected

    @property
    def disconnected(self):
        return self.connector.disconnected

    @property
    def state(self):
        return self.connector.state

    @property
    def error(self):
        return self.connector.error

    @property
    def errorString(self):
        return self.connector.errorString

    @property
    def errorOccurred(self):
        return self.connector.errorOccurred

    @property
    def connect_sv(self):
        return self.connector.connect_sv

    @property
    def disconnect_sv(self):
        return self.connector.disconnect_sv

    @property
    def reconnect_sv(self):
        return self.connector.reconnect_sv

    @property
    def incoming_transaction_data(self):
        return self.connector.incoming_transaction_data

    @property
    def send_transaction_data(self):
        return self.connector.send_transaction_data

    @property
    def transaction_sent(self):
        return self.connector.transaction_sent

    @property
    def got_remote_spec(self):
        return self.connector.got_remote_spec

    @property
    def stateChanged(self):
        return self.connector.stateChanged

    @property
    def get_remote_spec(self):
        return self.connector.get_remote_spec

    @property
    def connection_in_progress(self):
        return self.connector.connection_in_progress

    def __init__(self, config: Config):
        super(ConnectionThread, self).__init__()
        self.config: Config = config
        self.connector: Connector = Connector(self.config)
        self.thread: QThread = QThread()
        self.connector.moveToThread(self.thread)
        self.thread.started.connect(self.run)
        self.thread.start()  # Once the connector started no more direct call can be made

    def run(self):
        while not self.stop:  # Main endless cycle
            QCoreApplication.processEvents()  # Processes events instead of direct interaction
            QThread.msleep(10)

        self.thread.terminate()
        self.disconnect_sv()

    def stop_thread(self):  # Once the self.stop become True the connection will be dropped and the thread terminated
        self.stop = True

    def is_connected(self):
        return self.connector.state() == self.connector.SocketState.ConnectedState
