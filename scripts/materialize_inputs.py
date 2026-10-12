#!/usr/bin/env python3
"""Provision original signed APK inputs privately; no APK is committed to this repo."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from validate import ROOT


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def install(original, target, expected):
    assert digest(original) == expected, 'Unexpected APK content: ' + str(original)
    if target.exists():
        assert digest(target) == expected, 'Refusing to replace an unreviewed APK: ' + str(target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--camera-apk', type=Path)
    parser.add_argument('--gms-apk', type=Path)
    parser.add_argument('--fsck-erofs', default='fsck.erofs')
    args = parser.parse_args()
    source = args.source.resolve()
    inputs = json.loads((ROOT / 'provenance/external-inputs.json').read_text())
    for item in inputs:
        target = source / item['path']
        if item['path'].startswith('vendor/hardware_overlay/TrebleApp/'):
            continue  # Compiled from the exported TrebleApp source separately.
        if target.is_file() and digest(target) == item['sha256']:
            print('Original input already present: ' + item['path'])
            continue
        if item['path'].endswith('Camera-93.apk'):
            assert args.camera_apk, 'Supply the original GrapheneOS Camera 93 APK with --camera-apk'
            install(args.camera_apk, target, item['sha256'])
        elif args.gms_apk:
            install(args.gms_apk, target, item['sha256'])
        else:
            apex = source / item['source_apex']
            assert digest(apex) == item['source_apex_sha256'], 'Unexpected upstream GMS APEX'
            with tempfile.TemporaryDirectory(prefix='g9650-original-gms-') as directory:
                directory = Path(directory)
                with zipfile.ZipFile(apex) as archive:
                    with archive.open('apex_payload.img') as input_stream, (directory / 'payload.img').open('wb') as out:
                        shutil.copyfileobj(input_stream, out)
                extracted = directory / 'extracted'
                subprocess.run([args.fsck_erofs, '--extract=' + str(extracted), str(directory / 'payload.img')], check=True)
                install(extracted / item['payload_path'], target, item['sha256'])
        print('Provisioned original signed input: ' + item['path'])


if __name__ == '__main__':
    main()
