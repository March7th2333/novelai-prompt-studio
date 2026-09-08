"""Shared, dependency-free review-record and conservative prompt inspection logic.

This module is not NovelAI's tokenizer or prompt parser. It deliberately reports
incomplete coverage and does not execute prompt text or perform network calls.
"""
from __future__ import annotations

import copy
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 1_000_000
MAX_PROMPT_CHARS = 128_000
INTENTS = ('text', 'negative_space', 'film_grain', 'logo', 'glowing_eyes', 'multiple_views', 'feet')
MODEL_FILE = Path(__file__).resolve().parent.parent / 'references' / 'models.json'
NUMERIC = re.compile(r'([-+]?(?:\d+(?:\.\d*)?|\.\d+))::')
FOREIGN_WEIGHT = re.compile(r'(?<!\\)\([^()\n]+:\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*\)')
PATH_PATTERN = re.compile(r'[A-Za-z_][A-Za-z_0-9]*(?:\.(?:[A-Za-z_][A-Za-z_0-9]*|\d+))*\Z')
MISSING = object()


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class Atom:
    text: str
    weight: float


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if p.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f'File exceeds {MAX_FILE_BYTES} bytes: {p.name}')
    def reject_constant(value: str) -> None:
        raise ValueError(f'Non-finite JSON number: {value}')
    return json.loads(p.read_text(encoding='utf-8'), parse_constant=reject_constant)


def require_keys(value: Any, allowed: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f'{path} must be an object')
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f'{path}: unknown fields: {", ".join(sorted(unknown))}')
    return value


def require_string(value: Any, path: str, *, empty: bool = True) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f'{path} must be {"a" if empty else "a nonempty"} string')
    if len(value) > MAX_PROMPT_CHARS:
        raise ValueError(f'{path} exceeds {MAX_PROMPT_CHARS} characters')
    return value


def resolve_path(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split('.'):
        if isinstance(current, dict):
            if part not in current:
                return MISSING
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return MISSING
    return current


def validate_session(value: Any) -> dict[str, Any]:
    allowed = {'schema_version', 'model', 'quality_tags', 'quality_tags_text', 'uc_preset',
               'uc_preset_text', 'base_prompt', 'characters', 'uc', 'intent', 'spec',
               'locked_paths', 'generation'}
    require_keys(value, allowed, 'session')
    required = {'schema_version', 'model', 'quality_tags', 'uc_preset', 'base_prompt'}
    missing = required - set(value)
    if missing:
        raise ValueError('Missing fields: ' + ', '.join(sorted(missing)))
    v = copy.deepcopy(value)
    if type(v['schema_version']) is not int or v['schema_version'] != 1:
        raise ValueError('schema_version must be the integer 1')
    require_string(v['model'], 'model', empty=False)
    if not isinstance(v['quality_tags'], str) or v['quality_tags'] not in {'on', 'off', 'unknown'}:
        raise ValueError('quality_tags must be on, off or unknown')
    require_string(v['uc_preset'], 'uc_preset', empty=False)
    require_string(v['base_prompt'], 'base_prompt')
    for field in ('quality_tags_text', 'uc_preset_text'):
        v.setdefault(field, None)
        if v[field] is not None:
            require_string(v[field], field)
    if v['quality_tags'] == 'off' and v['quality_tags_text']:
        raise ValueError('quality_tags_text must be null/empty when quality_tags is off')
    if v['uc_preset'] == 'none' and v['uc_preset_text']:
        raise ValueError('uc_preset_text must be null/empty when uc_preset is none')
    v.setdefault('uc', '')
    require_string(v['uc'], 'uc')
    v.setdefault('characters', [])
    if not isinstance(v['characters'], list):
        raise ValueError('characters must be a list')
    ids: set[str] = set()
    for i, c in enumerate(v['characters']):
        path = f'characters.{i}'
        require_keys(c, {'id', 'prompt', 'uc', 'position'}, path)
        if 'id' not in c or 'prompt' not in c:
            raise ValueError(f'{path} requires id and prompt')
        require_string(c['id'], path + '.id', empty=False)
        if c['id'] in ids:
            raise ValueError('Duplicate character id: ' + c['id'])
        ids.add(c['id'])
        require_string(c['prompt'], path + '.prompt')
        c.setdefault('uc', '')
        c.setdefault('position', 'unspecified')
        require_string(c['uc'], path + '.uc')
        require_string(c['position'], path + '.position')
    v.setdefault('intent', {})
    require_keys(v['intent'], set(INTENTS), 'intent')
    for flag in INTENTS:
        v['intent'].setdefault(flag, False)
        if type(v['intent'][flag]) is not bool:
            raise ValueError(f'intent.{flag} must be a boolean')
    v.setdefault('spec', {})
    require_keys(v['spec'], {'must_keep', 'may_change', 'must_avoid'}, 'spec')
    for key in ('must_keep', 'may_change', 'must_avoid'):
        v['spec'].setdefault(key, [])
        if not isinstance(v['spec'][key], list):
            raise ValueError(f'spec.{key} must be a list of strings')
        for item in v['spec'][key]:
            require_string(item, f'spec.{key}', empty=False)
    v.setdefault('generation', {})
    require_keys(v['generation'], {'seed', 'width', 'height', 'steps', 'guidance', 'sampler'}, 'generation')
    for key in ('seed', 'width', 'height', 'steps', 'guidance', 'sampler'):
        v['generation'].setdefault(key, None)
        x = v['generation'][key]
        if x is None:
            continue
        if key == 'sampler':
            require_string(x, f'generation.{key}', empty=False)
        elif key == 'guidance':
            if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
                raise ValueError('generation.guidance must be a finite nonnegative number or null')
        elif type(x) is not int or x < (0 if key == 'seed' else 1):
            raise ValueError(f'generation.{key} must be a valid nonnegative/positive integer or null')
    v.setdefault('locked_paths', [])
    if not isinstance(v['locked_paths'], list):
        raise ValueError('locked_paths must be a list')
    for path in v['locked_paths']:
        if not isinstance(path, str) or not PATH_PATTERN.fullmatch(path):
            raise ValueError(f'Invalid locked path: {path!r}')
        if resolve_path(v, path) is MISSING:
            raise ValueError('Locked path does not exist: ' + path)
    return v


def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.replace('\\(', '(').replace('\\)', ')').replace('_', ' ')).strip().lower()


