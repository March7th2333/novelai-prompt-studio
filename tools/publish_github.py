#!/usr/bin/env python3
"""Explicit, non-destructive publication of a new personal GitHub repository.

Default is dry-run and private. Requires --execute for network writes.
Never uses shell=True, prints tokens, modifies global Git config, force-pushes,
changes visibility, or adopts an existing repository.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable
from repo_utils import ROOT, build_archives, read_version, snapshot
from validate_repo import validate

REPO_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z')
Runner = Callable[..., subprocess.CompletedProcess[str]]


class PublishError(RuntimeError):
    pass


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=120, check=False)


def plan(root: Path, repo: str, visibility: str) -> dict[str, object]:
    if not REPO_PATTERN.fullmatch(repo):
        raise ValueError('Repository must be a safe OWNER/NAME, not a URL')
    if visibility not in {'private', 'public'}:
        raise ValueError('Visibility must be private or public')
    version = read_version(root)
    return {'mode': 'dry-run', 'repository': repo, 'visibility': visibility,
            'tag': f'v{version}', 'remote_writes': False,
            'steps': ['validate allowlist', 'check matching authenticated account', 'refuse existing repository',
                      'run offline tests', 'build archives', 'create fresh local snapshot',
                      'create new repository', 'push main and tag without force', 'create release',
                      'read back repository, commit, tag and release asset metadata'],
            'note': 'Pass --execute to authorize writes in this environment. No publication has happened.'}


def publish(root: Path, repo: str, visibility: str, runner: Runner = run_command) -> dict[str, object]:
    details = plan(root, repo, visibility)
    stage = 'not_started'
    try:
        for executable in ('git', 'gh'):
            if shutil.which(executable) is None:
                raise PublishError(f'Required executable is unavailable: {executable}')
        validate(root)
        stage = 'local_package_validated'

        def checked(args: list[str], cwd: Path | None = None) -> str:
            result = runner(args, cwd=cwd)
            if result.returncode != 0:
                # Do not echo arbitrary command output: authentication helpers may include secrets.
                raise PublishError(f'Command failed ({args[0]} {args[1] if len(args) > 1 else ""}); exit {result.returncode}. Inspect that command locally; credentials are not echoed.')
            return result.stdout.strip()

        user = json.loads(checked(['gh', 'api', 'user']))
        login, uid = user.get('login'), user.get('id')
        if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', login) or type(uid) is not int:
            raise PublishError('Authenticated account response is invalid')
        if repo.split('/')[0].casefold() != login.casefold():
            raise PublishError('Repository owner does not match the authenticated personal account')
        stage = 'account_verified'
        existing = runner(['gh', 'api', f'repos/{repo}'], cwd=None)
        if existing.returncode == 0:
            raise PublishError('Repository already exists; automatic overwrite/adoption is forbidden')
        if not re.search(r'HTTP\s+404', existing.stderr or ''):
            raise PublishError('Cannot establish repository absence; no remote write attempted')
        stage = 'new_target_checked'
        checked([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], root)
        stage = 'offline_tests_passed'
        with tempfile.TemporaryDirectory(prefix='nai-publish-') as tmp:
            temp = Path(tmp)
            archive_paths = build_archives(root, temp / 'artifacts')
            work = temp / 'source'
            snapshot(root, work)
            checked(['git', 'init', '-b', 'main'], work)
            checked(['git', 'config', '--local', 'user.name', login], work)
            checked(['git', 'config', '--local', 'user.email', f'{uid}+{login}@users.noreply.github.com'], work)
            checked(['git', 'add', '--all'], work)
            checked(['git', '-c', 'commit.gpgsign=false', 'commit', '-m', f'Release {details["tag"]}'], work)
            checked(['git', '-c', 'tag.gpgsign=false', 'tag', '-a', str(details['tag']), '-m', f'NovelAI Prompt Studio {details["tag"]}'], work)
            commit = checked(['git', 'rev-parse', 'HEAD'], work)
            if not re.fullmatch(r'[a-f0-9]{40,64}', commit):
                raise PublishError('Local commit hash was not returned as expected')
            stage = 'local_snapshot_committed'
            checked(['gh', 'repo', 'create', repo, '--' + visibility,
                     '--description', 'NovelAI prompt design, constraint-preserving iteration, and version-aware checks'], work)
            stage = 'remote_repository_created'
            checked(['git', 'remote', 'add', 'origin', f'https://github.com/{repo}.git'], work)
            # Credential configuration applies to this invocation only, not global Git config.
            checked(['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
                     'push', '--atomic', '-u', 'origin', 'main', f'refs/tags/{details["tag"]}'], work)
            stage = 'main_and_tag_pushed'
            assets = [archive_paths[k] for k in ('source', 'skill', 'checksums')]
            checked(['gh', 'release', 'create', str(details['tag']), *map(str, assets), '--repo', repo,
                     '--verify-tag', '--title', f'NovelAI Prompt Studio {details["tag"]}',
                     '--notes-file', str(work / 'docs' / f'RELEASE_NOTES_{details["tag"]}.md')], work)
            stage = 'release_created'
            remote = json.loads(checked(['gh', 'repo', 'view', repo, '--json', 'url,visibility,nameWithOwner']))
            if remote.get('nameWithOwner', '').casefold() != repo.casefold() or remote.get('visibility', '').lower() != visibility:
                raise PublishError('Remote repository identity/visibility did not match the request')
            expected_repo_url = f'https://github.com/{repo}'
            if remote.get('url', '').casefold() != expected_repo_url.casefold():
                raise PublishError('Unexpected remote repository URL')
            remote_commit = json.loads(checked(['gh', 'api', f'repos/{repo}/commits/main']))
            if remote_commit.get('sha') != commit:
                raise PublishError('Remote main commit does not match the local snapshot')
            tag_ref = json.loads(checked(['gh', 'api', f'repos/{repo}/git/ref/tags/{details["tag"]}']))
            obj = tag_ref.get('object', {})
            if obj.get('type') == 'tag':
                tag_sha = obj.get('sha', '')
                if not re.fullmatch(r'[a-f0-9]{40,64}', tag_sha):
                    raise PublishError('Unexpected tag object hash')
                obj = json.loads(checked(['gh', 'api', f'repos/{repo}/git/tags/{tag_sha}'])).get('object', {})
            if obj.get('type') != 'commit' or obj.get('sha') != commit:
                raise PublishError('Remote tag does not identify the expected commit')
            release = json.loads(checked(['gh', 'release', 'view', str(details['tag']), '--repo', repo,
                                         '--json', 'url,tagName,assets']))
            expected_release_url = expected_repo_url + '/releases/tag/' + str(details['tag'])
            if release.get('tagName') != details['tag'] or release.get('url', '').casefold() != expected_release_url.casefold():
                raise PublishError('Unexpected release identity or URL')
            remote_assets = {a['name']: a.get('size') for a in release.get('assets', [])}
            if any(remote_assets.get(p.name) != p.stat().st_size for p in assets):
                raise PublishError('Release asset names/sizes did not match the built archives')
            stage = 'remote_metadata_verified'
            return {'status': 'published_and_verified', 'repository_url': remote['url'],
                    'release_url': release['url'], 'visibility': visibility, 'commit': commit,
                    'tag': details['tag'], 'assets': sorted(p.name for p in assets),
                    'verification': 'Remote repository identity/visibility, main commit, tag target and asset names/sizes read back; asset bytes not re-downloaded.'}
    except (PublishError, ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        raise PublishError(f'Publication stopped after stage {stage}: {exc}. Any created remote repository/release is left intact; inspect before retrying. No force push or destructive rollback was attempted.') from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True, help='Authenticated personal owner and a NEW repository name')
    p.add_argument('--visibility', choices=('private', 'public'), default='private')
    p.add_argument('--execute', action='store_true', help='Authorize GitHub repository, push and release writes')
    args = p.parse_args(argv)
    try:
        result = publish(ROOT, args.repo, args.visibility) if args.execute else plan(ROOT, args.repo, args.visibility)
    except (ValueError, PublishError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
