"""Parse an editable document without installing it as the active specification."""
import json
from common.core.data_models.EpaySpecificationModel import EpaySpecModel, IsoField
from common.core.tools.validators.Validator import Validator


def parse_spec_document(text):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key {key!r}')
            result[key] = value
        return result

    data = json.loads(text, object_pairs_hook=unique_object)

    def check_ascii(value):
        if isinstance(value, str):
            Validator.validate_ascii_printable(value)
        elif isinstance(value, dict):
            for key, child in value.items():
                check_ascii(key)
                check_ascii(child)
        elif isinstance(value, list):
            for child in value:
                check_ascii(child)

    check_ascii(data)
    if not isinstance(data, dict) or not isinstance(data.get('fields'), dict):
        raise ValueError('Expected a specification object with a fields object')
    if set(data) - set(EpaySpecModel.model_fields):
        raise ValueError('Unknown specification properties')
    document = EpaySpecModel.model_validate(dict(data, fields={}))

    def fields_from(raw, parent=()):
        fields = {}
        for number, properties in raw.items():
            if not isinstance(properties, dict):
                raise ValueError(f'Field entry {number!r} must be an object')
            if set(properties) - set(IsoField.model_fields):
                raise ValueError(f'Unknown properties in field entry {number!r}')
            children = properties.get('fields')
            if children is not None and not isinstance(children, dict):
                raise ValueError(f'Field entry {number!r}: fields must be an object or null')
            displayed_number = properties.get('field_number', number) if number else ''
            if displayed_number is None:
                displayed_number = ''
            if displayed_number and displayed_number != number:
                displayed_number = number
            safe = dict(properties, fields=None, field_number=displayed_number, field_path=[*parent, displayed_number])
            edits = {}
            for key in ('min_length', 'max_length', 'var_length', 'tag_length'):
                value = properties.get(key, '')
                if value is None:
                    value = ''
                if isinstance(value, bool) or not isinstance(value, (int, str)):
                    raise ValueError(f'Field entry {number!r}: {key} must be a number or editable text')
                edits[key] = value
                safe[key] = 0
            if safe.get('description') is None:
                safe['description'] = ''
            field = IsoField.model_validate(safe)
            edits['fields'] = fields_from(children, (*parent, number)) if children is not None else None
            # Only editable numeric cells may temporarily violate the model.
            fields[number] = field.model_copy(update=edits)
        return fields

    return document.model_copy(update={'fields': fields_from(data['fields'])})
