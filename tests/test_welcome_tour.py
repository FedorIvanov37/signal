"""Tour navigation, persistence, startup ordering and temporary demo state."""
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QTextBrowser, QPushButton, QDialog
from PyQt6.QtTest import QTest

from common.gui.windows.welcome_tour import WelcomeTour, WelcomeDialog, offer_welcome_tour
from common.core.enums.ReleaseDefinition import ReleaseDefinition






@pytest.fixture
def tour_window(runtime):
    class Window(QWidget):
        def __init__(self):
            super().__init__()
            self.resize(1000, 700)
            self.LogArea = QTextBrowser(self)
            self.LogArea.setGeometry(10, 350, 980, 300)
            self.LogArea.setPlainText('Real session log must survive')
            self.ButtonSettings = QPushButton('Settings', self)
            self.ButtonSettings.setGeometry(900, 660, 90, 30)
            self.applied = []

        def apply_theme_colors(self, colors):
            self.applied.append(dict(colors))
            for key, color in colors.items():
                runtime.app.setProperty(f'signal{key}Color', color)

    saved = {k: runtime.app.property(f'signal{k}Color') for k in ('Window', 'Tree', 'Console')}
    window = Window()
    window.apply_theme_colors({'Window': '#F0F0F0', 'Tree': '#243447', 'Console': '#012E4F'})
    window.show()
    yield window
    window.close()
    window.deleteLater()
    for key, color in saved.items():
        runtime.app.setProperty(f'signal{key}Color', color)


def test_navigation_restores_mixed_theme_and_never_changes_real_log(tour_window):
    tour = WelcomeTour(tour_window)
    original = dict(tour.original)
    assert not tour.back.isEnabled()
    assert tour.shade.target is tour_window.LogArea
    assert 'demonstration' in tour.description.text()
    tour.advance()
    assert tour.timer.isActive()
    assert set(tour_window.applied[-1].values()) == {'#102D28'}
    tour.cycle_theme()
    tour.cycle_theme()
    assert set(tour_window.applied[-1].values()) == {'#012E4F'}
    assert tour.timer.isActive()
    for _ in range(len(tour.COLORS)):
        tour.cycle_theme()
    assert not tour.timer.isActive()
    assert tour_window.applied[-3:] == [{'Console': '#3B202B'}, {'Tree': '#102D28'}, {'Window': '#292D32'}]
    tour.show_step(3)
    assert tour_window.applied[-1] == original
    assert tour.shade.target is tour_window.ButtonSettings
    tour.show_step(1)
    assert tour.timer.isActive()
    tour.reject()
    assert tour_window.applied[-1] == original
    assert not tour.timer.isActive()
    assert not tour.shade.isVisible()
    tour.cycle_theme()
    assert tour_window.applied[-1] == original
    assert tour_window.LogArea.toPlainText() == 'Real session log must survive'
    tour.deleteLater()


@pytest.mark.parametrize('exit_kind', ['escape', 'close', 'finish'])
def test_all_exit_paths_restore_theme(tour_window, exit_kind):
    tour = WelcomeTour(tour_window)
    tour.show()
    tour.show_step(1)
    if exit_kind == 'escape':
        QTest.keyClick(tour, Qt.Key.Key_Escape)
    elif exit_kind == 'close':
        tour.close()
    else:
        tour.show_step(len(tour.STEPS)-1)
        tour.advance()
        assert tour.result() == QDialog.DialogCode.Accepted
    assert tour_window.applied[-1] == tour.original
    assert not tour.timer.isActive()
    assert not tour.shade.isVisible()
    tour.deleteLater()






def test_license_rejection_never_opens_tour(runtime, monkeypatch):
    from common.gui.tools.SignalGui import SignalGui
    import common.gui.windows.welcome_tour as module
    offered = []
    monkeypatch.setattr(module, 'offer_welcome_tour', lambda window: offered.append(window))
    exits = []
    gui = SimpleNamespace(show_license_dialog=lambda: False,
                          pyqt_application=SimpleNamespace(exit=exits.append))
    SignalGui.on_startup(gui)
    assert exits == [0]
    assert offered == []

