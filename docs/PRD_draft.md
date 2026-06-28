下面是可直接作为项目 README / PRD 初稿的产品文档。实现上采用 local-first 独立应用 + 可选 Zotero 插件桥接：主程序承担联网检索、PDF 解析、LLM 路由、缓存与人工复核；Zotero 只负责导入、分类、标签、笔记与附件管理。Zotero 官方支持通过本地 JavaScript API 操作桌面端本地库，而 Web API 的写入面向在线库，因此本地优先写回应走插件或本地桥接，不应直接修改 SQLite。 

Paper Triage Agent

面向个人研究工作流的本地优先 AI 文献分诊与 Zotero 管理系统

1. 产品定位

Paper Triage Agent 是一个面向研究者的本地优先文献处理工具。

用户可以一次性输入 DOI、论文标题、BibTeX、PDF、ChatGPT Deep Research 阅读列表、Share Link、Markdown 文本或 Zotero 条目。系统自动完成论文身份匹配、版本识别、重复检测、PDF 获取与解析、基于用户研究兴趣的价值评估，并将论文分流到不同阅读队列。

产品不以“自动总结所有论文”为目标，而是帮助用户做出更合理的阅读资源分配：

* 高价值论文：用户自己精读，AI 只作为按需解释与检索助手；
* 中等价值论文：由 AI 生成高密度研究摘要，替代部分原文阅读；
* 低价值论文：仅保留元数据与归档理由，不消耗 PDF 解析和大模型预算；
* 不确定论文：先进行廉价粗筛，等待用户复核。

核心目标是将非结构化的论文输入、Deep Research 引用列表和阅读推荐，转化为可验证、可去重、可审阅、可写回 Zotero 的个人文献队列。

⸻

2. 用户问题

研究者在进行文献调研时通常会遇到以下问题：

1. Deep Research、搜索引擎和聊天记录一次返回数十篇论文、网页、项目页与博客，难以快速区分真正值得阅读的材料。
2. 同一工作可能同时存在 arXiv、OpenReview、会议版本、期刊扩展版本、项目页、GitHub 仓库与出版社页面。
3. DOI、标题和 BibTeX 往往不完整或存在错误，容易导入错误论文。
4. 用户没有时间全文阅读所有“有一点相关”的论文，但又不希望只看 abstract。
5. Zotero 擅长管理文献，但不擅长执行复杂的联网检索、LLM 阅读评估和个性化优先级排序。
6. 论文的重要程度与 AI 总结需求不是同一件事：最重要的论文往往值得用户亲自读；中等价值论文反而最适合 AI 做替读式总结。
7. 导师丢给你一堆论文名字，让你自己读

⸻

3. 产品目标

3.1 核心目标

* 支持从多种输入形式识别并匹配论文；
* 自动消歧、版本合并和本地 Zotero 去重；
* 自动寻找合法开放版本 PDF，或允许用户补充 PDF；
* 根据用户研究兴趣、项目背景和规则，对论文进行初筛；
* 支持用户在人工复核阶段决定“论文价值”和“AI 处理深度”；
* 将处理结果写回 Zotero collection、tag、note 和 attachment；
* 全流程可审计：每个判断保留来源、证据、模型、提示词版本与置信度。

3.2 非目标

第一版不实现：

* 自动绕过付费墙下载 PDF；
* 自动删除 Zotero 文献；
* 默认对全部论文调用旗舰模型全文总结；
* 直接修改 Zotero SQLite；
* 依赖 ChatGPT Share Link 的未公开页面结构或内部接口；
* 代替用户完成核心论文的主动理解。

⸻

4. 典型使用场景

场景 A：输入多篇论文

用户粘贴：

10.48550/arXiv.2601.12345
Attention is all you need
https://arxiv.org/xxxxx

系统：

1. 识别 DOI 或 arXiv ID；
2. 查询多个学术元数据源；
3. 查找正式版、预印本、OpenReview、项目页与开放 PDF；
5. 生成候选论文卡片；
6. 由用户选择：
    * 核心必读；
    * AI 深度总结；
    * 轻量背景保留；
    * 归档。

场景 B：导入 Deep Research 参考文献列表

