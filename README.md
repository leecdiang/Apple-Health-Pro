# Apple Health Pro 🍎 [![Downloads](https://img.shields.io/github/downloads/leecdiang/Apple-Health-Pro/total?style=for-the-badge&color=9B2C2C)](https://github.com/leecdiang/Apple-Health-Pro/releases)

#### A Studio-Grade Data Engine for Apple Health Export.
#### Apple Health Pro 是一款专为数据分析师、健康极客和开发者设计的跨平台桌面工具。它能够高效解析 Apple 健康导出的巨型 XML 压缩包，并将其转化为结构清晰、开箱即用的专业级数据集。

#### Apple Health Pro is a high-performance cross-platform desktop tool designed for data analysts, health enthusiasts, and developers. It efficiently parses massive Apple Health XML export archives and transforms them into organized, analysis-ready professional datasets.

<img width="850" height="878" alt="image" src="https://github.com/user-attachments/assets/e665bf0c-7272-40ce-9183-927bac3cb543" />

## ✨核心功能 (Core Features)
#### ⚡️高性能流式解析 (High-Performance Parsing)
采用 iterparse 空间优化技术。即使面对数 GB 级别的 export.xml，也能保证极低的内存占用，彻底告别程序崩溃。
Utilizing iterparse space optimization. It ensures extremely low memory usage even with multi-GB export.xml files, eliminating system crashes.

#### 🔍多维度来源过滤 (Multi-Dimensional Source Filtering)
自动识别所有数据来源（包括 Apple Watch, iPhone 及第三方 App），支持用户按需选取特定来源进行精准提取，避免数据重复。
Automatically identifies all data sources (including Apple Watch, iPhone, and 3rd-party apps), allowing users to select specific sources for precise extraction and avoid data duplication.

#### 📊 Supported Data Dimensions (支持导出的 15 大数据维度)

Apple Health Pro v8.5.0 utilizes a dual-tag parsing engine to seamlessly extract both raw data points (`Record`) and functional training logs (`Workout`), categorized into 15 professional dimensions:

| 分类序号 | 维度名称 (Category) | 导出文件名 (Exported CSV) | 核心指标涵盖 (Key Metrics Included) |
| :---: | :--- | :--- | :--- |
| **01** | **核心心血管** (Heart & Cardio) | `1_Heart_Cardio.csv` | 心率、静息心率、HRV (心率变异性)、步行平均心率 |
| **02** | **身体成分** (Body Metrics) | `2_Body_Metrics.csv` | 体重、BMI、体脂率、瘦体重、身体水分 |
| **03** | **日常基础消耗** (Daily Activity) | `3_Daily_Activity.csv` | 步数、活动能量消耗、静息能量消耗、步行距离、爬楼层数 |
| **04** | **睡眠与恢复** (Sleep Recovery) | `4_Sleep_Recovery.csv` | 睡眠分析 (核心、深度、快速动眼、清醒等状态) |
| **05** | **步态与行动力** (Mobility & Gait) | `5_Mobility_Gait.csv` | 步行速度、步长、不对称性、双足支撑时间、步态稳定性 |
| **06** | **生殖与生理健康** (Reproductive) | `6_Reproductive.csv` | 经期记录、排卵测试结果、宫颈粘液质量 |
| **07** | **生命体征** (Vitals & Respiratory)| `7_Vitals_Respiratory.csv`| 血氧饱和度、呼吸率、体温、血压 |
| **08** | **跑步硬核动态** (Running Dynamics) | `8_Running_Dynamics.csv` | 跑步功率、垂直振幅、触地时间、跑步步幅、跑步速度 |
| **09** | **骑行表现** (Cycling Stats) | `9_Cycling_Stats.csv` | 骑行功率、踏频、骑行速度、功能性阈值功率 (FTP) |
| **10** | **游泳与水域** (Swimming & Water) | `10_Swimming_Water.csv` | 游泳距离、划水次数、水下深度、水温 |
| **11** | **通用体能训练** (Workouts & Training)| `11_Workouts_Training.csv`| 力量训练、瑜伽、HIIT、传统跑/骑/游等所有手动开启的运动记录 |
| **12** | **环境与感官** (Environment & Senses)| `12_Environment_Senses.csv`| 日照时间、环境音量暴露、耳机音量暴露 |
| **13** | **营养与摄入** (Nutrition & Hydration)| `13_Nutrition_Hydration.csv`| 膳食能量、碳水、蛋白质、饮水量、咖啡因摄入 |
| **14** | **心理状态与正念** (Mindfulness & Mental)| `14_Mindfulness_Mental.csv`| 心理状态打卡、情绪追踪、正念冥想时间 |
| **15** | **症状与病史** (Symptoms & Illness)| `15_Symptoms_Illness.csv` | 头痛、咳嗽、疲劳等手动打卡的各类症状记录 |