@pytest.mark.parametrize("managed", [False, True])
def test_real_main_window_theme_preview_does_not_persist(runtime, config, tmp_path, monkeypatch, managed):
    import common.gui.windows.main_window as module
    monkeypatch.setattr(module, 'APPEARANCE_SETTINGS_PATH', tmp_path / 'panel.json')
    from common.core.tools.ConfigManager import ConfigManager
    active = ConfigManager(config, tmp_path / 'chosen-config.json').view if managed else config
    window = module.MainWindow(active)
    help_items = [a.text() for a in window.ButtonHelp.menu().actions() if not a.isSeparator()]
    assert help_items[-2:] == [f'Quick tour {ReleaseDefinition.VERSION}', 'About Signal']
    before = config.model_dump()
    theme = {k: runtime.app.property(f'signal{k}Color') for k in ('Window', 'Tree', 'Console')}
    window.show()
    panel_before = (tmp_path / 'panel.json').read_bytes()
    tour = WelcomeTour(window)
    tour.show()
    try:
        tour.show_step(1)
        tour.cycle_theme()
        tour.cycle_theme()
        tour.show_step(3)
        assert {k: runtime.app.property(f'signal{k}Color') for k in theme} == theme
        assert config.model_dump() == before
        tour.show_step(2)
        settings = tour.settings_preview
        assert settings.MainTabs.currentWidget() is settings.Appearance
        for button in settings.findChildren(QPushButton):
            if button.text().replace('&', '') in ('OK', 'Cancel'):
                assert not button.isVisible()
                assert not button.isEnabled()
        original_preview = dict(settings.Appearance.colors)
        tour.animate_settings_preview()
        tour.animate_settings_preview()
        assert settings.Appearance.colors != original_preview
        assert not tour.preview_timer.isActive()
        assert config.model_dump() == before
        tour.show_step(4)
        assert tour.shade.target is window.json_view.sort_fields_button
        assert not settings.isVisible()
        tour.show_step(5)
        assert settings.MainTabs.tabText(settings.MainTabs.currentIndex()) == 'Fields'
        assert settings.AutoSortFields.isVisible()
        settings.AutoSortFields.toggle()
        assert config.model_dump() == before
        tour.show_step(3)
        sizes = window.main_splitter.sizes()
        tour.show_step(tour.RESIZE_STEP)
        tour.resize_control.setValue(70)
        assert window.main_splitter.sizes() != sizes
        QTest.mouseDClick(tour.resize_control, Qt.MouseButton.LeftButton)
        assert window.main_splitter.sizes() == sizes
        tour.resize_control.setValue(65)
        tour.show_step(tour.API_STEP)
        assert window.main_splitter.sizes() == sizes
        assert tour.shade.target is window.ButtonTools
        assert tour.tools_preview.isVisible()
        assert tour.api_preview.isVisible()
        assert [a.text() for a in tour.api_preview.actions() if not a.isSeparator()] == [
            a.text() for a in window.ButtonTools.menu().actions()[0].menu().actions()]
        tour.show_step(len(tour.STEPS)-1)
        runtime.app.processEvents()
        assert runtime.app.activePopupWidget() is None
        assert QWidget.mouseGrabber() is None
        assert 'Specification recovery from backups' in tour.release_notes.toPlainText()
        assert 'TCP message handling and response matching' in tour.release_notes.toPlainText()
        assert (tmp_path / 'panel.json').read_bytes() == panel_before
    finally:
        tour.reject()
        tour.deleteLater()
        window.close()
        window.deleteLater()





def test_demo_tracks_nested_console_after_layout_moves(tour_window, runtime):
    from PyQt6.QtCore import QPoint
    pane = QWidget(tour_window)
    pane.setGeometry(25, 300, 920, 330)
    tour_window.LogArea.setParent(pane)
    tour_window.LogArea.setGeometry(8, 30, 900, 280)
    pane.show()
    tour_window.LogArea.show()
    tour_window.move(170, 120)
    tour = WelcomeTour(tour_window)
    tour.show()
    try:
        runtime.app.processEvents()
        assert tour.demo.mapToGlobal(QPoint()) == tour_window.LogArea.mapToGlobal(QPoint())
        pane.move(40, 340)
        tour_window.LogArea.resize(870, 230)
        runtime.app.processEvents()
        runtime.app.processEvents()
        assert tour.demo.mapToGlobal(QPoint()) == tour_window.LogArea.mapToGlobal(QPoint())
        assert tour.demo.size() == tour_window.LogArea.size()
        assert tour.demo.font().pointSize() == 14
        assert tour.description.font().pointSize() == 13
    finally:
        tour.reject()
        tour.deleteLater()




@pytest.mark.parametrize("managed", [False, True])
def test_explicit_settings_choices_persist_and_survive_tour_exit(runtime, config, tmp_path, monkeypatch, managed):
    import common.gui.windows.main_window as module
    from common.core.data_models.Config import Config
    monkeypatch.setattr(module, 'APPEARANCE_SETTINGS_PATH', tmp_path / 'panel.json')
    config._source_file = str(tmp_path / 'chosen-config.json')
    from common.core.tools.ConfigManager import ConfigManager
    active = ConfigManager(config, tmp_path / 'chosen-config.json').view if managed else config
    window = module.MainWindow(active)
    window.show()
    tour = WelcomeTour(window)
    tour.show()
    try:
        initial_console = config.theme.consoleColor
        tour.show_step(2)
        tour.animate_settings_preview()
        tour.animate_settings_preview()
        assert not (tmp_path / 'chosen-config.json').exists()
        buttons = tour.settings_preview.Appearance.selectors['Tree'].buttons()
        green = next(button for button in buttons if button.property('themeColor') == '#102D28')
        green.click()
        saved = Config(str(tmp_path / 'chosen-config.json'))
        assert saved.theme.treeColor == '#102D28'
        assert saved.theme.consoleColor == initial_console  # Don't persist demo colours.
        tour.show_step(5)
        check = tour.settings_preview.AutoSortFields
        enabled = not check.isChecked()
        check.click()
        assert Config(str(tmp_path / 'chosen-config.json')).fields.auto_sort == enabled
        assert window.json_view._auto_sort_enabled == enabled
        tour.show_step(1)
        tour.cycle_theme()
        tour.reject()
        assert runtime.app.property('signalTreeColor') == '#102D28'
        assert runtime.app.property('signalConsoleColor') == initial_console
        assert window.config.fields.auto_sort == enabled
    finally:
        tour.reject()
        tour.deleteLater()
        window.close()
        window.deleteLater()


