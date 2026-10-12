import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate
import export_changes


class SourceToolsTest(unittest.TestCase):
    def test_export_preserves_checkout_and_excludes_generated_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()
            git('init', '--quiet')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (source / 'file.txt').write_text('before\n')
            git('add', '.')
            git('commit', '--quiet', '-m', 'baseline')
            base = git('rev-parse', 'HEAD')
            (source / 'file.txt').write_text('after\n')
            (source / 'Camera.APK').write_bytes(b'generated apk input')
            (source / 'key.pk8').write_bytes(b'private signing input')
            (source / 'build').mkdir()
            (source / 'build/cache.txt').write_text('generated cache')
            git('add', '.')
            git('commit', '--quiet', '-m', 'source and generated inputs')
            head = git('rev-parse', 'HEAD')
            queue = {'path': 'sample', 'kind': 'repo', 'base': base,
                     'base_tree': git('rev-parse', base + '^{tree}'), 'excluded_paths': ['build']}
            result = export_changes.export_project(queue, source, root / 'export')
            self.assertEqual(list(result['expected_files']), ['file.txt'])
            self.assertEqual(len(result['patches']), 1)
            contents = (root / 'export' / result['patches'][0]['file']).read_text()
            self.assertNotIn('Camera.APK', contents)
            self.assertNotIn('key.pk8', contents)
            self.assertNotIn('cache.txt', contents)
            self.assertEqual(git('rev-parse', 'HEAD'), head)
            self.assertEqual(git('status', '--porcelain'), '')
            (source / 'file.txt').write_text('uncommitted\n')
            with self.assertRaises(AssertionError):
                export_changes.export_project(queue, source, root / 'refused')

    def test_source_only_repository_rejects_payloads_and_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '--quiet', str(root)], check=True)
            (root / 'LICENSE').write_text('A permitted source license notice.\n')
            subprocess.run(['git', '-C', str(root), 'add', 'LICENSE'], check=True)
            with patch.object(validate, 'ROOT', root):
                validate.check_repository_contents()
                cases = [('payload.APK', b'binary'), ('system.img.xz', b'archive'),
                         ('archive.part01', b'chunk'),
                         ('secret.pem', b'-----BEGIN ' + b'PRIVATE KEY-----\n'),
                         ('token.txt', b'ghp_' + b'A' * 40)]
                for name, data in cases:
                    with self.subTest(name=name):
                        (root / name).write_bytes(data)
                        subprocess.run(['git', '-C', str(root), 'add', name], check=True)
                        with self.assertRaises(AssertionError):
                            validate.check_repository_contents()
                        subprocess.run(['git', '-C', str(root), 'rm', '--cached', '--quiet', name], check=True)
                        (root / name).unlink()

    def test_reject_paths_outside_checkout(self):
        for name in ['', '.', '/etc/passwd', '../secret', 'system/../../secret', 'system\\secret']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate.safe_path(name)

    def test_replay_real_patch_does_not_write_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            project = source / 'sample'
            project.mkdir(parents=True)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(project), *args], text=True).strip()
            git('init', '--quiet')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (project / 'file.txt').write_text('before\n')
            git('add', '.')
            git('commit', '--quiet', '-m', 'baseline')
            base = git('rev-parse', 'HEAD')
            (project / 'file.txt').write_text('after\n')
            git('commit', '--quiet', '-am', 'compatibility fix')
            head = git('rev-parse', 'HEAD')
            (root / 'patches').mkdir()
            exported = subprocess.check_output(['git', '-C', str(project), 'format-patch', '--stdout', base + '..' + head])
            (root / 'patches/fix.patch').write_bytes(exported)
            queue = {'path': 'sample', 'kind': 'repo', 'base': base, 'validated_head': head,
                     'patches': [{'file': 'patches/fix.patch', 'sha256': hashlib.sha256(exported).hexdigest()}],
                     'expected_files': {'file.txt': {'type': 'file', 'sha256': hashlib.sha256(b'after\n').hexdigest()}}}
            git('checkout', '--quiet', base)
            with patch.object(validate, 'ROOT', root), patch.object(validate, 'validate', return_value={'projects': [queue]}), contextlib.redirect_stdout(io.StringIO()):
                validate.replay(source)
            self.assertEqual(git('rev-parse', 'HEAD'), base)
            self.assertEqual((project / 'file.txt').read_text(), 'before\n')
            self.assertEqual(git('status', '--porcelain'), '')
            broken = copy.deepcopy(queue)
            (root / 'patches/fix.patch').write_bytes(exported.replace(b'-before', b'-wrong!'))
            with patch.object(validate, 'ROOT', root), patch.object(validate, 'validate', return_value={'projects': [broken]}):
                with self.assertRaises(subprocess.CalledProcessError):
                    validate.replay(source)
            self.assertEqual(git('status', '--porcelain'), '')

    def test_published_patch_corruption_is_rejected(self):
        index = validate.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = copy.deepcopy(index['projects'][0])
            entry['patches'] = entry['patches'][:1]
            item = entry['patches'][0]
            path = root / item['file']
            path.parent.mkdir(parents=True)
            path.write_bytes(b'tampered content\n')
            with patch.object(validate, 'ROOT', root), patch.object(validate, 'load', return_value={'format': index['format'], 'projects': [entry]}):
                with self.assertRaises(AssertionError):
                    validate.validate()


if __name__ == '__main__':
    unittest.main()
