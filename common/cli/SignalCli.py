from glob import glob
from time import sleep
from os import listdir, path, system, getcwd, getpid, kill
from os.path import normpath, basename, isfile
from loguru import logger
from datetime import datetime, UTC
from pydantic import ValidationError
from signal import signal, SIG_DFL, SIGINT
from PyQt6.QtCore import QCoreApplication, QTimer, pyqtSignal
from common.lib.data_models.Transaction import Transaction
from common.lib.data_models.Config import Config
from common.lib.enums.TextConstants import TextConstants
from common.cli.data_models.CliConfig import CliConfig
from common.cli.CliArgsParser import CliArgsParser
from common.lib.core.Terminal import Terminal
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.data_models.License import LicenseInfo
from common.lib.exceptions.exceptions import LicenseRejected
from common.api.ApiThread import ApiThread
from common.lib.exceptions.exceptions import DataValidationWarning


class SignalCli(Terminal):
    _cli_config: CliConfig = None
    _finished: pyqtSignal = pyqtSignal()
    _api_thread: ApiThread = None
    _run_api: pyqtSignal = pyqtSignal()

    def __init__(self, config: Config):
        super(SignalCli, self).__init__(config)
        self.config: Config = config
        self.application = QCoreApplication([])
        self.run_timer = QTimer()
        self.connect_all()
        self.setup()

    def setup(self):
        signal(SIGINT, SIG_DFL)

        cli_args_parser: CliArgsParser = CliArgsParser(self.config, description=TextConstants.CLI_DESCRIPTION)

        try:
            self._cli_config = cli_args_parser.parse_arguments()
        except (ValidationError, ValueError) as arg_parsing_error:
            logger.error(arg_parsing_error)
            exit(100)

        try:
            self.parse_cli_config(self._cli_config)
        except ValueError as config_parsing_error:
            logger.error(f"Error run in Console Mode: {config_parsing_error}")
            exit(100)

        if self._cli_config.log_file != TermFilesPath.LOG_FILE_NAME:
            self.logger.setup(filename=self._cli_config.log_file)

        self.logger.add_stdout_handler()

        try:
            self.show_license_dialog()
        except LicenseRejected:
            exit(100)

    def connect_all(self):
        self.run_timer.timeout.connect(self.main)
        self._finished.connect(self.application.quit)
        self._run_api.connect(self.run_api_mode)

    def run_application(self):
        self.run_timer.setSingleShot(True)
        self.run_timer.start(0)
        self.application.exec()

    def main(self):
        """

        This is the main function, which runs after CLI mode begin

        The function goes by scenario

        1. Print data if requested
        2. Tries to parse the requested files and send the transactions if needed
        3. Check the api-mode request and runs the API

        Important: --repeat flag has a priority over --api-mode. When --repeat flag set along with the --api-mode
        the api-mode will newer be run because the files will be parsed and sent in endless cycle

        """

        if self._cli_config.repeat and self._cli_config.api_mode:
            logger.error("Mutually exclusive flags --repeat and --api-mode are set")
            kill(getpid(), 9)

        # 1. Print data if requested
        print_data_map = {
            self._cli_config.version: self.log_printer.print_version,
            self._cli_config.about: self.log_printer.print_about,
            self._cli_config.print_config: lambda: self.log_printer.print_config(
                self.config, path=self._cli_config.config_file)
        }

        for need_run, function in print_data_map.items():
            if not need_run:
                continue

            try:
                function()
            except Exception as print_error:
                logger.error(print_error)

        if not any([self._cli_config.version, self._cli_config.about]):
            logger.info("## Running SIGNAL in Console mode ##")
            logger.info("Press CTRL+C to exit")
            logger.info(str())

        # 2. Check the api-mode request and runs the API
        if self._cli_config.api_mode:
            self._run_api.emit()

        # 3. Tries to parse the requested files and send the transactions if needed
        if not (filenames := self.get_files_to_process()):
            if not any([self._cli_config.about, self._cli_config.version]):
                logger.info("No files specified to parse")

            return

        while True:
            for file in filenames:
                logger.info(str())
                logger.info(f"Processing file {basename(file)}")

                try:
                    transaction: Transaction = self.parser.parse_file(file)
                except Exception as parsing_error:
                    logger.error(parsing_error)
                    continue

                self.send(transaction)

                if not self._cli_config.parallel:
                    self.wait_response(transaction)

                for _ in range(self._cli_config.interval * 10):
                    self.wait(0.1)
                    self.application.processEvents()

            if not self._cli_config.repeat:
                break

    def run_api_mode(self):
        logger.info("Run command line API mode")
        self._api_thread = ApiThread(self.config)
        self._api_thread.setup(terminal=self)
        self._api_thread.create_transaction.connect(self.send)
        self._api_thread.run_api.emit()

    def send(self, transaction: Transaction):
        if self.connector.connection_in_progress():
            transaction.success = False
            transaction.error = "Cannot send the transaction while the host connection is in progress"
            logger.error(transaction.error)
            return

        if self.spec.is_reversal(transaction.message_type) and not transaction.trans_id.endswith("_R"):
            transaction.trans_id = f"{transaction.trans_id}_R"

        if not transaction.is_keep_alive:
            logger.info(f"Processing transaction ID [{transaction.trans_id}]")

        if self.config.fields.send_internal_id:
            transaction: Transaction = self.generator.set_trans_id(transaction)

        if transaction.generate_fields:
            transaction: Transaction = self.generator.set_generated_fields(transaction)

        validation_conditions = (
            self.config.validation.validation_enabled,
            self.config.validation.validate_outgoing,
            not transaction.is_keep_alive,
        )

        if all(validation_conditions):
            try:
                self.trans_validator.validate_transaction(transaction)

            except DataValidationWarning as validation_warning:
                [logger.warning(warn) for warn in str(validation_warning).splitlines()]

            except Exception as validation_error:
                transaction.success = False
                transaction.error = str(validation_error)
                [logger.error(err) for err in transaction.error.splitlines()]
                return

        try:
            Terminal.send(self, transaction)  # Terminal always used to real data processing

        except Exception as sending_error:
            transaction.success = False
            transaction.error = f"Transaction sending error: {sending_error}"
            logger.error(transaction.error)
            return

    def show_license_dialog(self) -> None:
        license_info: LicenseInfo = self.get_license_info()

        if license_info.accepted:
            logger.info("")
            logger.info(f"License ID {license_info.license_id} accepted {license_info.last_acceptance_date:%d/%m/%Y %T} UTC")
            return

        print(TextConstants.HELLO_MESSAGE)
        print("")
        print("  Welcome to SIGNAL Command Line Mode!")
        print("")
        print("  SIGNAL distributes under GNU/GPL license as a free software. "
              "To proceed work you have to read and accept license agreement")
        print("")
        print("")

        show_license = None

        while not str(show_license).lower().strip() in ("yes", "y"):
            try:
                show_license = input(
                    '  Type "yes" or "y" to see the license agreement or press "Ctrl + C" to reject the license: ')

            except KeyboardInterrupt:
                logger.error("License agreement rejected, exiting")
                raise LicenseRejected

        agreement_path = f"{getcwd()}/{TermFilesPath.LICENSE_AGREEMENT}"
        agreement_path = path.normpath(agreement_path)

        if not isfile(agreement_path):
            raise ValueError("Lost license agreement text file")

        system(f"more {agreement_path}")
        print("")
        print("")
        print("  To proceed you have to accept the license agreement")
        print("")

        accepted = None

        while not str(accepted).lower().strip() in ("yes", "y"):
            try:

                accepted = input(
                    '  Type "yes" or "y" to accept the license agreement or press "Ctrl + C" to reject the license: ')

            except KeyboardInterrupt:
                logger.error("License agreement rejected, exiting")
                raise LicenseRejected

        logger.info(f"The license accepted! License ID {license_info.license_id}")

        license_info.accepted = True
        license_info.show_agreement = False
        license_info.last_acceptance_date = datetime.now(UTC)

        self.save_license_file(license_info)

    @staticmethod
    def save_license_file(license_info: LicenseInfo) -> None:
        try:
            with open(TermFilesPath.LICENSE_INFO, 'w') as license_info_file:
                license_info_file.write(license_info.model_dump_json())

        except Exception as file_saving_error:
            logger.error(file_saving_error)

    def get_files_to_process(self) -> list[str]:
        filenames: list[str] = list()

        if self._cli_config.dir:
            dir_files = listdir(self._cli_config.dir)
            dir_files = ["/".join([str(self._cli_config.dir), file]) for file in dir_files]

            filenames.extend(dir_files)

        if self._cli_config.file:
            filenames.extend(glob(self._cli_config.file))

        filenames = map(normpath, filenames)
        filenames = [filename for filename in filenames if isfile(filename)]
        filenames = list(set(filenames))

        if self._cli_config.default:
            filenames.insert(int(), TermFilesPath.DEFAULT_FILE)

        if self._cli_config.echo_test:
            filenames.insert(int(), TermFilesPath.ECHO_TEST)

        return filenames

    def parse_cli_config(self, cli_config: CliConfig):
        if cli_config.config_file != TermFilesPath.CONFIG:
            with open(cli_config.config_file) as json_config:
                self.config = Config.model_validate_json(json_config.read())

        self.config.host.host = str(cli_config.address) if cli_config.address else self.config.host.host
        self.config.host.port = int(cli_config.port) if cli_config.port else self.config.host.port
        self.config.debug.level = cli_config.log_level if cli_config.log_level else self.config.debug.level

    def wait_response(self, request: Transaction):
        while not request.matched:
            if (datetime.now() - request.sending_time).total_seconds() > self._cli_config.timeout:
                return

            self.wait(0.1)

    def wait(self, sec):
        sleep(sec)
        self.application.processEvents()

    @staticmethod
    def get_license_info():
        if not path.isfile(TermFilesPath.LICENSE_INFO):
            license_info = LicenseInfo()

            SignalCli.save_license_file(license_info)

            return license_info

        try:
            with open(TermFilesPath.LICENSE_INFO) as license_json:
                license_info = LicenseInfo.model_validate_json(license_json.read())

        except Exception:
            return license_info

        return license_info
