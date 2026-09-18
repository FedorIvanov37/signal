"""Assemble a Signal distribution with a freshly built binary.

Usage: python common/core/toolkit/build_binary/build_release.py
Output: dist/Signal_<version>.zip, with signal.exe at the archive root.
The layout follows the v0.20 distribution: release_info.txt, postman, and
common/{data,doc,log,src}. README.md belongs only to common/src.
Settings use default_config.json with the current config theme.
Temporary staging is removed automatically. Active settings are never changed.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from build_exe import prepare_build_data, build_binary

ROOT = Path(__file__).resolve().parents[4]
CODE_DIRS = ('api', 'cli', 'core', 'gui', 'lib')
CODE_SUFFIXES = {'.py', '.ui', '.manifest', '.qrc', '.qss', '.css', '.cpp', '.h', '.pro'}
EXCLUDED_DIRS = {'__pycache__', '.pytest_cache', '.git', '.idea', 'build', 'dist'}


def release_version(root):
    tree = ast.parse((root / 'common/core/enums/ReleaseDefinition.py').read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets):
            version = ast.literal_eval(node.value)
            if re.fullmatch(r'v\d+(?:\.\d+)+', version):
                return version
    raise ValueError('ReleaseDefinition.VERSION is missing or invalid')


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_resources(source, target):
    for path in source.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(source)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in {'.pyc', '.pyo', '.tmp', '.log'}:
            continue
        if path.name in {'appearance.json', 'appearance.ini', 'panel_layout.ini', 'license_info.json'}:
            continue
        copy_file(path, target / relative)


def release_notes_markdown(root, version):
    guide = (root / 'common/doc/signal_user_guide.md').read_text(encoding='utf-8-sig')
    match = re.search(r'^### Signal ' + re.escape(version) + r'\s*\n(.*?)(?=^#{1,3} |\Z)', guide, re.M | re.S)
    if not match:
        raise ValueError(f'Release notes for {version} not found in the guide')
    return match[1].strip()


def update_docs_release_info(root, version):
    """Update the sibling documentation project, retaining other release sections."""
    target = root.parent / 'signal.docs/docs/general/release-info.md'
    if not target.is_file():
        print(f'Documentation release notes skipped: {target} does not exist')
        return
    current = target.read_text(encoding='utf-8-sig')
    section = f'## Signal {version} release info\n\n' + release_notes_markdown(root, version) + '\n'
    pattern = re.compile(r'^## Signal ' + re.escape(version) + r' release info[^\n]*\n.*?(?=^#{1,2} |\Z)', re.M | re.S)
    updated = pattern.sub(lambda match: section + '\n', current, count=1) if pattern.search(current) else section + '\n' + current
    target.write_text(updated.rstrip() + '\n', encoding='utf-8')
    print(f'Documentation release notes updated: {target}')


def assemble(root, stage, defaults, version, binary):
    if not binary.is_file() or binary.stat().st_size == 0:
        raise FileNotFoundError('Fresh release binary was not produced')
    copy_file(binary, stage / 'signal.exe')
    data = stage / 'common/data'
    for directory in ('api_transactions', 'default', 'dictionary', 'postman', 'static'):
        copy_resources(root / 'common/data' / directory, data / directory)
    copy_resources(defaults / 'style', data / 'style')
    for name in ('config.json', 'default_config.json'):
        copy_file(defaults / 'settings' / name, data / 'settings' / name)
    copy_file(root / 'common/data/settings/specification.json', data / 'settings/specification.json')
    copy_file(root / 'common/data/license/agreement.txt', data / 'license/agreement.txt')
    (data / 'spec_backup').mkdir(parents=True)
    (stage / 'common/log').mkdir(parents=True)
    copy_file(root / 'common/doc/signal_user_guide.html', stage / 'common/doc/signal_user_guide.html')
    postman = root / 'common/postman' / f'Signal_{version}_postman_collection.zip'
    copy_file(postman, stage / 'postman' / postman.name)

    markdown = release_notes_markdown(root, version)
    plain = []
    for line in markdown.splitlines():
        heading = re.fullmatch(r'\s*\* \*\*(.+?)\*\*\s*', line)
        if heading:
            plain.append(heading[1] + ':')
            continue
        line = re.sub(r'^\s*[*+-]\s+', '  \u2022 ', line)
        line = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'\1 (\2)', line)
        plain.append(line.replace('**', '').replace('`', '').rstrip())
    notes = f'Signal {version}\nhttps://signal.iso8583.tech/\n\n' + '\n'.join(plain) + '\n'
    (stage / 'release_info.txt').write_text(notes, encoding='utf-8')

    src = stage / 'common/src'
    for name in ('Signal.py', 'requirements.txt', 'README.md'):
        copy_file(root / name, src / name)
    copy_file(stage / 'release_info.txt', src / 'release_info.txt')
    copy_file(root / 'common/signal.py', src / 'common/signal.py')
    for directory in CODE_DIRS:
        for path in (root / 'common' / directory).rglob('*'):
            if not path.is_file() or path.is_symlink() or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            copy_file(path, src / relative)
    # Runtime resources in the source package are the same clean defaults.
    shutil.copytree(data, src / 'common/data')
    shutil.copytree(stage / 'common/doc', src / 'common/doc')
    copy_file(root / 'common/doc/signal_user_guide.md', src / 'common/doc/signal_user_guide.md')
    shutil.copytree(stage / 'postman', src / 'postman')
    shutil.copytree(stage / 'postman', src / 'common/postman')
    for path in (root / 'common/scripts').glob('*.cmd'):
        copy_file(path, src / 'common/scripts' / path.name)
    (src / 'common/log').mkdir(parents=True)
    verify_stage(stage, defaults)


def verify_stage(stage, defaults):
    assert {p.name for p in stage.iterdir()} == {'signal.exe', 'release_info.txt', 'postman', 'common'}
    assert {p.name for p in (stage / 'common').iterdir()} == {'data', 'doc', 'log', 'src'}
    assert not (stage / 'README.md').exists()
    assert (stage / 'common/src/README.md').is_file()
    for base in (stage, stage / 'common/src'):
        for name in ('config.json', 'default_config.json'):
            assert (base / 'common/data/settings' / name).read_bytes() == (defaults / 'settings' / name).read_bytes()
        assert not any((base / 'common/log').iterdir())
        assert not any((base / 'common/data/spec_backup').iterdir())
    for p in stage.rglob('*'):
        assert p.name not in EXCLUDED_DIRS, p
        assert p.name not in {'license_info.json', 'appearance.json', 'appearance.ini', 'panel_layout.ini'}, p
        assert p.suffix.lower() not in {'.pyc', '.pyo', '.log'}, p


def main():
    version = release_version(ROOT)
    active = json.loads((ROOT / 'common/data/settings/config.json').read_text(encoding='utf-8-sig'))
    theme = active['theme']
    output = ROOT / 'dist' / f'Signal_{version}.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='signal-release-') as work:
        work = Path(work)
        defaults = prepare_build_data(work, theme=theme)
        stage = work / 'package'
        stage.mkdir()
        binary = work / "binary/signal.exe"
        build_binary(binary, theme=theme)
        assemble(ROOT, stage, defaults, version, binary)
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with ZipFile(temporary, 'w', ZIP_DEFLATED) as archive:
                for path in sorted(stage.rglob('*')):
                    relative = path.relative_to(stage).as_posix()
                    if path.is_dir():
                        archive.writestr(relative + '/', '')
                    else:
                        archive.write(path, relative)
            with ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError('Distribution ZIP failed its integrity check')
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
    update_docs_release_info(ROOT, version)
    print(f'Distribution ready: {output}')
    print('Built a fresh release binary in Temp; common/bin was not modified. No application was launched.')


if __name__ == '__main__':
    main()
