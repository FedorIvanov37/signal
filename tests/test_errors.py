import asyncio
import importlib
import runpy
import sys
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("level", ["ERROR", "WARNING", "INFO", "DEBUG"])
def test_error_trace_is_debug_only(runtime, level):
    from loguru import logger
    from common.core.tools.ErrorReporting import report_error
    from common.core.exceptions.exceptions import DataFileError
    messages = []
    sink = logger.add(messages.append, level=level, format="{message}")
    try:
        try:
            raise ValueError("private input")
        except ValueError as cause:
            try:
                raise DataFileError("config.json", "load", "invalid JSON") from cause
            except DataFileError as error:
                report_error(error)
    finally:
        logger.remove(sink)
    error_records = [m.record for m in messages if m.record["level"].name == "ERROR"]
    assert len(error_records) == 1
    assert error_records[0]["message"] == "Signal error: Cannot load file 'config.json': invalid JSON"
    assert error_records[0]["exception"] is None
    output = "".join(messages)
    assert ("test_error_trace_is_debug_only" in output) is (level == "DEBUG")
    assert ("Cause type: ValueError" in output) is (level == "DEBUG")
    assert "private input" not in output


def test_logging_failure_fallback_omits_trace(runtime, monkeypatch, capsys):
    reporting = importlib.import_module("common.core.tools.ErrorReporting")
    monkeypatch.setattr(reporting, "log_error", Mock(side_effect=RuntimeError("logger unavailable")))
    try:
        raise ValueError("invalid configuration")
    except ValueError as error:
        reporting.report_error(error)
    output = capsys.readouterr().err
    assert output == "Signal error: invalid configuration\n"


@pytest.mark.parametrize("error", [PermissionError("denied"), FileNotFoundError("missing")])
def test_config_read_has_context_and_cause(runtime, monkeypatch, error):
    from common.core.exceptions.exceptions import DataFileError
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=error))
    with pytest.raises(DataFileError) as caught:
        runtime.Config("config.json")
    assert caught.value.path == "config.json"
    assert caught.value.__cause__ is error


@pytest.mark.parametrize("content", ['{"host":', '{"host":{"port":"secret-invalid-value"}}'])
def test_bad_config_does_not_expose_contents(runtime, tmp_path, content):
    from common.core.exceptions.exceptions import DataFileError
    path = tmp_path / "config.json"
    path.write_text(content)
    with pytest.raises(DataFileError) as caught:
        runtime.Config(path)
    assert "secret-invalid-value" not in str(caught.value)
    assert str(path) in str(caught.value)


@pytest.mark.parametrize("stage", ["create", "replace", "flush"])
def test_failed_save_preserves_file(runtime, config, tmp_path, monkeypatch, stage):
    store = importlib.import_module("common.core.tools.ConfigStore")
    from common.core.exceptions.exceptions import DataFileError
    path = tmp_path / "config.json"
    path.write_text("original")
    if stage == "create":
        monkeypatch.setattr(store.tempfile, "NamedTemporaryFile", Mock(side_effect=PermissionError("denied")))
    else:
        monkeypatch.setattr(store.os, "replace" if stage == "replace" else "fsync",
                            Mock(side_effect=OSError("write failed")))
    with pytest.raises(DataFileError):
        store.save_config(config, path)
    assert path.read_text() == "original"
    assert list(tmp_path.iterdir()) == [path]


def test_save_validates_mutated_config(runtime, config, tmp_path):
    from common.core.tools.ConfigStore import save_config
    from common.core.exceptions.exceptions import DataFileError
    path = tmp_path / "config.json"
    path.write_text("original")
    config.host.port = 999999
    with pytest.raises(DataFileError):
        save_config(config, path)
    assert path.read_text() == "original"


def test_successful_save_round_trip(runtime, config, tmp_path):
    from common.core.tools.ConfigStore import save_config
    path = tmp_path / "config.json"
    config.host.port = 12345
    save_config(config, path)
    assert runtime.Config(path).host.port == 12345


def test_terminal_failed_reload_preserves_config(runtime, config, monkeypatch):
    module = importlib.import_module("common.core.tools.Terminal")
    from common.core.exceptions.exceptions import DataFileError
    from common.core.tools.ConfigManager import ConfigManager
    receiver = SimpleNamespace(config=config, config_manager=ConfigManager(config), update_config=Mock())
    monkeypatch.setattr(module, "Config", Mock(side_effect=DataFileError("config.json", "read", "denied")))
    with pytest.raises(DataFileError):
        module.Terminal.read_config(receiver)
    assert receiver.config is config


