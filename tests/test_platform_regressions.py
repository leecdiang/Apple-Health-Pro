"""Optional GUI services and packaging must fail safely at their boundaries."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import psutil
import pytest
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication
from healthpro.dates import DateField
from healthpro.gui import MainWindow


@pytest.fixture(scope='module')
def app():
    result = QApplication.instance() or QApplication([])
    result.setQuitOnLastWindowClosed(False)
    return result


@pytest.mark.parametrize('target', [
    'psutil.Process', 'psutil.cpu_count', 'psutil.virtual_memory',
    'psutil.Process.cpu_percent',
])
def test_hud_startup_failure_and_recovery(app, target):
    with patch(target, side_effect=psutil.AccessDenied(pid=123)):
        window = MainWindow()
        window.show()
        app.processEvents()
        assert window.resource_hud.process is None
        assert window.resource_hud.cpu_label.text() == '—'
        assert window.resource_hud.ram_label.text() == '—'
    window.resource_hud.sample()
    assert window.resource_hud.process is not None
    assert window.resource_hud.cpu_label.text() != '—'
    assert not window.windowIcon().isNull()
    window.close()
    window.deleteLater()
    app.processEvents()


def test_calendar_stays_within_python_date_range(app):
    field = DateField()
    for boundary, offset, invalid in [(QDate(9999, 12, 31), 1, QDate(10000, 1, 1)),
                                      (QDate(1, 1, 1), -1, QDate(-1, 12, 31))]:
        field.setDate(boundary)
        field.open_calendar()
        popup = field.popup
        before = popup.month
        popup.shift_month(offset)
        assert popup.month == before
        assert not (popup.next if offset > 0 else popup.previous).isEnabled()
        assert all(button.isEnabled() == (1 <= button.day.year() <= 9999) for button in popup.days)
        popup.focus_day(invalid)
        popup.choose(invalid)
        field.setDate(invalid)
        assert field.date() == boundary
        assert field.date().toPyDate().year == boundary.year()
        popup.close()
    field.deleteLater()
    app.processEvents()


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux packaging scripts')
@pytest.mark.parametrize('script', ['build_deb.sh', 'build_appimage.sh'])
def test_packaging_rebuilds_existing_dist_and_stops_if_build_fails(tmp_path, script):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'linux').mkdir()
    shutil.copyfile(root / 'linux' / script, tmp_path / 'linux' / script)
    (tmp_path / 'dist/healthpro').mkdir(parents=True)
    (tmp_path / 'dist/healthpro/healthpro').write_text('stale executable')
    # Intercept package installation/build, never download or execute old payloads.
    shim = tmp_path / 'bin'
    shim.mkdir()
    python = shim / 'python3'
    python.write_text('#!/bin/sh\n'
                      'if [ "$1" = "-c" ]; then echo 8.9.0; exit 0; fi\n'
                      'if [ "$2" = "pip" ]; then exit 0; fi\n'
                      'if [ "$2" = "PyInstaller" ]; then echo rebuild-invoked; exit 77; fi\n'
                      'exit 99\n')
    python.chmod(0o755)
    env = dict(os.environ, PATH=str(shim) + os.pathsep + os.environ['PATH'])
    result = subprocess.run(['bash', str(tmp_path / 'linux' / script)],
                            env=env, text=True, capture_output=True)
    assert result.returncode == 77
    assert 'rebuild-invoked' in result.stdout
    assert not (tmp_path / 'build').exists()


@pytest.mark.parametrize('spec', ['HealthPro.spec', 'HealthPro_linux.spec'])
def test_frozen_specs_bundle_window_icon(spec):
    # Evaluate spec with PyInstaller build primitives replaced by recording stubs.
    root = Path(__file__).resolve().parents[1]
    analyses = []
    class Analysis:
        def __init__(self, *args, **kwargs):
            analyses.append(kwargs)
            self.pure = self.scripts = self.binaries = self.datas = []
    namespace = {'SPECPATH': str(root), 'Analysis': Analysis,
                 'PYZ': lambda *a, **kw: None, 'EXE': lambda *a, **kw: None,
                 'COLLECT': lambda *a, **kw: None}
    with patch.object(sys, 'platform', 'linux'):
        exec(compile((root / spec).read_text(), spec, 'exec'), namespace)
    assert (str(root / 'icon.png'), '.') in analyses[0]['datas']


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux packaging scripts')
def test_appimage_corrupt_cached_tool_fails_before_execution(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'linux').mkdir()
    shutil.copyfile(root / 'linux/build_appimage.sh', tmp_path / 'linux/build_appimage.sh')
    (tmp_path / 'build').mkdir()
    tool = tmp_path / 'build/appimagetool-1.9.1-x86_64.AppImage'
    tool.write_text('#!/bin/sh\necho EXECUTED_UNVERIFIED_TOOL\n')
    tool.chmod(0o755)
    shim = tmp_path / 'bin'
    shim.mkdir()
    python = shim / 'python3'
    python.write_text('#!/bin/sh\nif [ "$1" = "-c" ]; then echo 8.9.1; fi\nexit 0\n')
    python.chmod(0o755)
    env = dict(os.environ, PATH=str(shim) + os.pathsep + os.environ['PATH'])
    result = subprocess.run(['bash', str(tmp_path / 'linux/build_appimage.sh')],
                            env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert 'EXECUTED_UNVERIFIED_TOOL' not in result.stdout + result.stderr
    assert not (tmp_path / 'build/HealthPro.AppDir').exists()
