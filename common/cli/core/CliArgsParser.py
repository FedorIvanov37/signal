from argparse import ArgumentParser
from common.cli.data_models.CliConfig import CliConfig
from common.lib.data_models.Config import Config
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.constants.LogDefinition import LOG_LEVEL, DebugLevels


class CliArgsParser(ArgumentParser):
    def __init__(self, config: Config, description: str | None = None):
        if description is None:
            description = str()

        super(CliArgsParser, self).__init__(description=description)
        self.config = config
        self.init_arguments()

    def init_arguments(self):
        self.add_argument("-c", "--console", action="store_true", required=True, help="Run SIGNAL in Command Line Interface mode")
        self.add_argument("-f", "--file", type=str, default=None, help="File or file-mask to parse")
        self.add_argument("-d", "--dir", type=str, default=None, help="Directory with files to parse. SIGNAL will try all of the files from the directory")
        self.add_argument("-a", "--address", default=self.config.host.host, action="store", help="Host TCP/IP address")
        self.add_argument("-p", "--port", type=int, default=self.config.host.port, action="store", help="TCP/IP port to connect")
        self.add_argument("-r", "--repeat", action="store_true", help="Repeat transactions after sending")
        self.add_argument("--log-file", type=str, default=TermFilesPath.LOG_FILE_NAME, action="store", help=f"Set log file path. Default {TermFilesPath.LOG_FILE_NAME}")
        self.add_argument("-l", "--log-level", type=str, default=DebugLevels.INFO, action="store", help=f"Debug level: {', '.join(LOG_LEVEL)}")
        self.add_argument("-i", "--interval", type=int, default=0, action="store", help="Wait (seconds) before send next transaction")
        self.add_argument("--parallel", action="store_true", help="Send new transaction with no waiting of answer for previous one")
        self.add_argument("-t", "--timeout", type=int, default=60, help="Timeout of waiting resp")
        self.add_argument("--about", action="store_true", help="Show info about the SIGNAL")
        self.add_argument("-e", "--echo-test", action="store_true", help="Send echo-test")
        self.add_argument("--default", action="store_true", help="Send default transaction message")
        self.add_argument("-v", "--version", action="store_true", help="Print current version of SIGNAL")
        self.add_argument("--print-config", action="store_true", help="Print configuration parameters")
        self.add_argument("--config-file", action="store", default=TermFilesPath.CONFIG, help="Set configuration file path")
        self.add_argument("--api-mode", action="store_true", default=False, help="Run signal in API mode")

    def parse_arguments(self) -> CliConfig:
        cli_arguments = self.parse_args()
        cli_config = CliConfig.model_validate(cli_arguments.__dict__)

        return cli_config
