#!/usr/bin/env python3
"""Export committed adaptation changes using the baselines in patches/series.json."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from validate import ROOT, REPOSITORY_EXCLUSIONS, git, load, safe_path, sha


def export_project(project, checkout, destination):
    assert not git(checkout, 'diff', '--name-only'), 'Commit source edits first: ' + str(checkout)
    assert not git(checkout, 'diff', '--cached', '--name-only'), 'Commit staged edits first: ' + str(checkout)
    base = project['base']
    head = git(checkout, 'rev-parse', 'HEAD')
    assert git(checkout, 'rev-parse', base + '^{tree}') == project['base_tree'], 'Baseline tree mismatch'
    subprocess.run(['git', '-C', str(checkout), 'merge-base', '--is-ancestor', base, head], check=True)
    changes = git(checkout, 'diff', '--name-only', '-z', base, head).split('\x00')
    excluded = project.get('excluded_paths', [])
    filters = ['.', *[':(exclude,icase,glob)**/*' + ext for ext in REPOSITORY_EXCLUSIONS],
               *[':(exclude)' + name for name in excluded]]
    folder = destination / 'patches/projects' / project['path'].replace('/', '__')
    folder.mkdir(parents=True)
    subprocess.run(['git', '-C', str(checkout), 'format-patch', '--quiet', '--no-signature',
                    '--binary', '--output-directory', str(folder), base + '..' + head,
                    '--', *filters], check=True)
    expected = {}
    for name in changes:
        if not name:
            continue
        safe_path(name)
        if name.lower().endswith(REPOSITORY_EXCLUSIONS) or any(name == x or name.startswith(x + '/') for x in excluded):
            continue
        file = checkout / name
        if file.is_symlink():
            expected[name] = {'type': 'symlink', 'target': os.readlink(str(file))}
        elif file.is_file():
            expected[name] = {'type': 'file', 'sha256': sha(file)}
        else:
            expected[name] = {'type': 'absent'}
    result = copy.deepcopy(project)
    result.update(validated_head=head, head_tree=git(checkout, 'rev-parse', 'HEAD^{tree}'),
                  expected_files=expected,
                  patches=[{'file': str(file.relative_to(destination)), 'sha256': sha(file)}
                           for file in sorted(folder.glob('*.patch'))])
    for item in result['patches']:
        subprocess.run(['git', 'apply', '--numstat', str(destination / item['file'])],
                       check=True, capture_output=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--write', action='store_true', help='Replace exported queues after staging every project successfully')
    args = parser.parse_args()
    source = args.source.resolve()
    index = load()
    with tempfile.TemporaryDirectory(prefix='g9650-source-export-') as directory:
        staged = Path(directory)
        exported = []
        changed = []
        for project in index['projects']:
            checkout = args.kernel.resolve() if project['kind'] == 'kernel' else source / safe_path(project['path'])
            result = export_project(project, checkout, staged)
            exported.append(result)
            if result != project:
                changed.append(project['path'])
        overlay = source / 'device/g9650/compat'
        assert overlay.is_dir(), 'Missing device overlay source'
        published = staged / 'overlays/device/g9650/compat'
        published.mkdir(parents=True)
        for file in overlay.rglob('*'):
            if not file.is_file() and not file.is_symlink():
                continue
            if file.name.lower().endswith(REPOSITORY_EXCLUSIONS):
                continue
            assert not file.is_symlink(), 'Review overlay symlinks manually: ' + str(file)
            target = published / file.relative_to(overlay)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
        if args.write:
            for project in exported:
                relative = Path('patches/projects') / project['path'].replace('/', '__')
                target = ROOT / relative
                target.mkdir(parents=True, exist_ok=True)
                for file in target.glob('*.patch'):
                    file.unlink()
                for file in (staged / relative).glob('*.patch'):
                    shutil.copy2(file, target / file.name)
            target = ROOT / 'overlays/device/g9650/compat'
            for file in target.rglob('*'):
                if file.is_file() and not (published / file.relative_to(target)).exists():
                    file.unlink()
            shutil.copytree(published, target, dirs_exist_ok=True)
            index['projects'] = exported
            (ROOT / 'patches/series.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'written': args.write, 'changed_queues': changed,
                          'queues': len(exported), 'patches': sum(len(p['patches']) for p in exported),
                          'scope': 'existing queue baselines and device overlays; no sync, build, or push'}, indent=2))


if __name__ == '__main__':
    main()
