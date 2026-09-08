# Validation levels

## Automated, offline

`python3 -m unittest discover -s tests -v` checks parser edge cases, model compatibility, known preset conflicts, per-character scope, text rendering boundaries, record validation, immutable-path diffs, safe installation, allowlisted reproducible archives and simulated publication safeguards.

`python3 tools/validate_repo.py` checks the distribution manifest, JSON examples, model metadata, entry-point frontmatter and package references required by the validator. It does not execute an AI host or browse reference URLs.

`python3 tools/build_release.py` creates source and standalone-skill zip files plus SHA-256 checksums from a fixed manifest. Archive timestamps are fixed to the version's source date for reproducibility.

## Not established by those checks

No live NovelAI generation has been performed. No visual success rate, exact token estimate, model quality comparison, host/plugin installation success or actual GitHub publication follows from unit tests. Behavioral scenarios are in the skill's `references/BEHAVIOR_EVALS.md` and must be run separately.

A local test execution report may accompany the delivered archives outside the public source tree. A future maintainer should rerun tests instead of relying on that historical report.
