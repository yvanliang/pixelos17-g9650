#!/usr/bin/env python3
"""Apply audited queues to clean baselines; resume only an exact previously recorded queue."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from validate import ROOT, git, load, matches, sha, validate, verify_source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--snapshot', type=Path)
    args = p.parse_args()
    source = args.source.resolve()
    assert (source / 'build/envsetup.sh').is_file()
    snapshot = args.snapshot or source / 'g9650-upstream/restless'
    index = validate()
    stamp = source / '.g9650-applied-queues.json'
    previous = json.loads(stamp.read_text()) if stamp.exists() else {}
    recorded = {}
    for project in index['projects']:
        if project['kind'] == 'kernel':
            continue
        target = source / project['path']
        if not target.exists() and project['kind'] == 'snapshot':
            assert git(snapshot, 'rev-parse', 'HEAD') == index['snapshot']['revision']
            shutil.copytree(snapshot / project['snapshot_path'], target)
            subprocess.run(['git', 'init', '--quiet', str(target)], check=True)
            subprocess.run(['git', '-C', str(target), 'add', '-A'], check=True)
            subprocess.run(['git', '-C', str(target), '-c', 'user.name=G9650 adaptation',
                            '-c', 'user.email=42460514+yvanliang@users.noreply.github.com',
                            'commit', '--quiet', '-m', 'Import pinned compatibility source snapshot'], check=True)
            assert git(target, 'rev-parse', 'HEAD^{tree}') == project['base_tree']
        assert not git(target, 'diff', '--name-only'), 'Tracked worktree edits: ' + str(target)
        assert not git(target, 'diff', '--cached', '--name-only'), 'Staged edits: ' + str(target)
        fingerprints = [x['sha256'] for x in project['patches']]
        old = previous.get(project['path'], [])
        if matches(project, source):
            recorded[project['path']] = fingerprints
            continue
        if old:
            assert fingerprints[:len(old)] == old, 'Queue changed; prepare a fresh baseline or explicitly rebase: ' + project['path']
            todo = project['patches'][len(old):]
        else:
            assert git(target, 'rev-parse', 'HEAD^{tree}') == project['base_tree'], 'Unexpected baseline: ' + project['path']
            todo = project['patches']
        for patch in todo:
            # No automatic conflict resolution or silently discarded compatibility fixes.
            subprocess.run(['git', '-C', str(target), '-c', 'user.name=G9650 adaptation',
                            '-c', 'user.email=42460514+yvanliang@users.noreply.github.com',
                            'am', str(ROOT / patch['file'])], check=True)
        assert matches(project, source), 'Replayed source fingerprint mismatch: ' + project['path']
        recorded[project['path']] = fingerprints
        stamp.write_text(json.dumps({**previous, **recorded}, indent=2) + '\n')
    for file in (ROOT / 'overlays').rglob('*'):
        if not file.is_file():
            continue
        destination = source / file.relative_to(ROOT / 'overlays')
        if destination.exists():
            assert sha(destination) == sha(file), 'Unreviewed device overlay: ' + str(destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
    stamp.write_text(json.dumps(recorded, indent=2) + '\n')
    verify_source(source)


if __name__ == '__main__':
    main()
