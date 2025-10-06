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
# This script runs Signal GUI or CLI, depending on start arguments. The script starts GUI or CLI only
# If you're using library see application example is the User Reference Guide
#
# The Signal started once the file is imported, no additional actions are required
#
# Example of the script run command: "from common import signal"
#

__author__ = "Fedor Ivanov"
__version__ = "v0.19"


# Correct way to run
if __name__ != "__main__":  # Runs only by import coюmmand

    # Preparation to run the Signal 
    
    try:
        from sys import exit, argv
        from os import makedirs
        from common.cli.core.SignalCli import SignalCli
        from common.cli.enums.CliDefinition import CliDefinition
        from common.lib.enums.TermFilesPath import TermFilesPath, TermDirs
        from common.lib.data_models.Config import Config
        from PyQt6.QtCore import QLoggingCategory
        from common.lib.core.CustomConfigFile import CustomConfigFile

        custom_config: CustomConfigFile = CustomConfigFile(add_help=False)  # Config file can be rewritten in CLI move

        config_file = custom_config.get_config_filename()  # Get the config file name
        
        with open(config_file) as json_file:  # Read the config
            config: Config = Config.model_validate_json(json_file.read())

        for directory in TermDirs:  # Create important priject directories in case when some of them don't exist
            makedirs(directory, exist_ok=True)
        
        QLoggingCategory.setFilterRules(  # Reduce redundant log messages from the output
            """qt.multimedia.*=false 
               qt.multimedia.ffmpeg.*=false"""
        )
        
    except Exception as run_preparation_error:
        print(run_preparation_error)
        exit(100)

    # Preparation is finished, let's start it
    
    cli_mode_triggers: tuple = (
        CliDefinition.CONSOLE_MODE,
        CliDefinition.CONSOLE_MODE_LONG,
        CliDefinition.HELP,
        CliDefinition.HELP_LONG,
    )

    if any(arg in argv for arg in cli_mode_triggers):  # In case when CLI mode requested
        cli: SignalCli = SignalCli(config)  # Run in Command Line Interface (CLI) mode
        cli.run_application()
        exit(int())  # GUI won't be ran after CLI

    try:  # Run Graphic User Interface (GUI) mode
        
        from common.gui.core.SignalGui import SignalGui

        terminal: SignalGui = SignalGui(config)

        status: int = terminal.run()

        exit(status)

    except Exception as run_signal_exception:
        print(run_signal_exception)
        exit(100)


# Incorrect way to run
if __name__ == "__main__":  # Do not run directly
    error_message = """
The file common/signal.py should be imported from the main working directory, the direct run has no effect
The GUI runs once the file is imported, no additional actions are required
Please, refer to the Signal documentation to read more about how to run the application
"""

    raise RuntimeError(error_message)
