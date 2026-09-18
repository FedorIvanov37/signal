import importlib
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="session")
def runtime(tmp_path_factory):
    """Load real project modules using disposable copies of their data files."""
    root = Path(__file__).resolve().parents[1]
    directory = tmp_path_factory.mktemp("signal")
    for name in ("settings", "dictionary"):
        shutil.copytree(root / "common/data" / name, directory / "common/data" / name)
    shutil.copyfile(directory / "common/data/settings/default_config.json",
                    directory / "common/data/settings/config.json")
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(directory)
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from common.core.data_models.Config import Config
        from common.core.data_models.Transaction import Transaction
        from common.core.tools.Connector import Connector
        from common.core.tools.Parser import Parser
        from common.core.toolkit.sv_emulator import SvEmulator, IsoConfig

        app = QApplication.instance() or QApplication([])
        yield SimpleNamespace(app=app, Config=Config, Transaction=Transaction,
                              Connector=Connector, Parser=Parser,
                              SvEmulator=SvEmulator, IsoConfig=IsoConfig)
        # Destroy widgets while QApplication and Python callbacks still exist.
        # Leaving hidden windows to interpreter teardown can crash native Qt.
        from PyQt6.QtCore import QCoreApplication, QEvent, QTimer
        from loguru import logger
        logger.remove()
        for widget in app.topLevelWidgets():
            for timer in widget.findChildren(QTimer):
                timer.stop()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def config(runtime, monkeypatch):
    config = runtime.Config()
    config.host.header_length = 2
    config.host.header_length_exists = True
    module = importlib.import_module("common.core.tools.Parser")
    monkeypatch.setattr(module, "Config", lambda *args, **kwargs: config)
    return config
