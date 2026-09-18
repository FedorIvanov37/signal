def test_apply_theme_keeps_other_settings_pending(runtime, config):
    from common.gui.windows.settings_window import SettingsWindow
    saved = []
    applied = []
    window = SettingsWindow(config, commit=lambda candidate: saved.append(candidate.model_copy(deep=True)),
                            change_colors=applied.append)
    window.show()
    original_port = config.host.port
    window.SvPort.setValue(original_port + 1)
    window.Appearance.set_colors(dict.fromkeys(('Tree', 'Window', 'Console'), '#000000'))
    window.ApplyThemeButton.click()
    assert window.isVisible()
    assert saved[-1].host.port == original_port
    assert saved[-1].theme.windowColor == '#000000'
    assert applied[-1] == dict.fromkeys(('Tree', 'Window', 'Console'), '#000000')
    assert window.SvPort.value() == original_port + 1
    window.ok()
    assert saved[-1].host.port == original_port + 1
    assert saved[-1].theme.windowColor == '#000000'
    window.deleteLater()