用户粘贴 ChatGPT Deep Research 报告正文、Markdown reading list、Share Link 或导出的 PDF。

系统：

1. 提取 URL、DOI、arXiv ID、BibTeX block、标题列表和推荐理由；
2. 区分 paper、dataset、project page、GitHub、blog、news、documentation；
3. 只将论文默认送入论文处理流程；
4. 保存原始上下文，例如：
    * “key baseline”
    * “must read”
    * “historical background”
    * “conflicting evidence”
    * “recommended for egocentric manipulation”
5. 将用户当次 Deep Research 的筛选意图解析为临时 profile；
6. 与用户长期兴趣 profile 合并后进行排序。

场景 C：批量导入 20 篇论文

用户从 Deep Research、会议论文列表或导师推荐中一次导入约 20 篇论文。

系统：

20 篇候选
  ↓
身份解析、版本合并、Zotero 查重
  ↓
全部执行低成本粗筛
  ↓
用户人工复核价值与处理方式
  ↓
仅对中等价值论文执行 AI 深度替读
  ↓
高价值论文进入 Core Reading
  ↓
低价值论文进入 Archive

⸻

5. 总体系统架构

┌──────────────────────────────────────────────┐
│                  User Interface              │
│  输入 / Inbox / Review / Report / Settings   │
└───────────────────────┬──────────────────────┘
                        │
┌───────────────────────▼──────────────────────┐
│              Local Orchestrator               │
│  Job Queue / Cache / Cost Guard / Audit Log   │
└───────┬───────────────┬───────────────┬──────┘
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Identity     │ │ PDF Pipeline │ │ LLM Pipeline │
│ Resolver     │ │ Extractor    │ │ Router       │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
Crossref/OpenAlex   Local PDF        Cheap / Balanced /
Semantic Scholar    GROBID/PyMuPDF   Flagship Models
Unpaywall/arXiv
       │
       ▼
┌──────────────────────────────────────────────┐
│                 Zotero Bridge                 │
│ Plugin / Local JavaScript API / Local HTTP    │
└──────────────────────────────────────────────┘

推荐实现形态：

Desktop shell: Tauri + React
Backend: Python + FastAPI
Task queue: asyncio + SQLite/DuckDB task table
Local store: SQLite or DuckDB
PDF extraction: GROBID + PyMuPDF fallback
LLM orchestration: OpenAI Responses API
Zotero integration: Zotero plugin + localhost bridge

⸻

6. 输入模块

6.1 支持输入类型

输入类型	示例	处理方式
DOI	10.1000/xyz	标准化 DOI 后直接查询
DOI URL	https://doi.org/...	提取 DOI 并归一化
arXiv ID	arXiv:2501.01234	查询 arXiv 元数据与版本
BibTeX	@inproceedings{...}	解析 DOI、title、author、year、venue
标题	"Vision-Language-Action..."	多源检索 + 候选消歧
标题 + 作者	"Title", Author, 2025	提高候选匹配置信度
本地 PDF	拖拽 PDF	从 PDF metadata、首页、参考信息识别
RIS / CSL JSON	文献导出文件	映射为统一 CanonicalPaper
Markdown reading list	标题、链接、理由	提取论文与推荐上下文
ChatGPT Share Link	Share URL	best-effort 获取可见文本并抽取引用
Deep Research PDF	导出的研究报告	解析引用、链接、标题和上下文
Zotero 条目	当前选中项	读取本地 item 与附件信息

6.2 输入归一化

所有输入统一转换为：

{
  "raw_input_id": "uuid",
  "source_type": "doi | bibtex | title | pdf | chatgpt_share | markdown | zotero",
  "raw_text": "...",
  "extracted_identifiers": {
    "doi": [],
    "arxiv_id": [],
    "semantic_scholar_id": [],
    "openalex_id": [],
    "urls": []
  },
  "context": {
    "source_role": "must_read | baseline | survey | unknown",
    "original_rationale": "...",
    "source_query": "...",
    "import_profile": {}
  }
}

⸻

7. 论文身份匹配与消歧

7.1 数据源策略

系统采用“确定性学术 API 优先，LLM 联网检索兜底”的策略。

