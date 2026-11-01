# Apple Health Pro

A local desktop tool for turning Apple Health export ZIPs into categorized CSV files.
本地处理 Apple 健康导出数据，按来源、日期与指标分类生成 CSV。

## v8.8.0

[下载正式版](https://github.com/leecdiang/Apple-Health-Pro/releases/latest) · [更新记录](CHANGELOG.md)

- 保留原始 `startdate` / `enddate`、时区、数值与单位，补充运动持续时间及可用统计字段。
- 两遍流式处理：首次扫描仅建立来源/日期/类型统计，导出时重新扫描并逐条写入。内存随不同来源、类型和最大单条记录大小变化，不保留全量 DataFrame。
- 完整检查 XML；损坏、截断、无效时间或空数据不会显示为成功。
- 完整 identifier 映射到唯一主分类；未知 Record 类型保留到 `16_Other_Unmapped`，计数可查。
- 每次导出创建独立目录，全部文件写完并生成清单后才发布。失败/取消会清理该次临时目录，不覆盖已有结果。
- 可取消的单任务 GUI；关闭窗口会等待任务停止与临时文件清理。
- 恢复公开版的 CPU / 内存小圆环和阶段配色进度转盘；资源每 1.5 秒非阻塞采样，空闲不播放动画。
- 精简主界面，更多导出选项与说明折叠；启动时跟随系统外观，右上角小按钮一键切换深色与浅色。
- macOS 使用原生文件选择 sheet 导入 ZIP 和选择输出文件夹；日历采用圆角弹出面板，支持年月选择、方向键与 Escape。导出按钮在禁用和可点击状态下均保持胶囊圆角。
- macOS 26+ 使用 AppKit NSGlassEffectView，较早版本回退到 NSVisualEffectView；其他平台采用不透明材质。系统“降低透明度”“增强对比度”“减少动态效果”即时生效。

## 使用

1. 在 iPhone 健康 App 中选择头像 → 导出所有健康数据，获得 ZIP。
2. 打开应用，选择或拖入 ZIP。完整扫描后勾选要导出的来源。
3. 选择日期和输出文件夹。日期范围按记录 **startDate 的原时区自然日**，两端包含；不会把跨午夜记录拆成每天的片段。
4. 点击“导出 CSV”。完成后点击“打开结果文件夹”，查看 CSV 和 `export_manifest.json`。

默认启用“匿名化来源名称”及“Excel 安全文本”。无来源或日期倒置时不能导出；空筛选结果不创建成功目录。
可通过“文件 → 载入演示数据”体验流程，演示记录全部为合成数据。
云盘或受系统管理的文件夹可能有额外读取等待；大文件建议先下载到本机。取消会等待当前系统文件读写返回后清理。

### 多来源与隐私

输出是 **raw records union**，不复现 Health App 的来源优先级，也不自动去重。
多个来源对同一指标有记录时，可在“详情”查看重叠说明，清单列出相应指标。不能直接跨来源累加步数或距离。

匿名化仅把 `sourceName` 替换为任务内一致的 `Source_001` 等标签；不导出源名称映射、设备描述或自由文本元数据。日期与健康数值仍可识别个人，匿名化不是完全去标识化。

Excel 安全文本会为可能被表格软件识别为公式的文本加单引号前缀，合法数字（含负数）保持不变。
用于机器处理、需要精确原始文本时可关闭；不要把不可信 CSV 当作可信表格打开。

### 输出格式

CSV 使用 UTF-8 BOM，字段顺序为：

```
type,value,unit,startdate,sourcename,enddate,record_kind,duration,durationunit,details_json
```

已有前五列保留，新增列附在后面。每类文件始终使用 `类别_Part001.csv` 编号，默认每片最多 880,000 条数据行。
清单记录过滤条件、已写/已排除行数、未知类型计数、多来源指标及文件 SHA-256。

支持 Record、Workout 和 StateOfMind。保留 Workout 的可用总距离/能量及 WorkoutStatistics。
缺失 endDate 时保留为空并报告数量，不推算不存在的终点。StateOfMind 保存属性，暂不解释嵌套标签/关联。
ActivitySummary 等未处理的顶层元素会计数提示；ECG/路线附件、ClinicalRecord、自由文本 MetadataEntry 不在本版本输出范围。

## 开发与验证

推荐 Python 3.11 或 3.12。代码兼容 Python 3.9；本地审核构建使用 Python 3.9.6。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python health_app.py
# 明确标注的合成数据预览
python health_app.py --demo
```

运行依赖为 PyQt6 与 psutil（仅用于资源监控）。解析器只使用标准库，不依赖 pandas、numpy 或 lxml。
源码运行前在 macOS 执行 `python scripts/build_native.py` 编译玻璃适配层；未编译时自动使用不透明样式。
核心 API 位于 `healthpro/core.py`，Qt 适配层位于 `healthpro/gui.py`。

### 构建

版本号统一维护在 `healthpro/version.txt`。

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller HealthPro.spec --clean --noconfirm
```

macOS 构建需要 Xcode 26+ SDK 编译小型 Objective-C 适配层（spec 自动执行），在本机架构构建；`rc` 版本输出独立的 `HealthPro Preview.app`，使用独立 bundle ID。
在 iCloud 同步目录构建时，Finder 元数据可能影响签名；可给 PyInstaller 指定本机临时目录作为 `--distpath`。
打包后可运行可执行文件的 `--smoke-test /tmp/healthpro-smoke.json`，它以合成数据验证导入/导出后退出；此选项不会读取个人健康数据。
Windows 输出 `dist/HealthPro`，可在仓库根目录运行 `iscc HealthPro.iss` 生成安装器。
Linux 使用 `HealthPro_linux.spec`，随后运行 `bash linux/build_deb.sh` / `bash linux/build_appimage.sh`。
构建脚本如指定版本参数，必须与源码版本一致。正式发行前须在目标系统构建并验证；PyInstaller 不跨系统编译。

CI 配置包含三系统、Python 3.11/3.12 的回归测试。配置存在不等于已经通过远端验证。
发布工作流在各平台测试、冻结应用 smoke 和打包全部通过后创建正式 tag / Release。不会由运行应用触发上传或发布。

## English summary

Import an Apple Health ZIP, select sources and an inclusive **start-date** range, and export to a new per-job directory.
All work happens locally. Unknown Record identifiers are retained, malformed input fails visibly, and cancellation removes temporary output.
Exports preserve raw records and do not reconcile overlapping sources. Source-name masking does not anonymize timestamps or health values.
The manifest provides row accounting, overlap flags, file checksums, and explicit scope limitations.

## Acknowledgements

Thanks to [@CybDnb](https://github.com/CybDnb) for the original Linux AppImage/deb support and packaging workflow.

[License](LICENSE) · [Issues](https://github.com/leecdiang/Apple-Health-Pro/issues)
