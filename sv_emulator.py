from time import sleep
from datetime import datetime
from copy import deepcopy
from struct import pack
from socket import socket
from contextlib import suppress
from string import digits, ascii_letters
from random import randint
from dataclasses import dataclass
from common.lib.data_models.Config import Config
from common.lib.data_models.Transaction import Transaction
from common.lib.core.Parser import Parser
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.enums.TextConstants import TextConstants


"""

SmartVista fake emulator for test purpose

Establish TCP connection, add utrnno, auth code, and RC=00 for each transaction, then return it to the socket. Utrnno 
will be generated and added in case of DE047 existing in the request

It does not analyse any transaction data and so on, just adds the fields to the request and returns the transaction back

"""


@dataclass
class IsoConfig:
    SERVER = True
    PORT = 16677
    ADDRESS = ""


class SvEmulator:
    _stop: bool = False

    @property
    def stop(self):
        return self._stop

    @stop.setter
    def stop(self, stop: bool):
        self._stop = stop

    def __init__(self):
        with open(TermFilesPath.CONFIG) as json_file:
            self.config: Config = Config.model_validate_json(json_file.read())

        self.parser: Parser = Parser(self.config)
        self.spec: EpaySpecification = EpaySpecification()

    def run(self, sleep_time: int | None = None):
        if sleep_time is None:
            sleep_time = randint(10, 100) / 100

        date_format = "%Y.%m.%d %H:%M:%S"

        print(f"{TextConstants.HELLO_MESSAGE} | SmartVisa Emulator")

        connection = self.get_connector()

        while True:

            try:
                if self.stop:
                    return

                data = connection.recv(1024)

                if not data:
                    connection = self.get_connector()
                    continue

                print("\n", datetime.strftime(datetime.now(), date_format), " <<< ", data)

                data = data[2:]  # Cut the header

                request: Transaction = self.parser.parse_dump(data, flat=True)
                response: Transaction = self.generate_resp(request)
                response.message_type = self.spec.get_resp_mti(request.message_type)

                print("\n", datetime.strftime(datetime.now(), date_format), " >>> ", response.data_fields)

                response: bytes = self.parser.create_dump(response)
                response: bytes = pack("!H", len(response)) + response

                print("\n", datetime.strftime(datetime.now(), date_format), " >>> ", response)

                sleep(sleep_time)

                connection.send(response)

            except KeyboardInterrupt:
                with suppress(Exception):
                    connection.close()

                exit()

            except Exception as connection_error:
                print(connection_error)

                try:
                    connection = self.get_connector()

                except KeyboardInterrupt:
                    exit()

                continue

    def generate_resp(self, request: Transaction):
        request: Transaction = deepcopy(request)
        utrnno: str = str(randint(111111111, 999999999))
        letters: str = digits + ascii_letters.upper()
        auth_code: str = str()

        for _ in range(self.spec.get_field_length(self.spec.FIELD_SET.FIELD_038_AUTHORIZATION_ID_CODE)):
            auth_code += letters[randint(int(), len(letters) - 1)]

        resp_fields_data = {
            self.spec.FIELD_SET.FIELD_038_AUTHORIZATION_ID_CODE: auth_code,
            self.spec.FIELD_SET.FIELD_039_AUTHORIZATION_RESPONSE_CODE: '00',
        }

        if request.data_fields.get(self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD):
            resp_fields_data.update(
                {
                    self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD:
                        request.data_fields.get(self.spec.FIELD_SET.FIELD_047_PROPRIETARY_FIELD) + f"064009{utrnno}"
                }
            )

        for field_number, field_data in resp_fields_data.items():
            try:
                request.data_fields[field_number] = field_data
            except KeyError:
                pass

        return request

    @staticmethod
    def get_connector():
        sock = socket()
        sock.bind((IsoConfig.ADDRESS, IsoConfig.PORT))
        sock.listen(1)
        conn, addr = sock.accept()
        return conn


if __name__ == "__main__":
    SvEmulator().run()
