#!/usr/bin/env python3
"""Validate published patch queues, or replay them using read-only borrowed Git objects."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = ('.apk', '.apex', '.jar', '.dex', '.odex', '.vdex', '.so', '.img', '.idsig')
REPOSITORY_EXCLUSIONS = BINARY_SUFFIXES + ('.zip', '.xz', '.tar.gz', '.ttf', '.otf', '.woff', '.woff2', '.pk8', '.p12', '.pfx', '.jks', '.keystore')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in name or '\x00' in name:
        raise ValueError('Unsafe relative path: ' + name)
    return p


def load():
    return json.loads((ROOT / 'patches/series.json').read_text())


def git(path, *args, env=None):
    return subprocess.check_output(['git', '-C', str(path), *args], env=env, text=True).strip()


def check_repository_contents():
    private_key = re.compile(rb'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----')
    token = re.compile(rb'\b(?:gh[opusr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b')
    for name in git(ROOT, 'ls-files', '-z').split('\x00'):
        if not name:
            continue
        path = ROOT / safe_path(name)
        assert not name.lower().endswith(REPOSITORY_EXCLUSIONS), 'Binary/archive or signing input outside source-only policy: ' + name
        assert not re.search(r'\.part\d+$', name, re.IGNORECASE), 'Firmware archive chunk: ' + name
        assert not path.is_symlink(), 'Published symlink: ' + name
        if path.is_file():
            data = path.read_bytes()
            assert not private_key.search(data) and not token.search(data), name


def validate():
    index = load()
    assert index['format'] == 'g9650-source-patch-queues-v1'
    seen = set()
    count = 0
    for project in index['projects']:
        safe_path(project['path'])
        assert project['path'] not in seen
        seen.add(project['path'])
        for patch in project['patches']:
            p = ROOT / safe_path(patch['file'])
            assert p.is_file() and not p.is_symlink()
            assert sha(p) == patch['sha256'], str(p)
            text = p.read_text()
            assert text.startswith('From ') and 'diff --git ' in text
            for line in text.splitlines():
                if line.startswith('+++ b/') or line.startswith('--- a/'):
                    name = line[6:]
                    safe_path(name)
                    assert not name.endswith(BINARY_SUFFIXES), name
                    assert '/.gradle/' not in '/' + name
            subprocess.run(['git', 'apply', '--numstat', str(p)], check=True, capture_output=True)
            count += 1
        for name in project['expected_files']:
            safe_path(name)
    private_key = re.compile(rb'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----')
    token = re.compile(rb'\b(?:gh[opusr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b')
    for folder in ['scripts', 'patches', 'overlays', 'provenance', 'ci', '.github', 'docs', 'manifests']:
        for p in (ROOT / folder).rglob('*'):
            if p.is_file():
                assert not p.is_symlink(), str(p)
                assert not p.name.endswith(BINARY_SUFFIXES), str(p)
                data = p.read_bytes()
                assert not private_key.search(data) and not token.search(data), str(p)
    check_repository_contents()
    for p in (ROOT / '.github/workflows').glob('*.yml'):
        assert 'self-hosted' not in p.read_text(), 'Public workflows must use hosted runners'
    manifest = ET.parse(ROOT / 'manifests/pinned.xml').getroot()
    paths = [p.get('path', p.get('name')) for p in manifest.findall('project')]
    assert len(paths) == len(set(paths)), 'Duplicate pinned project paths'
    bases = {p.get('path', p.get('name')): p.get('revision') for p in manifest.findall('project')}
    for path, revision in bases.items():
        safe_path(path)
        assert re.fullmatch('[a-f0-9]{40}', revision), 'Unpinned project: ' + path
    for project in index['projects']:
        if project['kind'] == 'repo':
            assert bases[project['path']] == project['base'], 'Patch/manifest baseline mismatch: ' + project['path']
    for p in ROOT.rglob('*.xml'):
        if '.git' not in p.parts:
            ET.parse(p)
    print('Validated %s queues and %s source patches.' % (len(seen), count))
    return index


def matches(project, source):
    if not project['expected_files']:
        return git(source / project['path'], 'rev-parse', 'HEAD^{tree}') == project['head_tree']
    for name, expected in project['expected_files'].items():
        p = source / project['path'] / name
        if expected['type'] == 'absent':
            if p.exists() or p.is_symlink():
                return False
        elif expected['type'] == 'symlink':
            if not p.is_symlink() or str(p.readlink()) != expected['target']:
                return False
        elif not p.is_file() or sha(p) != expected['sha256']:
            return False
    return True


def verify_source(source):
    index = validate()
    for project in index['projects']:
        if project['kind'] != 'kernel':
            assert (source / project['path']).is_dir(), project['path']
            assert matches(project, source), 'Source differs from exported queue: ' + project['path']
            target = source / project['path']
            assert not git(target, 'diff', '--name-only'), 'Uncommitted source edits: ' + project['path']
            assert not git(target, 'diff', '--cached', '--name-only'), 'Staged source edits: ' + project['path']
    patched = {p['path'] for p in index['projects']}
    def check_baseline(project):
        path = project.get('path', project.get('name'))
        if path in patched or path == 'g9650-upstream/restless':
            return
        assert git(source / path, 'rev-parse', 'HEAD') == project.get('revision'), 'Upstream baseline drift: ' + path
    with ThreadPoolExecutor(max_workers=24) as pool:
        list(pool.map(check_baseline, ET.parse(ROOT / 'manifests/pinned-base.xml').getroot().findall('project')))
    for p in (ROOT / 'overlays').rglob('*'):
        if p.is_file():
            live = source / p.relative_to(ROOT / 'overlays')
            assert live.is_file() and sha(live) == sha(p), str(live)
    print('Existing Android source matches every exported source fingerprint.')


def replay(source, kernel=None):
    index = validate()
    checked = 0
    with tempfile.TemporaryDirectory(prefix='g9650-patch-replay-') as directory:
        for project in index['projects']:
            if project['kind'] == 'kernel':
                if kernel is None:
                    continue
                original = kernel
            else:
                original = source / project['path']
            bare = Path(directory) / project['path'].replace('/', '__')
            subprocess.run(['git', 'init', '--bare', '--quiet', str(bare)], check=True)
            common = Path(git(original, 'rev-parse', '--git-common-dir'))
            if not common.is_absolute():
                common = original / common
            (bare / 'objects/info/alternates').write_text(str((common / 'objects').resolve()) + '\n')
            env = os.environ.copy()
            env['GIT_INDEX_FILE'] = str(bare / 'replay.index')
            git(bare, 'read-tree', project['base'], env=env)
            for patch in project['patches']:
                subprocess.run(['git', '-C', str(bare), 'apply', '--cached', '--whitespace=nowarn',
                                str(ROOT / patch['file'])], env=env, check=True)
            tree = git(bare, 'write-tree', env=env)
            filters = ['.', *[':(exclude)**/*' + suffix for suffix in BINARY_SUFFIXES],
                       *[':(exclude)' + p for p in project.get('excluded_paths', [])]]
            differences = git(bare, 'diff', '--name-only', project['validated_head'], tree,
                              '--', *filters, env=env)
            assert not differences, project['path'] + ': ' + differences
            checked += 1
            print('Replay passed: ' + project['path'], flush=True)
    print('All %s source trees reproduced; original checkouts were not written.' % checked)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path)
    p.add_argument('--replay-source', type=Path)
    p.add_argument('--kernel', type=Path)
    args = p.parse_args()
    if args.replay_source:
        replay(args.replay_source.resolve(), args.kernel.resolve() if args.kernel else None)
    elif args.source:
        verify_source(args.source.resolve())
    else:
        validate()


if __name__ == '__main__':
    main()
