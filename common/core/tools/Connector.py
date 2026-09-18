from common.core.tools.DebugTrace import trace_operation
from struct import pack, error as StructError
from http import HTTPStatus
from http.client import HTTPResponse
from urllib.request import urlopen
from loguru import logger
from pydantic import ValidationError
from PyQt6.QtNetwork import QTcpSocket
from PyQt6.QtCore import pyqtSignal
from common.core.data_models.Config import Config
from common.core.interfaces.MetaClasses import QObjectAbcMeta
from common.core.interfaces.ConnectorInterface import ConnectionInterface
from common.core.tools.validators.DataValidator import DataValidator
from common.core.exceptions.exceptions import DataValidationError, DataValidationWarning


class Connector(QTcpSocket, ConnectionInterface, metaclass=QObjectAbcMeta):
    incoming_transaction_data: pyqtSignal = pyqtSignal(bytes)
    transaction_sent: pyqtSignal = pyqtSignal(str)
    got_remote_spec: pyqtSignal = pyqtSignal(str)
    sending_error: pyqtSignal = pyqtSignal(str, str)
    _config: Config = None

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    def __init__(self, config: Config):
        QTcpSocket.__init__(self)
        self.config = config
        self.readyRead.connect(self.read_transaction_data)
        self._recv_buffer = bytes()
        self.disconnected.connect(self._clear_recv_buffer)

    def _clear_recv_buffer(self):
        logger.debug("TCP receive buffer cleared: discarded_bytes={}", len(self._recv_buffer))
        self._recv_buffer = bytes()

    def connection_in_progress(self):
        return self.state() == self.SocketState.ConnectingState

    def get_connected_host(self) -> str:
        return self.peerAddress().toString()

    def get_connected_port(self) -> int:
        return self.peerPort()

    def send_transaction_data(self, trans_id: str, transaction_data: bytes):
        logger.debug("TCP send requested: trans_id={} body_bytes={} state={}", trans_id, len(transaction_data), self.state().name)
        if not self.state() == self.SocketState.ConnectedState:
            logger.warning("Host disconnected. Trying to establish the connection")

            try:
                self.reconnect_sv()
            except Exception as connection_error:
                self.sending_error.emit(trans_id, str(connection_error))
                return

        if not self.state() == self.SocketState.ConnectedState:
            self.sending_error.emit(trans_id, "Cannot connect to host")
            return

        try:
            transaction_header = pack("!H", len(transaction_data))

        except StructError:
            self.sending_error.emit(trans_id, "Transaction exceeds the two-byte outgoing length limit")
            return

        transaction_data = transaction_header + transaction_data
        bytes_sent = self.write(transaction_data)

        if bytes_sent != len(transaction_data):
            # A partial frame must not be followed by another transaction.
            self.abort()
            self.sending_error.emit(trans_id, "Cannot send transaction data")
            return

        logger.debug("TCP frame buffered: trans_id={} frame_bytes={} accepted_bytes={}", trans_id, len(transaction_data), bytes_sent)

        self.flush()

        self.transaction_sent.emit(trans_id)

    def read_transaction_data(self):
        chunk = self.readAll().data()
        self._recv_buffer += chunk
        logger.debug("TCP data received: chunk_bytes={} buffered_bytes={}", len(chunk), len(self._recv_buffer))

        config = self.config.model_copy(deep=True)
        header_len = config.host.header_length if config.host.header_length_exists else int()

        if header_len <= 0:
            logger.error("TCP reception requires a positive message header length; check host settings")
            self._clear_recv_buffer()
            self.abort()
            return

        while len(self._recv_buffer) >= header_len:
            msg_len = int.from_bytes(self._recv_buffer[:header_len], 'big')

            if msg_len == 0:
                logger.error("Received an empty transaction frame")
                self._clear_recv_buffer()
                self.abort()
                return

            if len(self._recv_buffer) < header_len + msg_len:
                logger.debug("TCP frame incomplete: expected_bytes={} buffered_bytes={} missing_bytes={}",
                             header_len + msg_len, len(self._recv_buffer), header_len + msg_len - len(self._recv_buffer))
                break

            message = self._recv_buffer[:header_len + msg_len]
            self._recv_buffer = self._recv_buffer[header_len + msg_len:]
            logger.debug("TCP frame extracted: frame_bytes={} remaining_bytes={}", len(message), len(self._recv_buffer))
            self.incoming_transaction_data.emit(message)

    @trace_operation
    def connect_sv(self, host: str | None = None, port: int | None = None):
        config = self.config.model_copy(deep=True)
        if host is None:
            host = config.host.host

        if port is None:
            port = config.host.port

        for item in host, port:
            if item in (str(), None):
                logger.error("Missing SV host address or port number. Check the configuration.")
                logger.error("Connection is not established")
                return

        port = int(port)

        logger.info(f"Connecting to {host}:{port}")

        self._clear_recv_buffer()
        self.connectToHost(host, port)

        self.waitForConnected(msecs=10000)
        logger.debug("TCP connection attempt completed: state={} socket_error={}", self.state().name, self.error().name)

        if self.state() is self.SocketState.ConnectedState:
            self.setSocketOption(QTcpSocket.SocketOption.LowDelayOption, 1)
            return

        return self.error()

    @trace_operation
    def disconnect_sv(self):
        if not self.state() == QTcpSocket.SocketState.ConnectedState:
            return

        self.disconnectFromHost()

        if not self.state() == QTcpSocket.SocketState.UnconnectedState:
            self.waitForDisconnected(msecs=10000)

    @trace_operation
    def reconnect_sv(self, host: str | None = None, port: str | None = None):
        for retry in range(3):
            logger.debug("TCP reconnect cleanup: attempt={} state={}", retry + 1, self.state().name)

            if self.state() == self.SocketState.UnconnectedState:
                break

            self.disconnect_sv()

        else:
            logger.error("Cannot disconnect from the host")
            return

        try:
            self.connect_sv(host, port)

        except Exception as connection_error:
            logger.error(f"SV connection error: {connection_error}")

    def is_connected(self):
        return self.state() == self.SocketState.ConnectedState

    @trace_operation
    def get_remote_spec(self):
        validator = DataValidator(self.config)

        try:
            validator.validate_url(self.config.specification.remote_spec_url)

        except (DataValidationWarning, ValidationError, DataValidationError) as url_validation_error:
            logger.error(f'Cannot load remote spec due to incorrect URL: "{self.config.specification.remote_spec_url}"')
            logger.error(url_validation_error)

            return

        logger.info(f"Getting remote spec using url {self.config.specification.remote_spec_url}")

        use_local_spec_text = "Local specification will be used instead"

        try:
            resp: HTTPResponse | str = urlopen(self.config.specification.remote_spec_url)

        except Exception as spec_loading_error:
            logger.error(f"Cannot get remote specification: {spec_loading_error}")
            logger.warning(use_local_spec_text)
            return

        try:
            if resp.getcode() != HTTPStatus.OK:
                logger.error(f"Cannot get remote specification: Unsuccessful HTTP status code {resp.status}")
                logger.warning(use_local_spec_text)
                return

            spec_data: str = resp.read().decode()
            logger.debug("Remote specification received: status={} text_chars={}", resp.getcode(), len(spec_data))

            self.got_remote_spec.emit(spec_data)

        except Exception as spec_error:
            logger.error(f"Cannot load remote specification: {spec_error}")
            logger.warning(use_local_spec_text)
