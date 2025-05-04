from copy import deepcopy
from loguru import logger
from PyQt6.QtCore import pyqtSignal, QModelIndex
from PyQt6.QtWidgets import QTreeWidgetItem, QItemDelegate, QLineEdit
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.core.FieldsGenerator import FieldsGenerator
from common.lib.core.Parser import Parser
from common.lib.exceptions.exceptions import DataValidationError, DataValidationWarning
from common.lib.data_models.Transaction import Transaction, TypeFields
from common.lib.data_models.Config import Config
from common.lib.data_models.Types import FieldPath
from common.lib.data_models.EpaySpecificationModel import RawFieldSet
from common.gui.core.json_items.FIeldItem import FieldItem
from common.gui.core.validators.ItemsValidator import ItemsValidator
from common.gui.core.json_views.TreeView import TreeView
from common.gui.decorators.void_qt_signals import void_qt_signals
from common.gui.enums.CheckBoxesDefinition import CheckBoxesDefinition
from common.gui.enums.Colors import Colors
from common.gui.enums import MainFieldSpec as FieldsSpec
from common.gui.enums.RootItemNames import RootItemNames
from common.lib.toolkit.generate_trans_id import generate_trans_id


class JsonView(TreeView):
    class Delegate(QItemDelegate):
        _text_edited: pyqtSignal = pyqtSignal(str, int)

        @property
        def text_edited(self):
            return self._text_edited

        def setEditorData(self, editor: QLineEdit, index: QModelIndex):
            editor.textEdited.connect(lambda text: self.text_edited.emit(text, index.column()))
            QItemDelegate.setEditorData(self, editor, index)

    root: FieldItem
    need_disable_next_level: pyqtSignal = pyqtSignal()
    need_enable_next_level: pyqtSignal = pyqtSignal()
    trans_id_set: pyqtSignal = pyqtSignal()
    spec: EpaySpecification = EpaySpecification()

    @property
    def len_fill(self):
        return 3 if not self.config.specification.manual_input_mode else None

    @property
    def hide_secret_fields(self):
        return self.config.fields.hide_secrets

    def __init__(self, config: Config, root_name: str = RootItemNames.TRANSACTION_ROOT_NAME, parent=None):
        super(JsonView, self).__init__(parent=parent)
        self.root: FieldItem = FieldItem([root_name])
        self.config: Config = config
        self.delegate = JsonView.Delegate()
        self.validator = ItemsValidator(self.config)
        self.parser = Parser(self.config)
        self._setup()

    def _setup(self):
        self.setTabKeyNavigation(True)
        self.setAnimated(True)
        self.itemDoubleClicked.connect(self.editItem)
        self.itemChanged.connect(self.process_change_item)
        self.itemChanged.connect(self.disable_next_level)
        self.delegate.closeEditor.connect(lambda: self.hide_secrets())
        self.delegate.closeEditor.connect(lambda: self.set_all_items_length())
        self.delegate.text_edited.connect(self.set_item_length)
        self.currentItemChanged.connect(self.disable_next_level)
        self.setItemDelegate(self.delegate)
        self.setHeaderLabels(FieldsSpec.Columns)
        self.addTopLevelItem(self.root)
        self.header().setMaximumSectionSize(700)
        self.header().resizeSection(FieldsSpec.ColumnsOrder.DESCRIPTION, 470)
        self.make_order()

    def check_validation_config(function: callable):
        """
        This decorator check the configuration before validate FieldItem. If the validation is not activated
        the function will return None

        Keyword argument "force" has a priority. When force=True validation will be performed not depending on config
        """

        def wrapper(self, *args, **kwargs):
            validation_conditions = (
                kwargs.get("force"),
                self.config.validation.validation_enabled and self.config.validation.validate_window,
            )

            if not any(validation_conditions):
                return

            return function(self, *args, **kwargs)

        return wrapper

    def search(self, text: str, parent: FieldItem | None = None) -> None:
        TreeView.search(self, text, parent)

        if text == str():
            self.resize_all()

    @void_qt_signals
    def set_item_length(self, text, column):
        item: QTreeWidgetItem | FieldItem

        if not (item := self.currentItem()):
            return

        if item.childCount():
            return

        if column not in (FieldsSpec.ColumnsOrder.VALUE, FieldsSpec.ColumnsOrder.LENGTH):
            return

        if column == FieldsSpec.ColumnsOrder.LENGTH and not self.config.specification.manual_input_mode:
            return

        item.set_length(len(text), fill_length=self.len_fill)

    def set_all_items_length(self, parent: FieldItem | None = None):
        if parent is None:
            parent = self.root

        child_item: FieldItem

        for child_item in parent.get_children():
            if child_item.childCount():
                self.set_all_items_length(child_item)

            if not child_item.field_length.isdigit():
                continue

            child_item.set_length(fill_length=self.len_fill)

    def refresh_fields(self, parent: FieldItem | None = None, color: Colors | None = None):
        if parent is None:
            parent = self.root

        child_item: FieldItem

        for child_item in parent.get_children():
            if child_item.childCount():
                self.refresh_fields(parent=child_item, color=color)
                continue

            self.set_item_description(child_item)

            if color is not None:
                child_item.set_item_color(color)

        self.set_all_items_length(self.root)

    def hide_secrets(self, parent=None):
        if parent is None:
            parent = self.root

        child: FieldItem

        for child in parent.get_children():
            if child.childCount():
                self.hide_secrets(parent=child)

            child.hide_secret()

    def disable_next_level(self, item: FieldItem):  # Disable button NextLevel in case when flat-mode active
        current_item: FieldItem

        if not (current_item := self.currentItem()):
            current_item: FieldItem = item

        exemptions = [
            item.get_field_depth() != 1,
            not self.spec.is_field_complex(item.get_field_path()),
            item.checkbox_checked(CheckBoxesDefinition.JSON_MODE) and item is current_item,
            current_item.checkbox_checked(CheckBoxesDefinition.JSON_MODE),
            not self.spec.is_field_complex(current_item.get_field_path())
        ]

        signal = self.need_enable_next_level if any(exemptions) else self.need_disable_next_level
        signal.emit()

        if self.currentItem():
            return

        self.setCurrentItem(item)

    def editItem(self, item: FieldItem, column: int):
        if item is self.root:
            return

        if column not in (FieldsSpec.ColumnsOrder.FIELD, FieldsSpec.ColumnsOrder.VALUE, FieldsSpec.ColumnsOrder.LENGTH):
            return

        if column == FieldsSpec.ColumnsOrder.LENGTH and not self.config.specification.manual_input_mode:
            return

        if column == FieldsSpec.ColumnsOrder.VALUE:
            if item.childCount():
                return

            item.hide_secret(False)

        if column == FieldsSpec.ColumnsOrder.LENGTH and item.spec:
            return

        TreeView.editItem(self, item, column)

    def generate_item_data(self, item):
        if not item.checkbox_checked(CheckBoxesDefinition.GENERATE):
            return

        if item.is_trans_id:
            item.field_data = generate_trans_id()
            self.trans_id_set.emit()
            item.set_length()
            return

        item.field_data = FieldsGenerator.generate_field(item.field_number, self.config.fields.max_amount)

    def process_change_property(self, item: FieldItem) -> None:
        try:
            checkbox_type: str = self.itemWidget(item, FieldsSpec.ColumnsOrder.PROPERTY).text()
        except AttributeError | ValueError:
            return

        match checkbox_type:
            case CheckBoxesDefinition.JSON_MODE:
                if item.checkbox_checked(checkbox_type):
                    self.set_json_mode(item)
                    return

                self.set_flat_mode(item)

            case CheckBoxesDefinition.GENERATE:
                item.set_length(fill_length=self.len_fill)

                if not item.checkbox_checked(checkbox_type):
                    return

                item.set_item_color(Colors.BLACK)

    def get_trans_id(self) -> str | None:
        if not (field_item := self.get_trans_id_item()):
            return

        if not field_item.is_trans_id:
            return

        if field_item.checkbox_checked(CheckBoxesDefinition.GENERATE):
            trans_id = generate_trans_id()
            self.set_trans_id(trans_id)
            return trans_id

        return field_item.field_data

    @void_qt_signals
    def set_trans_id(self, trans_id: str):
        if not (field_item := self.get_trans_id_item()):
            return

        if spec := field_item.get_field_spec():
            if len(trans_id) > spec.max_length or len(trans_id) < spec.min_length:
                logger.warning("Invalid trans ID")
                return

        field_item.field_data = trans_id

    def get_item_by_path(self, field_path: FieldPath, parent: FieldItem | None = None) -> FieldItem | None:
        if parent is None:
            parent = self.root

        item: FieldItem | None = None
        child: FieldItem

        for child in parent.get_children():
            if item is not None:
                break

            if child.childCount():
                item = self.get_item_by_path(field_path=field_path, parent=child)
                continue

            if child.get_field_path() == field_path:
                item = child

        return item

    def get_trans_id_item(self) -> FieldItem | None:
        trans_id_path: FieldPath = self.spec.get_trans_id_path()
        trans_id_item: FieldItem = self.get_item_by_path(trans_id_path)

        return trans_id_item

    def set_subfields_length(self, item: FieldItem):
        parent: FieldItem
        child_item: FieldItem

        if not (parent := item.parent()):
            return

        if parent is self.root:
            return

        item_length: int = len(item.field_length)

        for child_item in parent.get_children():
            if child_item is item:
                continue

            if child_item.spec:
                continue

            child_length: int = len(child_item.field_length)

            if item_length > child_length:
                child_item.setText(FieldsSpec.ColumnsOrder.LENGTH, child_item.field_length.zfill(item_length))
                continue

            prefix: str = "0" * (child_length - item_length)

            child_item.setText(FieldsSpec.ColumnsOrder.LENGTH, child_item.field_length.removeprefix(prefix))

    @void_qt_signals
    def process_change_item(self, item: FieldItem, column):
        if item is self.root:
            return

        item.set_spec()

        validation_args = (item,)

        try:
            match column:
                case FieldsSpec.ColumnsOrder.VALUE:
                    self.generate_item_data(item)
                    self.modify_field_data(item)
                    item.is_new = False
                    self.validate_item(item)

                case FieldsSpec.ColumnsOrder.PROPERTY:
                    self.generate_item_data(item)
                    self.process_change_property(item)

                case FieldsSpec.ColumnsOrder.FIELD:
                    item.set_checkbox()
                    self.generate_item_data(item)
                    self.modify_field_data(item)
                    self.set_item_description(item)
                    self.resizeColumnToContents(FieldsSpec.ColumnsOrder.FIELD)

                    if item.is_new:
                        item.is_new = False
                        self.validate_field_number(item)
                    else:
                        self.validate_item(item)

                case FieldsSpec.ColumnsOrder.LENGTH:
                    self.set_subfields_length(item)

        except DataValidationError as validation_error:
            validation_args = (item, validation_error, logger.error)

        except DataValidationWarning as validation_warning:
            validation_args = (item, validation_warning, logger.warning)

        finally:
            self.set_validation_status(*validation_args)

    @check_validation_config
    def validate_field_number(self, item: FieldItem, force=False):
        self.validator.validate_field_number(item)

    @check_validation_config
    def validate_item(self, item: FieldItem, force=False):
        self.validator.validate_item(item)

    @void_qt_signals
    def set_item_description(self, item: FieldItem):
        try:
            item.set_spec()
        except Exception as set_spec_error:
            logger.debug(set_spec_error)

        if not self.spec.get_field_spec(item.get_field_path()):
            warn_text = f"⚠ ️No specification for field {item.get_field_path(string=True)}"

            if self.config.specification.manual_input_mode:
                warn_text = f"{warn_text}. set field length manually"

            item.set_description(warn_text)
            item.set_item_color(Colors.BLUE)
            return

        item.set_description()

        if not item.childCount():
            return

        for child in item.get_children():
            self.set_item_description(child)

    def set_validation_status(self, item: FieldItem, exception: Exception | None = None, level=logger.info):
        colors_map = {
            logger.error: Colors.RED,
            logger.warning: Colors.BLUE,
            logger.info: Colors.BLACK
        }

        item.set_item_color(colors_map.get(level, Colors.BLACK))

        if exception is None:
            return

        for string in str(exception).splitlines():
            level(f"Validation: {string}")

        self.setFocus()

    @void_qt_signals
    def check_all_items(self, parent: FieldItem = None, force=False):  # Validate and paint item, don't raise ValueError
        if not (self.config.validation.validation_enabled or force):
            return

        if parent is None:
            parent = self.root

        for child_item in parent.get_children():
            if child_item.childCount():
                self.check_all_items(child_item, force=force)
                continue

            validation_status_args = (child_item,)

            try:
                self.validate_item(child_item, force=force)

            except DataValidationError as validation_error:
                validation_status_args = (child_item, validation_error, logger.error,)

            except DataValidationWarning as validation_warning:
                validation_status_args = (child_item, validation_warning, logger.warning,)

            finally:
                self.set_validation_status(*validation_status_args)

    def plus(self):
        if not (current_item := self.currentItem()):
            return

        if not (parent := current_item.parent()):
            parent = self.root

        item = FieldItem([])
        index = parent.indexOfChild(current_item) + 1
        parent.insertChild(index, item)
        self.set_new_item(item)
        self.field_added.emit()

    @void_qt_signals
    def minus(self, *args):
        item: FieldItem | QTreeWidgetItem

        if not (item := self.currentItem()):
            return

        if item is self.root:
            self.setFocus()
            return

        if not (parent := item.parent()):
            return

        parent.removeChild(item)
        self.previousInFocusChain()
        parent.set_length(fill_length=self.len_fill)

        if not parent.childCount() and parent.field_number in self.spec.get_fields_to_generate():
            parent.set_checkbox()
            self.generate_item_data(parent)

        try:
            self.check_duplicates_after_remove(item, parent)
        except (DataValidationError, ValueError) as duplication_error:
            logger.error(duplication_error)

        self.setFocus()
        self.field_removed.emit()

    @void_qt_signals
    def next_level(self, *args):
        current_item: FieldItem | None = self.currentItem()

        if not current_item:
            return

        if current_item.get_field_depth() == 1:
            is_field_complex = self.spec.is_field_complex(current_item.get_field_path())

            if is_field_complex and not current_item.checkbox_checked(CheckBoxesDefinition.JSON_MODE):
                return

        item = FieldItem([])

        if current_item is None:
            return

        if current_item.checkbox_checked(CheckBoxesDefinition.GENERATE):
            current_item.remove_checkbox()

        current_item.hide_secret(False)
        current_item.setText(FieldsSpec.ColumnsOrder.VALUE, str())
        current_item.insertChild(int(), item)
        self.set_new_item(item)

    def set_new_item(self, item: FieldItem):
        self.setCurrentItem(item)
        self.scrollToItem(item)
        self.setFocus()
        self.editItem(item, int())

    def check_duplicates_after_remove(self, removed_item: FieldItem, parent_item: FieldItem):
        self.validator.validate_duplicates(removed_item, parent_item)

        for item in parent_item.get_children():
            if not item.field_number == removed_item.field_number:
                continue

            color = Colors.BLACK

            try:
                self.validator.validate_item(item)

            except (ValueError, DataValidationError) as duplication_error:
                color = Colors.RED
                raise duplication_error

            except DataValidationWarning as validation_warning:
                color = Colors.BLUE
                logger.warning(validation_warning)

            finally:
                item.set_item_color(color)

    def clean(self):
        TreeView.clean(self)
        self.root.set_length()

    @void_qt_signals
    def set_field_value(self, field, value):
        for item in self.root.get_children():
            if item.field_number != field:
                continue

            item.field_data = value

    def is_json_mode_on(self, field_path: FieldPath) -> bool | None:
        if not (json_mode_item := self.get_item_by_path(field_path)):
            return

        return json_mode_item.checkbox_checked(CheckBoxesDefinition.JSON_MODE)

    def is_trans_id_generate_mode_on(self) -> bool | None:
        if not (trans_id_item := self.get_trans_id_item()):
            return

        if not trans_id_item.is_trans_id:
            return

        if not trans_id_item.checkbox_checked(CheckBoxesDefinition.GENERATE):
            return False

        return True

    def parse_transaction(self, transaction: Transaction, to_generate_trans_id=True) -> None:
        for item in self.root.get_children():
            if not item.checkbox_checked(CheckBoxesDefinition.JSON_MODE):
                continue

            transaction.json_fields.append(item.field_number)

        self.clean()

        fields = deepcopy(transaction.data_fields)

        self.parse_fields(fields)
        self.set_checkboxes(transaction)
        self.check_all_items()

        for item in self.root.get_children():
            if item.checkbox_checked(CheckBoxesDefinition.JSON_MODE):
                self.set_json_mode(item)
                continue

            self.set_flat_mode(item)

        if trans_id_item := self.get_trans_id_item():
            trans_id_item.set_checkbox(to_generate_trans_id)

        self.set_all_items_length()

    def switch_json_mode(self, json_mode):
        for item in self.root.get_children():
            if not self.spec.is_field_complex(item.get_field_path()):
                continue

            item.set_checkbox(json_mode)

            if json_mode:
                self.set_json_mode(item)

            if not json_mode:
                self.set_flat_mode(item)

    def set_json_mode(self, item: FieldItem):
        parsing_error_text: str = "Cannot change JSON mode due to parsing error(s)"

        if item.childCount():
            return

        if not isinstance(item.field_data, str):
            return

        try:
            fields: RawFieldSet = Parser.split_complex_field(item.field_number, item.field_data)
            self.parse_fields(fields, parent=item, specification=self.spec.fields.get(item.field_number))

        except Exception as parsing_error:
            logger.error(f"{parsing_error_text}: {parsing_error}")
            item.set_checkbox(False)
            return

        item.field_data = ""

        self.check_all_items(item)
        self.hide_secrets(parent=item)
        self.setCurrentItem(item)

    def set_flat_mode(self, item):
        parsing_error_text: str = "Cannot change JSON mode due to parsing error(s)"

        if not item.childCount():
            return

        try:
            item.field_data = self.parser.join_complex_item(item)
            item.takeChildren()

        except Exception as parsing_error:
            logger.error(parsing_error_text)
            [logger.error(line) for line in str(parsing_error).splitlines()]
            item.set_checkbox()

        self.hide_secrets()

    @void_qt_signals
    def set_checkboxes(self, transaction: Transaction):
        generate_fields = self.spec.get_fields_to_generate()

        for item in self.root.get_children():
            is_checked = False

            if item.field_number in generate_fields:
                is_checked = item.field_number in transaction.generate_fields

            if self.spec.is_field_complex(item.get_field_path()):
                is_checked = self.config.fields.json_mode

                if item.field_number in transaction.json_fields:
                    is_checked = True

            item.set_checkbox(is_checked)

    def enable_json_mode_checkboxes(self, enable=True):
        item: FieldItem

        for item in self.root.get_children():
            if not (checkbox := item.get_checkbox()):
                continue

            if not checkbox.text() == CheckBoxesDefinition.JSON_MODE:
                continue

            checkbox.setEnabled(enable)

    def parse_fields(self, input_json: dict, parent: QTreeWidgetItem = None, specification=None):
        if parent is None:
            parent = self.root

        if specification is None:
            specification = self.spec.spec

        for field, field_data in input_json.items():
            try:
                field_spec = specification.fields.get(field)

            except AttributeError:
                logger.error(f"Cannot parse field {'.'.join(specification.field_path)}")
                child = FieldItem([field])
                child.field_data = str(field_data)
                parent.addChild(child, fill_len=self.len_fill)
                continue

            else:
                description = field_spec.description if field_spec else None

                if isinstance(field_data, dict):
                    child = FieldItem([field])
                    child.setText(FieldsSpec.ColumnsOrder.DESCRIPTION, description)
                    self.parse_fields(field_data, parent=child, specification=specification.fields.get(field))

                else:
                    field_data = self.validator.get_justified_field_data(field_spec, str(field_data))
                    string_data = [field, field_data, None, description]
                    child: FieldItem = FieldItem(string_data)

            parent.addChild(child, fill_len=self.len_fill)
            child.set_spec(field_spec)

        self.set_all_items_length()
        self.hide_secrets()
        self.make_order()

    def modify_all_fields_data(self):
        self.validator.modify_all_fields_data(self.root)
        self.setCurrentItem(self.root)

    def modify_field_data(self, item):
        if not self.config.validation.validate_window:
            return

        self.validator.modify_field_data(item)

    def get_top_level_field_numbers(self) -> list[str]:
        field_numbers: list[str] = list()

        for item in self.root.get_children():
            if item.field_data or bool(item.checkState(FieldsSpec.ColumnsOrder.PROPERTY)):
                field_numbers.append(item.field_number)

        return field_numbers

    def generate_fields(self, parent=None, flat: bool = False):
        result: TypeFields = dict()

        if parent is None:
            parent = self.root

        row: FieldItem

        for row in parent.get_children():
            if row.field_number in result:
                logger.warning(f"Duplicated field number {row.get_field_path(string=True)}")

            try:
                self.validator.validate_item(row)
            except DataValidationWarning:
                pass

            if row.childCount():
                if flat:
                    result[row.field_number] = self.parser.join_complex_item(row)
                else:
                    result[row.field_number] = self.generate_fields(row, flat=flat)

            if not row.childCount():
                result[row.field_number] = row.field_data

        if parent is self.root:
            try:
                fields = {field: result[field] for field in sorted(result, key=int)}
            except ValueError:
                logger.warning("Cannot sort top-level data fields, usually it happens due to non-digit field number")
                fields = result

            if not self.config.validation.validate_window:
                return fields

        return result

    def get_checkboxes(self, checkbox_type=CheckBoxesDefinition.GENERATE) -> list[str]:
        checkboxes = list()
        item: FieldItem

        for item in self.root.get_children():
            if not item.checkbox_checked(checkbox_type):
                continue

            checkboxes.append(item.field_number)

        return checkboxes

    def field_has_data(self, field_number: str, parent: FieldItem | None = None):
        if parent is None:
            parent = self.root

        item: FieldItem

        for item in parent.get_children():
            if item.field_number != field_number:
                continue

            return bool(int(item.get_field_length()))

        return False
