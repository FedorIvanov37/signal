from common.gui.data_models.Appearance import THEME_PRESETS
from sys import exit
import sys
from pathlib import Path
from PyQt6 import sip
from PyQt6.QtNetwork import QTcpSocket
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QEvent
from common.gui.data_models.Appearance import Appearance
from PyQt6.QtWidgets import QMainWindow, QMenu, QPushButton, QSizePolicy, QApplication, QWidgetAction, QSplitter, QWidget, QVBoxLayout
from common.core.enums.MessageLength import MessageLength
from common.core.enums.DataFormats import OutputFilesFormat
from common.core.enums import KeepAlive
from common.core.enums.TextConstants import TextConstants
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.data_models.Config import Config
from common.gui.forms.mainwindow import Ui_MainWindow
from common.gui.decorators.window_settings import set_window_icon
from common.gui.enums import ButtonActions, MainFieldSpec as FieldsSpec
from common.gui.enums.KeySequences import KeySequences
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.gui.enums.ApiMode import ApiModes, ApiModeNames
from common.gui.enums.Buttons import Buttons
from common.gui.enums.Colors import Colors
from common.gui.enums.ConnectionStatus import ConnectionStatus
from common.gui.enums.ConnectionStatus import ConnectionIcon
from common.gui.tools.tab_view.TabView import TabView
from common.gui.tools.json_views.TreeView import TreeView
from PyQt6.QtGui import QPalette, QColor, QKeyEvent
from common.gui.enums.ToolBarElements import ToolBarElements
from common.gui.toolkit.create_gui_elements import create_button, create_vertical_line


APPEARANCE_SETTINGS_PATH = (
    Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[3]
) / "common" / "data" / "style" / "appearance.json"

from PyQt6.QtGui import (
    QCloseEvent,
    QKeySequence,
    QShortcut,
    QPixmap,
    QIcon,
    QActionGroup,
    QAction,
)


"""
MainWindow is a general SVTerminal GUI

It runs as an independent application, interacts with the backend using pyqtSignal 

Can be run separately from the backend, but does nothing in this case. 
 
The goals of MainWindow are interaction with the GUI user, user input data collection, and data processing requests 
using pyqtSignal. Better to not force it to process the data, validate values, and so on
"""


