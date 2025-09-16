from sys import exit
from ctypes import windll
from PyQt6.QtNetwork import QTcpSocket
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QCloseEvent, QKeySequence, QShortcut, QPixmap, QFont
from PyQt6.QtWidgets import QMainWindow, QMenu, QPushButton
from common.gui.forms.mainwindow import Ui_MainWindow
from common.gui.decorators.window_settings import set_window_icon
from common.lib.data_models.Config import Config
from common.gui.enums import ButtonActions, MainFieldSpec as FieldsSpec
from common.gui.enums.KeySequences import KeySequences
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.gui.enums import ApiMode
from common.gui.enums.Buttons import Buttons
from common.gui.enums.ConnectionStatus import ConnectionStatus, ConnectionIcon
from common.lib.enums.MessageLength import MessageLength
from common.lib.enums.DataFormats import OutputFilesFormat
from common.lib.enums import KeepAlive
from common.lib.enums.ReleaseDefinition import ReleaseDefinition
from common.lib.enums.TextConstants import TextConstants
from common.lib.core.EpaySpecification import EpaySpecification
from common.gui.core.tab_view.TabView import TabView
from common.gui.enums.ToolBarElements import ToolBarElements
from common.gui.enums.ApiMode import ApiModes


"""
MainWindow is a general SVTerminal GUI, Runs as an independent application, interacts with the backend using pyqtSignal 
Can be run separately from the backend, but does nothing in this case. 
 
The goals of MainWindow are interaction with the GUI user, user input data collection, and data processing requests 
using pyqtSignal. Better to not force it to process the data, validate values, and so on
"""


