"""Capture Python thread stacks if the GUI stops processing events."""
import faulthandler
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer
from common.core.enums.TermFilesPath import TermDirs


class GuiWatchdog(QObject):
    def __init__(self, app):
        super().__init__(app)
        path = Path(TermDirs.LOG_DIR) / 'gui-freeze.log'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a', encoding='utf-8')
        self.stream.write(f'\nGUI monitoring started {datetime.now().isoformat()}\n')
        self.stream.flush()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.heartbeat)
        app.aboutToQuit.connect(self.stop)
        self.heartbeat()
        self.timer.start()

    def heartbeat(self):
        # Native faulthandler timer can capture even when Python's GIL is held.
        faulthandler.dump_traceback_later(10, file=self.stream, repeat=False)

    def stop(self):
        self.timer.stop()
        faulthandler.cancel_dump_traceback_later()
        if not self.stream.closed:
            self.stream.close()

    @classmethod
    def install(cls, app):
        if not hasattr(app, '_gui_watchdog'):
            try:
                app._gui_watchdog = cls(app)
            except OSError:
                # Diagnostic file access must not prevent application startup.
                return
        return app._gui_watchdog
