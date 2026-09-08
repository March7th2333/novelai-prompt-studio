#!/usr/bin/env python3
"""Validate distributable metadata, examples and internal Markdown references."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from repo_utils import ROOT, SKILL_PREFIX, manifest_files, read_version, safe_file


def validate(root: Path = ROOT) -> dict[str, object]:
    names = manifest_files(root)
    read_version(root)
    skill = safe_file(root, SKILL_PREFIX + 'SKILL.md').read_text(encoding='utf-8')
    if not skill.startswith('---\n') or '\n---\n' not in skill[4:]:
        raise ValueError('SKILL.md must have YAML frontmatter')
    front = skill.split('---', 2)[1]
    if not re.search(r'^name: novelai-prompt-studio$', front, re.M) or not re.search(r'^description:', front, re.M):
        raise ValueError('Missing skill name or description')
    if len(skill.splitlines()) > 500:
        raise ValueError('SKILL.md must remain below 500 lines')
    sys.path.insert(0, str(root / SKILL_PREFIX / 'scripts'))
    try:
        from studio import lint_session
        db = json.loads(safe_file(root, SKILL_PREFIX + 'references/models.json').read_text(encoding='utf-8'))
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', db['verified_on']):
            raise ValueError('Missing dated model verification')
        examples = []
        for name in names:
            if name.startswith(SKILL_PREFIX + 'examples/') and name.endswith('.json'):
                result = lint_session(json.loads(safe_file(root, name).read_text(encoding='utf-8')), db)
                if not result['ok']:
                    raise ValueError('Example has linter errors: ' + name)
                examples.append(name)
        for name in names:
            path = safe_file(root, name)
            if name.endswith('.json'):
                json.loads(path.read_text(encoding='utf-8'))
            if name.endswith('.md'):
                for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                    if ':' in link or link.startswith('#'):
                        continue
                    resolved = (path.parent / link.split('#')[0]).resolve()
                    if not resolved.exists():
                        raise ValueError(f'Broken Markdown link in {name}: {link}')
                    relative = resolved.relative_to(root.resolve()).as_posix()
                    if resolved.is_file() and relative not in names:
                        raise ValueError(f'Linked file missing from manifest: {relative}')
    finally:
        sys.path.pop(0)
    return {'manifest_files': len(names), 'examples_checked': len(examples),
            'skill_lines': len(skill.splitlines()), 'offline_validation': 'passed'}


def main() -> int:
    try:
        print(json.dumps(validate(), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as exc:
        print(f'Validation error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
