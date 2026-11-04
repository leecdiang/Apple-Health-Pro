"""Stable and preview versions keep Debian and application versions distinct."""
import json
from pathlib import Path

import pytest
from scripts import smoke_linux_packages


@pytest.mark.parametrize('version,deb_version', [
    ('8.9.1', '8.9.1'), ('8.9.2rc1', '8.9.2~rc1'),
])
def test_final_package_smoke_normalizes_only_debian_version(monkeypatch, version, deb_version):
    calls = []
    def check_output(command, **kwargs):
        assert Path(command[2]).name == f'healthpro_{deb_version}_amd64.deb'
        return deb_version + '\n'
    def run(command, **kwargs):
        calls.append(command)
        if command[0] == 'dpkg-deb':
            assert Path(command[2]).name == f'healthpro_{deb_version}_amd64.deb'
        else:
            Path(command[-1]).write_text(json.dumps({
                'success': True, 'cleanup': True, 'indexed': 217,
                'exported': 217, 'app_version': version,
            }))
    monkeypatch.setattr(smoke_linux_packages.subprocess, 'check_output', check_output)
    monkeypatch.setattr(smoke_linux_packages.subprocess, 'run', run)
    smoke_linux_packages.run(version)
    assert len(calls) == 3
    assert Path(calls[-1][0]).name == f'HealthPro-{version}-x86_64.AppImage'
