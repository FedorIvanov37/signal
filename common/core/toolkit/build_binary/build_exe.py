"""Build signal.exe into common/bin without assembling or running a release.

Usage: python common/core/toolkit/build_binary/build_exe.py
The command can run from any working directory. Install the application
requirements and PyInstaller in the Python environment used for this script.
The adjacent signal.exe.manifest is required and embedded in the executable.
Intermediate files use system Temp and are removed on exit. A successful build replaces
common/bin/signal.exe. Runtime configuration/specification files are not copied;
the binary must not be launched from common/bin.
Bundled settings are prepared from defaults in Temp; active settings and layout
files are never reset. External configuration still takes precedence at runtime.
"""
import os
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
MANIFEST = Path(__file__).with_name('signal.exe.manifest')
OUTPUT = ROOT / 'common/bin/signal.exe'



def prepare_build_data(build):
    """Prepare defaults without touching the active installation's settings."""
    data = build / 'data'
    settings = data / 'settings'
    settings.mkdir(parents=True)
    defaults = json.loads((ROOT / 'common/data/settings/default_config.json').read_text(encoding='utf-8-sig'))
    # Match Reset theme: white table/base and the default blue console.
    defaults['theme'] = dict(treeColor='#F0F0F0', windowColor='#F0F0F0', consoleColor='#012E4F')
    for name in ('config.json', 'default_config.json'):
        (settings / name).write_text(json.dumps(defaults, indent=4) + '\n', encoding='utf-8')
    shutil.copytree(ROOT / 'common/data/style', data / 'style',
                    ignore=shutil.ignore_patterns('appearance.json', 'appearance.ini',
                                                  'panel_layout.ini', '*.tmp'))
    return data


def build_binary(output):
    """Build fresh code into the explicit destination; never launch it."""
    output = Path(output).resolve()
    for resource in (ROOT / 'Signal.py', MANIFEST,
                     ROOT / 'common/data/style/logo_triangle.ico'):
        if not resource.is_file():
            raise FileNotFoundError(resource)
    for directory in ('common/data/style', 'common/data/static'):
        if not (ROOT / directory).is_dir():
            raise FileNotFoundError(ROOT / directory)

    with tempfile.TemporaryDirectory(prefix='signal-build-') as temporary_build:
        build = Path(temporary_build)
        build_data = prepare_build_data(build)
        windows = Path(os.environ.get('SystemRoot', r'C:\Windows'))
        previous_path = os.environ.get('PATH', '')
        previous_cwd = Path.cwd()
        try:
            # Avoid DLLs from unrelated tools (for example Poppler's ICU libraries).
            os.environ['PATH'] = os.pathsep.join(map(str, (
                windows / 'System32', windows, Path(sys.executable).parent,
                Path(sys.executable).parent / 'Scripts')))
            os.chdir(ROOT)
            import PyInstaller.__main__
            PyInstaller.__main__.run([
                str(ROOT / 'Signal.py'), '--name=signal', '--noconfirm', '--clean', '--onefile',
                '--hide-console=hide-early',
                f'--icon={ROOT / "common/data/style/logo_triangle.ico"}',
                f'--manifest={MANIFEST}',
                f'--distpath={build / "dist"}', f'--workpath={build / "work"}',
                f'--specpath={build}', f'--paths={ROOT}', '--log-level=INFO',
                f'--add-data={build_data / "style"};common/data/style',
                f'--add-data={build_data / "settings"};common/data/settings',
                f'--add-data={ROOT / "common/data/static"};common/data/static',
            ])
            binary = build / 'dist/signal.exe'
            if not binary.is_file() or binary.stat().st_size == 0:
                raise RuntimeError('PyInstaller did not produce signal.exe')
            output.parent.mkdir(parents=True, exist_ok=True)
            # The temporary and final files share a directory for atomic replacement.
            with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copyfile(binary, temporary)
                temporary.replace(output)
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            os.environ['PATH'] = previous_path
            os.chdir(previous_cwd)
        print(f'Binary ready: {output}')
        print('Not launched. Runtime data must be provided separately.')


def main():
    build_binary(OUTPUT)


if __name__ == '__main__':
    main()
