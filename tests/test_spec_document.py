import json
from copy import deepcopy
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def gui_error_presentation(runtime, monkeypatch):
    # The headless core no longer imports/installs GUI error presentation implicitly.
    import common.core.tools.ErrorReporting as reporting
    from common.gui.tools.ErrorPresentation import show_error
    monkeypatch.setattr(reporting, '_gui_error_handler', show_error)


@pytest.mark.parametrize('choice', ['fix', 'restore', 'exit'])
def test_recovery_dialog_buttons_dispatch_separate_actions(runtime, choice):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from common.gui.windows.error_dialog import ErrorDialog
    from common.core.tools.ErrorReporting import report_error
    selected = []
    def click():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ErrorDialog)
        assert dialog.fix_button.text() == 'Fix specification'
        assert dialog.recovery_button.text() == 'Restore'
        assert dialog.ok.text() == 'Exit'
        assert not dialog.fix_button.geometry().intersects(dialog.recovery_button.geometry())
        {'fix': dialog.fix_button, 'restore': dialog.recovery_button, 'exit': dialog.ok}[choice].click()
    QTimer.singleShot(0, click)
    report_error(ValueError('Invalid specification'), gui=True,
                 fix_action=lambda: selected.append('fix'),
                 recovery_action=lambda: selected.append('restore'),
                 exit_action=lambda: selected.append('exit'))
    assert selected == [choice]


@pytest.mark.parametrize('problem', ['field', 'json', 'missing'])
@pytest.mark.parametrize('has_backups', [False, True])
def test_startup_without_backups_offers_editor_only_for_repairable_file(runtime, document, monkeypatch, tmp_path, problem, has_backups):
    from types import SimpleNamespace
    from common.gui.tools.SignalGui import SignalGui
    from common.gui.windows.spec_window import SpecWindow
    import common.core.tools.ErrorReporting as reporting
    document['fields']['4']['min_length'] = ''
    text = json.dumps(document) if problem == 'field' else ('{' if problem == 'json' else None)
    calls, drafts = [], []
    monkeypatch.setattr(SpecWindow, 'has_backups', staticmethod(lambda: has_backups))
    monkeypatch.setattr(reporting, 'report_error', lambda error, **kwargs: calls.append(kwargs))
    spec = SimpleNamespace(recovery_error='Invalid specification', recovery_exception=ValueError('Invalid specification'),
                           recovery_text=text, filename=str(tmp_path / 'specification.json'))
    gui = SimpleNamespace(spec=spec, show_license_dialog=lambda: True, window=SimpleNamespace(show=lambda: None),
                          restore_specification_backup=lambda: None,
                          run_specification_window=lambda **kwargs: drafts.append(kwargs['draft']))
    SignalGui.on_startup(gui)
    assert len(calls) == 1
    if problem == 'field':
        assert 'Open File' not in calls[0]['action']
        calls[0]['fix_action']()
        assert drafts[0].fields['4'].min_length == ''
        assert spec.recovery_error is not None
    else:
        assert calls[0]['fix_action'] is None
    assert callable(calls[0]['recovery_action']) == has_backups


def test_recovery_success_uses_green_info_in_real_gui_handler(runtime):
    from loguru import logger
    from common.gui.tools.WirelessHandler import WirelessHandler
    handler = WirelessHandler()
    markup = []
    handler.formatted_record_appeared.connect(markup.append)
    sink = logger.add(handler, format='{message}', level='INFO')
    try:
        logger.bind(recovery_success=True).info('Recovery completed')
    finally:
        logger.remove(sink)
    assert len(markup) == 1
    assert '[INFO]' in markup[0]
    assert 'Level 25' not in markup[0]
    assert 'color: #ADDB67;">Recovery completed' in markup[0]


@pytest.mark.parametrize('cancel', [False, True])
def test_direct_recovery_does_not_apply_invalid_or_cancelled_backup(runtime, document, tmp_path, monkeypatch, cancel):
    from types import SimpleNamespace
    from common.gui.tools.SignalGui import SignalGui
    from common.gui.windows.spec_window import SpecWindow
    from PyQt6.QtWidgets import QFileDialog
    document['fields']['4']['min_length'] = ''
    path = tmp_path / 'spec_backup_test.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    monkeypatch.setattr(SpecWindow, 'valid_backups', staticmethod(lambda: [path]))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: ('' if cancel else str(path), ''))
    drafts = []
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid or cancelled backup was applied')
    gui = SimpleNamespace(window=SimpleNamespace(set_focus=lambda: None), spec=SimpleNamespace(reload_spec=forbidden),
                          _resume_after_spec_recovery=forbidden,
                          run_specification_window=lambda **kwargs: drafts.append(kwargs['draft']))
    SignalGui.restore_specification_backup(gui)
    assert len(drafts) == (0 if cancel else 1)


