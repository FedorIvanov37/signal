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
