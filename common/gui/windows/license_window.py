from common.core.tools.DebugTrace import trace_operation
from json.decoder import JSONDecodeError
from loguru import logger
from pydantic import ValidationError
from datetime import datetime, UTC
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame
from PyQt6.QtGui import QPixmap, QPalette
from common.gui.forms.license_window import Ui_LicenseWindow
from common.gui.decorators.window_settings import set_window_icon, frameless_window, themed_logo
from common.core.data_models.License import LicenseInfo
from common.core.exceptions.exceptions import LicenseDataLoadingError, LicenceAlreadyAccepted
from common.core.enums.TermFilesPath import TermFilesPath
from common.gui.enums.GuiFilesPath import GuiFilesPath
from common.core.enums.TextConstants import TextConstants
from common.core.data_models.Config import Config


class LicenseWindow(Ui_LicenseWindow, QDialog):
    _license_info: LicenseInfo

    @property
    def license_info(self):
        return self._license_info

    def __init__(self, config: Config, force: bool = False):
        super().__init__()
        self.config = config.model_copy(deep=True)
        self.force = force
        self.rejected_by_user = False
        self.setupUi(self)
        self.frame.setStyleSheet("")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setPalette(QPalette())
        self.InfoBoard.setPalette(QPalette())
        self._setup()

    @set_window_icon
    @frameless_window
    def _setup(self):
        self.LogoLabel.setPixmap(themed_logo(GuiFilesPath.SIGNED_LOGO))
        from common.gui.decorators.window_settings import enable_logo_click
        enable_logo_click(self.LogoLabel)
        self.InfoBoard.setText(TextConstants.LICENSE_AGREEMENT)
        self.CheckBoxAgreement.setFocus()

        try:
            self._license_info: LicenseInfo = LicenseInfo(TermFilesPath.LICENSE_INFO)

        except (ValueError, ValidationError, JSONDecodeError, FileNotFoundError):
            self._license_info: LicenseInfo = LicenseInfo()

        except Exception as license_parsing_error:
            raise LicenseDataLoadingError(f"GNU license info file parsing error: {license_parsing_error}")

        if self.force:

            widgets = (
                self.CheckBoxAgreement,
                self.CheckBoxDontShowAgain,
                self.ButtonAccept,
                self.ButtonReject,
                self.line_2
            )

            for widget in widgets:
                widget.setHidden(True)

            return
        
        if self._license_info.accepted and not self.config.terminal.show_license_dialog:
            raise LicenceAlreadyAccepted

        self.CheckBoxDontShowAgain.setChecked(not self.config.terminal.show_license_dialog)
        self.CheckBoxAgreement.setChecked(self._license_info.accepted)
        self.CheckBoxAgreement.stateChanged.connect(self.block_acceptance)
        self.rejected.connect(self.reject_license)
        self.accepted.connect(self.accept_license)
        self.block_acceptance()

    @trace_operation
    def accept_license(self):
        self._license_info.accepted = bool(self.CheckBoxAgreement.checkState().value)

        if not self._license_info.accepted:
            return

        self._license_info.last_acceptance_date = datetime.now(UTC)
        self._license_info.show_agreement = not bool(self.CheckBoxDontShowAgain.checkState().value)

        license_data: LicenseInfo = self._license_info.model_copy(deep=True)
        license_data.last_acceptance_date = license_data.last_acceptance_date.isoformat()

        self.config.terminal.show_license_dialog = license_data.show_agreement

        self.save_license_file(license_data)
        self.print_acceptance_info()
        self.close()

    @trace_operation
    def reject_license(self):
        if self.force:
            return

        license_data: LicenseInfo = self._license_info.model_copy(deep=True)
        license_data.accepted = False
        license_data.show_agreement = True
        license_data.last_acceptance_date = None

        self.config.terminal.show_license_dialog = license_data.show_agreement

        self.save_license_file(license_data)
        logger.warning("License agreement rejected. Exiting")
        self.rejected_by_user = True
        self.done(100)

    @staticmethod
    @trace_operation
    def save_license_file(license_data: LicenseInfo):
        with open(TermFilesPath.LICENSE_INFO, 'w') as license_file:
            license_file.write(license_data.model_dump_json(indent=4))

    def block_acceptance(self):
        accepted = bool(self.CheckBoxAgreement.checkState().value)

        if not accepted:
            self.CheckBoxDontShowAgain.setCheckState(Qt.CheckState.Unchecked)

        self.CheckBoxDontShowAgain.setEnabled(accepted)
        self.ButtonAccept.setEnabled(accepted)

    def print_acceptance_info(self):
        date_format = "%d/%m/%Y %T UTC"

        logger.info(f"License ID {self._license_info.license_id} | Accepted {
            datetime.strftime(self._license_info.last_acceptance_date, date_format)}")
