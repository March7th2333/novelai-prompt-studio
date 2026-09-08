# Review-record format, schema version 1

This is an internal review record for the bundled scripts. It is **not** an official NovelAI API payload, image metadata format or UI-import document. Copy the appropriate prompt strings to the corresponding UI fields; do not paste the complete JSON into NovelAI.

## Minimal record

```json
{
  "schema_version": 1,
  "model": "unknown",
  "quality_tags": "unknown",
  "uc_preset": "unknown",
  "base_prompt": "portrait, soft lighting"
}
```

Use `assets/session-template.json` for a full blank record or begin with a file from `examples/`.

## Field contract

| Field | Type and behavior |
|---|---|
| `schema_version` | Required integer `1`; boolean values are rejected |
| `model` | Required nonempty string; local profile keys are in `models.json`; unrecognized models remain unknown |
| `quality_tags` | Required `on`, `off` or `unknown` |
| `quality_tags_text` | String or null; exact current expansion supplied by the user, not a guess; null when unavailable |
| `uc_preset` | Required nonempty string; `none`, `unknown`, a stored local preset key (`light`, `heavy`, `human-focus`) or an unrecognized current preset name |
| `uc_preset_text` | String or null; user-supplied current expansion; never infer the full expansion from stored risk fragments |
| `base_prompt` | Required string, covering the global scene and overall subject count |
| `characters` | Optional list of `{id, prompt, uc, position}`; `id` and `prompt` required, IDs unique; other fields default to empty UC/unspecified position |
| `uc` | Global custom UC string; default empty |
| `intent` | Optional booleans: `text`, `negative_space`, `film_grain`, `logo`, `glowing_eyes`, `multiple_views`, `feet`; default false |
| `spec` | `must_keep`, `may_change`, `must_avoid`, each a list of strings; descriptive constraints are for the agent to review |
| `locked_paths` | List of existing dotted paths, e.g. `characters`, `characters.0.prompt`, `model`, `generation.seed`; enforced by the diff tool |
| `generation` | Optional known settings: integer `seed` (zero allowed), positive integer `width`/`height`/`steps`, finite nonnegative numeric `guidance`, nonempty string `sampler`; each may be null |

Unknown object keys are rejected to catch misspellings. `quality_tags_text` cannot be nonempty when the toggle is off; `uc_preset_text` cannot be nonempty when the preset is none. A missing setting is unknown/null, never an invented measured value. Maximum JSON file size is 1 MB; prompt strings are bounded to 128,000 characters for local input safety, not as a claimed model limit.

`quality_tags_text` and `uc_preset_text` are trusted only as supplied data. Their presence does not prove the tool inspected the actual UI or that the UI still has those settings.

## Matching and coverage

The linter normalizes case, whitespace and underscores. It checks exact term matches plus a narrowly defined hair-length/color alias pattern (e.g. `long blue hair` includes `blue hair`). It does not infer all natural-language synonyms, contradictions, artistic quality or character identity. Complex nested emphasis remains a manual review case.

Prompt terms after the first `Text:` marker are preserved as intended visible text, not parsed as tags. For multi-character records, pipe syntax is rejected when character fields also exist. Each character's custom UC applies only to that character; global UC applies to every subject. Ordinary negative numerical concepts are not treated as positive requests.

Stored preset risk fragments give `known_risk_subset` coverage, not a complete effective prompt. A user-supplied expansion gives `explicit_user_expansion` coverage. Disabled features are `not_active`; unknown selections/switches/expansions remain unknown and produce a warning.

## Exit codes

Linter: `0` means no error-severity finding; warnings may remain. `--strict` also makes warnings return `1`. `1` means a finding blocked the chosen policy; `2` means invalid/unreadable input.

Diff: `0` means the previous record's locked fields were preserved, even if other fields changed. `1` means at least one prior lock was violated. `2` means invalid/unreadable input. Removing locks in the new record does not disable the old record's protection. A field lock preserves record values, not generated pixels.