def test_recovery_error_is_short_and_logged_before_success(runtime, monkeypatch, tmp_path):
    from loguru import logger
    import common.gui.windows.error_dialog as dialogs
    from common.core.tools.ErrorReporting import report_error, specification_recovery_message
    records = []
    shown = {}
    class Dialog:
        recovery_requested = True
        def __init__(self, message, trace, parent, **options):
            shown.update(message=message, trace=trace, **options)
        def exec(self):
            pass
    monkeypatch.setattr(dialogs, 'ErrorDialog', Dialog)
    sink = logger.add(lambda message: records.append((message.record['level'].name, str(message))), level='INFO')
    try:
        report_error(ValueError('technical diagnostic'), gui=True,
                     user_message=specification_recovery_message(tmp_path / 'specification.json', ''),
                     action='Choose Open backup.',
                     recovery_action=lambda: logger.info('Recovery completed'))
    finally:
        logger.remove(sink)
    assert shown['recovery_label'] == 'Restore'
    assert 'file is empty' in shown['message']
    assert 'technical diagnostic' not in shown['message']
    assert 'technical diagnostic' in shown['trace']
    assert [level for level, _ in records] == ['ERROR', 'INFO']
    assert 'technical diagnostic' not in records[0][1]
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QCloseEvent


@pytest.fixture
def document(runtime):
    return {'name': 'Test specification', 'mti': [{'request': '0200', 'response': '0210'}], 'fields': {'4': {
        'field_number': '4', 'field_path': ['4'], 'description': 'Amount',
        'min_length': 1, 'max_length': 12, 'var_length': 0, 'tag_length': 0,
        'alpha': False, 'numeric': True, 'special': False, 'generate': False,
        'matching': False, 'reversal': False, 'reserved_for_future': False,
    }}}


def test_recovery_saves_with_fallback_config_and_no_regular_config(runtime, config, document, monkeypatch, tmp_path):
    from pathlib import Path
    from common.core.tools.StartupConfig import load_startup_config
    from common.core.tools.ConfigManager import ConfigManager
    from common.core.enums.TermFilesPath import TermFilesPath, TermDirs
    from common.core.tools.EpaySpecification import EpaySpecification
    from common.core.data_models.EpaySpecificationModel import EpaySpecModel
    monkeypatch.chdir(tmp_path)
    defaults = Path(TermFilesPath.DEFAULT_CONFIG)
    defaults.parent.mkdir(parents=True)
    defaults.write_text(config.model_dump_json(), encoding='utf-8')
    fallback, warning = load_startup_config()
    assert warning and not Path(TermFilesPath.CONFIG).exists()
    active = EpaySpecification()
    monkeypatch.setattr(active, 'filename', str(tmp_path / 'restored.json'))
    monkeypatch.setattr(active, '_specification_model', active.spec.model_copy(deep=True))
    for name, value in (('recovery_error', 'missing'), ('recovery_text', None), ('recovery_exception', None)):
        monkeypatch.setattr(active, name, value)
    active.reload_spec(EpaySpecModel.model_validate(document), True, config=ConfigManager(fallback).view)
    active.require_ready()
    EpaySpecModel(active.filename).validate_for_use()
    backups = list(Path(TermDirs.SPEC_BACKUP_DIR).glob('*.json'))
    assert len(backups) == 1
    EpaySpecModel(backups[0]).validate_for_use()
    assert not Path(TermFilesPath.CONFIG).exists()


