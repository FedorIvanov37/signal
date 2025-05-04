from enum import StrEnum


class ConnectionActions(StrEnum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"
