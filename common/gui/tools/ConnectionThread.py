from PyQt6.QtCore import QObject, QThread
from common.core.tools.Connector import Connector
from common.core.data_models.Config import Config
from common.core.interfaces.ConnectorInterface import ConnectionInterface
from common.core.interfaces.MetaClasses import QObjectAbcMeta
from contextlib import suppress


"""

 TCP socket worker using the native QThread event loop.
 Shutdown stops the event loop and deletes the socket in its owning thread.

 The connector Implements ConnectionInterface - metaclass, which describes the functions kit. In case of changing the 
 code, change the interface first 

"""


class ConnectionThread(ConnectionInterface, QObject, metaclass=QObjectAbcMeta):
    thread: QThread
    stop: bool = False
    _config: Config

    @property
    def config(self):
        try:
            return self.connector.config
        except AttributeError:
            return self._config

    @config.setter
    def config(self, config):
        self._config = config

        with suppress(AttributeError):
            self.connector.config = config

    @property
    def get_connected_host(self):
        return self.connector.get_connected_host

    @property
    def get_connected_port(self):
        return self.connector.get_connected_port

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
        self.thread.finished.connect(self.connector.deleteLater)
        self.thread.start()

    def stop_thread(self):
        self.stop = True
        self.thread.quit()
        self.thread.wait()

    def is_connected(self):
        return self.connector.state() == self.connector.SocketState.ConnectedState