def test_backup_rotation_uses_live_settings_and_independent_instances(runtime, config, document, monkeypatch, tmp_path):
    from common.core.tools.ConfigManager import ConfigManager
    from common.core.tools.SpecFilesRotator import SpecFilesRotator
    from common.core.data_models.EpaySpecificationModel import EpaySpecModel
    from common.core.enums.TermFilesPath import TermDirs
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    config.specification.backup_storage = True
    config.specification.backup_storage_depth = 3
    manager = ConfigManager(config)
    rotator = SpecFilesRotator(manager.view)
    other = SpecFilesRotator(config.model_copy(deep=True))
    assert other is not rotator
    candidate = EpaySpecModel.model_validate(document)
    for name in ('first', 'second'):
        candidate.name = name
        rotator.backup_spec(required=True, specification=candidate)
    assert len(list(Path(TermDirs.SPEC_BACKUP_DIR).glob('*.json'))) == 2
    updated, _ = manager.read()
    updated.specification.backup_storage_depth = 1
    manager.replace(updated, persist=False)
    candidate.name = 'third'
    rotator.backup_spec(required=True, specification=candidate)
    assert len(list(Path(TermDirs.SPEC_BACKUP_DIR).glob('*.json'))) == 1
    assert other.config.specification.backup_storage_depth == 3


@pytest.mark.parametrize('bad', ['', 'abc', None])
def test_import_retains_repairable_cells_without_installing(runtime, document, bad):
    from common.gui.tools.spec_document import parse_spec_document
    from common.gui.tools.json_views.SpecView import SpecView
    from common.core.tools.EpaySpecification import EpaySpecification
    active = EpaySpecification().spec.model_dump()
    document['fields']['4']['min_length'] = bad
    draft = parse_spec_document(json.dumps(document))
    view = SpecView(SimpleNamespace(read_only=False))
    try:
        view.parse_spec(draft)
        assert view.root.child(0).text(2) == ('' if bad is None else bad)
        with pytest.raises(ValueError):
            view.generate_spec()
        assert EpaySpecification().spec.model_dump() == active
        view.root.child(0).setText(2, '1')
        view.generate_spec().validate_for_use()
    finally:
        view.close()
        view.deleteLater()


@pytest.mark.parametrize('change', ['unicode', 'structure', 'children'])
def test_critical_import_is_rejected(runtime, document, change):
    from common.gui.tools.spec_document import parse_spec_document
    if change == 'unicode':
        document['fields']['4']['description'] = 'Мама'
    elif change == 'structure':
        document['fields'] = []
    else:
        document['fields']['4']['fields'] = []
    with pytest.raises(ValueError):
        parse_spec_document(json.dumps(document))


def test_generated_fields_follow_specification_replacement(runtime, document, monkeypatch):
    from common.core.tools.EpaySpecification import EpaySpecification
    from common.core.data_models.EpaySpecificationModel import EpaySpecModel
    from common.core.data_models.Transaction import Transaction, OldTransactionConfig
    active = EpaySpecification()
    monkeypatch.setattr(active, '_specification_model', EpaySpecModel())
    with pytest.raises(ValueError):
        Transaction(message_type='0200', data_fields={}, generate_fields=['4'])
    document['fields']['4']['generate'] = True
    active._specification_model = EpaySpecModel.model_validate(document)
    assert Transaction(message_type='0200', data_fields={}, generate_fields=['4']).generate_fields == ['4']
    assert OldTransactionConfig(generate_fields=['4']).generate_fields == ['4']
    with pytest.raises(ValueError):
        Transaction(message_type='0200', data_fields={}, generate_fields=['7'])


def test_empty_description_is_valid(runtime, document):
    from common.gui.tools.spec_document import parse_spec_document
    from common.gui.tools.json_views.SpecView import SpecView
    document['fields']['4']['description'] = ''
    view = SpecView(SimpleNamespace(read_only=False))
    try:
        view.parse_spec(parse_spec_document(json.dumps(document)))
        result = view.validator.validate_spec_row(view.root.child(0))
        assert not any(result.errors.values())
        view.generate_spec().validate_for_use()
    finally:
        view.close()
        view.deleteLater()


def test_explicit_empty_number_is_preserved_and_sorted_first(runtime, document):
    from common.gui.tools.spec_document import parse_spec_document
    from common.gui.tools.json_views.SpecView import SpecView
    document['fields']['6'] = dict(document['fields']['4'], field_number='')
    view = SpecView(SimpleNamespace(read_only=False))
    try:
        view.parse_spec(parse_spec_document(json.dumps(document)))
        assert view.root.child(0).field_number == ''
        assert view.root.child(1).field_number == '4'
        view.sort_top_level_fields(0)
        assert view.root.child(0).field_number == ''
    finally:
        view.close()
        view.deleteLater()


