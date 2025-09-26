from argparse import ArgumentParser
from common.lib.enums.TermFilesPath import TermFilesPath


class CustomConfigFile(ArgumentParser):
    def __init__(self, add_help):
        super(CustomConfigFile, self).__init__(add_help=add_help, description="Custom config parser")

        self.add_argument(
            "--config-file",
            action="store",
            default=TermFilesPath.CONFIG,
            help="Set configuration file path"
        )

    def get_config_filename(self):
        config, others = self.parse_known_args()
        return config.config_file
