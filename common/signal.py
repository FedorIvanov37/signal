#
#  ::::::::  :::::::::::  ::::::::   ::::    :::      :::      :::
# :+:    :+:     :+:     :+:    :+:  :+:+:   :+:    :+: :+:    :+:
# +:+            +:+     +:+         :+:+:+  +:+   +:+   +:+   +:+
# +#++:++#++     +#+     :#:         +#+ +:+ +#+  +#++:++#++:  +#+
#        +#+     +#+     +#+   +#+#  +#+  +#+#+#  +#+     +#+  +#+
# #+#    #+#     #+#     #+#    #+#  #+#   #+#+#  #+#     #+#  #+#
#  ########  ###########  ########   ###    ####  ###     ###  ##########
#
# Signal starting script
#
# This script make preparation and runs Signal GUI or CLI, depending on start arguments.
#
# The script starts GUI or CLI only. If you're using library see application example is the User Reference Guide
#
# The Signal started once the file is imported, no additional actions are required
#
# Example of the script run command: "from common import signal"
#


__author__ = "Fedor Ivanov"
__version__ = "v0.19.1"


error_message = """
The file common/signal.py should be imported from the main working directory, the direct run has no effect
The GUI runs once the file is imported, no additional actions are required
Please, refer to the Signal documentation to read more about how to run the application
"""


def start_preparation():  # General preparation to run the application in any mode
    from os import makedirs
    from contextlib import suppress
    from common.lib.enums.TermFilesPath import TermDirs

    for directory in TermDirs:  # Create important project directories in case when some of them don't exist
        makedirs(directory, exist_ok=True)

    with suppress(Exception):  # Remove redundant log entries from PyQt media player
        from PyQt6.QtCore import QLoggingCategory
        QLoggingCategory.setFilterRules("qt.multimedia.*=false\nqt.multimedia.ffmpeg.*=false")  # Reduce redundant log


def cli_mode_requested() -> bool:
    from sys import argv
    from common.cli.enums.CliDefinition import CliDefinition
    return any(arg in argv for arg in CliDefinition)


def run_cli_mode() -> int:
    from common.run.run_signal_cli import run_signal_cli
    return run_signal_cli()


def run_gui_mode() -> int:
    from common.run.run_signal_gui import run_signal_gui
    return run_signal_gui()


def run_signal() -> int:  # Begin Signal
    from sys import stderr

    try:
        start_preparation()

        if cli_mode_requested():
            return run_cli_mode()

        return run_gui_mode()

    except Exception as run_error:
        print(f"Signal starting error: {run_error}", file=stderr)
        return 100


# Incorrect way to run
if __name__ == "__main__":  # Do not run directly, runs only by import command
    raise RuntimeError(error_message)


raise SystemExit(run_signal())  # Correct way to run using import
