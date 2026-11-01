"""Validate a source or frozen CLI with synthetic data; requires only stdlib."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def run(command):
    with tempfile.TemporaryDirectory(prefix='HealthPro-CLI-smoke-') as tmp:
        root = Path(tmp)
        source = root/'synthetic.zip'
        record = '<Record type="HKQuantityTypeIdentifierStepCount" sourceName="Synthetic Watch" value="12" unit="count" startDate="2026-10-31 12:00:00 +0800" endDate="2026-10-31 12:01:00 +0800"/>'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('export.xml', '<HealthData>' + record*3 + '</HealthData>')
        def call(*args):
            result = subprocess.run(command + list(map(str, args)), capture_output=True,
                                    encoding='utf-8', timeout=60,
                                    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            assert result.returncode == 0, result.stderr
            return json.loads(result.stdout)
        listing = call('sources', '--input', source, '--quiet')
        assert listing['records_indexed'] == 3
        for fmt in ('csv', 'jsonl'):
            result = call('export', '--input', source, '--output', root, '--format', fmt,
                          '--chunk-rows', 2, '--quiet')
            assert result['records_written'] == 3 and result['data_files'] == 2
            manifest = json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
            assert manifest['format'] == fmt
            for info in manifest['files']:
                content = (Path(result['directory'])/info['name']).read_bytes()
                assert hashlib.sha256(content).hexdigest() == info['sha256']
                assert b'Synthetic Watch' not in content
        assert not list(root.glob('.healthpro-*'))
        print('CLI smoke passed: sources, CSV, JSONL, chunking, privacy, checksums')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python scripts/smoke_cli.py COMMAND [PREFIX_ARGS...]')
    run(sys.argv[1:])