def test_error_dialog_offers_recovery_without_applying(runtime):
    from common.gui.windows.error_dialog import ErrorDialog
    from PyQt6.QtTest import QTest
    from PyQt6.QtCore import Qt
    dialog = ErrorDialog('Cannot load specification', 'trace', recovery_label='Open backup...')
    try:
        dialog.show()
        QTest.mouseClick(dialog.recovery_button, Qt.MouseButton.LeftButton)
        assert dialog.recovery_requested
        assert not dialog.isVisible()
    finally:
        dialog.deleteLater()


def test_backup_offer_depends_on_existing_backup_files(runtime, document, monkeypatch, tmp_path):
    import common.gui.windows.spec_window as module
    monkeypatch.setattr(module, 'TermDirs', SimpleNamespace(SPEC_BACKUP_DIR=str(tmp_path)))
    assert not module.SpecWindow.has_backups()
    (tmp_path / 'other.json').write_text('{}')
    assert not module.SpecWindow.has_backups()
    (tmp_path / 'spec_backup_test.json').write_text('{}')
    assert not module.SpecWindow.has_backups()
    (tmp_path / 'spec_backup_valid.json').write_text(json.dumps(document))
    assert module.SpecWindow.has_backups()


@pytest.mark.parametrize('commit', [False, True])
def test_successful_apply_is_backed_up_and_clears_recovery(runtime, document, monkeypatch, tmp_path, commit):
    from common.core.tools.EpaySpecification import EpaySpecification
    from common.core.tools.SpecFilesRotator import SpecFilesRotator
    from common.core.data_models.EpaySpecificationModel import EpaySpecModel
    active = EpaySpecification()
    path = tmp_path / 'spec.json'
    path.write_text('original disk bytes', encoding='utf-8')
    monkeypatch.setattr(active, 'filename', str(path))
    monkeypatch.setattr(active, '_specification_model', active.spec.model_copy(deep=True))
    monkeypatch.setattr(active, 'recovery_error', 'broken')
    monkeypatch.setattr(active, 'recovery_text', 'original disk bytes')
    calls = []
    def backup(self, **kwargs):
        assert path.read_text() == 'original disk bytes'
        calls.append(kwargs)
        return 'backup.json'
    monkeypatch.setattr(SpecFilesRotator, 'backup_spec', backup)
    active.reload_spec(EpaySpecModel.model_validate(document), commit)
    assert len(calls) == 1 and calls[0]['required'] is True
    calls[0]['specification'].validate_for_use()
    active.require_ready()
    if commit:
        EpaySpecModel(str(path)).validate_for_use()
    else:
        assert path.read_text() == 'original disk bytes'


def test_backup_rejects_damaged_source_and_rotates_valid_documents(runtime, config, document, monkeypatch, tmp_path):
    from common.core.tools.EpaySpecification import EpaySpecification
    from common.core.tools.SpecFilesRotator import SpecFilesRotator
    import importlib
    module = importlib.import_module('common.core.tools.SpecFilesRotator')
    active = EpaySpecification()
    path = tmp_path / 'spec.json'
    original = b'broken\x00original'
    path.write_bytes(original)
    monkeypatch.setattr(active, 'filename', str(path))
    monkeypatch.setattr(active, 'recovery_error', 'broken')
    from common.core.data_models.EpaySpecificationModel import EpaySpecModel
    monkeypatch.setattr(active, '_specification_model', EpaySpecModel())
    backup_dir = tmp_path / 'backups'
    monkeypatch.setattr(module, 'TermDirs', SimpleNamespace(SPEC_BACKUP_DIR=str(backup_dir)))
    rotator = SpecFilesRotator(config)
    assert rotator.backup_spec() is None
    assert not backup_dir.exists()
    candidate = EpaySpecModel.model_validate(document)
    first = rotator.backup_spec(required=True, specification=candidate)
    EpaySpecModel(str(backup_dir / first)).validate_for_use()
    monkeypatch.setattr(rotator, 'config', SimpleNamespace(specification=SimpleNamespace(
        backup_storage=False, backup_storage_depth=1)))
    candidate.name = 'Changed name'
    second = rotator.backup_spec(required=True, specification=candidate)
    EpaySpecModel(str(backup_dir / second)).validate_for_use()
    assert len(list(backup_dir.iterdir())) == 1


