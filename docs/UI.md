# PaperReady UI Specification

本文档描述 PaperReady 的桌面端 UI 目标状态。实现上以 macOS 桌面工具为基准，产品感受应接近下载管理器、Finder 列表、Xcode Build Log 和 Zotero Connector 的组合，而不是网页式营销页。

## 0. 实现约束

当前应用不应继续依赖系统自带 Python 作为运行时。构建和开发模式按以下方式处理：

* `pnpm build` / Tauri 打包时，将 Python backend 通过 PyInstaller 打包为 sidecar，并压缩进应用 bundle。
* `pnpm tauri dev` 开发时，临时使用 conda `generic` 环境中的 Python 调试 backend。
* UI 不直接暴露 Python 路径选择，除非进入诊断模式。

窗口实现要求：

* 固定主窗口内部布局高度，不允许出现“整个网页再滚动”的双层滚动条。
* 列表、Inspector、Prompt 编辑器等具体区域可以独立滚动。
* macOS 红黄绿窗口按钮必须使用 Tauri / 原生窗口能力实现，不要使用不可点击的 HTML 模拟按钮。
* 自定义标题栏只承担拖拽、导航和工具栏职责，不覆盖系统窗口控制区。

## 1. 整体产品框架

主窗口采用三段式 macOS 桌面结构：

* 左侧：Sidebar 导航栏。
* 中间：当前页面主内容。
* 右侧：按需出现的 Inspector。
* 顶部：原生感 toolbar / titlebar。

默认窗口尺寸：

* 宽度：1180-1280 px。
* 高度：760-820 px。
* Sidebar 宽度：220-240 px。
* Inspector 宽度：320-380 px。
* 主列表最小宽度：680 px。

左侧导航包含：

* 导入
* 任务
* 设置

Sidebar 底部显示运行状态：

* Backend 状态：运行中 / 未连接 / 启动失败。
* Zotero 状态：未检测 / 已连接 / 连接失败。
* Worker 状态：已停止 / 运行中。
* YOLO 模式：全局开关，默认关闭。

状态点可以使用绿色、黄色、红色，但必须同时配合文字，不允许只靠颜色表达含义。

整体视觉原则：

* 使用系统背景、浅灰 sidebar、白色或系统内容背景。
* 使用 SF Pro 字体和 SF Symbols 风格图标。
* 优先使用原生 table/list、segmented control、popover、sheet。
* 主强调色跟随系统 Accent Color。
* 避免大面积渐变、网页卡片堆叠、AI 聊天气泡和夸张动效。
* 成功、警告、失败都使用图标 + 文案组合，例如“已完成”“需复核”“匹配失败”。

## 2. 首页：导入中心

首页承担“快速开始一次论文处理队列”的作用。用户一打开应用，应立刻看到输入论文的主要入口，而不是配置项。

### 2.1 文本导入区

页面主区域顶部是一个大输入框，支持一行一个输入：

* DOI。
* DOI URL。
* arXiv ID 或 arXiv URL。
* 论文标题。
* 出版社页面 URL。
* OpenReview / Semantic Scholar / 项目页 URL。
* Markdown reading list 中的标题和链接。

输入框下方显示轻量提示：

支持 DOI、arXiv、OpenReview、Semantic Scholar、出版社页面、PDF URL 和纯标题。每行会创建一篇文章任务。

输入框右下角放置主按钮：

开始导入

按钮要求：

* 左侧使用 `tray.and.arrow.down.fill` 或 `arrow.down.doc.fill`。
* 输入为空时禁用。
* 输入可识别时激活。
* 点击后立即创建文章级任务，并跳转到“任务 > 当前任务”。

### 2.2 文件上传区

文本框下方放置本地文件导入区。它应低调但足够明确，不要做成大幅宣传卡片。

标题：

或导入本地文件

说明：

拖入 PDF、BibTeX、RIS、CSV 或 ZIP 文件，也可以从 Finder 选择文件。

支持类型：

