import asyncio
import importlib
from pathlib import Path
from threading import Thread
from unittest.mock import Mock

import httpx
import pytest


@pytest.fixture
def manager(runtime, config, tmp_path):
    from common.core.tools.ConfigManager import ConfigManager
    return ConfigManager(config, tmp_path / "config.json")


def test_retained_consumers_and_sections_see_new_version(runtime, manager):
    from common.core.tools.validators.DataValidator import DataValidator
    from common.core.tools.validators.TransValidator import TransValidator
    parser = runtime.Parser(manager.view)
    validator = DataValidator(manager.view)
    trans_validator = TransValidator(manager.view)
    retained_section = manager.view.host
    candidate, version = manager.read()
    candidate.host.port = 12345
    manager.replace(candidate)
    assert manager.view is parser.config is validator.config is validator.validator.config
    assert trans_validator.validator.config.host.port == 12345
    assert retained_section.port == 12345
    assert manager.read()[1] == version + 1


def test_snapshot_and_active_config_cannot_be_mutated_accidentally(manager):
    original = manager.view.host.port
    snapshot, _ = manager.read()
    snapshot.host.port = 12345
    assert manager.view.host.port == original
    with pytest.raises(AttributeError, match="read-only"):
        manager.view.host.port = 12345
    data = manager.view.model_dump()
    data["host"]["port"] = 23456
    assert manager.view.host.port == original


def test_failed_save_publishes_nothing(manager, monkeypatch):
    module = importlib.import_module("common.core.tools.ConfigManager")
    listener = Mock()
    manager.subscribe(listener)
    old, revision = manager.read()
    candidate = old.model_copy(deep=True)
    candidate.host.port = 12345
    monkeypatch.setattr(module, "save_config", Mock(side_effect=PermissionError("denied")))
    with pytest.raises(PermissionError):
        manager.replace(candidate)
    assert manager.read() == (old, revision)
    assert not listener.called


def test_failed_listener_rolls_back_all_views_and_notifies_recovery(manager, runtime):
    events = []
    old, revision = manager.read()
    def listener(before, after):
        events.append(after.host.port)
        if after.host.port == 12345:
            raise RuntimeError("apply failure")
    manager.subscribe(listener)
    candidate = old.model_copy(deep=True)
    candidate.host.port = 12345
    with pytest.raises(Exception, match="restored"):
        manager.replace(candidate)
    assert manager.read() == (old, revision)
    assert events == [12345, old.host.port]
    assert runtime.Config(manager.filename).model_dump() == old.model_dump()


def test_stale_editor_does_not_overwrite_api_change(manager):
    from common.core.tools.ConfigManager import ConfigConflictError
    draft, revision = manager.read()
    current = draft.model_copy(deep=True)
    current.host.port = 23456
    manager.replace(current)
    draft.host.port = 12345
    with pytest.raises(ConfigConflictError):
        manager.replace(draft, expected_revision=revision)
    assert manager.view.host.port == 23456


def test_custom_path_preserved_and_instances_are_independent(runtime, config, tmp_path):
    from common.core.tools.ConfigManager import ConfigManager
    path = tmp_path / "custom.json"
    path.write_text(config.model_dump_json())
    first = ConfigManager(runtime.Config(path))
    second = ConfigManager(config, tmp_path / "other.json")
    candidate, _ = first.read()
    candidate.host.port = 12345
    first.replace(candidate)
    assert runtime.Config(path).host.port == 12345
    assert second.view.host.port == config.host.port


def test_writer_thread_enforced_but_worker_can_read(manager):
    errors, snapshots = [], []
    def worker():
        snapshot, _ = manager.read()
        snapshots.append(snapshot)
        try:
            manager.replace(snapshot)
        except Exception as error:
            errors.append(error)
    worker_thread = Thread(target=worker)
    worker_thread.start()
    worker_thread.join(2)
    assert not worker_thread.is_alive()
    assert len(snapshots) == len(errors) == 1
    assert "application thread" in str(errors[0])


def test_queue_uses_runtime_config_without_reading_disk(runtime, manager, monkeypatch):
    from common.core.tools.TransactionQueue import TransactionQueue
    candidate, _ = manager.read()
    candidate.host.header_length = 4
    manager.replace(candidate, persist=False)
    connector = runtime.Connector(manager.view)
    queue = TransactionQueue(connector)
    messages = []
    queue.incoming_transaction.connect(messages.append)
    body = runtime.Parser.create_dump(runtime.Transaction(message_type="0810", data_fields={"70": "301"}))
    module = importlib.import_module("common.core.tools.Parser")
    monkeypatch.setattr(module, "Config", Mock(side_effect=AssertionError("Unexpected disk read")))
    queue.receive_transaction_data(len(body).to_bytes(4, "big") + body)
    assert len(messages) == 1


@pytest.fixture
def gui(runtime, config, monkeypatch, tmp_path):
    window_module = importlib.import_module("common.gui.windows.main_window")
    monkeypatch.setattr(window_module, "APPEARANCE_SETTINGS_PATH", tmp_path / "common" / "data" / "style" / "appearance.json")
    module = importlib.import_module("common.gui.tools.SignalGui")
    from common.gui.tools.ResourcePath import ResourcePath
    monkeypatch.setattr(ResourcePath, "resource_path", staticmethod(lambda path: str(tmp_path)))
    # Exercise real GUI/backend/widgets; omit the background socket thread and startup actions.
    monkeypatch.setattr(module, "ConnectionThread", runtime.Connector)
    original_setup = module.SignalGui.setup
    monkeypatch.setattr(module.SignalGui, "setup", lambda self: None)
    config._source_file = str(tmp_path / "gui-config.json")
    app = module.SignalGui(config)
    app._test_original_setup = lambda: original_setup(app)
    # Python 3.14 logging probes this optional attribute after Qt teardown.
    app.wireless_handler.flushOnClose = True
    yield app
    app.window.hide()
    app.connector.abort()
    app.keep_alive_timer._trans_loop_timer.stop()


async def request(gui, method, path, **kwargs):
    gui.api.api._loop = asyncio.get_running_loop()
    transport = httpx.ASGITransport(app=gui.api.api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://signal.test") as client:
        return await client.request(method, path, **kwargs)


def test_specification_window_renders_without_callback_errors(gui, monkeypatch):
    import sys
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.windows.spec_window import SpecWindow
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *error: errors.append(error))
    window = SpecWindow(gui.connector, gui.config)
    window.wireless_handler.flushOnClose = True
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    try:
        window.show()
        QTest.qWait(50)
        assert not window.grab().isNull()
        assert not errors, errors
    finally:
        window.hide()
        window.deleteLater()