def test_demo_log_columns_are_aligned(tour_window):
    tour = WelcomeTour(tour_window)
    try:
        lines = [line for line in tour.demo.toPlainText().splitlines() if line.startswith('12:00:')]
        assert len(lines) == 6
        separators = [[i for i, char in enumerate(line) if char == '|'] for line in lines]
        assert all(positions == separators[0] for positions in separators)
    finally:
        tour.reject()
        tour.deleteLater()

def test_regular_steps_keep_width_top_and_heading_position(tour_window, runtime):
    from PyQt6.QtCore import QPoint
    tour = WelcomeTour(tour_window)
    tour.show()
    try:
        positions = []
        for step in (0, 1, 3, 4, tour.RESIZE_STEP, tour.API_STEP, 8, len(tour.STEPS)-1):
            tour.show_step(step)
            runtime.app.processEvents()
            positions.append((tour.width(), tour.pos(), tour.title.mapToGlobal(QPoint())))
        assert all(position == positions[0] for position in positions)
        assert positions[0][0] == 540
        tour.show_step(tour.API_STEP)
        assert tour.shade.callout == 'Tools → API'
        tour.show_step(4)
        assert 'JSON fields' not in tour.title.text()
        assert tour.shade.callout == 'Sort Data Fields'
    finally:
        tour.reject()
        tour.deleteLater()


def test_console_only_demo_changes_console_and_preserves_other_colours(tour_window, runtime):
    tour = WelcomeTour(tour_window)
    try:
        tour.show_step(1)
        for _ in range(len(tour.COLORS)-1):
            tour.cycle_theme()
        before = {key: runtime.app.property(f'signal{key}Color') for key in tour.original}
        tour.cycle_theme()
        after = {key: runtime.app.property(f'signal{key}Color') for key in tour.original}
        assert after['Window'] == before['Window']
        assert after['Tree'] == before['Tree']
        assert after['Console'] != before['Console']
        assert after['Console'] not in (after['Window'], after['Tree'])
    finally:
        tour.reject()
        tour.deleteLater()

@pytest.mark.parametrize('base', ['#F0F0F0', '#102D28', '#012E4F'])
def test_tour_cards_keep_starting_theme(tour_window, runtime, base):
    runtime.app.setProperty('signalWindowColor', base)
    welcome = WelcomeDialog(tour_window)
    tour = WelcomeTour(tour_window)
    try:
        assert welcome.tour_colors['base'] == base
        assert tour.tour_colors['base'] == base
        assert f'background: {base}' in welcome.styleSheet()
        original_style = tour.styleSheet()
        tour.show_step(1)
        tour.cycle_theme()
        assert tour.styleSheet() == original_style
        assert tour.tour_colors['text'] == ('#243447' if base == '#F0F0F0' else '#E2E8F0')
    finally:
        tour.reject()
        tour.deleteLater()
        welcome.deleteLater()

def test_release_info_scrolls_after_tools_step(tour_window, runtime):
    from PyQt6.QtCore import QPoint, QPointF
    from PyQt6.QtGui import QWheelEvent
    tour = WelcomeTour(tour_window)
    tour.show()
    try:
        tour.show_step(tour.API_STEP)
        tour.show_step(len(tour.STEPS)-1)
        runtime.app.processEvents()
        viewport = tour.release_notes.viewport()
        bar = tour.release_notes.verticalScrollBar()
        assert bar.maximum() > 0
        point = viewport.rect().center()
        wheel = QWheelEvent(QPointF(point), QPointF(viewport.mapToGlobal(point)), QPoint(),
                            QPoint(0, -120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        runtime.app.sendEvent(viewport, wheel)
        runtime.app.processEvents()
        assert bar.value() > 0
    finally:
        tour.reject()
        tour.deleteLater()






def test_manual_welcome_has_no_opt_out(tour_window, monkeypatch):
    from PyQt6.QtWidgets import QCheckBox
    opened = []
    def decline(dialog):
        assert not dialog.findChildren(QCheckBox)
        opened.append(True)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(WelcomeDialog, 'exec', decline)
    offer_welcome_tour(tour_window)
    offer_welcome_tour(tour_window)
    assert opened == [True, True]


def test_startup_has_no_tour_call():
    import inspect
    from common.gui.tools.SignalGui import SignalGui
    assert 'welcome_tour' not in inspect.getsource(SignalGui.on_startup)