* PDF：从元数据、首页文字和文件名识别论文。
* BibTeX / RIS / CSV：解析多条文献记录。
* ZIP：展开后按文件类型批量导入。

文件被拖入后，上传区切换为小型文件队列：

| 文件 | 类型 | 状态 | 操作 |
| --- | --- | --- | --- |
| robotics_survey.pdf | PDF | 等待解析 | 移除 |

文件类型图标：

* PDF：`doc.richtext`。
* BibTeX / RIS / CSV：`tablecells`。
* ZIP：`archivebox`。

### 2.3 导入预检查

点击“开始导入”前，首页可以做轻量预检查，但不应阻塞用户进入任务中心。

预检查显示：

* 已识别输入数量。
* 可能重复的输入。
* 无法识别但仍会作为标题尝试匹配的行。
* 本地文件是否可访问。

预检查错误分级：

* 阻塞：文件不存在、文件类型不支持、ZIP 无法读取。
* 非阻塞：标题过短、URL 类型不确定、疑似重复。

非阻塞问题应进入任务中心后由单行任务显示“需复核”，不要在首页要求用户一次性修完。

### 2.4 最近导入

首页下半部分保留“最近导入”区，不抢占主输入框注意力。

显示最近 3-5 个批次：

| 时间 | 来源 | 论文数 | 状态 |
| --- | --- | --- | --- |
| 今天 14:12 | RSS / arXiv Batch | 18 | 处理中 |
| 昨天 | ICRA Papers | 42 | 已完成 |
| 昨天 | SLAM Survey PDFs | 7 | 需复核 |

每行点击后进入任务页，并按该批次过滤当前任务列表。

右上角提供：

查看全部任务

### 2.5 首页空态与错误

首次打开应用时，首页不显示教学长文。只保留一个简短空态：

粘贴 DOI、标题、arXiv 链接，或拖入 PDF 开始。

Backend 未连接时：

* 主按钮禁用。
* 输入框仍可编辑。
* 顶部显示“Backend 未连接，正在尝试启动...”。
* 诊断入口显示 backend URL、Python 运行时和最近错误。

## 3. 任务列表：下载管理器式任务中心

任务列表是 PaperReady 的核心操作页面。它不是“任务批次列表”，而是文章级下载管理器。每一行代表一篇文章或一个待解析的论文输入。

用户在这里能看到：

* 当前有哪些文章等待处理。
* 每篇文章处理到了哪一步。
* 哪些文章需要人工确认。
* 哪些文章失败、能否重试。
* 哪些报告已生成。
* 哪些内容尚未导出到 Zotero。
* 当前 Token 和预算消耗。

### 3.1 顶部工具栏

Toolbar 左侧直接放 segmented control，不再显示单独的“任务”页内标题：

当前任务 | 已导入

Toolbar 右侧使用紧凑操作栏，优先使用短标签或图标按钮：

* 刷新
* 运行一次
* 全部处理
* 启动 / 停止 Worker
* 重试失败项
* 删除 / 移除

图标建议：

* 运行一次：`play.circle`。
* 启动：`play.fill`。
* 停止：`stop.fill`。
* 重试：`arrow.clockwise`。
* 删除：`trash`。

没有选中文章时，依赖选择的按钮保持灰色禁用。
任务页本身由菜单容器承载，不再额外包一层圆角卡片；列表、工具栏和右侧 Inspector 直接铺满内容区域。

### 3.2 当前任务与已导入

当前任务是默认 tab，包含所有还需要用户继续处理的文章：

* 等待定位论文身份。
* 等待用户消歧。
* 等待 PDF 获取或本地 PDF 替换。
* 等待解析或解析中。
* 等待价值评估或需复核。
* 等待生成报告。
* 报告正在生成。
* 报告已生成但尚未导出到 Zotero。
* 处理失败但仍可重试。
* 因预算暂停。

已导入 tab 只放已经成功导出并写入 Zotero 的文章，作为历史记录和回看入口。

