from PyQt6.QtNetwork import QTcpSocket
from common.gui.enums.GuiFilesPath import GuiFilesPath
from enum import StrEnum


class ConnectionStatuses(StrEnum):
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    IN_PROGRESS = "Connection In Progress"
    UNKNOWN = "Unknown"


class ConnectionIcons(StrEnum):
    GREY = GuiFilesPath.GREY_CIRCLE
    GREEN = GuiFilesPath.GREEN_CIRCLE
    YELLOW = GuiFilesPath.YELLOW_CIRCLE
    RED = GuiFilesPath.RED_CIRCLE


ConnectionStatusDict = {
    QTcpSocket.SocketState.ConnectedState: ConnectionStatuses.CONNECTED,
    QTcpSocket.SocketState.UnconnectedState: ConnectionStatuses.DISCONNECTED,
    QTcpSocket.SocketState.ConnectingState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.HostLookupState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.BoundState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.ClosingState: ConnectionStatuses.IN_PROGRESS,
    QTcpSocket.SocketState.ListeningState: ConnectionStatuses.UNKNOWN,
}


ConnectionIconDict = {
    QTcpSocket.SocketState.ConnectedState: GuiFilesPath.GREEN_CIRCLE,
    QTcpSocket.SocketState.UnconnectedState: GuiFilesPath.RED_CIRCLE,
    QTcpSocket.SocketState.ConnectingState: GuiFilesPath.YELLOW_CIRCLE,
    QTcpSocket.SocketState.HostLookupState: GuiFilesPath.YELLOW_CIRCLE,
    QTcpSocket.SocketState.BoundState: GuiFilesPath.YELLOW_CIRCLE,
    QTcpSocket.SocketState.ClosingState: GuiFilesPath.YELLOW_CIRCLE,
    QTcpSocket.SocketState.ListeningState: GuiFilesPath.GREY_CIRCLE,
}


ConnectionStatus = StrEnum("ConnectionStatus", {field.name: value for field, value in ConnectionStatusDict.items()})
