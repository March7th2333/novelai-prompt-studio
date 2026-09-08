# Model selection and incomplete state

The machine-readable file `models.json` is a dated capability snapshot. Its model IDs are **local profile keys**, not NovelAI API model identifiers.

V3 uses the legacy bracket emphasis scheme; numeric emphasis is not supported. V4 adds numeric emphasis and separate character prompts. V4.5 and V5 also support negative numeric emphasis. [NAI-WEIGHTS; NAI-CHARACTERS]

V4/V4.5 share a documented approximate 512-token allowance across Base and Character Prompts. V5 profiles record only the model page's approximate Base allowances; do not assume an undocumented shared allocation or exact character conversion. None of these values are measured by the linter. [NAI-MODELS]

Use English for the portable default. V5 explicitly broadens language support, while V4/V4.5 have tokenizer and text-rendering constraints. [NAI-MODELS; NAI-TEXT]

`unknown` and an unrecognized future model must remain unknown. Offer plain-language composition without version-specific emphasis, preserve the user's model spelling, and request/check the UI only when necessary to continue.

The linter recognizes only selected automatic suppressors (`no text`, `feet`) and selected UC risks. It never claims to reconstruct full preset text from these fragments. If `quality_tags_text` or `uc_preset_text` is provided, that is a **user-supplied explicit expansion**, not an authenticated API read.

Source IDs resolve in `SOURCES.md`.