@pytest.mark.parametrize('problem', ['empty_length', 'unicode', 'bad_json', 'empty_number', 'empty_key', 'missing'])
@pytest.mark.parametrize('load_default', [False, True])
def test_cold_start_with_bad_file_keeps_main_and_spec_windows_available(runtime, document, tmp_path, problem, load_default):
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    from common.core.enums.TermFilesPath import TermFilesPath
    shutil.copytree('common/data', tmp_path / 'common/data')
    shutil.copytree(Path(__file__).resolve().parents[1] / 'common/data/static', tmp_path / 'common/data/static')
    repaired = deepcopy(document)
    repaired['fields']['4']['generate'] = True
    (tmp_path / 'repair.json').write_text(json.dumps(repaired), encoding='utf-8')
    default_file = tmp_path / str(TermFilesPath.DEFAULT_FILE)
    default_file.parent.mkdir(parents=True, exist_ok=True)
    default_file.write_text(json.dumps({'message_type': '0200', 'data_fields': {'4': '1'},
                                       'generate_fields': ['4']}), encoding='utf-8')
    if problem == 'empty_length':
        document['fields']['4']['min_length'] = ''
    elif problem == 'unicode':
        document['fields']['4']['description'] = 'Мама'
    elif problem == 'empty_number':
        document['fields']['4']['field_number'] = ''
    elif problem == 'empty_key':
        document['fields'][''] = document['fields'].pop('4')
    path = tmp_path / str(TermFilesPath.SPECIFICATION)
    path.write_text('not JSON' if problem == 'bad_json' else json.dumps(document), encoding='utf-8')
    if problem == 'missing':
        path.unlink()
    backup = tmp_path / 'common/data/spec_backup/spec_backup_20990101_000000_12345.json'
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps(repaired), encoding='utf-8')
    script = '''
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication, QEvent, QTimer
app = QApplication([])
import sys, traceback, os
def exception_hook(kind, error, tb):
    traceback.print_exception(kind, error, tb)
    sys.stderr.flush()
    os._exit(1)
sys.excepthook = exception_hook
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.data_models.Config import Config
from common.core.tools.Connector import Connector
from common.gui.tools.SignalGui import SignalGui
from common.gui.windows.spec_window import SpecWindow
import common.core.tools.ErrorReporting as reporting
import common.gui.windows.spec_window as spec_module
reported = []
recoveries = []
def report(error, **kwargs):
    assert kwargs.get('gui') is True
    reported.append(kwargs['action'])
    recoveries.append(kwargs.get('recovery_action'))
reporting.report_error = report
spec_module.report_error = report
spec = EpaySpecification()
assert spec.recovery_error is not None
try:
    spec.require_ready()
except ValueError:
    pass
else:
    raise AssertionError('message processing was not blocked')
config = Config()
config.terminal.connect_on_startup = False
config.terminal.run_api = False
config.terminal.process_default_dump = os.environ['TEST_LOAD_DEFAULT'] == '1'
config.specification.backup_on_startup = False
gui = SignalGui(config)
gui._run_timer.stop()
gui.show_license_dialog = lambda: True
def unexpected_config_dump():
    raise AssertionError('configuration was dumped during recovery startup')
original_print = gui.log_printer.print_startup_info
gui.log_printer.print_startup_info = unexpected_config_dump
if not config.terminal.process_default_dump:
    def forbidden_default(*args, **kwargs):
        raise AssertionError('Default loading is disabled in configuration')
    gui.set_default_values = forbidden_default
gui.on_startup()
assert reported and callable(recoveries[0])
spec_module.QFileDialog.getOpenFileName = lambda *args, **kwargs: ('common/data/spec_backup/spec_backup_20990101_000000_12345.json', '')
def unexpected_editor(*args, **kwargs):
    raise AssertionError('Valid backup opened the specification editor')
SpecWindow.__init__ = unexpected_editor
recoveries[0]()
assert not gui._startup_waiting_for_spec
assert bool(gui.window.json_view.root.childCount()) == config.terminal.process_default_dump
from common.core.data_models.Transaction import Transaction
from common.core.data_models.EpaySpecificationModel import EpaySpecModel
assert Transaction(message_type='0200', data_fields={'4': '1'}, generate_fields=['4']).generate_fields == ['4']
EpaySpecModel(spec.filename).validate_for_use()
gui._shutting_down = True
gui.connector.stop_thread()
for widget in app.topLevelWidgets():
    widget.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
'''
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]), QT_QPA_PLATFORM='offscreen',
                       TEST_LOAD_DEFAULT='1' if load_default else '0')
    result = subprocess.run([sys.executable, '-B', '-c', script], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
    log = (tmp_path / 'common/log/signal.log').read_text(encoding='utf-8')
    assert 'Specification recovery completed successfully. Resuming normal operation.' in log
    assert 'Configuration parameters' not in log


def test_startup_recovery_keeps_editor_available(runtime, config, document, monkeypatch, tmp_path):
    from common.core.tools.EpaySpecification import EpaySpecification
    from common.gui.tools.json_views.SpecView import SpecView
    from common.gui.windows.spec_window import SpecWindow
    document['fields']['4']['min_length'] = ''
    path = tmp_path / 'broken.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    recovering = type(EpaySpecification())(str(path))
    assert recovering.recovery_error is not None
    with pytest.raises(ValueError, match='Open Tools'):
        recovering.require_ready()
    monkeypatch.setattr(SpecView, '_spec', recovering)
    monkeypatch.setattr(SpecWindow, '_spec', recovering)
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    try:
        item = window.SpecView.root.child(0)
        assert item.text(2) == ''
        item.setText(2, '1')
        window.SpecView.generate_spec().validate_for_use()
    finally:
        window.hide()
        window.deleteLater()


@pytest.mark.parametrize('number', ['', '1000', 'abc'])
def test_bad_number_is_visible_but_not_applicable(runtime, document, number):
    from common.gui.tools.spec_document import parse_spec_document
    from common.gui.tools.json_views.SpecView import SpecView
    document['fields'][number] = document['fields'].pop('4')
    view = SpecView(SimpleNamespace(read_only=False))
    try:
        view.parse_spec(parse_spec_document(json.dumps(document)))
        assert view.root.child(0).text(0) == number
        with pytest.raises(ValueError):
            view.generate_spec()
    finally:
        view.close()
        view.deleteLater()


@pytest.mark.parametrize('commit', [False, True])
def test_core_rejects_invalid_spec_without_backup_or_mutation(runtime, document, monkeypatch, commit):
    from common.core.tools.EpaySpecification import EpaySpecification
    from common.core.tools.SpecFilesRotator import SpecFilesRotator
    from common.core.data_models.EpaySpecificationModel import EpaySpecModel
    active = EpaySpecification()
    before = active.spec.model_dump()
    document['fields']['4']['description'] = 'Мама'
    monkeypatch.setattr(SpecFilesRotator, 'backup_spec', lambda self, **kwargs: pytest.fail('invalid data reached backup'))
    with pytest.raises(ValueError):
        active.reload_spec(EpaySpecModel.model_validate(document), commit)
    assert active.spec.model_dump() == before


@pytest.mark.parametrize('failure', ['backup', 'replace'])
def test_failed_save_keeps_disk_and_memory(runtime, document, monkeypatch, tmp_path, failure):
    from common.core.tools.EpaySpecification import EpaySpecification
    from common.core.tools.SpecFilesRotator import SpecFilesRotator
    from common.core.data_models.EpaySpecificationModel import EpaySpecModel
    import os
    active = EpaySpecification()
    before = active.spec.model_dump()
    path = tmp_path / 'spec.json'
    path.write_text(active.spec.model_dump_json(), encoding='utf-8')
    original = path.read_bytes()
    monkeypatch.setattr(active, 'filename', str(path))
    def fail(*args, **kwargs):
        raise OSError('simulated failure')
    monkeypatch.setattr(SpecFilesRotator, 'backup_spec', fail if failure == 'backup' else lambda self, **kwargs: 'backup.json')
    if failure == 'replace':
        monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError):
        active.reload_spec(EpaySpecModel.model_validate(document), True)
    assert path.read_bytes() == original
    assert active.spec.model_dump() == before
    assert not list(tmp_path.glob('.spec-*.tmp'))


