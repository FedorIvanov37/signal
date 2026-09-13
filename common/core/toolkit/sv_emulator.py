from time import sleep
from sys import stderr
from loguru import logger
from common.core.constants.LogDefinition import console_format
from common.core.constants.EpaySpecificationData import MessageTypeIndicators
from copy import deepcopy
from struct import pack
from socket import socket
from contextlib import suppress
from string import digits, ascii_letters
from random import randint
from dataclasses import dataclass
from common.core.data_models.Config import Config
from common.core.data_models.Transaction import Transaction
from common.core.tools.Parser import Parser
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.enums.TextConstants import TextConstants


"""
SmartVista E-pay Emulator for test purpose

Establish TCP connection, add utrnno, auth code, and RC=00 for each transaction, then return it to the socket
Utrnno will be generated and added in case of DE047 existing in the request

Emulator does not analyse any transaction data and so on, just adds the fields to the request and returns the
transaction back


How to run the emulator

To run the emulator do not move this file anywhere, just create run script in the base directory, where signal.exe is,
as it described below

1. Create some .py file in the base directory, where signal.exe is. For example run_emulator.py

2. Write the emulator run script as in example below to the file run_emulator.py to import and start the emulator

3. Run the emulator by command "python run_emulator.py"


Run script code example

# Start of code

from common.core.toolkit.sv_emulator import SvEmulator, IsoConfig

host = "127.0.0.1"
port = 16677

config = IsoConfig(ADDRESS=host, PORT=port)
emulator = SvEmulator(config)

emulator.run()

# End of code

"""


@dataclass
class IsoConfig:
    PORT: int = 16677
    SERVER: bool = True
    ADDRESS: str = ""


class SvEmulator:
    _stop: bool = False

    @property
    def stop(self):
        return self._stop

    @stop.setter
    def stop(self, stop: bool):
        self._stop = stop

    def __init__(self, iso_config: IsoConfig):
        from common.core.tools.StartupConfig import load_startup_config
        self.config: Config = load_startup_config()[0]
        self.parser: Parser = Parser(self.config)
        self.spec: EpaySpecification = EpaySpecification()
        self.iso_config = iso_config

    @staticmethod
    def _format_bytes(data: bytes) -> str:
        """Render bytes like Python repr, with stable double quotes."""
        representation = repr(data)
        return 'b"' + representation[2:-1].replace('"', '\\"') + '"'

    def run(self, sleep_time: int | None = None):
        # Configure logging when running the emulator, not when importing it.
        logger.remove()
        if stderr is not None:
            logger.add(stderr, format=console_format, level="INFO", backtrace=False, diagnose=False)

        if sleep_time is None:
            sleep_time = randint(10, 100) / 100

        print(f"{TextConstants.HELLO_MESSAGE} | SmartVista Emulator\n", flush=True)

        connection = None
        try:
            while not self.stop:
                if connection is None:
                    connection = self.get_connector(self.iso_config)

                try:
                    data = connection.recv(1024)
                    if not data:
                        logger.info("Emulator connection DISCONNECTED: peer closed the connection")
                        connection.close()
                        connection = None
                        continue

                    logger.info("<<< Received {} bytes: {}", len(data), self._format_bytes(data))

                    data = data[2:]  # Cut the header

                    request: Transaction = self.parser.parse_dump(data, flat=True)
                    logger.info("<<< Message fields: {}", request.data_fields)
                    response_mti = self.spec.get_resp_mti(request.message_type)
                    if not response_mti:
                        logger.info("<<< MTI {} received; no response required", request.message_type)
                        continue
                    response: Transaction = self.generate_resp(request)
                    response.message_type = response_mti

                    logger.info(">>> Response fields: {}", response.data_fields)

                    response: bytes = self.parser.create_dump(response)
                    response: bytes = pack("!H", len(response)) + response

                    sleep(sleep_time)

                    connection.sendall(response)
                    logger.info(">>> Sent {} bytes: {}", len(response), self._format_bytes(response))


                except OSError as error:
                    logger.warning("Emulator connection DISCONNECTED: {}", error)
                    connection.close()
                    connection = None

                except Exception as error:
                    logger.error("Emulator message processing failed: {}", error)
                    connection.close()
                    connection = None
                    logger.info("Emulator connection DISCONNECTED: message processing failed")

        except KeyboardInterrupt:
            logger.info("Emulator shutdown requested")

        except OSError as error:
            logger.error("Emulator connection setup failed: {}", error)

        finally:
            if connection is not None:
                with suppress(OSError):
                    connection.close()
                logger.info("Emulator connection DISCONNECTED: emulator stopping")
            logger.info("Emulator stopped")

    def generate_resp(self, request: Transaction):
        request: Transaction = deepcopy(request)
        utrnno: str = str(randint(111111111, 999999999))
        auth_field = self.spec.FIELD_SET.FIELD_038_AUTHORIZATION_ID_CODE
        resp_fields_data = {self.spec.FIELD_SET.FIELD_039_AUTHORIZATION_RESPONSE_CODE: '00'}

        if self.spec.get_resp_mti(request.message_type) == MessageTypeIndicators.NETWORK_MANAGEMENT_RESPONSE:
            request.data_fields.pop(auth_field, None)
        else:
            letters = digits + ascii_letters.upper()
            auth_code = "".join(
                letters[randint(0, len(letters) - 1)]
                for _ in range(self.spec.get_field_length(auth_field))
            )
            resp_fields_data[auth_field] = auth_code

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
    def get_connector(iso_config: IsoConfig):
        with socket() as sock:
            sock.bind((iso_config.ADDRESS, iso_config.PORT))
            sock.listen(1)
            host, port = sock.getsockname()
            logger.info("Emulator listening on {}:{}; waiting for connection", host, port)
            conn, addr = sock.accept()
            logger.info("Emulator connection ESTABLISHED: peer={}:{}", *addr)
            return conn


def main(argv=None):
    """Run the local test host from the project or installation directory."""
    from argparse import ArgumentParser
    parser = ArgumentParser(description="Run the local SmartVista test emulator.")
    parser.add_argument("--port", type=int, default=16677, help="TCP port (default: 16677)")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    SvEmulator(IsoConfig(ADDRESS="127.0.0.1", PORT=args.port)).run()


if __name__ == "__main__":
    main()
