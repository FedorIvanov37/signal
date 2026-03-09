from pathlib import Path
from common.gui.core.SignalGui import SignalGui
from common.lib.data_models.Config import Config
from common.lib.enums.TermFilesPath import TermFilesPath


def run_signal_gui() -> int:
    config: Config = Config.model_validate_json(Path(TermFilesPath.CONFIG).read_text())
    terminal: SignalGui = SignalGui(config)
    status: int = terminal.run()

    return status  # Exit status
