from binascii import b2a_hex, a2b_hex
from collections import OrderedDict
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.enums.MessageLength import MessageLength


class Bitmap:
    _supported_types: tuple = (hex, bin, dict, bytes)
    _spec: EpaySpecification = EpaySpecification()

    @property
    def spec(self):
        return self._spec

    def __init__(self, bitmap, bitmap_type=dict):
        self.bitmap: OrderedDict = self._parse_bitmap(bitmap, bitmap_type)
        sorted_bitmap = OrderedDict()

        for bit in sorted(self.bitmap.keys(), key=int):
            sorted_bitmap[bit] = self.bitmap[bit]

        self.bitmap = sorted_bitmap.copy()
        self.first_bitmap: dict = dict()
        self.second_bitmap = dict()

        for bit, exists in self.bitmap.items():
            first_bitmap_capacity = MessageLength.FIRST_BITMAP_CAPACITY + 1
            second_bitmap_capacity = MessageLength.SECOND_BITMAP_CAPACITY + 1

            match int(bit):
                case bit if bit in range(1, first_bitmap_capacity):
                    self.first_bitmap[bit] = exists

                case bit if bit in range(first_bitmap_capacity, second_bitmap_capacity):
                    self.second_bitmap[bit] = exists

                case _:
                    raise ValueError("Broken bitmap!")

    def _parse_bitmap(self, bitmap, bitmap_type):
        parsed_bitmap = {self.spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY: False}
        parsed_bitmap.update(dict.fromkeys(self.spec.fields.keys(), False))

        if bitmap_type not in self._supported_types:
            raise TypeError("Wrong bitmap type")

        if bitmap_type is dict:
            for bit, value in bitmap.items():
                parsed_bitmap[bit] = bool(value)

                if int(bit) > MessageLength.FIRST_BITMAP_CAPACITY:
                    parsed_bitmap[self.spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY] = True

            return parsed_bitmap

        if bitmap_type is bytes:
            return self._parse_bitmap(b2a_hex(bitmap), hex)

        if bitmap_type is hex:
            if len(bitmap) not in (MessageLength.FIRST_BITMAP_LENGTH_HEX, MessageLength.SECOND_BITMAP_LENGTH_HEX):
                raise ValueError("Invalid bitmap length")

            bitmap = bin(int(bitmap, 16))[2:]

            if len(bitmap) < MessageLength.FIRST_BITMAP_CAPACITY:
                bitmap = bitmap.zfill(MessageLength.FIRST_BITMAP_CAPACITY)

        if bitmap_type is bin:
            if len(bitmap) not in (MessageLength.FIRST_BITMAP_CAPACITY, MessageLength.SECOND_BITMAP_CAPACITY):
                raise ValueError("Invalid bitmap length")

        for pos, bit in enumerate(bitmap, start=1):
            parsed_bitmap[str(pos)] = bool(int(bit))

        return parsed_bitmap

    def get_bitmap(self, bitmap_type: callable = dict, has_data: bool = None):
        result = None
        bitmap = self.bitmap.copy()

        if isinstance(has_data, bool):
            bitmap = {key: val for key, val in bitmap.items() if val is has_data}

        if bitmap_type is dict:
            result = bitmap

        if bitmap_type is str:
            result = [str(field) for field, exists in bitmap.items() if exists]
            result = ", ".join(result)

        if bitmap_type is bin:
            result = [str(int(exists)) for exists in bitmap.values()]
            result = "".join(result)

            if not self.second_bitmap_exists():
                result = result[:MessageLength.FIRST_BITMAP_CAPACITY]

        if bitmap_type is hex:
            result = self.get_bitmap(bin)
            result = hex(int(result, 2))[2:].upper()
            result = result.zfill(MessageLength.BITMAP_LENGTH)

            if not self.second_bitmap_exists():
                result = result[:MessageLength.FIRST_BITMAP_LENGTH_HEX]

        if bitmap_type is list:
            result = self.get_field_set(filled=True)

        if bitmap_type is bytes:
            result = self.get_bitmap(hex)
            result = a2b_hex(result)

        if result is None:
            raise TypeError("Wrong bitmap type")

        return result

    def second_bitmap_exists(self):
        return bool(self.bitmap.get(self.spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY))

    def get_field_set(self, filled=None):
        if filled is None:
            return list(self.bitmap.keys())

        return [field for field, has_data in self.bitmap.items() if has_data is filled]
