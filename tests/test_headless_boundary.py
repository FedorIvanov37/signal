"""Exercise backend initialization with GUI imports explicitly forbidden."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_api_and_terminal_without_gui(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for name in ('settings', 'dictionary'):
        shutil.copytree(root / 'common/data' / name, tmp_path / 'common/data' / name)
    shutil.copyfile(tmp_path / 'common/data/settings/default_config.json',
                    tmp_path / 'common/data/settings/config.json')
    (tmp_path / 'common/data/static').mkdir(parents=True)
    script = '''
import importlib.abc
import sys
class NoGui(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'common.gui' or fullname.startswith(('common.gui.', 'PyQt6.QtWidgets', 'PyQt6.QtGui')):
            raise AssertionError('GUI dependency: ' + fullname)
sys.meta_path.insert(0, NoGui())
from common.core.data_models.Config import Config
from common.core.tools.Terminal import Terminal
from common.api.tools.SignalApi import SignalApi
from common.cli.tools.SignalCli import SignalCli
from PyQt6.QtCore import QCoreApplication
from fastapi.testclient import TestClient
from loguru import logger
terminal = Terminal(Config())
assert type(terminal.pyqt_application) is QCoreApplication
backend = SignalApi(terminal.config, terminal)
with TestClient(backend.api.app) as client:
    response = client.get('/openapi.json')
    assert response.status_code == 200, response.text
    assert response.json()['paths']
    for route in ('/api/config', '/api/connection', '/api/transactions'):
        response = client.get(route)
        assert response.status_code == 200, response.text
terminal.keep_alive_timer._trans_loop_timer.stop()
terminal.connector.abort()
logger.remove()
'''
    env = dict(os.environ, PYTHONPATH=str(root))
    result = subprocess.run([sys.executable, '-B', '-c', script], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