当前任务页面每一行展示：

* 文章名字。
* 当前处理进度。
* 推荐阅读程度。
* 拟生成报告文档复杂度。
* Zotero 导出状态。

示例：

| 文章 | 进度 | 推荐阅读程度 | 报告复杂度 | 状态 |
| --- | --- | --- | --- | --- |
| Diffusion Policy for Robot Manipulation | 生成报告 · 68% | 强烈推荐 | 深度论文解析 | 处理中 |
| Survey on Vision-Language-Action Models | 等待生成 | 推荐 | 标准研究笔记 | 等待中 |
| Robust SLAM in Dynamic Scenes | 报告已生成 | 一般 | 摘要级分析 | 待导出 |

用户可以多选文章后批量执行：

* 生成报告。
* 重新生成报告。
* 导出到 Zotero。
* 重试失败项。
* 启用 / 禁用 YOLO。
* 移除文章。

文章已经生成报告但尚未导出到 Zotero 时，仍保留在当前任务页面，并显示“待导出”。只有成功写入 Zotero 后，文章才移动到“已导入”页面。

### 3.3 单篇文章行设计

文章行高度建议为 58-72 px，比 Finder 表格略高，便于承载状态、进度和报告复杂度信息。

左侧：

* 多选框。
* 状态图标。
* 文章标题或原始输入。

状态图标：

* 排队：`clock`。
* 处理中：旋转进度环。
* 需复核：`exclamationmark.triangle.fill`。
* 预算暂停：`creditcard.trianglebadge.exclamationmark` 或同类警告图标。
* 已完成：`checkmark.circle.fill`。
* 失败：`xmark.octagon.fill`。
* 已暂停：`pause.circle.fill`。

主信息区域第一行：

Diffusion Policy for Robot Manipulation

主信息区域第二行：

RSS 2023 · 导入自 DOI 列表 · 目标写入 Robotics / Manipulation

右侧信息区域：

正在生成深度论文解析
68%
强烈推荐
14:27 更新

文章行内部可以显示一条很细的进度条，位于第二行下方。进度条表达 pipeline 步骤完成度，不表达模型调用的瞬时 token 流。

行最右侧只保留真正高频的轻量操作，例如可生成时的“生成”。不要提供“显示详情 / 打开详情”按钮；用户点击整行即可打开右侧 Inspector。

更多菜单：

* 修改报告复杂度。
* 修改报告模型。
* 重新生成报告。
* 导出到 Zotero。
* 替换 PDF。
* 编辑元数据。
* 重新运行失败项。
* 在 Zotero 中打开。
* 移除文章。

### 3.4 列表列定义

默认列：

| 列 | 内容 |
| --- | --- |
| 文章 | 标题、作者年份、来源批次 |
| 定位 | Queued / Locating / Needs disambiguation / Located |
| PDF | Downloading / PDF ready / PDF unavailable / Parse failed |
| 解析 | Waiting / Parsing / Parsed / Failed |
| 推荐 | Very Important / Brief Reading / Unrelated / Needs Review |
| 报告 | Not generated / Ready / Summarizing / Generated / Budget paused |
| Zotero | Not ready / Preview ready / Ready for export / Exported / Failed |
| 成本 | 估算 Token / 实际 Token |
| 下一步 | 消歧、生成报告、导出、重试等主操作 |

小屏宽度不足时，保留“文章、进度、推荐、报告、下一步”，其他列折叠进 Inspector。

### 3.5 文章详情 Inspector

选中某篇文章后，右侧 Inspector 展开。未选中时，右侧收起，主列表占满空间。

顶部显示：

Diffusion Policy for Robot Manipulation
处理中 · 生成报告 68%

Inspector 分区：

* 概览。
* Pipeline。
* 元数据。
* PDF。
* 推荐判断。
* 报告预览。
* Zotero 导出。
* 错误与审计记录。

Pipeline 步骤：

