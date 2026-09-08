# Installation

Install with `python3 tools/install_skill.py` from the extracted source root. Python 3.10+ is required only for bundled scripts; the instructions can be read without Python.

The default destination is `~/.agents/skills/novelai-prompt-studio`. For a repository-scoped installation, pass the parent folder `.agents/skills` as `--dest`. The installer refuses an existing destination, copies only allowlisted skill files, rejects symlinks, and never changes other installed skills. Updating requires reviewing and moving/removing the old folder deliberately; there is no silent overwrite flag.

In a host that supports local skills, select the installed skill. Codex CLI/IDE support `$novelai-prompt-studio`; desktop invocation depends on its current skill picker. Source: https://developers.openai.com/codex/skills/ (checked 2026-09-08).

A GitHub repository or downloaded zip is not automatically an installed ChatGPT plugin. The standalone zip contains the same skill directory and can be copied to a supported local skill path. No third-party host has been integration-tested in this session.

To uninstall, remove only the `novelai-prompt-studio` folder you installed. User reference materials should live outside that directory and outside the public repository.
