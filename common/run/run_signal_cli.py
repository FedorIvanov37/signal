from pathlib import Path
from common.cli.core.SignalCli import SignalCli
from common.lib.data_models.Config import Config
from common.lib.core.CustomConfigFile import CustomConfigFile


def run_signal_cli() -> int:
    custom_config: CustomConfigFile = CustomConfigFile(add_help=False)  # Config file can be rewritten in CLI mode
    config_file = custom_config.get_config_filename()  # Get the config file name
    config: Config = Config.model_validate_json(Path(config_file).read_text())
    cli: SignalCli = SignalCli(config)
    status: int = cli.run_application()

    return status  # Exit status
