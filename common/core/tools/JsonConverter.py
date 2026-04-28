from pydantic import ValidationError
from common.core.data_models.Transaction import Transaction, OldTransactionModel


"""
Temporary solution for backward compatibility of JSON transaction messages. JSON files format was simplified in v0.15. 

Guess the correct transaction model - old or new. In case of old style rewrites JSON file by new model data 
"""


class JsonConverter:

    @staticmethod
    def convert(filename):  # Check data type and rewrite JSON-file when need
        if JsonConverter.get_transaction_model(filename) is OldTransactionModel:
            JsonConverter.convert_json(filename)

    @staticmethod
    def convert_json(filename: str):
        old_transaction: OldTransactionModel = OldTransactionModel(filename)

        transaction = Transaction(
            trans_id=old_transaction.transaction.id,
            message_type=old_transaction.transaction.message_type,
            max_amount=old_transaction.config.max_amount,
            generate_fields=old_transaction.config.generate_fields,
            data_fields=old_transaction.transaction.fields,
        )

        with open(filename, 'w') as file:
            file.write(transaction.model_dump_json(indent=4))

        return transaction

    @staticmethod
    def get_transaction_model(filename):  # Gues the file format

        try:  # Try to parse in old style
            OldTransactionModel(filename)

            return OldTransactionModel

        except ValidationError as validation_error:  # Check the result in case of fail

            # Such reject usually happens when we try to parse new data by old model
            err = validation_error.errors()[0]

            try:
                if err["loc"][0].lower() == 'config' and err["msg"].lower() == 'field required':
                    return Transaction

            except KeyError:
                raise validation_error

            raise validation_error