第一层：确定性元数据源

DOI / 标准书目信息：
  Crossref
论文、作者、主题、引用网络：
  OpenAlex
  Semantic Scholar
开放获取版本：
  Unpaywall
  arXiv
  OpenReview
  论文作者主页 / 机构仓储

Crossref 提供 works 等元数据查询接口；OpenAlex 提供论文、作者、机构、主题等研究图谱数据；Semantic Scholar API 可检索论文、作者、引用和 venue 信息。(www.crossref.org⁠￼)

第二层：OpenAI Web Search 兜底

当出现以下情况时，调用 OpenAI Responses API 并启用 web search：

* 标题过于模糊；
* 搜索结果存在多个重名或近似标题；
* DOI/BibTeX 字段缺失；
* 论文可能仅存在于项目页、OpenReview 或作者主页；
* 需要寻找正式发表版本；
* 需要确认某个 PDF 是否属于某篇论文；
* 需要确认某个 URL 是论文页、项目页还是 GitHub 仓库。

OpenAI Responses API 支持 web search 工具，适合作为候选论文发现与网页证据补充层；其输出必须要求返回结构化候选与来源 URL，而不能直接信任自然语言结论。(platform.openai.com⁠￼)

7.2 匹配流程

输入
  ↓
提取 DOI / arXiv ID / 标题 / 作者 / 年份 / venue
  ↓
确定性查询：
Crossref + OpenAlex + Semantic Scholar + arXiv
  ↓
候选标准化
  ↓
候选评分
  ↓
高置信度：自动确认
低置信度：OpenAI web search 补充候选
仍存在冲突：人工选择

7.3 候选评分

identity_score =
  0.45 × normalized_title_similarity
+ 0.20 × author_overlap
+ 0.15 × year_consistency
+ 0.10 × venue_consistency
+ 0.10 × identifier_consistency

自动确认阈值：

top1_score >= 0.90
AND top1_score - top2_score >= 0.08
AND no conflicting DOI/arXiv evidence

进入人工消歧的条件：

top1_score < 0.90
OR top1_score - top2_score < 0.08
OR title conflict exists
OR multiple versions have unclear parent-child relation

7.4 消歧 UI

用户看到候选卡片：

Candidate A
- Title
- Authors
- Year / Venue
- DOI / arXiv
- PDF availability
- Match confidence
- Why matched
Candidate B
- 同样字段

用户操作：

[选择此版本]
[标记为同一工作不同版本]
[不是我要找的论文]
[手动编辑元数据]

⸻

8. 版本识别与去重

8.1 版本类型

系统显式记录：

preprint
conference
journal
workshop
camera_ready
openreview_submission
technical_report
project_page
code_repository

8.2 版本关系

{
  "work_family_id": "work:uuid",
  "canonical_version_id": "doi:...",
  "versions": [
    {
      "version_id": "arxiv:...",
      "type": "preprint",
      "relationship": "earlier_version"
    },
    {
      "version_id": "doi:...",
      "type": "conference",
      "relationship": "canonical"
    }
  ]
}

默认策略：

* 会议/期刊正式版本优先作为 canonical item；
* 预印本 PDF 可作为附件或备选 PDF；
* journal extension 不自动视为重复，应提示用户判断是否有实质扩展；
* 同一 work family 只创建一个主 Zotero item，必要时在 note 中记录版本关系。

8.3 Zotero 去重

去重优先级：

1. DOI exact match
2. arXiv ID exact match
3. OpenAlex / Semantic Scholar external ID
4. normalized title exact match
5. title similarity + author overlap + year consistency

系统只读查询 Zotero 本地库，得到已有条目、collection、tags 和 attachment。

若检测到已有条目：

[已有主条目]
[已有预印本，发现正式会议版]
[已有论文但无 PDF]
[疑似重复，需确认]

默认不自动创建重复条目。

⸻

9. PDF 获取与合法性策略

9.1 PDF 来源优先级

1. 用户上传 PDF
2. Zotero 已有 attachment
3. arXiv / OpenReview
4. 论文作者主页
5. 机构 repository
6. Unpaywall 提供的合法 OA 位置
7. 仅保存 metadata，等待用户补充 PDF

