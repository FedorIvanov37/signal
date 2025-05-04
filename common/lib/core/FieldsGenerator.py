from datetime import datetime
from random import randint, choice
from common.lib.data_models.Transaction import Transaction
from common.lib.core.EpaySpecification import EpaySpecification


class FieldsGenerator:
    _spec: EpaySpecification = EpaySpecification()

    @property
    def spec(self):
        return self._spec

    def generate_original_data_elements(self, transaction: Transaction) -> str:
        try:
            mti: str = transaction.message_type
            stan: str = transaction.data_fields[self.spec.FIELD_SET.FIELD_011_SYSTEM_TRACE_AUDIT_NUMBER]
            date: str = transaction.data_fields[self.spec.FIELD_SET.FIELD_007_TRANSMISSION_DATE_AND_TIME]
        except KeyError:
            raise ValueError("Original data elements generating error!")

        return f"{mti}{stan}{date}"

    def set_trans_id(self, transaction: Transaction) -> Transaction:
        if not (de047 := transaction.data_fields.get(self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD)):
            return transaction

        if isinstance(de047, str):
            if not (spec := self.spec.get_field_spec([self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD])):
                return transaction

            de047 = f"{de047}072{str(len(transaction.trans_id)).zfill(spec.tag_length)}{transaction.trans_id}"
            transaction.data_fields[self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD] = de047

            return transaction

        if isinstance(de047, dict):
            de047["072"] = transaction.trans_id
            transaction.data_fields[self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD] = de047

            return transaction

        return transaction

    def set_generated_fields(self, transaction: Transaction) -> Transaction:
        for field in transaction.generate_fields:
            if not self.spec.can_be_generated([field]):
                continue

            transaction.data_fields[field] = self.generate_field(field, max_amount=transaction.max_amount)

        transaction.data_fields = {
            field: transaction.data_fields[field] for field in sorted(transaction.data_fields, key=int)
        }

        return transaction

    @staticmethod
    def generate_field(field: str, max_amount: int = 100):
        spec = EpaySpecification()

        if field == spec.FIELD_SET.FIELD_004_TRANSACTION_AMOUNT:
            try:
                max_amount: int = int(max_amount)
            except ValueError:
                raise TypeError(f"Max amount contains letters: {max_amount}")

            match max_amount:
                case max_amount if max_amount < int():
                    raise ValueError(f"Wrong max amount value. Expected be positive integer, got: {max_amount}")

                case max_amount if max_amount > int():
                    amount: str = str(randint(1, max_amount * 100))

                case _:
                    amount: str = str()

            if not (field_length := spec.get_field_length(spec.FIELD_SET.FIELD_004_TRANSACTION_AMOUNT)):
                raise LookupError("Lost amount field length")

            return str(amount).zfill(field_length)

        if date_format := spec.get_field_date_format(field):
            return f"{datetime.now():{date_format}}"

        data_kit = spec.get_field_data_kit([field])
        length = spec.get_field_length(field)
        data = (choice(data_kit) for _ in range(length))
        data = "".join(data)

        return data

    def add_logical_fields(self, transaction: Transaction) -> Transaction:
        transaction.is_request = self.spec.is_request(transaction)
        transaction.is_reversal = self.spec.is_reversal(transaction.message_type)

        if transaction.is_request:
            return transaction

        if transaction.data_fields.get(self.spec.FIELD_SET.FIELD_039_AUTHORIZATION_RESPONSE_CODE) == "00":
            transaction.success = True

        return transaction

    def merge_trans_data(self, request: Transaction, response: Transaction):
        for message in (request, response):
            self.add_logical_fields(message)

        request.utrnno = response.utrnno
        request.success = response.success
        request.resp_time_seconds = response.resp_time_seconds
        response.generate_fields = request.generate_fields
        response.is_keep_alive = request.is_keep_alive
        response.is_reversal = request.is_reversal
