from common.gui.forms.settings_window import Ui_SettingsWindow
from logging import getLogger, getLevelName
from loguru import logger
from socket import gethostname, gethostbyname
from PyQt6.QtCore import QRegularExpression, pyqtSignal
from common.lib.constants import LogDefinition
from common.lib.data_models.Config import Config
from common.lib.enums.TermFilesPath import TermFilesPath
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.lib.enums.ReleaseDefinition import ReleaseDefinition
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QDialog, QDialogButtonBox
from PyQt6.QtGui import (
    QRegularExpressionValidator,
    QIntValidator,
    QPixmap,
    QIcon,
    QDesktopServices,
    QCloseEvent,
    QKeyEvent,
    QMovie,
)


class SettingsWindow(Ui_SettingsWindow, QDialog):
    _open_user_guide: pyqtSignal = pyqtSignal()
    _open_api_url: pyqtSignal = pyqtSignal(str)
    audio_output = QAudioOutput()
    player = QMediaPlayer()
    movie: QMovie

    @property
    def open_api_url(self):
        return self._open_api_url

    @property
    def open_user_guide(self):
        return self._open_user_guide

    def __init__(self, config: Config, about: bool = False):
        super().__init__()
        self.setupUi(self)
        self.config = config
        self.setup(about=about)

    @set_window_icon
    @has_close_button_only
    def setup(self, about: bool = False):
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(GuiFilesPath.VVVVVV))
        self.MainTabs.tabBar().setDocumentMode(True)
        self.MainTabs.tabBar().setExpanding(True)
        self.SvAddress.setValidator(QRegularExpressionValidator(QRegularExpression(r"(\d+\.){1,3}\d+")))
        self.MaxAmount.setEditable(True)
        self.RemoteSpecUrl.editingFinished.connect(lambda: self.RemoteSpecUrl.setCursorPosition(int()))
        self.MaxAmount.setValidator(QIntValidator(1, 2_100_000_000, self.MaxAmount))
        self.DebugLevel.addItems(LogDefinition.LOG_LEVEL)
        self.ParseSubfields.setHidden(True)  # TODO

        for button_box in self.GeneralButtonBox, self.FieldsButtonBox, self.ApiButtonBox, self.SpecificationButtonBox:
            button_box.accepted.connect(self.ok)
            button_box.rejected.connect(self.cancel)
            button_box.clicked.connect(self.process_default_button)

        self.HeaderLength.textChanged.connect(self.validate_header_length)
        self.DebugLevel.currentIndexChanged.connect(self.process_debug_level_change)
        self.KeepAliveMode.stateChanged.connect(lambda state: self.KeepAliveInterval.setEnabled(bool(state)))
        self.HeaderLengthMode.stateChanged.connect(lambda state: self.HeaderLength.setEnabled(bool(state)))
        self.MaxAmountBox.stateChanged.connect(lambda state: self.MaxAmount.setEnabled(bool(state)))
        self.LoadSpec2.stateChanged.connect(lambda: self.LoadSpec.setChecked(self.LoadSpec2.isChecked()))
        self.LoadSpec.stateChanged.connect(lambda: self.LoadSpec2.setChecked(self.LoadSpec.isChecked()))
        self.ValidationEnabled.stateChanged.connect(self.process_validation_change)
        self.ManualInputMode.stateChanged.connect(self.process_manual_entry_mode_change)
        self.ApiInfoLabel.linkActivated.connect(lambda: self.open_user_guide.emit())
        self.ApiAddress.linkActivated.connect(lambda: self.open_api_url.emit(self.get_api_url()))
        self.ApiPort.textChanged.connect(self.set_api_url)
        self.MusicOnOfButton.clicked.connect(self.switch_music)
        self.ContactLabel.linkActivated.connect(self.open_url)
        self.process_validation_change()
        self.process_manual_entry_mode_change()
        self.process_config(self.config)
        self.set_data_about()
        self.MainTabs.setCurrentIndex(self.MainTabs.count() - 1 if about else int())

    def process_config(self, config: Config):
        checkboxes_state_map = {
            self.MaxAmountBox: config.fields.max_amount_limited,
            self.ProcessDefaultDump: config.terminal.process_default_dump,
            self.ConnectOnStartup: config.terminal.connect_on_startup,
            self.ClearLog: config.debug.clear_log,
            self.ParseSubfields: config.debug.parse_subfields,
            self.BuildFld90: config.fields.build_fld_90,
            self.SendInternalId: config.fields.send_internal_id,
            self.ValidateWindow: config.validation.validate_window,
            self.JsonMode: config.fields.json_mode,
            self.KeepAliveMode: config.host.keep_alive_mode,
            self.HeaderLengthMode: config.host.header_length_exists,
            self.HideSecrets: config.fields.hide_secrets,
            self.RewriteLocalSpec: config.specification.rewrite_local_spec,
            self.LoadSpec: config.terminal.load_remote_spec,
            self.LoadSpec2: config.terminal.load_remote_spec,
            self.ShowLicense: config.terminal.show_license_dialog,
            self.ValidateIncoming: config.validation.validate_incoming,
            self.ValidateOutgoing: config.validation.validate_outgoing,
            self.ManualInputMode: config.specification.manual_input_mode,
            self.ValidationEnabled: config.validation.validation_enabled,
            self.ApiRun: config.terminal.run_api,
            self.ReduceKeepAlive: config.debug.reduce_keep_alive,
            self.WaitForRemoteHost: config.api.wait_remote_host_response,
            self.HideSecretsApi: config.api.hide_secrets,
            self.ParseComplexFields: config.api.parse_subfields,
        }

        scales_value_map = {
            self.SvPort: config.host.port,
            self.KeepAliveInterval: config.host.keep_alive_interval,
            self.HeaderLength: config.host.header_length,
            self.StorageDepth: config.specification.backup_storage_depth,
            self.LogStorageDepth: config.debug.backup_storage_depth,
            self.ApiPort: self.config.api.port,
        }

        for checkbox, state in checkboxes_state_map.items():
            checkbox.setChecked(state)

        for scale, value in scales_value_map.items():
            scale.setValue(int(value))

        self.DebugLevel.setCurrentText(config.debug.level)
        self.HeaderLength.setEnabled(config.host.header_length_exists)
        self.KeepAliveInterval.setEnabled(self.KeepAliveMode.isChecked())
        self.MaxAmount.setEnabled(self.MaxAmountBox.isChecked())
        self.SvAddress.setText(config.host.host)
        self.RemoteSpecUrl.setText(config.specification.remote_spec_url)
        self.RemoteSpecUrl.setCursorPosition(int())
        self.ValidationReaction.setCurrentIndex(self.ValidationReaction.findText(config.validation.validation_mode))
        self.set_api_url()

        if not config.fields.max_amount_limited:
            return

        max_amount: str = str(config.fields.max_amount)

        if (index := self.MaxAmount.findText(max_amount)) < int():  # If the max_amount from config is not found
            index: int = int()
            self.MaxAmount.insertItem(index, max_amount)

        self.MaxAmount.setCurrentIndex(index)

    def set_api_url(self):
        api_url = self.get_api_url()
        api_url_link = f'<html><head/><body><p><a href="www.a.com"><span style=" text-decoration: underline; color:#0000ff;">{api_url}</span></a></p></body></html>'
        self.ApiAddress.setText(api_url_link)

    def get_api_url(self):
        return f"http://{gethostbyname(gethostname())}:{self.ApiPort.value()}/api"

    def process_default_button(self, button):
        for button_box in self.GeneralButtonBox, self.FieldsButtonBox, self.ApiButtonBox, self.SpecificationButtonBox:
            if button_box.buttonRole(button) == QDialogButtonBox.ButtonRole.ResetRole:
                self.set_default_settings()
                break

    def process_manual_entry_mode_change(self):
        if not self.ManualInputMode.isChecked():
            return

        self.ValidationEnabled.setChecked(False)

    def process_validation_change(self):
        validation_elements = (
            self.ValidateWindow,
            self.ValidateIncoming,
            self.ValidateOutgoing,
            self.ValidationModeLabel,
            self.ValidationReaction,
        )

        for element in validation_elements:
            element.setEnabled(self.ValidationEnabled.isChecked())

    def set_data_about(self):
        self.logoLabel.setPixmap(QPixmap(GuiFilesPath.SIGNED_LOGO))
        self.MusicOnOfButton.setIcon(QIcon(QPixmap(GuiFilesPath.MAIN_LOGO)))
        self.MusicOnOfButton.setIcon(QIcon(QPixmap(GuiFilesPath.MUSIC_ON)))

        data_bind = {
            self.VersionLabel: ReleaseDefinition.VERSION,
            self.ReleaseLabel: ReleaseDefinition.RELEASE,
            self.ContactLabel: ReleaseDefinition.CONTACT,
            self.AuthorLabel: ReleaseDefinition.AUTHOR,
        }

        for label, text in data_bind.items():
            label.setText(f"{label.text()} {text}")

        self.player.playbackStateChanged.connect(self.record_finished)

    def set_default_settings(self) -> None:
        try:
            with open(TermFilesPath.DEFAULT_CONFIG) as json_file:
                default_config: Config = Config.model_validate_json(json_file.read())

        except Exception as parsing_error:
            logger.error(parsing_error)
            return

        default_config.host.host = self.config.host.host
        default_config.host.port = self.config.host.port
        default_config.specification.remote_spec_url = self.config.specification.remote_spec_url
        default_config.specification.rewrite_local_spec = self.config.specification.rewrite_local_spec
        default_config.api.address = self.config.api.address
        default_config.api.port = self.config.api.port

        self.process_config(default_config)

    def validate_header_length(self) -> None:
        header_length: int = int(self.HeaderLength.value())

        if self.HeaderLengthMode.isChecked() and self.HeaderLength.value() < 2:
            self.HeaderLength.setValue(2)

        if header_length % 2 != int():
            self.HeaderLength.setValue(header_length - 1)

    def process_debug_level_change(self) -> None:
        disabled: bool = False
        checked: bool = self.config.debug.clear_log

        if self.DebugLevel.currentText() == LogDefinition.DebugLevels.DEBUG:
            checked: bool = False
            disabled: bool = True

        for checkbox in self.ClearLog, self.HideSecrets:
            checkbox.setChecked(checked)
            checkbox.setDisabled(disabled)

    def ok(self) -> None:
        getLogger().setLevel(getLevelName(self.DebugLevel.currentText()))

        config = self.config

        config.host.host = self.SvAddress.text()
        config.host.port = self.SvPort.value()
        config.host.keep_alive_mode = self.KeepAliveMode.isChecked()
        config.host.header_length_exists = self.HeaderLengthMode.isChecked()
        config.host.keep_alive_interval = self.KeepAliveInterval.value()
        config.host.header_length = self.HeaderLength.value()
        config.terminal.process_default_dump = self.ProcessDefaultDump.isChecked()
        config.terminal.connect_on_startup = self.ConnectOnStartup.isChecked()
        config.terminal.load_remote_spec = self.LoadSpec.isChecked()
        config.terminal.show_license_dialog = self.ShowLicense.isChecked()
        config.debug.parse_subfields = self.ParseSubfields.isChecked()
        config.debug.backup_storage_depth = self.LogStorageDepth.value()
        config.debug.clear_log = self.ClearLog.isChecked()
        config.debug.level = self.DebugLevel.currentText()
        config.fields.max_amount_limited = self.MaxAmountBox.isChecked()
        config.fields.max_amount = int(self.MaxAmount.currentText())
        config.fields.build_fld_90 = self.BuildFld90.isChecked()
        config.fields.send_internal_id = self.SendInternalId.isChecked()
        config.fields.json_mode = self.JsonMode.isChecked()
        config.fields.hide_secrets = self.HideSecrets.isChecked()
        config.specification.rewrite_local_spec = self.RewriteLocalSpec.isChecked()
        config.specification.backup_storage_depth = self.StorageDepth.value()
        config.validation.validate_window = self.ValidateWindow.isChecked()
        config.validation.validate_incoming = self.ValidateIncoming.isChecked()
        config.validation.validate_outgoing = self.ValidateOutgoing.isChecked()
        config.validation.validation_mode = self.ValidationReaction.currentText()
        config.specification.remote_spec_url = self.RemoteSpecUrl.text()
        config.specification.manual_input_mode = self.ManualInputMode.isChecked()
        config.validation.validation_enabled = self.ValidationEnabled.isChecked()
        config.debug.reduce_keep_alive = self.ReduceKeepAlive.isChecked()
        config.api.port = self.ApiPort.value()
        config.api.wait_remote_host_response = self.WaitForRemoteHost.isChecked()
        config.api.hide_secrets = self.HideSecretsApi.isChecked()
        config.terminal.run_api = self.ApiRun.isChecked()
        config.api.parse_subfields = self.ParseComplexFields.isChecked()

        if not config.fields.max_amount_limited:
            config.fields.max_amount = 9_999_999_999

        with open(TermFilesPath.CONFIG, "w") as file:
            file.write(self.config.model_dump_json(indent=4))

        self.accept()

    def cancel(self) -> None:
        logger.info("Settings applying was canceled")
        self.reject()

    @staticmethod
    def open_url(link):
        link = QUrl(link)
        QDesktopServices.openUrl(link)

    def record_finished(self, state):
        if state == self.player.PlaybackState.StoppedState:
            self.MusicOnOfButton.setIcon(QIcon(QPixmap(GuiFilesPath.MUSIC_ON)))

    def switch_music(self):
        match self.player.playbackState():
            case self.player.PlaybackState.StoppedState:
                icon = GuiFilesPath.MUSIC_OFF
                self.player.play()

            case self.player.PlaybackState.PlayingState:
                icon = GuiFilesPath.MUSIC_ON
                self.player.stop()

            case _:
                return

        self.MusicOnOfButton.setIcon(QIcon(QPixmap(icon)))

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.player.stop()
        a0.accept()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()

        if a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.MainTabs.currentIndex() == self.MainTabs.count() - 1:
                return

            self.GeneralButtonBox.accepted.emit()
