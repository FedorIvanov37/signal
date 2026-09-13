import pytest

@pytest.mark.parametrize('accepted,configured,stored,show', [
    (True, True, False, True),
    (True, False, True, False),
    (False, False, False, True),
    (True, True, True, True),
])
def test_license_display_uses_config(runtime, config, monkeypatch, accepted, configured, stored, show):
    import common.gui.windows.license_window as module
    from common.core.data_models.License import LicenseInfo
    from common.core.exceptions.exceptions import LicenceAlreadyAccepted
    info = LicenseInfo()
    info.accepted = accepted
    info.show_agreement = stored
    monkeypatch.setattr(module, 'LicenseInfo', lambda *args: info)
    config.terminal.show_license_dialog = configured
    if not show:
        with pytest.raises(LicenceAlreadyAccepted):
            module.LicenseWindow(config)
        return
    window = module.LicenseWindow(config)
    assert window.CheckBoxAgreement.isChecked() == accepted
    assert window.CheckBoxDontShowAgain.isChecked() == (accepted and not configured)
    window.deleteLater()

@pytest.mark.parametrize('dont_show', [True, False])
def test_license_choice_survives_reload(runtime, config, monkeypatch, tmp_path, dont_show):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PyQt6.QtCore import QTimer
    import common.gui.tools.SignalGui as module
    from common.gui.windows.license_window import LicenseWindow
    from common.core.tools.ConfigManager import ConfigManager
    from common.core.data_models.Config import Config
    config.terminal.show_license_dialog = True
    filename = tmp_path / 'config.json'
    manager = ConfigManager(config, filename)
    def dialog(*args, **kwargs):
        window = LicenseWindow(*args, **kwargs)
        monkeypatch.setattr(window, 'save_license_file', lambda data: None)
        window.CheckBoxAgreement.setChecked(True)
        window.CheckBoxDontShowAgain.setChecked(dont_show)
        QTimer.singleShot(0, window.accept)
        return window
    monkeypatch.setattr(module, 'LicenseWindow', dialog)
    host = SimpleNamespace(config=manager.view, update_config=manager.replace, window=SimpleNamespace(set_focus=Mock()))
    assert module.SignalGui.show_license_dialog(host)
    assert Config(str(filename)).terminal.show_license_dialog == (not dont_show)
