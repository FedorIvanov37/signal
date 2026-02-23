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
# This script runs Signal GUI or CLI, depending on start arguments. The script starts GUI or CLI only. If you're using
# library see application example is the User Reference Guide
#
# The Signal started once the file is imported, no additional actions are required
#
# Example of the script run command: "from common import signal"
#


__author__ = "Fedor Ivanov"
__version__ = "v0.19.1"


# Incorrect way to run
if __name__ == "__main__":  # Do not run directly, runs only by import command

    error_message = """
The file common/signal.py should be imported from the main working directory, the direct run has no effect
The GUI runs once the file is imported, no additional actions are required
Please, refer to the Signal documentation to read more about how to run the application
"""

    raise RuntimeError(error_message)

# Part below will be done when file is imported

try:
    from contextlib import suppress

    with suppress(Exception):
        from PyQt6.QtCore import QLoggingCategory
        QLoggingCategory.setFilterRules("qt.multimedia.*=false\nqt.multimedia.ffmpeg.*=false")  # Reduce redundant log

    from os import makedirs
    from sys import exit, argv
    from loguru import logger

    from common.lib.enums.TermFilesPath import TermFilesPath, TermDirs
    from common.lib.data_models.Config import Config
    from common.lib.core.CustomConfigFile import CustomConfigFile
    from common.cli.core.SignalCli import SignalCli
    from common.cli.enums.CliDefinition import CliDefinition
    from common.gui.core.SignalGui import SignalGui

    # Preparation to run the Signal

    custom_config: CustomConfigFile = CustomConfigFile(add_help=False)  # Config file can be rewritten in CLI mode

    config_file = custom_config.get_config_filename()  # Get the config file name

    with open(config_file) as json_file:  # Read the config
        config: Config = Config.model_validate_json(json_file.read())

    for directory in TermDirs:  # Create important project directories in case when some of them don't exist
        makedirs(directory, exist_ok=True)

    # Preparation is finished, starting the Signal

    command_line_mode = any(arg in argv for arg in CliDefinition)  # Is Command Line Interface mode requested

    if command_line_mode:  # When CLI mode was requested

        # Run CLI mode

        cli: SignalCli = SignalCli(config)
        cli.run_application()
        exit(int())  # GUI won't be ran after CLI

        # CLI task is finished

    if not command_line_mode:  # When CLI mode was not requested

        # Run Graphic User Interface mode (GUI)

        terminal: SignalGui = SignalGui(config)
        status: int = terminal.run()
        exit(status)

        # GUI session is finished

except Exception as run_exception:
    logger.error(run_exception)
    print(run_exception)
    exit(100)
