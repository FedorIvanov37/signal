"""Observe Qt shortcut activation without maintaining a registry of hotkeys."""
from loguru import logger
from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QKeySequence


class ShortcutLogging(QObject):
    @classmethod
    def install(cls, application):
        # One filter per application, including when GUI backends are recreated.
        for child in application.children():
            if isinstance(child, cls):
                return child
        observer = cls(application)
        application.installEventFilter(observer)
        return observer

    def eventFilter(self, receiver, event):
        if event.type() == QEvent.Type.Shortcut:
            logger.debug(
                "GUI hotkey: sequence={} receiver={} object={} ambiguous={}",
                event.key().toString(QKeySequence.SequenceFormat.PortableText),
                type(receiver).__name__, receiver.objectName(), event.isAmbiguous(),
            )
        return False  # Qt must still deliver the event and invoke the action.
