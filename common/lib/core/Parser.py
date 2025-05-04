from json import loads
from pathlib import Path
from pydantic import FilePath
from binascii import hexlify, unhexlify, b2a_hex
from loguru import logger
from configparser import ConfigParser, NoSectionError, NoOptionError
from io import StringIO
from common.lib.toolkit.generate_trans_id import generate_trans_id
from common.lib.toolkit.toolkit import mask_secret, mask_pan
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.core.Bitmap import Bitmap
from common.lib.data_models.Config import Config
from common.lib.data_models.EpaySpecificationModel import IsoField, FieldSet, RawFieldSet
from common.lib.data_models.Transaction import TypeFields, Transaction
from common.lib.core.JsonConverter import JsonConverter
from common.lib.core.FieldsGenerator import FieldsGenerator
from common.lib.enums.DataFormats import DataFormats
from common.lib.enums.DumpDefinition import DumpLength, DumpFillers
from common.lib.enums.IniMessageDefinition import IniMessageDefinition
from common.lib.enums.MessageLength import MessageLength
from common.lib.enums.TermFilesPath import TermFilesPath


class Parser:
    _spec: EpaySpecification = EpaySpecification()

    @property
    def spec(self):
        return self._spec

    def __init__(self, config: Config):
        self.config: Config = config
        self.generator = FieldsGenerator()

    @staticmethod
    def parse_complex_fields(transaction: Transaction, split: bool = False) -> Transaction:
        spec: EpaySpecification = EpaySpecification()

        for field, field_data in transaction.data_fields.items():
            if not spec.is_field_complex([field]):
                continue

            if not split:
                transaction.data_fields[field] = Parser.join_complex_field(field, field_data)
                continue

            transaction.data_fields[field] = Parser.split_complex_field(field, field_data)

        return transaction

    @staticmethod
    def hide_secret_fields(transaction: Transaction) -> Transaction:
        spec: EpaySpecification = EpaySpecification()
        transaction: Transaction = Transaction.model_validate(transaction.dict())

        for field, field_data in transaction.data_fields.items():
            if field == spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY:
                continue

            if spec.is_field_complex([field]) and isinstance(field_data, dict):
                try:
                    field_data = Parser.join_complex_field(field, field_data)
                except Exception as parsing_error:
                    logger.error(f"Cannot print field {field}: {parsing_error}")
                    continue

            if all((spec.is_field_complex([field]), isinstance(field_data, str))):
                try:
                    split_field_data: dict = Parser.split_complex_field(field, field_data)
                    field_data: str = Parser.join_complex_field(field, split_field_data, hide_secrets=True)

                except Exception as field_parsing_error:
                    logger.warning(field_parsing_error)

            match field:
                case spec.FIELD_SET.FIELD_002_PRIMARY_ACCOUNT_NUMBER:
                    field_data: str = mask_pan(field_data)

                case _:
                    if spec.is_secret([field]):
                        field_data: str = mask_secret(field_data)

            transaction.data_fields[field] = field_data

        return transaction

    @staticmethod
    def create_dump(transaction: Transaction, body: bool = False) -> bytes | str:
        spec: EpaySpecification = EpaySpecification()
        msg_type: bytes = transaction.message_type.encode()
        bitmap: Bitmap = Bitmap(transaction.data_fields)
        bitmap: bytes = bitmap.get_bitmap(bytes)

        msg_body: bytes = bytes()

        for field in sorted(transaction.data_fields.keys(), key=int):
            if not (text := transaction.data_fields.get(field)):
                logger.warning("No value for field %s. IsoField was ignored" % field)
                continue

            if isinstance(text, dict):
                text = Parser.join_complex_field(field, text)

            field_length_var = spec.get_field_length_var(field)

            if field_length_var:
                text_length = str(len(text)).zfill(field_length_var)
                text = f"{text_length}{text}"

            if text is not None:
                msg_body: bytes = msg_body + text.encode()

        if body:
            return msg_body.decode()

        return msg_type + bitmap + msg_body

    @staticmethod
    def create_sv_dump(transaction: Transaction) -> str | None:
        mti: str = transaction.message_type
        bitmap: hex = Bitmap(transaction.data_fields)
        bitmap: hex = bitmap.get_bitmap(hex)

        try:
            body: str = Parser.create_dump(transaction, body=True)
        except Exception as parsing_error:
            logger.error(f"Parsing error {parsing_error}")
            return

        dump = "\n"
        ascii_dump = mti + DumpFillers.ASCII_BITMAP + body
        hex_dump = hexlify(mti.encode()).decode() + bitmap + hexlify(body.encode()).decode().upper()

        for position in range(0, len(hex_dump), DumpLength.LINE_LENGTH):
            sub_string = str()
            string = hex_dump[position:position + DumpLength.LINE_LENGTH]

            for sub_position in range(0, len(string), DumpLength.BYTE_LENGTH):
                sub_string += string[sub_position:sub_position + DumpLength.BYTE_LENGTH]
                sub_string += DumpFillers.SEPARATOR

            sub_string = sub_string[:-1]
            sub_string = sub_string.ljust(DumpLength.HEX_LINE_LENGTH, " ")
            position = int(position / 2)
            sub_string += ascii_dump[position:position + DumpLength.ASCII_LINE_LENGTH]
            sub_string += "\n"
            dump += sub_string

        return dump

    @staticmethod
    def join_complex_field(field, field_data, path=None, hide_secrets: bool = False) -> str:
        spec: EpaySpecification = EpaySpecification()

        if not isinstance(field_data, dict):
            return field_data
            # raise TypeError(f"Incorrect field value in {'.'.join(path) if path else field}")

        if path is None:
            path = [field]

        result: str = str()
        subfield_data: str | FieldSet
        subfield: str

        for subfield, subfield_data in field_data.items():
            path.append(subfield)

            if not (subfield_spec := spec.get_field_spec(path)):
                raise ValueError(f"Lost specification for field {'.'.join(path)}")

            if subfield_spec.fields:
                result += Parser.join_complex_field(subfield, subfield_data, path, hide_secrets=hide_secrets)
            else:
                if subfield_spec.is_secret and hide_secrets:
                    subfield_data = mask_secret(subfield_data)

                length = str(len(subfield_data))
                length = length.zfill(subfield_spec.var_length)
                result = f"{result}{subfield}{length}{subfield_data}"

            path.pop()

        if len(path) > 1:
            field_spec: IsoField = spec.get_field_spec(path)
            result = f"{field}{len(result):0{field_spec.var_length}}{result}"

        return result

    def join_complex_item(self, parent):
        if not parent.field_number:
            raise ValueError(f"Lost field number for field {parent.get_field_path(string=True)}")

        result: str = str()

        for child_item in parent.get_children():
            if child_item.childCount():
                result += self.join_complex_item(parent=child_item)
                continue

            if not child_item.field_data:
                raise ValueError(f"Lost field value for field {child_item.get_field_path(string=True)}")

            if not child_item.field_number:
                raise ValueError(f"Lost field number for field {child_item.get_field_path(string=True)}")

            length = str(int(child_item.field_length))

            if child_item.spec:
                length = length.zfill(child_item.spec.var_length)

            try:
                if not child_item.spec:
                    if self.config.specification.manual_input_mode:
                        length = length.zfill(len(child_item.field_length))
                    else:
                        length = length.zfill(parent.spec.tag_length)

            except AttributeError:

                for err in (f"Field: {child_item.get_field_path(string=True)}: "
                            "Unable to parse nested structure without the Specification",
                            "To work with such message add the field to the Specification or set the Manual entry mode "
                            "in the Configuration window"):

                    logger.error(err)

                raise ValueError

            result = f"{result}{child_item.field_number}{length}{child_item.field_data}"

        if parent.get_field_depth() <= 1:
            return result

        parent_length = str(len(result))

        try:
            parent_length = parent_length.zfill(parent.spec.var_length)
        except AttributeError:
            parent_length = parent_length.zfill(len(parent.field_length))

        result = f"{parent.field_number}{parent_length}{result}"

        return result

    @staticmethod
    def parse_raw_data(raw_data: bytes, flat=False) -> list[Transaction]:
        with open(TermFilesPath.CONFIG) as json_file:
            config: Config = Config.model_validate_json(json_file.read())

        header_length = config.host.header_length if config.host.header_length_exists else int()

        messages = list()

        while raw_data:
            try:
                if len(raw_data) < header_length:
                    raise IndexError

                message_length: bytes = raw_data[:header_length]
                message_length: int = int(b2a_hex(message_length).decode(), 16)
                raw_data = raw_data[header_length:]

                if len(raw_data) < message_length:
                    raise IndexError

                if len(message_data := raw_data[:message_length]) < message_length:
                    raise IndexError

                raw_data = raw_data[message_length:]

            except (ValueError, IndexError):
                if not config.host.header_length_exists:
                    logger.warning("No message header length set, ordinary header length is 2 or 4. Check the settings")

                if config.host.header_length_exists and config.host.header_length not in (2, 4):
                    logger.warning(f"Unusual message header length {config.host.header_length}, "
                            f"ordinary it is 2 or 4. Check the settings")

                raise ValueError("Invalid incoming message length")

            try:
                transaction: Transaction = Parser.parse_dump(message_data, flat=flat)

            except ValueError:
                message = "Cannot parse incoming message due to format error."
                message = f"{message} Change log level to DEBUG to see raw message"
                raise ValueError(message)

            messages.append(transaction)

        return messages

    @staticmethod
    def parse_dump(data, flat: bool = False) -> Transaction:
        spec: EpaySpecification = EpaySpecification()
        fields: RawFieldSet = {}
        position = int()
        message_type_indicator = data[position:MessageLength.MESSAGE_TYPE_LENGTH].decode()
        position += MessageLength.MESSAGE_TYPE_LENGTH
        bitmap: str = data[position: position + MessageLength.BITMAP_LENGTH]
        position += len(bitmap)
        second_bitmap_exists = Bitmap(bitmap, bytes).second_bitmap_exists()

        if second_bitmap_exists:
            length = len(bitmap)
            bitmap += data[position: position + length]
            position += length

        data = data[position:].decode()
        position = 0
        bitmap: Bitmap = Bitmap(bitmap, bytes)
        bitmap: dict[str, bool] = bitmap.get_bitmap(dict)

        for field, exists in bitmap.items():
            if not exists:
                continue

            if field == spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY:
                continue

            length_var = spec.get_field_length_var(field)

            if length_var > 0:
                length = int(data[position:position + length_var])
                position += length_var
                fields[field] = data[position:position + length]
            else:
                length = spec.get_field_length(field)
                fields[field] = data[position:position + length]

            position += length

        transaction: Transaction = Transaction(
            message_type=message_type_indicator,
            data_fields=fields
        )

        if flat:
            return transaction

        for field, field_data in fields.items():
            if not spec.is_field_complex([field]):
                continue
            try:
                fields[field]: RawFieldSet = Parser.split_complex_field(field, field_data)
            except ValueError:
                raise ValueError("Incorrect transaction message or wrong Specification settings")

        transaction.data_fields = fields

        return transaction

    @staticmethod
    def split_complex_field(field: str, field_data: str, spec: dict | None = None) -> RawFieldSet | None:
        complex_field_data: RawFieldSet = dict()

        if spec is None:  # First entry
            spec: EpaySpecification = EpaySpecification()
            spec: IsoField = spec.get_field_spec([field])

        while field_data:
            tag_number = field_data[:spec.tag_length]
            field_data = field_data[spec.tag_length:]
            field_spec = spec.fields.get(tag_number)

            try:
                var_length = spec.tag_length

                if not var_length:
                    raise ValueError("Lost variable length")

            except(AttributeError, ValueError):
                logger.error("Lost specification for field %s ", field)
                logger.error("The field and corresponding sub fields were absent")
                return {}

            var_length = spec.tag_length
            val_length = field_data[:var_length]
            val_length = int(val_length)
            field_data = field_data[var_length:]
            value_data = field_data[:val_length]
            field_data = field_data[val_length:]

            if field_spec and field_spec.fields:
                value_data = Parser.split_complex_field(tag_number, value_data, field_spec)

            complex_field_data[tag_number] = value_data

        return complex_field_data

    def transaction_to_ini_string(self, transaction: Transaction):
        generate_fields: list[str] = sorted(transaction.generate_fields, key=int)
        generate_fields: str = ", ".join(generate_fields)

        ini_data: list[str] | str = [
            f"[{IniMessageDefinition.CONFIG}]",
            f"{IniMessageDefinition.MAX_AMOUNT} = [{transaction.max_amount}]",
            f"{IniMessageDefinition.GENERATE_FIELDS} = [{generate_fields}]",
            f"[{IniMessageDefinition.MTI}]",
            f"{IniMessageDefinition.MTI} = [{transaction.message_type}]",
            f"[{IniMessageDefinition.MESSAGE}]"
        ]

        for field_number, field_data in transaction.data_fields.items():
            if isinstance(field_data, dict):
                field_data = self.join_complex_field(field_number, field_data)

            field_data = field_data.replace("%", "%%")

            try:
                field_number = f"F{int(field_number):03}"
            except ValueError:
                logger.error(f"Wrong field number {field_number}")

            ini_data.append(f"{field_number} = [{field_data}]")

        ini_data = "\n".join(ini_data)

        return ini_data

    def parse_file(self, filename: FilePath | str) -> Transaction:
        file_extension = Path(filename).suffix
        file_extension = file_extension.replace(".", "")
        file_extension = file_extension.upper()

        data_processing_map = {
            DataFormats.JSON: self._parse_json_file,
            DataFormats.INI: self._parse_ini_file,
            DataFormats.DUMP: self._parse_dump_file
        }

        transaction: Transaction | None = None

        if function := data_processing_map.get(file_extension):
            transaction: Transaction = function(filename)

        if not transaction:
            logger.warning("Unknown file extension, trying to guess the format")

            for extension in data_processing_map:
                logger.info(f"Trying to parse file as {extension}")

                if not (function := data_processing_map.get(extension)):
                    logger.warning(f"Cannot parse file as {extension}")
                    continue

                try:
                    if transaction := function(filename):
                        break

                except FileNotFoundError as file_not_found_error:
                    logger.error(file_not_found_error)
                    break

                except Exception as parsing_error:
                    logger.warning(f"Cannot parse file as {extension}: {parsing_error}")
                    continue

        if not transaction:
            raise TypeError("Can't parse incoming file using known formats")

        if transaction.generate_fields:
            self.generator.set_generated_fields(transaction)

        return transaction

    @staticmethod
    def _parse_json_file(filename: str) -> Transaction:
        JsonConverter.convert(filename)  # TODO: Temporary solution for transfer period

        with open(filename) as json_file:
            transaction: Transaction = Transaction.model_validate_json(json_file.read())

        transaction.trans_id = generate_trans_id()

        return transaction

    def parse_ini_string(self, ini_data: str) -> Transaction:
        ini: ConfigParser = ConfigParser()
        ini.read_file(StringIO(ini_data))

        return self._parse_ini(ini)

    @staticmethod
    def unpack_ini_field(data: str) -> str:
        return data.removeprefix('[').removesuffix(']')

    def _parse_ini_file(self, filename) -> Transaction:
        if not Path(filename).is_file():
            raise FileNotFoundError(f"No such file or directory: '{filename}'")

        ini = ConfigParser()
        ini.read(filename)

        return self._parse_ini(ini)

    def _parse_ini(self, ini: ConfigParser) -> Transaction:
        fields: TypeFields = self._parse_ini_fields(ini)

        ini_def = IniMessageDefinition

        try:
            max_amount = ini.get(ini_def.CONFIG, ini_def.MAX_AMOUNT)
            max_amount = self.unpack_ini_field(max_amount)
        except (NoSectionError, NoOptionError):
            max_amount = self.config.fields.max_amount

        try:
            generate_fields = loads(ini.get(ini_def.CONFIG, ini_def.GENERATE_FIELDS))
        except(NoSectionError, NoOptionError):
            generate_fields: list[str] = []

        mti = self.unpack_ini_field(ini.get(ini_def.MTI, ini_def.MTI))

        transaction: Transaction = Transaction(
            message_type=mti,
            generate_fields=generate_fields,
            max_amount=max_amount,
            data_fields=fields,
        )

        return transaction

    def _parse_ini_fields(self, ini: ConfigParser):
        fields: RawFieldSet = dict()

        for option in ini.options(IniMessageDefinition.MESSAGE):
            if not option.startswith("f"):
                raise ValueError("Wrong field name: %s. Should start from f. For example: f002", option)

            field = str(int(option.removeprefix("f")))
            value = self.unpack_ini_field(ini.get(IniMessageDefinition.MESSAGE, option))

            if self.spec.is_field_complex([field]):
                value = self.split_complex_field(field, value)

            fields[field] = value

        return fields

    def _parse_dump_file(self, filename: str) -> Transaction:
        string = str()

        with open(filename) as file:
            for line in file.readlines():
                if not line.replace(" ", "").replace("\n", ""):
                    continue

                try:
                    line = line.split()[0]
                except IndexError:
                    raise ValueError("Unexpected result of data parsing - no data")

                line = line.replace(DumpFillers.SEPARATOR, "")
                string += line

        mti = string[:MessageLength.MESSAGE_TYPE_LENGTH_HEX]
        string = string[len(mti):]
        bitmap = string[:MessageLength.FIRST_BITMAP_LENGTH_HEX]
        string = string[len(bitmap):]
        bitmap = Bitmap(bitmap, hex).get_bitmap(bytes)
        pre_message = unhexlify(mti) + bitmap + unhexlify(string)
        transaction: Transaction = self.parse_dump(pre_message)

        return transaction
