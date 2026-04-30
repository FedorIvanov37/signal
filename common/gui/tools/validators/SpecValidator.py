from common.core.tools.EpaySpecification import EpaySpecification
from common.gui.tools.json_items.SpecItem import SpecItem
from common.gui.enums import SpecFieldDef


class SpecValidator:
    spec: EpaySpecification = EpaySpecification()

    def validate_spec_row(self, row: SpecItem):
        for column in SpecFieldDef.ColumnsOrder:
            self.validate_column(row, column)

    def validate_column(self, item: SpecItem, column):
        validation_map = {
            SpecFieldDef.ColumnsOrder.FIELD: lambda: self.validate_field_number(item),
            SpecFieldDef.ColumnsOrder.MIN_LENGTH: lambda: self.validate_field_length(item),
            SpecFieldDef.ColumnsOrder.MAX_LENGTH: lambda: self.validate_field_length(item),
            SpecFieldDef.ColumnsOrder.VARIABLE_LENGTH: lambda: self.validate_number(item.var_length, True),
            SpecFieldDef.ColumnsOrder.TAG_LENGTH: lambda: self.validate_number(item.tag_length, True),
            SpecFieldDef.ColumnsOrder.ALPHA: lambda: self.validate_datatype_checkboxes(item),
            SpecFieldDef.ColumnsOrder.NUMERIC: lambda: self.validate_datatype_checkboxes(item),
            SpecFieldDef.ColumnsOrder.SPECIAL: lambda: self.validate_datatype_checkboxes(item),
        }

        if not (validator := validation_map.get(column)):
            return

        validator()

    @staticmethod
    def validate_number(number: str, allow_zero=False):
        try:
            number = int(number)
        except ValueError:
            raise ValueError("only numeric values allowed")

        if number < 1:
            if allow_zero and number == 0:
                return

            raise ValueError("only positive digits allowed")

    def validate_field_number(self, item):
        field_path = item.get_field_path(string=True)

        try:
            self.validate_number(item.field_number)
        except ValueError as value_error:
            raise ValueError(f"Invalid field number {field_path} - {value_error}")

        current_field_numbers = [field.get_field_path(string=True) for field in item.parent().get_children()]

        if current_field_numbers.count(field_path) > 1:
            raise ValueError(f"Field {field_path} - Duplicated field number")

        if item.get_field_depth() == 1:
            if int(item.field_number) < int(self.spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY):
                raise ValueError(f"Field {field_path}, column {SpecFieldDef.ColumnsOrder.FIELD} - Cannot set "
                                 f"field number less than {self.spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY}")

            if int(item.field_number) > int(self.spec.FIELD_SET.FIELD_128_SECONDARY_MAC_DATA):
                raise ValueError(f"Field {field_path}, column {SpecFieldDef.ColumnsOrder.FIELD} - Cannot set top "
                                 f"level field number greater than {self.spec.FIELD_SET.FIELD_128_SECONDARY_MAC_DATA}")

    def validate_field_length(self, item):
        field_path = item.get_field_path(string=True)

        for length in item.min_length, item.max_length:
            try:
                self.validate_number(length)
            except ValueError as validation_error:
                raise ValueError(f"Field {field_path} length validation error {validation_error}")

        for length in item.tag_length, item.var_length:
            try:
                self.validate_number(length, allow_zero=True)
            except ValueError as validation_error:
                raise ValueError(f"Field {field_path} length validation error {validation_error}")

        if int(item.min_length) > int(item.max_length):
            raise ValueError(f"Field {field_path} - Min Length over Max Length")

        if int(item.tag_length) > 0 and not item.childCount():
            raise ValueError(f"Non-zero Tag Len, but field {field_path} doesn't contain subfields")

    @staticmethod
    def validate_datatype_checkboxes(item: SpecItem):
        if any([item.alpha, item.numeric, item.special]):
            return

        field_path = item.get_field_path(string=True)

        raise ValueError(f"Field {field_path} - Lost field data type, no datatype checkboxes active")
