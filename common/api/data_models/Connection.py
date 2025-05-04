from pydantic import BaseModel
from common.gui.enums.ConnectionStatus import ConnectionStatus
from PyQt6.QtNetwork import QTcpSocket


class Connection(BaseModel):
    host: str | None = None
    port: int | None = None
    status: ConnectionStatus = ConnectionStatus[QTcpSocket.SocketState.UnconnectedState.name]
