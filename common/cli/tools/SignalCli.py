from common.core.tools.DebugTrace import trace_operation
from sys import exit
from glob import glob
from time import sleep
from uuid import uuid4
from os import listdir, path, system, getpid, kill
from os.path import normpath, basename, isfile, abspath
from loguru import logger
from datetime import datetime, timezone
from signal import signal, SIGINT, SIGTERM
from PyQt6.QtCore import QCoreApplication, QTimer, pyqtSignal
from common.core.data_models.Transaction import Transaction
from common.core.data_models.Config import Config
from common.core.enums.TextConstants import TextConstants
from common.cli.data_models.CliConfig import CliConfig
from common.cli.tools.CliArgsParser import CliArgsParser
from common.core.tools.Terminal import Terminal
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.data_models.License import LicenseInfo
from common.core.exceptions.exceptions import LicenseRejected
from common.core.exceptions.exceptions import DataValidationWarning
from common.api.tools.SignalApi import SignalApi
from common.cli.enums.LogMarks import LogMarks


"""

 CLI and API runner for Signal
 
 Extends Terminal with command-line argument handling, license management, file-based transaction processing, 
 and REST API hosting
 
 Use "signal.exe --help" to get the all the params description

"""


class SignalCli(Terminal):
    _cli_config: CliConfig = None
    _finished: pyqtSignal = pyqtSignal()
    _job_id: str = str(uuid4())

    def __init__(self, config: Config):
        super(SignalCli, self).__init__(config, application=QCoreApplication.instance() or QCoreApplication([]))
        self.api = SignalApi(self.config, terminal=self)
        self.run_timer = QTimer()
        self.api_timer = QTimer()
        self._stop_requested = False
        self._exit_code = 0
        self._finish_logged = False
        self._finish_mark = True
        self.connect_all()
        self.setup()

    @trace_operation
    def setup(self):
        self.api.open_connection.connect(self.reconnect)
        self.api.send_transaction.connect(self.send)

        cli_args_parser: CliArgsParser = CliArgsParser(self.config, description=TextConstants.CLI_DESCRIPTION)

        self._cli_config = cli_args_parser.parse_arguments()

        if not self._cli_config.no_print:
            print(f"{TextConstants.HELLO_MESSAGE}\n")

        try:
            self.parse_cli_config(self._cli_config)

        except ValueError as config_parsing_error:
            logger.error(f"Error running in console mode: {config_parsing_error}")
            exit(100)

        self.logger.setup(filename=self._cli_config.log_file)

        if not self._cli_config.no_print:
            self.logger.add_stdout_handler()

        logger.debug("Startup mode selected: CLI; configuration_file={} runtime_log_level={}",
                     self._cli_config.config_file, self.config.debug.level)
        logger.info("Press CTRL+C to exit")
        logger.info(str())
        logger.info(LogMarks.BEGIN % self._job_id)

        try:
            self.show_license_dialog()
        except LicenseRejected:
            exit(100)

        if self._cli_config.specification == TermFilesPath.SPECIFICATION:
            return

        logger.info(f"Trying to apply custom specification {self._cli_config.specification}")

        try:
            self.spec.parse_file(self._cli_config.specification, config=self.config)

        except Exception as spec_parsing_error:
            logger.error(f"Custom specification parsing error: {spec_parsing_error}")
            logger.error("Default specification will be used instead")

        else:
            logger.info("Custom specification successfully applied")

    def connect_all(self):
        self._finished.connect(self.pyqt_application.quit)
        self.run_timer.timeout.connect(self.main)
        self.api_timer.timeout.connect(self._check_stop)

    def _request_stop(self, signum, frame):
        # Python signal handlers may run inside a SIP/Qt call. Never raise or
        # destroy Qt objects here; unwind the active operation normally first.
        self._stop_requested = True
        self._exit_code = 128 + signum

    def _check_stop(self):
        if self._stop_requested:
            self.finish(self._exit_code)

    def run_application(self):
        previous_handlers = {sig: signal(sig, self._request_stop) for sig in (SIGINT, SIGTERM)}
        self.run_timer.setSingleShot(True)
        self.run_timer.start(0)
        self.api_timer.start(100)
        try:
            return self.pyqt_application.exec()
        finally:
            self.run_timer.stop()
            self.api_timer.stop()
            self.keep_alive_timer._trans_loop_timer.stop()
            for timer in self.trans_queue.timers.values():
                timer.stop()
            if self.api.is_started():
                self.api.stop()
            self.connector.abort()
            for sig, handler in previous_handlers.items():
                signal(sig, handler)
            if self._finish_mark and not self._finish_logged:
                self._finish_logged = True
                logger.info(LogMarks.FINISH % self._job_id)

    @trace_operation
    def main(self):

        """

        This is the main function, which runs after CLI mode begin

        Important: --repeat flag has a priority over --api-mode. When --repeat flag set along with the --api-mode
        API mode will never run because the files will be parsed and sent in an endless cycle

        """

        if self._cli_config.repeat and self._cli_config.api_mode:
            logger.error("Mutually exclusive flags --repeat and --api-mode are set")
            kill(getpid(), 9)

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

        if self._cli_config.api_mode:
            self.api_timer.start(100)

            if files := self.get_files_to_process():
                logger.warning(f"Signal started in API mode, file processing skipped: {', '.join(files)}")

            self.api.start()

            return

        if not (filenames := self.get_files_to_process()):
            if not any([self._cli_config.about, self._cli_config.version]):
                logger.warning("No files specified for processing")

            self.finish()
            return

        while not self._stop_requested:
            for file in filenames:
                if self._stop_requested:
                    break
                logger.info(str())
                logger.info(f"Processing file {basename(file)}")

                try:
                    transaction: Transaction = self.parser.parse_file(file)
                except Exception as parsing_error:
                    logger.error(parsing_error)
                    continue

                self.send(transaction)
                if self._stop_requested:
                    break

                if not self._cli_config.parallel:
                    self.wait_response(transaction)

                for _ in range(self._cli_config.interval * 10):
                    if self._stop_requested:
                        break
                    self.wait(0.1)
                    self.pyqt_application.processEvents()

            if not self._cli_config.repeat:
                break

        self.finish(self._exit_code)

    @trace_operation
    def finish(self, code=0, mark=True):
        self._stop_requested = True
        self._exit_code = code
        self._finish_mark = mark

        self.pyqt_application.exit(code)

    @trace_operation
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
            logger.debug("")
            logger.debug(
                f"License ID {license_info.license_id} accepted {license_info.last_acceptance_date:%d/%m/%Y %T} UTC"
            )

            return

        print(TextConstants.HELLO_MESSAGE)
        print("")
        print("  Welcome to Signal Command Line Mode!")
        print("")
        print("  Signal distributes under GNU/GPL license as a free software. "
              "To proceed work you have to read and accept license agreement")
        print("")
        print("")

        show_license = None

        while not str(show_license).lower().strip() in ("yes", "y"):
            try:
                show_license = input(
                    '  Type "yes" or "y" to see the license agreement or press "Ctrl + C" to reject the license: ')

            except KeyboardInterrupt:
                logger.error("License agreement rejected. Exiting")
                raise LicenseRejected

        agreement_path = abspath(TermFilesPath.LICENSE_AGREEMENT)

        if not isfile(agreement_path):
            raise ValueError("Missing license agreement text file")

        system(f'more "{agreement_path}"')
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
                logger.error("License agreement rejected. Exiting")
                raise LicenseRejected

        logger.info(f"The license was accepted. License ID: {license_info.license_id}")

        license_info.accepted = True
        license_info.show_agreement = False
        license_info.last_acceptance_date = datetime.now(timezone.utc)

        self.save_license_file(license_info)

    @staticmethod
    def save_license_file(license_info: LicenseInfo) -> None:
        try:
            with open(TermFilesPath.LICENSE_INFO, 'w') as license_info_file:
                license_info_file.write(license_info.model_dump_json())

        except Exception as file_saving_error:
            logger.error(file_saving_error)

    @trace_operation
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

    @trace_operation
    def parse_cli_config(self, cli_config: CliConfig):
        candidate = self.config.model_copy(deep=True)
        candidate.host.host = str(cli_config.address) if cli_config.address else candidate.host.host
        candidate.host.port = int(cli_config.port) if cli_config.port else candidate.host.port
        candidate.debug.level = cli_config.log_level if cli_config.log_level else candidate.debug.level
        self.update_config(candidate, persist=False)

    @trace_operation
    def wait_response(self, request: Transaction):
        if not self.spec.get_resp_mti(request.message_type):
            return
        while not self._stop_requested and not request.matched:
            if (datetime.now() - request.sending_time).total_seconds() > self._cli_config.timeout:
                return

            self.wait(0.1)

    def wait(self, sec):
        sleep(sec)
        self.pyqt_application.processEvents()

    @staticmethod
    def get_license_info():
        if not path.isfile(TermFilesPath.LICENSE_INFO):
            license_info = LicenseInfo()

            SignalCli.save_license_file(license_info)

            return license_info

        try:
            license_info = LicenseInfo(TermFilesPath.LICENSE_INFO)

        except Exception:
            return license_info

        return license_info
