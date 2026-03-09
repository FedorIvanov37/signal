#
#  ::::::::  :::::::::::  ::::::::   ::::    :::      :::      :::
# :+:    :+:     :+:     :+:    :+:  :+:+:   :+:    :+: :+:    :+:
# +:+            +:+     +:+         :+:+:+  +:+   +:+   +:+   +:+
# +#++:++#++     +#+     :#:         +#+ +:+ +#+  +#++:++#++:  +#+
#        +#+     +#+     +#+   +#+#  +#+  +#+#+#  +#+     +#+  +#+
# #+#    #+#     #+#     #+#    #+#  #+#   #+#+#  #+#     #+#  #+#
#  ########  ###########  ########   ###    ####  ###     ###  ##########
#
# Signal launcher script
#
# This script makes preparation and runs Signal in GUI or CLI mode, depending on start arguments
#
# If you are using Signal as a library, see the example in the User Reference Guide
#
# The Signal started once the file is imported, no additional actions are required
#
# Example of the script run command: "from common import signal"
#

from sys import stderr
from pathlib import Path
from common.lib.data_models.Config import Config


__author__ = "Fedor Ivanov"
__version__ = "v0.19.1"

error_message = """
The file common/Signal.py should be imported from the main working directory, the direct run has no effect
The GUI runs once the file is imported, no additional actions are required
Please, refer to the Signal documentation to read more about how to run the application
"""


class SignalRuntime:

    @staticmethod
    def prepare_runtime():  # General preparation to run the application in any mode
        from os import makedirs
        from contextlib import suppress
        from common.lib.enums.TermFilesPath import TermDirs

        for directory in TermDirs:  # Create important project directories in case when some of them don't exist
            makedirs(directory, exist_ok=True)

        with suppress(Exception):  # Remove redundant log entries from PyQt media player
            from PyQt6.QtCore import QLoggingCategory
            QLoggingCategory.setFilterRules("qt.multimedia.*=false\nqt.multimedia.ffmpeg.*=false")

    @staticmethod
    def read_config(filepath: str | Path) -> Config:
        filepath: Path = Path(filepath)
        config: Config = Config.model_validate_json(filepath.read_text())
        return config

    @staticmethod
    def cli_mode_requested() -> bool:
        from sys import argv
        from common.cli.enums.CliDefinition import CliDefinition
        return any(arg in argv for arg in CliDefinition)

    @staticmethod
    def run_cli_mode() -> int:
        from common.cli.core.SignalCli import SignalCli
        from common.lib.core.CustomConfigFile import CustomConfigFile

        custom_config: CustomConfigFile = CustomConfigFile(add_help=False)
        config_file = custom_config.get_config_filename()
        config: Config = SignalRuntime.read_config(config_file)
        signal_cli: SignalCli = SignalCli(config)
        status: int = signal_cli.run_application()

        return status

    @staticmethod
    def run_gui_mode() -> int:
        from common.gui.core.SignalGui import SignalGui
        from common.lib.enums.TermFilesPath import TermFilesPath

        config: Config = SignalRuntime.read_config(TermFilesPath.CONFIG)
        signal_gui: SignalGui = SignalGui(config)
        status: int = signal_gui.run_application()

        return status

    @staticmethod
    def run_signal() -> int:
        try:
            SignalRuntime.prepare_runtime()

            if SignalRuntime.cli_mode_requested():
                return SignalRuntime.run_cli_mode()

            return SignalRuntime.run_gui_mode()

        except Exception as run_error:
            print(f"Signal starting error: {run_error}", file=stderr)
            return 100


# Incorrect way to run
if __name__ == "__main__":  # Do not run directly, runs only by import command
    raise RuntimeError(error_message)

# The script starts here
raise SystemExit(SignalRuntime.run_signal())  # Correct way to run using import
