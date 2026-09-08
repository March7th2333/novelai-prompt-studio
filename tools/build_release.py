#!/usr/bin/env python3
"""Build deterministic source/skill archives from MANIFEST.json (offline)."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from repo_utils import ROOT, build_archives


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, help='Local output directory; defaults to dist/')
    args = p.parse_args(argv)
    try:
        paths = build_archives(ROOT, args.out)
    except (ValueError, OSError) as exc:
        print(f'Build error: {exc}', file=sys.stderr)
        return 2
    for key, path in paths.items():
        print(f'{key}: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
