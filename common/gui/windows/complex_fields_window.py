from re import search
from json import dumps, loads
from json.decoder import JSONDecodeError
from loguru import logger
from dataclasses import asdict
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu, QDialog, QPushButton, QApplication
from common.lib.data_models.Config import Config
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.core.Parser import Parser
from common.lib.data_models.Transaction import Transaction
from common.gui.forms.complex_fields_parser import Ui_ComplexFieldsParser
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.gui.core.json_views.JsonView import JsonView
from common.gui.enums import ButtonActions, MainFieldSpec
from common.gui.enums.KeySequences import KeySequences
from common.gui.enums.RootItemNames import RootItemNames
from common.lib.enums.TextConstants import TextConstants


class ComplexFieldsParser(Ui_ComplexFieldsParser, QDialog):
    spec: EpaySpecification = EpaySpecification()

    def __init__(self, config: Config, terminal):
        super(ComplexFieldsParser, self).__init__()
        self.config: Config = config
        self.terminal = terminal
        self.parser = Parser(self.config)
        self.setupUi(self)
        self._setup()

    @set_window_icon
    @has_close_button_only
    def _setup(self):
        self.PlusButton: QPushButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_PLUS_SIGN)
        self.MinusButton: QPushButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_MINUS_SIGN)
        self.NextLevelButton: QPushButton = QPushButton(ButtonActions.ButtonActionSigns.BUTTON_NEXT_LEVEL_SIGN)
        self.UpButton: QPushButton = QPushButton(f"{ButtonActions.ButtonActionSigns.BUTTON_UP_SIGN} To JSON ")
        self.DownButton: QPushButton = QPushButton(f"{ButtonActions.ButtonActionSigns.BUTTON_DOWN_SIGN} To String ")
        self.JsonView: JsonView = JsonView(self.config, RootItemNames.FIELD_CONSTRUCTOR_ROOT_NAME)

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

        for button in self.PlusButton, self.MinusButton, self.NextLevelButton, self.UpButton, self.DownButton:
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        for field in asdict(self.spec.FIELD_SET).values():
            if not self.spec.is_field_complex([field]):
                continue

            description: str = self.spec.get_field_description([field], string=True)

            self.FieldNumber.addItem(f"{field} - {description}")

        button_menu_structure = {
            self.ButtonClearString: {
                ButtonActions.ClearMenuActions.ALL: self.clear_all,
                ButtonActions.ClearMenuActions.JSON: self.JsonView.clean,
                ButtonActions.ClearMenuActions.STRING: self.clear_string,
            },

            self.ButtonCopy: {
                ButtonActions.ClearMenuActions.JSON: self.copy_json,
                ButtonActions.ClearMenuActions.STRING: self.copy_string,
            },

            self.ButtonMainWindow: {
                ButtonActions.DataMenuActions.GET_DATA: self.get_from_main_window,
                ButtonActions.DataMenuActions.SET_DATA: self.set_on_main_windows,
            },
        }

        for button, actions in button_menu_structure.items():
            button.setMenu(QMenu())

            for action, function in actions.items():
                button.menu().addAction(action, function)
                button.menu().addSeparator()

        self.JsonView.hideColumn(MainFieldSpec.ColumnsOrder.PROPERTY)
        self.connect_all()
        self.set_field_data()

    def connect_all(self):
        button_connection_map = {
            self.ButtonClose: self.close,
            self.ButtonClearString: self.clear_string,
            self.UpButton: self.parse_string,
            self.DownButton: self.parse_json,
            self.PlusButton: self.JsonView.plus,
            self.MinusButton: self.JsonView.minus,
            self.NextLevelButton: self.JsonView.next_level,
        }

        general_connection_map = {
            self.SearchLine.textChanged: self.JsonView.search,
            self.SearchLine.editingFinished: self.JsonView.setFocus,
            self.FieldNumber.currentIndexChanged: self.set_field_data,
        }

        keys_connection_map = {
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

    def set_message(self, message: str | None = None):
        if message is None:
            message = TextConstants.HELLO_MESSAGE + "\n"

        self.TextData.setText(message)
        self.TextData.clearFocus()

    def set_field_data(self):
        self.JsonView.clean()
        self.get_from_main_window()

    def clear_string(self):
        self.TextData.setText(str())

    def copy_json(self):
        json_data: dict = self.get_json_data()
        json_data: str = dumps(json_data, indent=4)
        self.set_clipboard_text(json_data)
        logger.info("JSON copied to clipboard")

    def copy_string(self):
        self.set_clipboard_text(self.TextData.toPlainText())
        logger.info("String copied to clipboard")

    @staticmethod
    def set_clipboard_text(data: str = str()) -> None:
        QApplication.clipboard().setText(data)

    def set_on_main_windows(self):
        try:
            field_number = self.get_field_number()
        except LookupError as lookup_error:
            logger.error(lookup_error)
            return

        if not (json_data := self.get_json_data()):
            logger.error("No data to set")
            return

        if not (field_data := json_data.get(field_number)):
            logger.error("Lost field data")
            return

        transaction: Transaction = self.terminal.parse_main_window_tab()
        transaction.data_fields[field_number] = field_data

        self.terminal.parse_transaction(transaction)

        logger.info(f"Set field {field_number} data to MainWindow")

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

    def clear_all(self):
        self.JsonView.clean()
        self.clear_string()

    def parse_json(self):
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

    def get_from_main_window(self):
        try:
            field_number = self.get_field_number()
        except LookupError as lookup_error:
            logger.error(lookup_error)
            return

        try:
            if not (transaction := self.terminal.parse_main_window_tab()):
                raise LookupError("Lost transaction data")

        except Exception as window_parsing_error:
            logger.error(window_parsing_error)
            return

        if not (field_data := transaction.data_fields.get(field_number)):
            logger.error("Lost field data")
            return

        if isinstance(field_data, dict):
            try:
                field_data: str = Parser.join_complex_field(field_number, field_data)
            except Exception as parsing_error:
                logger.error(parsing_error)
                return

        self.TextData.setText(field_data)

        self.parse_string()

        logger.info(f"Got field {field_number} data from MainWindow")

    def parse_string(self):
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

    def get_field_number(self):
        field_number = self.FieldNumber.currentText()

        if not (field_number := search(r"^\d{1,3}", field_number)):
            raise LookupError("Cannot get field number")

        field_number = field_number.group()

        return field_number
