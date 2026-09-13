from common.core.tools.DebugTrace import trace_operation
from loguru import logger
from json import loads
from io import StringIO
from pathlib import Path
from pydantic import FilePath
from binascii import hexlify, unhexlify, b2a_hex
from configparser import ConfigParser, NoSectionError, NoOptionError
from common.core.tools.FieldsGenerator import FieldsGenerator
from common.core.toolkit.toolkit import mask_secret, mask_pan
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.tools.Bitmap import Bitmap
from common.core.data_models.Config import Config
from common.core.data_models.EpaySpecificationModel import IsoField, FieldSet, RawFieldSet
from common.core.data_models.Transaction import TypeFields, Transaction
from common.core.enums.DataFormats import DataFormats
from common.core.enums.DumpDefinition import DumpLength, DumpFillers
from common.core.enums.IniMessageDefinition import IniMessageDefinition
from common.core.enums.MessageLength import MessageLength
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.data_models.Types import FieldPath
from common.core.exceptions.exceptions import MessageParseError


class Parser:
    _spec: EpaySpecification = EpaySpecification()
    _config: Config

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    @property
    def spec(self):
        return self._spec

    def __init__(self, config: Config):
        self.config: Config = config

    @staticmethod
    @trace_operation
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
        transaction: Transaction = Transaction.model_validate(transaction.model_dump())

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
    @trace_operation
    def create_dump(transaction: Transaction, body: bool = False) -> bytes | str:
        EpaySpecification().require_ready()
        logger.debug("ISO encoding: trans_id={} mti={} fields={} body_only={}",
                     transaction.trans_id, transaction.message_type, len(transaction.data_fields), body)
        spec: EpaySpecification = EpaySpecification()
        msg_type: bytes = transaction.message_type.encode()
        bitmap: Bitmap = Bitmap(transaction.data_fields)
        bitmap: bytes = bitmap.get_bitmap(bytes)

        msg_body: bytes = bytes()

        for field in sorted(transaction.data_fields.keys(), key=int):
            if not (text := transaction.data_fields.get(field)):
                logger.warning(f"No value for field {field}. Field skipped")
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

        result = msg_type + bitmap + msg_body
        logger.debug("ISO encoding completed: trans_id={} bitmap_bytes={} body_bytes={} total_bytes={}",
                     transaction.trans_id, len(bitmap), len(msg_body), len(result))
        return result

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
    @trace_operation
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

            subfield_spec = spec.get_field_spec(path)

            if not subfield_spec:
                raise ValueError(f"Missing specification for field {'.'.join(path)}")

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
            raise ValueError(f"Missing field number for field {parent.get_field_path(string=True)}")

        result: str = str()

        for child_item in parent.get_children():
            if child_item.is_disabled:
                continue

            if child_item.childCount():
                result += self.join_complex_item(parent=child_item)
                continue

            if not child_item.field_data:
                raise ValueError(f"Missing field value for field {child_item.get_field_path(string=True)}")

            if not child_item.field_number:
                raise ValueError(f"Missing field number for field {child_item.get_field_path(string=True)}")

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
    @trace_operation
    def parse_raw_data(raw_data: bytes, flat=False, config=None) -> list[Transaction]:
        EpaySpecification().require_ready()
        logger.debug("ISO framed input: total_bytes={} flat={} supplied_config={}", len(raw_data), flat, config is not None)
        if config is None:  # Standalone library use; the running queue supplies its live settings.
            config = Config(TermFilesPath.CONFIG)
        header_length = config.host.header_length if config.host.header_length_exists else int()
        logger.debug("ISO framing selected: header_bytes={}", header_length)

        if header_length <= 0:
            raise ValueError("A positive message header length is required")

        messages = list()

        while raw_data:  # Loop for multi messages processing
            try:
                if len(raw_data) < header_length:
                    raise IndexError

                message_length: bytes = raw_data[:header_length]
                message_length: int = int(b2a_hex(message_length).decode(), 16)

                if message_length == 0:
                    raise ValueError("Empty transaction frame")

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

            except ValueError as error:
                raise MessageParseError(f"Cannot parse incoming message: {error}") from error

            messages.append(transaction)

        logger.debug("ISO framed input completed: messages={}", len(messages))
        return messages

    @staticmethod
    @trace_operation
    def parse_dump(data, flat: bool = False) -> Transaction:
        EpaySpecification().require_ready()
        logger.debug("ISO decoding: total_bytes={} flat={}", len(data), flat)
        spec: EpaySpecification = EpaySpecification()
        fields: RawFieldSet = {}
        position = int()
        message_type_indicator = data[position:MessageLength.MESSAGE_TYPE_LENGTH].decode()
        position += MessageLength.MESSAGE_TYPE_LENGTH
        bitmap: str = data[position: position + MessageLength.BITMAP_LENGTH]
        position += len(bitmap)
        second_bitmap_exists = Bitmap(bitmap, bytes).second_bitmap_exists()
        logger.debug("ISO bitmap decoded: secondary_present={}", second_bitmap_exists)

        if second_bitmap_exists:
            length = len(bitmap)

            if len(data) < position + length:
                raise ValueError("Incomplete secondary bitmap")

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

                if len(data) < position + length_var:
                    raise ValueError(f"Incomplete length prefix for field {field}")

                length = int(data[position:position + length_var])
                position += length_var
            else:
                length = spec.get_field_length(field)

            if length < 0 or len(data) < position + length:
                logger.debug("ISO field truncated: field={} expected_chars={} available_chars={} offset={}",
                             field, length, len(data) - position, position)
                raise ValueError(f"Incomplete data for field {field}")

            fields[field] = data[position:position + length]
            logger.debug("ISO field decoded: field={} length_prefix_chars={} value_chars={} offset={}",
                         field, length_var, length, position)

            position += length

        transaction: Transaction = Transaction(
            message_type=message_type_indicator,
            data_fields=fields
        )
        logger.debug("ISO decoding completed: trans_id={} mti={} fields={} remaining_chars={}",
                     transaction.trans_id, transaction.message_type, len(fields), len(data) - position)

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
    @trace_operation
    def split_complex_field(field: str, field_data: str, spec: dict | None = None) -> RawFieldSet | None:
        complex_field_data: RawFieldSet = dict()

        if spec is None:  # First entry
            epay_spec: EpaySpecification = EpaySpecification()
            spec: IsoField = epay_spec.get_field_spec([field])

            if not epay_spec.is_field_complex(spec.field_path):
                return field_data

        while field_data:
            tag_number = field_data[:spec.tag_length]
            field_data = field_data[spec.tag_length:]
            field_spec = spec.fields.get(tag_number)

            try:
                var_length = spec.tag_length

                if not var_length:
                    raise ValueError("Missing variable length")

            except (AttributeError, ValueError):
                logger.error(f"Missing specification for field {field}")
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

    @trace_operation
    def parse_text(self, text: str) -> Transaction:
        """Parse a transaction without a filename or temporary files."""
        self.spec.require_ready()
        text = text.lstrip('\ufeff').strip()
        if not text:
            raise ValueError('Empty transaction text')
        if text.startswith('{'):
            transaction = self._parse_json_text(text)
        elif text.startswith('['):
            transaction = self.parse_ini_string(text)
        else:
            transaction = self.parse_dump_text(text)
        return FieldsGenerator.set_generated_fields(transaction)

    def parse_file(self, filename: FilePath | str) -> Transaction:
        self.spec.require_ready()
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

        transaction: Transaction = FieldsGenerator.set_generated_fields(transaction)

        return transaction

    @staticmethod
    def _parse_json_file(filename: str) -> Transaction:
        return Parser._parse_json_text(Path(filename).read_text(encoding='utf-8-sig'))

    @staticmethod
    def _parse_json_text(text: str) -> Transaction:
        data = loads(text)
        if not isinstance(data, dict):
            raise ValueError('Transaction JSON must be an object')
        if 'transaction' in data:
            from common.core.data_models.Transaction import OldTransactionModel
            old = OldTransactionModel(**data)
            return Transaction(trans_id=old.transaction.id,
                message_type=old.transaction.message_type, data_fields=old.transaction.fields,
                max_amount=(old.config.max_amount if old.config.max_amount is not None
                            else Transaction.model_fields['max_amount'].default),
                generate_fields=old.config.generate_fields)
        return Transaction(**data)

    @staticmethod
    def get_field_data(fields: FieldSet, field_path: FieldPath):
        for field_number, field_data in fields.items():
            fields[field_number] = Parser.split_complex_field(field_number, field_data)

        field_data = fields

        for field_number in field_path:
            if field_data := field_data.get(field_number):
                continue

            return

        return field_data

    @trace_operation
    def parse_ini_string(self, ini_data: str) -> Transaction:
        self.spec.require_ready()
        ini: ConfigParser = ConfigParser()
        ini.read_file(StringIO(ini_data))

        return self._parse_ini(ini)

    @staticmethod
    def unpack_ini_field(data: str) -> str:
        return data.removeprefix('[').removesuffix(']')

    def _parse_ini_file(self, filename) -> Transaction:
        return self.parse_ini_string(Path(filename).read_text(encoding='utf-8-sig'))

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
        except (NoSectionError, NoOptionError):
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
                raise ValueError(f"Wrong field name: {option}. Should start from f. For example: f002")

            field = str(int(option.removeprefix("f")))
            value = self.unpack_ini_field(ini.get(IniMessageDefinition.MESSAGE, option))

            if self.spec.is_field_complex([field]):
                value = self.split_complex_field(field, value)

            fields[field] = value

        return fields

    @trace_operation
    def parse_dump_text(self, dump_text: str) -> Transaction:
        string: str = self.clean_dump(dump_text)
        transaction: Transaction = self.parse_dump(string)
        if self.spec.is_request(transaction):
            # DUMP has no generation settings. Infer them only for fields
            # actually present, using the same rule for files and dropped text.
            transaction.generate_fields = [field for field in self.spec.get_fields_to_generate()
                                           if field in transaction.data_fields]
        return transaction

    @staticmethod
    def clean_dump(dump_text: str) -> str:
        string = str()

        for line in dump_text.splitlines():
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
        clean_string = unhexlify(mti) + bitmap + unhexlify(string)

        return clean_string

    def _parse_dump_file(self, filename: str) -> Transaction:
        raw_data = Path(filename).read_text(encoding='utf-8-sig')
        return self.parse_dump_text(raw_data)
