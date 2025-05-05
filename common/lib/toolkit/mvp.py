from PyQt6.QtCore import QCoreApplication, QTimer
from common.lib.data_models.Config import Config
from common.lib.enums.TermFilesPath import TermFilesPath
from common.lib.core.Terminal import Terminal
from common.lib.data_models.Transaction import Transaction
from common.lib.core.FieldsGenerator import FieldsGenerator
from common.lib.core.Logger import Logger

"""
A bit more complicated example, with usage PyQt6 features, logging, and so on

This script not runs QApplication and QEventLoop. Due to that, the script will wait for the answer, also the 
signal-slot model can be used
 
This example illustrates the creation of the PyQt application, which is run and ready for interaction in PyQt style
"""

# The objects preparation

# In case when your solution does not use GUI it is required to create QCoreApplication and set in on the Terminal
application = QCoreApplication([])  # Create the Signal PyQt application

# Create Config object. The Config is a crucial data object, contains basic settings for all the application
config: Config = Config.parse_file(TermFilesPath.CONFIG)
# After the config is created you can set the parameters as you prefer
# e.g.: config.host.port = 16677 and so on

# The Terminal - core of the application, which will be used for sending the transaction
terminal: Terminal = Terminal(config=config, application=application)  # Send previously-made QCoreApplication

# Set the default screen logger up
Logger().create_logger()

# This object will update transaction fields to avoid transaction duplicates
data_generator = FieldsGenerator()

# Parse default transaction file
transaction: Transaction = Transaction.parse_file(TermFilesPath.DEFAULT_FILE)

# Update fields dynamic values such as ID, date and so on
transaction: Transaction = data_generator.set_generated_fields(transaction)


# Create a delayed start timer. This workaround will help to begin the task after the application is started
timer = QTimer()  # This timer will be processed in QEventloop right after the application is executed
timer.setSingleShot(True)  # It signals once the application start
timer.timeout.connect(lambda: terminal.send(transaction))  # Transaction will be one of the first events
timer.start(0)  # Signals timeout immediately


# Finally run the application, which begin the QEventloop and send the transaction
# Due to the part below the application proceed to work, processing PyQt events and signals
terminal.run()  # Run the QCoreApplication