1. 收集来源。
2. 解析文件与链接。
3. 匹配论文元数据。
4. 去重与消歧。
5. 获取 PDF。
6. 解析 PDF。
7. 论文筛选与分类。
8. 生成阅读报告。
9. 写入 Zotero。

每一步显示：

* 已完成。
* 正在处理。
* 等待中。
* 已跳过。
* 出错。

示例：

| 阶段 | 状态 |
| --- | --- |
| 解析 DOI | 已完成 |
| 匹配 Crossref / arXiv Metadata | 已完成 |
| 版本校验 | 已完成 |
| 论文价值筛选 | 强烈推荐 |
| 生成深度论文解析 | 进行中 |
| 写入 Zotero | 等待中 |

文章统计：

* 推荐阅读程度：强烈推荐。
* 报告复杂度：深度论文解析。
* 元数据版本：arXiv / Published Version / User Edited。
* PDF 状态：已缓存 / 用户上传 / 不可用。
* Zotero 状态：待导出。
* 已消耗 Token：18k / 30k。

如果报告已经生成，Inspector 直接显示报告预览，并提供“打开完整报告”。报告预览默认折叠长章节，只显示标题、主要贡献、推荐理由和局限摘要。

如果文章处理出错，错误信息仍在 Inspector 中提示，并在列表行保留明确失败状态。错误区必须包括：

* 失败步骤。
* 用户可读错误。
* 原始错误详情折叠区。
* 最近一次发生时间。
* 可执行恢复动作，例如“重试定位”“替换 PDF”“跳过 PDF 继续”。

### 3.6 消歧与元数据编辑

当定位结果存在多个候选时，文章行显示“需复核”。Inspector 展示候选列表：

| 候选 | 来源 | 年份 | 置信度 | 操作 |
| --- | --- | --- | --- | --- |
| Paper A | arXiv | 2025 | 0.82 | 选择 |
| Paper A Extended | Crossref | 2026 | 0.71 | 选择 |

候选卡片应展示：

* 标题。
* 作者。
* venue / year。
* DOI / arXiv ID。
* 来源 URL。
* 模型或检索器给出的匹配理由。

用户可以：

* 选择候选。
* 编辑元数据后确认。
* 标记为非论文。
* 移除该行。

元数据编辑表单包含：

* Title。
* Authors。
* Year。
* Venue。
* DOI。
* arXiv ID。
* URLs。
* Abstract。

保存后清空下游 PDF、解析、评估和报告结果，并从新身份继续 pipeline。

### 3.7 PDF 与解析状态

PDF 状态要和论文身份状态分开显示。

可能状态：

* 使用用户上传 PDF。
* 已从 arXiv 获取 PDF。
* 已从开放 URL 获取 PDF。
* PDF unavailable，继续 metadata-only 处理。
* PDF mismatch，需要复核。
* Parse failed，可重试或替换 PDF。

用户操作：

* 添加 / 替换本地 PDF。
* 打开缓存 PDF。
* 跳过 PDF 继续。
* 重试 PDF 下载。
* 重试解析。

metadata-only 不是失败状态。它应显示为可继续处理，只是报告质量和推荐置信度会降低。

### 3.8 批量操作

当用户勾选多篇文章时，顶部 toolbar 切换为批量操作模式。

显示：

已选择 6 篇文章

批量控件：

* 报告粒度：标准研究笔记。
* 生成报告。
* 导出到 Zotero。
* 启用 YOLO。
* 禁用 YOLO。
* 重试失败项。
* 移除。

报告粒度下拉：

* 不生成报告。
* Quick Brief。
* Standard Report。
* Detailed Report。
* 保留文章当前设置。

应用时使用 macOS Sheet 确认：

更改 6 篇文章的报告粒度？
已生成的报告不会自动重新生成，除非同时选择“重新生成已完成报告”。

复选项：

* 对后续未处理论文生效。
* 重新生成已完成报告。
* 保留原有人工修改内容。

### 3.9 总进度条

页面底部固定全局进度区域，像下载管理器状态栏。

