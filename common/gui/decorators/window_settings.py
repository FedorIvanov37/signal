from PyQt6.QtWidgets import QDialog, QApplication, QLabel, QWidget
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPalette
from PyQt6.QtCore import Qt, QObject, QEvent, QTimer
import ctypes
import sys
from common.gui.enums.GuiFilesPath import GuiFilesPath


"""

This set of decorators is used to set an universal settings for each window during window creation 

The decorator will bring the window to the state described in the decorator's function 

Use it to set a logo, select a window type, etc. Window settings can be changed during operation. Restarting the window 
is required to change the settings, restarting SVTerminal is not required

"""


# Set default window icon before show window. Will not have any effect on the frameless windows
LOGO_THEME_COLORS = {
    '#282828': '#EBDBB2',
    '#2E3440': '#D8DEE9',
    '#282A36': '#BD93F9',
    '#1E1E2E': '#B4BEFE',
    "#292D32": "#A5AFBC",
    "#2D3742": "#9EACBA",
    "#2C3935": "#A2B4A8",
    "#38323C": "#B1A5B8",
    "#24658C": "#A5AFBC",
    "#124B70": "#A5AFBC",
    "#012E4F": "#A5AFBC",
    "#011627": "#A5B57A",
    "#243447": "#7EA6C4",
    "#102D28": "#79BC87",
    "#3B202B": "#D58B77",
    "#000000": "#737373",
}


def themed_logo(path, dark_color=None):
    pixmap = QPixmap(path)
    override = QApplication.instance().property('signalLogoColor') if str(path) in (
        str(GuiFilesPath.MAIN_LOGO), str(GuiFilesPath.SIGNED_LOGO)) else None
    if (override or QApplication.instance().property("signalDarkTheme")) and not pixmap.isNull():
        if override:
            dark_color = override
        if dark_color is None:
            dark_color = LOGO_THEME_COLORS.get(QApplication.instance().property("signalWindowColor"), "#A5AFBC")
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(dark_color))
        painter.end()
    return pixmap


def apply_caption_theme(window):
    app = QApplication.instance()
    if (sys.platform != "win32" or app.platformName() != "windows"
            or not window.isWindow() or not window.isVisible()
            or window.windowFlags() & Qt.WindowType.FramelessWindowHint):
        return
    background = window.palette().color(QPalette.ColorRole.Window)
    text = window.palette().color(QPalette.ColorRole.WindowText)
    setter = ctypes.windll.dwmapi.DwmSetWindowAttribute
    setter.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    setter.restype = ctypes.c_long
    for attribute, color in ((35, background), (36, text)):
        value = ctypes.c_uint32(color.red() | color.green() << 8 | color.blue() << 16)
        # Unsupported Windows versions ignore these optional caption attributes.
        setter(int(window.winId()), attribute, ctypes.byref(value), ctypes.sizeof(value))


class CaptionThemeFilter(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QWidget) and event.type() in (QEvent.Type.Show, QEvent.Type.WindowActivate):
            apply_caption_theme(watched)
            if watched.isWindow():
                from common.gui.toolkit.create_gui_elements import set_button_hints
                set_button_hints(watched)
        return False


class LogoClickFilter(QObject):
    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton):
            toggle_logo_animation()
            return True
        return False


def enable_logo_click(label):
    if not hasattr(label, '_logo_click_filter'):
        label._logo_click_filter = LogoClickFilter(label)
        label.installEventFilter(label._logo_click_filter)


def refresh_window_logos():
    app = QApplication.instance()
    if not hasattr(app, "_signal_caption_filter"):
        app._signal_caption_filter = CaptionThemeFilter(app)
        app.installEventFilter(app._signal_caption_filter)
    icon = QIcon(themed_logo(GuiFilesPath.MAIN_LOGO))
    app.setWindowIcon(icon)
    for window in app.topLevelWidgets():
        window.setWindowIcon(icon)
        apply_caption_theme(window)
    for widget in app.allWidgets():
        if isinstance(widget, QLabel) and widget.property('signalPreviewLogo'):
            widget.setPixmap(themed_logo(GuiFilesPath.MAIN_LOGO).scaled(
                36, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if widget.property("signalMusicIcon"):
            widget.setIcon(QIcon(themed_logo(widget.property("signalMusicIcon"), "#FFFFFF")))
        if isinstance(widget, QLabel) and (widget.objectName() in ("logoLabel", "LogoLabel")
                                          or widget.property('signalLogoPath')):
            pixmap = themed_logo(widget.property("signalLogoPath") or GuiFilesPath.SIGNED_LOGO)
            if widget.property('signalLogoSize'):
                pixmap = pixmap.scaled(widget.property('signalLogoSize'), Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            widget.setPixmap(pixmap)


def toggle_logo_animation():
    app = QApplication.instance()
    if not hasattr(app, '_logo_animation_timer'):
        app._logo_animation_timer = QTimer(app)
        app._logo_animation_timer.setInterval(1000)
        app._logo_animation_timer.timeout.connect(cycle_logo_color)
        app.aboutToQuit.connect(app._logo_animation_timer.stop)
    timer = app._logo_animation_timer
    if timer.isActive():
        timer.stop()
    else:
        cycle_logo_color()
        timer.start()


def cycle_logo_color():
    app = QApplication.instance()
    colors = ['#FF6B35', '#FFD23F', '#A8E63D', '#00D9A6', '#00CFFF',
              '#668CFF', '#B06CFF', '#F35CDE', '#FF5C8A']
    current = app.property('signalLogoColor') or LOGO_THEME_COLORS.get(app.property('signalWindowColor'))
    index = colors.index(current) + 1 if current in colors else 0
    app.setProperty('signalLogoColor', colors[index % len(colors)])
    refresh_window_logos()


def set_application_identity():
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MainWindow')
    QApplication.instance().setWindowIcon(QIcon(themed_logo(GuiFilesPath.MAIN_LOGO)))


def set_window_icon(setup_function: callable):

    def wrapper(window: QDialog, *args, **kwargs):
        window.setWindowIcon(QIcon(themed_logo(GuiFilesPath.MAIN_LOGO)))
        setup_function(window, *args, **kwargs)
        from common.gui.toolkit.create_gui_elements import set_button_hints
        set_button_hints(window)

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
