from PyQt6.QtWidgets import QDialog
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from common.gui.enums.GuiFilesPath import GuiFilesPath


"""

This set of decorators is used to set an universal settings for each window during window creation 

The decorator will bring the window to the state described in the decorator's function 

Use it to set a logo, select a window type, etc. Window settings can be changed during operation. Restarting the window 
is required to change the settings, restarting SVTerminal is not required

"""


# Set default window icon before show window. Will not have any effect on the frameless windows
def set_window_icon(setup_function: callable):

    def wrapper(window: QDialog, *args, **kwargs):
        window.setWindowIcon(QIcon(GuiFilesPath.MAIN_LOGO))
        setup_function(window, *args, **kwargs)

    return wrapper


# Transform the window to a frameless window, with no close menu, window title, etc. Use the ESC button to close
def frameless_window(setup_function: callable):

    def wrapper(window: QDialog, *args, **kwargs):
        window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        setup_function(window, *args, **kwargs)

    return wrapper


# Remove the right top menu. Such window will have a close button only, buttons that resize and collapse are absent
def has_close_button_only(setup_function: callable):

    def wrapper(window: QDialog, *args, **kwargs):
        window.setWindowFlags(Qt.WindowType.WindowCloseButtonHint)
        setup_function(window, *args, **kwargs)

    return wrapper
