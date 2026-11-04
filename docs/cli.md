# 命令行导出（8.9.1）

在源码目录运行 `python -m healthpro` 或 `python healthpro_cli.py`，仅需 Python 3.9+ 标准库。无需 GUI、显示服务器、Qt 或 psutil。`python health_app.py export ...` 也会直接进入无 GUI 路径。

独立程序：`python -m PyInstaller HealthProCLI.spec --noconfirm`，生成 `dist/healthpro-cli`（Windows 为 `.exe`）。此包使用控制台入口，可重定向标准输出。桌面版 Windows EXE 为无控制台应用，请使用专用 CLI。

## 来源查询

```bash
python -m healthpro sources --input export.zip --quiet
```

stdout 为单个 JSON 对象，包含 `schema_version`、`app_version`、`status`、`records_indexed` 和 `sources`。每个来源包含原始 `name`、记录数、起止自然日、各类型记录数。此命令有意展示真实来源名，方便精确筛选；不要把其结果误认为匿名数据。

## 导出

```bash
mkdir -p output
python -m healthpro export --input export.zip --output output --format jsonl \
  --source-filter "Apple Watch" --source-filter "iPhone" \
  --start-date 2026-01-01 --end-date 2026-10-31 --quiet > result.json
```

| 参数 | 行为 |
| --- | --- |
| `--input` | 必填，健康导出 ZIP；支持带空格或中文的路径 |
| `--output` | 必填、已存在的目录；不会覆盖旧结果 |
| `--format csv\|jsonl` | 默认 CSV；JSONL 是逐行 JSON，不是单个 JSON 数组 |
| `--source-filter NAME` | 精确、区分大小写，可重复；省略则选择所有来源；拼错会报错，不会退回全选 |
| `--start-date` / `--end-date` | `YYYY-MM-DD`，按每条记录原时区的 startDate 自然日筛选，两端包含；省略某端则使用归档对应边界 |
| `--chunk-rows` | 默认 880000，每文件 1–1048575 条记录，按分类分片 |
| `--no-anonymize` | 关闭默认来源名匿名化；匿名 ID 仅保证同一次导出内一致 |
| `--no-excel-safe` | 关闭 CSV 公式文本防护；JSONL 本来就保留原始文本，不受此参数影响 |
| `--quiet` | 隐藏进度，仍输出错误及多来源警告 |
| `--version` | 放在子命令之前，显示软件版本 |

成功后 stdout 只有一个 JSON 结果，包含实际 `directory`、`manifest` 绝对路径、`format`、`records_written`、`data_files`、`unmapped_records` 和 `types_with_multiple_sources`。记录本身位于结果目录；不向 stdout 混入进度或健康记录。

进度、警告、错误使用 stderr。默认所有来源都被选择，因此若共享指标，会提示原始记录没有自动去重；扫描阶段的提示可能覆盖日期范围之外的重叠，最终以导出清单内的筛选后来源计数为准。

## JSONL schema 1

每个文件为 UTF-8（无 BOM），一行一个对象。字段名稳定，新增字段时消费者应允许未知字段。

```json
{"schema_version":1,"category":"1_Heart_Cardio","type":"HKQuantityTypeIdentifierHeartRate","value":"72.0","numeric_value":72.0,"unit":"count/min","startdate":"2026-10-31 12:00:00 +0800","enddate":"2026-10-31 12:01:00 +0800","sourcename":"Source_001","record_kind":"Record","duration":null,"numeric_duration":null,"durationunit":null,"details":{}}
```

- `value` 始终为原始字符串，`duration` 为原始字符串或 null，是精确数值的权威来源；分类枚举也原样保留。
- `numeric_value` / `numeric_duration` 为辅助数值：整数输出为 JSON 整数，小数和指数转换为有限浮点值；非数值、NaN、Infinity 或超出有限浮点范围的数值输出 null。小数可能舍入，极小值可能下溢；JavaScript 等消费者还可能丢失大整数精度。精确计算应从原始字符串构造 Decimal。
- 缺失的 `unit`、`enddate`、`duration`、`durationunit` 为 null；时间戳保留原始时区，不做 UTC 转换。
- `details` 为嵌套对象，运动统计位于 `details.statistics` 数组，统计属性的值保持原始字符串；不再把对象编码为 JSON 字符串。
- 隐私与范围和桌面版一致：不输出设备描述、自由文本 MetadataEntry；来源匿名化不代表日期或健康数值完全去标识化。

CSV 字段与默认防护保持不变。两种格式均生成 `export_manifest.json`，增加 `format` 字段；JSONL 的 `spreadsheet_safe_text` 为 false。清单包含各类型的贡献来源及计数、排除数量、未知类型、分片行数和 SHA-256。未知 Record 类型保留到 `16_Other_Unmapped`。

## 退出与取消

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功，stdout 含结果（help / version 按常规输出文本） |
| 1 | 输入、来源、日期顺序或文件读写错误 |
| 2 | 命令参数错误 |
| 3 | 筛选后无记录，不创建成功目录 |
| 130 | Ctrl+C / SIGINT 取消 |
| 143 | SIGTERM 请求取消（系统支持递送该信号时） |

SIGINT / SIGTERM 在下一个解析或写出检查点取消，关闭文件并清理本次临时目录。不能保证强制终止进程、断电或操作系统文件调用一直不返回时完成清理。目录成功提交后到达的信号不会把已完成导出改报为取消。

## 自动验证

```bash
python scripts/smoke_cli.py python -S -m healthpro
python scripts/smoke_cli.py dist/healthpro-cli
```

只使用自动生成的合成记录，检查来源查询、CSV / JSONL、分片、匿名化和校验值。
