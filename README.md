<div align="center">
  <img src="assets/SVG/Square.svg" width="120" alt="ValiRef Logo" />
  <h1>ValiRef</h1>
  <p><strong>AI-Powered Citation Validation for Academic Papers</strong></p>
  <p>
    <a href="#features">Features</a> •
    <a href="#installation">Installation</a> •
    <a href="#usage">Usage</a> •
    <a href="#how-it-works">How It Works</a> •
    <a href="#benchmark">Benchmark</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT" />
    <img src="https://img.shields.io/badge/async-first-purple.svg" alt="Async First" />
  </p>
</div>

---

## Overview

ValiRef is an intelligent tool designed to detect **hallucinated citations** in academic papers. With the rise of AI-generated content, Large Language Models (LLMs) sometimes generate plausible-sounding but non-existent references. ValiRef helps researchers, reviewers, and publishers verify the authenticity of citations in PDF documents.

### What ValiRef Detects

| Hallucination Type | Description | Example |
|-------------------|-------------|---------|
| 🔮 **Fabrication** | Completely fake paper that doesn't exist | A paper with a convincing title but no actual publication |
| 👤 **Attribution Error** | Real paper, wrong authors | Citing "Attention is All You Need" by someone other than Vaswani et al. |
| 📄 **Irrelevance** | Real paper, but claim doesn't match content | Citing a paper about NLP for a claim about computer vision |
| 🔄 **Counterfactual** | Real paper, opposite conclusion | Claiming a paper supports X when it actually argues against X |

---

## Features

- 🔍 **Multi-Source Verification** - Cross-references citations against ArXiv, Google Scholar, Semantic Scholar, OpenReview, OpenAlex, and DuckDuckGo
- 🤖 **AI-Powered Detection** - Uses DeepSeek LLM with ReAct reasoning to analyze search results
- ⚡ **Async-First Architecture** - Concurrent validation of multiple references for optimal performance
- 📊 **Rich CLI Output** - Beautiful terminal interface with progress bars and detailed reports
- 📈 **Benchmark Suite** - Built-in dataset generation and evaluation framework
- 🛡️ **Rate Limiting** - Respects API limits with intelligent retry logic
- 🎯 **High Accuracy** - Confidence scoring with detailed reasoning for each validation

---

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/valiref.git
cd valiref

# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add your DeepSeek API key
```

### Environment Configuration

Create a `.env` file with your API keys:

```bash
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Optional: for enhanced search capabilities
SERPAPI_API_KEY=your_serpapi_key
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_key

# Optional: LangSmith tracing
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your_langchain_key
LANGCHAIN_PROJECT=ValiRef
```

---

## Usage

### Validate References in a PDF

```bash
# Basic usage
uv run python main.py validate paper.pdf

# With concurrent workers (default: 5)
uv run python main.py validate paper.pdf --workers 10

# Output as JSON
uv run python main.py validate paper.pdf --json

# Enable verbose logging
uv run python main.py validate paper.pdf --verbose
```

### Example Output

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

## How It Works

ValiRef employs a sophisticated multi-step validation pipeline:

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  PDF Input  │ →  │   Extract    │ →  │    Search    │ →  │   Validate  │
│             │    │  References  │    │  Multi-Source│    │  with LLM   │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
                                                              │
                                                              ▼
                                                        ┌─────────────┐
                                                        │   Report    │
                                                        │  Results    │
                                                        └─────────────┘
```

### 1. Reference Extraction
- Parses PDF documents using PyMuPDF
- Uses LLM to intelligently extract structured reference data from bibliography sections
- Handles various citation formats (APA, MLA, Chicago, etc.)

### 2. Multi-Source Search
Simultaneously queries multiple academic databases:
- **ArXiv** - Preprint server with full-text access
- **Google Scholar** - Broad academic search
- **Semantic Scholar** - AI-powered academic search
- **OpenReview** - Peer-reviewed conference papers
- **OpenAlex** - Open academic graph
- **DuckDuckGo** - Web search fallback

### 3. AI Validation
The HallucinationDetector uses a ReAct (Reasoning + Acting) agent powered by DeepSeek LLM:
- Analyzes search results from all sources
- Compares paper metadata (title, authors, abstract, venue)
- Evaluates claims against actual paper content
- Provides confidence scores with detailed reasoning

### 4. Concurrent Processing
- Async/await throughout for non-blocking I/O
- Semaphore-controlled concurrency (configurable workers)
- Rate limiting per source to respect API constraints

---

## Benchmark

ValiRef includes a comprehensive benchmark suite for evaluating hallucination detection performance.

### Generate Benchmark Dataset

```bash
uv run python scripts/generate_dataset.py \
  --topic cs.CL \
  --count 1000 \
  --output data/dataset.csv
```

### Dataset Composition

The benchmark dataset combines real ArXiv papers with synthetic hallucinations:

| Category | Description | Percentage |
|----------|-------------|------------|
| Real | Genuine papers from ArXiv | 50% |
| Fabrication | AI-generated fake papers | 12.5% |
| Attribution Error | Real papers with wrong authors | 12.5% |
| Irrelevance | Real papers with mismatched claims | 12.5% |
| Counterfactual | Real papers with inverted claims | 12.5% |

### Running Tests

```bash
# Run unit tests (fast, no external APIs)
uv run pytest

# Run integration tests (slow, requires API keys)
uv run pytest -m integration

# Run specific test
uv run pytest tests/core/test_tools.py -v
```

---

## Architecture

```
valiref/
├── src/
│   ├── cli.py                 # Typer-based CLI interface
│   ├── cli_callbacks.py       # Progress callbacks
│   ├── core/                  # Core validation engine
│   │   ├── pipeline.py        # Async validation orchestration
│   │   ├── detector.py        # LLM-based hallucination detection
│   │   ├── extract.py         # PDF/text extraction
│   │   ├── tools.py           # Academic search tools
│   │   ├── config.py          # Configuration management
│   │   └── logger.py          # Rich-based logging
│   ├── bench/                 # Benchmark framework
│   │   ├── crawler.py         # ArXiv paper crawler
│   │   ├── dataset.py         # Hallucination injection
│   │   └── schema.py          # Pydantic data models
│   └── api/                   # API interface (future)
├── scripts/
│   └── generate_dataset.py    # Dataset generation script
└── tests/                     # Test suite
```

---

## Configuration

Key settings in `src/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_MODEL` | deepseek-chat | LLM for validation |
| `LLM_TEMPERATURE` | 0.7 | Creativity vs determinism |
| `DETECTOR_TEMPERATURE` | 0.1 | Lower for consistent reasoning |
| `EXTRACTION_CHAR_LIMIT` | 20000 | Max chars from PDF references |
| `MAX_WORKERS` | 5 | Concurrent validation threads |

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
uv sync --dev

# Run linting
uv run ruff check .
uv run ruff format .

# Run tests
uv run pytest
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Built with [LangChain](https://github.com/langchain-ai/langchain) and [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by [DeepSeek](https://deepseek.com/) LLM
- Academic search via [ArXiv](https://arxiv.org/), [Semantic Scholar](https://www.semanticscholar.org/), [OpenReview](https://openreview.net/), and [OpenAlex](https://openalex.org/)
- CLI powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://github.com/Textualize/rich)

---

<div align="center">
  <p>
    <sub>Built with ❤️ for the research community</sub>
  </p>
</div>
