from enum import StrEnum
from PyQt6.QtNetwork import QTcpSocket


class ConnectionStatuses(StrEnum):
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    IN_PROGRESS = "Connection In Progress"
    UNKNOWN = "Unknown"


ConnectionStatusDict = {
    QTcpSocket.SocketState.ConnectedState: ConnectionStatuses.CONNECTED,
    QTcpSocket.SocketState.UnconnectedState: ConnectionStatuses.DISCONNECTED,
    QTcpSocket.SocketState.ConnectingState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.HostLookupState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.BoundState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.ClosingState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.ListeningState: ConnectionStatuses.UNKNOWN,
}

ConnectionStatus = StrEnum(
    "ConnectionStatus", {field.name: value for field, value in ConnectionStatusDict.items()}
)
