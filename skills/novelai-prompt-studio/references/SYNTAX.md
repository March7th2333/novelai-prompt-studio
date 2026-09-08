# Syntax and scope

Use plain comma-separated tags plus short natural-language statements. A plausible tag is not necessarily a recognized NovelAI tag. Do not invent autocomplete results. [NAI-TAGS]

## Emphasis

`{content}` strengthens and `[content]` weakens; each nesting level changes focus by a factor of 1.05. In UC, stronger means more avoidance. Numeric emphasis is V4+; negative numeric emphasis is V4.5+. Use e.g. `1.2::rim lighting::` only for a specific need. [NAI-WEIGHTS]

`::` resets emphasis and can close bracket emphasis. Consequently `{{rain::` is not automatically an invalid unbalanced prompt. Unclosed emphasis affects the remaining text, so the tool reports a scope warning rather than claiming the model will reject it. Exotic mixed/nested weighting is marked for manual review. This is a conservative inspector, not NovelAI's parser.

Do not rewrite character-name parentheses as weights. `(rim lighting:1.2)` is a foreign weighting convention; inspect and convert intentionally rather than pretending it is NovelAI syntax.

## Characters

Counts belong in Base; individual character fields describe a `girl`, `boy` or `other` without a numeric count. Keep lighting/environment in Base and per-person colors/garments/actions in their own fields. The UI's separate fields and `|` encoding are alternate input modes; do not combine them. Position hints are not precise geometry. [NAI-CHARACTERS]

## Text

For supported models, add a text request in Base and place `Text:` followed by the required wording at the end. Everything after it is treated as desired visible text by this tool, including commas and braces; it is not linted as tag syntax. Do not append ordinary tags after the text. Automatic quality additions can conflict with text requests. [NAI-TEXT; NAI-QUALITY]

## Negative content

UC is avoidance, not a logical NOT operator with guaranteed results. A negatively weighted positive-prompt concept is not a normal desired concept. Do not report it as a positive-versus-UC contradiction solely because the same word appears in both. Removing a term from a custom UC supplement does not remove it from the active preset. [NAI-WEIGHTS; NAI-UC]

Source IDs resolve in `SOURCES.md`.
