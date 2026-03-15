<div align="center">
  <img src="assets/SVG/Square.svg" width="120" alt="ValiRef Logo" />
  <h1>ValiRef</h1>
  <p><strong>AI驱动的学术论文引用验证工具</strong></p>
  <p>
    <a href="#功能特性">功能特性</a> •
    <a href="#安装">安装</a> •
    <a href="#使用方法">使用方法</a> •
    <a href="#工作原理">工作原理</a> •
    <a href="#基准测试">基准测试</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT" />
    <img src="https://img.shields.io/badge/async-first-purple.svg" alt="Async First" />
  </p>
</div>

---

## 概述

ValiRef 是一款用于检测学术论文中**幻觉引用**的智能工具。随着 AI 生成内容的兴起，大语言模型（LLM）有时会生成听起来合理但实际上并不存在的参考文献。ValiRef 帮助研究人员、审稿人和出版商验证 PDF 文档中引用的真实性。

### ValiRef 检测的幻觉类型

| 幻觉类型 | 描述 | 示例 |
|-------------------|-------------|---------|
| 🔮 **完全伪造** | 完全虚假的论文，不存在 | 标题令人信服但实际从未发表的论文 |
| 👤 **作者归属错误** | 论文真实，但作者错误 | 将 "Attention is All You Need" 的作者归为 Vaswani 等人以外的其他人 |
| 📄 **内容不相关** | 论文真实，但引用内容与论文实际内容不符 | 在计算机视觉相关论述中引用 NLP 论文 |
| 🔄 **结论相反** | 论文真实，但引用的结论与论文实际结论相反 | 声称某论文支持观点 X，而实际上该论文反对观点 X |

---

## 功能特性

- 🔍 **多源验证** - 交叉验证 ArXiv、Google Scholar、Semantic Scholar、OpenReview、OpenAlex 和 DuckDuckGo 的引用
- 🤖 **AI 驱动检测** - 使用 DeepSeek LLM 结合 ReAct 推理分析搜索结果
- ⚡ **异步优先架构** - 并发验证多个参考文献，实现最佳性能
- 📊 **丰富的 CLI 输出** - 精美的终端界面，包含进度条、实时指标和详细报告
- 📈 **基准测试套件** - 内置数据集生成和评估框架
- 🛡️ **弹性 API 处理** - 令牌桶速率限制 + 熔断器模式，确保外部 API 调用可靠
- 🎯 **高准确率** - 在 1000 样本基准测试中达到 88%+ 的准确率，包含置信度评分和详细推理

---

## 安装

### 环境要求

