import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("stage", ["connection", "response", "interval"])
def test_ctrl_c_during_native_connection_error_exits_cleanly(runtime, stage):
    # Deliver SIGINT from the real Qt socket error callback while
    # waitForConnected is on the stack; use a child so SystemExit cannot kill pytest.
    import shutil
    shutil.copytree(Path(__file__).resolve().parents[1] / 'common/data/default', Path('common/data/default'), dirs_exist_ok=True)
    script = r'''
import signal
import socket
import sys
from pathlib import Path
Path('common/data/static').mkdir(parents=True, exist_ok=True)
from PyQt6.QtCore import QCoreApplication
from common.core.data_models.Config import Config
from common.cli.tools.SignalCli import SignalCli

with socket.socket() as reserve:
    reserve.bind(('127.0.0.1', 0))
    port = reserve.getsockname()[1]
sys.argv = ['Signal.py', '-c', '--default', '--repeat', '--interval', '2']
SignalCli.show_license_dialog = lambda self: None
config = Config()
config.host.host = '127.0.0.1'
config.host.port = port
cli = SignalCli(config)
if TEST_STAGE == 'connection':
    cli.connector.errorOccurred.connect(lambda error: signal.raise_signal(signal.SIGINT))
else:
    def send(transaction):
        from datetime import datetime
        transaction.sending_time = datetime.now()
        transaction.matched = TEST_STAGE == 'interval'
    cli.send = send
    original_wait = cli.wait
    def interrupt_wait(seconds):
        signal.raise_signal(signal.SIGINT)
        original_wait(seconds)
    cli.wait = interrupt_wait
status = cli.run_application()
assert cli.connector.state() == cli.connector.SocketState.UnconnectedState
assert not cli.run_timer.isActive()
assert not cli.api_timer.isActive()
print('CLEAN_SHUTDOWN', status)
sys.exit(status)
'''
    script = script.replace('TEST_STAGE', repr(stage))
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run([sys.executable, '-B', '-c', script], env=env,
                            capture_output=True, text=True, timeout=25)
    output = result.stdout + result.stderr
    assert result.returncode == 130, output
    assert 'CLEAN_SHUTDOWN 130' in output
    assert 'TypeError' not in output
    assert 'Traceback' not in output
    assert output.count('Finish command line job') == 1
    lines = result.stdout[:result.stdout.index('CLEAN_SHUTDOWN')].rstrip().splitlines()
    assert 'Finish command line job' in lines[-1]