def test_failed_apply_restores_config_and_file(runtime, config, tmp_path):
    from common.core.tools.Terminal import Terminal
    from common.core.tools.ConfigManager import ConfigManager
    from common.core.exceptions.exceptions import SignalError
    path = tmp_path / "config.json"
    candidate = config.model_copy(deep=True)
    candidate.host.port = 12345
    manager = ConfigManager(config, path)
    def apply(old, new):
        if new.host.port == 12345:
            raise RuntimeError("apply failed")
    manager.subscribe(apply)
    receiver = SimpleNamespace(config=manager.view, config_manager=manager)
    with pytest.raises(SignalError, match="restored"):
        Terminal.update_config(receiver, candidate)
    assert receiver.config.host.port == config.host.port
    assert runtime.Config(path).host.port == config.host.port


def test_settings_write_denial_keeps_dialog_and_active_config(runtime, config, monkeypatch):
    from common.gui.windows.settings_window import SettingsWindow
    from common.core.exceptions.exceptions import DataFileError
    reporting = importlib.import_module("common.core.tools.ErrorReporting")
    report = Mock()
    monkeypatch.setattr(reporting, "report_error", report)
    commit = Mock(side_effect=DataFileError("config.json", "save", "access denied"))
    window = SettingsWindow(config, commit=commit)
    accepted = Mock()
    window.accepted.connect(accepted)
    old_port = config.host.port
    window.SvPort.setValue(12345)
    window.ok()
    assert config.host.port == old_port
    assert not accepted.called
    assert report.called
    window.close()


@pytest.mark.parametrize("gui", [True, False])
def test_startup_config_denial_is_reported(runtime, monkeypatch, gui):
    source = Path(__file__).resolve().parents[1] / "common/signal.py"
    from common.core.exceptions.exceptions import DataFileError
    module = importlib.import_module("common.core.data_models.Config")
    reporting = importlib.import_module("common.core.tools.ErrorReporting")
    report = Mock()
    monkeypatch.setattr(reporting, "report_error", report)
    monkeypatch.setattr(module, "Config", Mock(side_effect=DataFileError("config.json", "read", "access denied")))
    monkeypatch.setattr(sys, "argv", ["Signal.py"] if gui else ["Signal.py", "--console"])
    previous = sys.excepthook
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(source), run_name="signal_launch_test")
    assert caught.value.code == 100
    assert report.call_args.kwargs["gui"] is gui
    assert sys.excepthook is previous


def test_parser_error_reaches_queue_notification(runtime, config):
    from common.core.tools.TransactionQueue import TransactionQueue
    queue = TransactionQueue(runtime.Connector(config))
    errors = []
    queue.parsing_error.connect(errors.append)
    body = b"0800" + bytes.fromhex("2000000000000000") + b"123"
    queue.receive_transaction_data(len(body).to_bytes(2, "big") + body)
    assert len(errors) == 1 and "field 3" in errors[0]
    assert not queue.queue


def test_outgoing_parse_failure_notifies_request(runtime, config, monkeypatch):
    from common.core.tools.TransactionQueue import TransactionQueue
    queue = TransactionQueue(runtime.Connector(config))
    failed = []
    queue.socket_error.connect(failed.append)
    monkeypatch.setattr(runtime.Parser, "create_dump", Mock(side_effect=ValueError("bad field")))
    request = runtime.Transaction(message_type="0800", data_fields={"70": "301"})
    queue.put_transaction(request)
    assert failed == [request]
    assert request.success is False and "bad field" in request.error


@pytest.mark.parametrize("expected", [True, False])
def test_qt_api_error_completes_pending_future(runtime, config, expected):
    from PyQt6.QtCore import QObject
    from common.api.tools.Api import Api
    from common.api.tools.SignalApi import SignalApi
    from common.api.data_models.ApiRequests import ApiRequest
    from common.api.exceptions.TerminalApiError import TerminalApiError
    from common.core.exceptions.exceptions import DataFileError
    backend = SignalApi.__new__(SignalApi)
    QObject.__init__(backend)
    backend.config = config
    backend.lock = Lock()
    backend.api_tasks = {}
    error = DataFileError("config.json", "save", "denied") if expected else RuntimeError("private details")
    backend._process_api_call = Mock(side_effect=error)
    api = Api.__new__(Api)
    QObject.__init__(api)
    api.backend = backend
    api.pending_jobs = {}
    api.api_request.connect(backend.process_api_call)
    backend.terminal_response.connect(api.process_backend_response)
    async def scenario():
        api._loop = asyncio.get_running_loop()
        with pytest.raises(TerminalApiError) as caught:
            await asyncio.wait_for(api.backend_request(ApiRequest(request_id="test")), 1)
        assert caught.value.http_status == 500
        assert "private details" not in str(caught.value.detail)
        assert not api.pending_jobs
    asyncio.run(scenario())


def test_new_transaction_format_still_detected(runtime, tmp_path):
    from common.core.tools.JsonConverter import JsonConverter
    path = tmp_path / "transaction.json"
    content = '{"message_type":"0800","data_fields":{"70":"301"}}'
    path.write_text(content)
    assert JsonConverter.get_transaction_model(path) is runtime.Transaction
    assert path.read_text() == content