@pytest.mark.parametrize('commit', [False, True])
def test_invalid_draft_cannot_apply_or_save_on_close(runtime, config, monkeypatch, commit):
    import common.gui.windows.spec_window as module
    from common.core.tools.EpaySpecification import EpaySpecification
    window = module.SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    before = EpaySpecification().spec.model_dump()
    item = window.SpecView.get_item_by_path(['4'])
    item.setText(0, '')
    class Unsaved(QObject):
        return_to_spec = pyqtSignal()
        save = pyqtSignal(bool)
        def accept(self):
            pass
        def exec(self):
            self.save.emit(commit)
    monkeypatch.setattr(module, 'SpecUnsaved', Unsaved)
    try:
        assert window.apply(commit) is False
        event = QCloseEvent()
        window.process_close(event)
        assert not event.isAccepted()
        assert EpaySpecification().spec.model_dump() == before
    finally:
        window.hide()
        window.deleteLater()


def test_apply_logs_each_validation_error_as_separate_record(runtime, config):
    from loguru import logger
    from common.gui.windows.spec_window import SpecWindow
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    item = window.SpecView.get_item_by_path(['4'])
    item.setText(2, '')
    item.setText(3, 'bad')
    records = []
    handler = logger.add(lambda message: records.append(message.record), level='ERROR')
    try:
        assert window.apply(False) is False
        messages = [record['message'] for record in records]
        assert all('\n' not in message and '\r' not in message for message in messages)
        assert any('Min Len' in message for message in messages)
        assert any('Max Len' in message for message in messages)
        assert all(record['time'] and record['level'].name == 'ERROR' for record in records)
    finally:
        logger.remove(handler)
        window.hide()
        window.deleteLater()


