from pathlib import Path
import sys

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFont, QIcon, QPalette, QPainter
from PyQt6.QtWidgets import (
    QApplication, QDialog, QLabel, QPlainTextEdit, QPushButton,
    QToolButton, QWidget, QVBoxLayout, QHBoxLayout, QStyle,
)
from common.gui.data_models.Appearance import Appearance
from common.gui.decorators.window_settings import themed_logo, apply_caption_theme
from common.gui.enums.GuiFilesPath import GuiFilesPath


class TraceLineNumbers(QWidget):
    def paintEvent(self, event):
        self.parent().paint_line_numbers(event)


class TraceEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_numbers = TraceLineNumbers(self)
        self.blockCountChanged.connect(self.update_number_width)
        self.updateRequest.connect(self.update_numbers)
        self.update_number_width()

    def number_width(self):
        return 16 + self.fontMetrics().horizontalAdvance('9') * len(str(self.blockCount()))

    def update_number_width(self, *args):
        self.setViewportMargins(self.number_width(), 0, 0, 0)

    def update_numbers(self, rect, dy):
        if dy:
            self.line_numbers.scroll(0, dy)
        else:
            self.line_numbers.update(0, rect.y(), self.number_width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_number_width()
        rect = self.contentsRect()
        self.line_numbers.setGeometry(rect.left(), rect.top(), self.number_width(), rect.height())

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_numbers)
        palette = self.viewport().palette()
        painter.fillRect(event.rect(), palette.color(QPalette.ColorRole.Base))
        painter.setPen(palette.color(QPalette.ColorRole.Text))
        painter.setOpacity(0.6)
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        while block.isValid():
            top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
            if top > event.rect().bottom():
                break
            if block.isVisible():
                painter.drawText(0, top, self.line_numbers.width() - 8, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(block.blockNumber() + 1))
            block = block.next()
        painter.end()


