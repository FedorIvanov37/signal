from PyQt6.QtCore import QEvent, QSettings, Qt
from PyQt6.QtWidgets import QSplitter, QVBoxLayout, QWidget, QLineEdit, QPushButton, QSizePolicy


def align_toolbar_height(layout):
    """Use a compact, uniform height for editor toolbar controls."""
    layout.setSpacing(6)
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.layout() is not None:
            align_toolbar_height(item.layout())
        widget = item.widget()
        if isinstance(widget, (QLineEdit, QPushButton)):
            widget.setFixedHeight(30)
            widget.setStyleSheet(widget.styleSheet() +
                                '\nQPushButton, QLineEdit { padding-top: 1px; padding-bottom: 1px; }')
            policy = widget.sizePolicy()
            policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
            widget.setSizePolicy(policy)


class PanelSplitter(QSplitter):
    """Resizable editor and output panels, with a toolbar below the handle."""

    def __init__(self, window, upper_layout, toolbar, output, footer, row, key):
        super().__init__(Qt.Orientation.Vertical, window)
        from common.gui.windows.main_window import APPEARANCE_SETTINGS_PATH

        self.settings = QSettings(str(APPEARANCE_SETTINGS_PATH.with_name('panel_layout.ini')),
                                  QSettings.Format.IniFormat)
        self.key = key
        self.default_ratio = 0.58
        grid = window.gridLayout
        for item in (upper_layout, toolbar, footer):
            grid.removeItem(item)
        grid.removeWidget(output)
        upper = QWidget()
        layout = QVBoxLayout(upper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(upper_layout)
        upper.setMinimumHeight(160)
        lower = QWidget()
        layout = QVBoxLayout(lower)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addLayout(toolbar)
        align_toolbar_height(toolbar)
        layout.addWidget(output, 1)
        output.setMinimumHeight(80)
        output.setMaximumHeight(16777215)
        self.addWidget(upper)
        self.addWidget(lower)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(3)
        self.setStretchFactor(0, 1)
        self.setStretchFactor(1, 1)
        self.setStyleSheet('QSplitter::handle:vertical { background: palette(window); '
                          'margin: 0; padding: 0; border: none; }')
        self.handle(1).setCursor(Qt.CursorShape.SplitVCursor)
        self.handle(1).setToolTip('Drag to resize; double-click to restore default proportions')
        self.handle(1).installEventFilter(self)
        grid.addWidget(self, row, 0)
        grid.addLayout(footer, row + 1, 0)
        for index in range(grid.rowCount()):
            grid.setRowStretch(index, int(index == row))
        try:
            ratio = float(self.settings.value(key, self.default_ratio))
        except (ValueError, TypeError):
            ratio = self.default_ratio
        if not 0 < ratio < 1:
            ratio = self.default_ratio
        self.setSizes([round(ratio * 1000), round((1 - ratio) * 1000)])
        self.splitterMoved.connect(self.save_position)

    def save_position(self, *_):
        sizes = self.sizes()
        if all(sizes):
            self.settings.setValue(self.key, sizes[0] / sum(sizes))
            self.settings.sync()

    def eventFilter(self, watched, event):
        if (watched is self.handle(1) and event.type() == QEvent.Type.MouseButtonDblClick
                and event.button() == Qt.MouseButton.LeftButton):
            available = sum(self.sizes())
            upper = round(available * self.default_ratio)
            self.setSizes([upper, available - upper])
            self.save_position()
            return True
        return super().eventFilter(watched, event)