Unpaywall 用于发现开放获取论文版本和合法全文位置，不用于绕过付费墙。(unpaywall.org⁠￼)

9.2 PDF 质量检查

每个 PDF 入库前执行：

- 是否可打开；
- 页数是否合理；
- 首页标题与候选论文是否一致；
- 是否为完整论文而不是 poster、slides、supplementary；
- 是否存在可提取文本；
- 是否需要 OCR；
- 是否为最终版本、预印本或作者稿。

输出：

{
  "pdf_quality": 0.0,
  "pdf_type": "full_paper | supplementary | slides | unknown",
  "text_extractable": true,
  "requires_ocr": false,
  "title_verified": true
}

⸻

10. PDF 解析与结构化中间表示

10.1 解析工具链

默认：

GROBID:
  论文结构、标题、作者、章节、参考文献、图表标题
PyMuPDF:
  页码、文本提取、局部段落、渲染与 fallback
pdfplumber:
  表格候选提取与 layout fallback
OCR:
  仅用于扫描版、文本层损坏或图像 PDF

10.2 结构化 Paper IR

{
  "paper_id": "uuid",
  "metadata": {
    "title": "...",
    "authors": [],
    "year": 2026,
    "venue": "...",
    "doi": "...",
    "arxiv_id": "..."
  },
  "sections": [
    {
      "section_id": "method",
      "heading": "Method",
      "page_start": 3,
      "page_end": 6,
      "text": "..."
    }
  ],
  "figures": [
    {
      "figure_id": "fig2",
      "page": 4,
      "caption": "...",
      "image_path": "..."
    }
  ],
  "tables": [],
  "references": [],
  "quality": {
    "text_coverage": 0.94,
    "structure_confidence": 0.87
  }
}

10.3 分层阅读输入

系统不默认将完整 PDF 直接发送给旗舰模型。

粗筛阶段输入：

Title
Abstract
Introduction
Conclusion
Figure captions
Table captions
Metadata

深度替读阶段输入：

Factual paper card
Method sections
Experiment sections
关键图表及 captions
Limitations / failure cases
用户 research profile

核心论文辅助阶段输入：

用户选择的段落、图表或章节
用户问题
与用户项目相关的上下文

OpenAI API 支持文件输入与结构化输出；产品可把 PDF 作为模型输入或在本地先完成解析后，仅发送必要片段。为了控制成本、可追溯性与页码引用，默认采用“本地结构化解析优先，模型输入精选证据片段”的方案。(platform.openai.com⁠￼)

⸻

11. LLM 模型路由

11.1 模型层级

系统不在产品默认 UI 中强调具体模型名称，而是提供任务层级：

Cheap
Balanced
Flagship
Manual

高级设置中允许用户映射实际模型，例如：

model_policy:
  cheap:
    model: "gpt-4o-mini-or-equivalent"
    use_cases:
      - title normalization
      - candidate ranking
      - citation extraction
      - basic metadata cleanup
      - low-cost triage
  balanced:
    model: "mid-tier reasoning model"
    use_cases:
      - abstract/introduction/conclusion rough reading
      - relevance scoring
      - structured factual card
      - basic report generation
  flagship:
    model: "GPT-5.5-or-latest-flagship"
    use_cases:
      - medium-value AI substitute brief
      - difficult method reconstruction
      - evidence-grounded detailed report
      - cross-paper comparison
      - project-specific technical analysis
  manual:
    model: null
    use_cases:
      - core papers selected for self-reading

11.2 模型路由原则

论文价值 ≠ AI 处理深度

系统保存两个独立字段：

{
  "paper_value": "high | medium | low | uncertain",
  "reading_mode": "self_read | ai_substitute | skim | archive",
  "analysis_depth": "none | light | standard | deep",
  "model_tier": "cheap | balanced | flagship | manual"
}

11.3 默认路由策略

