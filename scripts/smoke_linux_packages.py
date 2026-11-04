"""Verify the final Linux package payloads, using synthetic demo records only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(version):
    root = Path(__file__).resolve().parents[1]
    deb_version = version.replace('rc', '~rc', 1)
    deb = root / 'build' / f'healthpro_{deb_version}_amd64.deb'
    appimage = root / 'dist' / f'HealthPro-{version}-x86_64.AppImage'
    actual = subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Version'], text=True).strip()
    assert actual == deb_version, (actual, deb_version)
    with tempfile.TemporaryDirectory(prefix='HealthPro-package-smoke-') as temp:
        temp = Path(temp)
        unpacked = temp / 'deb'
        subprocess.run(['dpkg-deb', '-x', str(deb), str(unpacked)], check=True)
        commands = {
            'deb': [str(unpacked / 'opt/healthpro/healthpro')],
            'appimage': [str(appimage), '--appimage-extract-and-run'],
        }
        for name, command in commands.items():
            report = temp / f'{name}.json'
            subprocess.run(command + ['--smoke-test', str(report)], check=True,
                           timeout=60, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
            result = json.loads(report.read_text())
            assert result['success'] and result['cleanup'], result
            assert result['indexed'] == result['exported'] == 217, result
            assert result['app_version'] == version, result
            print(f'{name} final package smoke passed: {version}, 217 synthetic records')


if __name__ == '__main__':
    run(sys.argv[1])