class MainWindow(Ui_MainWindow, QMainWindow):

    """
    Data processing request signals. Some of them send string modifiers as a hint on how to process the data
    Each common has a corresponding @property for external interactions. The signals handling should be build
    using their properties
    """

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
    api_mode_changed: pyqtSignal = pyqtSignal(str)
    exit: pyqtSignal = pyqtSignal(int)
    show_document: pyqtSignal = pyqtSignal()
    show_license: pyqtSignal = pyqtSignal()
    disable_item: pyqtSignal = pyqtSignal()
    enable_item: pyqtSignal = pyqtSignal()
    enable_all_items: pyqtSignal = pyqtSignal()
    _message_repeat_menu: QMenu = None
    _keep_alive_menu: QMenu = None
    _print_menu: QMenu = None
    _api_menu: QMenu = None
    _control_buttons: list = list()

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
        self.config = config
        self._tab_view: TabView = TabView(self.config)
        self._setup()

    @set_window_icon
    def _setup(self) -> None:
        self.setupUi(self)
        self._add_control_buttons()
        self._add_json_control_buttons()
        self._connect_all()
        self.setWindowTitle(f"{TextConstants.SYSTEM_NAME.capitalize()} {ReleaseDefinition.VERSION} | Terminal GUI")
        windll.shell32.SetCurrentProcessExplicitAppUserModelID("MainWindow")
        self.ButtonSend.setFocus()
        self.set_connection_status(QTcpSocket.SocketState.UnconnectedState)
        self.ButtonsLayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.set_buttons_menu()
        self.TabViewLayout.addWidget(self._tab_view)
        self.api_mode_changed.emit(ApiMode.ApiModes.NOT_RUN)

        for transaction_type in (
            KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE,
            KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION
        ):
            self.process_transaction_loop_change(KeepAlive.IntervalNames.KEEP_ALIVE_STOP, transaction_type)

    def _add_control_buttons(self):
        def create_control_button(name):
            button = QPushButton()
            button.setText(name)
            button.setFont(QFont("Arial", 10))
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            control_buttons.append(button)
            return button

        control_buttons: list[QPushButton] = list()

        self.ButtonSend = create_control_button(Buttons.SEND)
        self.ButtonRepeat = create_control_button(Buttons.REPEAT)
        self.ButtonReverse = create_control_button(Buttons.REVERSE)
        self.ButtonClearLog = create_control_button(Buttons.CLEAR_LOG)
        self.ButtonMessage = create_control_button(Buttons.MESSAGE)
        self.ButtonFiles = create_control_button(Buttons.FILE)
        self.ButtonReconnect = create_control_button(Buttons.RECONNECT)
        self.ButtonEchoTest = create_control_button(Buttons.ECHO_TEST)
        self.ButtonLog = create_control_button(Buttons.LOG)
        self.ButtonPrint = create_control_button(Buttons.PRINT)
        self.ButtonTools = create_control_button(Buttons.TOOLS)
        self.ButtonHelp = create_control_button(Buttons.HELP)

        for control_button in control_buttons:
            self.ButtonsLayout.addWidget(control_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def _add_json_control_buttons(self) -> None:
        # Create and place the JSON-view control buttons as "New Field", "New Subfield", "Remove Field"

        self.PlusButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_PLUS_SIGN)
        self.MinusButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_MINUS_SIGN)
        self.NextLevelButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_NEXT_LEVEL_SIGN)
        self.ButtonDisable = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_DISABLE)
        self.ButtonEnable = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_ENABLE)
        self.ButtonEnableAll = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_ENABLE_ALL)

        buttons_layouts_map = {
            self.PlusLayout: self.PlusButton,
            self.MinusLayout: self.MinusButton,
            self.NextLevelLayout: self.NextLevelButton,
            self.DisableLayout: self.ButtonDisable,
            self.EnableLayout: self.ButtonEnable,
            self.EnableAllLayout: self.ButtonEnableAll,
        }

        for layout, button in buttons_layouts_map.items():
            layout.addWidget(button)

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
            self.ButtonClearLog: self.clear_log,
            self.ButtonEchoTest: self.echo_test,
            self.ButtonReconnect: self.reconnect,
            self.ButtonDisable: self.disable_item,
            self.ButtonEnable: self.enable_item,
            self.ButtonEnableAll: self.enable_all_items,
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
        }

        event_connection_map = {
            self.SearchLine.textChanged: self.search,
            self.SearchLine.editingFinished: self._tab_view.set_json_focus,
            self.api_mode_changed: self.process_api_mode_change,
        }

        keys_connection_map = {

            # Signals, which should be emitted by key sequences on keyboard
            # The string argument (modifier) is a hint about a requested data format

            # Predefined Key Sequences
            QKeySequence.StandardKey.New: self._tab_view.plus,
            QKeySequence.StandardKey.Delete: self._tab_view.minus,
            QKeySequence.StandardKey.HelpContents: self.about,
            QKeySequence.StandardKey.Save: lambda: self.save.emit(ButtonActions.SaveMenuActions.CURRENT_TAB, ButtonActions.SaveButtonDataFormats.JSON),
            QKeySequence.StandardKey.Open: self.parse_file,
            QKeySequence.StandardKey.Undo: self.json_view.undo,
            QKeySequence.StandardKey.Redo: self.json_view.redo,
            QKeySequence.StandardKey.Find: self.activate_search,
            QKeySequence.StandardKey.Close: self._tab_view.close_current_tab,
            QKeySequence.StandardKey.Print: lambda: self.ButtonPrint.showMenu(),

            # Custom Key Sequences
            # The string argument (modifier) is a hint about a requested data format
            KeySequences.CTRL_T: self.add_tab,
            KeySequences.CTRL_SHIFT_ENTER: lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.LAST),
            KeySequences.CTRL_ENTER: self.send,
            KeySequences.CTRL_R: self.reconnect,
            KeySequences.CTRL_L: self.clear_log,
            KeySequences.CTRL_E: lambda: self.json_view.edit_column(FieldsSpec.ColumnsOrder.VALUE),
            KeySequences.CTRL_W: lambda: self.json_view.edit_column(FieldsSpec.ColumnsOrder.FIELD),
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

        for combination, function in keys_connection_map.items():  # Key sequences
            QShortcut(QKeySequence(combination), self).activated.connect(function)

        for button, slot in buttons_connection_map.items():
            button.clicked.connect(slot)

        for connection_map in tab_view_connection_map, event_connection_map:
            for signal, slot in connection_map.items():
                signal.connect(slot)

    def set_buttons_menu(self):

        def process_menu_structure(structure: dict, menu=None):
            for button in structure.keys():
                if not isinstance(button, QPushButton):
                    continue

                if not structure.get(button):
                    continue

                button.setMenu(QMenu())

                process_menu_structure(structure.get(button), button.menu())

            for function, action in structure.items():
                if menu is None:
                    continue

                if isinstance(action, dict):
                    sub_menu = menu.addMenu(function)

                    match function:
                        case KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION:
                            self._message_repeat_menu = sub_menu

                        case KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE:
                            self._keep_alive_menu = sub_menu

                        case ToolBarElements.PRINT:
                            self._print_menu = sub_menu

                        case ToolBarElements.API:
                            self._api_menu = sub_menu

                    process_menu_structure(structure=action, menu=sub_menu)

                    continue

                menu.addAction(function, action)
                menu.addSeparator()

        buttons_menu_structure = {
            self.ButtonReverse: {
                ToolBarElements.LAST: lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.LAST),
                ToolBarElements.OTHER: lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.OTHER),
                ToolBarElements.SET_REVERSAL_FIELDS: lambda: self.reverse.emit(ButtonActions.ReversalMenuActions.SET_REVERSAL),
            },
            self.ButtonMessage: {
                ToolBarElements.CLEAR_MESSAGE: self.clear,
                ToolBarElements.RESET_MESSAGE: lambda: self.reset.emit(False),
                ToolBarElements.VALIDATE: lambda: self.validate_message.emit(True),
            },
            self.ButtonLog: {
                ToolBarElements.CLEAR_LOG: self.clear_log,
                ToolBarElements.COPY_LOG: self.copy_log,
            },
            self.ButtonPrint: {
                ToolBarElements.JSON: lambda: self.print.emit(OutputFilesFormat.JSON),
                ToolBarElements.INI: lambda: self.print.emit(OutputFilesFormat.INI),
                ToolBarElements.DUMP: lambda: self.print.emit(OutputFilesFormat.DUMP),
                ButtonActions.PrintButtonDataFormats.SPEC: lambda: self.print.emit(ButtonActions.PrintButtonDataFormats.SPEC),
                ButtonActions.PrintButtonDataFormats.TERM: lambda: self.print.emit(ButtonActions.PrintButtonDataFormats.TERM),
                ButtonActions.PrintButtonDataFormats.CONFIG: lambda: self.print.emit(ButtonActions.PrintButtonDataFormats.CONFIG),
            },
            self.ButtonFiles: {
                ToolBarElements.OPEN: self.parse_file,
                ToolBarElements.SAVE: {
                    ToolBarElements.CURRENT_TAB: lambda: self.save.emit(ButtonActions.SaveMenuActions.CURRENT_TAB, str()),
                    ToolBarElements.ALL_TABS: {
                        OutputFilesFormat.JSON: lambda: self.save.emit(ButtonActions.SaveMenuActions.ALL_TABS, OutputFilesFormat.JSON),
                        OutputFilesFormat.INI: lambda: self.save.emit(ButtonActions.SaveMenuActions.ALL_TABS, OutputFilesFormat.INI),
                        OutputFilesFormat.DUMP: lambda: self.save.emit(ButtonActions.SaveMenuActions.ALL_TABS, OutputFilesFormat.DUMP),
                    },
                },
            },
            self.ButtonRepeat: {
                KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION: {
                    KeepAlive.IntervalNames.KEEP_ALIVE_1S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_1S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_5S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_5S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_10S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_10S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_30S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_30S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_60S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_60S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_300S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_300S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_STOP: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_STOP),
                },
                KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE: {
                    KeepAlive.IntervalNames.KEEP_ALIVE_1S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_1S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_5S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_5S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_10S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_10S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_30S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_30S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_60S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_60S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_300S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_300S),
                    KeepAlive.IntervalNames.KEEP_ALIVE_STOP: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_STOP),
                },

            },
            self.ButtonTools: {
                ToolBarElements.SETTINGS: self.settings,
                ToolBarElements.CONSTRUCT_FIELD: self.parse_complex_field,
                ToolBarElements.SPECIFICATION: self.specification,
                ToolBarElements.API: {
                    ToolBarElements.START: lambda: self.api_mode_changed.emit(ApiModes.START),
                    ToolBarElements.STOP: lambda: self.api_mode_changed.emit(ApiModes.STOP),
                },
            },
            self.ButtonHelp: {
                ToolBarElements.DOCUMENTATION: self.show_document,
                ToolBarElements.HOTKEYS: self.hotkeys,
                ToolBarElements.LICENSE: self.show_license,
                ToolBarElements.ABOUT: self.about,
            }
        }

        process_menu_structure(structure=buttons_menu_structure)

    def process_transaction_loop_change(self, interval_name: str, trans_type: KeepAlive.TransTypes):
        if not interval_name:
            return

        menu_map = {
            KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION: self._message_repeat_menu,
            KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE: self._keep_alive_menu,
        }

        signals_map = {
            KeepAlive.TransTypes.TRANS_TYPE_TRANSACTION: {
                KeepAlive.IntervalNames.KEEP_ALIVE_1S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_1S),
                KeepAlive.IntervalNames.KEEP_ALIVE_5S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_5S),
                KeepAlive.IntervalNames.KEEP_ALIVE_10S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_10S),
                KeepAlive.IntervalNames.KEEP_ALIVE_30S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_30S),
                KeepAlive.IntervalNames.KEEP_ALIVE_60S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_60S),
                KeepAlive.IntervalNames.KEEP_ALIVE_300S: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_300S),
                KeepAlive.IntervalNames.KEEP_ALIVE_STOP: lambda: self.repeat.emit(KeepAlive.IntervalNames.KEEP_ALIVE_STOP),

            },

            KeepAlive.TransTypes.TRANS_TYPE_KEEP_ALIVE: {
                KeepAlive.IntervalNames.KEEP_ALIVE_1S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_1S),
                KeepAlive.IntervalNames.KEEP_ALIVE_5S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_5S),
                KeepAlive.IntervalNames.KEEP_ALIVE_10S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_10S),
                KeepAlive.IntervalNames.KEEP_ALIVE_30S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_30S),
                KeepAlive.IntervalNames.KEEP_ALIVE_60S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_60S),
                KeepAlive.IntervalNames.KEEP_ALIVE_300S: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_300S),
                KeepAlive.IntervalNames.KEEP_ALIVE_STOP: lambda: self.keep_alive.emit(KeepAlive.IntervalNames.KEEP_ALIVE_STOP),
            }
        }

        if not (menu := menu_map.get(trans_type)):
            return

        if not (signals := signals_map.get(trans_type)):
            return

        menu.clear()

        for interval, signal in signals.items():

            if interval == interval_name:
                interval = f"{ButtonActions.Marks.CURRENT_ACTION_MARK} {interval}"

            menu.addAction(interval, signal)
            menu.addSeparator()

    def process_api_mode_change(self, state: str):
        match state:
            case ApiMode.ApiModes.NOT_RUN:
                icon = GuiFilesPath.GREY_CIRCLE

            case ApiMode.ApiModes.STOP:
                icon = GuiFilesPath.RED_CIRCLE

            case ApiMode.ApiModes.START:
                icon = GuiFilesPath.GREEN_CIRCLE

                if self._api_menu:
                    for action in self._api_menu.actions():
                        action.setDisabled(True)
                
            case _:
                icon = GuiFilesPath.GREY_CIRCLE

        self.ApiStatus.setText(ApiMode.ApiModeNames[state])
        self.ApiStatusLabel.setPixmap(QPixmap(icon))

    def set_tab_name(self, tab_name):
        self._tab_view.setTabText(label=tab_name)

    def add_tab(self):
        try:
            self._tab_view.add_tab()
        except IndexError:
            return

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
        self.LogArea.setText(str())

    def get_fields_to_generate(self) -> list[str]:
        return self.json_view.get_checkboxes()

    def get_mti(self, length: int = MessageLength.MESSAGE_TYPE_LENGTH, tab_name: str | None = None) -> str | None:
        if tab_name is None and not (tab_name := self._tab_view.get_current_tab_name()):
            self._tab_view.setTabText()

        if not self._tab_view.get_current_tab_name():
            raise ValueError("Lost tab name")

        if not (msg_type_box := self._tab_view.get_msg_type(tab_name)):
            return

        if not (message_type := msg_type_box.currentText()):
            return

        if not (message_type := message_type[:length]):
            return

        return message_type

    def set_log_data(self, data: str = str()) -> None:
        self.LogArea.setText(data)

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

    def closeEvent(self, a0: QCloseEvent) -> None:
        # Closing network connections and so on before MainWindow switch off
        self.hide()
        self.window_close.emit()
        a0.accept()
