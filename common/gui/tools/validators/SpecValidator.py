from common.core.data_models.Validation import ValidationResult, ValidationTypes
from common.core.tools.validators.Validator import Validator
from common.gui.tools.json_items.SpecItem import SpecItem
from common.gui.enums import SpecFieldDef


class SpecValidator:
    def location(self, item: SpecItem):
        if item.parent() is None:
            return 'Specification'
        ancestors = []
        current = item
        while current.parent() is not None:
            ancestors.append(current)
            current = current.parent()
        try:
            for ancestor in ancestors:
                self.validate_field_number(ancestor)
        except ValueError:
            position = '.'.join(str(ancestor.parent().indexOfChild(ancestor) + 1)
                                for ancestor in reversed(ancestors))
            return f'Row {position}'
        return f'Field {item.get_field_path(string=True)}'

    def validate_spec_row(self, row: SpecItem):
        result = ValidationResult()
        errors = result.errors[ValidationTypes.FIELD_SPEC_VALIDATION]
        valid_columns = set()
        for column in SpecFieldDef.ColumnsOrder:
            try:
                self.validate_column(row, column)
                valid_columns.add(column)
            except ValueError as error:
                errors.add(str(error))
        if row.parent() is None:
            return result
        order = SpecFieldDef.ColumnsOrder
        location = self.location(row)
        if {order.MIN_LENGTH, order.MAX_LENGTH} <= valid_columns:
            try:
                self.validate_length_relation(row)
            except ValueError as error:
                errors.add(str(error))
        if order.TAG_LENGTH in valid_columns and int(row.tag_length) > 0 and not row.childCount():
            errors.add(f'{location} - Non-zero Tag Len, but field does not contain subfields')
        if not any((row.alpha, row.numeric, row.special)):
            errors.add(f'{location}, Alpha/Numeric/Special - Missing field data type, no datatype checkboxes active')
        return result

    def validate_length_relation(self, item):
        try:
            self.validate_number(item.min_length)
            self.validate_number(item.max_length)
        except ValueError:
            return
        if int(item.min_length) > int(item.max_length):
            raise ValueError(f'{self.location(item)}, Min Len/Max Len - Min Length over Max Length')

    def validate_column(self, item: SpecItem, column):
        order = SpecFieldDef.ColumnsOrder
        try:
            if item.parent() is not None and column == order.FIELD:
                self.validate_field_number(item)
                return
            Validator.validate_ascii_printable(item.text(column))
            if item.parent() is not None and column in (
                order.MIN_LENGTH, order.MAX_LENGTH, order.VARIABLE_LENGTH, order.TAG_LENGTH
            ):
                self.validate_number(item.text(column), column in (order.VARIABLE_LENGTH, order.TAG_LENGTH))
        except ValueError as error:
            label = SpecFieldDef.Columns[order(column).name]
            raise ValueError(f'{self.location(item)}, {label} - {error}') from error

    @staticmethod
    def validate_number(number: str, allow_zero=False):
        if not number or any(character not in '0123456789' for character in number):
            raise ValueError('only numeric values allowed')
        if int(number) < (0 if allow_zero else 1):
            raise ValueError('only positive digits allowed')

    def validate_field_number(self, item):
        number = item.field_number
        try:
            self.validate_number(number)
        except ValueError as error:
            raise ValueError(f'Invalid field number {number!r} - {error}') from error
        if item.get_field_depth() == 1 and not 2 <= int(number) <= 128:
            raise ValueError(f'Invalid field number {number!r} - top level field number must be in range 2-128')
        matches = [sibling for sibling in item.parent().get_children() if sibling.field_number
                   and all(character in '0123456789' for character in sibling.field_number)
                   and int(sibling.field_number) == int(number)]
        if len(matches) > 1:
            raise ValueError(f'Duplicated field number {number!r}')