@pytest.mark.parametrize('action,closes', [('discard', True), ('cancel', False), ('escape', False), ('close', False)])
def test_unsaved_dialog_exit_choices(runtime, config, action, closes):
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from common.gui.windows.spec_window import SpecWindow
    from common.gui.windows.spec_unsaved import SpecUnsaved
    from common.core.tools.EpaySpecification import EpaySpecification
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    before = EpaySpecification().spec.model_dump()
    window.SpecView.get_item_by_path(['4']).setText(2, '')
    window.show()
    QApplication.processEvents()
    def choose():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, SpecUnsaved)
        if action == 'discard':
            QTest.mouseClick(dialog.ButtonClose, Qt.MouseButton.LeftButton)
        elif action == 'cancel':
            QTest.mouseClick(dialog.ButtonReturn, Qt.MouseButton.LeftButton)
        elif action == 'escape':
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        else:
            dialog.close()
    try:
        QTimer.singleShot(0, choose)
        window.close()
        assert window.isVisible() is not closes
        assert EpaySpecification().spec.model_dump() == before
    finally:
        window.hide()
        window.deleteLater()


def test_apply_checks_editor_text_not_previous_committed_value(runtime, config):
    from common.gui.windows.spec_window import SpecWindow
    from PyQt6.QtWidgets import QApplication, QLineEdit
    from common.core.tools.EpaySpecification import EpaySpecification
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    window.show()
    QApplication.processEvents()
    before = EpaySpecification().spec.model_dump()
    window.set_read_only(False)
    item = window.SpecView.get_item_by_path(['4'])
    window.SpecView.editItem(item, 2)
    editor = QApplication.focusWidget()
    assert isinstance(editor, QLineEdit)
    try:
        editor.setText('')
        assert window.apply(False) is False
        assert item.text(2) == ''
        assert EpaySpecification().spec.model_dump() == before
    finally:
        window.hide()
        window.deleteLater()


def test_file_and_http_load_same_draft_and_rejected_import_preserves_it(runtime, config, document, tmp_path, monkeypatch):
    from common.gui.windows.spec_window import SpecWindow
    import common.gui.windows.spec_window as module
    reported = []
    monkeypatch.setattr(module, 'report_error', lambda error, **kwargs: reported.append(error))
    from common.core.tools.EpaySpecification import EpaySpecification
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    before = EpaySpecification().spec.model_dump()
    document['fields']['4']['max_length'] = ''
    path = tmp_path / 'incoming.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    try:
        window.parse_file(str(path))
        file_snapshot = window.SpecView.draft_snapshot()
        window.process_remote_spec(json.dumps(document))
        assert window.SpecView.draft_snapshot() == file_snapshot
        window.process_remote_spec('{"fields": []}')
        assert len(reported) == 1
        assert window.SpecView.draft_snapshot() == file_snapshot
        assert EpaySpecification().spec.model_dump() == before
    finally:
        window.hide()
        window.deleteLater()
