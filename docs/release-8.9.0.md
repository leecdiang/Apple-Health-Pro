## Apple Health Pro v8.9.0

无需打开界面，也能把 Apple 健康导出 ZIP 转成 CSV 或 JSONL。本版加入命令行自动化和四个平台的独立 CLI 下载，保留 v8.8 的桌面界面与原生玻璃效果。

- **命令行**：`sources` 查询来源，`export` 按来源和日期导出；纯标准库源码入口，无需 Qt 或显示服务器。
- **JSONL**：逐行流式写入，保留原始数值文本，提供数值辅助字段和嵌套运动统计。
- **可自动化**：stdout 输出 JSON 结果，stderr 输出进度和错误；明确退出码，支持取消后的临时文件清理。
- **原有保障**：来源名匿名化、分类分片、独立结果目录、未知类型保留、SHA-256 清单和多来源记录说明。
- **文档**：README 新增 macOS 深浅色与导出完成截图、平台下载表及 CLI 示例。截图与测试仅使用合成数据。

### 下载

| 平台 | 桌面版 | CLI |
| --- | --- | --- |
| macOS Apple Silicon | `HealthPro_v8.9.0_macOS_AppleSilicon.dmg` | `HealthProCLI_v8.9.0_macOS_AppleSilicon.tar.gz` |
| macOS Intel | `HealthPro_v8.9.0_macOS_Intel.dmg` | `HealthProCLI_v8.9.0_macOS_Intel.tar.gz` |
| Windows x64 | `HealthPro_Setup_v8.9.0.exe` | `HealthProCLI_v8.9.0_Windows.exe` |
| Linux x86_64 | `.deb` / `.AppImage` | `HealthProCLI_v8.9.0_Linux.tar.gz` |

独立 CLI 无需安装 Python。macOS / Linux 解压后运行 `./healthpro-cli --help`；Windows 在 PowerShell 运行 `.\HealthProCLI_v8.9.0_Windows.exe --help`。桌面 Windows EXE 没有控制台，请使用专用 CLI。

```bash
mkdir -p output
./healthpro-cli sources --input export.zip --quiet
./healthpro-cli export --input export.zip --output output --format jsonl
```

[完整用法](https://github.com/leecdiang/Apple-Health-Pro/blob/v8.9.0/docs/cli.md) · [截图与快速开始](https://github.com/leecdiang/Apple-Health-Pro/tree/v8.9.0#readme)

JSONL 的原始字符串是精确数值依据；辅助浮点值可能舍入。导出保留各来源原始记录，不复现 Apple 健康的去重与优先级，不能直接跨来源累加。来源名匿名化不等于健康数据完全去标识化。

macOS 采用 ad-hoc 签名，尚未进行 Developer ID 公证。桌面版继续默认导出 CSV，JSONL 通过 CLI 使用。所有资产提供 SHA-256 校验值。

Closes #3 via #5.
