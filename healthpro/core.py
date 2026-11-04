"""GUI-independent bounded-memory parsing and transactional CSV / JSONL export."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
import uuid
import zipfile
import zlib
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, Iterator, Optional, Set, Tuple

from . import __version__
from .categories import category_for

CSV_FIELDS = ["type", "value", "unit", "startdate", "sourcename", "enddate",
              "record_kind", "duration", "durationunit", "details_json"]
SUPPORTED_TAGS = {"Record", "Workout", "StateOfMind"}
Progress = Callable[[int, int, int], None]


class HealthDataError(Exception):
    """A user-actionable input or output failure."""


class Cancelled(Exception):
    pass


class NoMatchingRecords(HealthDataError):
    pass


def _check_cancel(cancel):
    if cancel and cancel():
        raise Cancelled()


def _identity(path):
    s = Path(path).stat()
    return (s.st_size, s.st_mtime_ns, s.st_ino)


def parse_timestamp(value):
    if not value:
        return None
    try:
        normalized = value.strip().replace("Z", "+00:00")
        # Apple uses a space before a compact UTC offset. Python 3.9's
        # fromisoformat requires +HH:MM directly after the time component.
        if len(normalized) > 5 and normalized[-5] in "+-" and normalized[-4:].isdigit():
            normalized = normalized[:-5].rstrip() + normalized[-5:-2] + ":" + normalized[-2:]
        elif len(normalized) > 6 and normalized[-6] in "+-" and normalized[-3] == ":":
            normalized = normalized[:-6].rstrip() + normalized[-6:]
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HealthDataError("健康记录包含无效时间：" + value[:60]) from exc


@dataclass
class Sample:
    kind: str
    type: str
    value: str
    unit: str
    startdate: str
    enddate: str
    source: str
    start_day: date
    duration: str = ""
    durationunit: str = ""
    details: str = ""

    @property
    def category(self):
        return category_for(self.kind, self.type)


@dataclass
class SourceInfo:
    count: int = 0
    first_day: Optional[date] = None
    last_day: Optional[date] = None
    types: Counter = field(default_factory=Counter)


@dataclass
class ArchiveIndex:
    path: Path
    member: str
    identity: Tuple[int, int, int]
    xml_size: int
    total_records: int
    first_day: date
    last_day: date
    sources: Dict[str, SourceInfo]
    types: Counter
    categories: Counter
    skipped_tags: Counter
    missing_end_dates: int

    def overlapping_types(self, selected):
        counts = Counter()
        for name in selected:
            counts.update(self.sources[name].types.keys())
        return sorted(t for t, count in counts.items() if count > 1)


def find_xml(path):
    with zipfile.ZipFile(path) as archive:
        candidates = [i for i in archive.infolist() if not i.is_dir()
                      and i.filename.lower().endswith(".xml")
                      and not i.filename.lower().endswith("export_cda.xml")]
        preferred = [i for i in candidates if Path(i.filename).name.lower()
                     in {"export.xml", "导出.xml", "輸出.xml"}]
        if len(preferred) > 1:
            raise HealthDataError("ZIP 中包含多份健康主 XML，请分别导出或仅保留一份。")
        if not candidates:
            raise HealthDataError("ZIP 中没有健康数据 XML。请选择健康 App 的“导出所有健康数据”压缩包。")
        chosen = preferred[0] if preferred else max(candidates, key=lambda i: i.file_size)
        if chosen.flag_bits & 1:
            raise HealthDataError("不支持加密 ZIP，请先解密。")
        return chosen.filename, chosen.file_size


def _sample(elem):
    a = elem.attrib
    start_raw, end_raw = a.get("startDate", ""), a.get("endDate", "")
    start = parse_timestamp(start_raw)
    end = parse_timestamp(end_raw)
    if start is None:
        raise HealthDataError("健康记录缺少 startDate，无法可靠筛选；导入已停止。")
    if end is not None:
        try:
            if end < start:
                raise HealthDataError("发现 endDate 早于 startDate 的记录；导入已停止。")
        except TypeError as exc:
            raise HealthDataError("同一记录的起止时间时区格式不一致。") from exc
    kind = elem.tag
    if kind == "Workout":
        identifier = a.get("workoutActivityType", "Workout")
        value, unit = a.get("duration", ""), a.get("durationUnit", "")
        # Preserve measurements without device names or free-form metadata.
        details = {k: a[k] for k in ("totalDistance", "totalDistanceUnit", "totalEnergyBurned", "totalEnergyBurnedUnit") if k in a}
        stats = [{k: child.attrib[k] for k in ("type", "sum", "average", "minimum", "maximum", "unit", "startDate", "endDate") if k in child.attrib}
                 for child in elem if child.tag == "WorkoutStatistics"]
        if stats:
            details["statistics"] = stats
    elif kind == "StateOfMind":
        identifier = "HKStateOfMind"
        value, unit = a.get("valence", ""), ""
        details = {k: a[k] for k in ("kind", "labels", "associations") if k in a}
    else:
        identifier = a.get("type", "UnknownRecordType")
        value, unit, details = a.get("value", ""), a.get("unit", ""), {}
    return Sample(kind, identifier, value, unit, start_raw, end_raw,
                  a.get("sourceName") or "Unknown source", start.date(),
                  a.get("duration", ""), a.get("durationUnit", ""),
                  json.dumps(details, ensure_ascii=False, sort_keys=True) if details else "")


def _xml_events(stream):
    """Normalize parser/decoder errors without swallowing caller callback failures."""
    try:
        yield from ET.iterparse(stream, events=("start", "end"))
    except (LookupError, ValueError) as exc:
        raise HealthDataError("XML 编码不受支持或无效，请重新从健康 App 导出。") from exc
    except (zlib.error, EOFError) as exc:
        raise HealthDataError("ZIP 压缩数据损坏或不完整，请重新传输或导出。") from exc


def iter_samples(path, member, *, cancel=None, progress=None, skipped=None) -> Iterator[Sample]:
    """Retain at most a top-level record subtree; validate the entire document."""
    _check_cancel(cancel)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(member)
        with archive.open(info) as stream:
            stack = []
            count = 0
            root = None
            try:
                for event, elem in _xml_events(stream):
                    _check_cancel(cancel)
                    if event == "start":
                        if root is None:
                            root = elem
                            if root.tag != "HealthData":
                                raise HealthDataError("XML 根节点不是 HealthData；这不是受支持的 Apple 健康导出。")
                        stack.append(elem)
                        continue
                    # Correlation children are references to records also exported
                    # at top level, not additional independent observations.
                    if len(stack) == 2 and elem.tag in SUPPORTED_TAGS:
                        sample = _sample(elem)
                        count += 1
                        yield sample
                        if progress and count % 2000 == 0:
                            progress(stream.tell(), info.file_size, count)
                    # Do not clear nested statistics before their parent Workout ends.
                    if len(stack) == 2:
                        if skipped is not None and elem.tag not in SUPPORTED_TAGS | {"ExportDate", "Me", "Correlation"}:
                            skipped[elem.tag] += 1
                        root.remove(elem)
                        elem.clear()
                    stack.pop()
                if root is None or stack:
                    raise HealthDataError("XML 文档不完整。")
                if progress:
                    progress(info.file_size, info.file_size, count)
            except ET.ParseError as exc:
                line, column = getattr(exc, "position", (0, 0))
                raise HealthDataError(f"XML 不完整或损坏（第 {line} 行，第 {column} 列）。未接受部分结果，请重新从健康 App 导出。") from exc


def scan_archive(path, *, cancel=None, progress=None):
    path = Path(path).resolve()
    identity = _identity(path)
    member, xml_size = find_xml(path)
    sources = {}
    types, categories, skipped = Counter(), Counter(), Counter()
    first = last = None
    total = missing_end = 0
    for sample in iter_samples(path, member, cancel=cancel, progress=progress, skipped=skipped):
        total += 1
        missing_end += not bool(sample.enddate)
        first = min(first, sample.start_day) if first else sample.start_day
        last = max(last, sample.start_day) if last else sample.start_day
        source = sources.get(sample.source)
        if source is None:
            source = sources[sample.source] = SourceInfo()
        source.count += 1
        source.first_day = min(source.first_day, sample.start_day) if source.first_day else sample.start_day
        source.last_day = max(source.last_day, sample.start_day) if source.last_day else sample.start_day
        source.types[sample.type] += 1
        types[sample.type] += 1
        categories[sample.category] += 1
    _check_cancel(cancel)
    if identity != _identity(path):
        raise HealthDataError("文件在读取过程中发生变化，请重新导入。")
    if not total:
        raise HealthDataError("没有找到可导出的 Record、Workout 或 StateOfMind 记录。")
    return ArchiveIndex(path, member, identity, xml_size, total, first, last,
                        sources, types, categories, skipped, missing_end)


@dataclass(frozen=True)
class ExportOptions:
    sources: Set[str]
    start: date
    end: date
    destination: Path
    privacy: bool = True
    spreadsheet_safe: bool = True
    chunk_rows: int = 880000
    format: str = "csv"


@dataclass
class ExportResult:
    directory: Path
    rows: int
    csv_files: int
    unmapped_rows: int
    overlap_types: list
    manifest: dict

    @property
    def data_files(self):
        return len(self.manifest["files"])


def _spreadsheet_text(value):
    """Escape formulas in textual cells; leave validated numerical values unchanged."""
    if not value:
        return value
    stripped = value.lstrip(" \t\r\n")
    if stripped.startswith(("=", "+", "-", "@", "＝", "＋", "－", "＠")) or value[0] in "\t\r\n":
        return "'" + value
    return value


def _numeric_or_text(value):
    import re
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value or ""):
        return value
    return _spreadsheet_text(value)


def _csv_row(sample, source, safe):
    row = dict(zip(CSV_FIELDS, [sample.type, sample.value, sample.unit, sample.startdate,
               source, sample.enddate, sample.kind, sample.duration, sample.durationunit, sample.details]))
    if safe:
        row = {key: (_numeric_or_text(value) if key in {"value", "duration"} else _spreadsheet_text(value))
               for key, value in row.items()}
    return row


def _json_number(raw):
    """Convenience numeric value; original XML text remains authoritative."""
    import re
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", raw or "", re.ASCII):
        return None
    try:
        value = int(raw) if re.fullmatch(r"[+-]?\d+", raw, re.ASCII) else float(raw)
        return value if isinstance(value, int) or math.isfinite(value) else None
    except (ValueError, OverflowError):
        return None


def _json_row(sample, source):
    return {"schema_version": 1, "category": sample.category,
            "type": sample.type, "value": sample.value,
            "numeric_value": _json_number(sample.value), "unit": sample.unit or None,
            "startdate": sample.startdate, "enddate": sample.enddate or None,
            "sourcename": source, "record_kind": sample.kind,
            "duration": sample.duration or None,
            "numeric_duration": _json_number(sample.duration),
            "durationunit": sample.durationunit or None,
            "details": json.loads(sample.details) if sample.details else {}}


class _HashingWriter(io.BufferedWriter):
    """Hash exactly the encoded bytes accepted by the output buffer."""
    def __init__(self, raw, digest):
        super().__init__(raw)
        self.digest = digest

    def write(self, data):
        written = super().write(data)
        self.digest.update(memoryview(data)[:written])
        return written


class _CsvSink:
    suffix = "csv"
    encoding = "utf-8-sig"
    def __init__(self, directory, limit):
        self.directory, self.limit = directory, limit
        self.handles, self.writers, self.counts, self.parts = {}, {}, Counter(), Counter()
        self.files = []
        self.active_files = {}
        self.digests = {}

    def write(self, category, row):
        if category not in self.handles or self.counts[category] % self.limit == 0:
            if category in self.handles:
                self.handles.pop(category).close()
            self.parts[category] += 1
            # Always numbered: filenames never change when another chunk appears.
            name = f"{category}_Part{self.parts[category]:03d}.{self.suffix}"
            digest = hashlib.sha256()
            raw = (self.directory / name).open("wb", buffering=0)
            try:
                handle = io.TextIOWrapper(_HashingWriter(raw, digest),
                                          encoding=self.encoding, newline="")
            except BaseException:
                raw.close()
                raise
            self.digests[name] = digest
            self.handles[category] = handle
            self.open_writer(category, handle)
            metadata = {"name": name, "category": category, "rows": 0}
            self.files.append(metadata)
            self.active_files[category] = metadata
        self.write_row(category, row)
        self.counts[category] += 1
        self.active_files[category]["rows"] += 1

    def open_writer(self, category, handle):
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
        self.writers[category] = writer
        writer.writeheader()

    def write_row(self, category, row):
        self.writers[category].writerow(row)

    def close(self):
        error = None
        for handle in self.handles.values():
            try:
                handle.close()
            except OSError as exc:
                error = error or exc
        self.handles.clear()
        if error:
            raise error


class _JsonlSink(_CsvSink):
    suffix = "jsonl"
    encoding = "utf-8"

    def open_writer(self, category, handle):
        pass

    def write_row(self, category, row):
        self.handles[category].write(json.dumps(row, ensure_ascii=False, allow_nan=False,
                                               separators=(",", ":")) + "\n")


def export_archive(index, options, *, cancel=None, progress=None):
    if options.format not in {"csv", "jsonl"}:
        raise HealthDataError("输出格式必须为 csv 或 jsonl。")
    if not options.sources or not options.sources <= index.sources.keys():
        raise HealthDataError("请选择有效的数据来源。")
    if options.start > options.end:
        raise HealthDataError("开始日期不能晚于结束日期。")
    if options.chunk_rows < 1 or options.chunk_rows > 1_048_575:
        raise HealthDataError("每片行数必须为 1–1,048,575。")
    if _identity(index.path) != index.identity:
        raise HealthDataError("原始 ZIP 已变化，请重新导入后导出。")
    destination = Path(options.destination).expanduser().resolve()
    if not destination.is_dir():
        raise HealthDataError("输出位置不存在，请选择一个文件夹。")
    _check_cancel(cancel)
    staging = Path(tempfile.mkdtemp(prefix=".healthpro-", dir=destination))
    sink = (_CsvSink if options.format == "csv" else _JsonlSink)(staging, options.chunk_rows)
    source_map = {name: f"Source_{i:03d}" for i, name in enumerate(sorted(options.sources), 1)}
    selected_rows = 0
    omitted_sources = omitted_dates = 0
    selected_types = defaultdict(Counter)
    missing_end = 0
    published = False
    try:
        for sample in iter_samples(index.path, index.member, cancel=cancel, progress=progress):
            if sample.source not in options.sources:
                omitted_sources += 1
                continue
            if not options.start <= sample.start_day <= options.end:
                omitted_dates += 1
                continue
            source = source_map[sample.source] if options.privacy else sample.source
            row = (_csv_row(sample, source, options.spreadsheet_safe) if options.format == "csv"
                   else _json_row(sample, source))
            sink.write(sample.category, row)
            selected_types[sample.type][source] += 1
            selected_rows += 1
            missing_end += not bool(sample.enddate)
        sink.close()
        _check_cancel(cancel)
        if _identity(index.path) != index.identity:
            raise HealthDataError("文件在导出过程中发生变化，结果未发布。请重新导入。")
        if not selected_rows:
            raise NoMatchingRecords("所选来源与日期范围内没有记录；没有生成结果目录。")
        overlaps = sorted(t for t, sources in selected_types.items() if len(sources) > 1)
        for info in sink.files:
            _check_cancel(cancel)
            info["sha256"] = sink.digests[info["name"]].hexdigest()
        manifest = {
            "schema_version": 1, "app_version": __version__, "status": "complete",
            "format": options.format,
            "created_at": datetime.now().astimezone().isoformat(),
            "input": {"zip_size": index.identity[0], "xml_size": index.xml_size,
                      "records_indexed": index.total_records},
            "filters": {"start": options.start.isoformat(), "end": options.end.isoformat(),
                        "date_policy": "inclusive startDate calendar date in each record's original timezone",
                        "sources": list(source_map.values()) if options.privacy else sorted(options.sources)},
            "privacy": {"source_names_masked": options.privacy, "scope": "sourceName only; dates and health values remain sensitive; free-form metadata and device descriptors are not exported"},
            "spreadsheet_safe_text": options.spreadsheet_safe if options.format == "csv" else False,
            "merge_policy": "raw_records_union_no_deduplication",
            "records_written": selected_rows,
            "records_excluded_by_source": omitted_sources,
            "records_excluded_by_date": omitted_dates,
            "missing_end_dates": missing_end,
            "unmapped_records": sink.counts["16_Other_Unmapped"],
            "skipped_top_level_elements": dict(index.skipped_tags),
            "types_with_multiple_sources": overlaps,
            "type_sources": {t: dict(counts) for t, counts in selected_types.items()},
            "files": sink.files,
            "limitations": ["No reconciliation with Health App source priorities.",
                            "No free-form Record metadata, routes, ECG files, or ClinicalRecord export.",
                            "StateOfMind exports attributes; nested labels/associations are not interpreted."],
        }
        if selected_rows + omitted_sources + omitted_dates != index.total_records:
            raise HealthDataError("记录数量与索引不一致，结果未发布。请重新导入。")
        with (staging / "export_manifest.json").open("w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)
            file.write("\n")
        _check_cancel(cancel)
        name = "HealthPro_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        final = destination / name
        os.rename(staging, final)
        published = True
        return ExportResult(final, selected_rows, len(sink.files) if options.format == "csv" else 0,
                            sink.counts["16_Other_Unmapped"], overlaps, manifest)
    finally:
        try:
            sink.close()
        finally:
            if not published:
                shutil.rmtree(staging)