routing_policy:
  high_value:
    default_reading_mode: self_read
    default_analysis_depth: none
    default_model_tier: manual
    available_actions:
      - explain_selected_passage
      - inspect_figure_or_table
      - compare_with_project
      - extract_implementation_details
      - verify_claim
  medium_value:
    default_reading_mode: ai_substitute
    default_analysis_depth: deep
    default_model_tier: flagship
    expected_output:
      - research_brief
      - method_explanation
      - evidence_map
      - limitations
      - project_relevance
      - upgrade_to_full_read_recommendation
  low_value:
    default_reading_mode: archive
    default_analysis_depth: none
    default_model_tier: none
    retained_output:
      - metadata
      - abstract
      - one_line_archive_reason
  uncertain:
    default_reading_mode: skim
    default_analysis_depth: light
    default_model_tier: cheap_or_balanced

⸻

12. AI 初筛

12.1 初筛目标

初筛不是决定论文“好不好”，而是判断：

- 是否与用户当前研究方向相关；
- 是否需要进入人工复核；
- 是否像同一工作不同版本；
- 是否有值得进一步处理的 PDF；
- 是否属于 paper / dataset / code / project page / blog；
- 是否有明显的低优先级信号。

12.2 输入

- 标题
- abstract
- metadata
- 当前用户 profile
- 当前导入任务的临时筛选条件
- 必要时 introduction/conclusion

12.3 输出格式

{
  "content_type": "paper | dataset | code | project_page | blog | documentation | other",
  "relevance_score": 0.0,
  "relevance_reasons": [],
  "positive_signals": [],
  "negative_signals": [],
  "recommended_value": "high | medium | low | uncertain",
  "recommended_reading_mode": "self_read | ai_substitute | skim | archive",
  "confidence": 0.0,
  "needs_pdf": true,
  "needs_human_review": true
}

12.4 用户 profile

用户可以维护长期兴趣 profile：

research_interests:
  - vision-language-action
  - dexterous manipulation
  - egocentric video pretraining
  - world models
  - active SLAM
  - 3D reconstruction
  - transformer sequence modeling
positive_signals:
  - real robot experiments
  - egocentric human-to-robot transfer
  - large-scale dataset
  - strong ablations
  - open-source code
  - reproducible implementation details
  - steerable or controllable policies
negative_signals:
  - simulation only
  - no ablation
  - weak baselines
  - inaccessible data
  - novelty mainly prompt engineering
  - benchmark gains without mechanism analysis

一次 Deep Research 导入也可以提供临时 profile：

import_profile:
  query: "2024-2026 egocentric VLA transfer"
  preferred_evidence:
    - real robot
    - public code
    - large-scale data
  exclusions:
    - survey only
    - simulation only

最终评分同时考虑长期 profile 与本次导入意图。

⸻

13. 人工复核界面

13.1 复核卡片

每篇论文显示：

论文标题
作者 / 年份 / venue
匹配置信度
PDF 状态
与当前项目相关性
初筛理由
原始推荐上下文
Zotero 重复检测结果
预计处理成本

用户选择：

( ) Core Reading
    我自己精读；默认不生成完整总结
( ) AI Briefing Queue
    中等价值；让 AI 生成深度替读报告
( ) Citation / Background
    只保留背景、引用或轻量摘要
( ) Archive
    当前不处理；仅保留 metadata 与归档理由
( ) Needs Review
    论文身份、版本或价值尚不明确

13.2 AI 报告模型选择

当用户选择 AI Briefing Queue 时，再显示：

报告级别：
[快速卡片]
[研究摘要]
[深度替读]
[横向比较]
模型档位：
[省钱]
[平衡]
[高质量]
预计：
- 输入文本量
- 预计 token 区间
- 预计费用区间
- 预计输出长度

产品默认推荐，而不是强制：

快速卡片 → Cheap
研究摘要 → Balanced
深度替读 → Flagship
横向比较 → Flagship

⸻

14. 中等价值论文的深度替读报告

14.1 输出目标

深度替读报告应帮助用户“不完整读原文也能知道是否值得进一步投入”。

输出必须避免把推测写成事实，并为关键判断绑定原文证据。

14.2 固定报告结构

