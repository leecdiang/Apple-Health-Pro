# 8.8.0rc3 界面审核记录

基于公开版本 v8.7.0 和本地 rc1 数据完整性修复，恢复资源监控与阶段转盘，并按本轮反馈精简界面。尚未创建远端 tag 或 Release。

## 变化

- CPU 采用本进程 CPU 时间除以逻辑核心数，显示 0–100%；内存显示当前 RSS 和占整机物理内存的环形比例。1.5 秒非阻塞采样，隐藏时暂停。
- 转盘：灰色待导入、橙色读取、酒红色导出、绿色就绪/完成、红色失败。状态同时有文字，不只靠颜色。未知进度时 25 FPS；已知进度仅作短插值，空闲不持续旋转。
- 精简重复文案、日期范围与状态说明；来源单行展示，合并全选/取消全选。额外导出选项折叠，说明进入详情；完整路径和来源日期可悬停查看。合成演示保持明确标识。
- 顶部和底部操作栏使用 macOS 26+ NSGlassEffectView；内容卡片保持实色。旧系统使用 NSVisualEffectView，其余平台使用不透明样式。
- 原生玻璃作为透明 Qt native surface 的背景同级视图，不重设 QNSView 的父视图。共享 backing store 对相应圆角区域保留 alpha，避免 Qt 背景遮住玻璃。初版重设父视图造成的重复绘制/闪动不进入交付版。
- 支持系统/浅/深外观；系统降低透明度或增强对比度时切换实色，减少动态效果时关闭进度动画。窗口关闭移除原生材质并停止采样。

## 设计参考

阅读并应用设计原则，没有安装第三方 skill 或执行其中脚本：

- [Apple Design — HIG + Liquid Glass](https://github.com/SudewaJay/apple-design-skill/blob/main/apple-design/SKILL.md)：原生层次、克制强调色、内容可读性、无障碍材质。
- [SwiftUI Expert](https://github.com/AvdLee/SwiftUI-Agent-Skill/blob/main/skills/swiftui-expert-skill/SKILL.md) 及 Liquid Glass 参考：版本检测与降级。项目保持 PyQt 架构，没有声称改写为 SwiftUI。
- [Apple NSGlassEffectView](https://developer.apple.com/documentation/appkit/nsglasseffectview)、本机 Xcode SDK 公共头文件。

## 验证

- 48 项自动测试：包括已有数据正确性/取消/错误清理，以及 CPU 非阻塞归一化、采样失败占位、转盘状态/键盘/计时器、实时无障碍切换、折叠选项和关闭清理。
- ARM64 PyInstaller 应用构建；本地 ad-hoc 签名完整性验证。未进行 Developer ID 公证，尚未进行 Windows/Linux 实机或远端 CI 验证。
- 冻结应用使用 217 条合成记录验证导入/导出，产出 4 个 CSV；原生 smoke 检查玻璃 backend、控件父视图/几何、缩放、深浅色切换、无障碍回退和关闭释放。
- 本地 Cocoa 窗口通过 UI 验证载入演示、全选与导出。Qt 离屏截图仅用于布局，不作为原生玻璃效果的证明。

## 发布边界

本轮仅供本地审核。用户审核通过后再整理正式版本、构建目标平台并发布。当前本地 git 是从 GitHub 文件重建的快照；发布时必须基于真正 upstream commit 应用变更，不得强推本地快照历史。远端 PNG/ICO/Linux 图标需保留。