def split_rendered_text(text: str) -> tuple[str, str | None]:
    match = re.search(r'\bText:\s*', text)
    return (text[:match.start()], text[match.end():]) if match else (text, None)


def inspect_atoms(text: str, path: str, profile: dict[str, Any] | None) -> tuple[list[Atom], list[Issue], str | None]:
    body, rendered = split_rendered_text(text)
    issues: list[Issue] = []
    atoms: list[Atom] = []
    chunk: list[str] = []
    weight = 1.0
    active_numeric = False
    curly = square = 0
    i = 0

    def flush() -> None:
        if chunk:
            cleaned = normalize(''.join(chunk))
            if cleaned:
                atoms.append(Atom(cleaned, weight))
            chunk.clear()

    if FOREIGN_WEIGHT.search(body):
        issues.append(Issue('warning', 'foreign_weight_syntax', path,
                            'Parenthesized numerical weights are not NovelAI emphasis syntax.'))
    if '|' in body:
        issues.append(Issue('warning', 'pipe_not_parsed', path,
                            'Pipe-encoded prompts are not parsed into scopes here; use separate record fields.'))
    while i < len(body):
        char = body[i]
        if char == '\\' and i + 1 < len(body):
            chunk.append(body[i:i + 2])
            i += 2
            continue
        match = NUMERIC.match(body, i)
        if match:
            flush()
            if active_numeric:
                issues.append(Issue('warning', 'complex_weight_scope', path,
                                    'Consecutive numeric scopes need manual review; this is not the model parser.'))
            weight = float(match.group(1))
            if not math.isfinite(weight):
                issues.append(Issue('error', 'nonfinite_emphasis', path, 'Emphasis must be finite.'))
                weight = 0.0
            if profile is not None:
                if not profile['numeric_emphasis']:
                    issues.append(Issue('error', 'numeric_unsupported', path, 'Numeric emphasis requires V4 or higher.'))
                elif weight < 0 and not profile['negative_emphasis']:
                    issues.append(Issue('error', 'negative_unsupported', path, 'Negative emphasis requires V4.5 or higher.'))
            active_numeric = True
            i = match.end()
            continue
        if body.startswith('::', i):
            flush()
            weight = 1.0
            active_numeric = False
            curly = square = 0
            i += 2
            continue
        if char in '{}[]':
            flush()
            if char == '{':
                curly += 1
            elif char == '}':
                curly -= 1
            elif char == '[':
                square += 1
            else:
                square -= 1
            if curly < 0 or square < 0:
                issues.append(Issue('warning', 'unconventional_brackets', path,
                                    'Unconventional bracket arithmetic; review scope rather than treating this as a parse failure.'))
            i += 1
            continue
        if char in ',\n':
            flush()
        else:
            chunk.append(char)
        i += 1
    flush()
    if active_numeric or curly or square:
        issues.append(Issue('warning', 'open_emphasis_scope', path,
                            'Emphasis continues to the end; close it explicitly for a bounded edit.'))
    if profile and not profile['multilingual_prompting'] and re.search(r'[\u3040-\u30ff\u3400-\u9fff\U0001f300-\U0001faff]', text):
        issues.append(Issue('warning', 'language_support_check', path,
                            'This profile has limited Unicode/multilingual support; use an English description or verify the UI.'))
    if rendered is not None and profile and not profile['text_rendering']:
        issues.append(Issue('error', 'text_rendering_unsupported', path, 'Structured Text: rendering requires V4 or higher.'))
    return atoms, issues, rendered


