import csv
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
import pytest
from healthpro import core


def record(identifier="HKQuantityTypeIdentifierHeartRate", **attrs):
    fields = dict(type=identifier, sourceName="Alice's Watch", value="72", unit="count/min",
                  startDate="2026-10-31 22:00:00 +0800", endDate="2026-11-01 06:00:00 +0800")
    fields.update(attrs)
    return ET.tostring(ET.Element("Record", fields), encoding="unicode")


def archive(tmp_path, text, name="export.zip", member="apple_health_export/export.xml"):
    path = tmp_path/name
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr(member,text)
    return path


def health(*records):
    return "<HealthData>"+"".join(records)+"</HealthData>"


def options(index,tmp_path,**kwargs):
    values = dict(sources=set(index.sources),start=index.first_day,end=index.last_day,destination=tmp_path)
    values.update(kwargs)
    return core.ExportOptions(**values)


def rows(result):
    result_rows = []
    for path in result.directory.glob("*.csv"):
        with path.open(encoding="utf-8-sig",newline="") as f:
            result_rows.extend(csv.DictReader(f))
    return result_rows


def test_enddate_and_first_record_preserved(tmp_path):
    a = record("HKCategoryTypeIdentifierSleepAnalysis",value="AsleepCore",endDate="2026-10-31 23:00:00 +0800")
    b = record("HKCategoryTypeIdentifierSleepAnalysis",value="AsleepCore")
    index = core.scan_archive(archive(tmp_path,health(a,b)))
    result = core.export_archive(index,options(index,tmp_path))
    assert index.total_records == result.rows == 2
    assert [r['enddate'] for r in rows(result)] == ['2026-10-31 23:00:00 +0800','2026-11-01 06:00:00 +0800']


@pytest.mark.parametrize('xml',[
    '<HealthData>'+record()+'<Record broken',
    '<NotHealth><Record/></NotHealth>',
    '',
    '<HealthData>'+record(value='a\x0bb')+'</HealthData>',
])
def test_bad_xml_never_succeeds(tmp_path,xml):
    with pytest.raises(core.HealthDataError):
        core.scan_archive(archive(tmp_path,xml))


def test_bad_zip(tmp_path):
    path=tmp_path/'bad.zip'; path.write_bytes(b'not zip')
    with pytest.raises(zipfile.BadZipFile):
        core.scan_archive(path)


def test_no_xml(tmp_path):
    with pytest.raises(core.HealthDataError,match='没有健康'):
        core.scan_archive(archive(tmp_path,'x',member='note.txt'))


@pytest.mark.parametrize('name',['export.xml','导出.xml','輸出.xml','EXPORT.XML','unusual.xml'])
def test_localized_xml(tmp_path,name):
    assert core.scan_archive(archive(tmp_path,health(record()),member=name)).total_records == 1


def test_ambiguous_xml(tmp_path):
    path=archive(tmp_path,health(record()))
    with zipfile.ZipFile(path,'a') as z:z.writestr('other/export.xml',health(record()))
    with pytest.raises(core.HealthDataError,match='多份'):
        core.scan_archive(path)


def test_exclusive_categories_and_unknown_preserved(tmp_path):
    identifiers=['HKCategoryTypeIdentifierHeadache','HKCategoryTypeIdentifierFatigue',
      'HKQuantityTypeIdentifierVO2Max','HKQuantityTypeIdentifierAppleExerciseTime',
      'HKQuantityTypeIdentifierWalkingSpeed','HKQuantityTypeIdentifierDistanceSwimming',
      'HKQuantityTypeIdentifierUnderwaterDepth','HKQuantityTypeIdentifierFutureMetric']
    index=core.scan_archive(archive(tmp_path,health(*(record(t) for t in identifiers))))
    result=core.export_archive(index,options(index,tmp_path))
    exported=rows(result)
    assert len(exported)==len(identifiers)
    assert sorted(r['type'] for r in exported)==sorted(identifiers)
    assert result.unmapped_rows==1
    assert index.categories['15_Symptoms_Illness']==2
    assert index.categories['13_Nutrition_Hydration']==0


def test_workout_statistics_survive_until_parent_end(tmp_path):
    workout='<Workout workoutActivityType="HKWorkoutActivityTypeSwimming" sourceName="Watch" startDate="2026-10-31 12:00:00 +0800" endDate="2026-10-31 13:00:00 +0800" duration="60" durationUnit="min"><WorkoutStatistics type="HKQuantityTypeIdentifierDistanceSwimming" sum="1000" unit="m"/></Workout>'
    index=core.scan_archive(archive(tmp_path,health(workout)))
    result=core.export_archive(index,options(index,tmp_path))
    row=rows(result)[0]
    assert row['record_kind']=='Workout' and row['duration']=='60'
    assert json.loads(row['details_json'])['statistics'][0]['sum']=='1000'
    assert index.categories['11_Workouts_Training']==1


def test_missing_enddate_explicit_and_unknown_source(tmp_path):
    node=ET.fromstring(record()); del node.attrib['endDate']; del node.attrib['sourceName']
    index=core.scan_archive(archive(tmp_path,health(ET.tostring(node,encoding='unicode'))))
    result=core.export_archive(index,options(index,tmp_path))
    assert result.manifest['missing_end_dates']==1
    assert rows(result)[0]['enddate']==''