def test_gui_error_uses_visible_dialog(runtime, monkeypatch):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from common.gui.windows.error_dialog import ErrorDialog
    from common.gui.tools.ErrorPresentation import show_error
    import common.core.tools.ErrorReporting as reporting
    monkeypatch.setattr(reporting, '_gui_error_handler', show_error)
    from common.core.tools.ErrorReporting import report_error
    from common.core.exceptions.exceptions import DataFileError
    messages = []
    def close_dialog():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ErrorDialog)
        messages.append(dialog.message.text())
        dialog.accept()
    QTimer.singleShot(0, close_dialog)
    report_error(DataFileError("config.json", "read", "access denied"), gui=True)
    assert len(messages) == 1
    assert "config.json" in messages[0]


def test_cli_error_uses_stderr(runtime, capsys):
    from common.core.tools.ErrorReporting import report_error
    from common.core.exceptions.exceptions import DataFileError
    report_error(DataFileError("config.json", "read", "access denied"))
    assert "config.json" in capsys.readouterr().err


@pytest.mark.parametrize("expected", [True, False])
def test_http_boundary_returns_error_response(runtime, config, monkeypatch, tmp_path, expected):
    from fastapi.testclient import TestClient
    from common.api.tools.Api import Api
    from common.core.exceptions.exceptions import SignalError
    from common.gui.tools.ResourcePath import ResourcePath
    monkeypatch.setattr(ResourcePath, "resource_path", staticmethod(lambda path: str(tmp_path)))
    api = Api(SimpleNamespace(config=config, terminal_response=Mock()))
    @api.app.get("/failure-test")
    def fail():
        if expected:
            raise SignalError("Operation unavailable")
        raise RuntimeError("private details")
    with TestClient(api.app, raise_server_exceptions=False) as client:
        response = client.get("/failure-test")
    assert response.status_code == 500
    assert response.headers["X-Request-ID"]
    assert "private details" not in response.text


def test_cli_emergency_hook_requests_clean_exit(runtime, monkeypatch):
    module = importlib.import_module("common.core.tools.ErrorReporting")
    from PyQt6.QtCore import QCoreApplication
    report = Mock()
    exit_app = Mock()
    monkeypatch.setattr(module, "report_error", report)
    monkeypatch.setattr(QCoreApplication, "exit", exit_app)
    previous = module.install_exception_hook()
    try:
        error = RuntimeError("callback failed")
        sys.excepthook(type(error), error, None)
        assert report.called
        exit_app.assert_called_once_with(100)
    finally:
        sys.excepthook = previous


def test_gui_exception_hook_allows_next_action(runtime, monkeypatch):
    module = importlib.import_module("common.core.tools.ErrorReporting")
    from PyQt6.QtCore import QCoreApplication, QTimer
    from PyQt6.QtWidgets import QPushButton
    report = Mock()
    exit_app = Mock()
    next_action = Mock()
    monkeypatch.setattr(module, "report_error", report)
    monkeypatch.setattr(QCoreApplication, "exit", exit_app)
    button = QPushButton()

    def fail():
        raise RuntimeError("callback failed")

    button.clicked.connect(fail)
    previous = module.install_exception_hook(gui=True)
    try:
        button.click()
        report.assert_called_once()
        exit_app.assert_not_called()
        button.clicked.disconnect(fail)
        button.clicked.connect(next_action)
        QTimer.singleShot(0, button.click)
        runtime.app.processEvents()
        next_action.assert_called_once()
        exit_app.assert_not_called()
    finally:
        sys.excepthook = previous
        button.deleteLater()


def test_generator_failure_uses_transaction_error_channel(runtime, config):
    from common.core.tools.Terminal import Terminal
    from common.core.tools.TransactionQueue import TransactionQueue
    queue = TransactionQueue(runtime.Connector(config))
    failed = []
    queue.socket_error.connect(failed.append)
    request = runtime.Transaction(message_type="0800", data_fields={"70": "301"}, generate_fields=["11"])
    receiver = SimpleNamespace(spec=queue.spec, trans_queue=queue, generator=SimpleNamespace(
        set_generated_fields=Mock(side_effect=KeyError("missing generator field"))))
    Terminal.send(receiver, request)
    assert failed == [request]
    assert request.success is False


def test_successful_config_apply_publishes_candidate(runtime, config, tmp_path):
    from common.core.tools.Terminal import Terminal
    from common.core.tools.ConfigManager import ConfigManager
    path = tmp_path / "config.json"
    candidate = config.model_copy(deep=True)
    candidate.host.port = 12345
    manager = ConfigManager(config, path)
    receiver = SimpleNamespace(config=manager.view, config_manager=manager)
    Terminal.update_config(receiver, candidate)
    assert receiver.config.host.port == 12345
    assert runtime.Config(path).host.port == 12345
    assert config.host.port != 12345
