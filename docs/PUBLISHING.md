# Publishing to GitHub

Prerequisites: Python 3.10+, Git, GitHub CLI (`gh`), an authenticated personal GitHub account, and permission to create repositories. The original chat's connected GitHub account does not automatically authenticate a separate Work terminal.

## Inspect before executing

```sh
python3 tools/publish_github.py --repo YOUR_LOGIN/novelai-prompt-studio
```

This prints a plan and performs no remote write. The repository owner must match the account returned by `gh api user` at execution time. The default visibility is **private**; use `--visibility public` only when public sharing is intended.

## Execute

```sh
python3 tools/publish_github.py --repo YOUR_LOGIN/novelai-prompt-studio --visibility private --execute
```

The helper validates the package, runs tests, builds both zip archives, snapshots only manifest-allowlisted files, and creates a new personal repository. It pushes a new `main` and version tag, creates a release with checksums, then reads back the commit, tag and release metadata. It prints verified URLs and SHA on success.

An existing repository causes a refusal, including an apparently empty one. This prevents accidental replacement of unrelated work. Do not workaround this with force push. If publication stops after repository creation, the partial remote repository is left intact and the tool reports the last completed stage. Inspect it before resuming manually; no remote deletion or destructive rollback is attempted.

The helper never modifies global Git settings, prints credentials, makes a private repository public, overwrites a release, or uploads files outside `MANIFEST.json`. GitHub publication is distinct from plugin-directory distribution.

## Verification boundaries

Offline tests simulate GitHub commands; they do not establish remote credentials, account permissions, or actual deployment success. Do not report the planned repository link as live before the remote verification step succeeds.

CLI references (checked 2026-09-08):
- https://cli.github.com/manual/gh_repo_create
- https://cli.github.com/manual/gh_release_create