def lint_session(value: Any, profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    v = validate_session(value)
    db = profiles if profiles is not None else load_json(MODEL_FILE)
    profile = db['models'].get(v['model'])
    issues: list[Issue] = []
    fields: dict[str, list[Atom]] = {}
    rendered_segments: dict[str, str] = {}
    source_fields = {'base_prompt': v['base_prompt'], 'uc': v['uc']}
    for i, c in enumerate(v['characters']):
        source_fields[f'characters.{i}.prompt'] = c['prompt']
        source_fields[f'characters.{i}.uc'] = c['uc']
    if profile is None:
        issues.append(Issue('warning', 'model_unknown', 'model',
                            'Unknown model profile; version-specific compatibility is not verified.'))
    for path, text in source_fields.items():
        atoms, more, rendered = inspect_atoms(text, path, profile)
        fields[path] = atoms
        issues.extend(more)
        if rendered is not None:
            rendered_segments[path] = rendered
        counts = Counter(a.text for a in atoms if a.weight > 0)
        for term, count in counts.items():
            if count > 1:
                issues.append(Issue('warning', 'duplicate_term', path, f'Duplicate in this field: {term!r} ({count} occurrences).'))
    if v['characters'] and any('|' in split_rendered_text(t)[0] for t in source_fields.values()):
        issues.append(Issue('error', 'mixed_character_input', 'characters',
                            'Do not combine character boxes with pipe-encoded input.'))
    if profile and v['characters']:
        if not profile['character_boxes']:
            issues.append(Issue('error', 'character_boxes_unsupported', 'characters', 'This profile does not support separate character prompts.'))
        elif len(v['characters']) > profile['max_character_boxes']:
            issues.append(Issue('error', 'too_many_characters', 'characters', 'Character count exceeds the documented model-specific limit.'))
    for i in range(len(v['characters'])):
        path = f'characters.{i}.prompt'
        if any(re.fullmatch(r'\d+(?:girls?|boys?|others?)', a.text) for a in fields[path]):
            issues.append(Issue('warning', 'count_in_character', path, 'Put numeric subject counts in Base, not in an individual character field.'))
    count_tags = [re.fullmatch(r'(\d+)(?:girls?|boys?|others?)', a.text) for a in fields['base_prompt'] if a.weight > 0]
    base_count = sum(int(m.group(1)) for m in count_tags if m)
    if v['characters'] and base_count and base_count != len(v['characters']):
        issues.append(Issue('warning', 'character_count_mismatch', 'base_prompt', 'Base subject counts do not match the number of character fields.'))

    def positive(atoms: list[Atom]) -> set[str]:
        terms = {a.text for a in atoms if a.weight > 0}
        # A deliberately small, auditable alias set; not arbitrary substring matching.
        # Descriptive "long blue hair" also requests the concept "blue hair".
        aliases = set()
        for term in terms:
            match = re.fullmatch(
                r'(very long|long|short|medium) (pink|blue|red|green|black|white|brown|blonde|purple|silver|gray) hair', term)
            if match:
                aliases.add(match.group(1) + ' hair')
                aliases.add(match.group(2) + ' hair')
        return terms | aliases

    quality_atoms: list[Atom] = []
    preset_atoms: list[Atom] = []
    quality_suppressors: set[str] = set()
    preset_risks: set[str] = set()
    coverage: dict[str, str] = {}
    if v['quality_tags'] == 'off':
        coverage['quality_tags'] = 'not_active'
    elif v['quality_tags'] == 'unknown':
        coverage['quality_tags'] = 'unknown_switch'
    elif v['quality_tags_text'] is not None:
        coverage['quality_tags'] = 'explicit_user_expansion'
        quality_atoms, more, _ = inspect_atoms(v['quality_tags_text'], 'quality_tags_text', profile)
        issues.extend(more)
        quality_suppressors = {a.text for a in quality_atoms if a.weight < 0}
        if 'no text' in positive(quality_atoms):
            quality_suppressors.add('no text')
    else:
        known = profile.get('quality_suppressors') if profile else None
        coverage['quality_tags'] = 'known_risk_subset' if known is not None else 'unknown_expansion'
        quality_suppressors = set(known or [])
    if v['uc_preset'] == 'none':
        coverage['uc_preset'] = 'not_active'
    elif v['uc_preset'] == 'unknown':
        coverage['uc_preset'] = 'unknown_selection'
    elif v['uc_preset_text'] is not None:
        coverage['uc_preset'] = 'explicit_user_expansion'
        preset_atoms, more, _ = inspect_atoms(v['uc_preset_text'], 'uc_preset_text', profile)
        issues.extend(more)
        preset_risks = positive(preset_atoms)
    else:
        known = profile.get('uc_risks', {}).get(v['uc_preset']) if profile else None
        coverage['uc_preset'] = 'known_risk_subset' if known is not None else 'unknown_expansion'
        preset_risks = set(known or [])
    for field, state in coverage.items():
        if state not in {'not_active', 'explicit_user_expansion'}:
            issues.append(Issue('warning', 'coverage_incomplete', field, f'Check coverage is {state}; absence of findings does not mean conflict-free.'))

    global_uc = positive(fields['uc']) | positive(preset_atoms)
    global_positive = positive(fields['base_prompt']) | positive(quality_atoms)
    positive_by_scope = {'base_prompt': global_positive}
    for i in range(len(v['characters'])):
        positive_by_scope[f'characters.{i}.prompt'] = positive(fields[f'characters.{i}.prompt'])
    for path, terms in positive_by_scope.items():
        avoided = set(global_uc)
        if path.startswith('characters.'):
            i = path.split('.')[1]
            avoided |= positive(fields[f'characters.{i}.uc'])
        for term in sorted(terms & avoided):
            issues.append(Issue('warning', 'positive_uc_conflict', path, f'Desired term is also avoided in its applicable UC scope: {term!r}.'))
    for term in sorted(positive(fields['base_prompt']) & positive(quality_atoms)):
        issues.append(Issue('warning', 'duplicate_quality_term', 'base_prompt', f'Term is also added by supplied quality expansion: {term!r}.'))
    all_desired = set().union(*positive_by_scope.values())
    aliases = {
        'text': {'text', 'english text'}, 'negative_space': {'negative space'},
        'film_grain': {'film grain'}, 'logo': {'logo'}, 'glowing_eyes': {'glowing eyes'},
        'multiple_views': {'multiple views'}, 'feet': {'feet', 'bare feet'},
    }
    for intent, terms in aliases.items():
        requested = v['intent'][intent] or bool(terms & all_desired) or (intent == 'text' and bool(rendered_segments))
        if not requested:
            continue
        blockers = {'no text'} if intent == 'text' else terms
        if blockers & quality_suppressors:
            issues.append(Issue('warning', 'intent_quality_conflict', 'quality_tags', f'Requested {intent} conflicts with known automatic suppression.'))
        uc_blockers = terms & (global_uc | preset_risks)
        if uc_blockers:
            issues.append(Issue('warning', 'intent_uc_conflict', 'uc_preset' if terms & preset_risks else 'uc', f'Requested {intent} is discouraged by applicable UC: {", ".join(sorted(uc_blockers))}.'))
        if intent == 'text' and 'no text' in all_desired:
            issues.append(Issue('warning', 'text_no_text_conflict', 'base_prompt', 'Text is requested but a positive prompt also says no text.'))
    # Negative weighted desired concepts are intentionally excluded from ordinary UC intersections.
    unique = list(dict.fromkeys(issues))
    return {
        'schema_version': 1, 'model': v['model'], 'verified_on': db['verified_on'],
        'ok': not any(i.severity == 'error' for i in unique),
        'coverage': coverage,
        'token_count': {'status': 'not_measured', 'approx_documented_limit': profile.get('approx_prompt_tokens') if profile else None,
                        'scope': profile.get('prompt_token_scope') if profile else None},
        'text_segments': rendered_segments,
        'issues': [asdict(i) for i in unique],
        'limits': 'Conservative static inspection only; not exact tokenization, full semantic checking or image validation.'
    }


def diff_sessions(before: Any, after: Any) -> dict[str, Any]:
    old = validate_session(before)
    new = validate_session(after)
    changes: list[dict[str, Any]] = []
    def walk(a: Any, b: Any, path: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() | b.keys()):
                walk(a.get(key, MISSING), b.get(key, MISSING), f'{path}.{key}' if path else key)
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f'{path}.{i}')
        elif a is MISSING or b is MISSING or type(a) is not type(b) or a != b:
            changes.append({'path': path, 'before': None if a is MISSING else a,
                            'after': None if b is MISSING else b,
                            'before_exists': a is not MISSING, 'after_exists': b is not MISSING})
    walk(old, new, '')
    violations = []
    for path in dict.fromkeys(old['locked_paths']):
        a, b = resolve_path(old, path), resolve_path(new, path)
        if b is MISSING or type(a) is not type(b) or a != b:
            violations.append(path)
    return {'schema_version': 1, 'ok': not violations,
            'checked_locked_paths': old['locked_paths'], 'lock_violations': violations,
            'changes': changes,
            'limits': 'Exact record-field preservation, not a guarantee of identical generated pixels.'}