class MainWindow(Ui_MainWindow, QMainWindow):

    # Data processing request signals. Some of them send string modifiers as a hint on how to process the data

    window_close: pyqtSignal = pyqtSignal()
    print: pyqtSignal = pyqtSignal(str)
    save: pyqtSignal = pyqtSignal(str, str)
    reverse: pyqtSignal = pyqtSignal(str)
    about: pyqtSignal = pyqtSignal()
    field_changed: pyqtSignal = pyqtSignal()
    field_removed: pyqtSignal = pyqtSignal()
    field_added: pyqtSignal = pyqtSignal()
    clear_log: pyqtSignal = pyqtSignal()
    settings: pyqtSignal = pyqtSignal()
    specification: pyqtSignal = pyqtSignal()
    echo_test: pyqtSignal = pyqtSignal()
    clear: pyqtSignal = pyqtSignal()
    copy_log: pyqtSignal = pyqtSignal()
    copy_bitmap: pyqtSignal = pyqtSignal()
    reconnect: pyqtSignal = pyqtSignal()
    parse_file: pyqtSignal = pyqtSignal()
    hotkeys: pyqtSignal = pyqtSignal()
    send: pyqtSignal = pyqtSignal()
    reset: pyqtSignal = pyqtSignal(bool)
    keep_alive: pyqtSignal = pyqtSignal(str)
    repeat: pyqtSignal = pyqtSignal(str)
    parse_complex_field: pyqtSignal = pyqtSignal()
    validate_message: pyqtSignal = pyqtSignal(bool)
    spec: EpaySpecification = EpaySpecification()
    api_mode_changed: pyqtSignal = pyqtSignal(ApiModes)
    exit: pyqtSignal = pyqtSignal(int)
    show_document: pyqtSignal = pyqtSignal()
    show_openapi_doc: pyqtSignal = pyqtSignal()
    show_license: pyqtSignal = pyqtSignal()
    disable_item: pyqtSignal = pyqtSignal()
    enable_item: pyqtSignal = pyqtSignal()
    enable_all_items: pyqtSignal = pyqtSignal()
    files_dropped: pyqtSignal = pyqtSignal(list)
    text_dropped: pyqtSignal = pyqtSignal(str)
    undo: pyqtSignal = pyqtSignal()
    redo: pyqtSignal = pyqtSignal()
    repeat_actions: dict = dict()
    _config: Config

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config
        self.tab_view.config = config

    @property
    def json_view(self):
        return self._tab_view.json_view

    @property
    def tab_view(self):
        return self._tab_view

    @property
    def log_browser(self):
        return self.LogArea

    def __init__(self, config: Config):
        super().__init__()
        self._config = config
        self._tab_view: TabView = TabView(self.config)
        self._setup()

    @set_window_icon
    def _setup(self) -> None:
        self.setupUi(self)
        self.LogArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._add_control_buttons()
        self.set_repeat_actions()
        self._connect_all()
        self.setWindowTitle(TextConstants.SYSTEM_NAME.capitalize())
        from common.gui.decorators.window_settings import set_application_identity
        set_application_identity()
        self.ButtonSend.setFocus()
        self.set_connection_status(QTcpSocket.SocketState.UnconnectedState)
        self.ButtonsLayout.setAlignment(Qt.AlignmentFlag(0))
        self.set_buttons_menu()
        self.TabViewLayout.addWidget(self._tab_view)
        self.process_api_mode_change(ApiModes.NOT_RUN)
        self._apply_dark_theme()
        self._setup_splitter()

    def _setup_splitter(self):
        self.gridLayout.removeItem(self.TabViewLayout)
        self.gridLayout.removeItem(self.horizontalLayout)
        self.gridLayout.removeWidget(self.LogArea)
        transaction_pane = QWidget()
        layout = QVBoxLayout(transaction_pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.TabViewLayout, 1)
        transaction_pane.setMinimumHeight(160)
        console_pane = QWidget()
        console_layout = QVBoxLayout(console_pane)
        # The splitter itself provides the top gap above the toolbar.
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(3)
        console_layout.addLayout(self.horizontalLayout)
        from common.gui.toolkit.panel_splitter import align_toolbar_height
        align_toolbar_height(self.horizontalLayout)
        console_layout.addWidget(self.LogArea, 1)
        self.LogArea.setMinimumHeight(80)
        self.main_splitter = QSplitter(Qt.Orientation.Vertical, self.centralwidget)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(3)
        self.main_splitter.addWidget(transaction_pane)
        self.main_splitter.addWidget(console_pane)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.handle(1).setCursor(Qt.CursorShape.SplitVCursor)
        self.main_splitter.handle(1).setToolTip('Drag to resize; double-click to restore default proportions')
        self.main_splitter.handle(1).installEventFilter(self)
        self.main_splitter.setStyleSheet(
            'QSplitter::handle:vertical { background: palette(window); margin: 0; padding: 0; border: none; }')
        self.gridLayout.removeItem(self.ButtonsLayout)
        self.gridLayout.addWidget(self.main_splitter, 1, 0)
        self.gridLayout.addLayout(self.ButtonsLayout, 2, 0)
        self.gridLayout.setRowStretch(0, 0)
        self.gridLayout.setRowStretch(1, 1)
        self.gridLayout.setRowStretch(2, 0)
        ratio = self._appearance_settings.transactionPaneRatio
        self.main_splitter.setSizes([round(ratio * 1000), round((1 - ratio) * 1000)])
        self._splitter_save_timer = QTimer(self)
        self._splitter_save_timer.setSingleShot(True)
        self._splitter_save_timer.setInterval(250)
        self._splitter_dirty = False
        self._splitter_save_timer.timeout.connect(self._save_splitter_position)
        self.main_splitter.splitterMoved.connect(self._splitter_moved)
        QApplication.instance().aboutToQuit.connect(self._save_splitter_position)

    def eventFilter(self, watched, event):
        event_type = event.type()
        if event_type not in (QEvent.Type.Show, QEvent.Type.MouseMove, QEvent.Type.Leave,
                              QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                              QEvent.Type.MouseButtonDblClick):
            return False
        if isinstance(watched, QMenu) and event.type() == QEvent.Type.Show:
            previous = None
            for action in watched.actions():
                if previous is not None and not previous.isSeparator() and not action.isSeparator():
                    watched.insertSeparator(action)
                previous = action
        for button_name in ('ButtonTools',):
            button = getattr(self, button_name, None)
            if button is None or sip.isdeleted(button):
                continue
            menu = button.menu()
            if menu is None or sip.isdeleted(menu):
                continue
            if watched is menu and event.type() in (QEvent.Type.MouseMove, QEvent.Type.Leave):
                return True
            if (event.type() == QEvent.Type.MouseButtonRelease
                    and getattr(self, '_submenu_category_clicked', False)):
                self._submenu_category_clicked = False
                return True
            if (menu.isVisible() and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
                    and event.button() == Qt.MouseButton.LeftButton):
                position = event.globalPosition().toPoint()
                on_button = button.rect().contains(button.mapFromGlobal(position))
                local = menu.mapFromGlobal(position)
                action = menu.actionAt(local) if menu.rect().contains(local) else None
                if on_button or (action is not None and action.menu() is not None):
                    was_visible = action.menu().isVisible() if action is not None else False
                    for category in menu.actions():
                        if category.menu() is not None:
                            category.menu().hide()
                    menu.setActiveAction(None)
                    if on_button:
                        menu.hide()
                        button.setDown(False)
                    elif not was_visible:
                        menu.setActiveAction(action)
                        # Open as a native submenu so Qt restores the parent's
                        # mouse grab when it closes, rather than a separate popup.
                        QApplication.sendEvent(menu, QKeyEvent(
                            QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier))
                    self._submenu_category_clicked = True
                    return True
        if (event_type == QEvent.Type.MouseButtonDblClick
                and hasattr(self, 'main_splitter') and not sip.isdeleted(self.main_splitter)
                and watched is self.main_splitter.handle(1)
                and event.button() == Qt.MouseButton.LeftButton):
            available = sum(self.main_splitter.sizes())
            ratio = Appearance.model_fields['transactionPaneRatio'].default
            upper = round(available * ratio)
            self.main_splitter.setSizes([upper, available - upper])
            self._splitter_moved(upper, 1)
            return True
        return super().eventFilter(watched, event)

    def _splitter_moved(self, position, index):
        sizes = self.main_splitter.sizes()
        if all(sizes):
            self._appearance_settings.transactionPaneRatio = sizes[0] / sum(sizes)
            self._splitter_dirty = True
            self._splitter_save_timer.start()

    def _save_splitter_position(self):
        if not self._splitter_dirty:
            return
        if self._splitter_save_timer.isActive():
            self._splitter_save_timer.stop()
        self._appearance_settings.save(APPEARANCE_SETTINGS_PATH)
        self._splitter_dirty = False

    def _theme_stylesheet(self):
        return getattr(self, '_pending_theme_style', QApplication.instance().styleSheet())

    def _set_theme_stylesheet(self, style):
        if hasattr(self, '_pending_theme_style'):
            self._pending_theme_style = style
        else:
            QApplication.instance().setStyleSheet(style)

    def _persist_theme_color(self, field, color):
        setattr(self._appearance_settings, field, color)
        candidate = self.config.model_copy(deep=True)
        setattr(candidate.theme, field, color)
        manager = getattr(self.config, "manager", None)
        if manager is not None:
            manager.replace(candidate)
        else:
            from common.core.tools.ConfigStore import save_config
            save_config(candidate)
            self._config = candidate

    def apply_theme_colors(self, colors):
        from time import perf_counter
        from loguru import logger
        app = QApplication.instance()
        colors = {key: color for key, color in colors.items()
                  if app.property(f'signal{key}Color') != color}
        if not colors:
            return
        started = perf_counter()
        self._pending_theme_style = app.styleSheet()
        try:
            # Publish all target colors before the dependent style rules are built.
            for key, color in colors.items():
                app.setProperty(f'signal{key}Color', color)
                setattr(self._appearance_settings, {'Tree': 'treeColor', 'Window': 'windowColor',
                                                   'Console': 'consoleColor'}[key], color)
            if 'Window' in colors:
                self._apply_dark_theme(colors['Window'])
            elif 'Console' in colors:
                self._set_console_color(colors['Console'])
            else:
                self._set_tree_color(colors['Tree'])
            style = self._pending_theme_style
        finally:
            del self._pending_theme_style
        app.setStyleSheet(style)
        from common.gui.decorators.window_settings import refresh_window_logos
        refresh_window_logos()
        for widget in app.allWidgets():
            if hasattr(widget, '_update_checkbox_text_colors'):
                widget._update_checkbox_text_colors()
        logger.debug('Theme applied in {:.1f} ms; changed={}', (perf_counter() - started) * 1000, ','.join(colors))

    def _apply_dark_theme(self, color=None, *, persist=False):
        app = QApplication.instance()
        if not hasattr(app, "_signal_default_palette"):
            app._signal_default_palette = QPalette(app.palette())
        colors = [action.data() for action in self.window_colors.actions()]
        color = color or self._appearance_settings.windowColor
        if color not in colors:
            color = "#243447"
        self.setProperty("signalDarkTheme", color not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'))
        app.setProperty("signalDarkTheme", color not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'))
        self.setProperty("signalWindowColor", color)
        app.setProperty("signalWindowColor", color)
        palette = self.palette()
        for role, palette_color in (
            (QPalette.ColorRole.Window, "#191F28"),
            (QPalette.ColorRole.WindowText, "#E2E8F0"),
            (QPalette.ColorRole.Text, "#E2E8F0"),
            (QPalette.ColorRole.ButtonText, "#E2E8F0"),
            (QPalette.ColorRole.Base, "#202833"),
            (QPalette.ColorRole.AlternateBase, "#263140"),
            (QPalette.ColorRole.Button, "#293442"),
            (QPalette.ColorRole.PlaceholderText, "#94A3B8"),
            (QPalette.ColorRole.Link, "#91C5FF"),
            (QPalette.ColorRole.LinkVisited, "#C2ADFF"),
        ):
            palette.setColor(role, QColor(palette_color))
        self.setPalette(palette)
        stylesheet = """
            QMainWindow, QDialog, QMessageBox, QStatusBar { background: #191F28; }
            QGroupBox { color: #CDD5DF; border: none; margin-top: 1.4em; }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                left: 9px; padding: 0;
            }
            QCheckBox::indicator:unchecked {
                background-color: #B4BCC5; border: 1px solid #8793A1;
                border-radius: 2px;
            }
            QCheckBox::indicator:unchecked:hover { background-color: #C3CBD3; }
            QCheckBox::indicator:unchecked:disabled { background-color: #78838F; }
            QSpinBox, QDoubleSpinBox, QDateTimeEdit, QTextEdit, QPlainTextEdit {
                background: #202833; color: #CDD5DF; border: none;
            }
            QLabel { color: #E2E8F0; background: transparent; }
            QLineEdit, QComboBox {
                background: #202833; color: #E2E8F0; border: 1px solid #465468;
                border-radius: 3px; padding: 3px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #7798BD; }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox QAbstractItemView,
            QTableView { selection-background-color: palette(highlight); selection-color: palette(highlighted-text); }
            QTreeWidget, QTableView {
                background: #202833; alternate-background-color: #263140;
                color: #E2E8F0; border: 1px solid #465468;
                selection-background-color: palette(highlight); selection-color: #FFFFFF;
            }
            QHeaderView, QHeaderView::section {
                background: #293442; color: #B9C8DA;
                border: none; padding: 4px;
            }
            QPushButton, QToolButton {
                background: #293442; color: #E2E8F0; border: 1px solid #465468;
                border-radius: 3px; padding: 4px 8px;
            }
            QPushButton:hover, QToolButton:hover { background: #37465A; border-color: #7798BD; }
            QPushButton:pressed, QToolButton:pressed { background: #202833; }
            QPushButton:disabled, QToolButton:disabled { color: #788596; background: #222A35; }
            QTabWidget::pane { border: 1px solid #465468; background: #191F28; }
            QTabBar::tab {
                background: #202833; color: #A7B7CA; border: 1px solid #465468;
                padding: 5px 10px;
            }
            QTabBar::tab:selected { background: #344358; color: #FFFFFF; }
            QMenu { background: #202833; color: #E2E8F0; border: 1px solid #465468; }
            QMenu::item { padding: 5px 22px; }
            QMenu::item:selected { background: palette(highlight); color: palette(highlighted-text); }
            QMenu::item:disabled { color: #788596; }
            QMenu::separator { height: 1px; background: #465468; margin: 4px 8px; }
            QComboBox QAbstractItemView {
                background: #202833; color: #CDD5DF; border: none;
                selection-background-color: palette(highlight); selection-color: palette(highlighted-text);
            }
            QScrollBar:vertical { background: #191F28; width: 14px; margin: 0; }
            QScrollBar:horizontal { background: #191F28; height: 14px; margin: 0; }
            QScrollBar::handle { background: #53647A; border-radius: 4px; }
            QScrollBar::handle:vertical { min-height: 20px; margin: 0 4px; }
            QScrollBar::handle:horizontal { min-width: 20px; margin: 4px 0; }
            QScrollBar::handle:hover { background: #7188A4; }
            QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
            QScrollBar::add-page, QScrollBar::sub-page { background: none; }
            QLabel, QLineEdit, QComboBox, QTreeWidget, QTableView, QHeaderView::section,
            QPushButton, QToolButton, QTabBar::tab, QMenu { color: #CDD5DF; }
            QLineEdit, QComboBox, QTreeWidget, QTableView, QTextEdit, QPlainTextEdit,
            QPushButton, QToolButton, QTabWidget::pane, QTabBar::tab, QMenu {
                border: none;
            }
            QFrame[frameShape="4"], QFrame[frameShape="5"] {
                border: none; background: transparent;
            }
        """
        base = QColor(color)
        shades = {
            "#191F28": base.darker(125).name(),
            "#202833": base.name(),
            "#263140": base.lighter(115).name(),
            "#293442": base.lighter(125).name(),
            "#344358": base.lighter(145).name(),
            "#37465A": base.lighter(155).name(),
            "#222A35": base.darker(110).name(),
            "#465468": base.lighter(175).name(),
            "#53647A": base.lighter(200).name(),
            "#7188A4": base.lighter(240).name(),
        }
        preset = THEME_PRESETS.get(color)
        if preset:
            shades.update({'#191F28': color, '#202833': color,
                           '#263140': preset['surface'], '#293442': preset['surface'],
                           '#344358': preset['selection'], '#37465A': preset['hover'],
                           '#222A35': color, '#465468': preset['hover'],
                           '#53647A': preset['selection'], '#7188A4': preset['text']})
            for text_color in ('#E2E8F0', '#CDD5DF', '#FFFFFF'):
                stylesheet = stylesheet.replace(text_color, preset['text'])
            for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
                palette.setColor(role, QColor(preset['text']))
        import re
        if color == "#000000":
            shades.update({
                "#191F28": "#000000", "#202833": "#111111", "#263140": "#1B1B1B",
                "#293442": "#242424", "#344358": "#303030", "#37465A": "#383838",
                "#222A35": "#181818", "#465468": "#484848", "#53647A": "#606060",
                "#7188A4": "#888888",
            })
        stylesheet = re.sub("|".join(shades), lambda match: shades[match.group()], stylesheet)
        palette.setColor(QPalette.ColorRole.Window, QColor(shades["#191F28"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(shades["#293442"]))
        palette.setColor(QPalette.ColorRole.Midlight, QColor(shades["#37465A"]))
        palette.setColor(QPalette.ColorRole.Mid, QColor(shades["#202833"]))
        if color in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
            stylesheet = """
                QPushButton, QToolButton {
                    border: 1px solid #929BA5; border-radius: 3px; padding: 4px 8px;
                }
                QPushButton:hover, QToolButton:hover { border-color: #0078D7; }
                QPushButton::menu-indicator { image: url(common/data/style/menu_down_light.svg); }
                QComboBox::down-arrow { image: url(common/data/style/combo_chevron_light.svg); }
                QScrollBar:vertical { background: #F0F0F0; width: 14px; margin: 0; }
                QScrollBar:horizontal { background: #F0F0F0; height: 14px; margin: 0; }
                QScrollBar::handle { background: #A0A0A0; border-radius: 4px; }
                QScrollBar::handle:vertical { min-height: 20px; margin: 0 4px; }
                QScrollBar::handle:horizontal { min-width: 20px; margin: 4px 0; }
                QScrollBar::handle:hover { background: #707070; }
                QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
                QScrollBar::add-page, QScrollBar::sub-page { background: none; }
                QTextEdit#LogArea, QPlainTextEdit#LogArea { border: none; }
                QTabWidget::pane { border: none; }
            """
            stylesheet = stylesheet.replace("#F0F0F0", color)
            palette = QPalette(app._signal_default_palette)
            palette.setColor(QPalette.ColorRole.Window, QColor(color))
            palette.setColor(QPalette.ColorRole.Button, QColor(color))
            if preset:
                palette.setColor(QPalette.ColorRole.Button, QColor(preset['surface']))
                palette.setColor(QPalette.ColorRole.Midlight, QColor(preset['hover']))
                for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
                    palette.setColor(role, QColor(preset['text']))
        stylesheet += '\nQComboBox { padding-right: 22px; }'
        previous = app.property("signalWindowStyle") or ""
        current = self._theme_stylesheet()
        from common.gui.toolkit.create_gui_elements import CONTROL_FONT_STYLE
        if CONTROL_FONT_STYLE not in current:
            current += CONTROL_FONT_STYLE
        if previous:
            current = current.replace(previous, "")
        app.setProperty("signalWindowStyle", stylesheet)
        self.setStyleSheet("")
        self.setPalette(QPalette())
        app.setPalette(palette)
        self._set_theme_stylesheet(current + stylesheet)
        from common.gui.decorators.window_settings import refresh_window_logos
        refresh_window_logos()
        self._tab_view.update_plus_icon()
        for index in range(self._tab_view.count()):
            page = self._tab_view.widget(index)
            if page.layout() is not None:
                margins = page.layout().contentsMargins()
                page.layout().setContentsMargins(0, margins.top(),
                                                0, 0)
        for action in self.window_colors.actions():
            action.setChecked(action.data() == color)
            border = "2px solid #0078D7" if action.isChecked() else "1px solid #8090A0"
            action.defaultWidget().setStyleSheet(
                f"QPushButton {{ background-color: {action.data()}; border: {border}; border-radius: 3px; }}"
                "QPushButton:hover { border: 2px solid #70B7FF; }"
            )
        if persist:
            self._persist_theme_color("windowColor", color)
        self.LogArea.ensurePolished()
        self.LogArea.verticalScrollBar().ensurePolished()
        spacing = self.horizontalLayout.itemAt(self.horizontalLayout.count() - 1).spacerItem()
        spacing.changeSize(
            self.LogArea.verticalScrollBar().sizeHint().width() + self.LogArea.frameWidth(),
            0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum,
        )
        self.horizontalLayout.invalidate()
        self.ButtonsLayout.itemAt(self.ButtonsLayout.count() - 1).spacerItem().changeSize(
            self.LogArea.verticalScrollBar().sizeHint().width() + self.LogArea.frameWidth(),
            0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.ButtonsLayout.invalidate()
        self._set_console_color(QApplication.instance().property("signalConsoleColor"))
        self.ButtonSettings.ensurePolished()
        self.ButtonSettings.refresh_icon()
        self.json_view._update_checkbox_text_colors()

    def _set_console_color(self, color, *, persist=False):
        app = QApplication.instance()
        window_color = self.property("signalWindowColor") or self._appearance_settings.windowColor
        selection = QColor(Colors.SELECTION_BLUE if window_color.upper() in ("#012E4F", "#011627", "#F0F0F0", "#8996A3") else window_color)
        hue, saturation, lightness, alpha = selection.getHslF()
        if window_color.upper() not in ("#012E4F", "#011627", "#F0F0F0", "#8996A3"):
            selection.setHslF(hue, saturation, min(max(lightness + 0.07, 0.30), 1.0), alpha)
        if window_color.upper() == "#3B202B":
            selection = QColor("#98506C")
        if window_color in THEME_PRESETS:
            selection = QColor(THEME_PRESETS[window_color]['selection'])
        selection_color = selection.name()
        checkbox = QColor(Colors.SELECTION_BLUE if window_color in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else window_color)
        if window_color not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
            hue, saturation, lightness, alpha = checkbox.getHslF()
            checkbox.setHslF(hue, saturation * 0.7, 0.42, alpha)
        checkbox_color = checkbox.name()
        console_selection = QColor("#2D78B8") if color.upper() == "#012E4F" else QColor(color).lighter(165)
        if color.upper() == "#011627":
            console_selection = QColor(Colors.SELECTION_BLUE)
        elif color.upper() in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
            console_selection = QColor("#B7C8E0")
        elif color.upper() == "#000000":
            console_selection = QColor("#4A4A4A")
        console_preset = THEME_PRESETS.get(color, {})
        if console_preset:
            console_selection = QColor(console_preset['selection'])
        console_foreground = console_preset.get('text', '#243447' if color in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else '#D6DEEB')
        console_selection_color = console_selection.name()
        previous = app.property("signalConsoleStyle") or ""
        stylesheet = self._theme_stylesheet()
        if previous:
            stylesheet = stylesheet.replace(previous, "")
        rule = (
            f"\nQTextEdit#LogArea, QPlainTextEdit#LogArea {{ background-color: {color}; color: {console_foreground}; selection-background-color: {console_selection_color}; selection-color: {'#FFFFFF' if console_preset else ('#243447' if color in ('#F0F0F0', '#8996A3') else '#FFFFFF')}; font-weight: {'bold' if color in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else 'normal'}; }}"
            "QTextEdit#LogArea::corner, QPlainTextEdit#LogArea::corner { background-color: palette(window); }"
            f"QTreeWidget QLineEdit, QTableView QLineEdit {{ selection-background-color: {selection_color}; selection-color: #FFFFFF; }}"
            f"QLineEdit, QTextEdit, QPlainTextEdit, QComboBox QAbstractItemView, QTableView {{ selection-background-color: {selection_color}; selection-color: #FFFFFF; }}"
            "QCheckBox::indicator, QGroupBox::indicator, QAbstractItemView::indicator {"
            " width: 12px; height: 12px; border: 1px solid #8793A1; border-radius: 2px; }"
            "QCheckBox::indicator:checked, QGroupBox::indicator:checked, "
            "QAbstractItemView::indicator:checked {"
            f" background-color: {checkbox_color}; border: 1px solid {checkbox_color};"
            f' border-radius: 2px; image: url("{str(GuiFilesPath.CHECK_WHITE).replace(chr(92), "/")}"); }}'
            "QCheckBox::indicator:indeterminate, QAbstractItemView::indicator:indeterminate {"
            f" background-color: {checkbox_color}; border: 1px solid {checkbox_color};"
            f' border-radius: 2px; image: url("{str(GuiFilesPath.CHECK_PARTIAL_WHITE).replace(chr(92), "/")}"); }}'
        )
        app.setProperty("signalConsoleStyle", rule)
        app.setProperty("signalConsoleColor", color)
        app.setProperty("signalSelectionColor", str(selection_color))
        palette = app.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(selection_color))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        app.setPalette(palette)
        self._set_theme_stylesheet(stylesheet + rule)
        from common.gui.tools.WirelessHandler import WirelessHandler
        for widget in app.allWidgets():
            if widget.objectName() == "LogArea" and hasattr(widget, "toHtml"):
                light = color.upper() in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5')
                if bool(widget.property("signalLightConsole")) != light:
                    scroll = widget.verticalScrollBar().value()
                    widget.setHtml(WirelessHandler.console_markup(widget.toHtml(), light))
                    widget.verticalScrollBar().setValue(scroll)
                    widget.setProperty("signalLightConsole", light)
            if isinstance(widget, TreeView):
                palette = widget.palette()
                palette.setColor(QPalette.ColorRole.Highlight, QColor(selection_color))
                widget.setPalette(palette)
                from common.gui.tools.json_views.JsonView import JsonView
                if isinstance(widget, JsonView):
                    widget._update_checkbox_text_colors()
                widget.viewport().update()
        for action in self.console_colors.actions():
            action.setChecked(action.data() == color)
            border = "2px solid #0078D7" if action.data() == color else "1px solid #8090A0"
            action.defaultWidget().setStyleSheet(
                f"QPushButton {{ background-color: {action.data()}; border: {border}; border-radius: 3px; }}"
                "QPushButton:hover { border: 2px solid #70B7FF; }"
            )
        if persist:
            self._persist_theme_color("consoleColor", color)
        for window in app.topLevelWidgets():
            if hasattr(window, '_print_highlighter'):
                window._print_highlighter.rehighlight()
        if hasattr(self, 'tree_colors'):
            self._set_tree_color(app.property('signalTreeColor') or self._appearance_settings.treeColor)

    def _set_tree_color(self, color, *, persist=False):
        app = QApplication.instance()
        base = QColor(color)
        light = color in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5')
        foreground = '#000000' if light else '#E2E8F0'
        background = '#FFFFFF' if color == '#F0F0F0' else color
        alternate = (Colors.LIGHT_GREY if color == '#F0F0F0' else base.lighter(110).name()) if light else ('#1B1B1B' if color == '#000000' else base.lighter(115).name())
        header = background if light else ('#242424' if color == '#000000' else base.lighter(125).name())
        selection = Colors.SELECTION_BLUE if color in ('#012E4F', '#011627', '#F0F0F0', '#8996A3') else ('#4A4A4A' if color == '#000000' else base.lighter(180).name())
        preset = THEME_PRESETS.get(color, {})
        foreground = preset.get('text', foreground)
        alternate = preset.get('surface', alternate)
        header = preset.get('surface', header)
        selection = preset.get('selection', selection)
        checkbox = QColor(Colors.SELECTION_BLUE) if light else QColor(base)
        if not light:
            hue, saturation, lightness, alpha = checkbox.getHslF()
            checkbox.setHslF(hue, saturation * 0.7, max(0.48, lightness + 0.20), alpha)
        checkbox_color = checkbox.name()
        rule = (
            f'\nQTreeView {{ background: {background}; alternate-background-color: {alternate}; color: {foreground}; border: none; '
            f'selection-background-color: {selection}; selection-color: #FFFFFF; }}'
            f'QTreeView QHeaderView, QTreeView QHeaderView::section {{ background: {header}; color: {foreground}; border: none; }}'
            f'QTreeView QHeaderView QToolButton {{ background: {header}; color: {foreground}; border: none; }}'
            f'QTreeView QLineEdit {{ background: {background}; color: {foreground}; selection-background-color: {selection}; }}'
            'QTreeView::indicator:checked, QTreeView QCheckBox::indicator:checked, '
            'QTreeView::indicator:indeterminate, QTreeView QCheckBox::indicator:indeterminate {'
            f' background-color: {checkbox_color}; border-color: {checkbox_color}; }}'
            'QTreeView::indicator:unchecked, QTreeView QCheckBox::indicator:unchecked {'
            f' background-color: {background}; border-color: {foreground}; }}'
            'QTreeView::indicator:unchecked:hover, QTreeView QCheckBox::indicator:unchecked:hover {'
            f' background-color: {alternate}; border: 1px solid {foreground}; }}'
        )
        previous = app.property('signalTreeStyle') or ''
        self._set_theme_stylesheet(self._theme_stylesheet().replace(previous, '') + rule)
        app.setProperty('signalTreeStyle', rule)
        app.setProperty('signalTreeColor', color)
        app.setProperty('signalSelectionColor', str(selection))
        for widget in app.allWidgets():
            if isinstance(widget, TreeView):
                palette = widget.palette()
                palette.setColor(QPalette.ColorRole.Highlight, QColor(selection))
                widget.setPalette(palette)
                widget.viewport().update()
                if hasattr(widget, '_update_checkbox_text_colors'):
                    widget._update_checkbox_text_colors()
        for action in self.tree_colors.actions():
            action.setChecked(action.data() == color)
            border = '2px solid #0078D7' if action.isChecked() else '1px solid #8090A0'
            action.defaultWidget().setStyleSheet(
                f'QPushButton {{ background-color: {action.data()}; border: {border}; border-radius: 3px; }}')
        if persist:
            self._persist_theme_color("treeColor", color)

    def _add_control_buttons(self) -> None:

        # Create general control buttons

        self.ButtonSend: QPushButton = create_button(Buttons.SEND)
        self.ButtonRepeat: QPushButton = create_button(Buttons.REPEAT)
        self.ButtonKeepAlive: QPushButton = create_button(Buttons.KEEP_ALIVE)
        self.ButtonReverse: QPushButton = create_button(Buttons.REVERSE)
        self.ButtonLog: QPushButton = create_button(Buttons.LOG)
        self.ButtonMessage: QPushButton = create_button(Buttons.MESSAGE)
        self.ButtonFiles: QPushButton = create_button(Buttons.FILE)
        self.ButtonSave: QPushButton = create_button(Buttons.SAVE)
        self.ButtonReconnect: QPushButton = create_button(Buttons.RECONNECT)
        self.ButtonEchoTest: QPushButton = create_button(Buttons.ECHO_TEST)
        self.ButtonPrint: QPushButton = create_button(Buttons.PRINT)
        self.ButtonTools: QPushButton = create_button(Buttons.TOOLS)
        from common.gui.tools.widgets.SettingsButton import SettingsButton
        self.ButtonSettings = SettingsButton()
        from PyQt6.QtCore import QSize
        self.ButtonSettings.setText("")
        self.ButtonSettings.setIcon(QIcon(GuiFilesPath.SETTINGS))
        self.ButtonSettings.setIconSize(QSize(24, 24))
        self.ButtonSettings.setStyleSheet("QPushButton { padding: 4px; }")
        self.ButtonSettings.setAccessibleName("Settings")
        self.ButtonSettings.setToolTip("Settings")
        self.ButtonSettings.setFixedWidth(38)
        self.ButtonHelp: QPushButton = create_button(Buttons.HELP)

        # Create and place the JSON-view control buttons as "New Field", "New Subfield", "Remove Field"

        self.PlusButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_PLUS_SIGN)
        self.MinusButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_MINUS_SIGN)
        self.NextLevelButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_NEXT_LEVEL_SIGN)
        self.ButtonDisable: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_DISABLE)
        self.ButtonEnable: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_ENABLE)
        self.ButtonEnableAll: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_ENABLE_ALL)
        self.ButtonUndo: QPushButton = create_button(Buttons.UNDO)
        self.ButtonRedo: QPushButton = create_button(Buttons.REDO)

        # Setup buttons to the destination layout. The order of button below will change their order on the MainWindow

        # Transaction data tree control buttons

        json_control_buttons = (
            self.PlusButton,
            self.MinusButton,
            self.NextLevelButton,
            self.ButtonDisable,
            self.ButtonEnable,
            self.ButtonEnableAll,
            self.ButtonUndo,
            self.ButtonRedo,
        )

        # Main control buttons

        main_control_buttons = (
            self.ButtonSend,
            self.ButtonReverse,
            self.ButtonRepeat,
            self.ButtonKeepAlive,
            self.ButtonLog,
            self.ButtonMessage,
            self.ButtonFiles,
            self.ButtonSave,
            self.ButtonReconnect,
            self.ButtonEchoTest,
            self.ButtonPrint,
            self.ButtonTools,
            self.ButtonHelp,
        )

        for button in main_control_buttons:
            self.ButtonsLayout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        from PyQt6.QtWidgets import QLayout
        self.ButtonsLayout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.ButtonsLayout.addSpacing(12)
        self.ButtonsLayout.addStretch()
        self.ButtonsLayout.addWidget(self.ButtonSettings)
        self.ButtonsLayout.addSpacing(0)

        theme_menu = QMenu(self)
        console_menu = QMenu("Console", theme_menu)
        self.console_colors = QActionGroup(console_menu)
        self.console_colors.setExclusive(True)
        themes = {'Light': '#F0F0F0', 'Dark green': '#102D28', 'Dark red': '#3B202B', 'Graphite': '#292D32', 'Slate blue': '#243447', 'Signal blue': '#012E4F', 'Midnight': '#011627', 'Black': '#000000'}
        self._appearance_settings = Appearance.load(APPEARANCE_SETTINGS_PATH)
        for field, color in self.config.theme.model_dump().items():
            setattr(self._appearance_settings, field, color)
        for key, field in (("Tree", "treeColor"), ("Window", "windowColor"), ("Console", "consoleColor")):
            QApplication.instance().setProperty(f"signal{key}Color", getattr(self._appearance_settings, field))
        saved_color = self._appearance_settings.consoleColor
        current_color = QApplication.instance().property("signalConsoleColor") or saved_color
        if current_color == "#252526":
            current_color = themes["Nord"]
        if current_color not in themes.values():
            current_color = themes["Signal blue"]
        for name, color in themes.items():
            action = QWidgetAction(console_menu)
            swatch = QPushButton(console_menu)
            swatch.setFixedSize(96, 26)
            swatch.setToolTip(name)
            swatch.setAccessibleName(name)
            action.setDefaultWidget(swatch)
            console_menu.addAction(action)
            action.setCheckable(True)
            action.setData(color)
            action.setChecked(color == current_color)
            self.console_colors.addAction(action)
            swatch.clicked.connect(lambda checked=False, value=color: self._set_console_color(value, persist=True))
        self.console_colors.triggered.connect(lambda action: self._set_console_color(action.data(), persist=True))
        window_menu = QMenu("Base", theme_menu)
        self.window_colors = QActionGroup(window_menu)
        self.window_colors.setExclusive(True)
        for name, color in themes.items():
            action = QWidgetAction(window_menu)
            swatch = QPushButton(window_menu)
            swatch.setFixedSize(96, 26)
            swatch.setToolTip(name)
            swatch.setAccessibleName(name)
            action.setDefaultWidget(swatch)
            action.setCheckable(True)
            action.setData(color)
            window_menu.addAction(action)
            self.window_colors.addAction(action)
            swatch.clicked.connect(lambda checked=False, value=color: self._apply_dark_theme(value, persist=True))
        self.window_colors.triggered.connect(lambda action: self._apply_dark_theme(action.data(), persist=True))
        tree_menu = QMenu("Data Fields", theme_menu)
        self.tree_colors = QActionGroup(tree_menu)
        self.tree_colors.setExclusive(True)
        for name, color in themes.items():
            action = QWidgetAction(tree_menu)
            swatch = QPushButton(tree_menu)
            swatch.setFixedSize(96, 26)
            swatch.setToolTip(name)
            swatch.setAccessibleName(name)
            action.setDefaultWidget(swatch)
            action.setCheckable(True)
            action.setData(color)
            tree_menu.addAction(action)
            self.tree_colors.addAction(action)
            swatch.clicked.connect(lambda checked=False, value=color: self._set_tree_color(value, persist=True))
        self.tree_colors.triggered.connect(lambda action: self._set_tree_color(action.data(), persist=True))
        for menu in (tree_menu, window_menu, console_menu):
            theme_menu.addMenu(menu)
        QApplication.instance().installEventFilter(self)
        self.horizontalLayout.addSpacing(0)
        self._set_console_color(current_color)

        self.JsonButtonsLayout.setSpacing(6)
        self.JsonButtonsLayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for button in json_control_buttons:
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            self.JsonButtonsLayout.addWidget(button)

        for button in self.ButtonRepeat, self.ButtonKeepAlive:
            button.setIcon(QIcon(GuiFilesPath.GREY_CIRCLE))

    def _connect_all(self) -> None:

        """
        This function connects buttons, key sequences, and special menu buttons to corresponding data processing
        requests. The MainWindow doesn't process the data by itself, instead of this it will send a data processing
        request by pyqtSignal. All of these groups use the same signals - clear, echo_test, parse_file, reconnect,
        and so on. Call syntax is a little different for each group. One common can be emitted by different methods,
        e.g. cause for transaction data sending (common "send") can be MainWindow key press or keyboard key sequence.
        """

        buttons_connection_map = {  # Signals, which should be emitted by MainWindow key press event
            self.PlusButton: self._tab_view.plus,
            self.MinusButton: self._tab_view.minus,
            self.NextLevelButton: self._tab_view.next_level,
            self.ButtonSend: self.send,
            self.ButtonEchoTest: self.echo_test,
            self.ButtonReconnect: self.reconnect,
            self.ButtonDisable: self.disable_item,
            self.ButtonEnable: self.enable_item,
            self.ButtonEnableAll: self.enable_all_items,
            self.ButtonUndo: self.undo,
            self.ButtonRedo: self.redo,
            self.ButtonFiles: self.parse_file,
            self.ButtonSettings: self.settings,
        }

        tab_view_connection_map = {
            self._tab_view.field_changed: self.field_changed,
            self._tab_view.field_added: self.field_added,
            self._tab_view.field_removed: self.field_removed,
            self._tab_view.disable_next_level_button: self.disable_next_level_button,
            self._tab_view.enable_next_level_button: self.enable_next_level_button,
            self._tab_view.new_tab_opened: lambda: self.reset.emit(False),
            self._tab_view.copy_bitmap: self.copy_bitmap,
            self._tab_view.trans_id_set: self.set_reversal_trans_id,
            self._tab_view.tab_changed: self.process_tab_change,
            self._tab_view.files_dropped: self.files_dropped,
            self._tab_view.text_dropped: self.text_dropped,
        }

        event_connection_map = {
            self.SearchLine.textChanged: self.search,
            self.SearchLine.editingFinished: self._tab_view.set_json_focus,
            # self.api_mode_changed: self.process_api_mode_change,
        }

        keys_connection_map = {

            # Signals, which should be emitted by key sequences on keyboard
            # The string argument (modifier) is a hint about a requested data format

            # Predefined Key Sequences
            QKeySequence.StandardKey.New: self._tab_view.plus,
            QKeySequence.StandardKey.Delete: self._tab_view.minus,
            QKeySequence.StandardKey.HelpContents: self.about,
            QKeySequence.StandardKey.Open: self.parse_file,
            QKeySequence.StandardKey.Undo: self.undo,
            QKeySequence.StandardKey.Redo: self.redo,
            QKeySequence.StandardKey.Find: self.activate_search,
            QKeySequence.StandardKey.Close: self._tab_view.close_current_tab,
            QKeySequence.StandardKey.Print: lambda: self.ButtonPrint.showMenu(),
            QKeySequence.StandardKey.Save: lambda: self.save.emit(
                ButtonActions.SaveMenuActions.CURRENT_TAB, ButtonActions.SaveButtonDataFormats.JSON
            ),

            # Custom Key Sequences
            # The string argument (modifier) is a hint about a requested data format
            KeySequences.CTRL_T: self.add_tab,
            KeySequences.CTRL_SHIFT_ENTER: lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.LAST),
            KeySequences.CTRL_ENTER: self.send,
            KeySequences.CTRL_R: self.reconnect,
            KeySequences.CTRL_L: self.clear_log,
            KeySequences.CTRL_E: lambda: self.json_view.edit_column(FieldsSpec.ColumnsOrder.VALUE),
            KeySequences.CTRL_W: lambda: self.json_view.edit_column(FieldsSpec.ColumnsOrder.FIELD),
            KeySequences.CTRL_D: self.set_item_disabled,
            KeySequences.CTRL_Q: self._tab_view.close_current_tab,
            KeySequences.CTRL_SHIFT_N: self._tab_view.next_level,
            KeySequences.CTRL_ALT_Q: exit,
            KeySequences.CTRL_ALT_ENTER: self.echo_test,
            KeySequences.CTRL_ALT_V: lambda: self.validate_message.emit(True),
            KeySequences.CTRL_PAGE_UP: self._tab_view.prev_tab,
            KeySequences.CTRL_PAGE_DOWN: self._tab_view.next_tab,
            KeySequences.CTRL_TAB: self._tab_view.next_tab,
            KeySequences.CTRL_SHIFT_TAB: self._tab_view.prev_tab,
            KeySequences.CTRL_ALT_P: lambda: self.print.emit(ButtonActions.PrintButtonDataFormats.TERM),
        }

        # The mapping is defined, let's connect them all
        from common.gui.toolkit.create_gui_elements import set_button_hints, set_shortcut_hints
        set_button_hints(self)
        set_shortcut_hints(buttons_connection_map, keys_connection_map)
        self.ButtonPrint.setToolTip("Print data to console (Ctrl+P)")
        self.ButtonSave.setToolTip("Save file (Ctrl+S: save current tab as JSON)")
        self.ButtonReverse.setToolTip("Reverse transaction (Ctrl+Shift+Enter: reverse last transaction)")
        self.ButtonDisable.setToolTip("Disable selected field (Ctrl+D: toggle enabled state)")
        self.ButtonEnable.setToolTip("Enable selected field (Ctrl+D: toggle enabled state)")

        for combination, function in keys_connection_map.items():  # Key sequences
            QShortcut(QKeySequence(combination), self).activated.connect(function)

        for button, slot in buttons_connection_map.items():
            button.clicked.connect(slot)

        for connection_map in tab_view_connection_map, event_connection_map:
            for signal, slot in connection_map.items():
                signal.connect(slot)

    def set_custom_repeat_interval(self, interval_name, trans_type):
        match trans_type:
            case KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION:
                button = self.ButtonRepeat

            case KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE:
                button = self.ButtonKeepAlive

            case _:
                return

        icon = GuiFilesPath.GREEN_CIRCLE

        if interval_name in (KeepAlive.IntervalNames.KEEP_ALIVE_STOP, KeepAlive.IntervalNames.KEEP_ALIVE_ONCE):
            icon = GuiFilesPath.GREY_CIRCLE

        button.setIcon(QIcon(icon))

    def set_repeat_actions(self):
        for button in self.ButtonRepeat, self.ButtonKeepAlive:

            menu = QMenu(button)
            group = QActionGroup(menu)
            group.setExclusive(True)

            self.repeat_actions[button] = dict()

            group.triggered.connect(lambda _action, _button=button: self.process_repeat_action(_action, _button))

            for interval in KeepAlive.IntervalNames:
                if interval == KeepAlive.IntervalNames.KEEP_ALIVE_DEFAULT:
                    continue

                action = menu.addAction(interval)
                action.setCheckable(True)
                action.setData(interval)

                group.addAction(action)
                self.repeat_actions[button][interval] = action

                if interval == KeepAlive.IntervalNames.KEEP_ALIVE_STOP:
                    action.setChecked(True)

            button.setMenu(menu)

    def set_item_disabled(self):
        if not (item := self.json_view.currentItem()):
            return

        if item.is_disabled:
            self.enable_item.emit()
            return

        self.disable_item.emit()

    def process_repeat_action(self, action: QAction, button: QPushButton):
        interval = action.data()

        if not (actions := self.repeat_actions.get(button)):
            return

        if not (stop_action := actions.get(KeepAlive.IntervalNames.KEEP_ALIVE_STOP)):
            return

        button.setIcon(QIcon(GuiFilesPath.GREEN_CIRCLE))

        if interval in (KeepAlive.IntervalNames.KEEP_ALIVE_STOP, KeepAlive.IntervalNames.KEEP_ALIVE_ONCE):
            stop_action.setChecked(True)
            button.setIcon(QIcon(GuiFilesPath.GREY_CIRCLE))

        match button:
            case self.ButtonRepeat:
                self.repeat.emit(interval)

            case self.ButtonKeepAlive:
                self.keep_alive.emit(interval)

    def set_buttons_menu(self) -> None:

        def process_menu_structure(structure: dict, menu=None):
            for button in structure.keys():
                if not isinstance(button, QPushButton):
                    continue

                if not structure.get(button):
                    continue

                button.setMenu(QMenu(button))

                process_menu_structure(structure.get(button), button.menu())

            for function, action in structure.items():
                if menu is None:
                    continue

                menu.addAction(function, action)
                menu.addSeparator()

        buttons_menu_structure = {

            self.ButtonReverse: {
                ToolBarElements.LAST: lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.LAST),
                ToolBarElements.OTHER: lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.OTHER),
                ToolBarElements.SET_REVERSAL_FIELDS:
                    lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.SET_REVERSAL),
            },

            self.ButtonMessage: {
                ToolBarElements.VALIDATE: lambda: self.validate_message.emit(True),
                ToolBarElements.RESET_MESSAGE: lambda: self.reset.emit(False),
                ToolBarElements.CLEAR_MESSAGE: self.clear,
            },

            self.ButtonLog: {
                ToolBarElements.CLEAR_LOG: self.clear_log,
                ToolBarElements.COPY_LOG: self.copy_log,
            },

            self.ButtonPrint: {
                ToolBarElements.JSON: lambda: self.print.emit(OutputFilesFormat.JSON),
                ToolBarElements.INI: lambda: self.print.emit(OutputFilesFormat.INI),
                ToolBarElements.DUMP: lambda: self.print.emit(OutputFilesFormat.DUMP),

                ButtonActions.PrintButtonDataFormats.SPEC.title():
                    lambda: self.print.emit(ButtonActions.PrintButtonDataFormats.SPEC),

                ButtonActions.PrintButtonDataFormats.CONFIG.title():
                    lambda: self.print.emit(ButtonActions.PrintButtonDataFormats.CONFIG),

                ButtonActions.PrintButtonDataFormats.TERM.title():
                    lambda: self.print.emit(ButtonActions.PrintButtonDataFormats.TERM),
            },

            self.ButtonSave: {
                ToolBarElements.CURRENT_TAB:
                    lambda: self.save.emit(ButtonActions.SaveMenuActions.CURRENT_TAB, str()),

                f"{ButtonActions.SaveMenuActions.ALL_TABS} as {OutputFilesFormat.JSON}":
                    lambda: self.save.emit(ButtonActions.SaveMenuActions.ALL_TABS, OutputFilesFormat.JSON),

                f"{ButtonActions.SaveMenuActions.ALL_TABS} as {OutputFilesFormat.INI}":
                    lambda: self.save.emit(ButtonActions.SaveMenuActions.ALL_TABS, OutputFilesFormat.INI),

                f"{ButtonActions.SaveMenuActions.ALL_TABS} as {OutputFilesFormat.DUMP}":
                    lambda: self.save.emit(ButtonActions.SaveMenuActions.ALL_TABS, OutputFilesFormat.DUMP),
            },

            self.ButtonRepeat: {
                # This menu will be set in self.process_transaction_loop_change by default
            },

            self.ButtonKeepAlive: {
                # This menu will be set in self.process_transaction_loop_change by default
            },

            self.ButtonTools: {
                ToolBarElements.SETTINGS: self.settings,
                ToolBarElements.SPECIFICATION: self.specification,
                ToolBarElements.CONSTRUCT_FIELD: self.parse_complex_field,
            },

            self.ButtonHelp: {
                ToolBarElements.DOCUMENTATION: self.show_document,
                ToolBarElements.OPENAPI_DOC: self.show_openapi_doc,
                ToolBarElements.HOTKEYS: self.hotkeys,
                ToolBarElements.LICENSE: self.show_license,
                ToolBarElements.ABOUT: self.about,
            }
        }

        process_menu_structure(structure=buttons_menu_structure)
        tools_menu = self.ButtonTools.menu()
        api_menu = QMenu('API', tools_menu)
        for label, mode in ((ToolBarElements.START, ApiModes.START),
                            (ToolBarElements.STOP, ApiModes.STOP),
                            (ToolBarElements.RESTART, ApiModes.RESTART)):
            api_menu.addAction(label, lambda checked=False, state=mode: self.api_mode_changed.emit(state))
        tools_menu.insertMenu(tools_menu.actions()[0], api_menu)

    def disable_openapi_menu(self, disable: bool):
        menu = self.ButtonHelp.menu()
        disabled_action_text = f"{ToolBarElements.OPENAPI_DOC} | Start API to unlock"

        for action in menu.actions():
            if not action.text().startswith(ToolBarElements.OPENAPI_DOC):
                continue

            action.setDisabled(disable)
            action.setText(disabled_action_text if disable else ToolBarElements.OPENAPI_DOC)

            return

    def undo_changes(self):
        self._tab_view.json_view.undo()

    def redo_changes(self):
        self._tab_view.json_view.redo()

    def process_api_mode_change(self, state: ApiModes):
        openapi_menu_disabled = True

        match state:

            case ApiModes.NOT_RUN:
                icon = GuiFilesPath.GREY_CIRCLE

            case ApiModes.STOP:
                icon = GuiFilesPath.RED_CIRCLE

            case ApiModes.START:
                icon = GuiFilesPath.GREEN_CIRCLE
                openapi_menu_disabled = False

            case _:
                icon = GuiFilesPath.GREY_CIRCLE

        self.ApiStatus.setText(ApiModeNames[state])
        self.ApiStatusLabel.setPixmap(QPixmap(icon))
        self.disable_openapi_menu(disable=openapi_menu_disabled)

    def set_tab_name(self, tab_name):
        self._tab_view.setTabText(label=tab_name)

    def add_tab(self):
        self._tab_view.add_tab()
        self.reset.emit(False)

    def search(self, text):
        self.json_view.search(text)

    def process_tab_change(self):
        self.SearchLine.setText(str())
        self.json_view.search(str())
        self.json_view.expandAll()

    def set_reversal_trans_id(self):
        if not (trans_id := self.json_view.get_trans_id()):
            return

        if not self.spec.is_reversal(self.get_mti()):
            return

        if not self.json_view.is_trans_id_generate_mode_on():
            return

        self.json_view.set_trans_id(f"{trans_id}_R")

    def set_focus(self):
        self.json_view.setFocus()

    def activate_search(self):
        self.SearchLine.setFocus()

    # Usually disables in fields flat-mode to avoid subfields creation
    def disable_next_level_button(self, disable: bool = True) -> None:
        self.NextLevelButton.setDisabled(disable)

    def enable_next_level_button(self, enable: bool = True) -> None:
        self.NextLevelButton.setEnabled(enable)

    def get_tab_names(self) -> list[str]:
        return self._tab_view.get_tab_names()

    def parse_tab(self, tab_name: str | None = None, flat=False):
        fields = self._tab_view.generate_fields(tab_name=tab_name, flat=flat)

        try:
            return {field: fields[field] for field in sorted(fields, key=int)}
        except ValueError:
            return fields

    def get_trans_id(self, tab_name: str):
        return self._tab_view.get_trans_id(tab_name)

    def get_tab_name(self, tab_index: int | None = None):
        if tab_index is None:
            tab_index = self._tab_view.currentIndex()

        return self._tab_view.tabText(tab_index)

    # Validate whole transaction data, presented on MainWindow
    def validate_fields(self, force=False) -> None:
        self.json_view.check_all_items(force=force)

    def clean_window_log(self) -> None:
        if hasattr(self, '_print_highlighter'):
            self._print_highlighter.cancel()
        self.LogArea.clear()

    def get_fields_to_generate(self) -> list[str]:
        return self.json_view.get_checkboxes()

    def get_mti(self, length: int = MessageLength.MESSAGE_TYPE_LENGTH, tab_name: str | None = None) -> str | None:
        if tab_name is None and not (tab_name := self._tab_view.get_current_tab_name()):
            self._tab_view.setTabText()

        if not self._tab_view.get_current_tab_name():
            raise ValueError("Missing tab name")

        if not (msg_type_box := self._tab_view.get_msg_type(tab_name)):
            return

        if not (message_type := msg_type_box.currentText()):
            return

        if not (message_type := message_type[:length]):
            return

        return message_type

    def set_log_data(self, data: str = str(), data_format=None) -> None:
        from common.gui.tools.PrintHighlighter import PrintHighlighter
        from PyQt6.QtGui import QTextCharFormat
        if not hasattr(self, '_print_highlighter'):
            self._print_highlighter = PrintHighlighter(self.LogArea.document())
        self._print_highlighter.cancel()
        self.LogArea.clear()
        self.LogArea.setCurrentCharFormat(QTextCharFormat())
        self.LogArea.setPlainText(data)
        self._print_highlighter.data_format = str(data_format or '')
        self._print_highlighter.printed_blocks = self.LogArea.document().blockCount()
        self._print_highlighter.rehighlight()

    def get_log_data(self) -> str:
        return self.LogArea.toPlainText()

    def get_bitmap_data(self) -> str:
        return self._tab_view.bit_map.text()

    # To avoid errors connection buttons will be disabled during the network connection opening
    def block_connection_buttons(self) -> None:
        self.change_connection_buttons_state(enabled=False)

    # After the connection status is changed connection buttons will be enabled again
    def unblock_connection_buttons(self) -> None:
        self.change_connection_buttons_state(enabled=True)

    def change_connection_buttons_state(self, enabled: bool) -> None:
        for button in (self.ButtonReconnect, self.ButtonSend, self.ButtonEchoTest):
            button.setEnabled(enabled)

    def set_connection_status(self, status: QTcpSocket.SocketState) -> None:
        try:
            text = ConnectionStatus[status.name]
            icon = ConnectionIcon[status.name]

        except KeyError:
            text = ConnectionStatus.ConnectionStatuses.UNKNOWN
            icon = ConnectionStatus.ConnectionIcons.GREY

        self.ConnectionStatus.setText(text)
        self.ConnectionStatusLabel.setPixmap(QPixmap(icon))

    def set_bitmap(self, bitmap: str = str()) -> None:
        self._tab_view.bit_map.setText(bitmap)

    # Closing network connections and so on before MainWindow switch off
    def closeEvent(self, a0: QCloseEvent) -> None:
        QApplication.instance().removeEventFilter(self)
        self._save_splitter_position()
        self.hide()
        self.window_close.emit()
        a0.accept()
