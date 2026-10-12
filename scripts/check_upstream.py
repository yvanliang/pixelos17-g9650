#!/usr/bin/env python3
"""Check the official manifest and patched branch tips; never change locked baselines."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from validate import ROOT, load


def gh(*args, payload=None):
    result = subprocess.run(['gh', *args], input=json.dumps(payload) if payload is not None else None,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def remote_tip(item):
    label, url, ref, base = item
    result = subprocess.run(['git', 'ls-remote', url, ref], capture_output=True, text=True,
                            check=True, timeout=90)
    tips = [line.split()[0] for line in result.stdout.splitlines()]
    if len(tips) != 1:
        raise RuntimeError('Cannot resolve upstream: ' + label + ' ' + ref)
    return None if tips[0] == base else {'project': label, 'url': url, 'ref': ref,
                                       'validated': base, 'upstream': tips[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issue', action='store_true')
    args = parser.parse_args()
    provenance = json.loads((ROOT / 'provenance/upstream.json').read_text())
    items = [('PixelOS manifest', provenance['manifest_url'], 'refs/heads/seventeen',
              provenance['validated_manifest_commit'])]
    manifest = ET.parse(ROOT / 'manifests/pinned-base.xml').getroot()
    remotes = {r.get('name'): r.get('fetch').rstrip('/') for r in manifest.findall('remote')}
    default = manifest.find('default')
    projects = {p.get('path', p.get('name')): p for p in manifest.findall('project')}
    for queue in load()['projects']:
        if queue['kind'] != 'repo':
            continue
        project = projects[queue['path']]
        ref = project.get('upstream', project.get('dest-branch', ''))
        if not ref or ref.startswith('refs/tags/'):
            continue
        if not ref.startswith('refs/'):
            ref = 'refs/heads/' + ref
        remote = project.get('remote', default.get('remote'))
        items.append((queue['path'], remotes[remote] + '/' + project.get('name'), ref, queue['base']))
    with ThreadPoolExecutor(max_workers=6) as pool:
        changes = [change for change in pool.map(remote_tip, items) if change]
    result = {'checked_refs': len(items), 'changes': changes,
              'scope': 'official manifest and branches of patched manifest projects',
              'automatic_merge': False, 'rom_build': False}
    print(json.dumps(result, indent=2))
    body = '## PixelOS upstream check\n\nChecked %s refs. Locked baselines were not changed.\n\n' % len(items)
    if changes:
        body += '\n'.join('- `%s`: `%s` → `%s` (%s)' %
                          (c['project'], c['validated'][:12], c['upstream'][:12], c['ref']) for c in changes)
        body += '\n\nFollow [docs/UPDATING.md](../blob/g9650-seventeen/docs/UPDATING.md). Rebase patches and test a candidate before promoting it.\n'
    else:
        body += 'No changes in the checked refs. This does not test or compile Android.\n'
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(body)
    if args.issue and changes:
        repo = os.environ['GH_REPO']
        title = '[upstream] PixelOS seventeen updates available'
        issues = gh('issue', 'list', '--repo', repo, '--state', 'open', '--json', 'number,title')
        issue = next((i for i in issues if i['title'] == title), None)
        endpoint = 'repos/' + repo + '/issues' + ('/' + str(issue['number']) if issue else '')
        gh('api', endpoint, '--method', 'PATCH' if issue else 'POST', '--input', '-',
           payload={'title': title, 'body': body})


if __name__ == '__main__':
    main()