# Paper Brief
## One-sentence verdict
这篇论文是否值得继续阅读，以及建议投入多少时间。
## Problem and setting
论文解决什么问题，输入输出是什么，适用场景是什么。
## Core contribution
作者真正提出了什么，不只是论文声称的贡献。
## Method reconstruction
从输入到输出的数据流、模块关系、训练目标和推理流程。
## Evidence and experiments
最有说服力的实验、关键 baseline、数据集、评估协议和 ablation。
## What the paper does not establish
论文没有证明什么；结论的边界、潜在混杂因素和局限。
## Relevance to my work
与用户当前项目的具体关联：
- 可复用模块；
- 可借鉴数据；
- 可比较动作表示；
- 可引用的 related-work 位置；
- 可能冲突的假设。
## Reading recommendation
- Enough to know from this brief
- Read only Sections X and Y
- Upgrade to full reading
- Keep as citation/background only
## Evidence map
每个关键结论对应：
- section
- page
- figure/table
- source excerpt

14.3 输出约束

* 所有事实型结论必须带 section/page/evidence；
* 不允许编造实验数据、模型规模、数据规模或代码可用性；
* 不确定时输出 unknown；
* 对“是否值得读”的判断必须分离：
    * 相关性；
    * 新颖性；
    * 可信度；
    * 实现价值；
    * 当前时效性；
    * 用户项目适配度。

⸻

15. 高价值论文的阅读辅助

高价值论文默认不由 AI 自动替读。

用户自己读原文时，系统提供：

- PDF 全文检索；
- 选段解释；
- 图表解释；
- 公式或训练目标解释；
- 方法输入输出数据流还原；
- 实现细节提取；
- 与用户项目对照；
- “这篇论文真正证明了什么”核验；
- 生成个人阅读笔记模板；
- 按问题检索相关章节。

例：

“解释 Section 3.2 的 action representation。”
“Figure 4 的 ablation 到底支持什么结论？”
“把这篇方法与 EgoSteer 的 world-model expert 设计对照。”
“找出作者在 appendix 中关于失败案例的讨论。”

⸻

16. ChatGPT Deep Research 与 Share Link 导入

16.1 支持策略

支持：

1. 直接粘贴 Deep Research 正文
2. 粘贴 Markdown reading list
3. 上传 Deep Research 导出的 PDF
4. 粘贴 ChatGPT Share Link
5. 浏览器扩展把当前可见 ChatGPT 页面发送到本地应用

优先级：

Markdown / plain text
  > 浏览器扩展导出当前可见内容
  > Share Link best-effort 解析
  > Deep Research PDF 解析

16.2 Share Link 原则

Share Link 不视为稳定或公开的结构化 API。

实现要求：

- 仅解析可见页面文本、URL、DOI、标题和列表；
- 不依赖网页内部 React payload、私有接口或 DOM class 名；
- 失败时提示用户：
  “请粘贴正文、导出 Markdown，或上传 Deep Research PDF。”
- 不将 Share Link 作为唯一导入方式；
- 不自动公开、转发或长期保存包含隐私内容的完整对话。

16.3 引用抽取

对于 reading list / Deep Research 文本：

提取：
- DOI
- arXiv ID
- URL
- BibTeX
- Markdown 链接
- 论文标题样式列表
- 年份、作者、venue
- 推荐级别词：
  must read / key / seminal / baseline / optional
- 原始推荐理由和上下文

分类：

paper
dataset
code repository
project page
blog/news
documentation
other

默认只有 paper 进入 Zotero 文献处理流程；其他资源可进入研究笔记或项目资源列表。

⸻

17. Zotero 集成

17.1 本地优先策略

Zotero 写入通过插件或本地 JavaScript API 完成：

独立应用
  ↓ localhost
Zotero 插件 bridge
  ↓
Zotero JavaScript API
  ↓
本地 Zotero library

不允许：

- 直接写 zotero.sqlite；
- 在用户未确认时自动删除条目；
- 以 Zotero collection 作为真实文件移动逻辑；
- 在身份不确定时自动创建新条目。

Zotero 插件可在桌面端内部调用 JavaScript API；官方也明确指出直接访问本地 SQLite 更脆弱。(Zotero⁠￼)

17.2 Collection 映射

推荐 collection：

AI Inbox
Core Reading
AI Briefing Queue
Citation / Background
Archive
Needs Review
Duplicate / Version Review

17.3 Tag 映射

