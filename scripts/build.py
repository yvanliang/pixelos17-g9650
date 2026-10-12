#!/usr/bin/env python3
"""Run a guarded incremental SYSTEM build. Never flash, format, clean, or sync implicitly."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from validate import ROOT, verify_source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=32)
    p.add_argument('--result-dir', type=Path, required=True)
    p.add_argument('--preflight', action='store_true')
    args = p.parse_args()
    source = args.source.resolve()
    result_dir = args.result_dir.resolve()
    result_dir.mkdir(parents=True, exist_ok=True)
    verify_source(source)
    for name in ['device/g9650/compat/camera/Camera-93.apk',
                 'vendor/pixel/gms/common/g9650-legacy/PrebuiltGmsCoreVic.apk',
                 'vendor/hardware_overlay/TrebleApp/app.apk']:
        assert (source / name).is_file(), 'Missing original/generated build input: ' + name
    assert shutil.disk_usage(source).free >= 60 * 1024**3, 'Incremental build needs 60 GiB free; keep the 40 GiB reserve'
    lock_path = Path(os.environ.get('G9650_BUILD_LOCK', str(source / '.g9650-build.lock')))
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        env = os.environ.copy()
        env['OUT_DIR'] = 'out'
        env['USE_CCACHE'] = 'false'
        env['PYTHONNOUSERSITE'] = '1'
        env.pop('M4', None)
        env.pop('BISON_PKGDATADIR', None)
        env.pop('GH_TOKEN', None)
        env.pop('GITHUB_TOKEN', None)
        if env.get('G9650_TOOL_PATH'):
            env['PATH'] = env['G9650_TOOL_PATH'] + ':' + env['PATH']
        for key in ['TMPDIR', 'XDG_CACHE_HOME']:
            if env.get(key):
                Path(env[key]).mkdir(parents=True, exist_ok=True)
        jobs = min(args.jobs, len(os.sched_getaffinity(0)))
        command = 'set -eo pipefail\nsource build/envsetup.sh\nlunch custom_g9650-cp2a-userdebug\nm %s -j%s\n' % ('nothing' if args.preflight else 'systemimage', jobs)
        with (result_dir / 'build.log').open('w') as log:
            process = subprocess.Popen(['bash', '--noprofile', '--norc', '-c', command], cwd=source,
                                       env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            def stop(signum, frame):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                raise SystemExit(128 + signum)
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            while process.poll() is None:
                if shutil.disk_usage(source).free < 40 * 1024**3:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=30)
                    raise RuntimeError('Stopped this build at the 40 GiB disk reserve')
                time.sleep(5)
            assert process.returncode == 0, 'Build failed; see ' + str(result_dir / 'build.log')
        report = {'state': 'preflight-passed' if args.preflight else 'systemimage-built',
                  'source_repository': 'yvanliang/pixelos17-g9650', 'jobs': jobs,
                  'code_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
                  'clean_performed': False, 'phone_written': False,
                  'completed_at': datetime.now(timezone.utc).isoformat()}
        if not args.preflight:
            image = source / 'out/target/product/tdgsi_arm64_ab/system.img'
            assert image.stat().st_size == 4762632192
            with image.open('rb') as stream:
                h = hashlib.sha256()
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                    h.update(chunk)
            report.update(image=str(image.resolve()), image_bytes=image.stat().st_size, image_sha256=h.hexdigest())
        (result_dir / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
