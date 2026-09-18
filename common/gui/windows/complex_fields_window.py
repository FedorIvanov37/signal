from common.gui.toolkit.clipboard import copy_text
from common.core.tools.DebugTrace import trace_operation
from re import search
from json import dumps, loads
from json.decoder import JSONDecodeError
from loguru import logger
from dataclasses import asdict
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, pyqtSlot, QEvent
from PyQt6.QtWidgets import QMenu, QDialog, QPushButton, QApplication, QSizePolicy
from common.core.data_models.Config import Config
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.tools.Parser import Parser
from common.core.data_models.Transaction import Transaction
from common.gui.forms.complex_fields_parser import Ui_ComplexFieldsParser
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.gui.tools.json_views.TransactionView import TransactionView
from common.gui.toolkit.create_gui_elements import create_button
from common.gui.enums import ButtonActions, MainFieldSpec
from common.gui.enums.KeySequences import KeySequences
from common.gui.enums.RootItemNames import RootItemNames
from common.core.enums.TextConstants import TextConstants


class ComplexFieldsParser(Ui_ComplexFieldsParser, QDialog):
    spec: EpaySpecification = EpaySpecification()

    def __init__(self, config: Config, terminal):
        super(ComplexFieldsParser, self).__init__()
        self.config: Config = config
        self.terminal = terminal
        self.parser = Parser(self.config)
        self.setupUi(self)
        self._history_busy = True
        self._setup()
        from common.gui.toolkit.panel_splitter import PanelSplitter
        self.main_splitter = PanelSplitter(self, self.JsonLayout, self.horizontalLayout_2,
                                           self.TextData, self.horizontalLayout, 1, 'field_constructor')
        from common.gui.undo_commands.ConstructorCommand import ConstructorState
        self._constructor_state = ConstructorState(self)
        self._history_busy = False
        self.TextData.textChanged.connect(self.record_text_change)
        self.TextData.installEventFilter(self)
        self.JsonView.undo_stack.indexChanged.connect(self.remember_constructor_state)

    @set_window_icon
    @has_close_button_only
    def _setup(self):
        self.PlusButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_PLUS_SIGN)
        self.MinusButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_MINUS_SIGN)
        self.NextLevelButton: QPushButton = create_button(ButtonActions.ButtonActionSigns.BUTTON_NEXT_LEVEL_SIGN)
        self.UpButton: QPushButton = create_button(f"{ButtonActions.ButtonActionSigns.BUTTON_UP_SIGN} To JSON ")
        self.DownButton: QPushButton = create_button(f"{ButtonActions.ButtonActionSigns.BUTTON_DOWN_SIGN} To String ")
        self.UndoButton = create_button('Undo')
        self.RedoButton = create_button('Redo')
        self.JsonView: TransactionView = TransactionView(self.config, RootItemNames.FIELD_CONSTRUCTOR_ROOT_NAME)

        widgets_layouts_map = {
            self.PlusLayout: self.PlusButton,
            self.MinusLayout: self.MinusButton,
            self.NextLevelLayout: self.NextLevelButton,
            self.UpLayout: self.UpButton,
            self.DownLayout: self.DownButton,
            self.JsonLayout: self.JsonView,
        }

        for button in self.UpButton, self.DownButton:
            button.setFont(QFont("MS Shell Dlg 2", 10))

        for layout, widget in widgets_layouts_map.items():
            layout.addWidget(widget)
        self.horizontalLayout_2.insertWidget(self.horizontalLayout_2.indexOf(self.SearchLine), self.UndoButton)
        self.horizontalLayout_2.insertWidget(self.horizontalLayout_2.indexOf(self.SearchLine), self.RedoButton)

        for separator in (self.line, self.line_2):
            self.horizontalLayout_2.removeWidget(separator)
            separator.hide()
        self.horizontalLayout_2.setSpacing(6)
        self.horizontalLayout_2.setStretch(self.horizontalLayout_2.indexOf(self.SearchLine), 1)
        for button in (self.PlusButton, self.MinusButton, self.NextLevelButton,
                       self.UpButton, self.DownButton):
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        for button in (self.PlusButton, self.MinusButton, self.NextLevelButton, self.UpButton, self.DownButton,
                       self.UndoButton, self.RedoButton):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        for field in asdict(self.spec.FIELD_SET).values():
            if not self.spec.is_field_complex([field]):
                continue

            description: str = self.spec.get_field_description([field], string=True)

            self.FieldNumber.addItem(f"{field} - {description}")

        button_menu_structure = {
            self.ButtonClearString: {
                ButtonActions.ClearMenuActions.ALL: lambda: self.history_action(self.clear_all, 'Clear all'),
                ButtonActions.ClearMenuActions.JSON: lambda: self.history_action(self.JsonView.clean, 'Clear JSON'),
                ButtonActions.ClearMenuActions.STRING: lambda: self.history_action(self.clear_string, 'Clear string'),
            },

            self.ButtonCopy: {
                ButtonActions.ClearMenuActions.JSON: self.copy_json,
                ButtonActions.ClearMenuActions.STRING: self.copy_string,
            },

            self.ButtonMainWindow: {
                ButtonActions.DataMenuActions.GET_DATA: lambda: self.history_action(self.get_from_main_window, 'Get field data'),
                ButtonActions.DataMenuActions.SET_DATA: self.set_on_main_windows,
            },
        }

        for button, actions in button_menu_structure.items():
            button.setMenu(QMenu())
            if button is self.ButtonMainWindow:
                button.menu().setStyleSheet('''
                    QMenu { padding: 4px 6px; }
                    QMenu::item { padding: 5px 8px 5px 4px; }
                    QMenu::icon { left: 6px; }
                ''')

            for action, function in actions.items():
                if action in (ButtonActions.DataMenuActions.GET_DATA, ButtonActions.DataMenuActions.SET_DATA):
                    from PyQt6.QtGui import QIcon
                    from common.gui.tools.widgets.FieldActionIcon import FieldActionIcon
                    direction = 'right' if action == ButtonActions.DataMenuActions.GET_DATA else 'left'
                    button.menu().addAction(QIcon(FieldActionIcon(direction)), str(action)[1:].strip(), function)
                else:
                    button.menu().addAction(action, function)
                button.menu().addSeparator()

        self.JsonView.hideColumn(MainFieldSpec.ColumnsOrder.PROPERTY)
        self.connect_all()
        self.set_field_data()

    def connect_all(self) -> None:
        button_connection_map = {
            self.ButtonClose: self.close,
            self.ButtonClearString: lambda: self.history_action(self.clear_string, 'Clear string'),
            self.UpButton: lambda: self.history_action(self.parse_string, 'To JSON'),
            self.DownButton: lambda: self.history_action(self.parse_json, 'To string'),
            self.UndoButton: self.JsonView.undo,
            self.RedoButton: self.JsonView.redo,
            self.PlusButton: self.JsonView.plus,
            self.MinusButton: self.JsonView.minus,
            self.NextLevelButton: self.JsonView.next_level,
        }

        general_connection_map = {
            self.SearchLine.textChanged: self.JsonView.search,
            self.SearchLine.editingFinished: self.JsonView.setFocus,
            self.FieldNumber.currentIndexChanged: self.change_field,
            self.JsonView.text_dropped: self.drop_field_text,
            self.JsonView.files_dropped: self.drop_field_files,
        }

        keys_connection_map = {
            QKeySequence.StandardKey.Undo: self.JsonView.undo,
            QKeySequence.StandardKey.Redo: self.JsonView.redo,
            QKeySequence.StandardKey.New: self.JsonView.plus,
            QKeySequence.StandardKey.Delete: self.JsonView.minus,
            QKeySequence.StandardKey.Find: self.SearchLine.setFocus,
            KeySequences.CTRL_L: self.ButtonClearString.showMenu,
            KeySequences.CTRL_E: lambda: self.JsonView.edit_column(MainFieldSpec.ColumnsOrder.VALUE),
            KeySequences.CTRL_W: lambda: self.JsonView.edit_column(MainFieldSpec.ColumnsOrder.FIELD),
            KeySequences.CTRL_SHIFT_N: self.JsonView.next_level,
            KeySequences.CTRL_T: self.set_message,
        }

        for button, action in button_connection_map.items():
            button.clicked.connect(action)

        for signal, slot in general_connection_map.items():
            signal.connect(slot)

        for combination, function in keys_connection_map.items():  # Key sequences
            QShortcut(QKeySequence(combination), self).activated.connect(function)
        from common.gui.toolkit.create_gui_elements import set_button_hints, set_shortcut_hints
        set_button_hints(self)
        set_shortcut_hints(button_connection_map, keys_connection_map)

    def set_message(self, message: str | None = None) -> None:
        if message is None:
            message: str = TextConstants.HELLO_MESSAGE + "\n"

        self.TextData.setText(message)
        self.TextData.clearFocus()

    def set_field_data(self) -> None:
        self.JsonView.clean()
        self.get_from_main_window()

    def clear_string(self) -> None:
        self.TextData.setText(str())

    def copy_json(self) -> None:
        json_data: dict = self.get_json_data()
        json_data: str = dumps(json_data, indent=4)
        self.set_clipboard_text(json_data)
        logger.info("JSON copied to clipboard")

    def copy_string(self) -> None:
        if self.set_clipboard_text(self.TextData.toPlainText()):
            logger.info("String copied to clipboard")

    @staticmethod
    def set_clipboard_text(data: str = str()) -> bool:
        return copy_text(data)

    @pyqtSlot()
    @trace_operation
    def set_on_main_windows(self) -> None:
        try:
            field_number = self.get_field_number()
        except LookupError as lookup_error:
            logger.error(lookup_error)
            return

        if not (json_data := self.get_json_data()):
            logger.error("No data to set")
            return

        if not (field_data := json_data.get(field_number)):
            logger.error("Missing field data")
            return

        transaction: Transaction = self.terminal.parse_main_window_tab()
        transaction.data_fields[field_number] = field_data

        view = self.terminal.window.json_view
        self.terminal._json_view_restore_state = (
            view,
            view.currentItem(),
            view.verticalScrollBar().value(),
            view.horizontalScrollBar().value(),
        )
        self.terminal.parse_transaction(transaction)

        logger.info(f"Field {field_number} data applied to main window")

    def get_json_data(self):
        try:
            field_number = self.get_field_number()
        except LookupError as lookup_error:
            logger.error(lookup_error)
            return

        try:
            if not (json_data := self.JsonView.generate_fields()):
                return json_data

        except ValueError as validation_error:
            self.clear_string()
            logger.error(validation_error)
            return {}

        if not (json_data.get(field_number)):
            return json_data

        return json_data

    def clear_all(self) -> None:
        self.JsonView.clean()
        self.clear_string()

    def remember_constructor_state(self, *_):
        if not self._history_busy:
            from common.gui.undo_commands.ConstructorCommand import ConstructorState
            self._constructor_state = ConstructorState(self)

    def history_action(self, action, label, before=None):
        from common.gui.undo_commands.ConstructorCommand import ConstructorState, ConstructorCommand
        if self._history_busy:
            action()
            return
        before = before or ConstructorState(self)
        self._history_busy = True
        try:
            action()
        finally:
            self._history_busy = False
        after = ConstructorState(self)
        if (before.index == after.index and before.text == after.text
                and before.tree.items == after.tree.items):
            self._constructor_state = after
            return
        self.JsonView.undo_stack.push(ConstructorCommand(self, before, after, label))

    def change_field(self, *_):
        self.history_action(self.set_field_data, 'Change field',
                            getattr(self, '_constructor_state', None))

    def record_text_change(self):
        if not self._history_busy:
            self.history_action(lambda: None, 'Edit string', self._constructor_state)

    def eventFilter(self, watched, event):
        if watched is self.TextData and event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            undo = event.matches(QKeySequence.StandardKey.Undo)
            redo = event.matches(QKeySequence.StandardKey.Redo)
            if undo or redo:
                event.accept()
                if event.type() == QEvent.Type.KeyPress:
                    (self.JsonView.undo if undo else self.JsonView.redo)()
                    self.TextData.setFocus()
                return True
        return super().eventFilter(watched, event)

    @pyqtSlot()
    @trace_operation
    def parse_json(self) -> None:
        string_data = str()

        for item in self.JsonView.root.get_children():
            if not item.childCount():
                continue

            try:
                string_data = string_data + self.parser.join_complex_item(item)
            except Exception as parsing_error:
                logger.error(f"JSON parsing error: {parsing_error}")
                return

        self.TextData.setText(string_data)

    @pyqtSlot()
    @trace_operation
    def get_from_main_window(self):
        try:
            field_number = self.get_field_number()
        except LookupError as lookup_error:
            logger.error(lookup_error)
            return

        try:
            if not (transaction := self.terminal.parse_main_window_tab()):
                raise LookupError("Missing transaction data")

        except Exception as window_parsing_error:
            logger.error(window_parsing_error)
            return

        if not (field_data := transaction.data_fields.get(field_number)):
            logger.error("Missing field data")
            return

        if isinstance(field_data, dict):
            try:
                field_data: str = Parser.join_complex_field(field_number, field_data)
            except Exception as parsing_error:
                logger.error(parsing_error)
                return

        self.TextData.setText(field_data)

        self.parse_string()

        logger.info(f"Field {field_number} data loaded from main window")

    @pyqtSlot()
    @trace_operation
    def parse_string(self) -> None:
        if TextConstants.HELLO_MESSAGE in self.TextData.toPlainText():
            return

        try:
            field_number = self.get_field_number()
        except LookupError as lookup_error:
            logger.error(lookup_error)
            return

        if not (field_data := self.TextData.toPlainText()):
            return

        try:
            field_data = self.parse_json_data(field_data)
        except Exception as parsing_error:
            logger.error(parsing_error)
            return

        field_data = field_data.replace("\n", "")

        try:
            json_data = Parser.split_complex_field(field_number, field_data)
        except Exception as parsing_error:
            logger.error(f"String parsing error: {parsing_error}")
            self.JsonView.clean()
            return

        json_data = {field_number: json_data}

        self.JsonView.clean()
        self.JsonView.parse_fields(json_data)

    def parse_json_data(self, data: str):

        try:
            json_data: dict = loads(data)
        except JSONDecodeError:
            return data

        if not isinstance(json_data, dict):
            return str(data)

        field_number = self.get_field_number()

        if not (json_body := json_data.get(field_number)):
            return data

        try:
            field_data: str = Parser.join_complex_field(field_number, json_body)
        except Exception as parsing_error:
            logger.error(f"Cannot set JSON data: {parsing_error}")
            return data

        return field_data

    def get_field_number(self) -> str:
        field_number = self.FieldNumber.currentText()

        if not (field_number := search(r"^\d{1,3}", field_number)):
            raise LookupError("Cannot get field number")

        field_number = field_number.group()

        return field_number

    def drop_field_files(self, files):
        from pathlib import Path
        for filename in files:
            try:
                self.drop_field_text(Path(filename).read_text(encoding='utf-8-sig'))
            except Exception as error:
                logger.error(f'Field file parsing error: {error}')

    def drop_field_text(self, text):
        try:
            text = text.lstrip('\ufeff').strip()
            field = self.get_field_number()
            try:
                data = loads(text)
            except JSONDecodeError:
                data = None
            if isinstance(data, dict) and 'message_type' not in data and 'transaction' not in data:
                value = data.get(field, data)
            else:
                try:
                    transaction = self.parser.parse_text(text)
                except Exception:
                    if data is not None or text.startswith('['):
                        raise
                    value = Parser.split_complex_field(field, text.replace('\n', '').replace('\r', ''))
                else:
                    value = transaction.data_fields[field]
            if isinstance(value, str):
                value = Parser.split_complex_field(field, value)
            packed = Parser.join_complex_field(field, value)
        except Exception as error:
            logger.error(f'Field text parsing error: {error}')
            return
        def apply():
            self.JsonView.clean()
            self.JsonView.parse_fields({field: value})
            self.TextData.setPlainText(packed)
        self.history_action(apply, 'Drop field text')
