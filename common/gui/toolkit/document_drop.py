from PyQt6.QtCore import QObject, QEvent


class DocumentDropFilter(QObject):
    """Route a document dropped on a child viewport to its window."""
    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            mime = event.mimeData()
            if mime.hasUrls() or mime.hasText():
                if event.type() == QEvent.Type.Drop:
                    self.parent().dropEvent(event)
                else:
                    event.acceptProposedAction()
                return True
        return False


def route_document_drops(window, widget):
    target = widget.viewport() if hasattr(widget, 'viewport') else widget
    target.setAcceptDrops(True)
    handler = DocumentDropFilter(window)
    target.installEventFilter(handler)
