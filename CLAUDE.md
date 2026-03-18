# ValiRef 项目备忘

## 项目管理

- **包管理器**: uv (不是pip)
- **添加依赖**: `uv add <package>`
- **运行**: `uv run python -m src.cli ...`

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (src/cli.py)                     │
│              validate / benchmark / version                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ValidationPipeline (src/core/pipeline.py)     │
│   1. 提取PDF引用 → 2.并发验证引用 → 3.汇总结果               │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          ▼                                       ▼
┌─────────────────────┐               ┌─────────────────────┐
│  PDFExtractor      │               │ HallucinationDetector│
│  (src/core/extract)│               │   (src/core/detector)│
└─────────────────────┘               └─────────────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    ReAct Agent (LangChain)   │
                                  │  LLM: DeepSeek + Tool Calls  │
                                  └─────────────────────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │   AggregateSearch (tools.py) │
                                  │  arxiv | openalex | openreview│
                                  │  duckduckgo | ...            │
                                  └─────────────────────────────┘
```

## 核心模块

### 1. 引用验证流程

- `src/core/pipeline.py` - ValidationPipeline: 主编排器，管理提取和验证流程
- `src/core/extract.py` - PDFExtractor: 从PDF提取参考文献
- `src/core/detector.py` - HallucinationDetector: 使用ReAct Agent检测幻觉引用

### 2. 搜索工具 (src/core/tools.py)

- `SearchTool` - 基类，集成限流+熔断+监控
- `ArxivSearch`, `OpenAlexSearch`, `OpenReviewSearch`, `DuckDuckGoSearch`
- `AggregateSearch` - 并发查询多个数据源，结果去重

### 3. API韧性 (src/core/search_queue.py)

- `TokenBucket` - 令牌桶限流，平滑请求速率
- `CircuitBreaker` - 熔断器模式 (CLOSED/HALF_OPEN/OPEN)
- `ToolRequestQueue` - 每工具独立的请求队列

### 4. 工具监控 (src/core/tool_monitor.py)

- 使用 **blinker** 信号发布订阅
- `tool_call_started` / `tool_call_ended` 信号
- `ToolMetricsCollector` - 收集统计：调用次数、成功率、平均延迟、并发数、调用速率
- Rich Live 实时显示工具指标

### 5. CLI回调 (src/cli_callbacks.py)

- `CliCallback` - Rich 进度条 + 实时工具指标显示

### 6. Benchmark (src/bench/bench.py)

- `BenchmarkRunner` - 评估幻觉检测性能
- 计算 Accuracy/Precision/Recall/F1，按幻觉类型分类统计

## 依赖库

- **LLM**: langchain-deepseek (DeepSeek API)
- **搜索**: httpx (异步HTTP), duckduckgo-search, semanticscholar, scholarly, openalex
- **PDF**: pypdf
- **UI**: typer (CLI), rich (终端UI/Live显示)
- **事件**: blinker (信号系统)
- **观测**: langsmith (可选)

## CLI命令

```bash
# 验证PDF中的引用
uv run python -m src.cli validate paper.pdf -w 5 --metrics

# 运行基准测试
uv run python -m src.cli benchmark dataset.csv -w 5 -o results.json

# 查看版本
uv run python -m src.cli version
```

## 开发工作流

由于benchmark可能正在运行，使用worktree：

```bash
# 创建worktree
git worktree add ../ValiRef-dev <branch-name>
cd ../ValiRef-dev

# 开发完成后
cd /home/cyh/ValiRef
git worktree remove ValiRef-dev
```

## 配置项 (src/core/config.py)

- LLM: `LLM_MODEL`, `DETECTOR_TEMPERATURE`, `LLM_TIMEOUT`
- 限流: `TOKEN_BUCKET_RATE_*` 各数据源速率
- 熔断: `CIRCUIT_BREAKER_*` 阈值和超时

## 架构原则

- 使用 **blinker** 进行事件发布订阅
- 使用 **Rich Live** 进行实时监控展示
- 每个工具独立限流+熔断，避免单点故障影响全局
- 信号驱动的监控，无需持有工具实例引用
- 优先使用成熟开源方案，不造轮子
- 不要编写过度的兜底代码，不要过度防御性编程。对于超出期望的数据应当直接抛出错误，打出日志方便后续定位。
- 遵循KISS原则，Keep it simple, stupid，不要有过度的抽象
- 仅保留文档性注释，保持核心代码简洁，自解释，代码即文档
- 控制流反转原则。
- 在每个需求完成后运行回归测试并添加单测
- 在计划时向用户简要介绍计划添加的单测用例
