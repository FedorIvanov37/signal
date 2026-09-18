"""A checkout without personal config must support the documented entry points."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode', ['cli', 'explicit-missing', 'emulator'])
def test_source_checkout_without_personal_config(tmp_path, mode):
    root = Path(__file__).resolve().parents[1]
    for directory in ('settings', 'dictionary'):
        shutil.copytree(root / 'common/data' / directory, tmp_path / 'common/data' / directory)
    (tmp_path / 'common/data/static').mkdir(parents=True)
    active = tmp_path / 'common/data/settings/config.json'
    active.unlink(missing_ok=True)
    if mode == 'emulator':
        code = ('from common.core.toolkit.sv_emulator import SvEmulator, IsoConfig; '
                'e = SvEmulator(IsoConfig()); assert e.config.theme.windowColor == "#F0F0F0"')
        args = ['-c', code]
    else:
        args = [str(root / 'Signal.py'), '--console', '--help']
        if mode == 'explicit-missing':
            args += ['--config-file', 'missing-config.json']
    result = subprocess.run([sys.executable, '-B', *args], cwd=tmp_path,
                            env=dict(os.environ, PYTHONPATH=str(root), QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, timeout=30)
    assert result.returncode == (100 if mode == 'explicit-missing' else 0), result.stdout + result.stderr
    assert not active.exists()