class TraceButton(QToolButton):
    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self.icon().pixmap(self.iconSize())
        image = pixmap.toImage()
        visible = [x for x in range(image.width())
                   if any(image.pixelColor(x, y).alpha() for y in range(image.height()))]
        if visible:
            pixmap = pixmap.copy(min(visible), 0, max(visible) - min(visible) + 1, pixmap.height())
        painter.drawPixmap(0, (self.height() - pixmap.height()) // 2, pixmap)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawText(QRect(20, 0, self.width() - 20, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        painter.end()


class ErrorDialog(QDialog):
    MAX_MESSAGE_WIDTH = 500
    """A fixed upper panel with an independently expandable trace below it."""

    def __init__(self, message, trace, parent=None, recovery_label=None, fix_label=None, exit_label=None):
        super().__init__(parent)
        self.recovery_requested = False
        self.fix_requested = False
        self.exit_requested = False
        app = QApplication.instance()
        appearance = Appearance()
        if app.property('signalWindowColor') is None or app.property('signalConsoleColor') is None:
            root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]
            try:
                appearance = Appearance.load(root / 'common/data/style/appearance.json')
            except Exception:
                pass
        window_color = app.property('signalWindowColor') or appearance.windowColor
        console_color = app.property('signalConsoleColor') or appearance.consoleColor
        app.setProperty('signalWindowColor', window_color)
        app.setProperty('signalDarkTheme', window_color not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'))
        from common.gui.decorators.window_settings import set_application_identity
        set_application_identity()
        base = QColor(window_color)
        dark = window_color not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5')
        background = base.darker(125).name() if dark else window_color
        foreground = '#E2E8F0' if dark else '#202020'
        button_color = ('#242424' if window_color == '#000000' else base.lighter(125).name())
        self.setWindowTitle('Signal | Error')
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setFont(QFont('Calibri', 12))
        self.setWindowIcon(QIcon(themed_logo(GuiFilesPath.MAIN_LOGO)))
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(background))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(foreground))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            f'QDialog {{ background: {background}; }}'
            f'QLabel, QToolButton {{ color: {foreground}; background: transparent; }}'
            f'QPushButton {{ background: {button_color}; color: {foreground}; '
            'border: 1px solid #8090A0; border-radius: 3px; padding: 4px 12px; }'
        )
        self.upper = QWidget(self)
        layout = QVBoxLayout(self.upper)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(16)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.logo = QLabel(self.upper)
        self.logo.setFixedSize(30, 30)
        self.logo.setProperty('signalLogoPath', GuiFilesPath.MAIN_LOGO)
        self.logo.setProperty('signalLogoSize', self.logo.size())
        from common.gui.decorators.window_settings import enable_logo_click
        enable_logo_click(self.logo)
        self.logo.setPixmap(themed_logo(GuiFilesPath.MAIN_LOGO).scaled(
            30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.message = QLabel(message, self.upper)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.message.setWordWrap(True)
        row.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.message, 1)
        layout.addLayout(row)
        buttons = QHBoxLayout()
        self.ok = QPushButton(exit_label or 'OK', self.upper)
        self.ok.clicked.connect(self._request_exit if exit_label else self.accept)
        self.ok.setDefault(True)
        self.ok.setFixedWidth(64)
        self.trace_button = TraceButton(self.upper)
        self.trace_button.setText('Trace')
        self._trace_icons = []
        for arrow in (QStyle.StandardPixmap.SP_ArrowRight, QStyle.StandardPixmap.SP_ArrowDown):
            pixmap = self.style().standardIcon(arrow).pixmap(14, 14)
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), QColor(foreground))
            painter.end()
            self._trace_icons.append(QIcon(pixmap))
        self.trace_button.setIcon(self._trace_icons[0])
        self.trace_button.setIconSize(pixmap.size())
        self.trace_button.setCheckable(True)
        self.trace_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.trace_button.setStyleSheet('QToolButton { border: none; font: 12pt Calibri; padding: 2px 0; }')
        buttons.addSpacing(self.logo.width() + row.spacing())
        buttons.addWidget(self.trace_button, 0, Qt.AlignmentFlag.AlignVCenter)
        buttons.addStretch()
        if fix_label:
            self.fix_button = QPushButton(fix_label, self.upper)
            self.fix_button.clicked.connect(self._request_fix)
            buttons.addWidget(self.fix_button)
        if recovery_label:
            self.recovery_button = QPushButton(recovery_label, self.upper)
            self.recovery_button.clicked.connect(self._request_recovery)
            buttons.addWidget(self.recovery_button)
        buttons.addWidget(self.ok)
        layout.addLayout(buttons)
        self.trace_view = TraceEditor(self)
        self.trace_view.setReadOnly(True)
        self.trace_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.trace_view.setPlainText(trace)
        trace_foreground = '#202020' if console_color in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else '#E2E8F0'
        self.trace_view.setStyleSheet(
            f'QPlainTextEdit {{ background: {console_color}; color: {trace_foreground}; '
            'border: none; font: 10pt Consolas; }'
            f'QAbstractScrollArea::corner {{ background: {background}; border: none; }}')
        self.trace_view.hide()
        self.ensurePolished()
        self.message.ensurePolished()
        metrics = self.message.fontMetrics()
        longest_line = max((metrics.horizontalAdvance(line) for line in message.splitlines()), default=0)
        width = min(self.MAX_MESSAGE_WIDTH + 74, max(420, longest_line + 74))
        # Fit the longest rendered line, rather than leaving unused space after it.
        text_bounds = metrics.boundingRect(
            QRect(0, 0, width - 74, 10000), Qt.TextFlag.TextWordWrap, message)
        width = min(self.MAX_MESSAGE_WIDTH + 74, max(300, text_bounds.width() + 74))
        width = max(width, buttons.sizeHint().width() + layout.contentsMargins().left() + layout.contentsMargins().right())
        self.upper.resize(width, 200)
        self._collapsed_height = max(108, layout.totalHeightForWidth(width))
        self.upper.setFixedSize(width, self._collapsed_height)
        self.setFixedSize(width, self._collapsed_height)
        self.trace_view.setGeometry(12, self._collapsed_height, width - 24, 170)
        # Polish, lay out and paint the editor before the first expansion.
        self.trace_view.ensurePolished()
        self.trace_view.document().documentLayout().documentSize()
        self.trace_view.grab()
        self.trace_button.toggled.connect(self._toggle_trace)

    def _request_exit(self):
        self.exit_requested = True
        self.accept()

    def _request_fix(self):
        self.fix_requested = True
        self.accept()

    def _request_recovery(self):
        self.recovery_requested = True
        self.accept()

    def _toggle_trace(self, expanded):
        position = self.pos()
        self.trace_button.setIcon(self._trace_icons[int(expanded)])
        self.setUpdatesEnabled(False)
        try:
            self.trace_view.setVisible(expanded)
            self.setFixedHeight(self._collapsed_height + (182 if expanded else 0))
            self.move(position)
        finally:
            self.setUpdatesEnabled(True)
        self.repaint()

    def showEvent(self, event):
        super().showEvent(event)
        apply_caption_theme(self)
