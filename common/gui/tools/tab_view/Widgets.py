from PyQt6.QtGui import QFont, QPalette
from PyQt6.QtCore import pyqtSignal, QSignalBlocker, Qt
from PyQt6.QtWidgets import QTabBar, QComboBox, QWidget, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QApplication, QStyle, QStyleOptionTab, QStylePainter
from common.core.tools.EpaySpecification import EpaySpecification
from common.gui.tools.json_views import JsonView


CALIBRI_12: QFont = QFont("Calibri", 12)
MS_SHELL_10: QFont = QFont("MS Shell Dlg 2", 10)


class PushButton(QPushButton):
    def __init__(self, parent: QWidget | None = None):
        super(PushButton, self).__init__(parent=parent)
        self._setup()

    def _setup(self):
        self.setFont(MS_SHELL_10)
        self.setText("Copy")
        self.setFixedSize(75, 27)


class ComboBox(QComboBox):
    spec: EpaySpecification = EpaySpecification()

    def __init__(self, parent: QWidget | None = None):
        super(ComboBox, self).__init__(parent=parent)
        self._history_tree = getattr(parent, 'json_view', None)
        self._setup()
        self._before_selection = self.currentText()
        self.activated.connect(self._record_selection)

    def _record_selection(self, index):
        after = self.currentText()
        if self._history_tree is not None and after != self._before_selection:
            from common.gui.undo_commands.ChangeMtiCommand import ChangeMtiCommand
            self._history_tree.undo_stack.push(ChangeMtiCommand(self, self._before_selection, after))
        self._before_selection = after

    def keyPressEvent(self, event):
        self._before_selection = self.currentText()
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        self._before_selection = self.currentText()
        super().wheelEvent(event)

    def _setup(self):
        self.setFont(CALIBRI_12)
        self.setEditable(False)
        self.addItems(self.spec.get_mti_list())

    def refresh_specification(self):
        previous = self.currentText().split(' ', 1)[0]
        with QSignalBlocker(self):
            self.clear()
            self.addItems(self.spec.get_mti_list())
            index = self.findText(previous, Qt.MatchFlag.MatchStartsWith) if previous else -1
            if index >= 0:
                self.setCurrentIndex(index)

    def showPopup(self):
        self._before_selection = self.currentText()
        # Show the MTI list in its final geometry without Qt's roll-down animation.
        effect = Qt.UIEffect.UI_AnimateCombo
        animated = QApplication.isEffectEnabled(effect)
        QApplication.setEffectEnabled(effect, False)
        try:
            super().showPopup()
        finally:
            QApplication.setEffectEnabled(effect, animated)



class LineEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None):
        super(LineEdit, self).__init__(parent=parent)
        self._setup()

    def _setup(self):
        self.setFont(CALIBRI_12)
        self.setReadOnly(True)


class TabBar(QTabBar):
    # Custom TabBar
    # Allows to edit tab names and signals about the tab name change

    _text_edited: pyqtSignal = pyqtSignal(int, str)  # Tab index, new text
    _edited_tab: int
    _edit: QLineEdit

    @property
    def text_edited(self):
        return self._text_edited

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)

    def paintEvent(self, event):
        if QApplication.instance().property("signalWindowColor") not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
            super().paintEvent(event)
            return
        # Native inactive-tab frames leave a dark top edge on the light base.
        # Paint flat backgrounds while keeping Qt's label and button geometry.
        painter = QStylePainter(self)
        painter.fillRect(self.rect(), self.palette().brush(QPalette.ColorRole.Window))
        for index in range(self.count()):
            if not self.isTabVisible(index):
                continue
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            is_action = not self.tabText(index) and not self.tabIcon(index).isNull()
            if index == self.currentIndex() and not is_action:
                painter.fillRect(option.rect, self.palette().brush(QPalette.ColorRole.Base))
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabLabel, option)

    def mouseDoubleClickEvent(self, event):
        tab_index = self.tabAt(event.pos())

        if tab_index == int():
            return

        self.tabBarDoubleClicked.emit(tab_index)
        self.start_rename(tab_index)

    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        # Close-button presence must not change the transaction area's origin.
        size.setHeight(max(self.fontMetrics().height(), self.iconSize().height()) + 8)
        if not self.tabText(index) and not self.tabIcon(index).isNull():
            size.setWidth(self.iconSize().width() + 20)
        return size

    def start_rename(self, tab_index):
        if tab_index == self.parent().count() - 1:
            return

        top_margin = 3
        left_margin = 6
        rect = self.tabRect(tab_index)
        self._edited_tab = tab_index
        self._edit = QLineEdit(self)
        self._edit.show()
        self._edit.move(rect.left() + left_margin, rect.top() + top_margin)
        self._edit.resize(rect.width() - 2 * left_margin, rect.height() - 2 * top_margin)
        self._edit.setText(self.tabText(tab_index))
        self._edit.selectAll()
        self._edit.setFocus()
        self._edit.editingFinished.connect(self.finish_rename)

    def finish_rename(self):
        self.text_edited.emit(self._edited_tab, self._edit.text())
        self._edit.deleteLater()


class TabWidget(QWidget):
    json_view: JsonView = None
    button: PushButton | None = None

    def __init__(self, json_view: JsonView):
        super(TabWidget, self).__init__()
        self.json_view = json_view
        self.json_view.setParent(self)
        self.setup()

    def setup(self):
        self.button = PushButton(parent=self)

        bitmap_layout = QHBoxLayout()
        bitmap_layout.addWidget(LineEdit(parent=self))
        bitmap_layout.addWidget(self.button)

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 9, 0, 0)
        if QApplication.instance().property("signalDarkTheme"):
            margins = self.layout().contentsMargins()
            self.layout().setContentsMargins(margins.left(), margins.top(), 0, margins.bottom())
        self.header = QWidget(self)
        self.header_layout = QVBoxLayout(self.header)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.addWidget(ComboBox(parent=self))
        self.header_layout.addLayout(bitmap_layout)
        self.layout().addWidget(self.header)
        self.layout().addWidget(self.json_view)
        self.json_view.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        from PyQt6.QtCore import QEvent
        if watched is self.json_view.viewport() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            viewport = self.json_view.viewport().geometry()
            right = max(0, self.json_view.width() - viewport.right() - 1)
            self.header_layout.setContentsMargins(0, 0, right, 0)
        return super().eventFilter(watched, event)