def test_api_commands_are_first_tools_submenu(gui):
    from common.gui.enums.ApiMode import ApiModes
    window = gui.window
    assert not hasattr(window, 'ButtonApi')
    action = window.ButtonTools.menu().actions()[0]
    assert action.text() == 'API'
    assert action.icon().isNull()
    commands = action.menu().actions()
    assert [command.text() for command in commands] == ['Start', 'Stop', 'Restart']
    received = []
    window.api_mode_changed.disconnect(gui.api.process_change_api_mode)
    window.api_mode_changed.connect(received.append)
    try:
        for command in commands:
            command.trigger()
        assert received == [ApiModes.START, ApiModes.STOP, ApiModes.RESTART]
        for mode in (ApiModes.START, ApiModes.STOP, ApiModes.NOT_RUN):
            window.process_api_mode_change(mode)
            assert action.icon().isNull()
    finally:
        window.api_mode_changed.disconnect(received.append)
        window.api_mode_changed.connect(gui.api.process_change_api_mode)


def test_tools_api_submenu_requires_click(gui):
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    window = gui.window
    menu = window.ButtonTools.menu()
    window.show()
    menu.popup(window.ButtonTools.mapToGlobal(QPoint(0, -menu.sizeHint().height())))
    action = menu.actions()[0]
    try:
        point = menu.actionGeometry(action).center()
        QTest.mouseMove(menu, point)
        QTest.qWait(350)
        assert not action.menu().isVisible()
        for expected in (True, False, True, False):
            QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=point)
            assert action.menu().isVisible() == expected
    finally:
        action.menu().close()
        menu.close()
        window.hide()


def test_theme_batch_applies_global_style_once(gui, monkeypatch):
    from time import perf_counter
    app, window = gui.pyqt_application, gui.window
    original = app.setStyleSheet
    writes = []
    def record(style):
        writes.append(style)
        original(style)
    monkeypatch.setattr(app, 'setStyleSheet', record)
    started = perf_counter()
    window._set_tree_color('#102D28')
    window._apply_dark_theme('#102D28')
    window._set_console_color('#102D28')
    baseline = perf_counter() - started
    baseline_writes = len(writes)
    writes.clear()
    started = perf_counter()
    window.apply_theme_colors({'Tree': '#012E4F', 'Window': '#012E4F', 'Console': '#012E4F'})
    elapsed = perf_counter() - started
    assert len(writes) == 1
    for key in ('Tree', 'Window', 'Console'):
        assert app.property(f'signal{key}Color') == '#012E4F'
    writes.clear()
    window.apply_theme_colors({'Tree': '#012E4F', 'Window': '#012E4F', 'Console': '#012E4F'})
    assert not writes
    print(f'Theme sequential: {baseline:.3f}s/{baseline_writes} writes; batch: {elapsed:.3f}s/1 write')


def test_settings_hide_and_apply_theme_before_commit(gui):
    from common.gui.windows.settings_window import SettingsWindow
    events = []
    window = SettingsWindow(gui.config, commit=lambda config: events.append(('config', window.isVisible())),
                            change_color=lambda key, color: events.append((key, window.isVisible())))
    try:
        window.show()
        window.SvPort.setValue(window.SvPort.value() + 1)
        for key, color in window.Appearance.initial_colors.items():
            window.Appearance.choose(key, '#000000' if color != '#000000' else '#F0F0F0')
        window.ok()
        assert [name for name, visible in events] == ['Tree', 'Window', 'Console', 'config']
        assert all(not visible for name, visible in events)
    finally:
        window.hide()
        window.deleteLater()


def test_unchanged_settings_close_without_applying_or_saving(gui):
    from common.gui.windows.settings_window import SettingsWindow
    commit, theme = Mock(), Mock()
    window = SettingsWindow(gui.config, commit=commit, change_color=theme)
    try:
        window.show()
        initial = window.SvPort.value()
        window.SvPort.setValue(initial + 1)
        window.SvPort.setValue(initial)
        window.ok()
        commit.assert_not_called()
        theme.assert_not_called()
        assert not window.isVisible()
    finally:
        window.deleteLater()


def test_theme_settings_persist_and_reopen(gui):
    from common.core.data_models.Config import Config
    from common.gui.windows.settings_window import SettingsWindow
    window = SettingsWindow(gui.config, commit=gui.update_config,
                            change_colors=gui.window.apply_theme_colors)
    try:
        window.Appearance.choose('Tree', '#000000')
        window.Appearance.choose('Window', '#F0F0F0')
        window.Appearance.choose('Console', '#012E4F')
        expected = dict(window.Appearance.colors)
        window.ok()
        assert gui.config.theme.model_copy().colors() == expected
        assert Config(gui.config_manager.filename).theme.colors() == expected
        reopened = SettingsWindow(gui.config, commit=Mock(), change_colors=Mock())
        try:
            assert reopened.Appearance.colors == expected
            reopened.Appearance.choose('Tree', '#102D28')
            reopened.cancel()
            assert Config(gui.config_manager.filename).theme.colors() == expected
        finally:
            reopened.deleteLater()
    finally:
        window.deleteLater()


def test_theme_save_failure_restores_active_colors(gui, monkeypatch):
    from common.gui.windows.settings_window import SettingsWindow
    reporting = importlib.import_module('common.core.tools.ErrorReporting')
    monkeypatch.setattr(reporting, 'report_error', Mock())
    apply = Mock()
    window = SettingsWindow(gui.config, commit=Mock(side_effect=OSError('save failed')),
                            change_colors=apply)
    try:
        initial = dict(window.Appearance.initial_colors)
        chosen = '#000000' if initial['Tree'] != '#000000' else '#F0F0F0'
        window.Appearance.choose('Tree', chosen)
        window.ok()
        assert apply.call_args_list[0].args == ({'Tree': chosen},)
        assert apply.call_args_list[-1].args == (initial,)
        assert window.Appearance.initial_colors == initial
        assert window.Appearance.colors['Tree'] == chosen
        assert window.isVisible()
    finally:
        window.hide()
        window.deleteLater()


