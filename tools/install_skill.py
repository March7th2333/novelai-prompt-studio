#!/usr/bin/env python3
"""Install the packaged skill without overwriting any existing installation."""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path
from repo_utils import ROOT, SKILL_PREFIX, manifest_files, safe_file


def install(root: Path, parent: Path) -> Path:
    names = [n for n in manifest_files(root) if n.startswith(SKILL_PREFIX)]
    parent = parent.expanduser().resolve()
    target = parent / 'novelai-prompt-studio'
    if target.exists() or target.is_symlink():
        raise ValueError('Destination already exists; refusing to overwrite: ' + str(target))
    parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()  # exclusive creation; no dirs_exist_ok overwrite
    try:
        for name in names:
            dest = target / name[len(SKILL_PREFIX):]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_file(root, name), dest)
        shutil.copyfile(safe_file(root, 'LICENSE'), target / 'LICENSE')
    except Exception:
        shutil.rmtree(target)
        raise
    return target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dest', type=Path, default=Path.home() / '.agents' / 'skills',
                   help='Parent skill directory, not the skill directory itself')
    args = p.parse_args(argv)
    try:
        target = install(ROOT, args.dest)
    except (ValueError, OSError) as exc:
        print(f'Install error: {exc}', file=sys.stderr)
        return 2
    print(f'Installed skill files at {target}')
    print('Host discovery is a separate step; this command does not verify host activation.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
