from http import HTTPStatus


class TransactionTimeout(Exception):
    pass


class LostTransactionResponse(Exception):
    pass


class TransactionSendingError(Exception):
    pass


class HostAlreadyConnected(Exception):
    pass


class HostAlreadyDisconnected(Exception):
    pass


class HostConnectionError(Exception):
    pass


class HostConnectionTimeout(Exception):
    pass


class TerminalApiError(Exception):
    def __init__(self, detail: str, http_status: HTTPStatus):
        self.detail = detail
        self.http_status = http_status
