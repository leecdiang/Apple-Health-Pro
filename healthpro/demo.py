"""Explicitly labelled synthetic fixtures for the review build."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def create_demo():
    directory = Path(tempfile.mkdtemp(prefix="HealthPro-Demo-"))
    root = ET.Element("HealthData", locale="zh_CN")
    ET.SubElement(root, "ExportDate", value="2026-11-01 12:00:00 +0800")
    start = datetime(2026, 10, 1, tzinfo=timezone(timedelta(hours=8)))
    for day in range(31):
        for source, types in [
            ("演示 · Apple Watch", [("HeartRate", "68", "count/min"), ("StepCount", "7500", "count"), ("VO2Max", "42", "ml/kg*min")]),
            ("演示 · iPhone", [("StepCount", "8000", "count"), ("DistanceWalkingRunning", "5.8", "km")]),
            ("演示 · 手动记录", [("BodyMass", "75", "kg")]),
        ]:
            for identifier, value, unit in types:
                stamp = (start + timedelta(days=day, hours=12)).strftime("%Y-%m-%d %H:%M:%S %z")
                ET.SubElement(root, "Record", type="HKQuantityTypeIdentifier"+identifier,
                              sourceName=source, value=value, unit=unit, startDate=stamp, endDate=stamp)
        sleep = start + timedelta(days=day, hours=23)
        ET.SubElement(root, "Record", type="HKCategoryTypeIdentifierSleepAnalysis", sourceName="演示 · Apple Watch",
                      value="HKCategoryValueSleepAnalysisAsleepCore", startDate=sleep.strftime("%Y-%m-%d %H:%M:%S %z"),
                      endDate=(sleep+timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S %z"))
    path = directory / "演示数据（全部为合成记录）.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("apple_health_export/export.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return path
