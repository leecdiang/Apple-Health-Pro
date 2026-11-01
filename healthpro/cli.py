"""Headless CLI. stdout contains one JSON result; diagnostics use stderr."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import json
from pathlib import Path
import signal
import sys
import time
import zipfile

from . import __version__
from .core import Cancelled, HealthDataError, NoMatchingRecords, ExportOptions, scan_archive, export_archive


def iso_date(value):
    try:
        day = date.fromisoformat(value)
        if day.isoformat() != value:
            raise ValueError()
        return day
    except ValueError:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")


def chunk_size(value):
    try:
        count = int(value)
        if not 1 <= count <= 1_048_575:
            raise ValueError()
        return count
    except ValueError:
        raise argparse.ArgumentTypeError("chunk rows must be 1–1,048,575")


def parser():
    root = argparse.ArgumentParser(prog="healthpro", description="Local Apple Health ZIP export; no GUI or network.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    sources = commands.add_parser("sources", help="list exact source names as JSON (contains original names)")
    export = commands.add_parser("export", help="export selected records to a new result directory")
    for command in (sources, export):
        command.add_argument("--input", required=True, type=Path, help="Apple Health export ZIP")
        command.add_argument("--quiet", action="store_true", help="hide progress; warnings and errors remain")
    export.add_argument("--output", required=True, type=Path, help="existing output folder; each export creates a new subfolder")
    export.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    export.add_argument("--source-filter", action="append", metavar="NAME", help="exact, case-sensitive source name; repeat to select multiple; default: all")
    export.add_argument("--start-date", type=iso_date, help="inclusive original-timezone startDate day")
    export.add_argument("--end-date", type=iso_date, help="inclusive original-timezone startDate day")
    export.add_argument("--chunk-rows", type=chunk_size, default=880000)
    export.add_argument("--no-anonymize", action="store_true", help="include original source names (default: Source_001 etc.)")
    export.add_argument("--no-excel-safe", action="store_true", help="disable CSV formula text protection (JSONL always preserves text)")
    return root


@contextmanager
def cancellation():
    """Defer interruption until the engine can unwind and remove staging output."""
    received = [None]
    previous = {}

    def request(signum, frame):
        received[0] = signum

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, request)
        yield received
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def progress_reporter(stage, quiet):
    last = [0.0]

    def report(current, total, count):
        now = time.monotonic()
        if not quiet and (now - last[0] >= .5 or current == total):
            last[0] = now
            print(f"{stage}: {count} records ({100 * current // total if total else 0}%)", file=sys.stderr)
    return report


def emit(value):
    print(json.dumps(value, ensure_ascii=True, allow_nan=False))


def main(argv=None):
    args = parser().parse_args(argv)
    received = [None]
    try:
        if args.command == "export":
            if not args.output.expanduser().is_dir():
                raise HealthDataError("Output folder does not exist or is not a directory.")
            if args.start_date and args.end_date and args.start_date > args.end_date:
                raise HealthDataError("Start date must not be after end date.")
        with cancellation() as received:
            cancel = lambda: received[0] is not None
            index = scan_archive(args.input.expanduser(), cancel=cancel,
                                 progress=progress_reporter("scan", args.quiet))
            if cancel():
                raise Cancelled()
            if args.command == "sources":
                emit({"schema_version": 1, "app_version": __version__, "status": "complete",
                      "records_indexed": index.total_records,
                      "sources": [{"name": name, "records": info.count,
                                   "first_day": info.first_day.isoformat(), "last_day": info.last_day.isoformat(),
                                   "types": dict(info.types)} for name, info in sorted(index.sources.items())]})
                return 0
            selected = set(args.source_filter) if args.source_filter else set(index.sources)
            if not selected <= index.sources.keys():
                raise HealthDataError("Unknown source filter. Use 'healthpro sources --input ZIP' to list exact names.")
            start, end = args.start_date or index.first_day, args.end_date or index.last_day
            if start > end:
                # A one-sided filter completely outside the archive is an empty selection.
                raise NoMatchingRecords("No records in the requested date range.")
            if index.overlapping_types(selected):
                print("Warning: selected sources share metrics; raw records are preserved without deduplication. "
                      "Do not sum across sources. See export_manifest.json for filtered overlap counts.", file=sys.stderr)
            options = ExportOptions(selected, start, end, args.output, not args.no_anonymize,
                                    not args.no_excel_safe, args.chunk_rows, args.format)
            result = export_archive(index, options, cancel=cancel,
                                    progress=progress_reporter("export", args.quiet))
            # The directory has now committed successfully. A late signal must not report
            # cancellation while leaving completed output behind.
            emit({"schema_version": 1, "app_version": __version__, "status": "complete",
                  "format": args.format, "directory": str(result.directory),
                  "manifest": str(result.directory / "export_manifest.json"),
                  "records_written": result.rows, "data_files": result.data_files,
                  "unmapped_records": result.unmapped_rows,
                  "types_with_multiple_sources": result.overlap_types})
        return 0
    except Cancelled:
        print("Cancelled; unfinished export removed.", file=sys.stderr)
        return 128 + int(received[0] or signal.SIGINT)
    except NoMatchingRecords as exc:
        print(f"No matching records: {exc}", file=sys.stderr)
        return 3
    except (HealthDataError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
