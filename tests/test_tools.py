from __future__ import annotations
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/novelai-prompt-studio'
sys.path.insert(0,str(ROOT/'tools'))
import repo_utils
import install_skill
import publish_github
from validate_repo import validate


class LocalToolTests(unittest.TestCase):
    def test_repository_validation(self):
        self.assertEqual(validate(ROOT)['offline_validation'],'passed')

    def test_manifest_has_core_skill(self):
        self.assertIn('skills/novelai-prompt-studio/SKILL.md',repo_utils.manifest_files(ROOT))

    def test_unsafe_manifest_paths_rejected(self):
        for name in ('../secret','/etc/passwd','private/a.md','tools/../../a.md','tools\\x.py','.git/config','.env'):
            with self.subTest(name=name),self.assertRaises(ValueError):repo_utils.safe_file(ROOT,name)

    def test_symlinked_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'tools').mkdir();(p/'README.md').write_text('safe')
            (p/'tools/link.py').symlink_to(p/'README.md')
            with self.assertRaises(ValueError):repo_utils.safe_file(p,'tools/link.py')

    def test_symlinked_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'real').mkdir();(p/'real/x.py').write_text('x=1')
            (p/'tools').symlink_to(p/'real',target_is_directory=True)
            with self.assertRaises(ValueError):repo_utils.safe_file(p,'tools/x.py')

    def test_archives_are_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            a=repo_utils.build_archives(ROOT,Path(d)/'a');b=repo_utils.build_archives(ROOT,Path(d)/'b')
            for key in a:self.assertEqual(a[key].read_bytes(),b[key].read_bytes())

    def test_only_manifest_files_in_source_archive(self):
        with tempfile.TemporaryDirectory() as d:
            paths=repo_utils.build_archives(ROOT,Path(d))
            with zipfile.ZipFile(paths['source']) as z:
                self.assertEqual(set(z.namelist()),{'novelai-prompt-studio/'+n for n in repo_utils.manifest_files(ROOT)})

    def test_standalone_archive_has_no_publish_tools(self):
        with tempfile.TemporaryDirectory() as d:
            paths=repo_utils.build_archives(ROOT,Path(d))
            with zipfile.ZipFile(paths['skill']) as z:
                self.assertIn('novelai-prompt-studio/SKILL.md',z.namelist())
                self.assertIn('novelai-prompt-studio/LICENSE',z.namelist())
                self.assertFalse(any('publish_github' in n for n in z.namelist()))

    def test_unlisted_private_material_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'snapshot';repo_utils.snapshot(ROOT,source)
            (source/'private').mkdir();(source/'private'/'note.md').write_text('not for distribution')
            paths=repo_utils.build_archives(source,p/'out')
            with zipfile.ZipFile(paths['source']) as z:self.assertFalse(any('/private/' in n for n in z.namelist()))

    def test_snapshot_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):repo_utils.snapshot(ROOT,Path(d))

    def test_checksums_match_archives(self):
        with tempfile.TemporaryDirectory() as d:
            paths=repo_utils.build_archives(ROOT,Path(d))
            for line in paths['checksums'].read_text().splitlines():
                digest,name=line.split('  ')
                self.assertEqual(digest,hashlib.sha256((Path(d)/name).read_bytes()).hexdigest())

    def test_checksum_output_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out';out.mkdir();sentinel=Path(d)/'keep.txt';sentinel.write_text('keep')
            (out/'SHA256SUMS.txt').symlink_to(sentinel)
            with self.assertRaises(ValueError):repo_utils.build_archives(ROOT,out)
            self.assertEqual(sentinel.read_text(),'keep')

    def test_install_is_self_contained(self):
        with tempfile.TemporaryDirectory() as d:
            target=install_skill.install(ROOT,Path(d))
            p=subprocess.run([sys.executable,str(target/'scripts/lint_prompt.py'),str(target/'examples/portrait.json'),'--strict'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertTrue((target/'LICENSE').exists())

    def test_install_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target=install_skill.install(ROOT,Path(d));sentinel=target/'local-note';sentinel.write_text('keep')
            with self.assertRaises(ValueError):install_skill.install(ROOT,Path(d))
            self.assertEqual(sentinel.read_text(),'keep')

    def test_lint_cli_json(self):
        p=subprocess.run([sys.executable,str(SKILL/'scripts/lint_prompt.py'),str(SKILL/'examples/portrait.json'),'--format','json'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0);self.assertTrue(json.loads(p.stdout)['ok'])

    def test_cli_missing_file_returns_input_error(self):
        p=subprocess.run([sys.executable,str(SKILL/'scripts/lint_prompt.py'),'/nonexistent/nai-record.json'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertNotIn('Traceback',p.stderr)

    def test_strict_cli_fails_on_unknown_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'record.json';v={'schema_version':1,'model':'unknown','quality_tags':'unknown','uc_preset':'unknown','base_prompt':'portrait'}
            p.write_text(json.dumps(v))
            result=subprocess.run([sys.executable,str(SKILL/'scripts/lint_prompt.py'),str(p),'--strict'],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)

    def test_diff_cli(self):
        p=subprocess.run([sys.executable,str(SKILL/'scripts/diff_prompt.py'),str(SKILL/'examples/portrait.json'),str(SKILL/'examples/portrait-refined.json'),'--format','json'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0);self.assertTrue(json.loads(p.stdout)['ok'])


class FakeGitHub:
    """Offline command responses only. No git or gh command is executed."""
    def __init__(self, failure=None):
        self.failure=failure;self.calls=[];self.assets=[];self.commit='a'*40
    def __call__(self,args,*,cwd=None):
        self.calls.append(args)
        def result(data='',code=0,err=''):
            return subprocess.CompletedProcess(args,code,json.dumps(data) if isinstance(data,(dict,list)) else data,err)
        if args[:3]==['gh','api','user']:
            return result({'login':'different' if self.failure=='account' else 'test-user','id':42})
        if args==['gh','api','repos/test-user/nai-test']:
            if self.failure=='existing':return result({'name':'nai-test'})
            if self.failure=='unknown_access':return result('',1,'HTTP 403')
            return result('',1,'gh: Not Found (HTTP 404)')
        if args[:3]==['git','rev-parse','HEAD']:return result(self.commit)
        if args[0]==sys.executable and self.failure=='tests':return result('',1,'test failure')
        if args[0]=='git' and 'push' in args and self.failure=='push':return result('',1,'remote rejected')
        if args[:3]==['gh','release','create']:
            self.assets=[Path(x) for x in args[4:args.index('--repo')]]
        if args[:3]==['gh','repo','view']:
            return result({'nameWithOwner':'test-user/nai-test','visibility':'PRIVATE','url':'https://github.com/test-user/nai-test'})
        if args[:3]==['gh','api','repos/test-user/nai-test/commits/main']:
            return result({'sha':'b'*40 if self.failure=='commit' else self.commit})
        if args[:3]==['gh','api','repos/test-user/nai-test/git/ref/tags/v1.0.0']:
            return result({'object':{'type':'tag','sha':'c'*40}})
        if args[:3]==['gh','api','repos/test-user/nai-test/git/tags/'+'c'*40]:
            return result({'object':{'type':'commit','sha':self.commit}})
        if args[:3]==['gh','release','view']:
            return result({'url':'https://github.com/test-user/nai-test/releases/tag/v1.0.0','tagName':'v1.0.0',
                           'assets':[{'name':p.name,'size':0 if self.failure=='assets' else p.stat().st_size} for p in self.assets]})
        return result('')


class PublishingSafeguardTests(unittest.TestCase):
    def run_fake(self,failure=None):
        fake=FakeGitHub(failure)
        with patch('publish_github.shutil.which',return_value='/mock/tool'):
            result=publish_github.publish(ROOT,'test-user/nai-test','private',fake)
        return result,fake

    def test_default_plan_performs_no_remote_write(self):
        with patch('publish_github.publish') as publisher,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(publish_github.main(['--repo','test-user/nai-test']),0)
        publisher.assert_not_called();result=json.loads(out.getvalue())
        self.assertFalse(result['remote_writes']);self.assertEqual(result['visibility'],'private')

    def test_bad_repository_name_rejected(self):
        for value in ('https://github.com/a/b','../repo','a/b;rm -rf','a/b/c'):
            with self.subTest(value=value),self.assertRaises(ValueError):publish_github.plan(ROOT,value,'private')

    def test_missing_gh_is_reported(self):
        with patch('publish_github.shutil.which',return_value=None),self.assertRaises(publish_github.PublishError):
            publish_github.publish(ROOT,'test-user/nai-test','private',FakeGitHub())

    def test_full_flow_with_mocked_remote_verification(self):
        result,fake=self.run_fake()
        self.assertEqual(result['status'],'published_and_verified')
        self.assertEqual(result['commit'],'a'*40)
        self.assertTrue(any(c[:3]==['gh','repo','create'] for c in fake.calls))
        self.assertFalse(any('--force' in c or '--global' in c for c in fake.calls))

    def test_account_mismatch_prevents_creation(self):
        fake=FakeGitHub('account')
        with patch('publish_github.shutil.which',return_value='/mock/tool'),self.assertRaises(publish_github.PublishError):
            publish_github.publish(ROOT,'test-user/nai-test','private',fake)
        self.assertFalse(any(c[:3]==['gh','repo','create'] for c in fake.calls))

    def test_existing_repository_never_overwritten(self):
        fake=FakeGitHub('existing')
        with patch('publish_github.shutil.which',return_value='/mock/tool'),self.assertRaises(publish_github.PublishError):
            publish_github.publish(ROOT,'test-user/nai-test','private',fake)
        self.assertFalse(any(c[:3]==['gh','repo','create'] for c in fake.calls))

    def test_unknown_access_not_treated_as_missing(self):
        fake=FakeGitHub('unknown_access')
        with patch('publish_github.shutil.which',return_value='/mock/tool'),self.assertRaises(publish_github.PublishError):
            publish_github.publish(ROOT,'test-user/nai-test','private',fake)
        self.assertFalse(any(c[:3]==['gh','repo','create'] for c in fake.calls))

    def test_tests_fail_before_remote_creation(self):
        fake=FakeGitHub('tests')
        with patch('publish_github.shutil.which',return_value='/mock/tool'),self.assertRaises(publish_github.PublishError):
            publish_github.publish(ROOT,'test-user/nai-test','private',fake)
        self.assertFalse(any(c[:3]==['gh','repo','create'] for c in fake.calls))

    def test_push_failure_reports_partial_state(self):
        fake=FakeGitHub('push')
        with patch('publish_github.shutil.which',return_value='/mock/tool'),self.assertRaisesRegex(publish_github.PublishError,'remote_repository_created'):
            publish_github.publish(ROOT,'test-user/nai-test','private',fake)
        self.assertFalse(any(c[:3]==['gh','release','create'] for c in fake.calls))
        self.assertFalse(any('delete' in c for c in fake.calls))

    def test_wrong_remote_commit_not_claimed_success(self):
        with self.assertRaisesRegex(publish_github.PublishError,'Remote main commit'):self.run_fake('commit')

    def test_wrong_asset_sizes_not_claimed_success(self):
        with self.assertRaisesRegex(publish_github.PublishError,'asset names/sizes'):self.run_fake('assets')


if __name__=='__main__':unittest.main()