#### 📊自动分块导出 (Automated Data Chunking)
针对大规模时间序列数据（如分钟级心率），应用执行自动分片逻辑。当单文件超过 80 万行时自动拆分，确保 Excel 及各类 AI 模型可以流畅加载。
For large-scale time-series data, the app executes auto-sharding. Files are automatically split when exceeding 800,000 rows, ensuring smooth loading in Excel and AI models.

## 🚀 操作指南 (Operation Guide)
#### 准备数据 (Prepare Data)
在 iPhone “健康” App 中点击头像 -> “导出所有健康数据”。获得 export.zip。
Export data in the iPhone "Health" App via Profile -> "Export All Health Data" to obtain export.zip.
<img width="1179" height="563" alt="image" src="https://github.com/user-attachments/assets/9eead494-93f8-4040-9ac5-8d38b6a02fe1" />

#### 加载与索引 (Load & Index)
启动程序，点击 SELECT DATA ARCHIVE (.ZIP)。系统执行索引构建。
Launch the app and click SELECT DATA ARCHIVE (.ZIP). The system builds the data index.

#### 选择来源 (Select Sources)
在 IDENTIFIED SOURCES 列表中勾选目标源。默认状态为“全不选”。
Check target sources in the IDENTIFIED SOURCES list. Default is set to deselect all.

#### 执行导出 (Execute Export)
点击 EXECUTE EXPORT。生成的 CSV 将存储于原压缩包同级目录。
Click EXECUTE EXPORT. CSV files will be saved in the same directory as the source zip.

#### 推荐的提示词 (Prompt)
你是一名具备运动生理学、 心血管医学 和健康数据建模能力的专业分析师。我将提供Apple Health原始数据（CSV），请基于数据进行接近专业体检级别的分析，并严格按照以下结构输出：首先给出【一句话结论】，直接判断整体健康状态（健康 / 亚健康 / 风险状态），不得模糊；然后进行【生理系统拆解分析】，从心血管系统（心率、HRV、静息心率）、神经系统（基于HRV分析交感/副交感平衡）、睡眠恢复系统、代谢与活动水平四个层面分析，必须解释背后的生理机制而非表象；接着进行【趋势建模】，基于时间序列判断是否存在周期性波动、长期改善或恶化趋势

You are a professional analyst with expertise in exercise physiology, cardiovascular medicine, and health data modeling. I will provide raw Apple Health data (CSV). Please conduct a professional, clinical-grade analysis based on this data, adhering strictly to the following structure:

[One-Sentence Conclusion]: Provide a direct assessment of the overall health status (Healthy / Sub-healthy / At-risk) without ambiguity.
[Physiological System Breakdown Analysis]: Analyze four key areas—the cardiovascular system (Heart Rate, HRV, Resting Heart Rate), the nervous system (Sympathetic/Parasympathetic balance based on HRV), the sleep recovery system, and metabolism/activity levels. You must explain the underlying physiological mechanisms rather than merely reporting surface-level observations.
[Trend Modeling]: Based on time-series data, identify periodic fluctuations and determine whether there are long-term trends of improvement or deterioration.
<img width="2442" height="1804" alt="image" src="https://github.com/user-attachments/assets/1658d1ca-fdeb-4142-9187-0a0a14b010c2" />


## 📥下载与安装 (Installation)
无需配置 Python 环境，直接下载构建完成的二进制包：
No Python environment required. Download the pre-built binary packages directly:

#### Windows: HealthPro_Setup_v8.5.0.exe

#### macOS: HealthPro_v8.5.0.dmg（Apple Silicon）

#### macOS: HealthPro_v8.5.0_macOS_IntelChip.dmg （Intel CPU）

##### (注：macOS 初次运行请右键图标选择”打开” / Note: For macOS, right-click and select “Open” for the first launch)

#### Linux: HealthPro-8.5.0-x86_64.AppImage (通用 / Universal)

#### Linux: healthpro_8.5.0_amd64.deb (Debian / Ubuntu)

```bash
# AppImage — 下载即用 / Download and run directly
chmod +x HealthPro-8.4.0-x86_64.AppImage
./HealthPro-8.4.0-x86_64.AppImage

# Debian/Ubuntu — deb 安装 / Install with dpkg
sudo dpkg -i healthpro_8.4.0_amd64.deb
sudo apt-get install -f   # 自动修复依赖 / Fix dependencies if needed
```
## 🙏 Acknowledgements / 鸣谢

This project exists thanks to all the people who contribute. Special thanks to the following developers for their outstanding contributions to Apple Health Pro:
特别感谢以下开发者对本项目的杰出贡献：

* **[@CybDnb](https://github.com/CybDnb)** - For building the Linux native support (AppImage & deb) and the automated CI/CD packaging pipeline. (为本项目构建了完整的 Linux 原生支持与自动化打包流水线。)

## © 2026 LEEcDiang. All rights reserved.

---
### ✍️ About the Author
I'm **LEEcDiang**, a developer passionate about health data and studio-grade tools. 
If you find this tool helpful, check out more of my thoughts and tutorials on my blog:
👉 [**leecdiang.github.io**](https://leecdiang.github.io/myblog-source/)
