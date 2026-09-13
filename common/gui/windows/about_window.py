from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPainter, QIcon, QDesktopServices, QFont, QPalette
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QSizePolicy
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from common.gui.decorators.window_settings import set_window_icon, frameless_window, themed_logo
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.core.enums.ReleaseDefinition import ReleaseDefinition
from common.core.enums.TextConstants import TextConstants


class ProportionalLogo(QLabel):
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            from common.gui.decorators.window_settings import toggle_logo_animation
            toggle_logo_animation()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return
        rect = self.contentsRect()
        size = pixmap.size().scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = rect.__class__(0, 0, size.width(), size.height())
        target.moveCenter(rect.center())
        # The signed image includes empty space below its caption.
        target.moveBottom(rect.bottom() + 12)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(target, pixmap)


class AboutSeparator(QFrame):
    def paintEvent(self, event):
        painter = QPainter(self)
        color = self.palette().color(QPalette.ColorRole.WindowText)
        color.setAlpha(100)
        painter.setPen(color)
        painter.drawLine(0, 0, self.width() - 1, 0)


class AboutWindow(QDialog):
    open_user_guide = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup()

    @set_window_icon
    @frameless_window
    def setup(self):
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('Signal | About')
        self.setFixedSize(430, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(6)
        self.logoLabel = ProportionalLogo(self)
        self.logoLabel.setObjectName('logoLabel')
        self.logoLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.logoLabel.setPixmap(themed_logo(GuiFilesPath.SIGNED_LOGO))
        layout.addWidget(self.logoLabel, 1)
        self.line = AboutSeparator(self)
        self.line.setFixedHeight(1)
        layout.addWidget(self.line)
        layout.addSpacing(12)
        self.UserGuideLink = QLabel(TextConstants.USER_REFERENCE_GUIDE, self)
        self.UserGuideLink.setFont(QFont('Calibri', 12))
        self.UserGuideLink.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.UserGuideLink.linkActivated.connect(self.open_user_guide)
        layout.addWidget(self.UserGuideLink)
        footer = QHBoxLayout()
        details = QVBoxLayout()
        details.setSpacing(6)
        footer.addLayout(details)
        for name, prefix, value in (
            ('VersionLabel', 'Version', ReleaseDefinition.VERSION),
            ('ReleaseLabel', 'Released in', ReleaseDefinition.RELEASE),
            ('AuthorLabel', 'Developed by', ReleaseDefinition.AUTHOR),
            ('ContactLabel', 'Contact', ReleaseDefinition.CONTACT),
        ):
            label = QLabel(f'{prefix} {value}', self)
            label.setFont(QFont('Calibri', 12))
            setattr(self, name, label)
            label.linkActivated.connect(lambda link: QDesktopServices.openUrl(QUrl(link)))
            details.addWidget(label)
        footer.addStretch()
        self.MusicOnOfButton = QPushButton(self)
        self.MusicOnOfButton.setFixedSize(30, 24)
        music_layout = QVBoxLayout()
        music_layout.setSpacing(0)
        music_layout.addStretch()
        music_layout.addWidget(self.MusicOnOfButton)
        music_layout.addSpacing(3)
        footer.addLayout(music_layout)
        layout.addLayout(footer)
        self.audio_output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(GuiFilesPath.VVVVVV))
        self.set_music_icon(GuiFilesPath.MUSIC_ON)
        self.MusicOnOfButton.clicked.connect(self.switch_music)
        self.player.playbackStateChanged.connect(self.record_finished)

    def record_finished(self, state) -> None:
        if state == self.player.PlaybackState.StoppedState:
            self.set_music_icon(GuiFilesPath.MUSIC_ON)

    def set_music_icon(self, path):
        self.MusicOnOfButton.setProperty("signalMusicIcon", str(path))
        self.MusicOnOfButton.setIcon(QIcon(themed_logo(path, "#FFFFFF")))

    def switch_music(self) -> None:
        match self.player.playbackState():
            case self.player.PlaybackState.StoppedState | self.player.PlaybackState.PausedState:
                icon = GuiFilesPath.MUSIC_OFF
                self.player.play()

            case self.player.PlaybackState.PlayingState:
                icon = GuiFilesPath.MUSIC_ON
                self.player.stop()

            case _:
                return

        self.set_music_icon(icon)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        screen = parent.screen() if parent is not None else self.screen()
        available = screen.availableGeometry()
        target = self.frameGeometry()
        target.moveCenter(parent.frameGeometry().center() if parent is not None else available.center())
        target.moveLeft(max(available.left(), min(target.left(), available.right() - target.width() + 1)))
        target.moveTop(max(available.top(), min(target.top(), available.bottom() - target.height() + 1)))
        self.move(target.topLeft())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
        else:
            super().keyPressEvent(event)

    def done(self, result):
        self.player.stop()
        super().done(result)

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
