"""Allowlisted, symlink-resistant local package operations; no network access."""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
SKILL_PREFIX = 'skills/novelai-prompt-studio/'
FIXED_ZIP_TIME = (2026, 9, 8, 0, 0, 0)
ROOT_FILES = {'README.md', 'LICENSE', 'VERSION', 'CHANGELOG.md', 'AGENTS.md',
              '.gitignore', '.gitattributes', 'MANIFEST.json'}
ALLOWED_ROOTS = {'skills', 'tools', 'tests', 'docs', '.github'}
FORBIDDEN_PARTS = {'.git', '.env', '.venv', '__pycache__', 'private', 'local', 'dist'}
ALLOWED_SUFFIXES = {'.md', '.py', '.json', '.yml', '.yaml'}


def read_version(root: Path = ROOT) -> str:
    value = safe_file(root, 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', value):
        raise ValueError('VERSION must be a simple semantic version')
    return value


def safe_file(root: Path, name: str) -> Path:
    if not isinstance(name, str) or '\\' in name:
        raise ValueError('Manifest paths must be relative POSIX strings')
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in {'.', '..'} for p in name.split('/')):
        raise ValueError(f'Unsafe manifest path: {name!r}')
    if any(p in FORBIDDEN_PARTS or p.startswith('.env') for p in path.parts):
        raise ValueError(f'Excluded material in manifest: {name}')
    if name not in ROOT_FILES and (path.parts[0] not in ALLOWED_ROOTS or path.suffix not in ALLOWED_SUFFIXES):
        raise ValueError(f'Not an allowed distribution path: {name}')
    root = root.resolve()
    candidate = root
    for part in path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError(f'Symlinks are not distributed: {name}')
    candidate.resolve().relative_to(root)
    if not candidate.is_file():
        raise ValueError(f'Missing manifest file: {name}')
    return candidate


def manifest_files(root: Path = ROOT) -> list[str]:
    path = safe_file(root, 'MANIFEST.json')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('Unsupported manifest schema')
    files = manifest.get('files')
    if not isinstance(files, list) or not files or any(not isinstance(p, str) for p in files):
        raise ValueError('Manifest files must be a nonempty list of paths')
    if len(set(files)) != len(files):
        raise ValueError('Manifest contains duplicate paths')
    if not {'MANIFEST.json', 'LICENSE', 'VERSION', SKILL_PREFIX + 'SKILL.md'}.issubset(files):
        raise ValueError('Manifest omits required distribution files')
    for name in files:
        safe_file(root, name)
    return sorted(files)


def snapshot(root: Path, dest: Path) -> None:
    """Copy only reviewed manifest files into a new snapshot directory."""
    if dest.exists():
        raise ValueError('Snapshot target must not exist')
    names = manifest_files(root)
    dest.mkdir(parents=True)
    for name in names:
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_file(root, name), target)


def write_zip(path: Path, entries: list[tuple[str, bytes]]) -> None:
    if path.exists():
        path.unlink()  # Only the explicitly named local build output, never source files.
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, content in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_archives(root: Path = ROOT, out: Path | None = None) -> dict[str, Path]:
    root = root.resolve()
    out = (out or root / 'dist').resolve()
    names = manifest_files(root)
    version = read_version(root)
    out.mkdir(parents=True, exist_ok=True)
    source_entries = [('novelai-prompt-studio/' + n, safe_file(root, n).read_bytes()) for n in names]
    skill_entries = [('novelai-prompt-studio/' + n[len(SKILL_PREFIX):], safe_file(root, n).read_bytes())
                     for n in names if n.startswith(SKILL_PREFIX)]
    skill_entries.append(('novelai-prompt-studio/LICENSE', safe_file(root, 'LICENSE').read_bytes()))
    paths = {
        'source': out / f'novelai-prompt-studio-v{version}-source.zip',
        'skill': out / f'novelai-prompt-studio-v{version}-skill.zip',
        'checksums': out / 'SHA256SUMS.txt',
    }
    if any(p.is_symlink() for p in paths.values()):
        raise ValueError('Build output paths must not be symlinks')
    # Build outputs may never replace a listed source file.
    sources = {safe_file(root, n).resolve() for n in names}
    if any(p.resolve() in sources for p in paths.values()):
        raise ValueError('Build output collides with a source file')
    write_zip(paths['source'], source_entries)
    write_zip(paths['skill'], skill_entries)
    paths['checksums'].write_text(''.join(
        f'{hashlib.sha256(paths[k].read_bytes()).hexdigest()}  {paths[k].name}\n'
        for k in ('source', 'skill')), encoding='utf-8')
    return paths
