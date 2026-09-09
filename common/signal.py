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


__author__ = "Fedor Ivanov"
__version__ = "v0.20.1"


if __name__ == "__main__":  # Do not run directly, runs only by import command
    raise RuntimeError("The common/signal.py file should be imported from the main working directory. "
                       "Running it directly has no effect\n"
                       "The GUI starts automatically once the file is imported, so no additional actions are required\n"
                       "Please refer to the Signal documentation for more information on how to run the application")


from common.core.data_models.Config import Config


class SignalRuntime:

    @staticmethod
    def prepare_runtime():  # General preparation to run the application in any mode
        from os import makedirs
        from contextlib import suppress
        from common.core.enums.TermFilesPath import TermDirs

        for directory in TermDirs:  # Create important project directories in case when some of them don't exist
            if directory is TermDirs.DOC_DIR:
                continue

            makedirs(directory, exist_ok=True)

        with suppress(Exception):  # Remove redundant log entries from PyQt media player
            from PyQt6.QtCore import QLoggingCategory
            QLoggingCategory.setFilterRules("qt.multimedia.*=false\nqt.multimedia.ffmpeg.*=false")

    @staticmethod
    def cli_mode_requested() -> bool:
        from sys import argv
        from common.cli.enums.CliDefinition import CliDefinition
        return any(arg in argv for arg in CliDefinition)

    @staticmethod
    def run_cli_mode() -> int:
        from common.cli.tools.SignalCli import SignalCli
        from common.core.tools.CustomConfigFile import CustomConfigFile

        custom_config: CustomConfigFile = CustomConfigFile(add_help=False)
        config_file = custom_config.get_config_filename()
        config: Config = Config(config_file)
        signal_cli: SignalCli = SignalCli(config)
        status: int = signal_cli.run_application()

        return status

    @staticmethod
    def run_gui_mode() -> int:
        from common.gui.tools.SignalGui import SignalGui
        from common.core.enums.TermFilesPath import TermFilesPath

        config: Config = Config(TermFilesPath.CONFIG)
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


# The script starts here
raise SystemExit(SignalRuntime.run_signal())  # Correct way to run using import