@pytest.mark.parametrize('attrs',[{'startDate':''},{'startDate':'bad'},{'endDate':'2026-10-30 22:00:00 +0800'},{'endDate':'2026-10-31 23:00:00'}])
def test_invalid_timestamps_fail(tmp_path,attrs):
    with pytest.raises(core.HealthDataError):
        core.scan_archive(archive(tmp_path,health(record(**attrs))))


def test_date_filter_keeps_original_timezone_and_enddate(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(record(),record(startDate='2026-11-01 00:00:00 -0700',endDate='2026-11-01 01:00:00 -0700'))))
    result=core.export_archive(index,options(index,tmp_path,start=date(2026,11,1),end=date(2026,11,1)))
    assert result.rows==1 and rows(result)[0]['startdate'].endswith('-0700')
    assert result.manifest['records_excluded_by_date']==1


@pytest.mark.parametrize('count',[1,2,3,4,5])
def test_chunks_no_off_by_one(tmp_path,count):
    index=core.scan_archive(archive(tmp_path,health(*[record()]*count)))
    result=core.export_archive(index,options(index,tmp_path,chunk_rows=2))
    assert result.csv_files==(count+1)//2
    assert len(rows(result))==count
    assert sum(f['rows'] for f in result.manifest['files'])==count
    for info in result.manifest['files']:
        assert hashlib.sha256((result.directory/info['name']).read_bytes()).hexdigest()==info['sha256']


def test_repeat_export_isolated_and_anonymous(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(*[record()]*3)))
    first=core.export_archive(index,options(index,tmp_path,privacy=False,chunk_rows=2))
    second=core.export_archive(index,options(index,tmp_path,privacy=True,chunk_rows=4))
    assert first.directory!=second.directory
    assert first.csv_files==2 and second.csv_files==1
    assert "Alice's Watch" in (first.directory/'1_Heart_Cardio_Part001.csv').read_text()
    for p in second.directory.iterdir():
        assert "Alice's Watch" not in p.read_text()


def test_raw_union_warning_is_metric_specific(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(record('HKQuantityTypeIdentifierStepCount',sourceName='Phone',value='8000'),record('HKQuantityTypeIdentifierStepCount',sourceName='Watch',value='7500'),record(sourceName='Watch'))))
    result=core.export_archive(index,options(index,tmp_path))
    assert result.overlap_types==['HKQuantityTypeIdentifierStepCount']
    assert sum(int(r['value']) for r in rows(result) if 'StepCount' in r['type'])==15500
    assert result.manifest['merge_policy']=='raw_records_union_no_deduplication'


def test_formula_text_and_numeric_roundtrip(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(record(sourceName='=1+1',value='-2.5'))))
    safe=core.export_archive(index,options(index,tmp_path,privacy=False))
    raw=core.export_archive(index,options(index,tmp_path,privacy=False,spreadsheet_safe=False))
    assert rows(safe)[0]['sourcename']=="'=1+1"
    assert rows(safe)[0]['value']=='-2.5'
    assert rows(raw)[0]['sourcename']=='=1+1'


def test_no_match_publishes_nothing(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(record())))
    with pytest.raises(core.NoMatchingRecords):
        core.export_archive(index,options(index,tmp_path,start=date(2030,1,1),end=date(2030,1,2)))
    assert not list(tmp_path.glob('HealthPro_*')) and not list(tmp_path.glob('.healthpro-*'))


def test_disk_failure_cleans_partial_files(tmp_path,monkeypatch):
    index=core.scan_archive(archive(tmp_path,health(record(),record())))
    original=core._CsvSink.write
    def fail(self,category,row):
        original(self,category,row)
        raise OSError('simulated disk full')
    monkeypatch.setattr(core._CsvSink,'write',fail)
    with pytest.raises(OSError,match='disk full'):
        core.export_archive(index,options(index,tmp_path))
    assert not list(tmp_path.glob('HealthPro_*')) and not list(tmp_path.glob('.healthpro-*'))


def test_cancel_cleans_output(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(*[record()]*10)))
    calls=0
    def cancel():
        nonlocal calls
        calls+=1
        return calls>8
    with pytest.raises(core.Cancelled):
        core.export_archive(index,options(index,tmp_path),cancel=cancel)
    assert not list(tmp_path.glob('HealthPro_*')) and not list(tmp_path.glob('.healthpro-*'))


def test_changed_input_rejected(tmp_path):
    path=archive(tmp_path,health(record()))
    index=core.scan_archive(path)
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(core.HealthDataError,match='变化'):
        core.export_archive(index,options(index,tmp_path))


def test_invalid_options(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(record())))
    for changes in [dict(sources=set()),dict(sources={'bad'}),dict(start=date(2030,1,1)),dict(chunk_rows=0),dict(chunk_rows=1048576)]:
        with pytest.raises(core.HealthDataError):
            core.export_archive(index,options(index,tmp_path,**changes))


def test_skipped_top_level_tags_counted(tmp_path):
    index=core.scan_archive(archive(tmp_path,health(record(),'<ActivitySummary dateComponents="2026-10-31"/>')))
    assert index.skipped_tags=={'ActivitySummary':1}


def test_parser_root_does_not_retain_records(tmp_path,monkeypatch):
    original=core.ET.iterparse
    retained=[]
    def observe(*args,**kwargs):
        for event,elem in original(*args,**kwargs):
            if event=='end' and elem.tag=='HealthData':retained.append(len(elem))
            yield event,elem
    monkeypatch.setattr(core.ET,'iterparse',observe)
    index=core.scan_archive(archive(tmp_path,health(*[record()]*10000)))
    assert index.total_records==10000 and retained==[0]
