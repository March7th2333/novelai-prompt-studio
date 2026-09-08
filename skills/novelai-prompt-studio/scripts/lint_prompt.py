#!/usr/bin/env python3
"""Inspect a NovelAI Prompt Studio JSON review record without network access."""
from __future__ import annotations
import argparse
import json
import sys
from studio import lint_session, load_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('session', help='Internal review-record JSON; not an official NovelAI import file')
    p.add_argument('--format', choices=('text', 'json'), default='text')
    p.add_argument('--strict', action='store_true', help='Exit 1 on warnings as well as errors')
    args = p.parse_args(argv)
    try:
        result = lint_session(load_json(args.session))
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'Input error: {exc}', file=sys.stderr)
        return 2
    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f'Model: {result["model"]}; profile verification: {result["verified_on"]}')
        print('Coverage: ' + ', '.join(f'{k}={v}' for k, v in result['coverage'].items()))
        for issue in result['issues']:
            print(f'{issue["severity"].upper()} [{issue["code"]}] {issue["path"]}: {issue["message"]}')
        if not result['issues']:
            print('No findings in the implemented static checks.')
        print(result['limits'])
    blocked = not result['ok'] or (args.strict and any(i['severity'] == 'warning' for i in result['issues']))
    return 1 if blocked else 0


if __name__ == '__main__':
    raise SystemExit(main())
