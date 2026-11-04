## Apple Health Pro v8.9.1

- AppImage 构建工具固定为官方 1.9.1，工具与运行时均校验官方 SHA-256；发布前验证最终 .deb / AppImage 中的应用。

本版修复代码审查发现的解析、桌面边界和 Linux 打包问题，保持 CSV / JSONL 格式与命令行接口兼容。

- **记录计数**：只导出顶层 Record、Workout 和 StateOfMind，避免 Correlation 内的重复记录被再次计数；不采集未知容器中的嵌套记录。
- **错误处理**：不支持的 XML 编码、截断或损坏的压缩数据返回可读错误。
- **扫描效率**：复用已有来源索引，减少每条记录的临时对象分配。
- 写出时同步计算 SHA-256，避免完成前重新读取全部输出；保留 CSV BOM 和精确字节校验。
- **桌面稳定性**：日期控件限制在公元 1–9999 年；CPU / 内存监控无权限时仍可打开应用。
- **打包**：补齐运行时图标资源；Linux 包从当前源码重新构建，避免旧 dist 被标记为新版本。
- **验证**：补充合成数据回归测试；发布流程在 Linux、Windows、macOS Apple Silicon 和 Intel 分别运行测试及冻结应用 smoke 后发布。

如果此前导出的 ZIP 包含 Correlation，建议使用本版重新导出。不同来源之间仍保留各自的原始记录，不复现 Apple 健康的来源优先级或自动去重，不能直接跨来源累加。

### 下载

- Linux x86_64：`healthpro_8.9.1_amd64.deb`、`HealthPro-8.9.1-x86_64.AppImage`、`HealthProCLI_v8.9.1_Linux.tar.gz`
- Windows x64：`HealthPro_Setup_v8.9.1.exe`、`HealthProCLI_v8.9.1_Windows.exe`
- macOS Apple Silicon：`HealthPro_v8.9.1_macOS_AppleSilicon.dmg`、`HealthProCLI_v8.9.1_macOS_AppleSilicon.tar.gz`
- macOS Intel：`HealthPro_v8.9.1_macOS_Intel.dmg`、`HealthProCLI_v8.9.1_macOS_Intel.tar.gz`

资产附 `SHA256SUMS.txt`。Linux 容器或未安装 FUSE 的系统可使用 AppImage 的 `--appimage-extract-and-run` 模式。

macOS 仍采用 ad-hoc 签名，未进行 Developer ID 公证。默认匿名化只遮蔽来源名称，日期与健康数值仍可能识别个人。所有测试仅使用合成记录。

[使用说明](https://github.com/leecdiang/Apple-Health-Pro/tree/v8.9.1#readme) · [CLI 文档](https://github.com/leecdiang/Apple-Health-Pro/blob/v8.9.1/docs/cli.md)
