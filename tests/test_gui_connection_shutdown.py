from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PyQt6 import sip
from PyQt6.QtNetwork import QTcpSocket


def test_global_menu_filter_ignores_events_after_children_deleted(runtime, config):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtWidgets import QWidget
    from common.gui.windows.main_window import MainWindow
    window = MainWindow(config)
    watched = QWidget()
    sip.delete(window.ButtonTools)
    sip.delete(window.main_splitter)
    for event_type in (QEvent.Type.ChildRemoved, QEvent.Type.Show, QEvent.Type.Leave):
        assert not window.eventFilter(watched, QEvent(event_type))
    window.deleteLater()
    watched.deleteLater()

@pytest.mark.parametrize('closing', [False, True])
@pytest.mark.parametrize('state', [QTcpSocket.SocketState.ConnectingState, QTcpSocket.SocketState.UnconnectedState])
def test_status_after_connector_deleted(runtime, config, closing, state):
    from common.gui.tools.SignalGui import SignalGui
    socket = runtime.Connector(config)
    sip.delete(socket)
    host = SimpleNamespace(_shutting_down=closing, connector=socket, window=Mock())
    SignalGui.set_connection_status(host, state)
    if closing:
        assert not host.window.mock_calls
    else:
        host.window.set_connection_status.assert_called_once_with(state)
        if state == QTcpSocket.SocketState.ConnectingState:
            host.window.block_connection_buttons.assert_called_once()
        else:
            host.window.unblock_connection_buttons.assert_called_once()

@pytest.mark.parametrize('mode', ['reject', 'close'])
def test_gui_process_exits_cleanly(runtime, tmp_path, mode):
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = str(Path(__file__).resolve().parents[1])
    Path('common/data/static').mkdir(parents=True, exist_ok=True)
    script = '''
import sys
sys.path.insert(0, ROOT)
from PyQt6.QtCore import QTimer
from common.gui.tools.SignalGui import SignalGui
from common.gui.windows.license_window import LicenseWindow
from common.core.data_models.Config import Config
from common.core.data_models.License import LicenseInfo
import common.gui.windows.license_window as lm
lm.LicenseInfo = lambda *args: LicenseInfo()
LicenseWindow.save_license_file = staticmethod(lambda data: None)
original = LicenseWindow._setup
def setup(self):
    original(self)
    QTimer.singleShot(0, self.reject)
LicenseWindow._setup = setup
config = Config()
config.terminal.show_license_dialog = True
config.specification.backup_on_shutdown = False
if MODE == 'close':
    def startup(self):
        self.window.show()
        QTimer.singleShot(0, self.window.close)
    SignalGui.on_startup = startup
gui = SignalGui(config)
result = gui.run_application()
assert not gui.connector.thread.isRunning()
print('CLEAN_EXIT', result, flush=True)
sys.exit(result)
'''.replace('ROOT', repr(root)).replace('MODE', repr(mode))
    result = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True, text=True, timeout=20,
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
    assert result.returncode == 0, result.stderr
    assert 'CLEAN_EXIT 0' in result.stdout
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize('target', ['window', 'ConnectionStatus', 'ConnectionStatusLabel'])
def test_late_status_after_widget_deleted(runtime, config, target):
    from common.gui.tools.SignalGui import SignalGui
    from common.gui.windows.main_window import MainWindow
    window = MainWindow(config)
    host = SimpleNamespace(_shutting_down=False, window=window)
    sip.delete(window if target == 'window' else getattr(window, target))
    SignalGui.set_connection_status(host, QTcpSocket.SocketState.UnconnectedState)
    assert host._shutting_down
    if not sip.isdeleted(window):
        window.deleteLater()
