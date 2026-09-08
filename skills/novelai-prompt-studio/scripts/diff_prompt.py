#!/usr/bin/env python3
"""Compare review records, enforcing the locks declared by the previous version."""
from __future__ import annotations
import argparse
import json
import sys
from studio import diff_sessions, load_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before')
    p.add_argument('after')
    p.add_argument('--format', choices=('text', 'json'), default='text')
    args = p.parse_args(argv)
    try:
        result = diff_sessions(load_json(args.before), load_json(args.after))
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'Input error: {exc}', file=sys.stderr)
        return 2
    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('Preservation check: ' + ('PASS' if result['ok'] else 'FAIL'))
        for path in result['lock_violations']:
            print('LOCK VIOLATION: ' + path)
        for change in result['changes']:
            print(f'\n{change["path"]}\n- {json.dumps(change["before"], ensure_ascii=False)}\n+ {json.dumps(change["after"], ensure_ascii=False)}')
        if not result['changes']:
            print('No changes.')
        print(result['limits'])
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
