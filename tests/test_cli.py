import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest
from healthpro import cli, core
from test_core import archive, health, record, options

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args, entry=None):
    # -S removes site packages, including Qt/psutil: this must work with stdlib only.
    command = [sys.executable, '-S'] + ([str(ROOT/entry)] if entry else ['-m', 'healthpro'])
    return subprocess.run(command + list(map(str, args)), cwd=ROOT, capture_output=True,
                          encoding='utf-8', timeout=20,
                          env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})


def jsonl_rows(result):
    return [json.loads(line) for path in result.directory.glob('*.jsonl')
            for line in path.read_text(encoding='utf-8').splitlines()]


def test_jsonl_raw_values_nested_statistics_and_checksums(tmp_path):
    workout = '<Workout workoutActivityType="HKWorkoutActivityTypeRunning" sourceName="设备" startDate="2026-10-31 12:00:00 +0800" duration="60.5" durationUnit="min"><WorkoutStatistics type="Distance" sum="1000.25" unit="m"/></Workout>'
    inputs = [record(value='0.123456789012345678901'), record(value='9007199254740993'),
              record(value='HKCategoryValueSleepAnalysisAsleepCore'), record(value='1e9999'),
              record(value='=1+1'), workout]
    index = core.scan_archive(archive(tmp_path, health(*inputs)))
    result = core.export_archive(index, options(index, tmp_path, format='jsonl', chunk_rows=2))
    rows = jsonl_rows(result)
    assert len(rows) == result.rows == 6 and result.csv_files == 0 and result.data_files == 4
    assert not list(result.directory.glob('*.csv'))
    by_value = {r['value']: r for r in rows}
    assert by_value['0.123456789012345678901']['numeric_value'] == float('0.123456789012345678901')
    assert by_value['9007199254740993']['numeric_value'] == 9007199254740993
    assert by_value['HKCategoryValueSleepAnalysisAsleepCore']['numeric_value'] is None
    assert by_value['1e9999']['numeric_value'] is None
    assert by_value['=1+1']['numeric_value'] is None
    assert by_value['60.5']['details']['statistics'][0]['sum'] == '1000.25'
    assert by_value['60.5']['numeric_duration'] == 60.5 and by_value['60.5']['enddate'] is None
    assert result.manifest['format'] == 'jsonl' and not result.manifest['spreadsheet_safe_text']
    for info in result.manifest['files']:
        content = (result.directory/info['name']).read_bytes()
        assert not content.startswith(b'\xef\xbb\xbf')
        assert hashlib.sha256(content).hexdigest() == info['sha256']
    for path in result.directory.iterdir():
        text = path.read_text(encoding='utf-8')
        assert "Alice's Watch" not in text and '设备' not in text


@pytest.mark.parametrize('failure', ['disk', 'cancel'])
def test_jsonl_failure_removes_staging(tmp_path, monkeypatch, failure):
    index = core.scan_archive(archive(tmp_path, health(record(), record())))
    original = core._JsonlSink.write
    def fail(self, category, row):
        original(self, category, row)
        raise OSError('disk full') if failure == 'disk' else core.Cancelled()
    monkeypatch.setattr(core._JsonlSink, 'write', fail)
    with pytest.raises((OSError, core.Cancelled)):
        core.export_archive(index, options(index, tmp_path, format='jsonl'))
    assert not list(tmp_path.glob('HealthPro_*')) and not list(tmp_path.glob('.healthpro-*'))


def test_sources_and_exact_filter_without_qt(tmp_path):
    path = archive(tmp_path, health(record(sourceName='手表'), record(sourceName='手表 Pro')))
    listing = run_cli('sources', '--input', path, '--quiet')
    assert listing.returncode == 0 and not listing.stderr
    assert [r['name'] for r in json.loads(listing.stdout)['sources']] == ['手表', '手表 Pro']
    result = run_cli('export', '--input', path, '--output', tmp_path, '--format', 'jsonl',
                     '--source-filter', '手表', '--quiet')
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['records_written'] == 1
    assert '手表' not in result.stdout
    manifest = json.loads(Path(data['manifest']).read_text(encoding='utf-8'))
    assert manifest['records_excluded_by_source'] == 1


