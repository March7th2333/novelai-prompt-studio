# Sources and evidence ledger

Verified: **2026-09-08**. This file links primary documentation; it is not a mirror of the source pages. Model claims are snapshots, not promises that interfaces cannot change.

| ID | Primary source | Used for |
|---|---|---|
| NAI-MODELS | https://docs.novelai.net/en/image/models/ | Version-specific capabilities; V5 character limit; approximate base token limits |
| NAI-WEIGHTS | https://docs.novelai.net/en/image/strengthening-weakening/ | Braces, square brackets, numerical emphasis, reset marker; version restrictions |
| NAI-TAGS | https://docs.novelai.net/en/image/tags/ | Known tags are helpful but not mandatory; tag/natural-language distinction |
| NAI-QUALITY | https://docs.novelai.net/en/image/qualitytags/ | Automatic quality additions; capacity usage; model-scoped known conflicts |
| NAI-UC | https://docs.novelai.net/en/image/undesiredcontent/ | UC presets and selected suppression risks |
| NAI-CHARACTERS | https://docs.novelai.net/en/image/multiplecharacters/ | Scene/character separation; count placement; boxes versus pipe syntax |
| NAI-TEXT | https://docs.novelai.net/en/image/textrendering/ | Text rendering marker and placement; supported languages |
| NAI-SEED | https://docs.novelai.net/en/image/seed/ | Seed dependence and limits of reproducibility |
| SKILLS | https://developers.openai.com/codex/skills/ | SKILL.md structure, local skill paths, optional agents/openai.yaml |
| GH-CREATE | https://cli.github.com/manual/gh_repo_create | Repository creation flags |
| GH-RELEASE | https://cli.github.com/manual/gh_release_create | Release creation and tag verification |

## Known gaps and apparent inconsistencies

- The general multi-character page describes six slots for V4 and later, but the model-specific page explicitly gives V5 up to 22. Apply six to V4/V4.5 and 22 to V5; do not generalize either across versions.
- V5 is listed on the models page, but the checked quality/UC pages do not provide a matching complete V5 preset expansion. Those fields remain unknown.
- V5 text-length units are worded differently in the models and text-rendering pages. This package does not enforce a V5 text-length ceiling; consult the current interface rather than silently treating tokens as characters.
- All stored UC terms and quality-risk terms are selected excerpts, not complete preset contents. Coverage remains partial unless the user supplies the exact current expansion or switches the corresponding feature off.
- No exact NovelAI tokenizer, API schema, image-generation test, or hidden model metadata is included.

## Evidence classes

`documented`: directly supported by a linked official source. `design_proposal`: an authored aesthetic/workflow choice. `observed_once`: one real, provided output. `observed_comparison`: multiple recorded outputs/settings. `unknown`: insufficient evidence.

Update the relevant model profile and its source note together. Never convert a suggestion into an official guarantee, or refresh a verification date without rereading the relevant source.

## CI dependency pins

Official repository tag refs were read on 2026-09-08. `actions/checkout` v4 resolved to `11d5960a326750d5838078e36cf38b85af677262`; `actions/setup-python` v5 resolved to `a26af69be951a213d495a4c3e4e4022e16d87065`. These are verified pins, not a claim that these major versions are the newest.

- https://api.github.com/repos/actions/checkout/git/ref/tags/v4
- https://api.github.com/repos/actions/setup-python/git/ref/tags/v5
