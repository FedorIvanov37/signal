from contextlib import suppress
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette
from PyQt6.QtWidgets import QTreeWidgetItem, QCheckBox, QWidget, QApplication
from common.core.data_models.EpaySpecificationModel import IsoField
from common.core.toolkit.toolkit import mask_pan, mask_secret
from common.core.tools.EpaySpecification import EpaySpecification
from common.gui.tools.json_items.Item import Item
from common.gui.decorators.void_qt_signals import void_tree_signals
from common.gui.enums.CheckBoxesDefinition import CheckBoxesDefinition
from common.gui.enums import MainFieldSpec as FieldsSpec
from common.gui.enums.MainFieldSpec import ColumnsOrder
from common.gui.enums.Colors import Colors
from common.gui.tools.widgets.FieldCheckBox import FieldCheckBox


class FieldItem(Item):
    epay_spec: EpaySpecification = EpaySpecification()
    spec: IsoField = None
    _secret: str = ""
    _masked: bool = False
    _is_new: bool = True

    @property
    def is_new(self):
        return self._is_new

    @is_new.setter
    def is_new(self, is_new):
        self._is_new = is_new

    @property
    def masked(self):
        return self._masked

    @masked.setter
    def masked(self, masked):
        self._masked = masked

    @property
    def field_data(self):
        if self.is_secret and self._secret:
            return self._secret

        return self.text(FieldsSpec.ColumnsOrder.VALUE)

    @field_data.setter
    def field_data(self, field_data):
        self.is_new: bool = False
        self.setText(FieldsSpec.ColumnsOrder.VALUE, field_data)
        self._secret: str = ""
        self.set_spec()
        self.hide_secret()

    @property
    def field_length(self):
        return self.text(FieldsSpec.ColumnsOrder.LENGTH)

    @property
    def field_number(self):
        return self.text(FieldsSpec.ColumnsOrder.FIELD)

    @property
    def is_secret(self):
        if not (spec := self.epay_spec.get_field_spec(self.get_field_path())):
            if not (spec := self.spec):
                return False

        return spec and spec.is_secret

    @property
    def description(self):
        return self.text(FieldsSpec.ColumnsOrder.DESCRIPTION)

    @property
    def is_trans_id(self):
        return self.get_field_path() == self.epay_spec.get_trans_id_path()

    def __init__(self, item_data: list[str], spec=None):
        super(FieldItem, self).__init__(item_data)
        self.spec = spec if spec else self.spec
        self.setTextAlignment(FieldsSpec.ColumnsOrder.LENGTH, Qt.AlignmentFlag.AlignRight)

    def set_disabled(self, disabled: bool, affect_child=True):
        if self.is_disabled is disabled and not self.get_children():
            return

        for item in self.get_children():
            if not affect_child:
                break

            item.set_disabled(disabled)

        self._is_disabled = disabled

        if checkbox := self.get_checkbox():
            checkbox.setDisabled(disabled)

        if self.is_disabled:
            self.set_item_color(Colors.GREY)

        if not self.is_disabled:
            self.set_item_color(Colors.BLACK)

            with suppress(AttributeError):
                self.treeWidget().process_change_item(self, ColumnsOrder.VALUE)

        self.set_length()

        if not (parent := self.parent()):
            return

        if not disabled and parent.is_disabled:
            parent.set_disabled(disabled, affect_child=False)

        for child_item in parent.get_children():
            if child_item.is_disabled is not disabled:
                return

        parent.set_disabled(disabled, affect_child=False)

    def addChild(self, item, fill_len=None):
        item.spec = self.epay_spec.get_field_spec(item.get_field_path())
        QTreeWidgetItem.addChild(self, item)
        item.set_length(fill_length=fill_len)

    def hide_secret(self, hide_the_secret: bool | None = None):
        tree = self.treeWidget()

        if tree and not tree.hide_secret_fields:
            if self.field_number != self.epay_spec.FIELD_SET.FIELD_002_PRIMARY_ACCOUNT_NUMBER:
                hide_the_secret = False
        
        if hide_the_secret is None:
            hide_the_secret: bool = self.is_secret

        if hide_the_secret:
            self.mask_secret_value()

        else:
            self.show_secret_value()

    @void_tree_signals
    def mask_secret_value(self):
        secret = self.field_data

        if self.field_number == self.epay_spec.FIELD_SET.FIELD_002_PRIMARY_ACCOUNT_NUMBER:
            mask = mask_pan(secret)
        else:
            mask = mask_secret(secret)

        self.setText(FieldsSpec.ColumnsOrder.VALUE, mask)
        self._secret = secret
        self.masked = True

    @void_tree_signals
    def show_secret_value(self):
        if not self.masked:
            return

        self.setText(FieldsSpec.ColumnsOrder.VALUE, self._secret)
        self._secret = ""
        self.masked = False

    def get_checkbox(self):
        if not (tree := self.treeWidget()):
            return

        checkbox: QWidget | QCheckBox = tree.itemWidget(self, FieldsSpec.ColumnsOrder.PROPERTY)

        return checkbox

    def checkbox_checked(self, checkbox_type: str):
        if checkbox_type not in (CheckBoxesDefinition.GENERATE, CheckBoxesDefinition.JSON_MODE):
            return False

        if checkbox_type == CheckBoxesDefinition.JSON_MODE:
            if not self.epay_spec.is_field_complex(self.get_field_path()):
                return False

        if checkbox_type == CheckBoxesDefinition.GENERATE:
            if self.field_number not in self.epay_spec.get_fields_to_generate() and not self.is_trans_id:
                return False

        if not (tree := self.treeWidget()):
            return False

        checkbox: QWidget | QCheckBox = tree.itemWidget(self, FieldsSpec.ColumnsOrder.PROPERTY)

        if not isinstance(checkbox, QCheckBox):
            return False

        return bool(checkbox.checkState().value)

    @void_tree_signals
    def set_checkbox(self, checked=True):
        if self.get_field_depth() != 1 and not self.is_trans_id:
            return

        column_number = FieldsSpec.ColumnsOrder.PROPERTY
        checkbox = FieldCheckBox()
        checkbox.setFont(QFont("Calibri", 12))
        checkbox.setChecked(checked)

        if not (tree := self.treeWidget()):
            return

        tree.removeItemWidget(self, FieldsSpec.ColumnsOrder.PROPERTY)

        if self.field_number in self.epay_spec.get_fields_to_generate() or self.is_trans_id:
            checkbox.setText(CheckBoxesDefinition.GENERATE)
            tree.setItemWidget(self, column_number, checkbox)

        if self.epay_spec.is_field_complex(self.get_field_path()):
            checkbox.setText(CheckBoxesDefinition.JSON_MODE)
            tree.setItemWidget(self, column_number, checkbox)

        # This is a persistent control, not a cell editor. Do not let Qt's
        # editor focus tracking move the current row when the control is entered.
        checkbox.removeEventFilter(tree)
        checkbox.removeEventFilter(tree.itemDelegate())
        checkbox.pressed.connect(lambda: tree.setCurrentItem(self, column_number))
        checkbox.stateChanged.connect(lambda: tree.itemChanged.emit(self, FieldsSpec.ColumnsOrder.PROPERTY))
        self.update_checkbox_text_color()

    def update_checkbox_text_color(self):
        checkbox = self.get_checkbox()
        if not isinstance(checkbox, QCheckBox):
            return
        palette = QPalette(checkbox.palette())
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
                color = (self.treeWidget().palette().color(group, QPalette.ColorRole.HighlightedText)
                         if self.isSelected() else self.treeWidget().palette().color(group, QPalette.ColorRole.Text))
                palette.setColor(group, role, color)
        checkbox.setPalette(palette)

    def remove_checkbox(self):
        if not (tree := self.treeWidget()):
            return

        tree.removeItemWidget(self, FieldsSpec.ColumnsOrder.PROPERTY)

    def process_change_item(self):
        self.set_spec()
        self.set_item_color()
        self.set_description()
        self.set_length()

    @void_tree_signals
    def set_description(self, text: str | None = None):
        if text is not None:
            self.setText(FieldsSpec.ColumnsOrder.DESCRIPTION, str(text))
            return

        if not self.spec:
            self.set_spec()

        self.setText(FieldsSpec.ColumnsOrder.DESCRIPTION, self.spec.description if self.spec else str())

    @void_tree_signals
    def set_length(self, length: int | None = None, fill_length: int | None = 3, *, preview=None) -> None:
        column = FieldsSpec.ColumnsOrder.LENGTH

        if not self.spec:
            self.set_spec()

        if length is None:
            length: int = self.get_field_length(count_disabled=self.is_disabled, preview=preview)

        if not self.spec and self.field_length:
            fill_length = len(self.text(FieldsSpec.ColumnsOrder.LENGTH))

        length: str = str(length).zfill(fill_length)

        self.setText(column, str(length))

        if parent := self.parent():
            parent.set_length(preview=preview)

    def get_field_length(self, count_disabled=False, *, preview=None):
        if not self.childCount():
            if preview is not None and preview[0] is self:
                return preview[1]
            return len(self.field_data)

        length = int()
        parent_spec = self.spec or self.epay_spec.get_field_spec(self.get_field_path())

        for item in self.get_children():
            if not count_disabled and item.is_disabled:
                continue

            length += item.get_field_length(preview=preview)
            # A row shows its value length. Its container additionally owns
            # the tag and length prefix used to encode that value.
            child_spec = item.spec or self.epay_spec.get_field_spec(item.get_field_path())
            if child_spec is not None:
                length += child_spec.var_length
            if parent_spec is not None:
                length += parent_spec.tag_length

        return length
