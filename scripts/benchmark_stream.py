"""Synthetic, separate-process benchmark. Example: python scripts/benchmark_stream.py 500000."""
import json
import resource
import sys
import tempfile
import time
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from healthpro.core import scan_archive

count = int(sys.argv[1])
row = b'<Record type="HKQuantityTypeIdentifierHeartRate" value="72" unit="count/min" sourceName="Synthetic Watch" startDate="2026-10-31 22:00:00 +0800" endDate="2026-10-31 22:00:00 +0800"/>'
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)/'synthetic.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        with archive.open('export.xml','w') as stream:
            stream.write(b'<HealthData><ExportDate/>')
            for _ in range(count//1000):
                stream.write(row*1000)
            stream.write(row*(count%1000))
            stream.write(b'</HealthData>')
    start=time.monotonic()
    index=scan_archive(path)
    elapsed=time.monotonic()-start
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform!='darwin':peak*=1024
    print(json.dumps({'records':count,'parsed':index.total_records,'seconds':round(elapsed,3),'peak_rss_mib':round(peak/2**20,2)}))