左侧：

正在处理 76 篇论文 · Worker 运行中

中央：

总进度 128 / 246 篇
[长进度条]

右侧：

Token：1.42M / 2.00M
暂停全部

进度条应以论文处理单元为基础，而不是导入批次数。点击进度区域展开 popover，显示：

* 当前正在运行的文章。
* 队列中的文章。
* 失败文章数量。
* 需复核文章数量。
* Token 使用情况。
* 当前模型调用状态。
* Worker 最近错误。

### 3.10 任务空态

当前任务为空：

没有正在处理的文章

下方提供：

* 导入论文。
* 查看已导入。

已导入为空：

还没有导出到 Zotero 的文章

下方提供：

* 返回当前任务。
* 打开 Zotero 设置。

## 4. Zotero 导出流程

Zotero 导出必须采用显式确认，不允许后台静默写入用户库。

### 4.1 Zotero 状态

任务页和设置页都应显示 Zotero 状态：

* 未配置。
* Connector 可用。
* Bridge URL 可用。
* prepare-only 模式。
* 连接失败。

状态旁边提供“检测 Zotero”按钮。

### 4.2 导出预览

点击“导出到 Zotero”后，先打开导出预览面板或 Sheet。

预览内容：

* 即将导出的文章数量。
* 目标 collection。
* 每篇文章的标题、作者、年份、DOI / arXiv。
* 将写入的 tags。
* 是否附加 PDF。
* 是否写入报告 note。
* 是否存在可能重复项。

用户可切换：

* 包含 PDF 附件。
* 包含报告笔记。
* 仅准备 payload，不写入 Zotero。

底部按钮：

取消
确认导出

导出成功后，文章进入“已导入”。导出失败时，文章保留在“当前任务”，状态显示“导出失败”，并可重试。

### 4.3 Zotero 分类

默认导出分类：

* Very Important。
* Brief Reading。
* Unrelated。
* Needs Review。

推荐阅读程度到 Zotero 的映射：

| 推荐 | Collection / Tag |
| --- | --- |
| Very Important | Very Important |
| Brief Reading | Brief Reading |
| Unrelated | Unrelated |
| Needs Review | Needs Review |

用户可以在设置页调整 collection 映射。

## 5. 设置页面

设置采用标准 macOS Settings 风格。左侧为分类，右侧为设置表单。不要在主任务页塞入复杂配置。

设置分类：

* 通用。
* 研究兴趣。
* 模型与 Token。
* Prompts。
* Zotero 与导出。
* 隐私与缓存。
* 诊断。

### 5.1 通用

字段：

* 默认启动页面：导入 / 任务。
* 默认报告类型。
* YOLO 默认行为。
* 预算超限行为：暂停并询问 / 允许本批次继续 / 禁止继续。
* 语言偏好占位：English / 简体中文 / 跟随系统。

YOLO 说明必须清楚：

YOLO 会让后台 Worker 对符合条件的文章自动生成报告，但仍会遵守预算限制，且 Zotero 导出始终需要用户确认。

### 5.2 研究兴趣

研究兴趣用于 Evaluator 和 Summarizer。

界面：

* 多行文本框。
* 可选结构化标签。
* 最近导入上下文提示。

占位示例：

我关注机器人操作、具身智能、视觉语言动作模型、长程任务规划和可复现实验。

底部显示：

此内容会被用于推荐阅读程度和报告生成，不会自动写入 Zotero。

### 5.3 模型与 Token

字段：

* API Base URL。
* API Key。
* 定位模型。
* 评估模型。
* 总结模型。
* 每批预算。
* 每日预算。
* 每月预算。
* 定位并发。
* 评估并发。
* 总结并发。

API Key 输入：

* 默认密码框。
* 支持显示 / 隐藏。
* 保存到本地安全存储；如果当前平台不支持，则明确提示保存位置。

预算显示：

* 当前批次已用。
* 今日已用。
* 本月已用。
* 最近一次暂停原因。