ai-status:core-reading
ai-status:briefing
ai-status:archive
ai-value:high
ai-value:medium
ai-value:low
ai-model:flagship
ai-model:balanced
ai-domain:vla
ai-domain:dexterous-manipulation
ai-domain:active-slam
ai-source:deep-research
ai-source:manual
ai-source:zotero
ai-confidence:high
ai-review-date:2026-06-28

17.4 Note 模板

# AI Triage
## User decision
AI Briefing Queue
## Identity
- Canonical DOI:
- arXiv:
- Version:
- Match confidence:
## Original recommendation context
- Source:
- Role:
- Original rationale:
## AI verdict
- Paper value:
- Reading mode:
- Recommended time budget:
- Confidence:
## Why it matters
...
## Risks and limitations
...
## Relevance to current projects
...
## Evidence map
- Page:
- Section:
- Figure/Table:
- Excerpt:
## Model provenance
- Model tier:
- Model ID:
- Prompt version:
- Date:

⸻

18. 数据模型

18.1 CanonicalPaper

{
  "paper_id": "uuid",
  "work_family_id": "uuid",
  "canonical_identifier": "doi:10.xxxx/xxxx",
  "title": "...",
  "authors": [],
  "year": 2026,
  "venue": "...",
  "identifiers": {
    "doi": "...",
    "arxiv_id": "...",
    "openalex_id": "...",
    "semantic_scholar_id": "..."
  },
  "versions": [],
  "metadata_sources": [],
  "pdf_sources": [],
  "identity_confidence": 0.97,
  "zotero": {
    "item_key": null,
    "duplicate_status": "new | existing | suspected_duplicate"
  }
}

18.2 ReviewDecision

{
  "paper_id": "uuid",
  "paper_value": "high | medium | low | uncertain",
  "reading_mode": "self_read | ai_substitute | skim | archive",
  "analysis_depth": "none | light | standard | deep",
  "model_tier": "cheap | balanced | flagship | manual",
  "user_decision": "confirmed",
  "decision_reason": "...",
  "created_at": "..."
}

18.3 AnalysisRecord

{
  "analysis_id": "uuid",
  "paper_id": "uuid",
  "task_type": "triage | factual_card | deep_brief | qa | comparison",
  "model_id": "...",
  "model_tier": "flagship",
  "input_manifest": {
    "sections": ["abstract", "method", "experiments"],
    "pages": [1, 2, 3, 4],
    "profile_version": "..."
  },
  "output": {},
  "evidence_map": [],
  "cost": {
    "input_tokens": 0,
    "output_tokens": 0,
    "tool_calls": 0,
    "estimated_usd": 0
  },
  "prompt_version": "..."
}

⸻

19. 成本控制

19.1 成本规则

- 不对低价值论文执行 PDF 深读；
- 不对高价值论文默认生成替读报告；
- 所有论文先走 metadata + abstract 粗筛；
- 旗舰模型只处理用户确认的中等价值论文；
- 同一 PDF 的结构化解析结果永久缓存；
- 同一论文不同版本共享部分分析结果；
- 用户每次触发前看到预计费用；
- 支持批处理与预算上限。

19.2 批量任务预算

用户可以设定：

budget:
  max_usd_per_import: 3.0
  max_flagship_papers: 5
  max_balanced_papers: 20
  allow_web_search_fallback: true
  require_confirmation_before_flagship: true

19.3 降级策略

当预算耗尽：

Flagship deep brief
  ↓
Balanced research summary
  ↓
Cheap factual card
  ↓
Metadata only

不会静默超预算。

⸻

20. 可靠性与可审计性

20.1 所有判断必须可追溯

每个关键结论保存：

- 输入来源；
- metadata source；
- PDF 版本；
- 证据页码；
- 模型与模型版本；
- prompt version；
- token 与费用；
- 用户最终决策；
- Zotero 写入记录。

20.2 不确定性原则

系统必须明确标记：

Unknown
Ambiguous
Needs human review
Insufficient evidence
PDF unavailable
Version conflict

不允许模型用自然语言掩盖证据不足。

20.3 自动化边界

默认不自动执行：

