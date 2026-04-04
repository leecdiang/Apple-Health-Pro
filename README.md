# Apple Health Pro 🍎
#### A Studio-Grade Data Engine for Apple Health Export.
#### Apple Health Pro 是一款专为数据分析师、健康极客和开发者设计的跨平台桌面工具。它能够高效解析 Apple 健康导出的巨型 XML 压缩包，并将其转化为结构清晰、开箱即用的专业级数据集。

#### Apple Health Pro is a high-performance cross-platform desktop tool designed for data analysts, health enthusiasts, and developers. It efficiently parses massive Apple Health XML export archives and transforms them into organized, analysis-ready professional datasets.

## ✨核心功能 (Core Features)
#### ⚡️高性能流式解析 (High-Performance Parsing)
采用 iterparse 空间优化技术。即使面对数 GB 级别的 export.xml，也能保证极低的内存占用，彻底告别程序崩溃。
Utilizing iterparse space optimization. It ensures extremely low memory usage even with multi-GB export.xml files, eliminating system crashes.

#### 🔍多维度来源过滤 (Multi-Dimensional Source Filtering)
自动识别所有数据来源（包括 Apple Watch, iPhone 及第三方 App），支持用户按需选取特定来源进行精准提取，避免数据重复。
Automatically identifies all data sources (including Apple Watch, iPhone, and 3rd-party apps), allowing users to select specific sources for precise extraction and avoid data duplication.

#### 📦智能数据分类 (Intelligent Data Categorization)
系统自动将原始记录映射至 7 大标准维度空间：
The system automatically maps raw records into 7 standard dimensions:

维度编号 (ID)	维度名称 (Dimension)	包含指标 (Key Metrics)

1	Heart Metrics	心率, 静息心率, HRV；

2	Body Composition	体重, BMI, 体脂率；

3	Activity & Energy	步数, 活动能量, 距离；

4	Sleep Analysis	睡眠分期, 睡眠效率；

5	Mobility & Gait	步行速度, 步长；

6	Reproductive Health	经期追踪, 排卵预测；

7	Vitals & Respiratory	血氧, 血压, 体温；

#### 📊自动分块导出 (Automated Data Chunking)
针对大规模时间序列数据（如分钟级心率），应用执行自动分片逻辑。当单文件超过 80 万行时自动拆分，确保 Excel 及各类 AI 模型可以流畅加载。
For large-scale time-series data, the app executes auto-sharding. Files are automatically split when exceeding 800,000 rows, ensuring smooth loading in Excel and AI models.

## 🚀 操作指南 (Operation Guide)
#### 准备数据 (Prepare Data)
在 iPhone “健康” App 中点击头像 -> “导出所有健康数据”。获得 export.zip。
Export data in the iPhone "Health" App via Profile -> "Export All Health Data" to obtain export.zip.

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

## 📥下载与安装 (Installation)
无需配置 Python 环境，直接下载构建完成的二进制包：
No Python environment required. Download the pre-built binary packages directly:

#### Windows: HealthPro_Setup_v8.2.0.exe

#### macOS: HealthPro_v8.2.0.dmg

##### (注：macOS 初次运行请右键图标选择“打开” / Note: For macOS, right-click and select "Open" for the first launch)


## © 2026 LEEcDiang. All rights reserved.

---
### ✍️ About the Author
I'm **LEEcDiang**, a developer passionate about health data and studio-grade tools. 
If you find this tool helpful, check out more of my thoughts and tutorials on my blog:
👉 [**leecdiang.github.io**]([https://leecdiang.github.io](https://leecdiang.github.io/myblog-source/))
