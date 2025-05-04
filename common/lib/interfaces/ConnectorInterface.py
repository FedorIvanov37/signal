from abc import abstractmethod, ABCMeta


class ConnectionInterface(metaclass=ABCMeta):

    @abstractmethod
    def sending_error(self):
        ...

    @abstractmethod
    def connected(self):
        ...

    @abstractmethod
    def disconnected(self):
        ...

    @abstractmethod
    def state(self):
        ...

    @abstractmethod
    def error(self):
        ...

    @abstractmethod
    def errorString(self):
        ...

    @abstractmethod
    def errorOccurred(self):
        ...

    @abstractmethod
    def connect_sv(self):
        ...

    @abstractmethod
    def disconnect_sv(self):
        ...

    @abstractmethod
    def reconnect_sv(self):
        ...

    @abstractmethod
    def incoming_transaction_data(self):
        ...

    @abstractmethod
    def send_transaction_data(self, *args):
        ...

    @abstractmethod
    def transaction_sent(self):
        ...

    @abstractmethod
    def stateChanged(self):
        ...

    @abstractmethod
    def is_connected(self):
        ...
