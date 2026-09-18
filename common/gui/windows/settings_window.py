from common.gui.toolkit.clipboard import copy_text
from common.core.tools.DebugTrace import trace_operation
from loguru import logger
from logging import getLogger, getLevelName
from common.gui.forms.settings_window import Ui_SettingsWindow
from common.core.enums.TextConstants import TextConstants
from common.gui.enums.KeySequences import KeySequences
from common.core.constants import LogDefinition
from common.core.data_models.Config import Config
from common.core.tools.ConfigStore import save_config
from common.core.tools.ErrorReporting import gui_action, report_error
from common.core.enums.TermFilesPath import TermFilesPath
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from PyQt6.QtCore import Qt, QRegularExpression, pyqtSignal, QEventLoop
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QApplication, QLineEdit, QComboBox, QCheckBox, QAbstractSpinBox, QGroupBox, QPushButton, QWidget, QHBoxLayout
from PyQt6.QtGui import (
    QKeySequence,
    QShortcut,
    QRegularExpressionValidator,
    QIntValidator,
)


class SettingsWindow(Ui_SettingsWindow, QDialog):
    _config: Config = None
    config_file_dropped: pyqtSignal = pyqtSignal(str)
    open_api_spec: pyqtSignal = pyqtSignal()

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config: Config):
        self._config = config

    def __init__(self, config: Config, commit=None, change_color=None, change_colors=None, commit_theme=None):
        super().__init__()
        self.setupUi(self)
        self.AutoSortFields = QCheckBox('Automatically sort fields', self.FieldsBox)
        self.AutoSortFields.setObjectName('AutoSortFields')
        self.gridLayout_5.addWidget(self.AutoSortFields, 5, 0, 1, 1)
        self.config = config.model_copy(deep=True)
        self.commit = commit or save_config
        self.commit_theme = commit_theme or self.commit
        from common.gui.windows.appearance_tab import AppearanceTab
        self.Appearance = AppearanceTab(change_color, self)
        self.Appearance.set_colors(self.config.theme.colors())
        self.Appearance.initial_colors = dict(self.Appearance.colors)
        self.Appearance.change_colors = change_colors
        if change_colors is not None:
            for button in self.Appearance.color_buttons:
                button.setEnabled(True)
        self.ThemeButtonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                               | QDialogButtonBox.StandardButton.Cancel
                                               | QDialogButtonBox.StandardButton.RestoreDefaults)
        self.Appearance.layout().addWidget(self.ThemeButtonBox)
        self.ApplyThemeButton = QPushButton('Apply theme', self.Appearance)
        self.ApplyThemeButton.setAutoDefault(False)
        self.ApplyThemeButton.clicked.connect(lambda: self.apply_theme())
        self.DefaultThemeButton = QPushButton('Reset theme', self.Appearance)
        self.DefaultThemeButton.setAutoDefault(False)
        self.DefaultThemeButton.setToolTip('Apply the default theme now')
        self.DefaultThemeButton.clicked.connect(self.set_default_theme)
        self.MainTabs.addTab(self.Appearance, 'Theme')
        self.setup()
        self._initial_control_values = [
            (widget, self._control_value(widget))
            for widget in self.findChildren((QLineEdit, QComboBox, QCheckBox, QAbstractSpinBox))
        ]
        self.ensurePolished()
        for index in range(self.MainTabs.count()):
            page_layout = self.MainTabs.widget(index).layout()
            margins = page_layout.contentsMargins()
            page_layout.setContentsMargins(margins.left(), margins.top(), 0, margins.bottom())
        right_controls = (self.SvPort, self.HeaderLength, self.KeepAliveInterval,
                          self.DebugLevel, self.LogStorageDepth, self.MaxAmount,
                          self.ValidationReaction, self.ApiPort, self.ApiTimeout,
                          self.StorageDepth)
        control_width = max(control.sizeHint().width() for control in right_controls)
        for control in right_controls:
            control.setFixedWidth(control_width)
        bar = self.MainTabs.tabBar()
        content_width = max(self.MainTabs.widget(i).minimumSizeHint().width()
                            for i in range(self.MainTabs.count()))
        self.setFixedWidth(max(bar.sizeHint().width(), content_width) + 22)
        bar.setExpanding(True)
        self.setFixedHeight(600)

    @set_window_icon
    @has_close_button_only
    def setup(self) -> None:
        self.setAcceptDrops(True)
        for group in self.findChildren(QGroupBox):
            if group.layout() is not None:
                margins = group.layout().contentsMargins()
                group.layout().setContentsMargins(0, margins.top(), 0, margins.bottom())
        self.setProperty('lightButtons', self.palette().window().color().lightness() > 200)
        self.setStyleSheet('''
            QDialog#SettingsWindow QGroupBox {
                border: 1px solid palette(mid); border-radius: 3px;
                padding-left: 8px; padding-right: 8px; padding-bottom: 4px; margin-top: 1em;
            }
            QDialog#SettingsWindow QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 4px;
            }
            QDialog#SettingsWindow QPushButton, QDialog#SettingsWindow QToolButton {
                background: palette(button); color: palette(button-text);
                border: none; border-radius: 3px; padding: 4px 8px;
            }
            QDialog#SettingsWindow QPushButton:hover, QDialog#SettingsWindow QToolButton:hover {
                background: palette(midlight);
            }
            QDialog#SettingsWindow QPushButton:pressed, QDialog#SettingsWindow QToolButton:pressed {
                background: palette(mid);
            }
            QDialog#SettingsWindow[lightButtons="true"] QPushButton,
            QDialog#SettingsWindow[lightButtons="true"] QToolButton {
                border: 1px solid #929BA5;
            }
            QDialog#SettingsWindow[lightButtons="true"] QPushButton:hover,
            QDialog#SettingsWindow[lightButtons="true"] QToolButton:hover {
                border-color: #0078D7;
            }
            QDialog#SettingsWindow QTabWidget::pane { border: none; }
            QDialog#SettingsWindow QTabBar::tab {
                background: palette(window); color: palette(window-text); border: none;
            }
            QDialog#SettingsWindow QTabBar::tab:selected { background: palette(button); }
            QDialog#SettingsWindow QLineEdit, QDialog#SettingsWindow QComboBox {
                border: none; border-radius: 3px; padding: 3px;
            }
            QDialog#SettingsWindow QHeaderView::section { border: none; padding: 4px; }
            QDialog#SettingsWindow QComboBox { padding-right: 22px; }
        ''')
        self.MainTabs.tabBar().setDocumentMode(True)
        self.MainTabs.tabBar().setExpanding(False)
        self.MainTabs.tabBar().setStyleSheet('QTabBar { font-family: Calibri; font-size: 12pt; } QTabBar::tab { padding: 5px 8px; }')
        if self.palette().window().color().lightness() > 200:
            self.setStyleSheet(self.styleSheet().replace(
                'QDialog#SettingsWindow QTabBar::tab:selected { background: palette(button); }',
                'QDialog#SettingsWindow QTabBar::tab:selected { background: #DCE6F2; color: #162D46; }'))
        self.SvAddress.setValidator(QRegularExpressionValidator(QRegularExpression(r"(\d+\.){1,3}\d+")))
        self.MaxAmount.setEditable(True)
        self.RemoteSpecUrl.editingFinished.connect(lambda: self.RemoteSpecUrl.setCursorPosition(int()))
        self.MaxAmount.setValidator(QIntValidator(1, 2_100_000_000, self.MaxAmount))
        self.DebugLevel.addItems(LogDefinition.LOG_LEVEL)
        self.ApiInfoLabel.setText(TextConstants.API_EXPLANATION_URL)

        for button_box in self.GeneralButtonBox, self.FieldsButtonBox, self.ApiButtonBox, self.SpecificationButtonBox, self.ThemeButtonBox:
            button_box.accepted.connect(self.ok)
            button_box.rejected.connect(self.cancel)
            button_box.clicked.connect(self.process_default_button)
            footer = QWidget(button_box.parentWidget())
            row = QHBoxLayout(footer)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            actions = [('OK', self.ok), ('Cancel', self.cancel)]
            if button_box is self.GeneralButtonBox:
                actions.append(('Reset all settings', self.set_default_settings))
            else:
                button_box.setStandardButtons(button_box.standardButtons()
                                              & ~QDialogButtonBox.StandardButton.RestoreDefaults)
            for label, callback in actions:
                button = QPushButton(label, footer)
                button.setAutoDefault(False)
                if callback == self.set_default_settings:
                    self.ResetAllSettingsButton = button
                    button.setToolTip('Reset settings across all tabs to their defaults')
                button.clicked.connect(lambda checked=False, action=callback: action())
                row.addWidget(button)
            if button_box is self.ThemeButtonBox:
                row.addWidget(self.DefaultThemeButton)
                row.addWidget(self.ApplyThemeButton)
            row.addStretch()
            button_box.parentWidget().layout().replaceWidget(button_box, footer)
            button_box.hide()

        self.HeaderLength.textChanged.connect(self.validate_header_length)
        self.KeepAliveMode.stateChanged.connect(lambda state: self.KeepAliveInterval.setEnabled(bool(state)))
        self.HeaderLengthMode.stateChanged.connect(lambda state: self.HeaderLength.setEnabled(bool(state)))
        self.MaxAmountBox.stateChanged.connect(lambda state: self.MaxAmount.setEnabled(bool(state)))
        self.LoadSpecGeneral.stateChanged.connect(lambda: self.LoadSpec.setChecked(self.LoadSpecGeneral.isChecked()))
        self.LoadSpec.stateChanged.connect(lambda: self.LoadSpecGeneral.setChecked(self.LoadSpec.isChecked()))
        self.ApiRun.stateChanged.connect(lambda: self.ApiRunGeneral.setCheckState(self.ApiRun.checkState()))
        self.ApiRunGeneral.stateChanged.connect(lambda: self.ApiRun.setCheckState(self.ApiRunGeneral.checkState()))

        self.LogBackupStorageExists.stateChanged.connect(
            lambda: self.LogStorageDepth.setEnabled(self.LogBackupStorageExists.isChecked())
        )

        self.SpecBackupStorageExists.stateChanged.connect(
            lambda: self.StorageDepth.setEnabled(self.SpecBackupStorageExists.isChecked())
        )

        self.ValidationEnabled.stateChanged.connect(self.process_validation_change)
        self.ApiInfoLabel.linkActivated.connect(self.open_api_spec)
        self.CopySpecUrl.clicked.connect(self.copy_remote_spec_url)
        self.process_validation_change()
        self.process_config(self.config)
        self.MainTabs.setCurrentIndex(0)
        self.ManualInputMode.setChecked(False)
        self.ManualInputMode.hide()

        QShortcut(QKeySequence(KeySequences.CTRL_PAGE_DOWN), self).activated.connect(
            lambda: self.MainTabs.setCurrentIndex(self.MainTabs.currentIndex() + 1)
        )

        QShortcut(QKeySequence(KeySequences.CTRL_PAGE_UP), self).activated.connect(
            lambda: self.MainTabs.setCurrentIndex(self.MainTabs.currentIndex() - 1)
        )

    def process_config(self, config: Config) -> None:
        checkboxes_state_map = {
            self.MaxAmountBox: config.fields.max_amount_limited,
            self.ProcessDefaultDump: config.terminal.process_default_dump,
            self.ConnectOnStartup: config.terminal.connect_on_startup,
            self.ClearLog: config.debug.clear_log,
            self.BuildFld90: config.fields.build_fld_90,
            self.SendInternalId: config.fields.send_internal_id,
            self.ValidateWindow: config.validation.validate_window,
            self.JsonMode: config.fields.json_mode,
            self.KeepAliveMode: config.host.keep_alive_mode,
            self.HeaderLengthMode: config.host.header_length_exists,
            self.HideSecrets: config.fields.hide_secrets,
            self.AutoSortFields: config.fields.auto_sort,
            self.RewriteLocalSpec: config.specification.rewrite_local_spec,
            self.LoadSpecGeneral: config.terminal.load_remote_spec,
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
            self.PrintSubfields: config.debug.parse_subfields,
            self.PrintDescription: config.debug.print_description,
            self.BackupLocalSpecStartup: config.specification.backup_on_startup,
            self.BackupLocalSpecShutdown: config.specification.backup_on_shutdown,
            self.LogBackupStorageExists: config.debug.backup_storage_depth_exists,
            self.SpecBackupStorageExists: config.specification.backup_storage,
        }

        scales_value_map = {
            self.SvPort: config.host.port,
            self.KeepAliveInterval: config.host.keep_alive_interval,
            self.HeaderLength: config.host.header_length,
            self.StorageDepth: config.specification.backup_storage_depth,
            self.LogStorageDepth: config.debug.backup_storage_depth,
            self.ApiPort: self.config.api.port,
            self.ApiTimeout: self.config.api.waiting_timeout_seconds,
        }

        for checkbox, state in checkboxes_state_map.items():
            checkbox.setChecked(state)

        enabled_dependence = {
            self.HeaderLength: lambda: config.host.header_length_exists,
            self.KeepAliveInterval: self.KeepAliveMode.isChecked,
            self.MaxAmount: self.MaxAmountBox.isChecked,
            self.StorageDepth: self.SpecBackupStorageExists.isChecked,
            self.LogStorageDepth: self.LogBackupStorageExists.isChecked,
        }

        for item, enabled in enabled_dependence.items():
            item.setEnabled(enabled())

        for scale, value in scales_value_map.items():
            scale.setValue(int(value))

        self.DebugLevel.setCurrentText(config.debug.level)
        self.SvAddress.setText(config.host.host)
        self.RemoteSpecUrl.setText(config.specification.remote_spec_url)
        self.RemoteSpecUrl.setCursorPosition(int())
        self.ValidationReaction.setCurrentIndex(self.ValidationReaction.findText(config.validation.validation_mode))

        if not config.fields.max_amount_limited:
            return

        max_amount: str = str(config.fields.max_amount)

        if (index := self.MaxAmount.findText(max_amount)) < int():  # If the max_amount from config is not found
            index: int = int()
            self.MaxAmount.insertItem(index, max_amount)

        self.MaxAmount.setCurrentIndex(index)

    def dragEnterEvent(self, event):
        if not (event.mimeData().hasUrls() or event.mimeData().hasText()):
            event.ignore()
            return

        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if not (event.mimeData().hasUrls() or event.mimeData().hasText()):
            event.ignore()
            return

        event.acceptProposedAction()

    @trace_operation
    def dropEvent(self, event):
        if not event.mimeData().hasUrls() and event.mimeData().hasText():
            try:
                from json import loads
                data = loads(event.mimeData().text().lstrip('\ufeff'))
                if not isinstance(data, dict) or not data:
                    raise ValueError('Configuration must be a non-empty JSON object')
                self.process_config(Config(**data))
            except Exception as error:
                report_error(error, gui=True, parent=self, configuration=True, source_file='dropped text')
            event.acceptProposedAction()
            return
        if not event.mimeData().urls():
            event.ignore()
            return

        for url in event.mimeData().urls():

            if not (config_file := url.toLocalFile()):
                continue

            logger.debug(f"Config file dropped {config_file}")

            try:
                config: Config = Config(config_file)
            except Exception as config_parsing_error:
                report_error(config_parsing_error, gui=True, parent=self, configuration=True, source_file=config_file)
                continue

            try:
                self.process_config(config)

            except Exception as config_processing_error:
                report_error(config_processing_error, gui=True, parent=self, configuration=True, source_file=config_file)
                continue

            logger.info(f"Config file parsed: {config_file}")

        event.acceptProposedAction()

    def copy_remote_spec_url(self):
        copy_text(self.RemoteSpecUrl.text())

    @trace_operation
    def process_default_button(self, button):
        for button_box in self.GeneralButtonBox, self.FieldsButtonBox, self.ApiButtonBox, self.SpecificationButtonBox, self.ThemeButtonBox:
            if button_box.buttonRole(button) == QDialogButtonBox.ButtonRole.ResetRole:
                self.set_default_settings()
                break

    def process_validation_change(self) -> None:
        validation_elements = (
            self.ValidateWindow,
            self.ValidateIncoming,
            self.ValidateOutgoing,
            self.ValidationModeLabel,
            self.ValidationReaction,
        )

        for element in validation_elements:
            element.setEnabled(self.ValidationEnabled.isChecked())

    def set_default_settings(self) -> None:
        try:
            default_config: Config = Config(TermFilesPath.DEFAULT_CONFIG)
        except Exception as parsing_error:
            report_error(parsing_error, gui=True, parent=self,
                         configuration=True, source_file=TermFilesPath.DEFAULT_CONFIG,
                         action="Cannot restore default settings")
            return

        default_config.host.host = self.config.host.host
        default_config.host.port = self.config.host.port
        default_config.specification.remote_spec_url = self.config.specification.remote_spec_url
        default_config.specification.rewrite_local_spec = self.config.specification.rewrite_local_spec
        default_config.api.address = self.config.api.address
        default_config.api.port = self.config.api.port

        self.process_config(default_config)
        self.Appearance.set_colors(default_config.theme.colors())

    def validate_header_length(self) -> None:
        header_length: int = int(self.HeaderLength.value())

        if self.HeaderLengthMode.isChecked() and self.HeaderLength.value() < 2:
            self.HeaderLength.setValue(2)

        if header_length % 2 != int():
            self.HeaderLength.setValue(header_length - 1)

    @gui_action
    @trace_operation
    def ok(self) -> None:
        config_changed = any(self._control_value(widget) != initial
                             for widget, initial in self._initial_control_values)
        if not config_changed and self.Appearance.colors == self.Appearance.initial_colors:
            self.accept()
            return
        self.hide()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        initial_colors = dict(self.Appearance.initial_colors)
        try:
            self.Appearance.apply()
            if config_changed:
                self._save_settings()
            else:
                candidate = self.config.model_copy(deep=True)
                self._set_theme(candidate)
                self.commit(candidate)
                self.config = candidate
                self.accept()
        except Exception:
            self.Appearance.initial_colors = initial_colors
            if self.Appearance.change_colors is not None:
                self.Appearance.change_colors(initial_colors)
            elif self.Appearance.change_color is not None:
                for key, color in initial_colors.items():
                    self.Appearance.change_color(key, color)
            self.show()
            self.raise_()
            raise

    @staticmethod
    def _control_value(widget):
        if isinstance(widget, QCheckBox):
            return widget.checkState().value
        if isinstance(widget, QComboBox):
            return widget.currentIndex(), widget.currentText()
        return widget.text()

    def set_default_theme(self):
        self.Appearance.set_colors({'Tree': '#F0F0F0', 'Window': '#F0F0F0', 'Console': '#012E4F'})
        self.apply_theme()

    @gui_action
    def apply_theme(self):
        if self.Appearance.colors == self.Appearance.initial_colors:
            return
        candidate = self.config.model_copy(deep=True)
        self._set_theme(candidate)
        self.commit_theme(candidate)
        self.config = candidate
        self.Appearance.apply()
        self.Appearance.initial_colors = dict(self.Appearance.colors)
        self.setPalette(QApplication.instance().palette())
        self.setProperty('lightButtons', candidate.theme.windowColor in ('#F0F0F0', '#FFFBEB', '#EFF1F5'))
        selected = ('background: #DCE6F2; color: #162D46;' if candidate.theme.windowColor.upper() in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5')
                    else 'background: palette(button);')
        import re
        self.setStyleSheet(re.sub(r'QDialog#SettingsWindow QTabBar::tab:selected \{[^}]*\}',
                                 'QDialog#SettingsWindow QTabBar::tab:selected { ' + selected + ' }',
                                 self.styleSheet()))

    def _set_theme(self, config):
        from common.core.data_models.Config import Theme
        config.theme = Theme(treeColor=self.Appearance.colors['Tree'],
                             windowColor=self.Appearance.colors['Window'],
                             consoleColor=self.Appearance.colors['Console'])

    def _save_settings(self) -> None:
        config = self.config.model_copy(deep=True)
        self._set_theme(config)

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
        config.debug.backup_storage_depth = self.LogStorageDepth.value()
        config.debug.clear_log = self.ClearLog.isChecked()
        config.debug.level = self.DebugLevel.currentText()
        config.fields.max_amount_limited = self.MaxAmountBox.isChecked()
        config.fields.max_amount = int(self.MaxAmount.currentText())
        config.fields.build_fld_90 = self.BuildFld90.isChecked()
        config.fields.send_internal_id = self.SendInternalId.isChecked()
        config.fields.json_mode = self.JsonMode.isChecked()
        config.fields.hide_secrets = self.HideSecrets.isChecked()
        config.fields.auto_sort = self.AutoSortFields.isChecked()
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
        config.api.waiting_timeout_seconds = self.ApiTimeout.value()
        config.terminal.run_api = self.ApiRun.isChecked()
        config.api.parse_subfields = self.ParseComplexFields.isChecked()
        config.debug.parse_subfields = self.PrintSubfields.isChecked()
        config.debug.print_description = self.PrintDescription.isChecked()
        config.specification.backup_on_shutdown = self.BackupLocalSpecShutdown.isChecked()
        config.specification.backup_on_startup = self.BackupLocalSpecStartup.isChecked()
        config.debug.backup_storage_depth_exists = self.LogBackupStorageExists.isChecked()
        config.specification.backup_storage = self.SpecBackupStorageExists.isChecked()
        config.specification.rewrite_local_spec = all(
            [
                self.RewriteLocalSpec.isChecked(),
                self.RewriteLocalSpec.isEnabled(),
            ]
        )

        if not config.fields.max_amount_limited:
            config.fields.max_amount = 9_999_999_999

        self.commit(config)
        self.config = config

        self.accept()

    @trace_operation
    def cancel(self) -> None:
        logger.info("Settings changes canceled")
        self.reject()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.ok()
        else:
            super().keyPressEvent(event)