### 5.4 Prompts

Prompt 页面包括：

* Prompt 名称与作用。
* Prompt 编辑器。
* 可插入变量。
* 输入变量预览。
* 最终 Prompt 预览。
* 恢复默认按钮。

Prompt 类型：

* Locator prompt。
* Evaluator prompt。
* Quick Brief prompt。
* Standard Report prompt。
* Detailed Report prompt。
* Zotero note prompt。

变量：

* `{{title}}`
* `{{abstract}}`
* `{{authors}}`
* `{{venue}}`
* `{{year}}`
* `{{doi}}`
* `{{arxiv_id}}`
* `{{pdf_text}}`
* `{{sections}}`
* `{{references}}`
* `{{user_research_context}}`
* `{{value_recommendation}}`

变量以可点击 token 标签形式出现。用户点击变量后插入到光标位置。

编辑器要求：

* 等宽字体。
* 支持撤销。
* 显示未保存状态。
* 保存前做最小校验：变量括号是否闭合、Prompt 是否为空。

### 5.5 Zotero 与导出

字段：

* Zotero Connector URL。
* Zotero Bridge URL。
* 导出模式：prepare-only / connector / bridge。
* 默认 collection。
* 推荐等级到 collection 的映射。
* 默认是否包含 PDF。
* 默认是否包含报告 note。

操作：

* 检测 Zotero。
* 发送测试 payload。
* 打开 Zotero。

说明：

PaperReady 不直接修改 Zotero SQLite，不自动删除 Zotero 条目，也不自动合并疑似重复项。

### 5.6 隐私与缓存

显示：

* SQLite 数据库位置。
* PDF 缓存目录。
* 报告缓存目录。
* 当前缓存大小。

操作：

* 打开数据目录。
* 清理失败任务缓存。
* 清理已导出文章的临时文件。
* 清理全部本地缓存。

清理全部本地缓存必须使用确认 Sheet，并明确不会删除 Zotero 库内容。

### 5.7 诊断

诊断页用于开发和排错，默认不打扰普通用户。

内容：

* Backend URL。
* Backend health。
* Worker 状态。
* Python runtime。
* PyInstaller sidecar 状态。
* 数据库路径。
* 最近 20 条错误。
* 当前 app 版本。
* 当前 commit / build id。

操作：

* 重启 backend。
* 导出诊断日志。
* 打开开发者工具。

## 6. 状态、错误与恢复

UI 必须让用户知道每篇文章的“当前状态”和“下一步动作”。

### 6.1 核心状态

文章状态：

* Queued。
* Locating。
* Needs disambiguation。
* Located。
* Downloading PDF。
* PDF unavailable。
* PDF ready。
* Parsing。
* Parse failed。
* Evaluating。
* Needs review。
* Ready for report。
* Summarizing。
* Budget paused。
* Ready for export。
* Exported。
* Failed。

每个状态都必须映射到：

* 列表短文案。
* Inspector 详细说明。
* 下一步主操作。
* 是否可被 Worker 自动推进。
* 是否需要用户确认。

### 6.2 错误展示

错误不使用 toast 作为唯一反馈。Toast 只适合短暂提示，真实错误必须落在对应文章行和 Inspector。

错误信息分三层：

* 列表：短状态，例如“PDF 解析失败”。
* Inspector：用户可读原因和恢复按钮。
* 折叠详情：原始异常、HTTP 状态码、模型响应摘要。

恢复动作示例：

* 重试当前步骤。
* 从定位步骤重跑。
* 替换 PDF。
* 跳过 PDF 继续。
* 编辑元数据。
* 降低报告复杂度。
* 提高预算后继续。

### 6.3 预算暂停

当预计消耗超过预算时，文章状态变为 `Budget paused`，不能静默继续。

UI 显示：

* 预计 Token。
* 当前预算剩余。
* 触发暂停的阶段。
* 使用的模型。

用户操作：