- Python 3.12 或更高版本
- [uv](https://docs.astral.sh/uv/) 包管理器（推荐）或 pip

### 从 PyPI 安装（推荐）

```bash
pip install valiref
```

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/Gianthard-cyh/ValiRef.git
cd ValiRef

# 安装依赖
uv sync

# 设置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 DeepSeek API 密钥
```

### 环境配置

创建 `.env` 文件并添加你的 API 密钥：

```bash
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 可选：用于增强搜索功能
SERPAPI_API_KEY=your_serpapi_key
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_key

# 可选：LangSmith 追踪
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your_langchain_key
LANGCHAIN_PROJECT=ValiRef
```

---

## 使用方法

### 验证 PDF 中的参考文献

```bash
# 基本用法
uv run python -m src.cli validate paper.pdf

# 指定并发工作线程数（默认：5）
uv run python -m src.cli validate paper.pdf --workers 10

# 输出为 JSON 格式
uv run python -m src.cli validate paper.pdf --json

# 启用详细日志
uv run python -m src.cli validate paper.pdf --verbose
```

### 示例输出

```
Validation Summary for paper.pdf
Total References: 12
Validated: 12
Duration: 15.34s

┌─────────────────────────────────────────────────────────────────────┐
│ ✅ Reference #1 - REAL REFERENCE                                    │
├─────────────────────────────────────────────────────────────────────┤
│ Title: Attention Is All You Need                                    │
│ Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar, et al.          │
│ Confidence: 0.98                                                    │
│                                                                     │
│ Reasoning:                                                          │
│ Found exact match on ArXiv (arxiv.org/abs/1706.03762). Title,       │
│ authors, and venue (NIPS 2017) all match the citation.              │
│                                                                     │
│ Evidence / Sources:                                                 │
│ - https://arxiv.org/abs/1706.03762                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 工作原理

ValiRef 采用复杂的多步骤验证流程：

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  PDF 输入   │ →  │   提取引用   │ →  │   多源搜索   │ →  │  LLM 验证   │
│             │    │              │    │              │    │             │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
                                                              │
                                                              ▼
                                                        ┌─────────────┐
                                                        │   生成报告  │
                                                        │             │
                                                        └─────────────┘
```

### 1. 引用提取
- 使用 PyMuPDF 解析 PDF 文档
- 使用 LLM 智能地从参考文献部分提取结构化引用数据
- 支持多种引用格式（APA、MLA、Chicago 等）

### 2. 多源搜索
同时查询多个学术数据库：
- **ArXiv** - 预印本服务器，提供全文访问
- **Google Scholar** - 广泛的学术搜索
- **Semantic Scholar** - AI 驱动的学术搜索
- **OpenReview** - 同行评审会议论文
- **OpenAlex** - 开放学术图谱
- **DuckDuckGo** - 网页搜索备用方案

### 3. AI 验证
HallucinationDetector 使用由 DeepSeek LLM 驱动的 ReAct（推理+行动）智能体：
- 分析来自所有来源的搜索结果
- 比较论文元数据（标题、作者、摘要、发表 venue）
- 评估引用内容与论文实际内容的一致性
- 提供带详细推理的置信度评分

### 弹性 API 架构

ValiRef 为外部 API 调用实现了生产级的弹性层：

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  搜索工具   │────▶│   工具请求队列  │────▶│    令牌桶       │
│ (按来源划分)│     │   (速率限制器)  │     │  (平滑流量)     │
└─────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │     熔断器      │
                     │  (不健康 API   │
                     │   快速失败)    │
                     └─────────────────┘
```

**特性：**
- **令牌桶速率限制** - 平滑请求流，每个来源可配置突发容量
- **熔断器模式** - 自动停止向故障服务发送请求（3 次失败 → 熔断，15 秒恢复超时）
- **实时指标** - 通过 blinker 信号实时显示 API 调用统计、活动请求和熔断状态
- **优雅降级** - 失败的来源会被标记为不可用，但不会阻塞其他来源

---

## 基准测试

ValiRef 包含用于评估幻觉检测性能的综合基准测试套件。

### 性能结果

在 1000 样本混合数据集上（本地搜索模式）：

| 指标 | 数值 |
|--------|-------|
| **准确率** | 88.1% |
| **宏平均精确率** | 0.9037 |
| **宏平均召回率** | 0.8748 |
| **宏平均 F1** | 0.8622 |
| **加权 F1** | 0.8659 |
| **吞吐量** | ~1.01 样本/秒 |
| **耗时** | ~16.5 分钟（1000 样本） |

### 各类型性能

| 幻觉类型 | 精确率 | 召回率 | F1 分数 | 样本数 |
|-------------------|-----------|--------|----------|---------|
| 真实论文 | 0.7528 | 0.9710 | 0.8481 | 207 |
| 完全伪造 | 0.9509 | 1.0000 | 0.9748 | 213 |
| 作者归属错误 | 0.9849 | 0.9899 | 0.9874 | 198 |
| 内容不相关 | 0.8297 | 0.9845 | 0.9005 | 193 |
| 结论相反 | 1.0000 | 0.4286 | 0.6000 | 189 |

### 生成基准数据集

```bash
uv run python scripts/generate_dataset.py \
  --topic cs.CL \
  --count 1000 \
  --output data/dataset.csv
```

### 数据集组成

基准数据集结合真实 ArXiv 论文和合成幻觉数据：

| 类别 | 描述 | 占比 |
|----------|-------------|------------|
| 真实论文 | 来自 ArXiv 的真实论文 | 50% |
| 完全伪造 | AI 生成的虚假论文 | 12.5% |
| 作者归属错误 | 作者错误的真实论文 | 12.5% |
| 内容不相关 | 引用内容与论文内容不匹配的真实论文 | 12.5% |
| 结论相反 | 引用结论与论文结论相反的真实论文 | 12.5% |

### 运行测试

```bash
# 运行单元测试（快速，不调用外部 API）
uv run pytest

# 运行集成测试（较慢，需要 API 密钥）
uv run pytest -m integration

# 运行特定测试
uv run pytest tests/core/test_tools.py -v
```

---

## 架构

```
valiref/
├── src/
│   ├── cli.py                 # 基于 Typer 的 CLI 界面
│   ├── cli_callbacks.py       # 进度回调和实时显示
│   ├── core/                  # 核心验证引擎
│   │   ├── pipeline.py        # 异步验证编排
│   │   ├── detector.py        # 基于 LLM 的幻觉检测
│   │   ├── extract.py         # PDF/文本提取
│   │   ├── tools.py           # 带速率限制的学术搜索工具
│   │   ├── search_queue.py    # 令牌桶 + 熔断器
│   │   ├── tool_monitor.py    # 通过 blinker 信号实现实时指标
│   │   ├── config.py          # 配置管理
│   │   └── logger.py          # 基于 Rich 的日志
│   ├── bench/                 # 基准测试框架
│   │   ├── crawler.py         # ArXiv 论文爬虫
│   │   ├── dataset.py         # 幻觉注入
│   │   ├── bench.py           # 带实时指标的基准测试运行器
│   │   └── schema.py          # Pydantic 数据模型
│   └── api/                   # API 接口（未来）
├── scripts/
│   └── generate_dataset.py    # 数据集生成脚本
├── tests/                     # 测试套件
└── data/                      # 基准数据集
```

---

## 配置

`src/core/config.py` 中的关键设置：

| 设置 | 默认值 | 描述 |
|---------|---------|-------------|
| `LLM_MODEL` | deepseek-chat | 用于验证的 LLM |
| `LLM_TEMPERATURE` | 0.7 | 创造性 vs 确定性 |
| `DETECTOR_TEMPERATURE` | 0.1 | 推理一致性（较低更稳定） |
| `EXTRACTION_CHAR_LIMIT` | 20000 | PDF 参考文献最大字符数 |
| `MAX_WORKERS` | 5 | 并发验证线程数 |

---

## 参与贡献

欢迎贡献！请随时提交 Pull Request。

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

### 开发环境设置

```bash
# 安装开发依赖
uv sync --dev

# 运行代码检查
uv run ruff check .
uv run ruff format .

# 运行测试
uv run pytest
```

---

## 许可证

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

---

## 致谢

- 使用 [LangChain](https://github.com/langchain-ai/langchain) 和 [LangGraph](https://github.com/langchain-ai/langgraph) 构建
- 由 [DeepSeek](https://deepseek.com/) LLM 提供支持
- 学术搜索来自 [ArXiv](https://arxiv.org/)、[Semantic Scholar](https://www.semanticscholar.org/)、[OpenReview](https://openreview.net/) 和 [OpenAlex](https://openalex.org/)
- CLI 由 [Typer](https://typer.tiangolo.com/) 和 [Rich](https://github.com/Textualize/rich) 提供支持

---

<div align="center">
  <p>
    <sub>Built with ❤️ for the research community</sub>
  </p>
</div>
