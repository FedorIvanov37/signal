from copy import deepcopy
from contextlib import suppress
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QListWidgetItem, QCheckBox, QLineEdit, QSpinBox
from common.gui.core.widgets.CheckableComboBox import CheckableComboBox
from common.gui.forms.field_validator_window import Ui_FieldDataSet
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.lib.data_models.EpaySpecificationModel import IsoField, Justification, LogicalValidators
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.enums.ValidationParams import LiteralValidations
from common.gui.enums.Colors import Colors
from common.gui.enums.FieldTypeParams import FieldTypeParams


class FieldDataSet(Ui_FieldDataSet, QDialog):
    spec: EpaySpecification = EpaySpecification()
    _field_spec: IsoField = None
    _literal_validations_map: dict
    _field_spec_accepted: pyqtSignal = pyqtSignal(IsoField)
    _field_type_checkboxes: dict[str, dict[str, QLineEdit | QCheckBox]] = {}

    @property
    def field_spec_accepted(self):
        return self._field_spec_accepted

    @property
    def field_spec(self):
        return self._field_spec

    def __init__(self, field_spec: IsoField):
        super(FieldDataSet, self).__init__()
        self._field_spec = deepcopy(field_spec)
        self.CheckTypeBox = CheckableComboBox()
        self.FieldType = CheckableComboBox()
        self.setupUi(self)
        self.setup()

    @set_window_icon
    @has_close_button_only
    def setup(self):
        self._literal_validations_map = {
            LiteralValidations.MUST_CONTAIN: self.field_spec.validators.must_contain,
            LiteralValidations.MUST_CONTAIN_ONLY: self.field_spec.validators.must_contain_only,
            LiteralValidations.MUST_NOT_CONTAIN: self.field_spec.validators.must_not_contain,
            LiteralValidations.MUST_NOT_CONTAIN_ONLY: self.field_spec.validators.must_not_contain_only,
            LiteralValidations.MUST_START_WITH: self.field_spec.validators.must_start_with,
            LiteralValidations.MUST_NOT_START_WITH: self.field_spec.validators.must_not_start_with,
            LiteralValidations.MUST_END_WITH: self.field_spec.validators.must_end_with,
            LiteralValidations.MUST_NOT_END_WITH: self.field_spec.validators.must_not_end_with,
            LiteralValidations.VALID_VALUES: self.field_spec.validators.valid_values,
            LiteralValidations.INVALID_VALUES: self.field_spec.validators.invalid_values,
        }

        palette = QPalette()
        palette.setColor(palette.ColorRole.AlternateBase, QColor(Colors.LIGHT_GREY))
        self.ValuesList.setPalette(palette)
        self.CheckTypeLayout.addWidget(self.CheckTypeBox)
        self.FieldTypeBoxLayout.addWidget(self.FieldType)
        self.CheckBoxGeneratible.setDisabled(True)
        self.process_fill_size_change()
        self.create_field_type_checkboxes()
        self.parse_field_spec()
        self.process_justification_change()
        self.process_field_type_change()
        self.process_field_type_element_change()
        self.process_check_type_change()
        self.connect_all()

        for combo_box in self.CheckTypeBox, self.FieldType:
            combo_box.set_active_index()

    def connect_all(self):
        connection_map = {
            self.FillSide.currentIndexChanged: self.process_justification_change,
            self.FieldType.currentIndexChanged: self.process_field_type_change,
            self.CheckTypeBox.currentIndexChanged: self.process_check_type_change,
            self.ValuesList.itemChanged: self.mark_all_check_types,
            self.CancelButton.clicked: self.reject,
            self.PlusButton.clicked: self.plus,
            self.MinusButton.clicked: self.minus,
            self.ButtonClear.clicked: self.clear_validation,
            self.ButtonClearAll.clicked: self.clear_all_validations,
            self.FillUpTo.currentIndexChanged: self.process_fill_size_change,
            self.FillUpTo.currentTextChanged: self.process_fill_size_text_change,
            self.OkButton.clicked: self.ok,
            self.CheckBoxGeneratible.stateChanged: self.set_generate,
        }

        for signal, slot in connection_map.items():
            signal.connect(slot)

        for elements in self._field_type_checkboxes.values():
            for element in elements.values():
                signal: pyqtSignal | None = None

                if isinstance(element, QCheckBox):
                    signal = element.stateChanged

                if isinstance(element, QLineEdit):
                    signal = element.textChanged

                if signal is None:
                    continue

                signal.connect(self.process_field_type_element_change)

    def ok(self):
        self.prepare_field_spec(self.field_spec)
        self.field_spec_accepted.emit(self.field_spec)
        self.accept()

    def process_fill_size_text_change(self, text: str):
        if text.lower() == Justification.CUSTOM.value.lower():
            self.FillUpTo.setCurrentText(str())

    def process_fill_size_change(self):
        self.FillUpTo.setEditable(self.FillUpTo.currentText().lower() == Justification.CUSTOM.value.lower())
        self.process_fill_size_text_change(self.FillUpTo.currentText())

    def clear_all_validations(self):
        self.clear_validation()

        for check_type in self._literal_validations_map:
            self._literal_validations_map[check_type] = list()

        self.mark_all_check_types()

    def clear_validation(self):
        for index in range(self.ValuesList.count()):
            self.ValuesList.takeItem(int())

        self.CheckTypeBox.set_validation_mark(mark=False, item=self.CheckTypeBox.currentIndex())

    def create_field_type_checkboxes(self):
        self._field_type_checkboxes = {
            FieldTypeParams.COUNTRY: {
                FieldTypeParams.COUNTRY_CODE_N3: QCheckBox(FieldTypeParams.COUNTRY_CODE_N3),
                FieldTypeParams.COUNTRY_CODE_A3: QCheckBox(FieldTypeParams.COUNTRY_CODE_A3),
                FieldTypeParams.COUNTRY_CODE_A2: QCheckBox(FieldTypeParams.COUNTRY_CODE_A2),
            },

            FieldTypeParams.CURRENCY: {
                FieldTypeParams.CURRENCY_CODE_A3: QCheckBox(FieldTypeParams.CURRENCY_CODE_A3),
                FieldTypeParams.CURRENCY_CODE_N3: QCheckBox(FieldTypeParams.CURRENCY_CODE_N3),
            },

            FieldTypeParams.MERCHANT_CATEGORY_CODE: {
                FieldTypeParams.MCC_ISO: QCheckBox(FieldTypeParams.MCC_ISO),
            },

            FieldTypeParams.DATE: {
                FieldTypeParams.DATE_FORMAT: QLineEdit(),
                FieldTypeParams.PAST_TIME: QCheckBox(FieldTypeParams.PAST_TIME),
                FieldTypeParams.PRESENT_TIME: QCheckBox(FieldTypeParams.PRESENT_TIME),
                FieldTypeParams.FUTURE_TIME: QCheckBox(FieldTypeParams.FUTURE_TIME),
            },

            FieldTypeParams.OTHER: {
                FieldTypeParams.CHECK_LUHN: QCheckBox(FieldTypeParams.CHECK_LUHN),
                FieldTypeParams.UPPERCASE: QCheckBox(FieldTypeParams.UPPERCASE),
                FieldTypeParams.LOWERCASE: QCheckBox(FieldTypeParams.LOWERCASE),
                FieldTypeParams.TO_UPPERCASE: QCheckBox(FieldTypeParams.TO_UPPERCASE),
                FieldTypeParams.TO_LOWERCASE: QCheckBox(FieldTypeParams.TO_LOWERCASE),
                FieldTypeParams.IGNORE_VALIDATIONS: QCheckBox(FieldTypeParams.IGNORE_VALIDATIONS),
            }
        }

        with suppress(KeyError):
            field_date: dict = self._field_type_checkboxes[FieldTypeParams.DATE]
            line_date: QLineEdit = field_date[FieldTypeParams.DATE_FORMAT]
            line_date.setPlaceholderText(FieldTypeParams.DATE_FORMAT)

        for field_type, widgets in self._field_type_checkboxes.items():
            self.FieldType.addItem(field_type)
            self.FieldType.set_validation_mark(mark=False, item=self.FieldType.count() -1)

            for widget in widgets.values():
                self.FieldTypeLayout.addWidget(widget)

        self.hide_field_type_widgets()

    def process_field_type_element_change(self):
        for field_type, elements in self._field_type_checkboxes.items():

            item_index = self.FieldType.findText(field_type)

            self.FieldType.set_validation_mark(mark=False, item=item_index)

            for element in elements.values():
                mark: bool | None = None

                if isinstance(element, QCheckBox) and element.isChecked():
                    mark = True

                if isinstance(element, QLineEdit) and element.text():
                    mark = True

                if mark is None:
                    continue

                self.FieldType.set_validation_mark(mark=mark, item=item_index)
                break

    def process_field_type_change(self):
        self.hide_field_type_widgets()

        if not (field_type := self.FieldType.currentText()):
            return

        if not (widgets := self._field_type_checkboxes.get(field_type)):
            return

        for widget in widgets.values():
            widget.show()

    def hide_field_type_widgets(self):
        for widgets in self._field_type_checkboxes.values():
            for widget in widgets.values():
                widget.hide()

    def prepare_field_spec(self, field_spec: IsoField | None = None) -> IsoField:
        if field_spec is None:
            field_spec = self.field_spec

        self.save_validations()

        field_spec.min_length = self.MinLength.value()
        field_spec.max_length = self.MaxLength.value()
        field_spec.tag_length = self.TagLength.value()
        field_spec.var_length = self.DataLength.value()

        field_spec.alpha = self.CheckBoxAlpha.isChecked()
        field_spec.numeric = self.CheckBoxNumeric.isChecked()
        field_spec.special = self.CheckBoxSpecial.isChecked()
        field_spec.matching = self.CheckBoxMatching.isChecked()
        field_spec.reversal = self.CheckBoxReversal.isChecked()
        field_spec.generate = self.CheckBoxGeneratible.isChecked()
        field_spec.is_secret = self.CheckBoxSecret.isChecked()

        field_spec.validators.justification_length = int()
        field_spec.validators.justification_element = None
        field_spec.validators.justification = None

        if self.FillSide.currentText() != FieldTypeParams.JUSTIFICATION_NONE:
            if self.FillUpTo.currentText() == FieldTypeParams.JUSTIFICATION_MIN_LEN:
                field_spec.validators.justification_length = field_spec.min_length

            if self.FillUpTo.currentText() == FieldTypeParams.JUSTIFICATION_MAX_LEN:
                field_spec.validators.justification_length = field_spec.max_length

            if self.FillUpTo.currentText().isdigit():
                field_spec.validators.justification_length = int(self.FillUpTo.currentText())

            if self.FillSide.currentText() == FieldTypeParams.JUSTIFICATION_LEFT:
                field_spec.validators.justification = Justification.LEFT

            if self.FillSide.currentText() == FieldTypeParams.JUSTIFICATION_RIGHT:
                field_spec.validators.justification = Justification.RIGHT

            if self.FillSymbol.text():
                field_spec.validators.justification_element = self.FillSymbol.text()

        logical_validators = LogicalValidators()

        for check_type in (
            FieldTypeParams.CURRENCY,
            FieldTypeParams.COUNTRY,
            FieldTypeParams.MCC,
            FieldTypeParams.DATE,
            FieldTypeParams.OTHER
        ):

            if not (validation_dict := self._field_type_checkboxes.get(check_type)):
                continue

            checkbox: QCheckBox = QCheckBox()
            lineedit: QLineEdit = QLineEdit()

            match check_type:
                case FieldTypeParams.CURRENCY:
                    logical_validators.currency_n3 = validation_dict.get(FieldTypeParams.CURRENCY_CODE_N3, checkbox).isChecked()
                    logical_validators.currency_a3 = validation_dict.get(FieldTypeParams.CURRENCY_CODE_A3, checkbox).isChecked()

                case FieldTypeParams.COUNTRY:
                    logical_validators.country_a2 = validation_dict.get(FieldTypeParams.COUNTRY_CODE_A2, checkbox).isChecked()
                    logical_validators.country_a3 = validation_dict.get(FieldTypeParams.COUNTRY_CODE_A3, checkbox).isChecked()
                    logical_validators.country_n3 = validation_dict.get(FieldTypeParams.COUNTRY_CODE_N3, checkbox).isChecked()

                case FieldTypeParams.MCC:
                    logical_validators.mcc = validation_dict.get(FieldTypeParams.MCC_ISO, checkbox).isChecked()

                case FieldTypeParams.DATE:
                    logical_validators.date_format = validation_dict.get(FieldTypeParams.DATE_FORMAT, lineedit).text()
                    logical_validators.future = validation_dict.get(FieldTypeParams.FUTURE_TIME, checkbox).isChecked()
                    logical_validators.present = validation_dict.get(FieldTypeParams.PRESENT_TIME, checkbox).isChecked()
                    logical_validators.past = validation_dict.get(FieldTypeParams.PAST_TIME, checkbox).isChecked()

                case FieldTypeParams.OTHER:
                    logical_validators.check_luhn = validation_dict.get(FieldTypeParams.CHECK_LUHN, checkbox).isChecked()
                    logical_validators.only_upper = validation_dict.get(FieldTypeParams.UPPERCASE, checkbox).isChecked()
                    logical_validators.only_lower = validation_dict.get(FieldTypeParams.LOWERCASE, checkbox).isChecked()
                    logical_validators.change_to_upper = validation_dict.get(FieldTypeParams.TO_UPPERCASE, checkbox).isChecked()
                    logical_validators.change_to_lower = validation_dict.get(FieldTypeParams.TO_LOWERCASE, checkbox).isChecked()
                    logical_validators.do_not_validate = validation_dict.get(FieldTypeParams.IGNORE_VALIDATIONS, checkbox).isChecked()

        field_spec.validators.field_type_validators = logical_validators

        return field_spec

    def set_generate(self):
        with suppress(AttributeError):
            self.CheckBoxGeneratible.setCheckState(
                Qt.CheckState.Checked if self.field_spec.generate else Qt.CheckState.Unchecked
            )

    def set_justification_simbols(self):
        self.field_spec.validators.justification_element = self.FillSymbol.text()

    def mark_all_check_types(self):
        self.save_validations()

        for item_index in range(self.CheckTypeBox.count()):
            if not self._literal_validations_map.get(self.CheckTypeBox.itemText(item_index)):
                self.CheckTypeBox.set_validation_mark(mark=False, item=item_index)
                continue

            self.CheckTypeBox.set_validation_mark(mark=True, item=item_index)

    def process_check_type_change(self):
        if previous_check_type := self.CheckTypeBox.get_previous_text():
            self.save_validations(previous_check_type)

        current_check_type: str = self.CheckTypeBox.currentText()

        self.set_validation_items(current_check_type)
        self.mark_all_check_types()
        self.ValuesList.setFocus()

    def save_validations(self, check_type: str | None = None):
        if check_type is None:
            check_type = self.CheckTypeBox.currentText()

        check_list = list[str]
        validations_map: dict[str, check_list] = self._literal_validations_map

        literal_list: check_list = [self.ValuesList.item(row).text() for row in range(self.ValuesList.count())]
        literal_list: check_list = list(set(literal_list))

        with suppress(ValueError):  # When no empty strings in literal_list
            literal_list.remove(str())

        validations_map[check_type] = literal_list

        self.field_spec.validators.must_contain = validations_map.get(LiteralValidations.MUST_CONTAIN)
        self.field_spec.validators.must_contain_only = validations_map.get(LiteralValidations.MUST_CONTAIN_ONLY)
        self.field_spec.validators.must_not_contain = validations_map.get(LiteralValidations.MUST_NOT_CONTAIN)
        self.field_spec.validators.must_not_contain_only = validations_map.get(LiteralValidations.MUST_NOT_CONTAIN_ONLY)
        self.field_spec.validators.must_start_with = validations_map.get(LiteralValidations.MUST_START_WITH)
        self.field_spec.validators.must_not_start_with = validations_map.get(LiteralValidations.MUST_NOT_START_WITH)
        self.field_spec.validators.must_end_with = validations_map.get(LiteralValidations.MUST_END_WITH)
        self.field_spec.validators.must_not_end_with = validations_map.get(LiteralValidations.MUST_NOT_END_WITH)
        self.field_spec.validators.valid_values = validations_map.get(LiteralValidations.VALID_VALUES)
        self.field_spec.validators.invalid_values = validations_map.get(LiteralValidations.INVALID_VALUES)

    def set_validation_items(self, check_type):
        if (validation_list := self._literal_validations_map.get(check_type)) is None:
            return

        self.clear_validation()

        if not validation_list:
            return

        for literal in validation_list:
            self.add_validation_value(literal)

    def minus(self):
        self.ValuesList.setFocus()

        if not (item := self.ValuesList.currentItem()):
            return

        self.ValuesList.takeItem(self.ValuesList.row(item))
        self.save_validations()
        self.mark_all_check_types()

    def plus(self):
        item: QListWidgetItem = self.add_validation_value()
        self.ValuesList.editItem(item)

    def set_validator_mark(self):
        values_count = len([row for row in range(self.ValuesList.count()) if self.ValuesList.item(row).text() != str()])
        validation_mark: bool = bool(values_count)
        self.CheckTypeBox.set_validation_mark(mark=validation_mark)

    def add_validation_value(self, value_data: str | None = None) -> QListWidgetItem:
        value_data: str = str() if value_data is None else value_data
        item: QListWidgetItem = QListWidgetItem(value_data)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
        self.ValuesList.addItem(item)
        return item

    def parse_field_spec(self, iso_field: IsoField | None = None):
        if iso_field is None:
            iso_field: IsoField = self.field_spec

        field_desc: str = self.spec.get_field_description(iso_field.field_path, string=True)
        field_path: str = ".".join(iso_field.field_path)

        self.FillSide.setCurrentText(iso_field.validators.justification)

        if not iso_field.validators.justification:
            self.FillSide.setCurrentText(FieldTypeParams.JUSTIFICATION_NONE)

        self.FieldDescription.setText(f"Field {field_path}  - {field_desc}")

        checkbox_property_map: dict[QCheckBox, bool] = {
            self.CheckBoxAlpha: iso_field.alpha,
            self.CheckBoxNumeric: iso_field.numeric,
            self.CheckBoxSpecial: iso_field.special,
            self.CheckBoxMatching: iso_field.matching,
            self.CheckBoxReversal: iso_field.reversal,
            self.CheckBoxGeneratible: iso_field.generate,
            self.CheckBoxSecret: iso_field.is_secret,
        }

        length_property_map: dict[QSpinBox, int] = {
            self.MinLength: iso_field.min_length,
            self.MaxLength: iso_field.max_length,
            self.DataLength: iso_field.var_length,
            self.TagLength: iso_field.tag_length,
        }

        for length, field_property in length_property_map.items():
            length.setValue(field_property)

        for checkbox, field_property in checkbox_property_map.items():
            checkbox.setChecked(field_property)

        if checkbox_property_map.get(self.CheckBoxGeneratible):
            self.CheckBoxGeneratible.setChecked(True)

        for check_type, values in self._literal_validations_map.items():
            self.CheckTypeBox.addItem(check_type)

        for field_type, field_type_values in self._field_type_checkboxes.items():
            try:
                match field_type:
                    case FieldTypeParams.COUNTRY:
                        field_type_values[FieldTypeParams.COUNTRY_CODE_N3].setChecked(iso_field.validators.field_type_validators.country_n3)
                        field_type_values[FieldTypeParams.COUNTRY_CODE_A3].setChecked(iso_field.validators.field_type_validators.country_a3)
                        field_type_values[FieldTypeParams.COUNTRY_CODE_A2].setChecked(iso_field.validators.field_type_validators.country_a2)

                    case FieldTypeParams.CURRENCY:
                        field_type_values[FieldTypeParams.CURRENCY_CODE_A3].setChecked(iso_field.validators.field_type_validators.currency_a3)
                        field_type_values[FieldTypeParams.CURRENCY_CODE_N3].setChecked(iso_field.validators.field_type_validators.currency_n3)

                    case FieldTypeParams.MERCHANT_CATEGORY_CODE:
                        field_type_values[FieldTypeParams.MCC_ISO].setChecked(iso_field.validators.field_type_validators.mcc)

                    case FieldTypeParams.DATE:
                        field_type_values[FieldTypeParams.DATE_FORMAT].setText(iso_field.validators.field_type_validators.date_format)
                        field_type_values[FieldTypeParams.PAST_TIME].setChecked(iso_field.validators.field_type_validators.past)
                        field_type_values[FieldTypeParams.PRESENT_TIME].setChecked(iso_field.validators.field_type_validators.present)
                        field_type_values[FieldTypeParams.FUTURE_TIME].setChecked(iso_field.validators.field_type_validators.future)

                    case FieldTypeParams.OTHER:
                        field_type_values[FieldTypeParams.CHECK_LUHN].setChecked(iso_field.validators.field_type_validators.check_luhn)
                        field_type_values[FieldTypeParams.UPPERCASE].setChecked(iso_field.validators.field_type_validators.only_upper)
                        field_type_values[FieldTypeParams.LOWERCASE].setChecked(iso_field.validators.field_type_validators.only_lower)
                        field_type_values[FieldTypeParams.TO_UPPERCASE].setChecked(iso_field.validators.field_type_validators.change_to_upper)
                        field_type_values[FieldTypeParams.TO_LOWERCASE].setChecked(iso_field.validators.field_type_validators.change_to_lower)
                        field_type_values[FieldTypeParams.IGNORE_VALIDATIONS].setChecked(iso_field.validators.field_type_validators.do_not_validate)

            except KeyError | AttributeError:
                continue

        if self.field_spec.field_number == self.spec.FIELD_SET.FIELD_002_PRIMARY_ACCOUNT_NUMBER:
            self.CheckBoxSecret.setCheckState(Qt.CheckState.Checked)
            self.CheckBoxSecret.setDisabled(True)
            self.CheckBoxSecret.stateChanged.connect(lambda: self.CheckBoxSecret.setCheckState(Qt.CheckState.Checked))
            self.CheckBoxSecret.setText(f"Hide value (required for PAN)")

        self.set_validation_items(self.CheckTypeBox.currentText())

        if iso_field.validators.justification is None:
            self.FillSide.setCurrentText(FieldTypeParams.JUSTIFICATION_NONE)
            return

        if iso_field.validators.justification == Justification.RIGHT:
            self.FillSide.setCurrentText(FieldTypeParams.JUSTIFICATION_RIGHT)

        if iso_field.validators.justification == Justification.LEFT:
            self.FillSide.setCurrentText(FieldTypeParams.JUSTIFICATION_LEFT)

        self.FillUpTo.setCurrentText(str(iso_field.validators.justification_length))
        self.FillSymbol.setText(iso_field.validators.justification_element)

        if iso_field.validators.justification_length == iso_field.max_length:
            self.FillUpTo.setCurrentText(FieldTypeParams.JUSTIFICATION_MAX_LEN)
            return

        if iso_field.validators.justification_length == iso_field.min_length:
            self.FillUpTo.setCurrentText(FieldTypeParams.JUSTIFICATION_MIN_LEN)

    def process_justification_change(self):
        justification_enabled = self.FillSide.currentText() != FieldTypeParams.JUSTIFICATION_NONE
        
        for element in self.FillUpTo, self.FillSymbolLabel, self.FillUpToLabel, self.FillSymbol:
            element.setEnabled(justification_enabled)