def test_theme_model_defaults_and_validation(config):
    from common.core.data_models.Config import Config
    from pydantic import ValidationError
    data = config.model_dump()
    data.pop('theme')
    assert Config.model_validate(data).theme.colors() == {
        'Tree': '#F0F0F0', 'Window': '#F0F0F0', 'Console': '#012E4F'}
    data['theme'] = {'treeColor': 'invalid'}
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_theme_restore_defaults_is_pending_until_ok(gui):
    from common.core.data_models.Config import Config
    from common.core.enums.TermFilesPath import TermFilesPath
    from common.gui.windows.settings_window import SettingsWindow
    apply = Mock()
    window = SettingsWindow(gui.config, commit=Mock(), change_colors=apply)
    try:
        initial = dict(window.Appearance.initial_colors)
        for key in initial:
            window.Appearance.choose(key, '#000000')
        window.ResetAllSettingsButton.click()
        defaults = Config(TermFilesPath.DEFAULT_CONFIG).theme
        assert window.Appearance.colors == {
            'Tree': defaults.treeColor, 'Window': defaults.windowColor, 'Console': defaults.consoleColor}
        for key, group in window.Appearance.selectors.items():
            assert group.checkedButton().property('themeColor') == window.Appearance.colors[key]
        assert window.Appearance.initial_colors == initial
        apply.assert_not_called()
        window.cancel()
        apply.assert_not_called()
    finally:
        window.deleteLater()


