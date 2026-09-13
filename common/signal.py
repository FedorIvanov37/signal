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


__author__ = "Fedor Ivanov"
__version__ = "v0.21"


if __name__ == "__main__":  # Do not run directly, runs only by import command
    raise RuntimeError("The common/signal.py file should be imported from the main working directory. "
                       "Running it directly has no effect\n"
                       "The GUI starts automatically once the file is imported, so no additional actions are required\n"
                       "Please refer to the Signal documentation for more information on how to run the application")


class SignalRuntime:

    @staticmethod
    def prepare_logging():
        from loguru import logger
        # Console output is configured by CLI only after its banner and arguments.
        logger.remove()

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
        from common.core.data_models.Config import Config
        from common.core.tools.CustomConfigFile import CustomConfigFile

        custom_config: CustomConfigFile = CustomConfigFile(add_help=False)
        custom_config.set_defaults(config_file=None)
        config_file = custom_config.get_config_filename()
        from common.core.tools.StartupConfig import load_startup_config
        config = Config(config_file) if config_file is not None else load_startup_config()[0]
        SignalRuntime.prepare_logging()
        from common.cli.tools.SignalCli import SignalCli
        signal_cli: SignalCli = SignalCli(config)
        status: int = signal_cli.run_application()

        return status

    @staticmethod
    def run_gui_mode() -> int:
        from common.core.data_models.Config import Config
        from common.core.enums.TermFilesPath import TermFilesPath

        from common.core.tools.StartupConfig import load_startup_config
        config, warning = load_startup_config()
        SignalRuntime.prepare_logging()
        from common.gui.tools.SignalGui import SignalGui
        signal_gui: SignalGui = SignalGui(config)
        signal_gui._startup_config_warning = warning
        status: int = signal_gui.run_application()

        return status

    @staticmethod
    def run_signal() -> int:
        from common.core.tools.ErrorReporting import report_error, install_exception_hook
        cli_mode = SignalRuntime.cli_mode_requested()
        previous_hook = install_exception_hook(gui=not cli_mode)

        try:
            if not cli_mode:
                from common.gui.tools.ErrorPresentation import install
                install()
            SignalRuntime.prepare_runtime()

            if cli_mode:
                return SignalRuntime.run_cli_mode()

            return SignalRuntime.run_gui_mode()

        except Exception as run_error:
            report_error(run_error, gui=not cli_mode, title="Signal could not start")
            return 100

        finally:
            import sys
            sys.excepthook = previous_hook


# The script starts here
raise SystemExit(SignalRuntime.run_signal())  # Correct way to run using import
