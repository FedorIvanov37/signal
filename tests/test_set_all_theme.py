def test_set_all_with_batch_theme_callback(runtime, config):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.windows.settings_window import SettingsWindow

    window = SettingsWindow(config, commit=lambda config: None, change_colors=lambda colors: None)
    try:
        window.MainTabs.setCurrentWidget(window.Appearance)
        window.show()
        runtime.app.processEvents()
        tab = window.Appearance
        button = next(b for b in tab.color_buttons if b.accessibleName() == 'Set all: Slate blue')
        assert button.isEnabled() and button.isVisible()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert tab.colors == dict.fromkeys(('Tree', 'Window', 'Console'), '#243447')
        assert not button.isCheckable()
        assert all(group.checkedButton().property('themeColor') == '#243447'
                   for group in tab.selectors.values())
        black = next(b for b in tab.selectors['Console'].buttons() if b.property('themeColor') == '#000000')
        QTest.mouseClick(black, Qt.MouseButton.LeftButton)
        assert tab.colors == {'Tree': '#243447', 'Window': '#243447', 'Console': '#000000'}
    finally:
        window.hide()
        window.deleteLater()
