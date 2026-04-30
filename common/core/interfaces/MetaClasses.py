from PyQt6.QtCore import QObject
from abc import ABCMeta


class QObjectAbcMeta(type(QObject), ABCMeta):
    pass