- 删除 Zotero 条目；
- 覆盖用户手写 note；
- 覆盖用户已有 tags；
- 将疑似重复条目合并；
- 将低置信度论文写入核心 collection；
- 下载非开放或受限 PDF。

⸻

21. MVP 范围

21.1 第一阶段：可用闭环

输入：
- DOI
- BibTeX
- 标题
- 本地 PDF
- Markdown reading list
解析：
- Crossref
- OpenAlex
- Semantic Scholar
- OpenAI web search fallback
处理：
- identity matching
- candidate disambiguation
- Zotero duplicate check
- PDF upload / local parse
- cheap triage
- manual review
- one flagship deep brief for selected papers
输出：
- local paper card
- structured report
- Zotero note/tags/collection write-back

21.2 第二阶段：批量工作流

- Deep Research text importer
- Share Link best-effort importer
- PDF auto-discovery through OA sources
- version family management
- budget dashboard
- batch processing
- browser extension
- cross-paper comparison

21.3 第三阶段：研究助手能力

- 从已有 Zotero 库学习偏好；
- 发现与当前项目最接近的论文；
- 自动推荐 related-work cluster；
- 发现缺失 baseline；
- 对多个论文生成技术谱系；
- 自动构建项目级 literature map。

⸻

22. 最小 API 设计

导入

POST /api/imports
{
  "source_type": "doi | bibtex | title | pdf | markdown | chatgpt_share",
  "content": "...",
  "profile_id": "default",
  "options": {
    "allow_web_search": true,
    "auto_find_open_pdf": true,
    "zotero_dedup": true
  }
}

获取候选

GET /api/imports/{import_id}/candidates

用户确认候选

POST /api/papers/{paper_id}/confirm-identity
{
  "candidate_id": "uuid",
  "version_policy": "canonical | keep_both | merge_family"
}

设置人工决策

POST /api/papers/{paper_id}/decision
{
  "paper_value": "medium",
  "reading_mode": "ai_substitute",
  "analysis_depth": "deep",
  "model_tier": "flagship"
}

触发分析

POST /api/papers/{paper_id}/analyze
{
  "task_type": "deep_brief",
  "model_tier": "flagship",
  "budget_cap_usd": 0.5
}

写入 Zotero

POST /api/papers/{paper_id}/zotero/write
{
  "collection": "AI Briefing Queue",
  "tags": [
    "ai-value:medium",
    "ai-status:briefing"
  ],
  "write_note": true,
  "attach_pdf": true
}

⸻

23. 产品成功标准

功能指标

- DOI 输入自动识别成功率；
- 标题输入 Top-1 identity accuracy；
- 低置信度论文进入人工复核的召回率；
- Zotero 重复条目误创建率；
- PDF 标题与论文身份一致率；
- 深度报告带 evidence map 的比例；
- 用户对“是否值得读”的人工修正率。

用户价值指标

- 每批 20 篇引用中，用户进入 Core Reading 的论文数；
- 每批中 AI Briefing Queue 的论文数；
- 用户实际打开原始 PDF 的比例；
- 用户从 AI Briefing 升级到精读的比例；
- 用户保留 AI note 并用于写作/related work 的比例；
- 每篇论文平均人工处理时间下降量。

⸻

24. 核心产品原则

1. 先验证身份，再理解内容。
2. 论文价值与 AI 总结深度必须分离。
3. 高价值论文优先保留给用户亲自阅读。
4. 中等价值论文是旗舰模型深度替读的主要对象。
5. 低价值论文不应消耗 PDF 解析和旗舰模型成本。
6. 所有模型结论必须能回到原文证据。
7. Zotero 是输出端和长期库，不是整个智能工作流的执行引擎。
8. 所有写入默认可逆、可审计、可人工确认。
9. Share Link 是可选导入入口，不是可靠 API 依赖。
10. 本地优先，用户的 PDF、研究兴趣、Zotero 库与审阅记录应由用户掌控。

OpenAI 侧建议使用 Responses API：web search 用于模糊标题、版本关系与网页证据兜底；structured outputs 用于让匹配结果、筛选结论、报告和 Zotero 写入计划都强制落到 JSON schema；PDF 处理则以本地解析为主，必要时才发送精选内容给模型。 