* 取消生成。
* 降低报告复杂度。
* 仅对所选文章放行。
* 调整预算设置。

### 6.4 YOLO 模式

YOLO 是后台自动处理能力，不是无确认导出。

规则：

* 全局 YOLO 默认关闭。
* 文章级 YOLO 可以继承全局、强制开启或强制关闭。
* YOLO 可以自动推进到报告生成。
* YOLO 必须遵守预算。
* Zotero 导出始终需要显式确认。

UI 表达：

* Sidebar 底部显示全局 YOLO。
* 行内或 Inspector 显示该文章 YOLO 状态。
* 批量工具栏支持启用 / 禁用所选文章 YOLO。

## 7. 视觉与交互规范

### 7.1 密度

PaperReady 是操作工具，不是宣传网站。

推荐密度：

* Sidebar item 高度：32-36 px。
* Toolbar 高度：44-52 px。
* 表格行高：58-72 px。
* Inspector 分区标题：13-14 px semibold。
* 正文：13-14 px。
* 辅助文案：12 px。

### 7.2 卡片使用

不要把每个模块都做成大卡片。

允许使用卡片的场景：

* 候选论文。
* 导出预览中的单篇文章摘要。
* 错误详情。
* 必要的内联提示或确认 Sheet。

不应使用卡片的场景：

* 整个任务列表。
* 整个设置页面。
* 整个首页主输入区。
* Sidebar。
* Inspector 每一个分区。

### 7.3 表格与列表

表格优先级高于瀑布流和卡片网格。

要求：

* 列标题固定。
* 主列表可垂直滚动。
* 行 hover 显示次要操作。
* 选中行高亮。
* 多选状态明确。
* 长标题最多两行，超出省略并可在 Inspector 查看完整标题。

### 7.4 可访问性

基本要求：

* 所有 icon-only 按钮必须有 tooltip。
* 状态不能只靠颜色表达。
* 表单字段必须有 label。
* 支持键盘 Tab 聚焦。
* 支持 Enter 触发默认按钮。
* 支持 Escape 关闭 Sheet / Popover。
* 错误文案清晰可读，不只显示代码。

### 7.5 响应式

目标主要是桌面宽屏，但窗口变窄时必须保持可用：

* 小于 1000 px 时 Inspector 默认收起。
* 小于 900 px 时隐藏低优先级列。
* Sidebar 可折叠为图标栏。
* Toolbar 操作折叠进更多菜单。

## 8. 页面验收清单

首页完成标准：

* 可以粘贴多行输入。
* 可以拖入或选择文件。
* 可以看到导入预检查。
* 可以创建文章级任务并跳转任务页。
* Backend 未连接时有明确提示。

任务页完成标准：

* 有“当前任务 / 已导入”两个 tab。
* 当前任务展示文章级行，而不是批次级任务。
* 每行显示文章名、进度、推荐阅读程度、报告复杂度和状态。
* 待生成、生成中、已生成未导出、需复核、失败可重试都留在当前任务。
* 已成功导出 Zotero 的文章进入已导入。
* 支持多选批量生成报告和导出 Zotero。
* 右侧 Inspector 可以查看单篇文章进度、错误、报告预览和 Zotero 状态。

Zotero 完成标准：

* 导出前有预览和确认。
* 可以选择是否包含 PDF 和报告 note。
* 导出失败可恢复，文章不丢失。
* 不直接写 Zotero SQLite。

设置页完成标准：

* 覆盖研究兴趣、预算、API、模型、并发、Prompt、Zotero、缓存和诊断。
* Prompt 可编辑、可预览、可恢复默认。
* API Key 有安全输入和保存说明。
* YOLO 和预算行为解释清楚。

视觉完成标准：

* 没有网页式大滚动页面。
* 红黄绿窗口按钮可点击并由原生窗口能力处理。
* 列表、Inspector、Settings 各自独立滚动。
* 状态均有文字和图标。
* 没有大面积渐变、装饰性光斑或营销页 hero。