@pytest.mark.parametrize('entry', [None, 'health_app.py', 'healthpro_cli.py'])
def test_cli_entrypoints_and_overlap_warning(tmp_path, entry):
    path = archive(tmp_path, health(record(sourceName='Watch'), record(sourceName='Phone')))
    result = run_cli('export', '--input', path, '--output', tmp_path, '--quiet', entry=entry)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['records_written'] == 2
    assert 'Do not sum across sources' in result.stderr
    assert 'scan:' not in result.stderr


@pytest.mark.parametrize('flags,code', [
    (['--format', 'json'], 2), (['--start-date', '2026-13-01'], 2),
    (['--start-date', '2030-01-01', '--end-date', '2020-01-01'], 1),
    (['--start-date', '2030-01-01'], 3), (['--end-date', '2020-01-01'], 3),
    (['--source-filter', 'watch'], 1), (['--chunk-rows', '0'], 2),
])
def test_cli_errors_never_publish(tmp_path, flags, code):
    path = archive(tmp_path, health(record(sourceName='Watch')))
    result = run_cli('export', '--input', path, '--output', tmp_path, *flags)
    assert result.returncode == code and result.stderr and not result.stdout
    assert not list(tmp_path.glob('HealthPro_*')) and not list(tmp_path.glob('.healthpro-*'))


def test_malformed_input_and_missing_destination(tmp_path):
    path = archive(tmp_path, '<HealthData>' + record())
    result = run_cli('export', '--input', path, '--output', tmp_path)
    assert result.returncode == 1 and not result.stdout and 'Traceback' not in result.stderr
    missing = run_cli('export', '--input', path, '--output', tmp_path/'absent')
    assert missing.returncode == 1 and not (tmp_path/'absent').exists()


def test_cli_repeat_filters_dates_and_privacy_opt_out(tmp_path):
    path = archive(tmp_path, health(record(sourceName='=Watch', value='-2.5'),
                  record(sourceName='Phone'), record(sourceName='Other')))
    for fmt in ('csv', 'jsonl'):
        result = run_cli('export', '--input', path, '--output', tmp_path, '--format', fmt,
                         '--source-filter', '=Watch', '--source-filter', 'Phone',
                         '--start-date', '2026-10-31', '--end-date', '2026-10-31',
                         '--no-anonymize', '--quiet')
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        manifest = json.loads(Path(data['manifest']).read_text(encoding='utf-8'))
        assert manifest['records_written'] == 2 and manifest['records_excluded_by_source'] == 1
        assert not manifest['privacy']['source_names_masked']
        if fmt == 'jsonl':
            rows = [json.loads(line) for p in Path(data['directory']).glob('*.jsonl')
                    for line in p.read_text(encoding='utf-8').splitlines()]
            assert next(r for r in rows if r['sourcename'] == '=Watch')['numeric_value'] == -2.5


@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM])
def test_cli_signal_cleanup_and_handler_restoration(tmp_path, monkeypatch, capsys, signum):
    path = archive(tmp_path, health(record(), record()))
    previous = signal.getsignal(signum)
    original = core._JsonlSink.write
    def interrupt(self, category, row):
        original(self, category, row)
        signal.raise_signal(signum)
    monkeypatch.setattr(core._JsonlSink, 'write', interrupt)
    status = cli.main(['export', '--input', str(path), '--output', str(tmp_path), '--format', 'jsonl'])
    assert status == 128 + signum and signal.getsignal(signum) == previous
    output = capsys.readouterr()
    assert not output.out and 'Cancelled' in output.err
    assert not list(tmp_path.glob('HealthPro_*')) and not list(tmp_path.glob('.healthpro-*'))