def test_about_window_contents_and_close_controls(gui, monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.windows.about_window import AboutWindow
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    window = AboutWindow(gui.window)
    try:
        window.show()
        gui.pyqt_application.processEvents()
        assert window.windowTitle() == 'Signal | About'
        assert window.isWindow()
        assert window.windowType() == Qt.WindowType.Dialog
        assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert not window.windowIcon().isNull()
        assert not window.logoLabel.pixmap().isNull()
        assert not window.windowFlags() & (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        widgets = [window.logoLabel, window.UserGuideLink, window.VersionLabel,
                   window.ReleaseLabel, window.AuthorLabel, window.ContactLabel]
        assert [w.y() for w in widgets] == sorted(w.y() for w in widgets)
        assert window.MusicOnOfButton.geometry().bottom() == window.ContactLabel.geometry().bottom() - 3
        assert window.UserGuideLink.font().pointSize() == 12
        assert window.ContactLabel.font().pointSize() == 12
        assert window.line.height() == 1
        window.MusicOnOfButton.setFocus()
        QTest.keyClick(window.MusicOnOfButton, Qt.Key.Key_Escape)
        assert not window.isVisible()
        window.show()
        window.close()
        assert not window.isVisible()
    finally:
        window.deleteLater()


def test_appearance_tab_color_grid_and_preview(gui):
    from common.gui.windows.settings_window import SettingsWindow
    from PyQt6.QtGui import QPalette
    callbacks = {'Tree': gui.window._set_tree_color, 'Window': gui.window._apply_dark_theme,
                 'Console': gui.window._set_console_color}
    settings = SettingsWindow(gui.config, commit=lambda config: None,
                              change_color=lambda key, color: callbacks[key](color, persist=True))
    before = {key: gui.pyqt_application.property(f'signal{key}Color') for key in callbacks}
    try:
        settings.MainTabs.setCurrentWidget(settings.Appearance)
        settings.show()
        gui.pyqt_application.processEvents()
        tab = settings.Appearance
        assert len(tab.selectors) == 3
        for key, group in tab.selectors.items():
            assert len(group.buttons()) == 8
            group.buttons()[1].click()
            assert group.checkedButton() is group.buttons()[1]
            assert gui.pyqt_application.property(f'signal{key}Color') == before[key]
        assert tab.tree.palette().color(QPalette.ColorRole.Base).name().upper() == '#102D28'
        assert not hasattr(gui.window, 'ButtonSetTheme')
        assert [settings.MainTabs.tabText(i) for i in range(settings.MainTabs.count())] == ['General', 'Fields', 'Specification', 'API', 'Theme']
        bar = settings.MainTabs.tabBar()
        assert sum(bar.tabRect(index).width() for index in range(bar.count())) <= bar.width(), [(bar.tabText(i), bar.tabRect(i).width()) for i in range(bar.count())]
        settings.ok()
        for key in callbacks:
            assert gui.pyqt_application.property(f'signal{key}Color') == '#102D28'
    finally:
        settings.hide()
        settings.deleteLater()


def test_console_color_menu_updates_existing_and_future_logs(gui):
    from PyQt6.QtWidgets import QTextBrowser, QTextEdit
    from PyQt6.QtGui import QPalette
    app = gui.pyqt_application
    other_log = QTextBrowser()
    other_log.setObjectName("LogArea")
    other_log.setPlainText("Existing log")
    unrelated = QTextEdit()
    unrelated.ensurePolished()
    original = unrelated.palette().color(QPalette.ColorRole.Base)
    actions = gui.window.console_colors.actions()
    from common.gui.tools.json_views.TreeView import TreeView
    existing_tree = TreeView()
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    from PyQt6.QtWidgets import QTreeWidgetItem, QLineEdit
    transaction_tree = JsonView(gui.config, parent=gui.window)
    item = FieldItem(['4', '000000000100'])
    QTreeWidgetItem.addChild(transaction_tree.root, item)
    item.set_checkbox(True)
    transaction_tree.setCurrentItem(item)
    editor = QLineEdit(transaction_tree.viewport())
    editor.setText('000000000100')
    editor.selectAll()
    assert len(actions) == 8
    assert [action.data() for action in actions][-2:] == ['#011627', '#000000']
    assert [action.data() for action in gui.window.window_colors.actions()] == [action.data() for action in actions]
    selection_before = app.property('signalSelectionColor')
    try:
        for action in actions:
            action.trigger()
            app.processEvents()
            selection = app.property('signalSelectionColor')
            assert selection == selection_before  # Console themes do not change field selection.
            assert item.get_checkbox().palette().color(QPalette.ColorRole.WindowText).name() == '#ffffff'
            editor.ensurePolished()
            assert editor.palette().color(QPalette.ColorRole.Highlight).name() == selection.lower()
            assert editor.selectedText() == '000000000100'
            assert existing_tree.palette().color(QPalette.ColorRole.Highlight).name() == selection.lower()
            new_tree = TreeView()
            assert new_tree.palette().color(QPalette.ColorRole.Highlight).name() == selection.lower()
            new_tree.deleteLater()
            for widget in (gui.window.LogArea, other_log):
                widget.ensurePolished()
                assert widget.palette().color(QPalette.ColorRole.Base).name() == action.data().lower()
            later = QTextBrowser()
            later.setObjectName("LogArea")
            later.ensurePolished()
            assert later.palette().color(QPalette.ColorRole.Base).name() == action.data().lower()
            later.close()
            assert unrelated.palette().color(QPalette.ColorRole.Base) == original
            assert other_log.toPlainText() == "Existing log"
        assert app.styleSheet().count("QTextEdit#LogArea, QPlainTextEdit#LogArea { background-color:") == 1
    finally:
        actions[0].trigger()
        other_log.close()
        unrelated.close()
        existing_tree.close()
        transaction_tree.deleteLater()


@pytest.mark.parametrize('data_format, text', [
    ('JSON', '{"key": "<tag> & 😀", "value": 12, "ok": true, "empty": null}'),
    ('SPEC', '{"fields": {"2": "PAN"}}'),
    ('CONFIG', '{"enabled": false}'),
    ('INI', '[message]\nfield = <value> & text'),
    ('DUMP', '30 32 30 30                                      0200'),
])
def test_print_syntax_preserves_text_and_excludes_logs(gui, data_format, text):
    window = gui.window
    window.set_log_data(text, data_format=data_format)
    gui.pyqt_application.processEvents()
    document = window.LogArea.document()
    assert document.toPlainText() == text
    assert document.firstBlock().layout().formats()
    for color in ('#F0F0F0', '#011627'):
        window._set_console_color(color)
        gui.pyqt_application.processEvents()
        assert document.toPlainText() == text
        assert document.firstBlock().layout().formats()
    window.LogArea.append('INFO {"ordinary": "log"}')
    gui.pyqt_application.processEvents()
    assert not document.lastBlock().layout().formats()
    window.set_log_data('SIGNAL', data_format='SIGNAL')
    assert not document.firstBlock().layout().formats()


def test_clearing_print_disables_syntax_for_new_logs(gui):
    window = gui.window
    window.set_log_data('{"field": 123}\n' * 2000, data_format='SPEC')
    window.clean_window_log()
    window.LogArea.append('[INFO] 2026-09-10 [048][055] test')
    gui.pyqt_application.processEvents()
    assert not window._print_highlighter._timer.isActive()
    assert window._print_highlighter.printed_blocks == 0
    assert not window.LogArea.document().firstBlock().layout().formats()


def test_large_spec_print_yields_to_event_loop(gui):
    from time import perf_counter
    from PyQt6.QtTest import QTest
    data = gui.spec.spec.model_dump_json(indent=4)
    if data.count('\n') < 1000:
        data = '[\n' + ',\n'.join(['{"field": "value", "length": 12}'] * 10000) + '\n]'
    started = perf_counter()
    gui.window.set_log_data(data, data_format='SPEC')
    elapsed = perf_counter() - started
    assert elapsed < 5, elapsed
    highlighter = gui.window._print_highlighter
    assert highlighter._batch_active
    QTest.qWait(50)
    assert highlighter._next_block > 0
    # Switching print format cancels the remaining work from the old document.
    started = perf_counter()
    gui.window.set_log_data('SIGNAL', data_format='SIGNAL')
    replacement_elapsed = perf_counter() - started
    assert replacement_elapsed < 1, replacement_elapsed
    QTest.qWait(20)
    assert gui.window.get_log_data() == 'SIGNAL'
    assert not highlighter._timer.isActive()
    print(f'Replacing partially highlighted spec: {replacement_elapsed:.3f}s')
    print(f'Large spec: {len(data)} characters, initial display {elapsed:.3f}s')


def test_checkbox_created_in_dark_theme_updates_on_light_switch(gui):
    from PyQt6.QtGui import QPalette
    window = gui.window
    window._apply_dark_theme('#102D28')
    tree = window.json_view
    tree.parse_fields({'4': '000000000100'})
    item = tree.get_item_by_path(['4'])
    item.set_checkbox(True)
    checkbox = item.get_checkbox()
    tree.setCurrentItem(tree.root)
    window._apply_dark_theme('#F0F0F0')
    window._set_tree_color('#F0F0F0')
    gui.pyqt_application.processEvents()
    assert checkbox.palette().color(QPalette.ColorRole.WindowText).lightnessF() < 0.3
    tree.setCurrentItem(item)
    assert checkbox.palette().color(QPalette.ColorRole.WindowText).name() == '#ffffff'
    tree.setCurrentItem(tree.root)
    assert checkbox.palette().color(QPalette.ColorRole.WindowText).lightnessF() < 0.3


def test_button_hints_include_window_shortcuts(gui):
    from PyQt6.QtWidgets import QPushButton
    from common.gui.windows.spec_window import SpecWindow
    main = gui.window
    assert 'Ctrl+Z' in main.ButtonUndo.toolTip()
    assert 'Ctrl+P' in main.ButtonPrint.toolTip()
    assert 'Ctrl+O' in main.ButtonFiles.toolTip()
    spec = SpecWindow(gui.connector, gui.config)
    spec.wireless_handler.flushOnClose = True
    try:
        assert 'Ctrl+Z' in spec.UndoButton.toolTip()
        assert 'Ctrl+S' in spec.ButtonBackup.toolTip()
        for window in (main, spec):
            for button in window.findChildren(QPushButton):
                assert button.toolTip(), button.objectName()
    finally:
        spec.deleteLater()


def test_json_mode_toggle_preserves_scroll(gui, monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.core.tools.Parser import Parser
    window = gui.window
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    tree = window.json_view
    tree.parse_fields({str(number): '123' for number in range(2, 65)})
    item = tree.get_item_by_path(['48'])
    item.set_checkbox(False)
    monkeypatch.setattr(Parser, 'split_complex_field', staticmethod(lambda *args: {'51': 'TEST'}))
    window.show()
    try:
        tree.setCurrentItem(item)
        tree.scrollToItem(item)
        QTest.qWait(100)
        position = tree.verticalScrollBar().value()
        assert position > 0
        tree.setColumnWidth(1, 160)
        widths = [tree.columnWidth(column) for column in range(tree.columnCount())]
        for checked in (True, False, True):
            item.get_checkbox().setChecked(checked)
            QTest.qWait(300)
            assert tree.verticalScrollBar().value() == position
            assert tree.currentItem() is item
            assert bool(item.childCount()) == checked
            assert [tree.columnWidth(column) for column in range(tree.columnCount())] == widths
    finally:
        window.hide()


def test_license_text_contrasts_without_selection_after_theme_changes(gui):
    from PyQt6.QtGui import QPalette
    from common.gui.windows.license_window import LicenseWindow
    window = LicenseWindow(gui.config, force=True)
    try:
        for color in ('#011627', '#F0F0F0', '#3B202B'):
            gui.window._apply_dark_theme(color)
            window.InfoBoard.ensurePolished()
            gui.pyqt_application.processEvents()
            palette = window.InfoBoard.palette()
            background = palette.color(QPalette.ColorRole.Base)
            foreground = palette.color(QPalette.ColorRole.Text)
            assert abs(background.lightnessF() - foreground.lightnessF()) > 0.5
            assert not window.InfoBoard.textCursor().hasSelection()
            assert 'GNU GENERAL PUBLIC LICENSE' in window.InfoBoard.toPlainText()
    finally:
        window.deleteLater()


def test_hotkeys_table_fits_after_theme_changes(gui):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.windows.hotkeys_hint_window import HotKeysHintWindow
    window = HotKeysHintWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    try:
        window.show()
        for color in ('#F0F0F0', '#243447', '#102D28', '#F0F0F0'):
            gui.window._apply_dark_theme(color)
            QTest.qWait(50)
            assert window.HintTable.verticalScrollBar().maximum() == 0
            assert window.HintTable.horizontalScrollBar().maximum() == 0
    finally:
        window.hide()
        window.deleteLater()


def test_global_theme_applies_to_existing_and_new_error_dialogs(gui):
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtGui import QPalette
    existing = QMessageBox()
    try:
        for color in ('#3B202B', '#102D28', '#F0F0F0'):
            gui.window._apply_dark_theme(color)
            new = QMessageBox()
            try:
                for dialog in (existing, new):
                    dialog.ensurePolished()
                    assert dialog.palette().color(QPalette.ColorRole.Window) == gui.pyqt_application.palette().color(QPalette.ColorRole.Window)
            finally:
                new.deleteLater()
    finally:
        existing.deleteLater()


def test_light_window_restores_application_palette(gui):
    from PyQt6.QtGui import QPalette
    window = gui.window
    window._apply_dark_theme('#3B202B')
    window._apply_dark_theme('#F0F0F0')
    gui.pyqt_application.processEvents()
    assert window.styleSheet() == ''
    assert not window.property('signalDarkTheme')
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.Button, QPalette.ColorRole.ButtonText):
        assert window.palette().color(role) == gui.pyqt_application.palette().color(role)


def test_window_theme_preserves_console_and_tree_selection(gui):
    from PyQt6.QtGui import QPalette
    app = gui.pyqt_application
    window = gui.window
    console_color = app.property('signalConsoleColor')
    selection_colors = set()
    window.LogArea.ensurePolished()
    background = window.LogArea.palette().color(QPalette.ColorRole.Base)
    for action in window.window_colors.actions():
        action.trigger()
        app.processEvents()
        assert window.property('signalWindowColor') == action.data()
        assert window._appearance_settings.windowColor == action.data()
        assert app.property('signalConsoleColor') == console_color
        selection_color = app.property('signalSelectionColor')
        selection_colors.add(selection_color)
        assert window.LogArea.palette().color(QPalette.ColorRole.Base) == background
        assert window.json_view.palette().color(QPalette.ColorRole.Highlight).name() == selection_color.lower()
    assert len(selection_colors) == 1


def test_light_tree_text_and_sort_button_on_dark_window(gui, monkeypatch):
    from PyQt6.QtGui import QColor, QPalette
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QItemDelegate, QStyleOptionViewItem
    from common.gui.windows.spec_window import SpecWindow
    captured = []
    monkeypatch.setattr(QItemDelegate, 'drawDisplay',
                        lambda self, painter, option, rect, text:
                        captured.append(option.palette.color(QPalette.ColorRole.Text)))
    window = gui.window
    window._apply_dark_theme('#012E4F')
    window._set_tree_color('#F0F0F0')
    spec = SpecWindow(gui.connector, gui.config)
    try:
        for tree in (window.json_view, spec.SpecView):
            tree.ensurePolished()
            option = QStyleOptionViewItem()
            option.palette.setColor(QPalette.ColorRole.Text, QColor('#000000'))
            tree.itemDelegate().drawDisplay(None, option, QRect(), 'Field')
            assert captured[-1].lightnessF() < 0.3
            button = tree.sort_fields_button
            button.ensurePolished()
            assert button.palette().color(QPalette.ColorRole.ButtonText).lightnessF() < 0.3
    finally:
        spec.hide()
        spec.deleteLater()


def test_tree_theme_is_independent_and_saved(gui):
    from common.core.data_models.Config import Config
    from PyQt6.QtGui import QPalette
    from common.gui.windows.spec_window import SpecWindow
    from common.gui.data_models.Appearance import Appearance
    from common.gui.windows.main_window import APPEARANCE_SETTINGS_PATH
    window = gui.window
    app = gui.pyqt_application
    original_window = app.property('signalWindowColor')
    original_console = app.property('signalConsoleColor')
    for color in ('#102D28', '#F0F0F0', '#3B202B'):
        window._set_tree_color(color, persist=True)
        spec = SpecWindow(gui.connector, gui.config)
        try:
            app.processEvents()
            for tree in (window.json_view, spec.SpecView):
                tree.ensurePolished()
                assert tree.palette().color(QPalette.ColorRole.Base).name().upper() == ('#FFFFFF' if color == '#F0F0F0' else color)
                if color == '#F0F0F0':
                    assert tree.palette().color(QPalette.ColorRole.AlternateBase).name().upper() == '#E0E9F6'
            assert app.property('signalWindowColor') == original_window
            assert app.property('signalConsoleColor') == original_console
            assert gui.config.theme.treeColor == color
            assert Config(gui.config_manager.filename).theme.treeColor == color
            style = app.property('signalTreeStyle')
            window._apply_dark_theme('#000000')
            window._set_console_color('#F0F0F0')
            assert app.property('signalTreeStyle') == style
            window._apply_dark_theme(original_window)
            window._set_console_color(original_console)
        finally:
            spec.hide()
            spec.deleteLater()


@pytest.mark.parametrize('kind', ['specification', 'field_constructor'])
def test_editor_splitter_resize_reset_and_reopen(gui, kind):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.windows.spec_window import SpecWindow
    from common.gui.windows.complex_fields_window import ComplexFieldsParser

    def create():
        return (SpecWindow(gui.connector, gui.config) if kind == 'specification'
                else ComplexFieldsParser(gui.config, gui))

    window = create()
    try:
        window.resize(1200, 900)
        window.show()
        gui.pyqt_application.processEvents()
        splitter = window.main_splitter
        toolbar = window.horizontalLayout if kind == 'specification' else window.horizontalLayout_2
        output = window.LogArea if kind == 'specification' else window.TextData
        assert splitter.widget(1).y() - splitter.widget(0).geometry().bottom() - 1 == 3
        assert output.y() - toolbar.geometry().bottom() - 1 == 3
        assert output.maximumHeight() > 1000
        assert window.SearchLine.height() == window.PlusButton.height()
        if kind == 'field_constructor':
            controls = [window.PlusButton, window.MinusButton, window.NextLevelButton,
                        window.UpButton, window.DownButton, window.UndoButton,
                        window.RedoButton, window.SearchLine]
            for left, right in zip(controls, controls[1:]):
                assert right.x() - left.geometry().right() - 1 == 6
        splitter.moveSplitter(round(sum(splitter.sizes()) * 0.7), 1)
        expected = splitter.sizes()[0] / sum(splitter.sizes())
        reopened = create()
        try:
            reopened.resize(1200, 900)
            reopened.show()
            gui.pyqt_application.processEvents()
            sizes = reopened.main_splitter.sizes()
            assert sizes[0] / sum(sizes) == pytest.approx(expected, abs=0.02)
        finally:
            reopened.hide()
            reopened.deleteLater()
        for height in (700, 1100):
            window.resize(1200, height)
            gui.pyqt_application.processEvents()
            handle = splitter.handle(1)
            QTest.mouseDClick(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
            sizes = splitter.sizes()
            assert sizes[0] / sum(sizes) == pytest.approx(0.58, abs=0.003)
    finally:
        window.hide()
        window.deleteLater()


def test_main_toolbar_matches_specification(gui):
    from common.gui.windows.spec_window import SpecWindow
    spec = SpecWindow(gui.connector, gui.config)
    main = gui.window
    try:
        spec.show()
        main.show()
        for width in (1200, 1800):
            main.resize(width, 900)
            gui.pyqt_application.processEvents()
            buttons = [main.PlusButton, main.MinusButton, main.NextLevelButton,
                       main.ButtonDisable, main.ButtonEnable, main.ButtonEnableAll,
                       main.ButtonUndo, main.ButtonRedo]
            for left, right in zip(buttons, buttons[1:]):
                assert right.x() - left.geometry().right() - 1 == 6
            for left, right in [(main.PlusButton, spec.PlusButton),
                                (main.MinusButton, spec.MinusButton),
                                (main.ButtonUndo, spec.UndoButton)]:
                assert left.size() == right.size()
            assert main.tab_view.currentWidget().layout().contentsMargins().bottom() == 0
            for control in (main.SearchLine,):
                assert control.height() == main.PlusButton.height()
                assert control.y() == main.PlusButton.y()
    finally:
        main.hide()
        spec.hide()
        spec.deleteLater()


def test_splitter_uses_window_height_and_entire_handle(gui):
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest
    window = gui.window
    window.show()
    window.resize(1400, 1000)
    gui.pyqt_application.processEvents()
    header = window.horizontalLayout_4
    assert header.geometry().height() <= header.sizeHint().height() + 2
    splitter = window.main_splitter
    assert splitter.y() <= header.geometry().bottom() + 12
    pane = splitter.widget(0)
    # The visible separator is the top border of the lower panel, above its toolbar.
    assert window.TabViewLayout.geometry().bottom() == pane.height() - 1
    handle = splitter.handle(1)
    assert handle.y() <= pane.y() + pane.height()
    assert splitter.widget(1).y() - pane.geometry().bottom() - 1 == 3
    assert handle.height() >= 3  # Qt expands the hit area without widening the visible gap.
    assert window.horizontalLayout.geometry().top() == 0
    table_bottom_margin = window.tab_view.currentWidget().layout().contentsMargins().bottom()
    assert window.LogArea.y() - window.horizontalLayout.geometry().bottom() - 1 == 3 + table_bottom_margin
    assert window.LogArea.y() > window.horizontalLayout.geometry().bottom()
    for edge in (0, 0.5, 1):
        point = QPoint(handle.width() // 2, round((handle.height() - 1) * edge))
        before = splitter.sizes()[0]
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(handle, point + QPoint(0, 20), delay=20)
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=point + QPoint(0, 20))
        gui.pyqt_application.processEvents()
        assert splitter.sizes()[0] > before
    window.hide()


def test_splitter_double_click_restores_default_at_different_window_sizes(gui):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.data_models.Appearance import Appearance
    from common.gui.windows.main_window import APPEARANCE_SETTINGS_PATH
    window = gui.window
    window.show()
    splitter = window.main_splitter
    for height in (700, 1000, 1400):
        window.resize(1400, height)
        gui.pyqt_application.processEvents()
        splitter.moveSplitter(round(sum(splitter.sizes()) * 0.75), 1)
        handle = splitter.handle(1)
        QTest.mouseDClick(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        sizes = splitter.sizes()
        assert sizes[0] / sum(sizes) == pytest.approx(0.58, abs=0.003)
        QTest.qWait(300)
        assert Appearance.load(APPEARANCE_SETTINGS_PATH).transactionPaneRatio == pytest.approx(0.58, abs=0.003)
    window.hide()


def test_splitter_restores_proportions_after_reopening(gui):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.windows.main_window import MainWindow, APPEARANCE_SETTINGS_PATH
    from common.gui.data_models.Appearance import Appearance
    window = gui.window
    window.show()
    gui.pyqt_application.processEvents()
    splitter = window.main_splitter
    assert splitter.orientation() == Qt.Orientation.Vertical
    assert not splitter.childrenCollapsible()
    splitter.moveSplitter(round(sum(splitter.sizes()) * 0.7), 1)
    expected = splitter.sizes()[0] / sum(splitter.sizes())
    QTest.qWait(300)
    assert Appearance.load(APPEARANCE_SETTINGS_PATH).transactionPaneRatio == pytest.approx(expected)
    splitter.moveSplitter(round(sum(splitter.sizes()) * 0.65), 1)
    expected = splitter.sizes()[0] / sum(splitter.sizes())
    window.window_close.disconnect()  # Exercise window persistence without shutting down the test application.
    window.close()
    assert Appearance.load(APPEARANCE_SETTINGS_PATH).transactionPaneRatio == pytest.approx(expected)
    reopened = MainWindow(gui.config)
    try:
        reopened.show()
        gui.pyqt_application.processEvents()
        sizes = reopened.main_splitter.sizes()
        assert sizes[0] / sum(sizes) == pytest.approx(expected, abs=0.02)
        reopened.resize(1400, 1400)
        gui.pyqt_application.processEvents()
        assert reopened.tab_view.height() > 520
        reopened.main_splitter.moveSplitter(0, 1)
        assert min(reopened.main_splitter.sizes()) > 0
    finally:
        reopened.close()
        reopened.deleteLater()


def test_console_color_survives_new_window(gui):
    from common.gui.windows.main_window import MainWindow
    app = gui.pyqt_application
    action = gui.window.console_colors.actions()[3]
    action.trigger()
    assert gui.window._appearance_settings.consoleColor == action.data()
    from common.gui.windows.main_window import APPEARANCE_SETTINGS_PATH
    from common.gui.data_models.Appearance import Appearance
    assert gui.config.theme.consoleColor == action.data()
    app.setProperty('signalConsoleColor', None)
    reopened = MainWindow(gui.config)
    try:
        assert app.property('signalConsoleColor') == action.data()
        assert reopened.console_colors.checkedAction().data() == action.data()
    finally:
        reopened.hide()
        reopened.deleteLater()
        gui.window.console_colors.actions()[0].trigger()


def test_theme_selection_after_full_gui_setup(gui):
    from PyQt6.QtWidgets import QLineEdit, QTreeWidgetItem
    from PyQt6.QtGui import QPalette
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    tree = JsonView(gui.config, parent=gui.window)
    item = FieldItem(['4', '000000000100'])
    QTreeWidgetItem.addChild(tree.root, item)
    item.set_checkbox(True)
    tree.setCurrentItem(item)
    editor = QLineEdit(tree.viewport())
    gui.window.console_colors.actions()[-1].trigger()
    gui._test_original_setup()
    gui._run_timer.stop()
    editor.ensurePolished()
    expected = gui.pyqt_application.property('signalSelectionColor')
    assert tree.palette().color(QPalette.ColorRole.Highlight).name() == expected.lower()
    assert editor.palette().color(QPalette.ColorRole.Highlight).name() == expected.lower()
    assert item.get_checkbox().palette().color(QPalette.ColorRole.WindowText).name() == '#ffffff'
    tree.deleteLater()


def config_url():
    from common.api.enums.ApiUrl import ApiUrl
    return f"{ApiUrl.API}{ApiUrl.UPDATE_CONFIG}"


def test_http_put_reaches_gui_all_tabs_and_nested_validators(gui):
    from common.gui.tools.json_views.JsonView import JsonView
    gui.window.tab_view.add_tab(tab_name="second")
    views = gui.window.tab_view.findChildren(JsonView)
    assert len(views) >= 2
    before = gui.config
    candidate = gui.api.get_config()
    candidate.fields.hide_secrets = not candidate.fields.hide_secrets
    candidate.host.port = 12345
    response = asyncio.run(request(gui, "PUT", config_url(), json=candidate.model_dump()))
    assert response.status_code == 200, response.text
    assert gui.config is before
    assert gui.config is gui.api.config is gui.connector.config is gui.window.config
    for view in views:
        assert view.config is before
        assert view.parser.config.host.port == 12345
        assert view.validator.validator.config.host.port == 12345
    assert gui.trans_validator.validator.config.host.port == 12345
    assert gui.api.parser.config.host.port == 12345
    assert response.json()["host"]["port"] == 12345


def test_gui_settings_commit_is_visible_through_http_get(gui):
    from common.gui.windows.settings_window import SettingsWindow
    draft, revision = gui.config_manager.read()
    window = SettingsWindow(draft, commit=lambda candidate: gui.update_config(candidate, expected_revision=revision))
    window.SvPort.setValue(23456)
    window.ok()
    assert window.result() == window.DialogCode.Accepted
    response = asyncio.run(request(gui, "GET", config_url()))
    assert response.status_code == 200
    assert response.json()["host"]["port"] == 23456
    window.close()


def test_open_gui_editor_reports_conflict_after_http_update(gui, monkeypatch):
    from common.gui.windows.settings_window import SettingsWindow
    reporting = importlib.import_module("common.core.tools.ErrorReporting")
    report = Mock()
    monkeypatch.setattr(reporting, "report_error", report)
    draft, revision = gui.config_manager.read()
    window = SettingsWindow(draft, commit=lambda candidate: gui.update_config(candidate, expected_revision=revision))
    candidate = gui.api.get_config()
    candidate.host.port = 34567
    response = asyncio.run(request(gui, "PUT", config_url(), json=candidate.model_dump()))
    assert response.status_code == 200
    window.SvPort.setValue(12345)
    window.ok()
    assert report.called
    assert "Reopen settings" in str(report.call_args.args[0])
    assert gui.config.host.port == 34567
    assert window.result() != window.DialogCode.Accepted
    window.close()


def test_listener_change_saved_while_api_running_without_restart(gui, monkeypatch):
    monkeypatch.setattr(gui.api.api, "is_api_started", lambda: True)
    restart = Mock()
    stop = Mock()
    monkeypatch.setattr(gui.api.api, "restart", restart)
    monkeypatch.setattr(gui.api.api, "stop", stop)
    old = gui.api.get_config()
    candidate = old.model_copy(deep=True)
    candidate.api.port += 1
    candidate.api.address = "127.0.0.1"
    response = asyncio.run(request(gui, "PUT", config_url(), json=candidate.model_dump()))
    assert response.status_code == 200, response.text
    assert response.json()["api"] == candidate.api.model_dump()
    assert gui.api.get_config().api == candidate.api
    from common.core.data_models.Config import Config
    assert Config(gui.config_manager.filename).api == candidate.api
    restart.assert_not_called()
    stop.assert_not_called()


def test_cli_overrides_and_api_share_manager(runtime, config, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from common.cli.tools.SignalCli import SignalCli
    from common.gui.tools.ResourcePath import ResourcePath
    monkeypatch.setattr(ResourcePath, "resource_path", staticmethod(lambda path: str(tmp_path)))
    monkeypatch.setattr(SignalCli, "setup", lambda self: None)
    config._source_file = str(tmp_path / "cli.json")
    cli = SignalCli(config)
    cli.parse_cli_config(SimpleNamespace(address="127.0.0.2", port=23456, log_level=None))
    assert cli.config is cli.api.config is cli.connector.config
    assert cli.api.get_config().host.port == 23456
    assert not cli.config_manager.filename.exists()  # Command-line overrides are not saved.
    candidate = cli.api.get_config()
    candidate.host.port = 34567
    cli.update_config(candidate)
    assert cli.parser.config.host.port == cli.api.get_config().host.port == 34567


def test_library_client_reads_current_settings(runtime):
    from common.lib.TerminalClient import TerminalClient
    client = TerminalClient()
    candidate = client.config.model_copy(deep=True)
    candidate.host.port = 12345
    client.terminal.update_config(candidate, persist=False)
    assert client.config is client.parser.config is client.terminal.config
    assert client.config.host.port == 12345


def test_api_failed_save_keeps_all_gui_views(gui, monkeypatch):
    module = importlib.import_module("common.core.tools.ConfigManager")
    from common.core.exceptions.exceptions import DataFileError
    old = gui.api.get_config()
    candidate = old.model_copy(deep=True)
    candidate.host.port = 12345
    monkeypatch.setattr(module, "save_config", Mock(side_effect=DataFileError("config.json", "save", "denied")))
    response = asyncio.run(request(gui, "PUT", config_url(), json=candidate.model_dump()))
    assert response.status_code == 500
    assert gui.api.get_config() == old
    assert gui.window.config.host.port == gui.connector.config.host.port == old.host.port


def test_updates_trigger_timer_behavior_in_gui(gui):
    candidate = gui.api.get_config()
    candidate.host.keep_alive_mode = True
    candidate.host.keep_alive_interval = 37
    response = asyncio.run(request(gui, "PUT", config_url(), json=candidate.model_dump()))
    assert response.status_code == 200
    assert gui.keep_alive_timer._trans_loop_timer.isActive()
    assert gui.keep_alive_timer._trans_loop_timer.interval() == 37000
    candidate.host.keep_alive_mode = False
    gui.update_config(candidate)
    assert not gui.keep_alive_timer._trans_loop_timer.isActive()


def test_muted_palette_and_contrast(gui):
    from PyQt6.QtGui import QPalette
    from common.gui.windows.settings_window import SettingsWindow
    app = gui.pyqt_application
    window = SettingsWindow(gui.config, commit=gui.config_manager.replace,
                            change_colors=gui.window.apply_theme_colors)
    try:
        colors = ['#F0F0F0', '#102D28', '#3B202B', '#292D32',
                  '#243447', '#012E4F', '#011627', '#000000']
        assert [b.property('themeColor') for b in window.Appearance.selectors['Tree'].buttons()] == colors
        button = next(b for b in window.Appearance.color_buttons
                      if b.accessibleName() == 'Set all: Dark green')
        button.click()
        window.ApplyThemeButton.click()
        app.processEvents()
        assert app.property('signalDarkTheme') is True
        assert gui.window.json_view.palette().color(QPalette.ColorRole.Text).lightness() > 180
        assert gui.window.json_view.palette().color(QPalette.ColorRole.Base).name() == '#102d28'
        assert app.palette().color(QPalette.ColorRole.Window).name() == '#0d2420'
        assert window.config.theme.windowColor == '#102D28'
    finally:
        window.hide()
        window.deleteLater()


def test_reset_settings_only_on_general(runtime, config):
    from PyQt6.QtWidgets import QPushButton, QDialogButtonBox
    from common.gui.windows.settings_window import SettingsWindow
    saved = []
    window = SettingsWindow(config, commit=saved.append)
    try:
        window.show()
        runtime.app.processEvents()
        button = window.ResetAllSettingsButton
        assert button.text() == 'Reset all settings'
        assert button.isVisible()
        assert len([b for b in window.findChildren(QPushButton) if b.text() == button.text()]) == 1
        button.click()
        assert not saved
        for box in (window.FieldsButtonBox, window.ApiButtonBox,
                    window.SpecificationButtonBox, window.ThemeButtonBox):
            assert box.button(QDialogButtonBox.StandardButton.RestoreDefaults) is None
        window.MainTabs.setCurrentWidget(window.Appearance)
        runtime.app.processEvents()
        assert not button.isVisible()
        window.cancel()
        assert not saved
    finally:
        window.hide()
        window.deleteLater()


def test_default_theme_applies_immediately_without_other_settings(runtime, config):
    from common.gui.windows.settings_window import SettingsWindow
    saved, applied = [], []
    window = SettingsWindow(config, commit=lambda c: saved.append(c.model_copy(deep=True)),
                            change_colors=applied.append)
    try:
        window.show()
        original = config.host.port
        window.SvPort.setValue(original + 1)
        window.MainTabs.setCurrentWidget(window.Appearance)
        runtime.app.processEvents()
        assert window.DefaultThemeButton.isVisible()
        window.Appearance.choose('Window', '#000000')
        window.config.theme.windowColor = '#000000'
        window.Appearance.initial_colors['Window'] = '#000000'
        window.DefaultThemeButton.click()
        expected = {'Tree': '#F0F0F0', 'Window': '#F0F0F0', 'Console': '#012E4F'}
        assert saved[-1].theme.colors() == expected
        assert saved[-1].host.port == original
        assert applied[-1] == {'Window': '#F0F0F0'}
        assert window.Appearance.colors == expected
        assert window.Appearance.initial_colors == expected
        assert all(group.checkedButton().property('themeColor') == expected[key]
                   for key, group in window.Appearance.selectors.items())
        assert window.SvPort.value() == original + 1
        assert window.isVisible()
        window.DefaultThemeButton.click()
        assert len(saved) == 1
        window.cancel()
        assert len(saved) == 1
    finally:
        window.hide()
        window.deleteLater()


def test_light_presets_apply_with_dark_text_and_visible_buttons(gui):
    from PyQt6.QtGui import QPalette
    from common.gui.windows.settings_window import SettingsWindow
    from common.gui.data_models.Appearance import THEME_PRESETS
    window = SettingsWindow(gui.config, commit=gui.config_manager.replace,
                            change_colors=gui.window.apply_theme_colors)
    app = gui.pyqt_application
    try:
        for color in ('#FFFBEB', '#EFF1F5'):
            preset = THEME_PRESETS[color]
            window.Appearance.set_colors(dict.fromkeys(('Tree', 'Window', 'Console'), color))
            window.ApplyThemeButton.click()
            app.processEvents()
            assert app.property('signalDarkTheme') is False
            assert window.property('lightButtons') is True
            assert gui.window.json_view.palette().color(QPalette.ColorRole.Base).name() == color.lower()
            assert gui.window.json_view.palette().color(QPalette.ColorRole.Text).name() == preset['text'].lower()
            assert gui.window.json_view.palette().color(QPalette.ColorRole.Highlight).name() == preset['selection'].lower()
            assert app.palette().color(QPalette.ColorRole.Window).name() == color.lower()
            assert 'border: 1px solid #929BA5' in window.Appearance.preview.styleSheet()
            assert window.config.theme.windowColor == color
    finally:
        window.hide()
        window.deleteLater()
