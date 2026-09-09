import PyInstaller.__main__
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

PyInstaller.__main__.run(
    [
        str(ROOT / "Signal.py"),
        "--name=signal.exe",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--hide-console=hide-early",
        f"--icon={ROOT / 'common/data/style/logo_triangle.ico'}",
        f"--distpath={ROOT}",
        "--log-level=INFO",
        f"--manifest={ROOT / 'signal.exe.manifest'}",
        "--add-data=common/data/style;common/data/style",
        "--add-data=common/doc;common/doc"
    ]
)
